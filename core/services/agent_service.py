from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union, TypedDict
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.services.memory_service import MemoryService
from core.services.tavily_service import TavilyService
from core.services.llm_service import LLMService
from core.services.conversation import ConversationService
from core.tools.extract import extract_long_term_facts_tool
from core.tools.search import tavily_search_tool
from infra.kafka.producer import KafkaProducerClient
from config import settings
from langsmith import traceable


try:
    _KAFKA_PRODUCER = KafkaProducerClient(bootstrap_servers=settings.kafka_bootstrap)
except Exception:
    _KAFKA_PRODUCER = None

class AgentState(TypedDict, total=False):
    user_id: Union[int, str]
    username: str
    user_message: str
    short_term_context: List[Dict[str, Any]]
    long_term_context: List[str]
    search_results: List[Dict[str, Any]]
    extracted_facts: List[str]
    assistant_reply: str


def _should_search(state: AgentState) -> bool:
    user_msg = state.get("user_message", "").lower()
    return any(kw in user_msg for kw in ["search", "tìm", "google", "web"])


class AgentService:
    def __init__(
        self,
        *,
        memory: Optional[MemoryService] = None,
        tavily: Optional[TavilyService] = None,
        llm: Optional[LLMService] = None,
        conversation: Optional[ConversationService] = None,
    ) -> None:
        self.memory = memory or MemoryService()
        self.tavily = tavily
        self.llm = llm or LLMService()
        self.conv = conversation or ConversationService()

        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        @traceable(name="agent.load_context")
        def load_context(state: AgentState) -> AgentState:
            user_id = state["user_id"]
            # Short-term: last 10 messages
            convo = self.conv.get_conversation(user_id=user_id, page_size=10, newest_first=True)
            history = list(reversed([{k: d[k] for k in ("role", "content")} for d in convo["items"]]))
            state["short_term_context"] = history
            # Long-term: retrieve similar memory to current message
            user_msg = state.get("user_message", "")
            ltm_docs = self.memory.search_long_term_memory(user_id=user_id, query=user_msg, top_k=5)
            state["long_term_context"] = [d.get("content", "") for d in ltm_docs]
            return state

        @traceable(name="agent.maybe_search")
        def maybe_search(state: AgentState) -> AgentState:
            if self.tavily and _should_search(state):
                q = state.get("user_message", "")
                results = tavily_search_tool.invoke({
                    "user_id": state["user_id"],
                    "query": q,
                    "max_results": 5,
                })
                state["search_results"] = results
            else:
                state["search_results"] = []
            return state

        @traceable(name="agent.extract_facts")
        def extract_facts(state: AgentState) -> AgentState:
            state["extracted_facts"] = []
            try:
                if _KAFKA_PRODUCER is not None:
                    _KAFKA_PRODUCER.send(
                        topic="ltm-extract",
                        key=str(state["user_id"]),
                        value={"user_id": state["user_id"], "message": state.get("user_message", "")},
                    )
                else:
                    raise RuntimeError("kafka not available")
            except Exception:
                try:
                    extract_long_term_facts_tool.invoke({
                        "user_id": state["user_id"],
                        "message": state.get("user_message", ""),
                    })
                except Exception:
                    pass
            return state

        @traceable(name="agent.respond")
        def respond(state: AgentState) -> AgentState:
            sys = "You are a helpful Vietnamese assistant. Use context when answering."
            parts: List[str] = []
            if state.get("long_term_context"):
                parts.append("Long-term memory:\n" + "\n".join(state["long_term_context"]))
            if state.get("short_term_context"):
                turns = [f"{m['role']}: {m['content']}" for m in state["short_term_context"]]
                parts.append("Recent conversation (last 10):\n" + "\n".join(turns))
            if state.get("search_results"):
                lines = [f"- {r.get('title','')} {r.get('url','')}" for r in state["search_results"]]
                parts.append("Web search results:\n" + "\n".join(lines))
            context = "\n\n".join(parts)

            user_prompt = f"Context (may be partial):\n{context}\n\nUser: {state.get('user_message','')}\nAssistant:"
            answer = self.llm.chat(system_prompt=sys, user_prompt=user_prompt)
            state["assistant_reply"] = answer
            return state

        builder.add_node("load_context", load_context)
        builder.add_node("maybe_search", maybe_search)
        builder.add_node("extract_facts", extract_facts)
        builder.add_node("respond", respond)

        builder.set_entry_point("load_context")
        builder.add_edge("load_context", "maybe_search")
        builder.add_edge("maybe_search", "extract_facts")
        builder.add_edge("extract_facts", "respond")
        builder.add_edge("respond", END)
        # Enable checkpointing (in-memory to avoid optional sqlite dependency issues)
        return builder.compile(checkpointer=MemorySaver())

    @traceable(name="AgentService.chat", tags=["agent","chat"])
    def chat(
        self,
        *,
        user_id: Union[int, str],
        username: str,
        message: str,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Persist user message
        self.conv.create_message(user_id=user_id, role="user", content=message)

        state: AgentState = {
            "user_id": user_id,
            "username": username,
            "user_message": message,
        }
        thread = thread_id or str(user_id)
        final_state = self.graph.invoke(state, config={"configurable": {"thread_id": thread}})

        answer = final_state.get("assistant_reply", "")
        # Persist assistant message
        if answer:
            self.conv.create_message(user_id=user_id, role="assistant", content=answer)

        return {
            "message": answer,
            "long_term": final_state.get("long_term_context", []),
            "search_results": final_state.get("search_results", []),
            "extracted_facts": final_state.get("extracted_facts", []),
        }


