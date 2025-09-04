from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from tavily import TavilyClient
from config import settings
from core.repositories.tool_logs import ToolLogRepo


class TavilyService:
    def __init__(self, *, repo: Optional[ToolLogRepo] = None) -> None:
        if not settings.tavily_api_key:
            raise RuntimeError("Tavily API key is not configured")
        self.client = TavilyClient(api_key=settings.tavily_api_key)
        self.repo = repo or ToolLogRepo()

    def search(self, *, user_id: Union[int, str], query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        resp = self.client.search(query, max_results=max_results)
        results = resp.get("results") or []
        try:
            self.repo.log_search(user_id=user_id, query=query, results=results)
        except Exception:
            pass
        return results

    def recent_results(self, *, user_id: Union[int, str], limit: int = 20) -> List[Dict[str, Any]]:
        return self.repo.list_recent(user_id=user_id, limit=limit)


