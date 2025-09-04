from __future__ import annotations

from typing import Any, Dict, List, Union

from langchain_core.tools import tool
from langsmith import traceable

from core.services.tavily_service import TavilyService


@tool("tavily_search")
@traceable(name="tool.tavily_search")
def tavily_search_tool(user_id: Union[int, str], query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Perform a web search with Tavily and persist results to tool logs.
    Returns a list of results (title, url, content/snippets if present).
    """
    svc = TavilyService()
    return svc.search(user_id=user_id, query=query, max_results=max_results)


