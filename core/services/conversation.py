
from typing import Optional, Dict, Any, Literal, Union
from core.repositories.conversation import ConversationRepo

Role = Literal["user", "assistant", "system"]

class ConversationService:

    def __init__(self, repo: Optional[ConversationRepo] = None) -> None:
        self.repo = repo or ConversationRepo()


    def create_message(
        self,
        *,
        user_id: Union[int, str],
        role: Role,
        content: str,
    ) -> Dict[str, Any]:
        if role not in ("user", "assistant", "system"):
            raise ValueError("role must be one of: 'user', 'assistant', 'system'")
        if not isinstance(user_id, (int, str)):
            raise ValueError("user_id must be int or str")
        content = (content or "").strip()
        if not content:
            raise ValueError("content must not be empty")

        message_id = self.repo.store_new_message(
            user_id=user_id,
            role=role,
            content=content,
        )
        return {"message_id": message_id}


    def get_conversation(
        self,
        *,
        user_id: Union[int, str],
        page_size: int = 50,
        cursor: Optional[str] = None,
        newest_first: bool = True,
    ) -> Dict[str, Any]:
        if not (1 <= page_size <= 200):
            raise ValueError("page_size must be between 1 and 200")

        projection = {
            "_id": 1,
            "user_id": 1,
            "message_id": 1,
            "role": 1,
            "content": 1,
            "created_at": 1,
        }

        return self.repo.get_conversation(
            user_id=user_id,
            page_size=page_size,
            cursor=cursor,
            newest_first=newest_first,
            projection=projection,
        )

    def delete_conversation(self, *, user_id: Union[int, str]) -> Dict[str, Any]:
        deleted = self.repo.delete_by_user(user_id=user_id)
        return {"deleted": deleted}