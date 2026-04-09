"""
app/memory/history_manager.py
------------------------------
Quản lý lịch sử hội thoại theo session.
Load N messages gần nhất và tự động trim khi vượt token limit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
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
        total_chars = 0

        for msg in messages:
            content = str(msg.get("content", ""))
            role = str(msg.get("role", ""))
            total_chars += len(content) + len(role)

            extra = msg.get("extra")
            if extra is not None:
                total_chars += len(str(extra))

        return ceil(total_chars / 4)

    def _trim_to_fit(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Cắt bớt messages cũ để total token vừa trong ``max_tokens``.

        Luôn giữ message đầu tiên (nếu là system) và các messages gần nhất.
        Không bao giờ cắt message user/assistant của lượt hiện tại.

        Args:
            messages: Danh sách messages theo thứ tự chronological.

        Returns:
            Danh sách messages đã trim.
        """
        if not messages:
            return []

        trimmed = messages[:]

        has_system = trimmed[0].get("role") == "system"
        system_msg = trimmed[0] if has_system else None
        body = trimmed[1:] if has_system else trimmed[:]

        if len(body) > self.max_messages:
            body = body[-self.max_messages :]

        trimmed = ([system_msg] if system_msg else []) + body

        while len(trimmed) > 2 and self._estimate_tokens(trimmed) > self.max_tokens:
            if has_system and len(trimmed) > 3:
                del trimmed[1]
            elif not has_system and len(trimmed) > 2:
                del trimmed[0]
            else:
                break

        return trimmed

    async def load_history(self, session_id: str) -> list[dict[str, Any]]:
        """Load N messages gần nhất của session từ MongoDB.

        Tự động trim nếu tổng token vượt ngưỡng.

        Args:
            session_id: UUID session.

        Returns:
            List message dict ``{"role": str, "content": str, ...}``
            theo thứ tự chronological, đã trim nếu cần.
        """
        try:
            session = await self.store.get_session(session_id)
            if not session:
                logger.info("No history found for session_id=%s", session_id)
                return []

            messages = session.get("messages", [])
            if not isinstance(messages, list):
                logger.warning("Invalid messages format for session_id=%s", session_id)
                return []

            trimmed = self._trim_to_fit(messages)

            if len(trimmed) != len(messages):
                logger.info(
                    "History trimmed for session_id=%s (%d -> %d messages)",
                    session_id,
                    len(messages),
                    len(trimmed),
                )

            return trimmed

        except Exception as exc:
            logger.exception(
                "Failed to load history for session_id=%s: %s",
                session_id,
                exc,
            )
            return []

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
        message: dict[str, Any] = {
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
        }

        if extra:
            message["extra"] = extra

        try:
            await self.store.append_message(session_id, message)
            logger.debug("Saved %s message for session_id=%s", role, session_id)
        except Exception as exc:
            logger.exception(
                "Failed to save %s message for session_id=%s: %s",
                role,
                session_id,
                exc,
            )
            raise

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
        await self.save_message(session_id=session_id, role="user", content=user_query)

        assistant_extra: dict[str, Any] | None = None
        if sources:
            assistant_extra = {"sources": sources}

        await self.save_message(
            session_id=session_id,
            role="assistant",
            content=assistant_answer,
            extra=assistant_extra,
        )

    async def clear_history(self, session_id: str) -> bool:
        """Xoá toàn bộ history của session.

        Args:
            session_id: UUID session cần xoá.

        Returns:
            True nếu session tồn tại và đã xoá, False nếu không tìm thấy.
        """
        try:
            deleted = await self.store.clear_session(session_id)
            logger.info("Cleared history for session_id=%s: %s", session_id, deleted)
            return bool(deleted)
        except Exception as exc:
            logger.exception(
                "Failed to clear history for session_id=%s: %s",
                session_id,
                exc,
            )
            return False


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