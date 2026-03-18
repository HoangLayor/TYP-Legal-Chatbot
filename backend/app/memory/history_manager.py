"""
app/memory/history_manager.py
------------------------------
Quản lý lịch sử hội thoại theo session.
Load N messages gần nhất và tự động trim khi vượt token limit.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.memory.mongo_store import MongoStore

logger = get_logger(__name__)
settings = get_settings()


class HistoryManager:
    """Quản lý chat history: load, trim và lưu messages.

    Attributes:
        store (MongoStore): Underlying MongoDB store.
        max_messages (int): Số messages giữ lại trong context.
        max_tokens (int): Giới hạn tổng token của history.
    """

    def __init__(
        self,
        store: MongoStore | None = None,
        max_messages: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Khởi tạo HistoryManager.

        Args:
            store: MongoStore instance. Mặc định tạo mới.
            max_messages: Số messages tối đa. Mặc định từ config.
            max_tokens: Token limit tổng history. Mặc định từ config.
        """
        self.store = store or MongoStore(settings.sessions_collection)
        self.max_messages = max_messages or settings.history_max_messages
        self.max_tokens = max_tokens or settings.history_max_tokens

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Ước tính tổng số token của danh sách messages.

        Dùng quy tắc thô: 1 token ≈ 4 ký tự.

        Args:
            messages: List message dict.

        Returns:
            Tổng token ước tính.
        """
        ...

    def _trim_to_fit(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cắt bớt messages cũ để total token vừa trong ``max_tokens``.

        Luôn giữ message đầu tiên (nếu là system) và các messages gần nhất.
        Không bao giờ cắt message user/assistant của lượt hiện tại.

        Args:
            messages: Danh sách messages theo thứ tự chronological.

        Returns:
            Danh sách messages đã trim.
        """
        ...

    async def load_history(self, session_id: str) -> list[dict[str, Any]]:
        """Load N messages gần nhất của session từ MongoDB.

        Tự động trim nếu tổng token vượt ngưỡng.

        Args:
            session_id: UUID session.

        Returns:
            List message dict ``{"role": str, "content": str, ...}``
            theo thứ tự chronological, đã trim nếu cần.
        """
        ...

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Lưu một message mới vào MongoDB.

        Args:
            session_id: UUID session.
            role: ``"user"`` hoặc ``"assistant"``.
            content: Nội dung message.
            extra: Thông tin bổ sung (ví dụ: ``{"sources": [...]}``) chỉ cho assistant messages.
        """
        ...

    async def save_exchange(
        self,
        session_id: str,
        user_query: str,
        assistant_answer: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> None:
        """Lưu cả user message và assistant response trong một lượt.

        Args:
            session_id: UUID session.
            user_query: Query của user.
            assistant_answer: Câu trả lời đầy đủ của assistant.
            sources: Sources đính kèm response.
        """
        ...

    async def clear_history(self, session_id: str) -> bool:
        """Xoá toàn bộ history của session.

        Args:
            session_id: UUID session cần xoá.

        Returns:
            True nếu session tồn tại và đã xoá, False nếu không tìm thấy.
        """
        ...


# ── Singleton ─────────────────────────────────────────────────────────────────

_history_manager: HistoryManager | None = None


def get_history_manager() -> HistoryManager:
    """Trả về singleton HistoryManager.

    Returns:
        HistoryManager: Instance được tái sử dụng.
    """
    global _history_manager
    if _history_manager is None:
        _history_manager = HistoryManager()
    return _history_manager
