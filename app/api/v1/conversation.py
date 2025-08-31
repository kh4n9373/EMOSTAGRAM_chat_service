
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Union
from core.services.conversation import ConversationService
from core.schemas.conversation import MessageCreate, MessageDoc, ConversationPage

router = APIRouter(prefix="/conversation")
svc = ConversationService()

def _to_msgdoc(doc: dict) -> MessageDoc:
    d = dict(doc)
    if "_id" in d:
        d["_id"] = str(d["_id"])
    return MessageDoc.model_validate(d)

@router.post("/messages")
def create_message(payload: MessageCreate):
    try:
        return svc.create_message(
            user_id=payload.user_id,
            role=payload.role,
            content=payload.content,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}")
def get_conversation(
    user_id: Union[int, str],
    page_size: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
    newest_first: bool = Query(True),
):
    try:
        data = svc.get_conversation(
            user_id=user_id,
            page_size=page_size,
            cursor=cursor,
            newest_first=newest_first,
        )
        items = [_to_msgdoc(d) for d in data["items"]]
        return ConversationPage(items=items, next_cursor=data["next_cursor"], page_size=data["page_size"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
