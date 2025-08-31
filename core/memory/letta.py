# eq_chat_service/app/api/v1/letta.py
import os
import time
import re
import unicodedata
import requests
from threading import Lock
from fastapi import APIRouter, HTTPException
from letta_client import CreateBlock, Letta, MessageCreate
router = APIRouter(prefix="/letta", tags=["letta"])

class LettaService:
    _instance = None
    _lock: Lock = Lock()

    def __new__(cls, backend_url: str, letta_base_url: str):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, backend_url: str, letta_base_url: str):
        if getattr(self, "_initialized", False):
            return
        self.backend_url = backend_url
        self.letta_url = letta_base_url
        self.client = Letta(base_url=letta_base_url)
        self._initialized = True


    # ------------- Helpers (service layer) -------------
    def _backend_get_agent_id(self, user_id: int) -> str | None:
        try:
            url = f"{self.backend_url}/users/{user_id}/agent-id"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return (r.json().get("data") or {}).get("agent_id")
            # Any non-200: treat as missing to avoid breaking chat
            return None
        except Exception:
            return None

    def _backend_set_agent_id(self, user_id: int, agent_id: str) -> None:
        try:
            url = f"{self.backend_url}/users/{user_id}/agent-id"
            requests.put(url, json={"agent_id": agent_id}, timeout=5)
        except Exception:
            # Best-effort persistence only
            pass
    def _get_agent_details(self, agent_id: str):
        try:
            url = f"{self.letta_url}/v1/agents/{agent_id}"
            agent_details = requests.get(url, timeout=5).json()
            return agent_details
        except Exception:
            pass

    @staticmethod
    def _make_safe_agent_name(raw_name: str, uid: int | None) -> str:
        ascii_name = unicodedata.normalize("NFKD", raw_name).encode("ascii", "ignore").decode().lower()
        ascii_name = re.sub(r"[^a-z0-9]+", "-", ascii_name)
        ascii_name = re.sub(r"-+", "-", ascii_name).strip("-")
        if not ascii_name:
            ascii_name = f"user-{uid if uid is not None else 'guest'}"
        elif uid is not None:
            ascii_name = f"{ascii_name}-{uid}"
        return ascii_name[:64]

    def _ensure_agent_id(self, user_id: int | None, username: str) -> tuple[str, str | None]:
        if user_id is not None:
            agent_id = self._backend_get_agent_id(user_id)
            agent_details = self._get_agent_details(agent_id=agent_id)
            agent_detail_extracted = {
                "created_at": agent_details["created_at"],
                "updated_at": agent_details["updated_at"],
                "id": agent_details["id"],
                "name": agent_details["name"],
                "agent_type": agent_details["agent_type"],
                "llm_config": agent_details["llm_config"],
                "embedding_config": agent_details["embedding_config"]
            }
            if agent_id:
                return agent_id, agent_detail_extracted

        agent = self.client.agents.create(
            memory_blocks=[
                CreateBlock(
                    value=f"you are chatting with a person named {username}",
                    label="persona",
                ),
            ],
            model="google_ai/gemini-2.0-flash",
            embedding="google_ai/text-embedding-004",
            name=self._make_safe_agent_name(username, user_id),
        )

        if user_id is not None:
            self._backend_set_agent_id(user_id, agent.id)

        return agent.id, agent_details

    def send_message(self, user_id: int | None, username: str, message: str) -> tuple[str, float, str, str | None]:
        t0 = time.perf_counter()
        agent_id, agent_details = self._ensure_agent_id(user_id, username)
        response = self.client.agents.messages.create(
            agent_id=agent_id,
            messages=[MessageCreate(role="user", content=message)],
        )
        elapsed = time.perf_counter() - t0

        reply_text = ""
        for msg in response.messages:
            if getattr(msg, "message_type", None) == "assistant_message":
                reply_text = msg.content
                break
        if not reply_text and response.messages:
            reply_text = getattr(response.messages[-1], "content", "")
        if not reply_text:
            raise HTTPException(status_code=500, detail="No assistant message in response")
        return reply_text, elapsed, agent_id, agent_details

