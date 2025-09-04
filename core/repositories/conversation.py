# core/repositories/conversation_repo.py
from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from bson import ObjectId
import base64, json

from core.database.mongodb_client import MongoManager 


class ConversationRepo:
    def __init__(self, *, db_name: str = "EMOSTAGRAM", collection: str = "messages"):
        self.client = MongoManager(db=db_name)
        self.collection = collection

    def store_new_message(
        self,
        *,
        user_id: int | str,
        role: str,
        content: str
    ) -> str:
        """
        Lưu message mới. Trả về message_id (string).
        """
        user_id_norm = self._normalize_user_id(user_id)  
        message_id = f"{user_id}_{uuid4()}"
        doc = {
            "user_id": user_id_norm, 
            "message_id": message_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
        }
        self.client.insert_one(self.collection, doc)
        return message_id

    def get_conversation(
        self,
        *,
        user_id: int | str,
        page_size: int = 50,
        cursor: Optional[str] = None,     
        newest_first: bool = True,
        projection: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Cursor/Keyset pagination (infinite scroll mượt):
        - newest_first=True: sort (created_at DESC, _id DESC)
        - next_cursor: base64 chứa (last_created_at, last_id)
        """
        page_size = max(1, min(page_size, 200))

        sort = [("created_at", -1), ("_id", -1)] if newest_first else [("created_at", 1), ("_id", 1)]
        uid = self._normalize_user_id(user_id)
        cand = {uid, str(uid)}
        flt: Dict[str, Any] ={"user_id": {"$in": list(cand)}}

        if cursor:
            c = self._decode_cursor(cursor)
            last_created_at = datetime.fromisoformat(c["last_created_at"])
            last_id = ObjectId(c["last_id"])
            if newest_first:
                flt["$or"] = [
                    {"created_at": {"$lt": last_created_at}},
                    {"created_at": last_created_at, "_id": {"$lt": last_id}},
                ]
            else:
                flt["$or"] = [
                    {"created_at": {"$gt": last_created_at}},
                    {"created_at": last_created_at, "_id": {"$gt": last_id}},
                ]

        docs: List[Dict[str, Any]] = self.client.find(
            collection_name=self.collection,
            filter=flt,
            projection=projection or {"_id": 1, "created_at": 1, "role": 1, "content": 1, "message_id": 1},
            sort=sort,
            limit=page_size,
        )

        next_cursor = None
        if docs:
            last = docs[-1]
            next_cursor = self._encode_cursor({
                "last_created_at": last["created_at"].isoformat() if isinstance(last.get("created_at"), datetime) else last.get("created_at"),
                "last_id": str(last["_id"]),
            })

        return {
            "items": docs,
            "next_cursor": next_cursor,
            "page_size": page_size,
        }

    def delete_by_user(self, *, user_id: int | str) -> int:
        uid = self._normalize_user_id(user_id)
        cand = {uid, str(uid)}
        coll = self.client._MongoManager__database[self.collection]
        res = coll.delete_many({"user_id": {"$in": list(cand)}})
        return int(getattr(res, "deleted_count", 0))
    @staticmethod
    def _normalize_user_id(user_id: int | str) -> int | str:
        if isinstance(user_id, str) and user_id.isdigit():
            return int(user_id)
        return user_id
    
    @staticmethod
    def _encode_cursor(cur: dict) -> str:
        payload = json.dumps(cur, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("utf-8")

    @staticmethod
    def _decode_cursor(token: str) -> dict:
        token_padded = token + "=" * (-len(token) % 4)  
        raw = base64.urlsafe_b64decode(token_padded.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
