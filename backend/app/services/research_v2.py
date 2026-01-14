"""
Enhanced research pipeline with Tavily caching and validation.

This module implements a 3-phase research pipeline:
1. Tavily Data Fetching & Validation (with caching)
2. Data Storage & Verification
3. Full LLM Analysis & Scoring
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable, Tuple
from sqlalchemy.orm import Session

from ..models import ResearchJob, Company, JobStatus, CompanyStatus
from .search import get_search_service
from .llm import get_llm_service

logger = logging.getLogger(__name__)


async def fetch_and_validate_tavily_data(
    company: Company,
    search_service,
    llm_service,
    db: Session,
    max_retries: int = 2
) -> Tuple[Company, Optional[str], Optional[str]]:
    """
    Phase 1: Fetch Tavily data, validate it, and cache if valid.
    
    Returns:
        (company, formatted_results, error_message)
    """
    # Check if we have cached, verified Tavily data
    if company.tavily_data_cached and company.tavily_data_verified:
        logger.info(f"Using cached Tavily data for {company.name} (cached at {company.tavily_cached_at})")
        if company.tavily_formatted_results:
            return company, company.tavily_formatted_results, None
    
    # Fetch fresh Tavily data
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching Tavily data for {company.name} (attempt {attempt + 1}/{max_retries})")
            
            company.status = CompanyStatus.RESEARCHING.value
            db.commit()
            
            # Fetch from Tavily
            search_results = await search_service.search_company(company.name)
            company.search_results_raw = json.dumps(search_results.get("raw_response", {}))
            company.tavily_credits_used = search_results.get("credits_used", 0.0)
            company.tavily_response_time = search_results.get("response_time")
            
            if not search_results.get("success"):
                error_msg = f"Search failed: {search_results.get('error', 'Unknown error')}"
                logger.warning(f"{company.name}: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return company, None, error_msg
            
            # Format results for LLM
            formatted_results = search_service.format_search_results_for_llm(search_results)
            
            # Validate data quality with lightweight LLM check
            logger.info(f"Validating Tavily data for {company.name}...")
            validation = await llm_service.validate_tavily_data(company.name, formatted_results)
            
            company.tavily_validation_message = validation.get("message", "")
            
            if validation.get("is_valid") and validation.get("confidence", 0) >= 0.6:
                # Data is valid - cache it
                company.tavily_data_cached = True
                company.tavily_data_verified = True
                company.tavily_cached_at = datetime.utcnow()
                company.tavily_formatted_results = formatted_results
                db.commit()
                
                logger.info(
                    f"✓ {company.name}: Tavily data VALID and cached "
                    f"(confidence: {validation['confidence']:.2f})"
                )
                return company, formatted_results, None
            else:
                # Data is invalid - retry
                issues = ", ".join(validation.get("issues", []))
                logger.warning(
                    f"✗ {company.name}: Tavily data INVALID "
                    f"(confidence: {validation['confidence']:.2f}, issues: {issues})"
                )
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying Tavily fetch for {company.name}...")
                    await asyncio.sleep(2 ** attempt)
                    continue
                
                # Max retries reached
                error_msg = f"Data validation failed after {max_retries} attempts: {validation['message']}"
                company.tavily_data_verified = False
                db.commit()
                return company, None, error_msg
        
        except Exception as e:
            logger.error(f"Error fetching/validating {company.name}: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return company, None, str(e)
    
    # Should not reach here
    return company, None, "Unknown error in fetch_and_validate"


async def run_job_with_caching(
    job_id: int,
    db_factory: Callable,
    batch_size: int = 10,
    tavily_concurrency: int = 50
):
    """
    Enhanced research pipeline with 3-phase processing:
    
    Phase 1: Tavily Data Fetching & Validation (parallel, with caching)
    Phase 2: Verification & Storage (immediate commit to cache)
    Phase 3: Full LLM Analysis & Scoring (batched)
    
    Benefits:
    - Reuses cached Tavily data for repeated companies (saves $0.016 per hit)
    - Validates data before expensive LLM analysis
    - Retries failed Tavily fetches automatically
    - Faster overall processing
    """
    db = db_factory()
    search_service = get_search_service()
    llm_service = get_llm_service()
    
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
        logger.info(f"=== Starting JOB {job_id} with {total} companies (CACHING ENABLED) ===")
        
        # ================================================================
        # PHASE 1: Fetch & Validate ALL Tavily Data (with caching)
        # ================================================================
        logger.info(f"📊 PHASE 1: Fetching & validating Tavily data...")
        phase1_start = datetime.utcnow()
        
        # Process in batches to avoid overwhelming APIs
        tavily_results = []
        cached_count = 0
        fetched_count = 0
        
        for i in range(0, total, tavily_concurrency):
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Job {job_id} cancelled during Phase 1")
                job.status = JobStatus.CANCELLED.value
                db.commit()
                return
            
            batch = pending_companies[i:i+tavily_concurrency]
            
            # Check cache first, fetch only if needed
            for company in batch:
                if company.tavily_data_cached and company.tavily_data_verified:
                    cached_count += 1
            
            # Fetch and validate in parallel
            batch_results = await asyncio.gather(
                *[fetch_and_validate_tavily_data(company, search_service, llm_service, db) for company in batch],
                return_exceptions=True
            )
            tavily_results.extend(batch_results)
            
            fetched_count = len([r for r in tavily_results if isinstance(r, tuple) and r[1] is not None])
            
            logger.info(
                f"Phase 1 progress: {min(i+tavily_concurrency, total)}/{total} companies "
                f"({cached_count} cached, {fetched_count} fetched)"
            )
        
        phase1_duration = (datetime.utcnow() - phase1_start).total_seconds()
        tavily_cost_saved = cached_count * 0.016
        
        logger.info(
            f"✓ PHASE 1 complete in {phase1_duration:.1f}s - "
            f"{cached_count} cached (saved ${tavily_cost_saved:.2f}), "
            f"{fetched_count} fetched, "
            f"{total - fetched_count - cached_count} failed"
        )
        
        # ================================================================
        # PHASE 2: Full LLM Analysis on Verified Data
        # ================================================================
        logger.info(f"🤖 PHASE 2: Running full LLM analysis...")
        phase2_start = datetime.utcnow()
        
        async def analyze_company_llm(company: Company, formatted_results: str):
            """Run full LLM analysis on verified Tavily data."""
            try:
                if formatted_results is None:
                    return company, None, "No valid Tavily data"
                
                analysis = await llm_service.analyze_company(company.name, formatted_results)
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
        from . import research  # Import to use _store_analysis_results
        pipeline = research.get_research_pipeline()
        
        for batch_num, i in enumerate(range(0, total, batch_size), 1):
            # Check for cancellation
            if asyncio.current_task().cancelled():
                logger.info(f"Job {job_id} cancelled during Phase 2")
                job.status = JobStatus.CANCELLED.value
                db.commit()
                return
            
            batch_end = min(i + batch_size, total)
            logger.info(f"LLM batch {batch_num}: companies {i+1}-{batch_end}/{total}")
            
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
                        analysis_tasks.append(analyze_company_llm(company, formatted_results))
            
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
                            pipeline._store_analysis_results(company, analysis)
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
            f"=== JOB {job_id} COMPLETE in {total_duration:.1f}s === "
            f"Phase 1: {phase1_duration:.1f}s, Phase 2: {phase2_duration:.1f}s | "
            f"Success: {job.completed_companies}, Failed: {job.failed_companies}, "
            f"Cached: {cached_count} (saved ${tavily_cost_saved:.2f})"
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
        db.close()
