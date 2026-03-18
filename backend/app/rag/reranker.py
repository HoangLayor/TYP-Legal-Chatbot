"""
app/rag/reranker.py
--------------------
Cross-encoder reranking để tăng độ chính xác sau hybrid search.
Hỗ trợ Cohere Rerank API và BAAI/bge-reranker-v2-m3 (local).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.hybrid_search import SearchResult

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class RankedResult:
    """Kết quả sau khi rerank.

    Attributes:
        id: Chunk ID.
        rerank_score: Score từ cross-encoder (0–1, càng cao càng liên quan).
        text: Nội dung chunk.
        metadata: Metadata của chunk.
        original_rank: Thứ hạng trước khi rerank (từ RRF).
    """

    id: str
    rerank_score: float
    text: str
    metadata: dict[str, Any]
    original_rank: int


# ── Abstract interface ────────────────────────────────────────────────────────


class BaseReranker(ABC):
    """Abstract base class cho tất cả reranker implementations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Rerank danh sách SearchResult theo relevance với query.

        Args:
            query: Query text gốc của user.
            results: Kết quả từ hybrid search cần rerank.
            top_n: Số kết quả giữ lại sau rerank.

        Returns:
            List[RankedResult] sorted theo rerank_score giảm dần,
            giới hạn top_n phần tử.
        """
        ...


# ── Cohere Reranker ───────────────────────────────────────────────────────────


class CohereReranker(BaseReranker):
    """Reranker sử dụng Cohere Rerank API.

    Model mặc định: ``rerank-multilingual-v3.0`` (hỗ trợ tiếng Việt).

    Attributes:
        client: Cohere AsyncClient.
        model (str): Tên model rerank của Cohere.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Khởi tạo Cohere client.

        Args:
            api_key: Cohere API key. Mặc định từ config.
        """
        ...

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Gọi Cohere Rerank API để score lại kết quả.

        Args:
            query: Query text.
            results: Danh sách SearchResult cần rerank (tối đa RERANK_TOP_K).
            top_n: Số kết quả giữ lại.

        Returns:
            List[RankedResult] sorted theo Cohere score.

        Raises:
            cohere.CohereAPIError: Nếu API call thất bại.
        """
        ...


# ── BGE Reranker (local) ──────────────────────────────────────────────────────


class BGEReranker(BaseReranker):
    """Reranker sử dụng BAAI/bge-reranker-v2-m3 chạy local.

    Không cần API key, nhưng cần GPU hoặc CPU đủ mạnh.
    Model được load lần đầu và giữ trong memory.

    Attributes:
        model_name (str): HuggingFace model ID.
        tokenizer: HuggingFace tokenizer.
        model: Cross-encoder model.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Load BGE reranker model từ HuggingFace Hub.

        Args:
            model_name: Model ID. Mặc định ``BAAI/bge-reranker-v2-m3`` từ config.
        """
        ...

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Score từng cặp (query, chunk) bằng BGE cross-encoder.

        Chạy trong executor để không block event loop.

        Args:
            query: Query text.
            results: Danh sách SearchResult.
            top_n: Số kết quả giữ lại.

        Returns:
            List[RankedResult] sorted theo BGE score.
        """
        ...


# ── No-op Reranker ────────────────────────────────────────────────────────────


class PassthroughReranker(BaseReranker):
    """Reranker giả — chỉ convert SearchResult → RankedResult không đổi thứ tự.

    Dùng khi ``RERANKER_PROVIDER=none`` hoặc để test.
    """

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Convert SearchResult thành RankedResult, giữ nguyên thứ tự RRF.

        Args:
            query: Không dùng.
            results: Danh sách SearchResult.
            top_n: Số phần tử giữ lại.

        Returns:
            List[RankedResult] với score = RRF score gốc, giới hạn top_n.
        """
        ...


# ── Factory ───────────────────────────────────────────────────────────────────

_reranker: BaseReranker | None = None


def get_reranker() -> BaseReranker:
    """Factory — trả về reranker phù hợp với config.

    Singleton: chỉ khởi tạo một lần.

    Returns:
        BaseReranker: Cohere, BGE hoặc Passthrough reranker.

    Raises:
        ValueError: Nếu ``RERANKER_PROVIDER`` không hợp lệ.
    """
    global _reranker
    if _reranker is not None:
        return _reranker

    provider = settings.reranker_provider
    logger.info("reranker_init", provider=provider)

    if provider == "cohere":
        _reranker = CohereReranker()
    elif provider == "bge":
        _reranker = BGEReranker()
    elif provider == "none":
        _reranker = PassthroughReranker()
    else:
        raise ValueError(f"Unsupported reranker provider: {provider}")

    return _reranker
