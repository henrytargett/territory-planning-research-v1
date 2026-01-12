"""Crusoe Cloud LLM service for company analysis."""

import time
import asyncio
from openai import OpenAI
from typing import Optional
import json
import logging

from ..config import get_settings
from ..utils import retry_with_backoff

logger = logging.getLogger(__name__)
settings = get_settings()

# System prompt for company research and GPU need analysis
SYSTEM_PROMPT = """You are an expert analyst specializing in identifying AI-native startups that need large GPU clusters for training and inference.

Your task is to analyze search results about a company and extract structured information to determine their likelihood of needing significant GPU infrastructure.

## GPU Use Case Tiers (from highest to lowest need):

**Tier S - Frontier Pre-training**: Companies training foundation models from scratch. They build their own base models, not just fine-tune others. Examples: Anthropic, Mistral, Cohere, xAI, Twelve Labs (multimodal). Need: 1000s-10,000s of GPUs. Score: 50 points.

**Tier A - Post-training at Scale**: Companies doing significant RLHF, DPO, or custom post-training on base models - not just LoRA or simple fine-tuning. Examples: Cursor (Composer model), Character.ai. Need: 100s-1000s of GPUs. Score: 45 points.

**Tier B - Massive In-House Inference**: Companies serving millions of users with AI products AND running their own inference infrastructure (not just calling OpenAI/Anthropic APIs). Examples: Perplexity (runs own inference), You.com. Key distinction: They must be running inference themselves, not outsourcing to API providers. Need: 100s-1000s of GPUs. Score: 45 points.

**Tier C - AI Infrastructure Platform**: Companies providing GPU/inference/training infrastructure to other AI companies. Examples: Together AI, Fireworks, Replicate, Modal, Anyscale. Need: 1000s+ of GPUs. Score: 45 points.

**Tier D - Specialized Training / High-GPU Industries**: Companies in inherently GPU-heavy industries OR with clear evidence of domain-specific model training:
- Autonomous Vehicles (perception models, simulation)
- Robotics (control models, reinforcement learning)
- Video AI / Computer Vision at scale
- Drug Discovery / Biotech ML
- Climate/Weather modeling
- Quantitative Trading / HFT (ML-driven trading firms run massive GPU clusters for model training and real-time inference)
Examples: May Mobility, Waymo, 1X, Figure AI, Recursion Pharma, Radix Trading, Two Sigma, Citadel. Need: 100s-1000s of GPUs. Score: 35-40 points.

**Tier E - Light AI Usage / API Wrappers / Unproven**: Companies that:
- Primarily use third-party APIs (OpenAI, Anthropic, Google)
- Claim "AI-powered" but show no evidence of model training
- Build applications on top of AI, not AI itself
- Have "no clear evidence" of training or in-house inference
Examples: Most "AI-powered" SaaS apps, chatbot wrappers, data labeling tools without custom models. Need: Minimal. Score: 10 points.

**CRITICAL**: If your analysis concludes "no clear evidence of training foundation models or running massive inference" - that is Tier E (10 points), NOT Tier D.

**UNKNOWN**: Cannot determine from available information. Score: 5 points.

## CRITICAL Distinctions:

1. **In-house inference vs API usage**: A company serving millions of users but using OpenAI's API is Tier E, not Tier B. Tier B requires SELF-HOSTED inference at scale.

2. **Industry matters**: Autonomous vehicles, robotics, video AI, and drug discovery companies almost always need significant GPU infrastructure for training perception models, simulation, etc. Give them credit even if specifics aren't public.

3. **"Fine-tuned" is often Tier E**: Unless there's evidence of custom model development beyond basic fine-tuning, assume Tier E.

4. **Funding signals budget, not GPU need**: A well-funded company using only APIs is still Tier E. Funding helps with Scale score, not GPU Use Case score.

## Signals to Look For:

**Strong GPU Need Signals (Tier S/A/B/C/D):**
- "Training our own models" / "proprietary foundation models"
- "Built our own LLM/model from scratch"
- "Pre-training" or "post-training" mentions
- Large ML/AI research teams (10+ ML engineers)
- Published papers on model architectures
- Running own inference infrastructure
- "Platform" providing GPU/inference to developers
- Autonomous vehicles, robotics, video understanding, drug discovery
- NVIDIA partnerships for compute

**Weak/Negative Signals (Tier E):**
- "Powered by GPT-4" / "Built on Claude" / "Using OpenAI API"
- "Fine-tuned GPT" / "Fine-tuned Llama" (without deeper custom work)
- Application layer focus ("AI-powered" marketing)
- No ML engineering roles in job postings
- Pure software company adding AI features

## Output Format:

You MUST respond with valid JSON only. No other text before or after the JSON.
"""

ANALYSIS_PROMPT_TEMPLATE = """Analyze the following search results for the company "{company_name}" and provide a structured assessment.

{search_results}

---

Based on the above information, provide your analysis in the following JSON format:

{{
  "company_name": "{company_name}",
  "research": {{
    "description": "Brief 1-2 sentence description of what the company does",
    "employee_count": "Estimated number or range (e.g., '150' or '100-500' or 'Unknown')",
    "total_funding": "Total funding raised as text (e.g., '$25M' or 'Unknown')",
    "funding_millions": 25.0,
    "last_round": "Last funding round info (e.g., 'Series A, $10M, Jan 2024' or 'Unknown')",
    "investors": ["List", "of", "known", "investors"],
    "headquarters": "City, Country or 'Unknown'",
    "founded_year": 2020,
    "industry": "Primary industry/vertical",
    "business_model": "B2B SaaS / B2C / Platform / etc."
  }},
  "gpu_analysis": {{
    "use_case_tier": "S/A/B/C/D/E/UNKNOWN",
    "use_case_label": "One of: Frontier pre-training / Post-training at scale / Massive inference / AI infrastructure platform / Specialized model training / Fine-tuning or API wrapper / Unknown",
    "reasoning": "2-3 sentences explaining why you classified them this way, citing specific evidence",
    "signals_positive": ["List of signals indicating GPU need"],
    "signals_negative": ["List of signals suggesting low GPU need"]
  }},
  "scores": {{
    "gpu_use_case": 0,
    "scale_budget": 0,
    "growth_signals": 0,
    "confidence": 0
  }}
}}

## Scoring Guidelines:

**gpu_use_case (0-50 points):** - THE MOST IMPORTANT SCORE
- Tier S (Frontier Pre-training): 50 points
- Tier A (Post-training at Scale): 45 points  
- Tier B (Massive In-House Inference): 45 points - ONLY if they run own inference, not APIs
- Tier C (AI Infrastructure Platform): 45 points
- Tier D (Specialized Training / High-GPU Industry): 35 points - includes AV, robotics, video AI, drug discovery
- Tier E (API Wrappers / Light AI): 10 points - most "AI-powered" apps fall here
- UNKNOWN: 5 points

**scale_budget (0-30 points):**
- $100M+ funding: 30 points
- $50-100M: 25 points
- $20-50M: 20 points
- $10-20M: 15 points
- $5-10M: 10 points
- <$5M or bootstrapped: 5 points
- Unknown funding: 10 points (assume some funding if they exist)
- **INDUSTRY BONUS**: Quantitative trading / HFT firms are notoriously well-capitalized. If funding is unknown for a quant firm, assume 25 points.

**growth_signals (0-10 points):** - Replaces timing_urgency, lower weight
- Rapid user/revenue growth: +4 points
- Actively hiring ML/infra roles: +3 points
- Recent funding or expansion: +3 points
- No growth signals: 0 points

**confidence (0-10 points):**
- High confidence (multiple sources, clear evidence): 10 points
- Medium confidence (some info found): 5 points
- Low confidence (little info, uncertain): 2 points

**IMPORTANT SCORING NOTES:**
- A company using OpenAI/Anthropic APIs should NEVER score above 10 for gpu_use_case, regardless of their funding or size.
- Autonomous vehicle, robotics, video AI, and quant trading companies should be AT LEAST Tier D (35 points) unless they clearly outsource all AI.
- Be skeptical of "AI-powered" marketing - look for evidence of actual model training.
- If your reasoning says "no clear evidence" of training or inference - that's Tier E (10 points), not Tier D.

**FUNDING_MILLIONS FIELD:**
- Convert total funding to a numeric value in millions USD
- "$25M" → 25.0
- "$1.5B" → 1500.0
- "$500K" → 0.5
- "Unknown" → null
- For quant/HFT firms with unknown funding, estimate 500.0 (they are typically well-capitalized)

Respond with ONLY the JSON object, no other text."""


class LLMService:
    """Service for analyzing companies using Crusoe Cloud LLM."""
    
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.crusoe_api_base_url,
            api_key=settings.crusoe_api_key,
        )
        self.model = settings.crusoe_model
    
    async def _perform_analysis(self, company_name: str, prompt: str) -> dict:
        """
        Internal method to perform LLM analysis (with retry support).

        Args:
            company_name: Name of the company
            prompt: Formatted prompt string

        Returns:
            LLM API response

        Raises:
            Exception: If the analysis fails
        """
        def sync_analyze():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                top_p=0.9,
                timeout=settings.llm_timeout,  # Add timeout
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_analyze)

    async def analyze_company(self, company_name: str, search_results: str) -> dict:
        """
        Analyze a company based on search results with retry logic and usage tracking.

        Args:
            company_name: Name of the company
            search_results: Formatted search results string

        Returns:
            dict with structured analysis, usage stats, and timing information
        """
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            company_name=company_name,
            search_results=search_results,
        )

        try:
            logger.info(f"Analyzing company: {company_name}")
            start_time = time.time()

            # Perform analysis with retry logic
            response = await retry_with_backoff(
                self._perform_analysis,
                company_name,
                prompt,
                max_retries=settings.max_retries,
                base_delay=settings.retry_base_delay,
                exceptions=(Exception,),
            )

            response_time = time.time() - start_time

            # Extract token usage
            tokens_used = 0
            if hasattr(response, 'usage') and response.usage:
                tokens_used = response.usage.total_tokens or 0
            
            response_text = response.choices[0].message.content.strip()
            logger.debug(f"LLM response for {company_name}: {response_text[:200]}...")

            # Parse JSON response
            try:
                # Try to extract JSON if there's extra text
                if response_text.startswith("{"):
                    json_str = response_text
                else:
                    # Find JSON in response
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_str = response_text[start:end]
                    else:
                        raise ValueError("No JSON found in response")

                analysis = json.loads(json_str)

                # Calculate total score
                scores = analysis.get("scores", {})
                total_score = (
                    scores.get("gpu_use_case", 0) +
                    scores.get("scale_budget", 0) +
                    scores.get("growth_signals", 0) +
                    scores.get("confidence", 0)
                )
                analysis["scores"]["total"] = total_score

                # Normalize timing_urgency to growth_signals if old format
                if "timing_urgency" in scores and "growth_signals" not in scores:
                    scores["growth_signals"] = scores.pop("timing_urgency")

                # Determine priority tier (adjusted for new max of 100)
                # HOT: 75+ (strong GPU use case + decent funding)
                # WARM: 55-74 (moderate GPU needs or high funding with some GPU need)
                # WATCH: 35-54 (potential but unproven)
                # COLD: <35 (API wrappers, no real GPU need)
                if total_score >= 75:
                    priority_tier = "HOT"
                    recommended_action = "High-priority outreach - strong GPU infrastructure needs with budget"
                elif total_score >= 55:
                    priority_tier = "WARM"
                    recommended_action = "Worth qualifying - potential GPU needs, investigate further"
                elif total_score >= 35:
                    priority_tier = "WATCH"
                    recommended_action = "Monitor for future - may develop GPU needs as they grow"
                else:
                    priority_tier = "COLD"
                    recommended_action = "Low priority - likely using third-party APIs, minimal GPU needs"

                analysis["priority_tier"] = priority_tier
                analysis["recommended_action"] = recommended_action
                analysis["success"] = True
                analysis["raw_response"] = response_text
                analysis["tokens_used"] = tokens_used
                analysis["response_time"] = response_time

                logger.info(
                    f"Analysis complete for {company_name}: {priority_tier} ({total_score} points, "
                    f"tokens: {tokens_used}, time: {response_time:.2f}s)"
                )

                return analysis

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response for {company_name}: {e}")
                return {
                    "success": False,
                    "error": f"Failed to parse LLM response: {e}",
                    "raw_response": response_text,
                    "company_name": company_name,
                    "tokens_used": tokens_used,
                    "response_time": response_time,
                }

        except Exception as e:
            logger.error(f"LLM analysis failed for {company_name} after {settings.max_retries} retries: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "company_name": company_name,
                "tokens_used": 0,
                "response_time": 0.0,
            }


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

