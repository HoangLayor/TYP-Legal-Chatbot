"""
app/api/v1/chat.py
-------------------
POST /api/v1/chat/stream — nhận query và stream response về client qua SSE.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.security import limiter
from app.models import ChatRequest
from app.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/chat", tags=["Chat"])

# Dependency: inject pipeline
# Trong production nên dùng FastAPI dependency injection đầy đủ
def get_pipeline() -> RAGPipeline:
    """Dependency để inject RAGPipeline vào route handler.

    Returns:
        RAGPipeline: Singleton pipeline instance.
    """
    return RAGPipeline()


async def _event_stream(
    pipeline: RAGPipeline, request: ChatRequest
) -> AsyncIterator[str]:
    """Generator cho SSE response stream.

    Yield từng event dưới dạng ``data: <json>\\n\\n`` (SSE format).

    Args:
        pipeline: RAGPipeline instance.
        request: ChatRequest từ client.

    Yields:
        SSE-formatted string cho mỗi event từ pipeline.
    """
    ...


@router.post(
    "/stream",
    summary="Chat với RAG pipeline (SSE streaming)",
    response_description="Server-Sent Events stream với chunks, sources và done signal",
)
@limiter.limit("30/minute")
async def chat_stream(
    http_request: Request,
    body: ChatRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
) -> StreamingResponse:
    """Gửi query và nhận response dạng SSE stream.

    **Flow:**
    1. Validate request body.
    2. Tạo SSE stream từ RAGPipeline.
    3. Stream về client real-time.

    **SSE Event types:**
    - ``chunk`` — text từ LLM
    - ``sources`` — danh sách nguồn tham khảo
    - ``done`` — kết thúc stream
    - ``error`` — lỗi (nếu có)

    Args:
        http_request: FastAPI Request (dùng cho rate limiter).
        body: ChatRequest với session_id, query, use_web_search.
        pipeline: Injected RAGPipeline.

    Returns:
        StreamingResponse với content-type ``text/event-stream``.
    """
    ...
