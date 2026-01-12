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
                max_results=8,            # Get enough context
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
                include_answer=True,      # Get a summarized answer
                include_usage=True,       # Get credit usage information
            )

        # Run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(sync_search)

    async def search_company(self, company_name: str) -> dict:
        """
        Search for company information with retry logic and cost tracking.

        Args:
            company_name: Name of the company to research

        Returns:
            dict with search results, usage stats, and cost information
        """
        # Craft a search query optimized for finding GPU/AI infrastructure needs
        query = f"{company_name} AI startup company funding employees training models infrastructure"

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
    
    def format_search_results_for_llm(self, search_response: dict) -> str:
        """
        Format search results into a string for the LLM to analyze.
        
        Args:
            search_response: Response from search_company()
            
        Returns:
            Formatted string with search results
        """
        if not search_response.get("success"):
            return f"Search failed: {search_response.get('error', 'Unknown error')}"
        
        parts = [f"# Search Results for: {search_response['company_name']}\n"]
        
        # Add the summarized answer if available
        if search_response.get("answer"):
            parts.append(f"## Summary\n{search_response['answer']}\n")
        
        # Add individual results
        parts.append("## Sources\n")
        for i, result in enumerate(search_response.get("results", []), 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "No content")
            
            parts.append(f"### Source {i}: {title}")
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



