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
        ...

    def _format_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Cắt history để vừa token limit, giữ lại N messages gần nhất.

        Args:
            history: Danh sách messages ``{"role": str, "content": str}``.

        Returns:
            History đã trim, vẫn giữ thứ tự chronological.
        """
        ...

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
        ...


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
        ...

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
        ...


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
