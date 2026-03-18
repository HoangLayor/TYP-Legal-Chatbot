"""
app/rag/web_search.py
----------------------
Tavily Web Search client — tìm kiếm web khi knowledge base không đủ thông tin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class WebSearchResult:
    """Kết quả từ Tavily web search.

    Attributes:
        title: Tiêu đề trang web.
        url: URL nguồn.
        content: Đoạn text trích xuất từ trang (snippet).
        score: Relevance score từ Tavily (0–1).
    """

    title: str
    url: str
    content: str
    score: float = 0.0


class TavilySearcher:
    """Client gọi Tavily Search API.

    Tavily được gọi fallback khi:
    - Max rerank score < ``WEB_SEARCH_THRESHOLD``, hoặc
    - Query chứa từ khoá thời sự (hôm nay, mới nhất, 2025, ...).

    Attributes:
        api_key (str): Tavily API key.
        search_depth (str): ``"basic"`` hoặc ``"advanced"``.
        max_results (int): Số kết quả tối đa mỗi query.
    """

    # Từ khoá gợi ý tìm kiếm real-time
    REALTIME_KEYWORDS: list[str] = [
        "hôm nay",
        "mới nhất",
        "gần đây",
        "vừa qua",
        "2025",
        "2026",
        "hiện tại",
        "latest",
        "today",
    ]

    def __init__(self) -> None:
        """Khởi tạo Tavily async client."""
        ...

    def should_search(self, query: str, max_rerank_score: float) -> bool:
        """Quyết định có nên gọi Tavily hay không.

        Args:
            query: Query text của user.
            max_rerank_score: Score cao nhất sau reranking.

        Returns:
            True nếu nên gọi Tavily (score thấp hoặc query thời sự).
        """
        score_below_threshold = max_rerank_score < settings.web_search_threshold
        has_realtime_keyword = any(kw in query.lower() for kw in self.REALTIME_KEYWORDS)
        return score_below_threshold or has_realtime_keyword

    async def search(self, query: str) -> list[WebSearchResult]:
        """Thực hiện Tavily web search.

        Args:
            query: Query text cần tìm kiếm.

        Returns:
            List[WebSearchResult] sorted theo score giảm dần,
            giới hạn ``self.max_results`` kết quả.

        Raises:
            tavily.TavilyError: Nếu API call thất bại.
        """
        ...

    def format_for_context(self, results: list[WebSearchResult]) -> str:
        """Định dạng kết quả web thành string để nhúng vào prompt context.

        Mỗi kết quả được đánh dấu ``[Web]`` để LLM phân biệt nguồn.

        Args:
            results: Danh sách kết quả từ ``search()``.

        Returns:
            String định dạng sẵn để thêm vào system prompt context.

        Example::

            [Web] Nguồn: https://example.com — Tiêu đề
            Nội dung: ...
        """
        ...


# ── Singleton ─────────────────────────────────────────────────────────────────

_tavily_searcher: TavilySearcher | None = None


def get_tavily_searcher() -> TavilySearcher:
    """Trả về singleton TavilySearcher.

    Returns:
        TavilySearcher: Instance được tái sử dụng.
    """
    global _tavily_searcher
    if _tavily_searcher is None:
        _tavily_searcher = TavilySearcher()
    return _tavily_searcher
