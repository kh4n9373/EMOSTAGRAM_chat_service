from typing import List, Optional, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

Role = Literal["user", "assistant", "system"]

class MessageCreate(BaseModel):
    user_id: Union[str,int]
    role: Role = "user"
    content: str = Field(min_length=1, max_length=4000)

class MessageDoc(BaseModel):
    id: str = Field(alias="_id")
    user_id: Union[str,int]
    message_id: str
    role: Role
    content: str
    created_at: datetime
    model_config = ConfigDict(populate_by_name=True)

class ConversationPage(BaseModel):
    items: List[MessageDoc]
    next_cursor: Optional[str] = None
    page_size: int