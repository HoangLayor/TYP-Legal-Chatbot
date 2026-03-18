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
        ...

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
        ...

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Lấy toàn bộ session document theo ID.

        Args:
            session_id: UUID string của session.

        Returns:
            Session document dict nếu tồn tại, None nếu không.
        """
        ...

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
        ...

    async def delete_session(self, session_id: str) -> bool:
        """Xoá toàn bộ session document.

        Args:
            session_id: UUID string của session.

        Returns:
            True nếu xoá thành công (document tồn tại), False nếu không tìm thấy.
        """
        ...

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
        ...
