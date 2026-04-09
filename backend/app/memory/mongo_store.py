"""
app/memory/mongo_store.py
--------------------------
Motor async CRUD operations cho MongoDB.
Xử lý lưu trữ và truy vấn sessions/messages ở tầng thấp nhất.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.db.mongo import get_collection

logger = get_logger(__name__)


class MongoStore:
    """Async CRUD wrapper cho MongoDB collection.

    Cung cấp các thao tác tầng thấp: upsert, find, delete.
    Không chứa business logic — dùng HistoryManager cho phần đó.

    Attributes:
        collection_name (str): Tên MongoDB collection.
    """

    def __init__(self, collection_name: str = "sessions") -> None:
        """Khởi tạo MongoStore với tên collection.

        Args:
            collection_name: Tên collection MongoDB. Mặc định ``"sessions"``.
        """
        self.collection_name = collection_name

    @property
    def collection(self):
        """Lazy accessor tới Motor collection.

        Trả về collection mới mỗi lần để tránh giữ reference cũ.
        """
        return get_collection(self.collection_name)

    async def upsert_session(self, session_id: str, data: dict[str, Any]) -> None:
        """Tạo hoặc cập nhật session document.

        Sử dụng ``$set`` để merge thay vì replace toàn bộ document.

        Args:
            session_id: UUID string của session.
            data: Các field cần set/update (không bao gồm ``_id``).
        """
        now = datetime.now(timezone.utc)

        update_data = dict(data)
        created_at = update_data.pop("created_at", now)
        messages = update_data.pop("messages", [])
        update_data["updated_at"] = now

        await self.collection.update_one(
            {"_id": session_id},
            {
                "$set": update_data,
                "$setOnInsert": {
                    "_id": session_id,
                    "created_at": created_at,
                    "messages": messages,
                },
            },
            upsert=True,
        )

        logger.debug("Upserted session_id=%s", session_id)

    async def append_message(
        self,
        session_id: str,
        message: dict[str, Any],
    ) -> None:
        """Thêm một message vào mảng ``messages`` của session.

        Sử dụng ``$push`` để append atomic.

        Args:
            session_id: UUID string của session.
            message: Dict message có dạng:
                     ``{"role": str, "content": str, "created_at": datetime, ...}``.
        """
        now = datetime.now(timezone.utc)

        message_to_save = dict(message)
        message_to_save.setdefault("created_at", now)

        await self.collection.update_one(
            {"_id": session_id},
            {
                "$push": {"messages": message_to_save},
                "$set": {
                    "updated_at": now,
                    "last_active": now,
                },
                "$setOnInsert": {
                    "_id": session_id,
                    "created_at": now,
                },
            },
            upsert=True,
        )

        logger.debug("Appended message to session_id=%s", session_id)

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Lấy toàn bộ session document theo ID.

        Args:
            session_id: UUID string của session.

        Returns:
            Session document dict nếu tồn tại, None nếu không.
        """
        doc = await self.collection.find_one({"_id": session_id})

        if doc is None:
            logger.debug("Session not found: session_id=%s", session_id)
            return None

        logger.debug("Fetched session_id=%s", session_id)
        return doc

    async def get_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Lấy danh sách messages của session.

        Args:
            session_id: UUID string của session.
            limit: Số messages lấy từ cuối (newest). None = lấy tất cả.

        Returns:
            List message dict sorted theo ``created_at`` tăng dần.
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        messages = session.get("messages", [])
        if not isinstance(messages, list):
            logger.warning("Invalid messages format for session_id=%s", session_id)
            return []

        def _sort_key(msg: dict[str, Any]) -> str:
            created_at = msg.get("created_at")
            if isinstance(created_at, datetime):
                return created_at.isoformat()
            return str(created_at or "")

        messages = sorted(messages, key=_sort_key)

        if limit is not None and limit > 0:
            messages = messages[-limit:]

        logger.debug(
            "Fetched %d messages for session_id=%s",
            len(messages),
            session_id,
        )
        return messages

    async def delete_session(self, session_id: str) -> bool:
        """Xoá toàn bộ session document.

        Args:
            session_id: UUID string của session.

        Returns:
            True nếu xoá thành công (document tồn tại), False nếu không tìm thấy.
        """
        result = await self.collection.delete_one({"_id": session_id})
        deleted = result.deleted_count > 0

        logger.debug("Deleted session_id=%s: %s", session_id, deleted)
        return deleted

    async def clear_session(self, session_id: str) -> bool:
        """Alias cho delete_session để tương thích với HistoryManager."""
        return await self.delete_session(session_id)

    async def list_sessions(
        self,
        page: int = 0,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Liệt kê tất cả sessions với phân trang.

        Args:
            page: Trang hiện tại (0-indexed).
            page_size: Số sessions mỗi trang.

        Returns:
            List session summary dict (không bao gồm messages).
        """
        if page < 0:
            page = 0

        if page_size <= 0:
            page_size = 20

        skip = page * page_size

        pipeline = [
            {
                "$project": {
                    "_id": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "last_active": 1,
                    "metadata": 1,
                    "message_count": {
                        "$size": {
                            "$ifNull": ["$messages", []]
                        }
                    },
                }
            },
            {"$sort": {"updated_at": -1}},
            {"$skip": skip},
            {"$limit": page_size},
        ]

        cursor = self.collection.aggregate(pipeline)
        sessions = await cursor.to_list(length=page_size)

        logger.debug(
            "Listed %d sessions (page=%d, page_size=%d)",
            len(sessions),
            page,
            page_size,
        )
        return sessions