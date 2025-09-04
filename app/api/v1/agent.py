from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
import time
from typing import Optional, Union

from core.schemas.chat import ChatRequest, ChatResponse
from core.services.agent_service import AgentService
from core.services.memory_service import MemoryService
from core.services.tavily_service import TavilyService
from core.services.conversation import ConversationService
from config import settings


router = APIRouter(prefix="/agent", tags=["agent"])


def _build_agent() -> AgentService:
    conversation = ConversationService()
    memory = MemoryService()
    tavily = None
    try:
        if settings.tavily_api_key:
            tavily = TavilyService()
    except Exception:
        tavily = None
    return AgentService(memory=memory, tavily=tavily, conversation=conversation)

# Reuse a singleton agent to avoid reloading models per request
AGENT = _build_agent()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        t0 = time.perf_counter()
        out = AGENT.chat(user_id=req.user_id or req.username, username=req.username, message=req.message)
        elapsed = time.perf_counter() - t0
        return ChatResponse(message=out.get("message", ""), gen_time_sec=round(elapsed, 4), agent_id="langgraph-agent", agent_detail={
            "long_term": out.get("long_term", []),
            "search_results": out.get("search_results", []),
            "extracted_facts": out.get("extracted_facts", []),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/conversation/{user_id}/recent")
def recent_conversation(user_id: Union[int, str], k: int = Query(10, ge=1, le=50)):
    try:
        conv = ConversationService().get_conversation(user_id=user_id, page_size=k, newest_first=True)
        return list(reversed([{k: d[k] for k in ("role", "content", "created_at", "message_id")} for d in conv["items"]]))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/memory/long-term/{user_id}")
def list_long_term_memory(user_id: Union[int, str], limit: Optional[int] = Query(None, ge=1, le=200)):
    try:
        docs = MemoryService().list_long_term_memory(user_id=user_id, limit=limit)
        out = []
        for d in docs:
            dd = dict(d)
            if "_id" in dd:
                dd["_id"] = str(dd["_id"])
            ca = dd.get("created_at")
            if hasattr(ca, "isoformat"):
                dd["created_at"] = ca.isoformat()
            out.append(dd)
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tools/search-results/{user_id}")
def recent_search_results(user_id: Union[int, str], limit: int = Query(20, ge=1, le=100)):
    try:
        tav = TavilyService()
        return tav.recent_results(user_id=user_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/reset/{user_id}")
def reset_user_state(user_id: Union[int, str]):
    """
    Xoá toàn bộ long-term memory và conversation history cho user_id.
    """
    try:
        mem_deleted = MemoryService().delete_long_term_memory(user_id=user_id)
        conv_deleted = ConversationService().delete_conversation(user_id=user_id)["deleted"]
        return {"user_id": user_id, "deleted_long_term": mem_deleted, "deleted_messages": conv_deleted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


