"""
Stage 1: Evidence Extraction Service using Qwen 235B.

This service extracts structured evidence from Tavily search results,
focusing on fact gathering without interpretation.
"""

import time
import asyncio
from openai import OpenAI
import json
import logging

from ..config import get_settings
from ..utils import retry_with_backoff
from ..schemas.llm_schemas import ExtractionResult

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# EXTRACTION PROMPT TEMPLATE
# ============================================================================

EXTRACTION_SYSTEM_PROMPT = """You are a technical data extraction specialist. Your job is to extract ONLY factual information explicitly stated in source material.

**CRITICAL RULES:**
1. Extract facts ONLY if they are explicitly mentioned in the source
2. For EACH fact extracted, include the source URL and relevant snippet
3. Do NOT classify, judge, or infer beyond what is stated
4. If something is implied but not directly stated, place it in "implicit_signals"
5. If you find contradictory information, extract both and note the sources
6. Your output must be valid JSON with NO additional text before or after

**YOUR TASK:**
Extract evidence related to managed inference adoption, technical infrastructure, scale indicators, and company operations.

Focus on:
- Managed inference provider mentions (Fireworks AI, Baseten, Ray Serve, Modal, Replicate, etc.)
- Technical architecture (vLLM, TensorRT, Triton, autoscaling, load balancing)
- Infrastructure keywords (GPU clusters, Kubernetes, dedicated endpoints, reserved capacity)
- Scale signals (API volume, user counts, real-time vs batch processing)
- Funding and operational data (funding rounds, employee counts, growth signals)

**OUTPUT FORMAT:**
Valid JSON matching this exact schema (no markdown, no explanations):
{
  "company_name": "string",
  "managed_providers": {
    "explicit_mentions": ["Provider name 1", "Provider name 2"],
    "implicit_signals": ["phrase suggesting managed inference"],
    "sources": ["https://url1: 'snippet text'", "https://url2: 'snippet text'"]
  },
  "technical_architecture": {
    "inference_keywords": ["vLLM", "autoscaling"],
    "compute_mentions": ["A100", "H100"],
    "deployment_patterns": ["Kubernetes", "FastAPI"],
    "sources": ["https://url: 'snippet'"]
  },
  "scale_indicators": {
    "volume_signals": ["millions of predictions"],
    "user_scale": ["10M users"],
    "real_time_vs_batch": "real-time",
    "sources": ["https://url: 'snippet'"]
  },
  "funding_operations": {
    "funding": "$50M Series B",
    "employees": "150-200",
    "growth_signals": ["hiring ML engineers"],
    "sources": ["https://url: 'snippet'"]
  },
  "extraction_notes": "Any notes about extraction quality or ambiguities"
}
"""

EXTRACTION_PROMPT_TEMPLATE = """Extract structured evidence from the following search results about "{company_name}".

**SEARCH RESULTS:**
{search_results}

---

**INSTRUCTIONS:**
1. Read all sources carefully
2. Extract only factual information with citations
3. For each fact, include the source URL and relevant text snippet
4. Do NOT interpret or classify - just extract
5. If information is missing or unclear, leave fields empty or note in extraction_notes

Output valid JSON only (no markdown code blocks, no explanations):
"""


# ============================================================================
# EXTRACTION SERVICE
# ============================================================================

class ExtractionService:
    """Service for extracting evidence from search results using Qwen 235B."""

    def __init__(self):
        self.client = OpenAI(
            base_url=settings.crusoe_api_base_url,
            api_key=settings.crusoe_api_key,
        )
        self.model = settings.extraction_model

    async def _perform_extraction(self, company_name: str, prompt: str) -> dict:
        """
        Internal method to perform LLM extraction (with retry support).

        Args:
            company_name: Name of the company
            prompt: Formatted extraction prompt

        Returns:
            LLM API response

        Raises:
            Exception: If extraction fails
        """
        def sync_extract():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Very low temperature for factual extraction
                top_p=0.9,
                timeout=settings.extraction_timeout,
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_extract)

    def _truncate_prompt_for_size(self, prompt: str, max_length: int = 100000) -> str:
        """
        Truncate search results if prompt is too large.

        Args:
            prompt: Original prompt
            max_length: Maximum character length

        Returns:
            Truncated prompt
        """
        if len(prompt) <= max_length:
            return prompt

        # Find the search results section and truncate it
        parts = prompt.split("**SEARCH RESULTS:**")
        if len(parts) == 2:
            header = parts[0] + "**SEARCH RESULTS:**"
            search_results = parts[1].split("---")[0]
            footer = "---" + "---".join(parts[1].split("---")[1:])

            # Calculate how much we can keep
            available_space = max_length - len(header) - len(footer) - 200  # buffer
            truncated_results = search_results[:available_space]
            truncated_results += "\n\n[... search results truncated due to size ...]"

            return header + truncated_results + footer

        # Fallback: just truncate the whole thing
        return prompt[:max_length]

    async def extract_evidence(
        self,
        company_name: str,
        search_results: str
    ) -> dict:
        """
        Extract structured evidence from search results.

        Args:
            company_name: Name of the company
            search_results: Formatted search results string from Tavily

        Returns:
            dict with:
                - success: bool
                - extraction_result: ExtractionResult (if successful)
                - extraction_result_raw: dict (raw JSON response)
                - tokens_used: int
                - response_time: float
                - error: str (if failed)
        """
        prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            company_name=company_name,
            search_results=search_results,
        )

        try:
            logger.info(f"[STAGE 1] Extracting evidence for: {company_name}")
            start_time = time.time()

            # Perform extraction with retry logic
            try:
                response = await retry_with_backoff(
                    self._perform_extraction,
                    company_name,
                    prompt,
                    max_retries=settings.max_retries,
                    base_delay=settings.retry_base_delay,
                    exceptions=(Exception,),
                    retry_on_400=True,
                )
            except Exception as e:
                error_str = str(e)
                # If payload too large, truncate and retry
                if '413' in error_str or 'too_large' in error_str.lower():
                    logger.warning(
                        f"[STAGE 1] Payload too large for {company_name}, "
                        "retrying with truncated prompt"
                    )
                    truncated_prompt = self._truncate_prompt_for_size(prompt)
                    response = await retry_with_backoff(
                        self._perform_extraction,
                        company_name,
                        truncated_prompt,
                        max_retries=2,
                        base_delay=settings.retry_base_delay,
                        exceptions=(Exception,),
                        retry_on_400=True,
                    )
                else:
                    raise

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
                extraction_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(
                    f"[STAGE 1] Failed to parse JSON for {company_name}: {e}\n"
                    f"Response: {response_text[:500]}"
                )
                raise ValueError(f"Invalid JSON response from extraction model: {e}")

            # Validate with Pydantic schema
            extraction_result = ExtractionResult(**extraction_data)

            logger.info(
                f"[STAGE 1] Successfully extracted evidence for {company_name} "
                f"in {response_time:.2f}s ({tokens_used} tokens)"
            )

            return {
                "success": True,
                "extraction_result": extraction_result,
                "extraction_result_raw": extraction_data,
                "tokens_used": tokens_used,
                "response_time": response_time,
            }

        except Exception as e:
            logger.error(
                f"[STAGE 1] Extraction failed for {company_name}: {str(e)}",
                exc_info=True
            )
            return {
                "success": False,
                "extraction_result": None,
                "extraction_result_raw": None,
                "tokens_used": 0,
                "response_time": 0,
                "error": str(e),
            }
