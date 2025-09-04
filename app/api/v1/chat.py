from fastapi import FastRouter
from core.schemas.chat import ChatRequest, ChatResponse

router = FastRouter()
@router.post("/chat")
def send_message(payload: ChatRequest) -> ChatResponse:

    # store user message

    # get history


    # get memory


    # infer


    # stpre assistant message


    pass





