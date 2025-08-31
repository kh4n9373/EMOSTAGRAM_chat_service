# app/api/v1/letta.py
from fastapi import APIRouter, HTTPException
from config import settings
from core.schemas.chat import ChatRequest, ChatResponse
from core.memory.letta import LettaService
from infra.kafka.producer import KafkaProducerClient
from datetime import datetime, timezone
from uuid import uuid4

router = APIRouter(prefix="/letta", tags=["letta"])

llm = LettaService(backend_url=settings.backend_url, letta_base_url=settings.letta_base_url)
kafka = KafkaProducerClient(bootstrap_servers=settings.kafka_bootstrap)

TOPIC = "chat-messages"

def _event(message_id, user_id, role, content, correlation_id):
    return {
        "event_type": "message.created",
        "version": 1,
        "message_id": message_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
    }

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        corr = f"req-{uuid4()}"
        # 1) publish user message (nhanh, không chặn lâu)
        print('1')
        user_msg_id = f"{req.user_id}_{uuid4()}"
        kafka.send(TOPIC, key=str(req.user_id),
                   value=_event(user_msg_id, req.user_id, "user", req.message, corr))

        # 2) gọi LLM
        print('2')
        reply, elapsed, agent_id, agent_details = llm.send_message(req.user_id, req.username, req.message)

        # 3) publish assistant message
        print(agent_details)
        print('3')
        asst_msg_id = f"{req.user_id}_{uuid4()}"
        kafka.send(TOPIC, key=str(req.user_id),
                   value=_event(asst_msg_id, req.user_id, "assistant", reply, corr))

        # 4) trả về cho UI
        print('4')
        return ChatResponse(message=reply, gen_time_sec=round(elapsed, 4),
                            agent_id=agent_id, agent_detail=agent_details)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
