"""API routes for research jobs."""

import asyncio
import csv
import io
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import ResearchJob, Company, JobStatus, CompanyStatus
from ..services.research import get_research_pipeline
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])
settings = get_settings()

VALID_JOB_TYPES = {"iaas", "managed_inference"}


# Pydantic models for API responses
class CompanyResponse(BaseModel):
    id: int
    name: str
    status: str
    description: Optional[str] = None
    employee_count: Optional[str] = None
    total_funding: Optional[str] = None
    funding_millions: Optional[float] = None
    last_round: Optional[str] = None
    headquarters: Optional[str] = None
    industry: Optional[str] = None
    business_model: Optional[str] = None
    gpu_use_case_tier: Optional[str] = None
    gpu_use_case_label: Optional[str] = None
    gpu_analysis_reasoning: Optional[str] = None
    score_gpu_use_case: int = 0
    score_scale_budget: int = 0
    score_growth_signals: int = 0
    score_confidence: int = 0
    score_total: int = 0
    priority_tier: Optional[str] = None
    recommended_action: Optional[str] = None
    error_message: Optional[str] = None
    # Cost tracking fields
    tavily_credits_used: float = 0.0
    tavily_response_time: Optional[float] = None
    llm_tokens_used: int = 0
    llm_response_time: Optional[float] = None

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    name: Optional[str] = None
    job_type: str = "iaas"
    status: str
    total_companies: int
    completed_companies: int
    failed_companies: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    original_filename: Optional[str] = None
    submitted_by: Optional[str] = None
    # Cost tracking fields
    total_tavily_credits: float = 0.0
    total_cost_usd: float = 0.0
    # Health monitoring fields
    last_activity_at: Optional[datetime] = None
    stalled: int = 0

    class Config:
        from_attributes = True


class JobDetailResponse(JobResponse):
    companies: List[CompanyResponse] = []


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


@router.post("/upload", response_model=JobResponse)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    submitted_by: Optional[str] = Query(None, description="Name of person submitting the job"),
    target_type: str = Query("iaas", description="Target type: iaas or managed_inference"),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file with company names to start a research job.
    
    The CSV should have a column named 'company_name' or 'name' or be a single column.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        content = await file.read()
        text = content.decode('utf-8')
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))
        
        # Find the company name column
        fieldnames = reader.fieldnames or []
        name_column = None
        for col in ['company_name', 'name', 'Company Name', 'Company', 'company']:
            if col in fieldnames:
                name_column = col
                break
        
        # If no header found, try reading as single column
        if name_column is None:
            if len(fieldnames) == 1:
                name_column = fieldnames[0]
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="CSV must have a column named 'company_name', 'name', or be a single column"
                )
        
        # Extract company names
        company_names = []
        for row in reader:
            name = row.get(name_column, '').strip()
            if name:
                company_names.append(name)
        
        if not company_names:
            raise HTTPException(status_code=400, detail="No company names found in CSV")
        
        # Validate target type
        if target_type not in VALID_JOB_TYPES:
            raise HTTPException(status_code=400, detail="Invalid target_type. Use 'iaas' or 'managed_inference'.")

        # Create job
        job = ResearchJob(
            name=f"Research Job - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            status=JobStatus.PENDING.value,
            total_companies=len(company_names),
            original_filename=file.filename,
            submitted_by=submitted_by or "Anonymous",
            job_type=target_type,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Create company records
        for name in company_names:
            company = Company(
                job_id=job.id,
                name=name,
                status=CompanyStatus.PENDING.value,
            )
            db.add(company)
        db.commit()
        
        # Start processing in background
        pipeline = get_research_pipeline()

        # Create async task directly in the event loop
        if settings.enable_batch_processing:
            logger.info(f"Starting job {job.id} with BATCH processing (batch_size={settings.batch_size})")
            task = asyncio.create_task(
                pipeline.run_job_batched(
                    job.id, 
                    lambda: SessionLocal(),
                    batch_size=settings.batch_size,
                    tavily_concurrency=settings.tavily_concurrency
                )
            )
        else:
            logger.info(f"Starting job {job.id} with SEQUENTIAL processing")
            task = asyncio.create_task(
                pipeline.run_job(job.id, lambda: SessionLocal())
            )
        
        # Register task with pipeline for proper cancellation
        pipeline.register_task(job.id, task)
        logger.info(f"Started background task for job {job.id}")

        return job
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid CSV encoding. Please use UTF-8.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@router.post("/single", response_model=JobResponse)
async def lookup_single_company(
    company_name: str = Query(..., description="Name of the company to research"),
    submitted_by: Optional[str] = Query(None, description="Name of person submitting the job"),
    target_type: str = Query("iaas", description="Target type: iaas or managed_inference"),
    db: Session = Depends(get_db),
):
    """
    Research a single company without uploading a CSV.
    """
    if not company_name or not company_name.strip():
        raise HTTPException(status_code=400, detail="Company name is required")
    
    company_name = company_name.strip()
    
    if target_type not in VALID_JOB_TYPES:
        raise HTTPException(status_code=400, detail="Invalid target_type. Use 'iaas' or 'managed_inference'.")

    # Create job
    job = ResearchJob(
        name=f"Single Company: {company_name}",
        status=JobStatus.PENDING.value,
        total_companies=1,
        original_filename=None,
        submitted_by=submitted_by or "Anonymous",
        job_type=target_type,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Create company record
    company = Company(
        job_id=job.id,
        name=company_name,
        status=CompanyStatus.PENDING.value,
    )
    db.add(company)
    db.commit()
    
    # Start processing in background (single company always uses batched method for consistency)
    pipeline = get_research_pipeline()
    task = asyncio.create_task(
        pipeline.run_job_batched(
            job.id,
            lambda: SessionLocal(),
            batch_size=1,  # Single company
            tavily_concurrency=1
        )
    )
    # Register task with pipeline for proper cancellation
    pipeline.register_task(job.id, task)
    logger.info(f"Started single company lookup for: {company_name}")

    return job


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    submitted_by: Optional[str] = None,
    job_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all research jobs. Optionally filter by submitter."""
    query = db.query(ResearchJob)
    
    if submitted_by:
        query = query.filter(ResearchJob.submitted_by == submitted_by)
    if job_type:
        if job_type not in VALID_JOB_TYPES:
            raise HTTPException(status_code=400, detail="Invalid job_type. Use 'iaas' or 'managed_inference'.")
        query = query.filter(ResearchJob.job_type == job_type)
    
    jobs = query.order_by(ResearchJob.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()
    return JobListResponse(jobs=jobs, total=total)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get details of a specific job including all companies."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get companies sorted by score
    companies = db.query(Company).filter(
        Company.job_id == job_id
    ).order_by(Company.score_total.desc()).all()
    
    return JobDetailResponse(
        id=job.id,
        name=job.name,
        job_type=job.job_type or "iaas",
        status=job.status,
        total_companies=job.total_companies,
        completed_companies=job.completed_companies,
        failed_companies=job.failed_companies,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        original_filename=job.original_filename,
        submitted_by=job.submitted_by,
        companies=companies,
    )


@router.get("/{job_id}/progress")
async def get_job_progress(job_id: int, db: Session = Depends(get_db)):
    """Get current progress of a job (lightweight endpoint for polling)."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "status": job.status,
        "total": job.total_companies,
        "completed": job.completed_companies,
        "failed": job.failed_companies,
        "pending": job.total_companies - job.completed_companies - job.failed_companies,
        "progress_percent": round(
            (job.completed_companies + job.failed_companies) / job.total_companies * 100, 1
        ) if job.total_companies > 0 else 0,
    }


@router.post("/{job_id}/start")
async def start_job(job_id: int, db: Session = Depends(get_db)):
    """Manually start or restart a pending/failed job."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status == JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Job is already running")
    
    # Reset job status
    job.status = JobStatus.PENDING.value
    db.commit()
    
    # Start processing
    pipeline = get_research_pipeline()
    
    if settings.enable_batch_processing:
        task = asyncio.create_task(
            pipeline.run_job_batched(
                job_id,
                lambda: SessionLocal(),
                batch_size=settings.batch_size,
                tavily_concurrency=settings.tavily_concurrency
            )
        )
    else:
        task = asyncio.create_task(
            pipeline.run_job(job_id, lambda: SessionLocal())
        )
    
    # Register task with pipeline for proper cancellation
    pipeline.register_task(job_id, task)
    logger.info(f"Manually started job {job_id}")

    return {"message": "Job started", "job_id": job_id}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """Cancel a running job."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Job is not running")

    pipeline = get_research_pipeline()
    cancelled = pipeline.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=400, detail="Job task not found - may have just completed")

    return {"message": "Cancellation requested", "job_id": job_id}


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Delete a job and all associated companies."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status == JobStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete a running job. Cancel it first.")
    
    db.delete(job)
    db.commit()
    
    return {"message": "Job deleted", "job_id": job_id}


@router.get("/{job_id}/export")
async def export_job_results(job_id: int, db: Session = Depends(get_db)):
    """Export job results as CSV."""
    job = db.query(ResearchJob).filter(ResearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    companies = db.query(Company).filter(
        Company.job_id == job_id
    ).order_by(Company.score_total.desc()).all()
    
    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    if (job.job_type or "iaas") == "managed_inference":
        writer.writerow([
            "Rank", "Company Name", "Priority Tier", "Total Score",
            "Inference Scale Tier", "Inference Scale", "Description",
            "Employee Count", "Funding (Millions USD)", "Total Funding (Text)", "Last Round",
            "Industry", "Business Model", "Headquarters",
            "Score: Inference Scale", "Score: Platform Adoption", "Score: Growth", "Score: Confidence",
            "Reasoning", "Positive Signals", "Negative Signals",
            "Recommended Action", "Status", "Submitted By"
        ])
    else:
        writer.writerow([
            "Rank", "Company Name", "Priority Tier", "Total Score",
            "GPU Use Case Tier", "GPU Use Case", "Description",
            "Employee Count", "Funding (Millions USD)", "Total Funding (Text)", "Last Round",
            "Industry", "Business Model", "Headquarters",
            "Score: GPU Use Case", "Score: Scale/Budget", "Score: Growth", "Score: Confidence",
            "Reasoning", "Positive Signals", "Negative Signals",
            "Recommended Action", "Status", "Submitted By"
        ])
    
    # Data rows
    for i, company in enumerate(companies, 1):
        writer.writerow([
            i,
            company.name,
            company.priority_tier or "N/A",
            company.score_total,
            company.gpu_use_case_tier or "N/A",
            company.gpu_use_case_label or "N/A",
            company.description or "",
            company.employee_count or "",
            company.funding_millions if company.funding_millions else "",
            company.total_funding or "",
            company.last_round or "",
            company.industry or "",
            company.business_model or "",
            company.headquarters or "",
            company.score_gpu_use_case,
            company.score_scale_budget,
            company.score_growth_signals,
            company.score_confidence,
            company.gpu_analysis_reasoning or "",
            company.signals_positive or "",
            company.signals_negative or "",
            company.recommended_action or "",
            company.status,
            job.submitted_by or "Anonymous",
        ])
    
    csv_content = output.getvalue()
    
    from fastapi.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=research_results_{job_id}.csv"
        }
    )

