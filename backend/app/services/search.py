"""Tavily search service for company research."""

import time
import asyncio
from tavily import TavilyClient
from typing import Optional
import logging

from ..config import get_settings
from ..utils import retry_with_backoff, estimate_tavily_cost

logger = logging.getLogger(__name__)
settings = get_settings()


class SearchService:
    """Service for searching company information using Tavily."""

    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    async def _perform_search(self, company_name: str, query: str) -> dict:
        """
        Internal method to perform the actual search (with retry support).

        Args:
            company_name: Name of the company
            query: Search query string

        Returns:
            Tavily API response

        Raises:
            Exception: If the search fails
        """
        # Tavily client is synchronous, so we wrap it
        def sync_search():
            return self.client.search(
                query=query,
                search_depth="advanced",  # More thorough search
                max_results=10,           # Reduced from 20 to prevent oversized responses
                include_domains=[         # Prioritize business/tech sources
                    "crunchbase.com",
                    "linkedin.com",
                    "techcrunch.com",
                    "bloomberg.com",
                    "reuters.com",
                    "forbes.com",
                    "venturebeat.com",
                    "pitchbook.com",
                ],
                include_answer=False,     # DO NOT use Tavily's answer - it hallucinates company info
                include_raw_content=True, # Get full page content (not just snippets)
                include_usage=True,       # Get credit usage information
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_search)

    async def search_company(self, company_name: str, target_type: str = "iaas") -> dict:
        """
        Search for company information with retry logic and cost tracking.

        Args:
            company_name: Name of the company to research
            target_type: "iaas" or "managed_inference"

        Returns:
            dict with search results, usage stats, and cost information
        """
        # Craft a search query optimized for target type
        if target_type == "managed_inference":
            # BROAD query to find ANY company with AI features
            # Use quotes around company name to ensure Tavily treats it as an entity, not keywords
            # Let the LLM identify managed inference signals from general AI content
            query = f'"{company_name}" company AI features machine learning inference API deployment model serving'
        else:
            # Default: IaaS targets (GPU infrastructure)
            # Optimized: removed "startup" (excludes enterprises), added GPU-specific terms
            query = f'"{company_name}" company GPU compute infrastructure machine learning training inference funding'

        try:
            logger.info(f"Searching for: {company_name}")
            start_time = time.time()

            # Perform search with retry logic
            response = await retry_with_backoff(
                self._perform_search,
                company_name,
                query,
                max_retries=settings.max_retries,
                base_delay=settings.retry_base_delay,
                exceptions=(Exception,),  # Retry on any exception
            )

            response_time = time.time() - start_time

            # Extract usage information
            usage = response.get("usage", {})
            credits_used = usage.get("credits", 2.0)  # Default to 2 for advanced search
            estimated_cost = estimate_tavily_cost(credits_used)

            logger.info(
                f"Found {len(response.get('results', []))} results for {company_name} "
                f"(credits: {credits_used}, cost: ${estimated_cost:.4f}, time: {response_time:.2f}s)"
            )

            return {
                "success": True,
                "company_name": company_name,
                "query": query,
                "target_type": target_type,
                "answer": response.get("answer", ""),
                "results": response.get("results", []),
                "credits_used": credits_used,
                "estimated_cost_usd": estimated_cost,
                "response_time": response_time,
                "raw_response": response,
            }

        except Exception as e:
            logger.error(f"Search failed for {company_name} after {settings.max_retries} retries: {str(e)}")
            return {
                "success": False,
                "company_name": company_name,
                "query": query,
                "error": str(e),
                "results": [],
                "credits_used": 0.0,
                "estimated_cost_usd": 0.0,
            }
    
    def format_search_results_for_llm(self, search_response: dict, min_score: float = 0.2) -> str:
        """
        Format search results into a string for the LLM to analyze.
        
        Args:
            search_response: Response from search_company()
            min_score: Minimum relevance score (0-1) to include results (default 0.2)
            
        Returns:
            Formatted string with search results
        """
        if not search_response.get("success"):
            return f"Search failed: {search_response.get('error', 'Unknown error')}"
        
        parts = [f"# Search Results for: {search_response['company_name']}\n"]
        
        # ⚠️ DO NOT include Tavily's "answer" field - it hallucinates!
        # Tavily's LLM-generated summaries frequently fabricate company information,
        # especially claiming non-AI companies are "AI infrastructure platforms".
        # We only use the raw source documents to prevent hallucinations.
        
        # Filter results by relevance score and sort by score (highest first)
        results = search_response.get("results", [])
        filtered_results = [r for r in results if r.get("score", 0) >= min_score]
        sorted_results = sorted(filtered_results, key=lambda x: x.get("score", 0), reverse=True)
        
        logger.info(f"Filtered {len(results)} results to {len(sorted_results)} (score >= {min_score})")
        
        # Add individual results
        parts.append(f"## Sources ({len(sorted_results)} high-quality results)\n")
        for i, result in enumerate(sorted_results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            score = result.get("score", 0)
            
            # Prefer raw_content (full page) over content (snippet)
            content = result.get("raw_content") or result.get("content", "No content")
            
            parts.append(f"### Source {i}: {title} (relevance: {score:.2f})")
            parts.append(f"URL: {url}")
            parts.append(f"Content: {content}\n")
        
        return "\n".join(parts)


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service



