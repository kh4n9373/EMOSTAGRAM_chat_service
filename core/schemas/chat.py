from pydantic import BaseModel

class ChatRequest(BaseModel):
    user_id: int | None = None
    username: str
    message: str
    include_agent_detail: bool = False

class ChatResponse(BaseModel):
    message: str
    gen_time_sec: float
    agent_id: str
    agent_detail: dict = {}