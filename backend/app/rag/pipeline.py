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
        # 1. Tối ưu: Nếu chưa có lịch sử (câu hỏi đầu tiên), không cần tốn tiền gọi AI làm gì
        if not history:
            return query

        logger.debug(f"Đang phân tích ngữ cảnh để viết lại câu hỏi: '{query}'")

        # 2. Rút gọn lịch sử: Chỉ lấy 6 tin nhắn (3 lượt hỏi-đáp) gần nhất để tiết kiệm token và tránh nhiễu
        recent_history = history[-6:]
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in recent_history])
        
        # 3. Prompt thiết kế đặc biệt (Chỉ thị rõ ràng, không cho phép AI trả lời)
        system_prompt = (
            "Bạn là một trợ lý phân tích ngữ cảnh ngôn ngữ. "
            "Nhiệm vụ của bạn: Đọc 'Lịch sử trò chuyện' và 'Câu hỏi mới nhất' của người dùng, "
            "sau đó viết lại câu hỏi mới nhất thành một câu hỏi ĐỘC LẬP (standalone query) "
            "sao cho có thể hiểu trọn vẹn ý nghĩa mà không cần đọc lịch sử.\n\n"
            "Quy tắc:\n"
            "1. Giải quyết các đại từ nhân xưng, từ chỉ định (nó, thế còn, vậy, v.v.) bằng danh từ cụ thể trong lịch sử.\n"
            "2. NẾU câu hỏi đã đủ rõ ràng, hãy trả về y nguyên.\n"
            "3. KHÔNG BAO GIỜ tự trả lời câu hỏi.\n"
            "4. CHỈ trả về đúng một câu hỏi đã được viết lại, không có văn bản nào khác."
        )
        
        user_prompt = f"--- Lịch sử trò chuyện ---\n{history_text}\n\n--- Câu hỏi mới nhất ---\nUser: {query}\n\nCâu hỏi độc lập:"

        try:
            # 4. Gọi LLM xuyên qua Generator client
            # Dùng thẳng client của self.generator để không phải khởi tạo lại
            response = await self.generator.client.chat.completions.create(
                model=self.generator.model, # Hoặc có thể cấu hình dùng model rẻ hơn như gpt-4o-mini ở đây
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0, # Nhiệt độ bằng 0: Yêu cầu tính chính xác tuyệt đối, không sáng tạo văn vở
                max_tokens=150   # Câu hỏi viết lại thường rất ngắn
            )
            
            rewritten_query = response.choices[0].message.content.strip()
            rewritten_query = response.choices[0].message.content
            
            # Ghi log để theo dõi độ thông minh của AI
            if rewritten_query != query:
                logger.info(f"Query Rewriting: '{query}' -> '{rewritten_query}'")
            else:
                logger.debug(f"Query Rewriting: Giữ nguyên '{query}'")
                
            return rewritten_query
            
        except Exception as e:
            # Phao cứu sinh: Nếu LLM lỗi (hết rate limit, đứt mạng...), 
            # ta nuốt lỗi và cứ dùng câu hỏi gốc để hệ thống vẫn chạy tiếp được.
            logger.error(f"Lỗi khi viết lại câu hỏi, fallback về query gốc: {e}")
            return query

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
        sources: list[dict[str, Any]] = []

        # 1. Xử lý tài liệu nội bộ (Từ Vector DB -> Reranker)
        for res in ranked_results:
            # Trích xuất metadata an toàn (dùng .get để không bị lỗi KeyError)
            meta = res.metadata or {}
            
            # Khéo léo ghép tên file và số trang làm Tiêu đề hiển thị
            filename = meta.get("filename", "Tài liệu nội bộ")
            page = meta.get("page")
            title = f"{filename} (Trang {page})" if page else filename

            sources.append({
                "type": "document",           # Đánh dấu loại nguồn
                "title": title,               # Tiêu đề hiển thị cho User
                "url": meta.get("url", ""),   # Link tải file PDF gốc (nếu bạn có lưu trong DB)
                "score": res.rerank_score,    # Điểm tin cậy từ Reranker
                "id": res.id,                 # ID của chunk để frontend làm key
                # Lấy 150 ký tự đầu tiên làm trích đoạn mồi (snippet) cho giao diện đẹp hơn
                "snippet": res.text[:150].strip() + "..." 
            })

        # 2. Xử lý tài liệu Internet (Từ Tavily)
        if web_results:
            for web in web_results:
                sources.append({
                    "type": "web",
                    "title": web.title,
                    "url": web.url,               # Link bài báo/trang web để User click vào đọc
                    "score": web.score,           # Điểm tin cậy từ Tavily
                    "id": web.url,                # Lấy luôn URL làm ID cho web
                    "snippet": web.content[:150].strip() + "..."
                })

        # 3. (Tùy chọn) Sắp xếp lại toàn bộ mảng theo điểm tin cậy từ cao xuống thấp 
        # Mặc dù từng mảng đã được xếp riêng, nhưng khi gộp chung ta có thể sort lại lần nữa cho chắc
        sources.sort(key=lambda x: x["score"], reverse=True)

        return sources

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
        logger.info(f"Bắt đầu Pipeline Stream cho session: {session_id} | Query: '{query}'")
        
        try:
            # 1. Gọi quản gia: Lấy lịch sử trò chuyện từ Database (MongoDB/PostgreSQL)
            # Trả về danh sách [{"role": "user", "content": "..."}, {"role": "assistant", ...}]
            history = await self.history_manager.get_history(session_id)

            # 2. Gọi phiên dịch: Viết lại câu hỏi nếu cần thiết (để Vector DB tìm chuẩn hơn)
            actual_query = await self._rewrite_query(query, history)

            # 3. Gọi đặc nhiệm: Hybrid Search (Vector + BM25 -> RRF)
            # Lấy dư ra một chút (top_k=20) để lát nữa cho Reranker có nhiều lựa chọn
            search_results = await self.retriever.retrieve(query=actual_query, top_k=20)

            # 4. Gọi giám khảo: Chấm điểm lại và chỉ lấy top 5 bài xuất sắc nhất
            ranked_results = await self.reranker.rerank(
                query=actual_query, 
                results=search_results, 
                top_n=5
            )

            # 5. Lướt Web (Tavily Fallback): Nếu điểm quá thấp hoặc hỏi thời sự
            web_results = []
            if use_web_search:
                # Lấy điểm cao nhất của tài liệu nội bộ (nếu có)
                max_score = ranked_results[0].rerank_score if ranked_results else 0.0
                
                # Gọi người gác cổng should_search của TavilySearcher
                if self.web_searcher.should_search(actual_query, max_score):
                    web_results = await self.web_searcher.search(actual_query)

            # 6. Chuẩn bị Bằng chứng thép (Sources)
            sources = await self._build_sources(ranked_results, web_results)
            
            # IELD ĐẦU TIÊN: Đẩy ngay danh sách tài liệu xuống Frontend!
            # Lúc này Frontend có thể hiện UI "Đang đọc: Điều 15 Luật..." dù AI chưa nói câu nào
            yield {"type": "sources", "items": sources}

            # 7. Gọi nhà văn OpenAI: Bắt đầu sinh câu trả lời (Streaming)
            full_answer = ""
            stream = self.generator.generate_stream(
                query=actual_query, # Nhét câu hỏi đã được làm rõ vào prompt
                ranked_results=ranked_results,
                history=history,
                web_results=web_results
            )

            # Hứng từng giọt chữ rớt xuống từ OpenAI và ném thẳng ra SSE
            async for chunk in stream:
                full_answer += chunk
                # YIELD THỨ HAI: Bắn chữ về Frontend liên tục (hiệu ứng typing)
                yield {"type": "chunk", "content": chunk}

            # 8. Ghi chép lịch sử: Lưu lại phiên hỏi đáp vào Database
            # Lưu ý: Lưu câu hỏi GỐC của user để UI hiển thị lịch sử cho đúng
            await self.history_manager.add_message(session_id, "user", query)
            await self.history_manager.add_message(session_id, "assistant", full_answer)

            # YIELD CUỐI CÙNG: Báo hiệu kết thúc
            yield {"type": "done"}
            logger.info(f"Kết thúc luồng Stream thành công cho session: {session_id}")

        except Exception as e:
            # Bắt toàn bộ lỗi (đứt cáp, sập DB, hết tiền API...)
            logger.error(f"Pipeline bị vỡ tại luồng Stream: {e}")
            # Bắn sự kiện lỗi về cho Frontend để nó hiện Pop-up thông báo thay vì loading mãi mãi
            yield {"type": "error", "message": "Hệ thống đang gặp sự cố. Vui lòng thử lại sau."}

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
        logger.info(f"Bắt đầu Pipeline (Non-stream) cho session: {session_id} | Query: '{query}'")
        
        try:
            # 1. Lấy lịch sử và viết lại câu hỏi (Giống hệt luồng Stream)
            history = await self.history_manager.get_history(session_id)
            actual_query = await self._rewrite_query(query, history)

            # 2. Tìm kiếm và Chấm điểm (Hybrid + Rerank)
            search_results = await self.retriever.retrieve(query=actual_query, top_k=20)
            ranked_results = await self.reranker.rerank(
                query=actual_query, 
                results=search_results, 
                top_n=5
            )

            # 3. Lướt Web (Tavily Fallback)
            web_results = []
            used_web = False
            top_score = ranked_results[0].rerank_score if ranked_results else 0.0
            
            if use_web_search and self.web_searcher.should_search(actual_query, top_score):
                web_results = await self.web_searcher.search(actual_query)
                used_web = True

            # 4. Chuẩn bị tài liệu trích dẫn
            sources = await self._build_sources(ranked_results, web_results)

            # 5. Gọi AI sinh câu trả lời (Sử dụng hàm generate non-stream)
            # Khác với generate_stream, hàm này sẽ block (chặn) cho đến khi AI viết xong toàn bộ chữ
            answer = await self.generator.generate(
                query=actual_query,
                ranked_results=ranked_results,
                history=history,
                web_results=web_results
            )

            # 6. Lưu lịch sử vào Database
            await self.history_manager.add_message(session_id, "user", query)
            await self.history_manager.add_message(session_id, "assistant", answer)

            logger.info(f"Hoàn tất Pipeline (Non-stream) cho session: {session_id}")

            # 7. Đóng gói và trả về cục kết quả
            return PipelineResult(
                answer=answer,
                sources=sources,
                used_web_search=used_web,
                top_score=top_score
            )

        except Exception as e:
            logger.error(f"Pipeline Non-stream vỡ trận: {e}")
            # Trả về kết quả an toàn để API không bị crash 500
            return PipelineResult(
                answer="Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau.",
                sources=[],
                used_web_search=False,
                top_score=0.0
            )
