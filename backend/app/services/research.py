"""Research pipeline orchestrating search and LLM analysis."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable
from sqlalchemy.orm import Session

from ..models import ResearchJob, Company, JobStatus, CompanyStatus
from .search import get_search_service
from .llm import get_llm_service

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """Orchestrates the company research process."""

    def __init__(self):
        self.search_service = get_search_service()
        self.llm_service = get_llm_service()
        self._running_tasks: dict[int, asyncio.Task] = {}  # Track running tasks for proper cancellation
    
    async def process_company(self, company: Company, db: Session) -> bool:
        """
        Process a single company through the research pipeline.
        
        Args:
            company: Company model instance
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update status to researching
            company.status = CompanyStatus.RESEARCHING.value
            db.commit()
            
            logger.info(f"Starting research for: {company.name}")
            
            # Step 1: Search for company information
            search_results = await self.search_service.search_company(company.name)
            company.search_results_raw = json.dumps(search_results.get("raw_response", {}))

            # Store Tavily cost data
            company.tavily_credits_used = search_results.get("credits_used", 0.0)
            company.tavily_response_time = search_results.get("response_time")

            if not search_results.get("success"):
                company.status = CompanyStatus.FAILED.value
                company.error_message = f"Search failed: {search_results.get('error', 'Unknown error')}"
                db.commit()
                return False

            # Step 2: Format search results for LLM
            formatted_results = self.search_service.format_search_results_for_llm(search_results)

            # Step 3: Analyze with LLM
            analysis = await self.llm_service.analyze_company(company.name, formatted_results)
            company.llm_response_raw = analysis.get("raw_response", "")

            # Store LLM usage data
            company.llm_tokens_used = analysis.get("tokens_used", 0)
            company.llm_response_time = analysis.get("response_time")

            if not analysis.get("success"):
                company.status = CompanyStatus.FAILED.value
                company.error_message = f"Analysis failed: {analysis.get('error', 'Unknown error')}"
                db.commit()
                return False

            # Step 4: Store results
            self._store_analysis_results(company, analysis)
            company.status = CompanyStatus.COMPLETED.value
            company.researched_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Completed research for {company.name}: {company.priority_tier} ({company.score_total} pts)")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {company.name}: {str(e)}")
            company.status = CompanyStatus.FAILED.value
            company.error_message = str(e)
            db.commit()
            return False
    
    def _store_analysis_results(self, company: Company, analysis: dict):
        """Store analysis results in the company record."""
        research = analysis.get("research", {})
        gpu_analysis = analysis.get("gpu_analysis", {})
        scores = analysis.get("scores", {})
        
        # Research data
        company.description = research.get("description")
        company.employee_count = str(research.get("employee_count", ""))
        company.employee_range = research.get("employee_range")
        company.total_funding = research.get("total_funding")
        company.funding_millions = research.get("funding_millions")
        company.last_round = research.get("last_round")
        company.investors = json.dumps(research.get("investors", []))
        company.headquarters = research.get("headquarters")
        company.founded_year = research.get("founded_year") if isinstance(research.get("founded_year"), int) else None
        company.industry = research.get("industry")
        company.business_model = research.get("business_model")
        
        # GPU Analysis
        company.gpu_use_case_tier = gpu_analysis.get("use_case_tier")
        company.gpu_use_case_label = gpu_analysis.get("use_case_label")
        company.gpu_analysis_reasoning = gpu_analysis.get("reasoning")
        company.signals_positive = json.dumps(gpu_analysis.get("signals_positive", []))
        company.signals_negative = json.dumps(gpu_analysis.get("signals_negative", []))
        
        # Scores
        company.score_gpu_use_case = scores.get("gpu_use_case", 0)
        company.score_scale_budget = scores.get("scale_budget", 0)
        company.score_growth_signals = scores.get("growth_signals", scores.get("timing_urgency", 0))
        company.score_confidence = scores.get("confidence", 0)
        company.score_total = scores.get("total", 0)
        
        # Classification
        company.priority_tier = analysis.get("priority_tier")
        company.recommended_action = analysis.get("recommended_action")
    
    async def run_job_batched(
        self,
        job_id: int,
        db_factory: Callable,
        batch_size: int = 50,
        tavily_concurrency: int = 100
    ):
        """
        Run a complete research job with parallel batch processing (MUCH FASTER).
        
        Two-phase approach:
        1. Fetch ALL Tavily data in parallel (seconds, not minutes)
        2. Process LLM requests in batches (parallel within batch)
        
        Args:
            job_id: ID of the ResearchJob to process
            db_factory: Factory function to create new database sessions
            batch_size: Number of concurrent LLM requests per batch
            tavily_concurrency: Number of concurrent Tavily searches
        """
        db = db_factory()
        
        try:
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            # Update job status
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()
            
            # Get pending companies
            pending_companies = db.query(Company).filter(
                Company.job_id == job_id,
                Company.status == CompanyStatus.PENDING.value
            ).all()
            
            total = len(pending_companies)
            logger.info(f"Starting BATCHED job {job_id} with {total} companies (batch_size={batch_size})")
            
            # ============================================================
            # PHASE 1: Fetch ALL Tavily data in parallel
            # ============================================================
            logger.info(f"PHASE 1: Fetching Tavily data for {total} companies in parallel...")
            phase1_start = datetime.utcnow()
            
            async def fetch_tavily(company: Company):
                """Fetch Tavily data for a single company with caching support."""
                from ..config import get_settings
                settings = get_settings()
                
                try:
                    # Check cache first if caching is enabled
                    if settings.enable_tavily_caching and company.tavily_data_cached and company.tavily_data_verified:
                        logger.info(f"💾 Cache HIT: {company.name} (saved $0.016, ~3s)")
                        # Use cached data
                        if company.tavily_formatted_results:
                            company.status = CompanyStatus.RESEARCHING.value
                            return company, company.tavily_formatted_results, None
                    
                    # Cache miss - fetch from Tavily
                    company.status = CompanyStatus.RESEARCHING.value
                    
                    # Attempt fetch with retry if validation fails
                    max_retries = settings.tavily_max_validation_retries if settings.tavily_validation_enabled else 1
                    
                    for attempt in range(max_retries):
                        search_results = await self.search_service.search_company(company.name)
                        company.search_results_raw = json.dumps(search_results.get("raw_response", {}))
                        company.tavily_credits_used = search_results.get("credits_used", 0.0)
                        company.tavily_response_time = search_results.get("response_time")
                        
                        if not search_results.get("success"):
                            error_msg = f"Search failed: {search_results.get('error', 'Unknown error')}"
                            if attempt < max_retries - 1:
                                logger.warning(f"Retry {attempt + 1}/{max_retries} for {company.name}")
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                                continue
                            return company, None, error_msg
                        
                        formatted_results = self.search_service.format_search_results_for_llm(search_results)
                        
                        # Validate data quality if enabled
                        if settings.tavily_validation_enabled:
                            validation = await self.llm_service.validate_tavily_data(company.name, formatted_results)
                            company.tavily_validation_message = validation.get("message", "")
                            
                            if validation.get("is_valid") and validation.get("confidence", 0) >= settings.tavily_validation_threshold:
                                # Data is valid - cache it if caching enabled
                                if settings.enable_tavily_caching:
                                    company.tavily_data_cached = True
                                    company.tavily_data_verified = True
                                    company.tavily_cached_at = datetime.utcnow()
                                    company.tavily_formatted_results = formatted_results
                                    db.commit()  # Persist cache immediately
                                    logger.info(f"✓ {company.name}: Validated & cached (confidence: {validation['confidence']:.2f})")
                                return company, formatted_results, None
                            else:
                                # Data is invalid - retry if attempts remain
                                issues = ", ".join(validation.get("issues", []))
                                logger.warning(
                                    f"✗ {company.name}: Data invalid (confidence: {validation['confidence']:.2f}, "
                                    f"issues: {issues})"
                                )
                                if attempt < max_retries - 1:
                                    logger.info(f"Retrying Tavily fetch for {company.name}...")
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                
                                # Max retries reached with invalid data
                                company.tavily_data_verified = False
                                return company, None, f"Data validation failed: {validation['message']}"
                        else:
                            # Validation disabled - accept data and cache if enabled
                            if settings.enable_tavily_caching:
                                company.tavily_data_cached = True
                                company.tavily_data_verified = True  # Assumed valid
                                company.tavily_cached_at = datetime.utcnow()
                                company.tavily_formatted_results = formatted_results
                                company.tavily_validation_message = "Validation skipped (disabled)"
                                db.commit()
                            return company, formatted_results, None
                    
                    return company, None, "Max retries reached"
                    
                except Exception as e:
                    logger.error(f"Tavily fetch failed for {company.name}: {str(e)}")
                    return company, None, str(e)
            
            # Process Tavily in batches to avoid overwhelming the API
            tavily_results = []
            for i in range(0, total, tavily_concurrency):
                # Check for cancellation
                if asyncio.current_task().cancelled():
                    logger.info(f"Job {job_id} cancelled during Tavily phase")
                    job.status = JobStatus.CANCELLED.value
                    db.commit()
                    return
                
                batch = pending_companies[i:i+tavily_concurrency]
                batch_results = await asyncio.gather(*[fetch_tavily(c) for c in batch], return_exceptions=True)
                tavily_results.extend(batch_results)
                
                # Update progress
                logger.info(f"Tavily progress: {min(i+tavily_concurrency, total)}/{total} companies")
            
            phase1_duration = (datetime.utcnow() - phase1_start).total_seconds()
            
            # Calculate cache statistics
            cache_hits = sum(1 for c in pending_companies if c.tavily_data_cached and c.tavily_data_verified)
            cache_misses = total - cache_hits
            cost_saved = cache_hits * 0.016
            
            logger.info(
                f"PHASE 1 complete in {phase1_duration:.1f}s - "
                f"Cache: {cache_hits} hits, {cache_misses} misses "
                f"(saved ${cost_saved:.2f})"
            )
            
            # ============================================================
            # PHASE 2: Process LLM analysis in batches
            # ============================================================
            logger.info(f"PHASE 2: Analyzing {total} companies in batches of {batch_size}...")
            phase2_start = datetime.utcnow()
            
            async def analyze_company_data(company: Company, formatted_results: str):
                """Analyze a single company with LLM."""
                try:
                    if formatted_results is None:
                        return company, None, "Search failed"
                    
                    analysis = await self.llm_service.analyze_company(company.name, formatted_results)
                    company.llm_response_raw = analysis.get("raw_response", "")
                    company.llm_tokens_used = analysis.get("tokens_used", 0)
                    company.llm_response_time = analysis.get("response_time")
                    
                    if not analysis.get("success"):
                        return company, None, f"Analysis failed: {analysis.get('error', 'Unknown error')}"
                    
                    return company, analysis, None
                except Exception as e:
                    logger.error(f"LLM analysis failed for {company.name}: {str(e)}")
                    return company, None, str(e)
            
            # Process LLM in batches
            for batch_num, i in enumerate(range(0, total, batch_size), 1):
                # Check for cancellation
                if asyncio.current_task().cancelled():
                    logger.info(f"Job {job_id} cancelled during LLM phase")
                    job.status = JobStatus.CANCELLED.value
                    db.commit()
                    return
                
                batch_end = min(i + batch_size, total)
                logger.info(f"Processing LLM batch {batch_num}: companies {i+1}-{batch_end}/{total}")
                
                # Get batch data
                batch_data = tavily_results[i:batch_end]
                
                # Analyze batch in parallel
                analysis_tasks = []
                for result in batch_data:
                    if isinstance(result, tuple):
                        company, formatted_results, error = result
                        if error:
                            company.status = CompanyStatus.FAILED.value
                            company.error_message = error
                            job.failed_companies += 1
                        else:
                            analysis_tasks.append(analyze_company_data(company, formatted_results))
                
                # Wait for batch to complete
                if analysis_tasks:
                    batch_analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                    
                    # Store results
                    for result in batch_analyses:
                        if isinstance(result, tuple):
                            company, analysis, error = result
                            if error:
                                company.status = CompanyStatus.FAILED.value
                                company.error_message = error
                                job.failed_companies += 1
                            else:
                                self._store_analysis_results(company, analysis)
                                company.status = CompanyStatus.COMPLETED.value
                                company.researched_at = datetime.utcnow()
                                job.completed_companies += 1
                                logger.info(f"✓ {company.name}: {company.priority_tier} ({company.score_total} pts)")
                
                # Aggregate costs
                job.total_tavily_credits = sum(c.tavily_credits_used or 0.0 for c in pending_companies)
                from ..utils import estimate_tavily_cost
                job.total_cost_usd = estimate_tavily_cost(job.total_tavily_credits)
                job.last_activity_at = datetime.utcnow()
                
                # Commit after each batch
                db.commit()
                
                logger.info(f"Batch {batch_num} complete: {job.completed_companies}/{total} successful, {job.failed_companies} failed")
            
            phase2_duration = (datetime.utcnow() - phase2_start).total_seconds()
            total_duration = phase1_duration + phase2_duration
            
            # Job complete
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(
                f"Job {job_id} COMPLETE in {total_duration:.1f}s "
                f"(Tavily: {phase1_duration:.1f}s, LLM: {phase2_duration:.1f}s) - "
                f"{job.completed_companies} successful, {job.failed_companies} failed"
            )
        
        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if job:
                job.status = JobStatus.CANCELLED.value
                db.commit()
            raise
        
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                db.commit()
        
        finally:
            self._running_tasks.pop(job_id, None)
            db.close()
    
    async def run_job(
        self,
        job_id: int,
        db_factory: Callable,
        delay_between_companies: float = 1.0
    ):
        """
        Run a complete research job.

        Args:
            job_id: ID of the ResearchJob to process
            db_factory: Factory function to create new database sessions
            delay_between_companies: Seconds to wait between companies (rate limiting)
        """
        # Get fresh session for the job
        db = db_factory()

        try:
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            # Update job status
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Starting job {job_id} with {job.total_companies} companies")
            
            # Get pending companies
            pending_companies = db.query(Company).filter(
                Company.job_id == job_id,
                Company.status == CompanyStatus.PENDING.value
            ).all()
            
            for i, company in enumerate(pending_companies):
                # Check if task was cancelled
                if asyncio.current_task().cancelled():
                    logger.info(f"Job {job_id} cancelled")
                    job.status = JobStatus.CANCELLED.value
                    db.commit()
                    return

                # Process company
                success = await self.process_company(company, db)

                # Update job progress and health monitoring
                if success:
                    job.completed_companies += 1
                    # Aggregate Tavily credits
                    job.total_tavily_credits += company.tavily_credits_used or 0.0
                else:
                    job.failed_companies += 1

                # Update health monitoring
                job.last_activity_at = datetime.utcnow()

                # Calculate estimated total cost
                from ..utils import estimate_tavily_cost
                job.total_cost_usd = estimate_tavily_cost(job.total_tavily_credits)

                db.commit()

                # Rate limiting delay
                if i < len(pending_companies) - 1:
                    await asyncio.sleep(delay_between_companies)
            
            # Job complete
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Job {job_id} completed: {job.completed_companies} successful, {job.failed_companies} failed")

        except asyncio.CancelledError:
            logger.info(f"Job {job_id} was cancelled")
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if job:
                job.status = JobStatus.CANCELLED.value
                db.commit()
            raise  # Re-raise to properly handle cancellation

        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                db.commit()
        finally:
            self._running_tasks.pop(job_id, None)
            db.close()
    
    def register_task(self, job_id: int, task: asyncio.Task):
        """Register a running task for a job."""
        self._running_tasks[job_id] = task
        logger.info(f"Registered task for job {job_id}")

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running job.

        Args:
            job_id: ID of the job to cancel

        Returns:
            True if cancellation was requested, False if job not found
        """
        if job_id in self._running_tasks:
            task = self._running_tasks[job_id]
            task.cancel()
            logger.info(f"Cancellation requested for job {job_id}")
            return True
        else:
            logger.warning(f"Cannot cancel job {job_id}: not running")
            return False


# Singleton instance
_research_pipeline: Optional[ResearchPipeline] = None


def get_research_pipeline() -> ResearchPipeline:
    """Get or create the research pipeline singleton."""
    global _research_pipeline
    if _research_pipeline is None:
        _research_pipeline = ResearchPipeline()
    return _research_pipeline

