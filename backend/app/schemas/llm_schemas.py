"""
Pydantic schemas for 2-stage LLM pipeline outputs.

Stage 1: Evidence Extraction (Qwen 235B)
Stage 2: Reasoning & Classification (DeepSeek R1)
Stage 3: Validation (Programmatic)
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# STAGE 1: EVIDENCE EXTRACTION SCHEMAS
# ============================================================================

class ManagedProviders(BaseModel):
    """Extracted managed inference provider mentions."""
    explicit_mentions: List[str] = Field(
        default_factory=list,
        description="Explicitly named managed inference providers (e.g., 'Fireworks AI', 'Baseten', 'Ray Serve')"
    )
    implicit_signals: List[str] = Field(
        default_factory=list,
        description="Phrases suggesting managed inference without naming providers (e.g., 'autoscaling replicas', 'dedicated endpoints')"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source citations in format 'URL: snippet text'"
    )


class TechnicalArchitecture(BaseModel):
    """Extracted technical infrastructure signals."""
    inference_keywords: List[str] = Field(
        default_factory=list,
        description="Inference-related technology mentions (e.g., 'vLLM', 'TensorRT', 'Triton')"
    )
    compute_mentions: List[str] = Field(
        default_factory=list,
        description="Compute hardware mentions (e.g., 'A100', 'H100', 'GPU cluster')"
    )
    deployment_patterns: List[str] = Field(
        default_factory=list,
        description="Deployment patterns (e.g., 'Kubernetes', 'FastAPI', 'serverless')"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source citations"
    )


class ScaleIndicators(BaseModel):
    """Extracted scale and usage signals."""
    volume_signals: List[str] = Field(
        default_factory=list,
        description="Volume indicators (e.g., 'millions of predictions', '100M API calls')"
    )
    user_scale: List[str] = Field(
        default_factory=list,
        description="User base scale (e.g., '10M users', 'enterprise customers')"
    )
    real_time_vs_batch: Optional[str] = Field(
        None,
        description="Whether inference is real-time, batch, or both"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source citations"
    )


class FundingOperations(BaseModel):
    """Extracted funding and operational data."""
    funding: Optional[str] = Field(
        None,
        description="Funding information (e.g., '$50M Series B')"
    )
    employees: Optional[str] = Field(
        None,
        description="Employee count or range"
    )
    growth_signals: List[str] = Field(
        default_factory=list,
        description="Growth indicators (e.g., 'hiring ML engineers', 'expanding infrastructure')"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source citations"
    )


class ExtractionResult(BaseModel):
    """Complete Stage 1 extraction output."""
    company_name: str
    managed_providers: ManagedProviders = Field(default_factory=ManagedProviders)
    technical_architecture: TechnicalArchitecture = Field(default_factory=TechnicalArchitecture)
    scale_indicators: ScaleIndicators = Field(default_factory=ScaleIndicators)
    funding_operations: FundingOperations = Field(default_factory=FundingOperations)
    extraction_notes: Optional[str] = Field(
        None,
        description="Any notes about extraction quality or ambiguities"
    )


# ============================================================================
# STAGE 2: REASONING & CLASSIFICATION SCHEMAS
# ============================================================================

class Classification(BaseModel):
    """Classification tier and label."""
    tier: str = Field(
        ...,
        description="Classification tier (A/B/C/D)"
    )
    label: str = Field(
        ...,
        description="Human-readable label for the tier"
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=10,
        description="Confidence score 0-10"
    )


class Scores(BaseModel):
    """Detailed scoring breakdown."""
    inference_scale: int = Field(
        ...,
        ge=0,
        le=50,
        description="Inference scale score (0-50 points)"
    )
    platform_adoption: int = Field(
        ...,
        ge=0,
        le=25,
        description="Managed platform adoption score (0-25 points)"
    )
    growth_signals: int = Field(
        ...,
        ge=0,
        le=15,
        description="Growth and momentum signals (0-15 points)"
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=10,
        description="Overall confidence (0-10 points)"
    )
    total: int = Field(
        ...,
        ge=0,
        le=100,
        description="Total score (sum of all components)"
    )


class EvidenceCitations(BaseModel):
    """Evidence citations for each scoring dimension."""
    inference_scale: Optional[str] = None
    platform_adoption: Optional[str] = None
    growth_signals: Optional[str] = None


class ClassificationResult(BaseModel):
    """Complete Stage 2 reasoning output."""
    company_name: str
    reasoning_trace: List[str] = Field(
        ...,
        description="Step-by-step reasoning process"
    )
    conflicting_signals: List[str] = Field(
        default_factory=list,
        description="Any conflicting evidence and how it was resolved"
    )
    classification: Classification
    scores: Scores
    evidence_citations: EvidenceCitations = Field(
        default_factory=EvidenceCitations,
        description="Specific evidence citations for each score"
    )


# ============================================================================
# STAGE 3: VALIDATION SCHEMAS
# ============================================================================

class ValidationIssue(BaseModel):
    """A single validation issue."""
    type: str = Field(
        ...,
        description="Issue type: 'hallucination', 'inconsistency', 'overconfidence', 'missing_citations'"
    )
    severity: str = Field(
        ...,
        description="Severity: 'high', 'medium', 'low'"
    )
    message: str = Field(
        ...,
        description="Human-readable description of the issue"
    )


class ValidationResult(BaseModel):
    """Complete Stage 3 validation output."""
    company_name: str
    valid: bool = Field(
        ...,
        description="True if no high-severity issues found"
    )
    issues: List[ValidationIssue] = Field(
        default_factory=list,
        description="List of all validation issues"
    )
    needs_human_review: bool = Field(
        ...,
        description="True if issues require manual review (>2 issues total)"
    )
    hallucination_detected: bool = Field(
        default=False,
        description="True if any hallucinations were detected"
    )


# ============================================================================
# COMBINED ANALYSIS RESULT
# ============================================================================

class CompanyAnalysis(BaseModel):
    """Complete 3-stage analysis result."""
    company_name: str
    extraction: ExtractionResult
    classification: ClassificationResult
    validation: ValidationResult

    @property
    def needs_review(self) -> bool:
        """Convenience property for flagging companies needing review."""
        return self.validation.needs_human_review

    @property
    def final_tier(self) -> str:
        """The final classification tier."""
        return self.classification.classification.tier

    @property
    def final_score(self) -> int:
        """The final total score."""
        return self.classification.scores.total
