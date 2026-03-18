"""
app/rag/pipeline.py
--------------------
Orchestrate toàn bộ RAG pipeline từ query đến streaming response.
Đây là entry point chính được gọi từ API endpoint /chat/stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.memory.history_manager import HistoryManager, get_history_manager
from app.rag.generator import Generator, get_generator
from app.rag.reranker import BaseReranker, RankedResult, get_reranker
from app.rag.retriever import Retriever
from app.rag.web_search import TavilySearcher, WebSearchResult, get_tavily_searcher

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class PipelineResult:
    """Kết quả đầy đủ của một pipeline run (dùng cho non-streaming mode).

    Attributes:
        answer: Câu trả lời đầy đủ từ LLM.
        sources: Danh sách sources đính kèm (ranked chunks + web).
        used_web_search: Có gọi Tavily hay không.
        top_score: Max rerank score (để debug/monitor).
    """

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    used_web_search: bool = False
    top_score: float = 0.0


class RAGPipeline:
    """Orchestrate toàn bộ RAG pipeline.

    Thứ tự xử lý:
    1. Load chat history từ MongoDB.
    2. (Optional) Query rewriting.
    3. Retrieval: Hybrid Search → RRF merge.
    4. Reranking: Cross-encoder top-k → top-n.
    5. (Conditional) Tavily web search nếu score thấp hoặc query thời sự.
    6. Build prompt: system + history + context + query.
    7. LLM stream generation.
    8. Lưu message vào MongoDB.
    9. Stream về client.

    Attributes:
        retriever (Retriever): Hybrid search retriever.
        reranker (BaseReranker): Cross-encoder reranker.
        generator (Generator): LLM generator.
        web_searcher (TavilySearcher): Tavily client.
        history_manager (HistoryManager): MongoDB history manager.
    """

    def __init__(
        self,
        retriever: Retriever | None = None,
        reranker: BaseReranker | None = None,
        generator: Generator | None = None,
        web_searcher: TavilySearcher | None = None,
        history_manager: HistoryManager | None = None,
    ) -> None:
        """Khởi tạo RAGPipeline với tất cả components.

        Args:
            retriever: Retriever instance. Mặc định tạo mới.
            reranker: Reranker instance. Mặc định dùng factory.
            generator: Generator instance. Mặc định dùng factory.
            web_searcher: Tavily client. Mặc định dùng factory.
            history_manager: MongoDB history manager. Mặc định dùng factory.
        """
        self.retriever = retriever or Retriever()
        self.reranker = reranker or get_reranker()
        self.generator = generator or get_generator()
        self.web_searcher = web_searcher or get_tavily_searcher()
        self.history_manager = history_manager or get_history_manager()

    async def _rewrite_query(self, query: str, history: list[dict]) -> str:
        """(Optional) Viết lại query để rõ ràng hơn dựa trên context lịch sử.

        Ví dụ: "Nó quy định gì?" → "Điều 5 Luật Doanh nghiệp 2020 quy định gì?"

        Args:
            query: Query gốc từ user.
            history: Chat history gần nhất.

        Returns:
            Query đã viết lại, hoặc query gốc nếu không cần thiết.
        """
        ...

    async def _build_sources(
        self,
        ranked_results: list[RankedResult],
        web_results: list[WebSearchResult],
    ) -> list[dict[str, Any]]:
        """Tổng hợp sources từ chunks và web results để gửi kèm response.

        Args:
            ranked_results: Chunks đã rerank.
            web_results: Web search results (có thể rỗng).

        Returns:
            List dict ``{"type": "document"|"web", "title": str, "url": str, "score": float}``.
        """
        ...

    async def run_stream(
        self,
        session_id: str,
        query: str,
        use_web_search: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Chạy toàn bộ pipeline và yield SSE events.

        Yield các event theo format:
        - ``{"type": "chunk", "content": str}`` — text từ LLM stream.
        - ``{"type": "sources", "items": list}`` — sources sau khi hoàn thành.
        - ``{"type": "done"}`` — signal kết thúc stream.
        - ``{"type": "error", "message": str}`` — nếu có lỗi.

        Args:
            session_id: UUID session của user (dùng làm key lưu history).
            query: Query text từ user.
            use_web_search: Cho phép gọi Tavily nếu cần. Mặc định True.

        Yields:
            dict: SSE event object.
        """
        ...

    async def run(
        self,
        session_id: str,
        query: str,
        use_web_search: bool = True,
    ) -> PipelineResult:
        """Chạy pipeline không streaming, trả về kết quả đầy đủ.

        Dùng để test hoặc các endpoint không cần SSE.

        Args:
            session_id: UUID session.
            query: Query text.
            use_web_search: Cho phép web search.

        Returns:
            PipelineResult chứa answer, sources và metadata.
        """
        ...
