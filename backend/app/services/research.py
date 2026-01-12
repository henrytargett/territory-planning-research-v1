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
        self._running_jobs: dict[int, bool] = {}  # Track running jobs for cancellation
    
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
        self._running_jobs[job_id] = True
        
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
                # Check for cancellation
                if not self._running_jobs.get(job_id, False):
                    logger.info(f"Job {job_id} cancelled")
                    job.status = JobStatus.CANCELLED.value
                    db.commit()
                    return
                
                # Process company
                success = await self.process_company(company, db)
                
                # Update job progress
                if success:
                    job.completed_companies += 1
                else:
                    job.failed_companies += 1
                db.commit()
                
                # Rate limiting delay
                if i < len(pending_companies) - 1:
                    await asyncio.sleep(delay_between_companies)
            
            # Job complete
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Job {job_id} completed: {job.completed_companies} successful, {job.failed_companies} failed")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                db.commit()
        finally:
            self._running_jobs.pop(job_id, None)
            db.close()
    
    def cancel_job(self, job_id: int):
        """Cancel a running job."""
        if job_id in self._running_jobs:
            self._running_jobs[job_id] = False
            logger.info(f"Cancellation requested for job {job_id}")


# Singleton instance
_research_pipeline: Optional[ResearchPipeline] = None


def get_research_pipeline() -> ResearchPipeline:
    """Get or create the research pipeline singleton."""
    global _research_pipeline
    if _research_pipeline is None:
        _research_pipeline = ResearchPipeline()
    return _research_pipeline

