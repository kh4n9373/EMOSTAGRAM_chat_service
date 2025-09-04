from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import json

from sentence_transformers import SentenceTransformer

from core.services.llm_service import LLMService

from core.repositories.long_term_memory import LongTermMemoryRepo
from core.repositories.vector_memory import QdrantVectorRepo


class MemoryService:

    def __init__(self, *, model_name: str = "all-MiniLM-L6-v2", repo: Optional[LongTermMemoryRepo] = None, llm: Optional[LLMService] = None) -> None:
        self._embedder = SentenceTransformer(model_name)
        self._repo = repo or LongTermMemoryRepo()
        self._llm = llm or LLMService()
        self._vec: Optional[QdrantVectorRepo] = None
        try:
            # Optional vector repo
            self._vec = QdrantVectorRepo()
        except Exception:
            self._vec = None

    def embed_text(self, text: str) -> List[float]:
        vec = self._embedder.encode(text, normalize_embeddings=False)
        return [float(x) for x in vec.tolist()]

    def add_long_term_memory(self, *, user_id: Union[int, str], content: str, source: str = "extracted", embed: bool = True) -> str:
        try:
            embedding: List[float] = self.embed_text(content) if embed else []
        except Exception:
            # Fallback: persist without embedding to not lose the memory
            embedding = []
        if self._vec:
            try:
                self._vec.upsert_memory(user_id=user_id, text=content, embedding=embedding)
            except Exception:
                pass
        return self._repo.add_memory(user_id=user_id, content=content, embedding=embedding, source=source)

    def search_long_term_memory(self, *, user_id: Union[int, str], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        q_emb = self.embed_text(query)
        if self._vec:
            try:
                vec_hits = self._vec.search(user_id=user_id, query_embedding=q_emb, top_k=top_k)
                # Map to legacy doc format
                docs = [
                    {"user_id": user_id, "content": hit.get("text"), "score": hit.get("score")}
                    for hit in (vec_hits or [])
                    if (hit.get("text") or "").strip()
                ]
                if docs:
                    return docs
            except Exception:
                pass
        return self._repo.search_similar(user_id=user_id, query_embedding=q_emb, top_k=top_k)

    def list_long_term_memory(self, *, user_id: Union[int, str], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._repo.list_by_user(user_id=user_id, limit=limit)

    def extract_long_term_facts(self, *, message: str) -> List[str]:
        """
        Ask the LLM to extract atomic long-term facts from a free-form message.
        The LLM must return a strict JSON object:
          { "facts": [ { "text": str, "category": str, "confidence": float } ] }
        We accept any category, keep unique non-empty texts, and ignore parsing errors gracefully.
        """

        prompt = f"""
Bạn là bộ trích xuất trí nhớ dài hạn.
Nhiệm vụ: Từ nội dung sau, trích ra các sự thật hạt nhân (ngắn gọn, bền vững theo thời gian) về người dùng.
Yêu cầu:
- Không đưa lời chào/câu hỏi/filler.
- Mỗi fact 3–200 ký tự.
- Category là một nhãn ngắn (snake_case) bạn tự chọn phù hợp nội dung.
- Confidence là số thực 0..1.
- Trả về JSON duy nhất theo schema: {{"facts": [{{"text": str, "category": str, "confidence": float}}]}}

Nội dung:
{message}
"""

        facts: List[str] = []
        try:
            raw = self._llm.chat(system_prompt=None, user_prompt=prompt, response_format={"type": "json_object"})
            data = json.loads(raw)
            items = data.get("facts") or []
            seen = set()
            for it in items:
                text = str((it or {}).get("text", "")).strip()
                if 3 <= len(text) <= 200 and text not in seen:
                    seen.add(text)
                    facts.append(text)
        except Exception:
            # If the model didn't return valid JSON, do not guess; return empty for safety
            pass

        return facts

    def delete_long_term_memory(self, *, user_id: Union[int, str]) -> int:
        return self._repo.delete_by_user(user_id=user_id)


