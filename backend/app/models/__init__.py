"""
app/models/__init__.py
-----------------------
Pydantic request/response models cho tất cả API endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body cho POST /api/v1/chat/stream."""

    session_id: str = Field(..., description="UUID v4 của session hội thoại")
    query: str = Field(..., min_length=1, max_length=2000, description="Câu hỏi của user")
    use_web_search: bool = Field(True, description="Cho phép fallback sang Tavily web search")

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        """Trim whitespace đầu/cuối khỏi query."""
        return v.strip()


class SourceItem(BaseModel):
    """Một source reference trong response."""

    type: Literal["document", "web"] = "document"
    title: str = ""
    url: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


# SSE event schemas (không dùng Pydantic trực tiếp nhưng documented ở đây)
# {"type": "chunk", "content": str}
# {"type": "sources", "items": list[SourceItem]}
# {"type": "done"}
# {"type": "error", "message": str}


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    """Response body cho POST /api/v1/ingest."""

    status: Literal["success", "error"] = "success"
    document_id: str
    chunks_indexed: int
    filename: str
    message: str = ""


# ── History ───────────────────────────────────────────────────────────────────

class MessageSchema(BaseModel):
    """Schema một message trong history."""

    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    sources: list[SourceItem] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    """Response cho GET /api/v1/history/{session_id}."""

    session_id: str
    messages: list[MessageSchema] = Field(default_factory=list)
    total: int = 0


class DeleteHistoryResponse(BaseModel):
    """Response cho DELETE /api/v1/history/{session_id}."""

    session_id: str
    deleted: bool
    message: str = ""


# ── Search (debug) ────────────────────────────────────────────────────────────

class SearchHit(BaseModel):
    """Một kết quả từ search endpoint."""

    id: str
    score: float
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    """Response cho GET /api/v1/search."""

    query: str
    hits: list[SearchHit]
    total: int
    used_reranker: bool = False
