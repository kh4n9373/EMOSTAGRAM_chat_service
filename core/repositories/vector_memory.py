from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from config import settings


class QdrantVectorRepo:
    def __init__(self, *, collection: str | None = None) -> None:
        if not settings.qdrant_url:
            raise RuntimeError("Qdrant URL not configured")
        self.collection = collection or settings.qdrant_collection
        self.client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        try:
            self.client.get_collection(self.collection)
        except Exception:
            self.client.recreate_collection(
                collection_name=self.collection,
                vectors_config=qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE),
            )

    def upsert_memory(self, *, user_id: Union[int, str], text: str, embedding: List[float]) -> None:
        payload = {"user_id": str(user_id), "text": text}
        self.client.upsert(
            collection_name=self.collection,
            points=[qmodels.PointStruct(id=None, vector=embedding, payload=payload)],
        )

    def search(self, *, user_id: Union[int, str], query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        res = self.client.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=qmodels.Filter(must=[qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=str(user_id)))])
        )
        out: List[Dict[str, Any]] = []
        for p in res:
            payload = dict(p.payload or {})
            payload["score"] = float(p.score or 0)
            out.append(payload)
        return out


