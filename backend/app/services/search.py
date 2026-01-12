"""Tavily search service for company research."""

from tavily import TavilyClient
from typing import Optional
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SearchService:
    """Service for searching company information using Tavily."""
    
    def __init__(self):
        self.client = TavilyClient(api_key=settings.tavily_api_key)
    
    async def search_company(self, company_name: str) -> dict:
        """
        Search for company information.
        
        Args:
            company_name: Name of the company to research
            
        Returns:
            dict with search results including snippets and URLs
        """
        # Craft a search query optimized for finding GPU/AI infrastructure needs
        query = f"{company_name} AI startup company funding employees training models infrastructure"
        
        try:
            logger.info(f"Searching for: {company_name}")
            
            # Use Tavily's search with options optimized for company research
            response = self.client.search(
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
            )
            
            logger.info(f"Found {len(response.get('results', []))} results for {company_name}")
            
            return {
                "success": True,
                "company_name": company_name,
                "query": query,
                "answer": response.get("answer", ""),
                "results": response.get("results", []),
                "raw_response": response,
            }
            
        except Exception as e:
            logger.error(f"Search failed for {company_name}: {str(e)}")
            return {
                "success": False,
                "company_name": company_name,
                "query": query,
                "error": str(e),
                "results": [],
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



