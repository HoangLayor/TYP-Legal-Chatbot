"""
app/api/v1/history.py
----------------------
GET /api/v1/history/{session_id}    — lấy lịch sử hội thoại.
DELETE /api/v1/history/{session_id} — xoá toàn bộ history của session.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.security import limiter
from app.memory.history_manager import HistoryManager, get_history_manager
from app.models import DeleteHistoryResponse, HistoryResponse

router = APIRouter(prefix="/history", tags=["History"])


@router.get(
    "/{session_id}",
    response_model=HistoryResponse,
    summary="Lấy lịch sử hội thoại của session",
)
@limiter.limit("60/minute")
async def get_history(
    request: Request,
    session_id: str,
    limit: int = 50,
) -> HistoryResponse:
    """Trả về danh sách messages của session theo thứ tự chronological.

    Args:
        http_request: FastAPI Request (dùng cho rate limiter).
        session_id: UUID string của session.
        limit: Số messages tối đa trả về. Mặc định 50.

    Returns:
        HistoryResponse chứa session_id, messages và total count.

    Raises:
        HTTPException 404: Nếu session không tồn tại.
    """
    ...


@router.delete(
    "/{session_id}",
    response_model=DeleteHistoryResponse,
    summary="Xoá toàn bộ lịch sử của session",
)
@limiter.limit("20/minute")
async def delete_history(
    request: Request,
    session_id: str,
) -> DeleteHistoryResponse:
    """Xoá toàn bộ messages của session từ MongoDB.

    Args:
        http_request: FastAPI Request.
        session_id: UUID string của session cần xoá.

    Returns:
        DeleteHistoryResponse với trạng thái xoá.

    Raises:
        HTTPException 404: Nếu session không tồn tại.
    """
    ...
