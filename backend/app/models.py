"""Database models for the Territory Planner app."""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Enum, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class JobStatus(str, enum.Enum):
    """Status of a research job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CompanyStatus(str, enum.Enum):
    """Status of individual company research."""
    PENDING = "pending"
    RESEARCHING = "researching"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GPUUseCaseTier(str, enum.Enum):
    """GPU use case classification tiers."""
    S = "S"  # Frontier pre-training
    A = "A"  # Post-training at scale
    B = "B"  # Massive inference
    C = "C"  # AI infrastructure platform
    D = "D"  # Specialized model training
    E = "E"  # Fine-tuning / API wrappers
    UNKNOWN = "UNKNOWN"


class PriorityTier(str, enum.Enum):
    """Final priority classification."""
    HOT = "HOT"      # 70-100 score
    WARM = "WARM"    # 50-69 score
    WATCH = "WATCH"  # 30-49 score
    COLD = "COLD"    # 0-29 score


class ResearchJob(Base):
    """A batch research job from an uploaded CSV."""
    __tablename__ = "research_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    status = Column(String(50), default=JobStatus.PENDING.value, index=True)

    # Progress tracking
    total_companies = Column(Integer, default=0)
    completed_companies = Column(Integer, default=0)
    failed_companies = Column(Integer, default=0)

    # Cost tracking
    total_tavily_credits = Column(Float, default=0.0)  # Total Tavily API credits used
    total_cost_usd = Column(Float, default=0.0)        # Estimated total cost in USD

    # Health monitoring
    last_activity_at = Column(DateTime, nullable=True)  # Last time a company was processed
    stalled = Column(Integer, default=0)                # Boolean flag for stalled jobs

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Original CSV filename
    original_filename = Column(String(255), nullable=True)

    # User tracking
    submitted_by = Column(String(100), nullable=True, index=True)  # Name/identifier of who submitted

    # Target type (IaaS vs Managed Inference)
    job_type = Column(String(32), default="iaas", index=True)

    # Relationships
    companies = relationship("Company", back_populates="job", cascade="all, delete-orphan")


class Company(Base):
    """A company being researched."""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("research_jobs.id"), nullable=False)
    
    # Input data
    name = Column(String(255), nullable=False)
    website = Column(String(500), nullable=True)
    
    # Processing status
    status = Column(String(50), default=CompanyStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    
    # Research results
    description = Column(Text, nullable=True)
    employee_count = Column(String(100), nullable=True)
    employee_range = Column(String(100), nullable=True)
    total_funding = Column(String(100), nullable=True)
    funding_millions = Column(Float, nullable=True)  # Numeric funding in millions USD
    last_round = Column(String(200), nullable=True)
    last_round_date = Column(String(100), nullable=True)
    investors = Column(Text, nullable=True)  # JSON array as string
    headquarters = Column(String(255), nullable=True)
    founded_year = Column(Integer, nullable=True)
    industry = Column(String(255), nullable=True)
    business_model = Column(String(255), nullable=True)
    
    # GPU Analysis
    gpu_use_case_tier = Column(String(20), nullable=True)
    gpu_use_case_label = Column(String(255), nullable=True)
    gpu_analysis_reasoning = Column(Text, nullable=True)
    signals_positive = Column(Text, nullable=True)  # JSON array as string
    signals_negative = Column(Text, nullable=True)  # JSON array as string
    
    # Scoring
    score_gpu_use_case = Column(Integer, default=0)
    score_scale_budget = Column(Integer, default=0)
    score_growth_signals = Column(Integer, default=0)
    score_confidence = Column(Integer, default=0)
    score_total = Column(Integer, default=0)
    
    # Final classification
    priority_tier = Column(String(20), nullable=True, index=True)
    recommended_action = Column(Text, nullable=True)

    # Cost tracking
    tavily_credits_used = Column(Float, default=0.0)     # Tavily API credits for this company
    tavily_response_time = Column(Float, nullable=True)  # Response time in seconds
    llm_tokens_used = Column(Integer, default=0)         # LLM tokens consumed
    llm_response_time = Column(Float, nullable=True)     # LLM response time in seconds

    # Raw data storage
    search_results_raw = Column(Text, nullable=True)  # Raw Tavily response
    llm_response_raw = Column(Text, nullable=True)    # Raw LLM response
    
    # Tavily data caching & verification
    tavily_data_cached = Column(Boolean, default=False)  # Whether Tavily data is cached
    tavily_data_verified = Column(Boolean, default=False)  # Whether data passed validation
    tavily_cached_at = Column(DateTime, nullable=True)  # When Tavily data was cached
    tavily_validation_message = Column(Text, nullable=True)  # Validation result message
    tavily_formatted_results = Column(Text, nullable=True)  # Cached formatted results for LLM

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    researched_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("ResearchJob", back_populates="companies")

