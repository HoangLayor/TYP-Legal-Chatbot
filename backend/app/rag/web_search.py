"""
app/rag/web_search.py
----------------------
Tavily Web Search client — tìm kiếm web khi knowledge base không đủ thông tin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import get_settings
from app.core.logging import get_logger

from tavily import AsyncTavilyClient

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
    search_depth: Literal['basic', 'advanced', 'fast', 'ultra-fast']

    def __init__(self) -> None:
        """Khởi tạo Tavily async client."""
        # Lấy API key từ cấu hình
        self.api_key = settings.tavily_api_key
        
        if not self.api_key:
            logger.warning("Chưa cấu hình TAVILY_API_KEY. Tính năng Web Search sẽ bị vô hiệu hóa.")
            self.client = None
        else:
            # Khởi tạo Client bất đồng bộ
            self.client = AsyncTavilyClient(api_key=self.api_key)
            
        # Cấu hình độ sâu tìm kiếm và số lượng kết quả
        self.search_depth = settings.tavily_search_depth
        self.max_results = settings.tavily_max_results

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
        if not self.client:
            return []

        logger.info(f"Kích hoạt Web Search với từ khóa: '{query}'")

        try:
            # Gọi API tìm kiếm của Tavily
            response = await self.client.search(
                query=query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_answer=False,       # Chỉ cần trích xuất nội dung, không cần Tavily tự gen câu trả lời
                include_raw_content=False   # Không cần lấy nguyên cục HTML raw cho nặng
            )

            results: list[WebSearchResult] = []
            
            # Tavily trả về một dictionary, danh sách bài web nằm trong key 'results'
            for item in response.get("results", []):
                results.append(
                    WebSearchResult(
                        title=item.get("title", "Không có tiêu đề"),
                        url=item.get("url", ""),
                        content=item.get("content", ""),
                        score=item.get("score", 0.0)
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Lỗi khi gọi Tavily Search API với query '{query}': {e}")
            return []



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
        # 1. Xử lý an toàn: Nếu mảng rỗng thì trả về chuỗi rỗng
        if not results:
            return ""

        formatted_parts = []
        
        # 2. Duyệt qua từng kết quả tìm kiếm được
        for result in results:
            # Dọn dẹp các khoảng trắng hoặc dấu xuống dòng thừa ở hai đầu
            clean_content = result.content.strip()
            
            # 3. Ép khuôn định dạng (như docstring đã thiết kế)
            part = (
                f"[Web] Nguồn: {result.url} — {result.title}\n"
                f"Nội dung: {clean_content}"
            )
            formatted_parts.append(part)

        # 4. Ghép tất cả các mảnh lại, cách nhau bởi 2 dấu xuống dòng để LLM dễ đọc
        return "\n\n".join(formatted_parts)


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


if __name__ == "__main__":
    import asyncio
    async def main():
        searcher = TavilySearcher()
        list_res = await searcher.search("Giá xăng hôm nay là bao nhiêu?")
        # for i, res in enumerate(list_res):
        #     print(f'{i + 1}: {res.title}')
        #     print(f'url: {res.url}')
        #     print(res.content)
        #     print("====================================================================================================")
        print(searcher.format_for_context(list_res))

    asyncio.run(main())
