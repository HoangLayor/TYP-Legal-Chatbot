"""
app/memory/session.py
----------------------
Session lifecycle management: tạo, truy vấn và đóng session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.memory.mongo_store import MongoStore

logger = get_logger(__name__)


class SessionManager:
    """Quản lý vòng đời session.

    Session đại diện cho một cuộc hội thoại của user.
    Mỗi session có UUID độc lập và được lưu trong MongoDB.

    Attributes:
        store (MongoStore): Underlying MongoDB store.
    """

    def __init__(self, store: MongoStore | None = None) -> None:
        """Khởi tạo SessionManager.

        Args:
            store: MongoStore instance. Mặc định tạo mới.
        """
        self.store = store or MongoStore()

    def generate_session_id(self) -> str:
        """Tạo session ID mới dạng UUID v4.

        Returns:
            UUID string mới, ví dụ: ``"550e8400-e29b-41d4-a716-446655440000"``.
        """
        return str(uuid.uuid4())

    async def create_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Tạo session mới trong MongoDB.

        Args:
            session_id: Custom session ID. Nếu None, tự generate UUID.
            metadata: Metadata tuỳ chọn (user_id, IP, model, ...).

        Returns:
            session_id đã được tạo.
        """
        sid = session_id or self.generate_session_id()
        now = datetime.now(timezone.utc)

        data: dict[str, Any] = {
            "created_at": now,
            "updated_at": now,
            "last_active": now,
            "messages": [],
        }

        if metadata:
            data["metadata"] = metadata

        await self.store.upsert_session(sid, data)

        logger.info("Created session_id=%s", sid)
        return sid

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Lấy thông tin session theo ID.

        Args:
            session_id: UUID string của session.

        Returns:
            Session document dict nếu tồn tại, None nếu không.
        """
        session = await self.store.get_session(session_id)

        if session is None:
            logger.debug("Session not found: session_id=%s", session_id)
            return None

        messages = session.get("messages", [])
        if not isinstance(messages, list):
            messages = []

        session_summary = {
            "id": session.get("_id"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "last_active": session.get("last_active"),
            "metadata": session.get("metadata", {}),
            "message_count": len(messages),
            "messages": messages,
        }

        logger.debug("Fetched session_id=%s", session_id)
        return session_summary

    async def session_exists(self, session_id: str) -> bool:
        """Kiểm tra session có tồn tại không.

        Args:
            session_id: UUID string.

        Returns:
            True nếu session tồn tại.
        """
        exists = await self.store.get_session(session_id) is not None
        logger.debug("Session exists session_id=%s: %s", session_id, exists)
        return exists

    async def update_last_active(self, session_id: str) -> None:
        """Cập nhật timestamp cuối cùng hoạt động của session.

        Gọi sau mỗi chat exchange để tracking.

        Args:
            session_id: UUID session.
        """
        now = datetime.now(timezone.utc)

        await self.store.upsert_session(
            session_id,
            {
                "last_active": now,
            },
        )

        logger.debug("Updated last_active for session_id=%s", session_id)

    async def delete_session(self, session_id: str) -> bool:
        """Xoá session và toàn bộ messages.

        Args:
            session_id: UUID session.

        Returns:
            True nếu xoá thành công.
        """
        deleted = await self.store.delete_session(session_id)
        logger.info("Deleted session_id=%s: %s", session_id, deleted)
        return deleted

    async def list_sessions(
        self,
        page: int = 0,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Liệt kê sessions với phân trang.

        Args:
            page: Trang (0-indexed).
            page_size: Số sessions mỗi trang.

        Returns:
            List session summary (id, created_at, last_active, message_count).
        """
        sessions = await self.store.list_sessions(page=page, page_size=page_size)

        result: list[dict[str, Any]] = []

        for session in sessions:
            result.append(
                {
                    "id": session.get("_id"),
                    "created_at": session.get("created_at"),
                    "updated_at": session.get("updated_at"),
                    "last_active": session.get("last_active"),
                    "metadata": session.get("metadata", {}),
                    "message_count": session.get("message_count", 0),
                }
            )

        logger.debug(
            "Listed %d sessions (page=%d, page_size=%d)",
            len(result),
            page,
            page_size,
        )
        return result