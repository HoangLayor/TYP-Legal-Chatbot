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
    """Orchestrate toàn bộ RAG pipeline."""

    def __init__(
        self,
        retriever: Retriever | None = None,
        reranker: BaseReranker | None = None,
        generator: Generator | None = None,
        web_searcher: TavilySearcher | None = None,
        history_manager: HistoryManager | None = None,
    ) -> None:
        self.retriever = retriever or Retriever()
        self.reranker = reranker or get_reranker()
        self.generator = generator or get_generator()
        self.web_searcher = web_searcher or get_tavily_searcher()
        self.history_manager = history_manager or get_history_manager()

    async def _rewrite_query(self, query: str, history: list[dict]) -> str:
        """(Optional) Viết lại query để rõ ràng hơn dựa trên context lịch sử."""
        # Tối ưu: Nếu không có lịch sử trò chuyện, không cần viết lại câu hỏi
        if not history:
            return query

        try:
            # Lấy 2 câu hỏi - đáp gần nhất để tạo ngữ cảnh
            recent_history = history[-4:] 
            history_text = "\n".join([f"{msg.get('role')}: {msg.get('content')}" for msg in recent_history])
            
            prompt = (
                f"Lịch sử trò chuyện:\n{history_text}\n\n"
                f"Câu hỏi mới của người dùng: '{query}'\n\n"
                "Nhiệm vụ: Hãy viết lại câu hỏi mới sao cho nó trở thành một câu độc lập, "
                "đầy đủ ý nghĩa dựa vào lịch sử trên (thay thế các đại từ 'nó', 'điều đó' bằng danh từ cụ thể). "
                "Chỉ trả về câu hỏi đã viết lại, không giải thích gì thêm."
            )
            
            # Sử dụng non-stream generation để lấy câu hỏi viết lại nhanh chóng
            rewritten_query = await self.generator.client.aio.models.generate_content(
                model=self.generator.model,
                contents=prompt
            )
            
            final_query = rewritten_query.text.strip() if rewritten_query.text else query
            logger.info(f"Đã viết lại câu hỏi: '{query}' -> '{final_query}'")
            return final_query
            
        except Exception as e:
            logger.error(f"Lỗi khi rewrite query: {e}")
            return query # Fallback: Trả về câu hỏi gốc nếu lỗi

    async def _build_sources(
        self,
        ranked_results: list[RankedResult],
        web_results: list[WebSearchResult],
    ) -> list[dict[str, Any]]:
        """Tổng hợp sources từ chunks và web results để gửi kèm response."""
        sources = []
        
        # Thêm tài liệu pháp lý từ Database
        for rank, res in enumerate(ranked_results, start=1):
            sources.append({
                "type": "document",
                "title": res.metadata.get("filename", "Tài liệu hệ thống"),
                "url": res.metadata.get("url", ""), # Nếu có URL dẫn tới file PDF
                "score": round(res.rerank_score, 4),
                "page": res.metadata.get("page", ""),
                "snippet": res.text[:200] + "..." # Lấy đoạn trích ngắn
            })
            
        # Thêm các bài viết từ Internet
        for web in web_results:
            sources.append({
                "type": "web",
                "title": web.title,
                "url": web.url,
                "score": round(web.score, 4),
                "snippet": web.content[:200] + "..."
            })
            
        return sources

    async def run_stream(
        self,
        session_id: str,
        query: str,
        use_web_search: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Chạy toàn bộ pipeline và yield SSE events."""
        try:
            # 1. Load lịch sử trò chuyện
            # history = await self.history_manager.get_session_history(session_id)
            history = []
            
            # 2. Viết lại câu hỏi
            actual_query = await self._rewrite_query(query, history)
            
            # 3. Retrieval: Hybrid Search (BM25 + Vector DB)
            retrieved_docs = await self.retriever.retrieve(query=actual_query, top_k=20)
            
            # 4. Reranking: Chấm điểm lại để chọn Top 5 chuẩn nhất
            ranked_docs = await self.reranker.rerank(query=actual_query, results=retrieved_docs, top_n=5)
            
            # 5. Fallback Web Search: Kiểm tra xem có cần lên mạng tìm thêm không
            web_results = []
            top_score = ranked_docs[0].rerank_score if ranked_docs else 0.0
            
            if use_web_search and self.web_searcher.should_search(actual_query, top_score):
                web_results = await self.web_searcher.search(actual_query)
                
            # 6. Generator: Tạo prompt và gọi LLM Streaming
            full_answer = ""
            async for chunk_text in self.generator.generate_stream(
                query=actual_query,
                ranked_results=ranked_docs,
                history=history,
                web_results=web_results
            ):
                full_answer += chunk_text
                # Yield từng chữ ra cho Frontend theo chuẩn Server-Sent Events (SSE)
                yield {"type": "chunk", "content": chunk_text}
                
            # 7. Lưu lại lịch sử vào MongoDB
            # await self.history_manager.add_message(session_id, role="user", content=query)
            # await self.history_manager.add_message(session_id, role="assistant", content=full_answer)
            
            # 8. Đóng gói Nguồn (Sources) trả về ở cuối cùng
            sources = await self._build_sources(ranked_docs, web_results)
            yield {"type": "sources", "items": sources}
            
            # Báo hiệu kết thúc luồng
            yield {"type": "done"}
            
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng trong Pipeline Stream: {e}")
            yield {"type": "error", "message": "Hệ thống đang gặp sự cố. Vui lòng thử lại sau."}

    async def run(
        self,
        session_id: str,
        query: str,
        use_web_search: bool = True,
    ) -> PipelineResult:
        """Chạy pipeline không streaming, trả về kết quả đầy đủ."""
        # 1 & 2. Lịch sử và Viết lại câu hỏi
        # history = await self.history_manager.get_session_history(session_id)
        history = []
        actual_query = await self._rewrite_query(query, history)
        
        # 3 & 4. Retrieve và Rerank
        retrieved_docs = await self.retriever.retrieve(query=actual_query, top_k=20)
        ranked_docs = await self.reranker.rerank(query=actual_query, results=retrieved_docs, top_n=5)
        
        # 5. Web Search
        web_results = []
        top_score = ranked_docs[0].rerank_score if ranked_docs else 0.0
        if use_web_search and self.web_searcher.should_search(actual_query, top_score):
            web_results = await self.web_searcher.search(actual_query)
            
        # 6. Sinh câu trả lời (Non-stream)
        answer = await self.generator.generate(
            query=actual_query,
            ranked_results=ranked_docs,
            history=history,
            web_results=web_results
        )
        
        # 7. Lưu lịch sử
        # await self.history_manager.add_message(session_id, role="user", content=query)
        # await self.history_manager.add_message(session_id, role="assistant", content=answer)
        
        # 8. Đóng gói kết quả
        sources = await self._build_sources(ranked_docs, web_results)
        
        return PipelineResult(
            answer=answer,
            sources=sources,
            used_web_search=bool(web_results),
            top_score=top_score
        )

if __name__ == "__main__":
    import asyncio

    async def main():
        # Khởi tạo pipeline
        pipeline = RAGPipeline()
        
        query = input("Hãy nhập câu hỏi: ")
        print(f"Câu hỏi: {query}\nĐang chạy pipeline, vui lòng đợi vài giây...")

        # Chạy luồng non-stream, lấy luôn kết quả cuối cùng
        result = await pipeline.run(
            session_id="test_cuc_nhanh",
            query=query,
            use_web_search=False
        )

        print("\n=== CÂU TRẢ LỜI ===")
        print(result.answer)
        
        print("\n=== TÀI LIỆU TÌM ĐƯỢC ===")
        for doc in result.sources:
            print(f"- {doc['title']} (Điểm: {doc['score']})")

    # Bấm chạy
    asyncio.run(main())