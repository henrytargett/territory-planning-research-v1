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

## ⚠️ CRITICAL: ANTI-HALLUCINATION RULES ⚠️

**YOU MUST ONLY USE INFORMATION EXPLICITLY STATED IN THE SEARCH RESULTS. DO NOT:**
1. ❌ Invent or assume what a company does based on keywords in unrelated articles
2. ❌ Make up company descriptions if the search results are sparse or irrelevant
3. ❌ Classify a company as AI-related just because GPU/AI terms appear in search results
4. ❌ Score a company highly if you cannot find DIRECT EVIDENCE of their business model
5. ❌ Assume a company is real if search results show no legitimate business information

**IF SEARCH RESULTS ARE:**
- Mostly ads, parked domains, or spam → Score as TIER E (10 points) with low confidence
- Irrelevant or about different companies → Score as TIER E (10 points), note in reasoning
- No real company information found → Score as UNKNOWN (5 points) with confidence 2
- Company appears fake/non-existent → Score as TIER E (10 points), state "No legitimate business found"

**VERIFICATION CHECKLIST - Before scoring above TIER D, confirm:**
✓ The company has a real website with actual product/service information
✓ Multiple independent sources confirm what they do
✓ Their business description matches across sources
✓ There's evidence of actual operations (employees, funding, customers, etc.)

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

MANAGED_INFERENCE_SYSTEM_PROMPT = """You are an expert analyst specializing in identifying companies that are Managed Inference Targets.

Managed Inference Targets are companies that serve large-scale AI inference via managed providers
(e.g., Fireworks AI, Baseten, Together.ai, or Anyscale) instead of running their own GPU servers.

Your task is to analyze search results and determine whether a company is a strong candidate
for reserved inference capacity on a managed platform.

## CRITICAL RULES

- Use ONLY information explicitly stated in the search results.
- Do NOT assume infrastructure choices without evidence.
- If evidence is weak or contradictory, score as UNKNOWN with low confidence.
- Infrastructure providers themselves (Fireworks, Baseten, Together.ai) are NOT targets.

## Managed Inference Tiers (use use_case_tier field)

**Tier S - Enterprise-scale Managed Inference**: Massive user base, AI is core, clear signals of
reserved capacity or dedicated endpoints. Score: 50.
**Tier A - High-volume Managed Inference**: Strong product usage, likely reserved capacity,
some evidence of managed inference usage. Score: 45.
**Tier B - Production Managed Inference**: Live AI product at scale but not massive, or partial
evidence of managed inference usage. Score: 35.
**Tier C - Small-scale / Experimental**: Early adoption or low volume, weak scale signals. Score: 25.
**Tier D - API Wrapper / Low Scale**: Basic API usage without scale needs. Score: 10.
**UNKNOWN**: Cannot determine from available info. Score: 5.

## Signals to look for

Positive:
- Mentions of managed inference providers (Fireworks, Baseten, Together.ai, Anyscale)
- "Dedicated endpoints", "reserved capacity", "provisioned throughput"
- Engineering blogs about scaling inference without managing GPUs
- High-volume AI product usage (coding assistant, productivity AI, realtime AI)
- Open-weights models served via managed APIs (Llama 3, Mistral, Qwen)

Negative:
- Running own Kubernetes or GPU fleet (those are IaaS targets)
- Pure API wrapper with no scale
- No evidence of managed inference usage

## Output Format:
You MUST respond with valid JSON only. No other text before or after the JSON.
"""

ANALYSIS_PROMPT_TEMPLATE = """Analyze the following search results for the company "{company_name}" and provide a structured assessment.

{search_results}

---

⚠️ BEFORE YOU ANALYZE: Perform these sanity checks:
1. Do the search results actually describe what {company_name} does?
2. Is {company_name} a real company with a real business?
3. Do multiple sources confirm the same information?
4. Are you about to make claims NOT supported by the search results above?

If the answer to questions 1-3 is NO, or question 4 is YES: Score as Tier E or UNKNOWN with low confidence.

**RED FLAGS** - If you see these, score as Tier E (10 points) max:
- Company is in logistics/delivery/fulfillment (unless explicit ML evidence)
- Search results show no real business, just a domain name
- Results are unrelated articles that happen to mention GPU/AI
- You cannot clearly explain what the company does from the results
- Company name looks fake or suspicious (e.g., "jomspar.com")

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
- **Package delivery, fulfillment, logistics, e-commerce companies are NOT AI companies** - Score as Tier E (10 points) unless explicit evidence of custom ML models.
- **Domain names without real businesses** (parked domains, "coming soon" pages) - Score as Tier E (10 points) with confidence 2.
- **If you cannot verify what the company actually does from search results** - Score as UNKNOWN (5 points) with low confidence, don't guess.

**FUNDING_MILLIONS FIELD:**
- Convert total funding to a numeric value in millions USD
- "$25M" → 25.0
- "$1.5B" → 1500.0
- "$500K" → 0.5
- "Unknown" → null
- For quant/HFT firms with unknown funding, estimate 500.0 (they are typically well-capitalized)

Respond with ONLY the JSON object, no other text."""

MANAGED_INFERENCE_PROMPT_TEMPLATE = """Analyze the following search results for the company "{company_name}" and provide a structured assessment.

{search_results}

---

This is the "Managed Inference Targets" analysis. You must determine if the company is
likely to purchase reserved inference capacity via a managed provider.

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
    "use_case_tier": "S/A/B/C/D/UNKNOWN",
    "use_case_label": "One of: Enterprise managed inference / High-volume managed inference / Production managed inference / Small-scale managed inference / API wrapper / Unknown",
    "reasoning": "2-3 sentences explaining why you classified them this way, citing specific evidence",
    "signals_positive": ["List of signals indicating managed inference usage"],
    "signals_negative": ["List of signals suggesting low or no managed inference usage"]
  }},
  "scores": {{
    "gpu_use_case": 0,
    "scale_budget": 0,
    "growth_signals": 0,
    "confidence": 0
  }}
}}

## Scoring Guidelines (Managed Inference Targets)

**gpu_use_case (0-50 points):** Use this field to represent INFERENCE SCALE.
- Tier S (Enterprise managed inference): 50 points
- Tier A (High-volume managed inference): 45 points
- Tier B (Production managed inference): 35 points
- Tier C (Small-scale/experimental): 25 points
- Tier D (API wrapper/low scale): 10 points
- UNKNOWN: 5 points

**scale_budget (0-30 points):** Use this field to represent MANAGED PLATFORM ADOPTION.
- Confirmed managed provider usage (Fireworks/Baseten/Together/Anyscale): 30 points
- Strong hints of managed endpoints / reserved capacity: 20 points
- Possible managed usage but unclear: 10 points
- No evidence of managed inference: 0 points

**growth_signals (0-10 points):**
- Rapid user/revenue growth: +4 points
- Hiring AI/ML or platform roles: +3 points
- Recent funding or expansion: +3 points
- No growth signals: 0 points

**confidence (0-10 points):**
- High confidence (multiple sources, clear evidence): 10 points
- Medium confidence (some info found): 5 points
- Low confidence (little info, uncertain): 2 points
"""


class LLMService:
    """Service for analyzing companies using Crusoe Cloud LLM."""
    
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.crusoe_api_base_url,
            api_key=settings.crusoe_api_key,
        )
        self.model = settings.crusoe_model
    
    async def _perform_analysis(self, company_name: str, prompt: str, system_prompt: str) -> dict:
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
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent output
                top_p=0.9,
                timeout=settings.llm_timeout,  # Add timeout
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_analyze)

    async def analyze_company(self, company_name: str, search_results: str, target_type: str = "iaas") -> dict:
        """
        Analyze a company based on search results with retry logic and usage tracking.

        Args:
            company_name: Name of the company
            search_results: Formatted search results string

        Returns:
            dict with structured analysis, usage stats, and timing information
        """
        # PRE-VALIDATION: Limit search results size BEFORE creating prompt
        # This prevents 400 errors and oversized payloads from reaching the API
        MAX_SEARCH_RESULTS_SIZE = 100000  # 100KB max (prevents 400 errors)
        if len(search_results) > MAX_SEARCH_RESULTS_SIZE:
            logger.warning(
                f"Search results for {company_name} are {len(search_results)} chars, "
                f"truncating to {MAX_SEARCH_RESULTS_SIZE} to prevent API errors"
            )
            search_results = self._smart_truncate_search_results(search_results, MAX_SEARCH_RESULTS_SIZE)
        
        if target_type == "managed_inference":
            prompt = MANAGED_INFERENCE_PROMPT_TEMPLATE.format(
                company_name=company_name,
                search_results=search_results,
            )
            system_prompt = MANAGED_INFERENCE_SYSTEM_PROMPT
        else:
            prompt = ANALYSIS_PROMPT_TEMPLATE.format(
                company_name=company_name,
                search_results=search_results,
            )
            system_prompt = SYSTEM_PROMPT

        try:
            logger.info(f"Analyzing company: {company_name} (prompt size: {len(prompt)} chars)")
            start_time = time.time()

            # Perform analysis with retry logic
            # Try with full prompt first
            try:
                response = await retry_with_backoff(
                    self._perform_analysis,
                    company_name,
                    prompt,
                    system_prompt,
                    max_retries=settings.max_retries,
                    base_delay=settings.retry_base_delay,
                    exceptions=(Exception,),
                    retry_on_400=True,  # Retry on 400 errors (API rejections)
                )
            except Exception as e:
                error_str = str(e)
                # If it's a 413 error (payload too large), try with truncated prompt
                if '413' in error_str and 'too_large' in error_str:
                    logger.warning(f"Payload too large for {company_name}, retrying with truncated prompt")
                    # Truncate the search results part of the prompt (keep instructions, truncate data)
                    truncated_prompt = self._truncate_prompt_for_size(prompt)
                    response = await retry_with_backoff(
                        self._perform_analysis,
                        company_name,
                        truncated_prompt,
                        system_prompt,
                        max_retries=2,  # Fewer retries for truncated version
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

                # FALLBACK: Handle missing "scores" field (happens with truncated prompts)
                if "scores" not in analysis:
                    logger.warning(f"LLM response for {company_name} missing 'scores' field, using defaults")
                    analysis["scores"] = {
                        "gpu_use_case": 5,
                        "scale_budget": 10,
                        "growth_signals": 0,
                        "confidence": 2
                    }
                
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
    
    async def validate_tavily_data(self, company_name: str, search_results: str) -> dict:
        """
        Lightweight validation check to verify Tavily data quality.
        
        Uses a simple LLM prompt to check if the search results are relevant and complete.
        
        Args:
            company_name: Name of the company
            search_results: Formatted search results from Tavily
            
        Returns:
            dict with validation results:
            - is_valid: bool
            - confidence: float (0-1)
            - message: str (explanation)
            - tokens_used: int
            - response_time: float
        """
        validation_prompt = f"""You are validating search results for company research.

Company: {company_name}

Search Results:
{search_results[:2000]}  # Truncate to first 2000 chars for fast validation

Task: Determine if these search results are valid and useful for analyzing this company's GPU infrastructure needs.

Respond with ONLY a JSON object:
{{
  "is_valid": true/false,
  "confidence": 0.0-1.0,
  "message": "Brief explanation (1 sentence)",
  "issues": ["List", "of", "any", "problems"]
}}

Validation criteria:
- Results mention the company name (or close match)
- Results contain business/tech information (not just ads/boilerplate)
- At least 1 high-quality source is present
- Data is not obviously wrong/irrelevant
- Company appears to be a real, operating business

Mark as INVALID if:
- No results mention the company
- All results are generic/spam
- Company name completely mismatched (e.g., searched "Anthropic", got "Party City")
- Less than 50 words of actual content
- Company appears to be just a domain name / parked domain
- Search results are mostly unrelated articles that just happen to mention AI/GPU keywords
- Company name appears fake or non-existent (e.g., "jomspar.com" with no real business info)
- Results show company does something completely different (e.g., package delivery company, not AI)
- Multiple unrelated topics in results suggest search didn't find the right company

⚠️ BE STRICT: If you're unsure whether results match the company or if the company is real, mark as INVALID.
"""
        
        try:
            start_time = time.time()
            
            def sync_validate():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a data quality validator. Respond only with valid JSON."},
                        {"role": "user", "content": validation_prompt}
                    ],
                    temperature=0.1,  # Low temperature for consistent validation
                    max_tokens=200,   # Short response
                    timeout=10,       # Fast timeout
                )
            
            response = await asyncio.to_thread(sync_validate)
            response_time = time.time() - start_time
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            validation_result = json.loads(content)
            
            # Extract usage
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(
                f"Validated {company_name}: {'VALID' if validation_result['is_valid'] else 'INVALID'} "
                f"(confidence: {validation_result['confidence']:.2f}, tokens: {tokens_used}, time: {response_time:.2f}s)"
            )
            
            return {
                "success": True,
                "is_valid": validation_result.get("is_valid", False),
                "confidence": validation_result.get("confidence", 0.0),
                "message": validation_result.get("message", ""),
                "issues": validation_result.get("issues", []),
                "tokens_used": tokens_used,
                "response_time": response_time,
            }
            
        except Exception as e:
            logger.error(f"Validation failed for {company_name}: {str(e)}")
            # On validation failure, assume data is valid (fail open)
            return {
                "success": False,
                "is_valid": True,  # Fail open - don't block on validation errors
                "confidence": 0.5,
                "message": f"Validation error: {str(e)}",
                "issues": ["validation_failed"],
                "tokens_used": 0,
                "response_time": 0,
            }


    def _smart_truncate_search_results(self, search_results: str, max_size: int) -> str:
        """
        Intelligently truncate search results while preserving structure.
        
        This is called BEFORE creating the prompt to prevent oversized payloads.
        
        Args:
            search_results: Formatted search results string
            max_size: Maximum character size
            
        Returns:
            Truncated search results
        """
        if len(search_results) <= max_size:
            return search_results
        
        try:
            # Keep header and first few sources (most relevant)
            lines = search_results.split('\n')
            truncated_lines = []
            current_size = 0
            
            for line in lines:
                if current_size + len(line) > max_size:
                    break
                truncated_lines.append(line)
                current_size += len(line) + 1  # +1 for newline
            
            result = '\n'.join(truncated_lines)
            result += f"\n\n[Truncated: Original had {len(search_results)} chars, showing first {len(result)} chars]"
            
            logger.info(f"Truncated search results from {len(search_results)} to {len(result)} chars")
            return result
            
        except Exception as e:
            logger.warning(f"Error in smart truncation: {e}, using simple truncation")
            return search_results[:max_size] + "\n\n[Content truncated]"

    def _truncate_prompt_for_size(self, prompt: str) -> str:
        """
        DEPRECATED: This method is now a fallback only.
        We now truncate search results BEFORE creating the prompt.
        
        Truncate the search results portion of the prompt to reduce payload size.

        Args:
            prompt: Original prompt string

        Returns:
            Truncated prompt with smaller search results
        """
        try:
            # Split the prompt to isolate the search results section
            parts = prompt.split("---")
            if len(parts) < 2:
                # Fallback: truncate the entire prompt
                logger.warning("Could not find '---' separator in prompt, using simple truncation")
                return prompt[:50000] + "\n\n[Content truncated due to size limits - NOTE: This may cause invalid JSON responses]"

            # Keep instructions (everything before search results) and truncate results
            instructions = parts[0]
            search_and_format = "---".join(parts[1:])
            
            # Target size: keep instructions + ~50KB of results
            max_total_size = 60000
            available_for_results = max_total_size - len(instructions)
            
            if available_for_results < 10000:
                # Instructions are too long, truncate everything more aggressively
                logger.warning("Instructions too long, aggressive truncation")
                return prompt[:30000] + "\n\n[Content heavily truncated - NOTE: This may cause invalid JSON responses]"
            
            if len(search_and_format) <= available_for_results:
                return prompt
            
            # Truncate search results - keep FIRST part (most relevant) not last
            truncated_results = search_and_format[:available_for_results] + "\n\n[Content truncated - showing most relevant results]"
            
            result = instructions + "---" + truncated_results
            logger.info(f"Truncated prompt from {len(prompt)} to {len(result)} chars")
            return result

        except Exception as e:
            logger.warning(f"Error truncating prompt: {e}, using simple truncation")
            return prompt[:50000] + "\n\n[Content truncated due to size limits]"


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

