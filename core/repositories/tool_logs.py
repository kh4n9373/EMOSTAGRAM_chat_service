from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

from core.database.mongodb_client import MongoManager


class ToolLogRepo:
    """
    Simple repository to persist tool call results (e.g., Tavily search) per user.
    """

    def __init__(self, *, db_name: str = "EMOSTAGRAM", collection: str = "tool_logs") -> None:
        self.client = MongoManager(db=db_name)
        self.collection = collection

    def log_search(
        self,
        *,
        user_id: Union[int, str],
        query: str,
        results: List[Dict[str, Any]],
        tool_name: str = "tavily",
    ) -> None:
        doc: Dict[str, Any] = {
            "user_id": user_id,
            "tool": tool_name,
            "query": query,
            "results": results,
            "created_at": datetime.now(timezone.utc),
        }
        self.client.insert_one(self.collection, doc)

    def list_recent(self, *, user_id: Union[int, str], limit: int = 20) -> List[Dict[str, Any]]:
        sort = [("created_at", -1), ("_id", -1)]
        return self.client.find(self.collection, filter={"user_id": {"$in": [user_id, str(user_id)]}}, sort=sort, limit=limit)


