"""
app/rag/retriever.py
--------------------
Orchestrate hybrid search pipeline:
Wrapper mỏng quanh HybridSearcher để chuẩn hóa interface cho pipeline.py.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.rag.hybrid_search import HybridSearcher, SearchResult

logger = get_logger(__name__)


class Retriever:
    """Orchestrate retrieval: chạy hybrid search và trả về danh sách kết quả.

    Là interface trung gian giữa ``pipeline.py`` và ``HybridSearcher``.
    Có thể mở rộng để thêm pre/post-processing (query expansion, metadata filter, ...).

    Attributes:
        searcher (HybridSearcher): Underlying hybrid search engine.
    """

    def __init__(self, searcher: HybridSearcher | None = None) -> None:
        """Khởi tạo Retriever.

        Args:
            searcher: HybridSearcher instance. Mặc định tạo mới.
        """
        self.searcher = searcher or HybridSearcher()

    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Lấy top-k documents liên quan nhất với query.

        Args:
            query: Query text của user (đã qua query rewriting nếu có).
            top_k: Số documents trả về. Mặc định 20 (sẽ qua reranker sau).
            filter: Metadata filter tùy chọn (ví dụ lọc theo loại văn bản pháp luật).

        Returns:
            List[SearchResult] đã sort theo RRF score, giới hạn top_k.
        """
        ...

    async def retrieve_for_ingestion_check(self, doc_id: str) -> bool:
        """Kiểm tra xem document đã tồn tại trong index chưa (dedup check).

        Args:
            doc_id: ID của document cần kiểm tra.

        Returns:
            True nếu document đã được index, False nếu chưa.
        """
        ...
