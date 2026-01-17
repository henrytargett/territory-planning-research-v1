"""
Stage 2: Reasoning & Classification Service using DeepSeek R1.

This service reasons about extracted evidence to produce classifications,
scores, and reasoning traces with chain-of-thought capabilities.
"""

import time
import asyncio
from openai import OpenAI
import json
import logging

from ..config import get_settings
from ..utils import retry_with_backoff
from ..schemas.llm_schemas import ExtractionResult, ClassificationResult

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# REASONING PROMPT TEMPLATE
# ============================================================================

REASONING_SYSTEM_PROMPT = """You are a territory planning analyst specializing in managed inference adoption. Your task is to analyze extracted evidence and determine a company's classification tier for managed inference usage.

**YOUR CAPABILITIES:**
- You have built-in chain-of-thought reasoning
- You can deliberate on contradictory evidence
- You must cite specific evidence for every conclusion
- You explain your reasoning step-by-step

**CLASSIFICATION TIERS:**

**Tier A (80-100 points): High-Volume Managed Inference**
- Explicit mentions of managed inference providers (Fireworks AI, Baseten, Ray Serve, Modal, Replicate, etc.)
- Evidence of production-scale inference (millions of API calls, real-time serving)
- Strong technical architecture signals (autoscaling, dedicated endpoints, reserved capacity)
- Well-funded with growth signals

**Tier B (60-79 points): Strong Managed Inference Signals**
- Strong implicit signals of managed inference without explicit provider names
- Technical architecture suggests managed platforms (autoscaling, load balancing, serverless patterns)
- Significant inference volume but provider unclear
- May be using managed infrastructure but not publicly disclosed

**Tier C (40-59 points): Some Inference Usage**
- Evidence of AI/ML inference but unclear if managed or self-hosted
- Mixed signals (both managed and self-hosted indicators)
- Limited scale or unclear production status
- Inference usage present but not core to business

**Tier D (0-39 points): Weak/No Managed Inference Signals**
- No evidence of managed inference providers
- Primarily self-hosted infrastructure or API wrappers (OpenAI/Anthropic/Google)
- No significant inference volume
- AI features present but likely using third-party APIs

**SCORING BREAKDOWN:**
- **inference_scale** (0-50 points): Volume and production evidence
  - 40-50: Millions of predictions/day, real-time, high availability requirements
  - 25-39: Significant volume, production inference
  - 10-24: Moderate inference usage
  - 0-9: Light or unclear usage

- **platform_adoption** (0-25 points): Evidence of managed platform usage
  - 20-25: Explicit managed provider mentions with production usage
  - 15-19: Strong implicit signals of managed platforms
  - 8-14: Some managed platform indicators
  - 0-7: Weak or no managed platform signals

- **growth_signals** (0-15 points): Company momentum and budget
  - 12-15: Strong funding + rapid growth + hiring infrastructure team
  - 8-11: Good funding or growth signals
  - 4-7: Some growth indicators
  - 0-3: Limited growth signals

- **confidence** (0-10 points): Evidence quality and consistency
  - 8-10: Multiple strong sources, consistent evidence
  - 5-7: Good evidence but some gaps
  - 2-4: Limited evidence, some uncertainty
  - 0-1: Very weak evidence

**CRITICAL RULES:**
1. ALWAYS cite specific evidence from the extraction for each score
2. If evidence is contradictory, explain how you resolved the conflict
3. Do NOT hallucinate providers or facts not in the evidence
4. If evidence is weak, score conservatively and note low confidence
5. Your reasoning_trace should show step-by-step logic
6. Output valid JSON with NO additional text

**OUTPUT FORMAT:**
{
  "company_name": "string",
  "reasoning_trace": [
    "Step 1: Observed X in evidence from source Y",
    "Step 2: This suggests Z because...",
    "Step 3: Weighed evidence A vs evidence B, conclusion: ..."
  ],
  "conflicting_signals": [
    "Found both 'AWS' (generic) and 'Ray Serve' (specific managed). Ray Serve more indicative."
  ],
  "classification": {
    "tier": "A",
    "label": "High-volume managed inference",
    "confidence": 8
  },
  "scores": {
    "inference_scale": 45,
    "platform_adoption": 20,
    "growth_signals": 12,
    "confidence": 8,
    "total": 85
  },
  "evidence_citations": {
    "inference_scale": "Ray Serve mentioned 3 times for autoscaling production inference",
    "platform_adoption": "Strong hints but no explicit Fireworks/Baseten confirmation",
    "growth_signals": "$50M Series B, hiring ML infrastructure team"
  }
}
"""

REASONING_PROMPT_TEMPLATE = """Analyze the following extracted evidence for "{company_name}" and produce a classification with reasoning.

**EXTRACTED EVIDENCE:**
{evidence_json}

---

**YOUR TASK:**
1. Review all extracted evidence carefully
2. Identify signals for/against managed inference usage
3. Resolve any conflicting signals and explain your reasoning
4. Assign classification tier (A/B/C/D) based on the rubric
5. Score each dimension (inference_scale, platform_adoption, growth_signals, confidence)
6. Cite specific evidence for EVERY score
7. Provide step-by-step reasoning in reasoning_trace

**REMEMBER:**
- Only use facts from the evidence above
- Cite sources for all claims
- If conflicting signals exist, document and resolve them
- Be conservative if evidence is weak

Output valid JSON only (no markdown, no explanations):
"""


# ============================================================================
# REASONING SERVICE
# ============================================================================

class ReasoningService:
    """Service for reasoning about evidence and producing classifications using DeepSeek R1."""

    def __init__(self):
        self.client = OpenAI(
            base_url=settings.crusoe_api_base_url,
            api_key=settings.crusoe_api_key,
        )
        self.model = settings.reasoning_model

    async def _perform_reasoning(self, company_name: str, prompt: str) -> dict:
        """
        Internal method to perform LLM reasoning (with retry support).

        Args:
            company_name: Name of the company
            prompt: Formatted reasoning prompt

        Returns:
            LLM API response

        Raises:
            Exception: If reasoning fails
        """
        def sync_reason():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Allow some creativity for reasoning
                top_p=0.9,
                timeout=settings.reasoning_timeout,
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_reason)

    async def classify_company(
        self,
        company_name: str,
        extraction_result: ExtractionResult
    ) -> dict:
        """
        Reason about extracted evidence and produce classification.

        Args:
            company_name: Name of the company
            extraction_result: ExtractionResult from Stage 1

        Returns:
            dict with:
                - success: bool
                - classification_result: ClassificationResult (if successful)
                - classification_result_raw: dict (raw JSON response)
                - tokens_used: int
                - response_time: float
                - error: str (if failed)
        """
        # Convert extraction result to JSON for prompt
        evidence_json = extraction_result.model_dump_json(indent=2)

        prompt = REASONING_PROMPT_TEMPLATE.format(
            company_name=company_name,
            evidence_json=evidence_json,
        )

        try:
            logger.info(f"[STAGE 2] Reasoning about evidence for: {company_name}")
            start_time = time.time()

            # Perform reasoning with retry logic
            response = await retry_with_backoff(
                self._perform_reasoning,
                company_name,
                prompt,
                max_retries=settings.max_retries,
                base_delay=settings.retry_base_delay,
                exceptions=(Exception,),
                retry_on_400=True,
            )

            response_time = time.time() - start_time

            # Extract token usage
            tokens_used = 0
            if hasattr(response, 'usage') and response.usage:
                tokens_used = response.usage.total_tokens or 0

            response_text = response.choices[0].message.content.strip()

            # Clean up response (remove markdown code blocks if present)
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse JSON
            try:
                classification_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(
                    f"[STAGE 2] Failed to parse JSON for {company_name}: {e}\n"
                    f"Response: {response_text[:500]}"
                )
                raise ValueError(f"Invalid JSON response from reasoning model: {e}")

            # Validate with Pydantic schema
            classification_result = ClassificationResult(**classification_data)

            logger.info(
                f"[STAGE 2] Successfully classified {company_name} as Tier "
                f"{classification_result.classification.tier} "
                f"(score: {classification_result.scores.total}) "
                f"in {response_time:.2f}s ({tokens_used} tokens)"
            )

            return {
                "success": True,
                "classification_result": classification_result,
                "classification_result_raw": classification_data,
                "tokens_used": tokens_used,
                "response_time": response_time,
            }

        except Exception as e:
            logger.error(
                f"[STAGE 2] Reasoning failed for {company_name}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "classification_result": None,
                "classification_result_raw": None,
                "tokens_used": 0,
                "response_time": 0,
                "error": str(e),
            }
