"""Web search tools.

Tools for searching the web using Tavily API.
"""

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List

import requests

if TYPE_CHECKING:
    from ..pc_manager import PCManager

logger = logging.getLogger(__name__)


def _get_tavily_api_key() -> str | None:
    """Get Tavily API key from environment.

    Returns:
        API key or None if not configured
    """
    return os.getenv("TAVILY_API_KEY")


def _build_search_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build Tavily API request payload from arguments.

    Args:
        args: Dictionary containing search parameters

    Returns:
        Dictionary with API payload
    """
    max_results = args.get("max_results", 5)

    payload = {
        "query": args.get("query"),
        "search_depth": args.get("search_depth", "basic"),
        "max_results": min(max(1, max_results), 20),
        "topic": args.get("topic", "general"),
        "include_answer": args.get("include_answer", False),
    }

    time_range = args.get("time_range")
    if time_range:
        payload["time_range"] = time_range

    return payload


def _call_tavily_api(payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Call Tavily search API.

    Args:
        payload: API request payload
        api_key: Tavily API key

    Returns:
        API response data

    Raises:
        requests.exceptions.RequestException: On API errors
    """
    response = requests.post(
        "https://api.tavily.com/search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    response.raise_for_status()
    data: Dict[str, Any] = response.json()
    return data


def _parse_search_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract and format search results from API response.

    Args:
        data: API response data

    Returns:
        List of formatted result dictionaries
    """
    results = []
    for result in data.get("results", []):
        results.append(
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0),
            }
        )
    return results


def _handle_api_error(e: Exception, query: str) -> Dict[str, Any]:
    """Handle API errors and return appropriate error response.

    Args:
        e: The exception that occurred
        query: Original search query

    Returns:
        Error response dictionary
    """
    if isinstance(e, requests.exceptions.HTTPError):
        if e.response.status_code == 401:
            logger.error("Tavily API authentication failed")
            return {
                "success": False,
                "error": "Tavily API authentication failed. Please check your TAVILY_API_KEY.",
                "query": query,
            }
        elif e.response.status_code == 429:
            logger.error("Tavily API rate limit exceeded")
            return {
                "success": False,
                "error": "Rate limit exceeded. Please try again later.",
                "query": query,
            }
        else:
            logger.error(f"Tavily API error: {e}")
            return {
                "success": False,
                "error": f"Tavily API error: {str(e)}",
                "query": query,
            }
    elif isinstance(e, requests.exceptions.RequestException):
        logger.error(f"Web search request failed: {e}")
        return {
            "success": False,
            "error": f"Request failed: {str(e)}",
            "query": query,
        }
    else:
        logger.error(f"Web search unexpected error: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "query": query,
        }


def create_web_search_tool(pc_manager: "PCManager"):
    """Create web_search tool using Tavily API.

    Args:
        pc_manager: PCManager instance (for logging purposes)

    Returns:
        Tool instance for web_search
    """
    from .base import Tool

    def execute_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search using Tavily API.

        Args:
            args: Dictionary containing query, search_depth, max_results, topic,
                  time_range, and include_answer options

        Returns:
            Dictionary with search results or error
        """
        query: str = args.get("query", "")

        # Validate API key
        api_key = _get_tavily_api_key()
        if not api_key:
            logger.error("TAVILY_API_KEY not configured")
            return {
                "success": False,
                "error": (
                    "Web search is not configured. Please set TAVILY_API_KEY in secrets/pc.env"
                ),
                "query": query,
            }

        try:
            # Build and execute search
            payload = _build_search_payload(args)
            logger.info(
                f"Web search: query='{query}', depth={payload['search_depth']}, "
                f"max_results={payload['max_results']}"
            )

            data = _call_tavily_api(payload, api_key)
            results = _parse_search_results(data)

            response_data = {
                "success": True,
                "query": query,
                "results": results,
                "result_count": len(results),
                "response_time": data.get("response_time", 0),
            }

            # Include AI-generated answer if requested
            if payload.get("include_answer") and data.get("answer"):
                response_data["answer"] = data["answer"]

            logger.info(
                f"Web search completed: {len(results)} results in "
                f"{data.get('response_time', 0):.2f}s"
            )

            return response_data

        except Exception as e:
            return _handle_api_error(e, query)

    return Tool(
        name="web_search",
        description="Search the web using Tavily search engine",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth level",
                    "enum": ["basic", "fast", "ultra-fast", "advanced"],
                    "default": "basic",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-20)",
                    "default": 5,
                },
                "topic": {
                    "type": "string",
                    "description": "Search topic category",
                    "enum": ["general", "news", "finance"],
                    "default": "general",
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range filter",
                    "enum": ["day", "week", "month", "year"],
                },
                "include_answer": {
                    "type": "boolean",
                    "description": "Whether to include AI-generated answer",
                    "default": False,
                },
            },
            "required": ["query"],
        },
        execute_func=execute_web_search,
        category="search",
        dangerous=False,
        allowed_by_default=True,
    )


def register_web_search_tools(registry, pc_manager: "PCManager"):
    """Register web search tools with the registry.

    Args:
        registry: ToolRegistry instance
        pc_manager: PCManager instance
    """
    registry.register_tool(create_web_search_tool(pc_manager))
