"""
app/api/v1/search.py
---------------------
GET /api/v1/search — debug endpoint: chạy hybrid search + rerank, trả kết quả raw.
Không qua LLM, dùng để test và tune retrieval pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.security import limiter
from app.models import SearchResponse
from app.rag.reranker import BaseReranker, get_reranker
from app.rag.retriever import Retriever

router = APIRouter(prefix="/search", tags=["Search (Debug)"])


@router.get(
    "",
    response_model=SearchResponse,
    summary="Debug: chạy hybrid search + rerank, trả kết quả raw",
)
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(..., min_length=1, description="Query string"),
    top_k: int = Query(10, ge=1, le=50, description="Số kết quả trả về"),
    use_rerank: bool = Query(True, description="Có chạy reranker không"),
    retriever: Retriever = Depends(lambda: Retriever()),
    reranker: BaseReranker = Depends(get_reranker),
) -> SearchResponse:
    """Chạy hybrid search (dense + sparse + RRF) và optionally rerank.

    Dùng để:
    - Kiểm tra chất lượng retrieval với một query cụ thể.
    - Tune các tham số top_k, rerank.
    - Debug xem chunks nào được retrieve.

    Args:
        http_request: FastAPI Request (rate limiter).
        q: Query text.
        top_k: Số kết quả.
        use_rerank: Có dùng reranker không.
        retriever: Injected Retriever.
        reranker: Injected Reranker.

    Returns:
        SearchResponse với danh sách hits kèm scores.
    """
    ...
