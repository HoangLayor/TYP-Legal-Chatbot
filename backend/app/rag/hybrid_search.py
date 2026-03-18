"""
app/rag/hybrid_search.py
-------------------------
Hybrid Search: kết hợp Dense (ANN vector) và Sparse (BM25) search,
merge kết quả bằng Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.bm25_store import BM25Store, get_bm25_store
from app.db.vector_db import VectorDBClient, get_vector_db
from app.rag.embedder import Embedder, get_embedder

logger = get_logger(__name__)
settings = get_settings()

# Hằng số RRF
RRF_K = 60
"""Hằng số k trong công thức RRF: score = Σ 1 / (k + rank_i)."""


@dataclass
class SearchResult:
    """Kết quả từ hybrid search.

    Attributes:
        id: ID của document/chunk.
        score: RRF score (hoặc dense/sparse score nếu chỉ dùng một nhánh).
        text: Nội dung văn bản của chunk.
        metadata: Metadata đi kèm (nguồn, trang, ...).
        dense_rank: Thứ hạng từ dense search (None nếu không trong top-k dense).
        sparse_rank: Thứ hạng từ sparse search (None nếu không trong top-k sparse).
    """

    id: str
    score: float
    text: str
    metadata: dict[str, Any]
    dense_rank: int | None = None
    sparse_rank: int | None = None


class HybridSearcher:
    """Thực hiện hybrid search kết hợp dense và sparse.

    Chạy cả hai nhánh song song (asyncio.gather) để giảm latency,
    sau đó merge bằng RRF.

    Attributes:
        vector_db (VectorDBClient): Client truy vấn dense ANN.
        bm25_store (BM25Store): Sparse BM25 index.
        embedder (Embedder): Encode query thành vector.
        rrf_k (int): Hằng số k cho công thức RRF.
    """

    def __init__(
        self,
        vector_db: VectorDBClient | None = None,
        bm25_store: BM25Store | None = None,
        embedder: Embedder | None = None,
        rrf_k: int = RRF_K,
    ) -> None:
        """Khởi tạo HybridSearcher với các dependency.

        Args:
            vector_db: Vector DB client. Mặc định dùng singleton từ ``get_vector_db()``.
            bm25_store: BM25 store. Mặc định dùng singleton từ ``get_bm25_store()``.
            embedder: Embedder. Mặc định dùng singleton từ ``get_embedder()``.
            rrf_k: Hằng số k cho RRF. Mặc định 60.
        """
        self.vector_db = vector_db or get_vector_db()
        self.bm25_store = bm25_store or get_bm25_store()
        self.embedder = embedder or get_embedder()
        self.rrf_k = rrf_k

    async def _dense_search(
        self,
        query: str,
        top_k: int,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Nhánh dense search: embed query → ANN lookup.

        Args:
            query: Query text.
            top_k: Số kết quả.
            filter: Metadata filter cho Vector DB.

        Returns:
            List kết quả từ Vector DB, đã có ``rank`` field.
        """
        ...

    def _sparse_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Nhánh sparse search: BM25 keyword matching.

        Args:
            query: Query text.
            top_k: Số kết quả.

        Returns:
            List kết quả từ BM25Store, đã có ``rank`` field.
        """
        ...

    def _rrf_merge(
        self,
        dense_results: list[dict[str, Any]],
        sparse_results: list[dict[str, Any]],
    ) -> list[SearchResult]:
        """Merge dense và sparse results bằng Reciprocal Rank Fusion.

        Công thức: RRF_score(doc) = Σ 1 / (k + rank_i)
        với k = ``self.rrf_k`` và rank_i là thứ hạng trong mỗi nhánh.

        Docs không có trong một nhánh được bỏ qua trong nhánh đó.

        Args:
            dense_results: Kết quả từ dense search (đã có ``rank``).
            sparse_results: Kết quả từ sparse search (đã có ``rank``).

        Returns:
            List[SearchResult] đã sort theo RRF score giảm dần.
        """
        ...

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """Thực hiện hybrid search tổng hợp.

        Chạy dense và sparse song song, merge bằng RRF.

        Args:
            query: Query text của user.
            top_k: Số kết quả trả về sau RRF.
            filter: Metadata filter (chỉ áp dụng cho dense search).

        Returns:
            List[SearchResult] sorted theo RRF score giảm dần,
            giới hạn ``top_k`` phần tử.
        """
        ...
