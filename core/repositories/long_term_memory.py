from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

import numpy as np

from core.database.mongodb_client import MongoManager


class LongTermMemoryRepo:
    """
    MongoDB-backed repository for long-term memory facts per user.
    Stores text content and its embedding vector for similarity search.
    """

    def __init__(self, *, db_name: str = "EMOSTAGRAM", collection: str = "long_term_memory") -> None:
        self.client = MongoManager(db=db_name)
        self.collection = collection

    def add_memory(
        self,
        *,
        user_id: Union[int, str],
        content: str,
        embedding: List[float],
        source: str = "extracted",
    ) -> str:
        doc: Dict[str, Any] = {
            "user_id": user_id,
            "content": content,
            "embedding": embedding,
            "source": source,
            "created_at": datetime.now(timezone.utc),
        }
        self.client.insert_one(self.collection, doc)
        # ObjectId is created by Mongo, but we return content as id is not immediately available
        return content

    def list_by_user(self, *, user_id: Union[int, str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sort = [("created_at", -1), ("_id", -1)]
        candidates = self._candidate_user_ids(user_id)
        docs = self.client.find(self.collection, filter={"user_id": {"$in": candidates}}, sort=sort, limit=limit)
        return docs

    def delete_by_user(self, *, user_id: Union[int, str]) -> int:
        candidates = self._candidate_user_ids(user_id)
        # MongoManager.delete_many returns None; we can run raw operation via private handle
        coll = self.client._MongoManager__database[self.collection]
        res = coll.delete_many({"user_id": {"$in": candidates}})
        return int(getattr(res, "deleted_count", 0))

    def search_similar(
        self,
        *,
        user_id: Union[int, str],
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Naive in-memory cosine similarity over user's memories. Suitable for small scale.
        """
        docs = self.list_by_user(user_id=user_id, limit=None)
        if not docs:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        if np.linalg.norm(q) == 0:
            return []
        q = q / (np.linalg.norm(q) + 1e-12)

        scored: List[tuple[float, Dict[str, Any]]] = []
        for d in docs:
            emb = np.array(d.get("embedding") or [], dtype=np.float32)
            if emb.size == 0:
                continue
            emb = emb / (np.linalg.norm(emb) + 1e-12)
            sim = float(np.dot(q, emb))
            scored.append((sim, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[: max(1, top_k)]]

    @staticmethod
    def _candidate_user_ids(user_id: Union[int, str]) -> List[Union[int, str]]:
        cand: List[Union[int, str]] = [user_id]
        s = str(user_id)
        if s not in cand:
            cand.append(s)
        if isinstance(user_id, str) and user_id.isdigit():
            i = int(user_id)
            if i not in cand:
                cand.append(i)
        return cand


