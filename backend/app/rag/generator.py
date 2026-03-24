"""
app/rag/generator.py
---------------------
LLM generation: xây dựng prompt và gọi LLM để sinh câu trả lời.
Hỗ trợ streaming response qua SSE và cả non-streaming cho internal use.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.reranker import RankedResult
from app.rag.web_search import WebSearchResult

from openai import AsyncOpenAI
from typing import AsyncIterator

logger = get_logger(__name__)
settings = get_settings()

# ── Prompt template ───────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """\
Bạn là trợ lý pháp lý thông minh, chuyên tư vấn về luật pháp Việt Nam.
Hãy trả lời dựa trên các tài liệu được cung cấp dưới đây.
Nếu thông tin không có trong tài liệu, hãy thành thật nói rõ.
Trả lời bằng tiếng Việt, ngắn gọn, chính xác và có trích dẫn nguồn.

--- TÀI LIỆU THAM KHẢO ---
{context}
--- KẾT THÚC TÀI LIỆU ---
"""


class PromptBuilder:
    """Xây dựng prompt từ query, context chunks và chat history.

    Attributes:
        max_context_tokens (int): Giới hạn token cho phần context.
    """

    def __init__(self, max_context_tokens: int = 3000) -> None:
        """Khởi tạo PromptBuilder.

        Args:
            max_context_tokens: Số token tối đa dành cho context (chunks + web results).
        """
        self.max_context_tokens = max_context_tokens

    def _format_chunk(self, result: RankedResult, index: int) -> str:
        """Định dạng một ranked chunk thành string để nhúng vào prompt.

        Args:
            result: Chunk đã rerank.
            index: Số thứ tự (1-indexed) để LLM dễ trích dẫn.

        Returns:
            String dạng ``[{index}] {source} — {text}``.
        """
        # Trích xuất nguồn từ metadata (ưu tiên filename, sau đó đến source nếu có)
        source = result.metadata.get("filename") or result.metadata.get("source") or "Tài liệu nội bộ"
        
        # Nếu có thông tin trang (page), ghép thêm vào để trích dẫn chi tiết hơn
        page = result.metadata.get("page")
        if page:
            source += f" (Trang {page})"
            
        clean_text = result.text.strip()
        return f"[{index}] Nguồn: {source} — {clean_text}"
    
    
    def _format_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Cắt history để vừa token limit, giữ lại N messages gần nhất.

        Args:
            history: Danh sách messages ``{"role": str, "content": str}``.

        Returns:
            History đã trim, vẫn giữ thứ tự chronological.
        """
        if not history:
            return []

        max_messages = 10 # 10 tin nhắt ~ 5 lần hỏi - đáp gàn nhất
        
        # Cắt lấy max_messages cuối cùng (ví dụ: lấy từ cuối ngược lên trên)
        trimmed_history = history[-max_messages:]

        # --- XỬ LÝ QUAN TRỌNG ĐỂ TRÁNH LỖI API ---
        # Rất nhiều model (đặc biệt là Claude/Anthropic) có quy định khắt khe: 
        # Lịch sử hội thoại PHẢI bắt đầu bằng tin nhắn của "user", không được bắt đầu bằng "assistant".
        # Nếu sau khi cắt mà tin nhắn đầu tiên lại rơi vào lượt của bot, ta bỏ luôn tin nhắn đó.
        if trimmed_history and trimmed_history[0].get("role") == "assistant":
            trimmed_history = trimmed_history[1:]
        return trimmed_history
    

    def build_messages(
        self,
        query: str,
        ranked_results: list[RankedResult],
        history: list[dict[str, str]],
        web_results: list[WebSearchResult] | None = None,
    ) -> list[dict[str, str]]:
        """Tạo danh sách messages gửi cho LLM.

        Cấu trúc:
        1. ``system``: System prompt kèm context chunks (+ web nếu có).
        2. ``user/assistant`` (N-1): Chat history đã trim.
        3. ``user``: Query hiện tại.

        Args:
            query: Query mới nhất của user.
            ranked_results: Chunks sau reranking.
            history: Lịch sử hội thoại từ MongoDB.
            web_results: Kết quả Tavily nếu có.

        Returns:
            List dict ``[{"role": str, "content": str}]`` sẵn cho LLM API.
        """
        context_parts = []
        index = 1 
        # Xử lý tài liệu lấy từ reranker.py
        if ranked_results:
            for result in ranked_results:
                context_parts.append(self._format_chunk(result, index))
                index += 1
                
        # Xử lý tài liệu từ Internet (nếu có)
        if web_results:
            # Thêm một vạch ngăn cách nhỏ để AI phân biệt được đâu là luật nội bộ, đâu là web
            context_parts.append("\n--- KẾT QUẢ TÌM KIẾM INTERNET ---")
            for web in web_results:
                clean_content = web.content.strip()
                context_parts.append(f"Web: {web.title} ({web.url}) — {clean_content}")
                
        # Gộp tất cả thành một chuỗi văn bản lớn
        context_str = "\n".join(context_parts)
        if not context_str.strip():
            context_str = "Hệ thống không tìm thấy tài liệu tham khảo nào phù hợp với câu hỏi này."
            
        #Lắp ráp System Prompt
        system_content = SYSTEM_PROMPT_TEMPLATE.format(context=context_str)
        messages = [{"role": "system", "content": system_content}]
        
        # Nối lịch sử trò chuyện (đã được cắt gọt an toàn)
        trimmed_history = self._format_history(history)
        messages.extend(trimmed_history)
        
        messages.append({"role": "user", "content": query})
        return messages


class Generator:
    """Gọi LLM để sinh câu trả lời, hỗ trợ streaming.

    Hỗ trợ OpenAI và Anthropic (chọn qua ``LLM_PROVIDER``).

    Attributes:
        provider (str): ``"openai"`` hoặc ``"anthropic"``.
        model (str): Tên model LLM.
        prompt_builder (PromptBuilder): Builder tạo messages.
    """

    def __init__(self) -> None:
        """Khởi tạo Generator với LLM client phù hợp.

        Client được chọn dựa trên ``LLM_PROVIDER`` trong config.
        """
        self.provider = settings.llm_provider
        self.model = settings.openai_model
        self.prompt_builder = PromptBuilder()
        # TODO: khởi tạo openai.AsyncOpenAI hoặc anthropic.AsyncAnthropic
        # Khởi tạo OpenAI Client bất đồng bộ
        if self.provider == "openai":
            self.client = AsyncOpenAI(api_key=settings.openai_api_key) #AsyncAnthropic
        else:
            raise ValueError(f"Chưa hỗ trợ provider: {self.provider}")
        
    async def generate_stream(
        self,
        query: str,
        ranked_results: list[RankedResult],
        history: list[dict[str, str]],
        web_results: list[WebSearchResult] | None = None,
    ) -> AsyncIterator[str]:
        """Sinh câu trả lời dạng streaming (chunk by chunk).

        Yield từng text chunk từ LLM để gửi qua SSE ngay khi có.

        Args:
            query: Query của user.
            ranked_results: Chunk context sau reranking.
            history: Chat history từ MongoDB.
            web_results: Web search results nếu có.

        Yields:
            str: Từng text chunk từ LLM response.

        Raises:
            openai.APIError | anthropic.APIError: Nếu LLM call thất bại.
        """
        # 1. Gọi "Thợ lắp ráp" để đóng gói toàn bộ dữ liệu thành kịch bản chuẩn
        messages = self.prompt_builder.build_messages(
            query=query,
            ranked_results=ranked_results,
            history=history,
            web_results=web_results
        )

        try:
            # 2. Gọi API của OpenAI với cờ stream=True (Đây là chìa khóa quan trọng nhất)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2, # Để temperature thấp (0.2) giúp AI trả lời pháp lý nghiêm túc, không bay bổng
                stream=True      # Bật chế độ trả về từng chữ
            )

            # 3. Hứng từng mảnh chữ (chunk) rớt xuống từ OpenAI và ném thẳng ra ngoài
            async for chunk in response:
                # OpenAI trả về một object phức tạp, ta chỉ móc lấy phần 'content' (chữ)
                content = chunk.choices[0].delta.content
                
                # Nếu có chữ (không phải None hay chuỗi rỗng), ta yield nó ra
                if content is not None:
                    yield content

        except openai.APIError as e:
            logger.error(f"Lỗi API từ OpenAI khi generate stream: {e}")
            # Nếu lỗi, yield ra một câu xin lỗi mượt mà để giao diện không bị treo
            yield "\n\n[Hệ thống] Xin lỗi, máy chủ AI đang gặp sự cố. Vui lòng thử lại sau."
            raise

    async def generate(
        self,
        query: str,
        ranked_results: list[RankedResult],
        history: list[dict[str, str]],
        web_results: list[WebSearchResult] | None = None,
    ) -> str:
        """Sinh câu trả lời đầy đủ (non-streaming).

        Dùng cho internal testing hoặc cases không cần stream.

        Args:
            query: Query của user.
            ranked_results: Chunk context.
            history: Chat history.
            web_results: Web results nếu có.

        Returns:
            Toàn bộ response text từ LLM.
        """
        messages = self.prompt_builder.build_messages(
            query=query, 
            ranked_results=ranked_results, 
            history=history, 
            web_results=web_results
        )

        try:
            # Không có stream=True
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2
            )
            # Trả về toàn bộ cục chữ một lần
            return response.choices[0].message.content or ""

        except openai.APIError as e:
            logger.error(f"Lỗi generate non-stream: {e}")
            raise


# ── Singleton ─────────────────────────────────────────────────────────────────

_generator: Generator | None = None


def get_generator() -> Generator:
    """Trả về singleton Generator instance.

    Returns:
        Generator: Instance được tái sử dụng.
    """
    global _generator
    if _generator is None:
        _generator = Generator()
        logger.info("generator_initialized", provider=_generator.provider)
    return _generator
