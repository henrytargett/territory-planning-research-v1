"""
Stage 3: Programmatic Validation Service.

This service validates the outputs of Stage 1 and Stage 2 using
deterministic logic (no LLM calls). It checks for:
- Hallucinations (claims not supported by evidence)
- Inconsistencies (scores don't match tiers)
- Overconfidence (high confidence with weak evidence)
- Missing citations
"""

import logging
from typing import List
import re

from ..schemas.llm_schemas import (
    ExtractionResult,
    ClassificationResult,
    ValidationResult,
    ValidationIssue
)

logger = logging.getLogger(__name__)


# ============================================================================
# VALIDATION SERVICE
# ============================================================================

class ValidationService:
    """Service for programmatic validation of LLM outputs."""

    def __init__(self):
        # Tier score ranges
        self.tier_ranges = {
            "A": (80, 100),
            "B": (60, 79),
            "C": (40, 59),
            "D": (0, 39),
        }

        # Known managed inference providers
        self.managed_providers = {
            "fireworks ai", "fireworks", "baseten", "ray serve", "rayserve",
            "modal", "replicate", "together ai", "together", "anyscale",
            "runpod", "banana", "mystic", "inferless", "octoai", "lepton ai",
            "brev", "coreweave", "lambda labs", "vast.ai"
        }

    def validate_analysis(
        self,
        company_name: str,
        extraction: ExtractionResult,
        classification: ClassificationResult
    ) -> ValidationResult:
        """
        Validate the complete analysis using programmatic checks.

        Args:
            company_name: Name of the company
            extraction: Stage 1 extraction result
            classification: Stage 2 classification result

        Returns:
            ValidationResult with issues and flags
        """
        logger.info(f"[STAGE 3] Validating analysis for: {company_name}")

        issues: List[ValidationIssue] = []

        # Check 1: Hallucination detection
        hallucination_issues = self._check_hallucinations(extraction, classification)
        issues.extend(hallucination_issues)

        # Check 2: Score/tier consistency
        consistency_issues = self._check_score_tier_consistency(classification)
        issues.extend(consistency_issues)

        # Check 3: Confidence calibration
        confidence_issues = self._check_confidence_calibration(extraction, classification)
        issues.extend(confidence_issues)

        # Check 4: Missing citations
        citation_issues = self._check_missing_citations(classification)
        issues.extend(citation_issues)

        # Check 5: Evidence quality
        evidence_issues = self._check_evidence_quality(extraction)
        issues.extend(evidence_issues)

        # Determine validation status
        high_severity_issues = [i for i in issues if i.severity == "high"]
        valid = len(high_severity_issues) == 0
        needs_review = len(issues) > 2  # More than 2 issues of any severity
        hallucination_detected = any(i.type == "hallucination" for i in issues)

        logger.info(
            f"[STAGE 3] Validation complete for {company_name}: "
            f"valid={valid}, issues={len(issues)}, needs_review={needs_review}"
        )

        return ValidationResult(
            company_name=company_name,
            valid=valid,
            issues=issues,
            needs_human_review=needs_review,
            hallucination_detected=hallucination_detected
        )

    def _check_hallucinations(
        self,
        extraction: ExtractionResult,
        classification: ClassificationResult
    ) -> List[ValidationIssue]:
        """
        Check if classification cites providers/facts not in extraction.

        Returns:
            List of hallucination issues
        """
        issues = []

        # Extract all providers mentioned in extraction
        extraction_text = (
            " ".join(extraction.managed_providers.explicit_mentions) + " " +
            " ".join(extraction.managed_providers.implicit_signals) + " " +
            " ".join(extraction.technical_architecture.inference_keywords) + " " +
            " ".join(extraction.technical_architecture.deployment_patterns)
        ).lower()

        # Check reasoning trace for provider mentions not in extraction
        reasoning_text = " ".join(classification.reasoning_trace).lower()

        for provider in self.managed_providers:
            if provider in reasoning_text and provider not in extraction_text:
                issues.append(ValidationIssue(
                    type="hallucination",
                    severity="high",
                    message=f"Reasoning mentions '{provider}' not found in extracted evidence"
                ))

        # Check evidence citations for specific claims
        citations = classification.evidence_citations

        # Check platform_adoption citation
        if citations.platform_adoption:
            citation_lower = citations.platform_adoption.lower()
            for provider in self.managed_providers:
                if provider in citation_lower and provider not in extraction_text:
                    issues.append(ValidationIssue(
                        type="hallucination",
                        severity="high",
                        message=f"Platform adoption cites '{provider}' not in evidence"
                    ))

        return issues

    def _check_score_tier_consistency(
        self,
        classification: ClassificationResult
    ) -> List[ValidationIssue]:
        """
        Check if total score matches the assigned tier.

        Returns:
            List of consistency issues
        """
        issues = []

        tier = classification.classification.tier
        total_score = classification.scores.total

        if tier not in self.tier_ranges:
            issues.append(ValidationIssue(
                type="inconsistency",
                severity="high",
                message=f"Invalid tier '{tier}' - must be A, B, C, or D"
            ))
            return issues

        min_score, max_score = self.tier_ranges[tier]

        if not (min_score <= total_score <= max_score):
            issues.append(ValidationIssue(
                type="inconsistency",
                severity="high",
                message=f"Tier {tier} (range {min_score}-{max_score}) doesn't match score {total_score}"
            ))

        # Check if total equals sum of components
        component_sum = (
            classification.scores.inference_scale +
            classification.scores.platform_adoption +
            classification.scores.growth_signals +
            classification.scores.confidence
        )

        if component_sum != total_score:
            issues.append(ValidationIssue(
                type="inconsistency",
                severity="medium",
                message=f"Score components sum to {component_sum} but total is {total_score}"
            ))

        return issues

    def _check_confidence_calibration(
        self,
        extraction: ExtractionResult,
        classification: ClassificationResult
    ) -> List[ValidationIssue]:
        """
        Check if confidence score is justified by evidence quality.

        Returns:
            List of overconfidence issues
        """
        issues = []

        confidence = classification.scores.confidence

        # Count evidence items
        evidence_count = (
            len(extraction.managed_providers.explicit_mentions) +
            len(extraction.managed_providers.implicit_signals) +
            len(extraction.technical_architecture.inference_keywords) +
            len(extraction.scale_indicators.volume_signals)
        )

        # High confidence (8-10) requires substantial evidence
        if confidence >= 8 and evidence_count < 3:
            issues.append(ValidationIssue(
                type="overconfidence",
                severity="medium",
                message=f"High confidence ({confidence}/10) with only {evidence_count} evidence items"
            ))

        # Medium confidence (5-7) requires some evidence
        if confidence >= 5 and evidence_count < 1:
            issues.append(ValidationIssue(
                type="overconfidence",
                severity="medium",
                message=f"Medium confidence ({confidence}/10) with no substantial evidence"
            ))

        # Check if classification confidence matches score confidence
        classification_confidence = classification.classification.confidence
        if abs(classification_confidence - confidence) > 2:
            issues.append(ValidationIssue(
                type="inconsistency",
                severity="low",
                message=f"Classification confidence ({classification_confidence}) differs from score confidence ({confidence})"
            ))

        return issues

    def _check_missing_citations(
        self,
        classification: ClassificationResult
    ) -> List[ValidationIssue]:
        """
        Check if evidence citations are provided for scoring.

        Returns:
            List of missing citation issues
        """
        issues = []

        citations = classification.evidence_citations

        # Check for missing citations on non-zero scores
        if classification.scores.inference_scale > 0 and not citations.inference_scale:
            issues.append(ValidationIssue(
                type="missing_citations",
                severity="medium",
                message="No citation provided for inference_scale score"
            ))

        if classification.scores.platform_adoption > 0 and not citations.platform_adoption:
            issues.append(ValidationIssue(
                type="missing_citations",
                severity="medium",
                message="No citation provided for platform_adoption score"
            ))

        if classification.scores.growth_signals > 0 and not citations.growth_signals:
            issues.append(ValidationIssue(
                type="missing_citations",
                severity="low",
                message="No citation provided for growth_signals score"
            ))

        return issues

    def _check_evidence_quality(
        self,
        extraction: ExtractionResult
    ) -> List[ValidationIssue]:
        """
        Check the quality and completeness of extracted evidence.

        Returns:
            List of evidence quality issues
        """
        issues = []

        # Check if sources are actually provided
        total_sources = (
            len(extraction.managed_providers.sources) +
            len(extraction.technical_architecture.sources) +
            len(extraction.scale_indicators.sources) +
            len(extraction.funding_operations.sources)
        )

        if total_sources == 0:
            issues.append(ValidationIssue(
                type="missing_citations",
                severity="high",
                message="No source citations provided in extraction"
            ))

        # Check for extraction notes indicating issues
        if extraction.extraction_notes:
            notes_lower = extraction.extraction_notes.lower()
            if any(word in notes_lower for word in ["unclear", "ambiguous", "missing", "limited"]):
                issues.append(ValidationIssue(
                    type="evidence_quality",
                    severity="low",
                    message=f"Extraction notes indicate issues: {extraction.extraction_notes}"
                ))

        return issues
