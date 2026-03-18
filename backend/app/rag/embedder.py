"""
app/rag/embedder.py
--------------------
Embedding model wrapper — chuyển text thành vector float.
Hỗ trợ OpenAI Embeddings, với batch processing để tối ưu API calls.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class Embedder:
    """Wrapper cho OpenAI Embeddings API.

    Tự động batch các request để giảm số lần gọi API.
    Normalize vector trước khi trả về (cosine similarity).

    Attributes:
        model (str): Tên embedding model (ví dụ: ``text-embedding-3-large``).
        dimension (int): Số chiều của vector output.
        batch_size (int): Số text tối đa mỗi API call.
    """

    def __init__(
        self,
        model: str | None = None,
        dimension: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        """Khởi tạo Embedder với OpenAI client.

        Args:
            model: Tên embedding model. Mặc định từ config.
            dimension: Số chiều vector. Mặc định từ config.
            batch_size: Kích thước batch. Mặc định từ config.
        """
        self.model = model or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension
        self.batch_size = batch_size or settings.embedding_batch_size
        # TODO: khởi tạo openai.AsyncOpenAI client ở đây

    async def embed_text(self, text: str) -> list[float]:
        """Embed một text string thành vector.

        Args:
            text: Văn bản cần embed. Sẽ được truncate nếu quá dài.

        Returns:
            List[float] có độ dài bằng ``self.dimension``.

        Raises:
            ValueError: Nếu text rỗng.
            openai.APIError: Nếu API call thất bại.
        """
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed danh sách texts theo batch để tối ưu số lần call API.

        Texts được chia thành các batch có kích thước ``self.batch_size``,
        mỗi batch gọi API một lần.

        Args:
            texts: Danh sách văn bản cần embed.

        Returns:
            List tương ứng với embedding của từng text trong ``texts``.
        """
        ...

    def _normalize(self, vector: list[float]) -> list[float]:
        """Normalize vector về unit length (L2 normalization).

        Cần thiết cho cosine similarity tương đương dot product.

        Args:
            vector: Vector gốc.

        Returns:
            Vector đã normalize.
        """
        ...

    def estimate_tokens(self, text: str) -> int:
        """Ước tính số token của text dùng tiktoken.

        Args:
            text: Văn bản cần đếm token.

        Returns:
            Số token ước tính.
        """
        ...


# ── Singleton ─────────────────────────────────────────────────────────────────

_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Trả về singleton Embedder instance.

    Returns:
        Embedder: Instance được tái sử dụng cho toàn bộ ứng dụng.
    """
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
        logger.info(
            "embedder_initialized", model=_embedder.model, dim=_embedder.dimension
        )
    return _embedder
