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

import asyncio
import tiktoken
import math
from sentence_transformers import SentenceTransformer
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
        # self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.encoder = SentenceTransformer(self.model)

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
        if not text or not text.strip():
            raise ValueError("Văn bản cần embed không được để trống.")

        #Tiền xử lý --> Mô hình hiểu context tốt hơn
        clean_text = text.replace("\n", " ")

        try:
            '''
            # đây là của openAI
            response = await self.client.embeddings.create(
                input=[clean_text],
                model=self.model,
                dimensions=self.dimension 
            )
            vector = response.data[0].embedding
            normalized_vector = self._normalize(vector)
            return normalized_vector
            '''
            # Dùng asyncio.to_thread để không làm block event loop của ứng dụng
            # Tham số normalize_embeddings=True thay thế cho hàm _normalize thủ công
            vector = await asyncio.to_thread(
                self.encoder.encode, 
                clean_text, 
                normalize_embeddings=True
            )
            return vector.tolist()

        except Exception as e:
            logger.error(f"Lỗi khi tính toán embedding với {self.model}: {e}")
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed danh sách texts theo batch để tối ưu số lần call API.

        Texts được chia thành các batch có kích thước ``self.batch_size``,
        mỗi batch gọi API một lần.

        Args:
            texts: Danh sách văn bản cần embed.

        Returns:
            List tương ứng với embedding của từng text trong ``texts``.
        """
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        
        # Vòng lặp cắt danh sách lớn thành các batch nhỏ dựa trên batch_size
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            clean_texts = [text.replace("\n", " ") for text in batch_texts]
            
            try:
                '''
                # Gửi toàn bộ lô này (input là một list) lên OpenAI trong 1 lần gọi
                response = await self.client.embeddings.create(
                    input=clean_texts,
                    model=self.model,
                    dimensions=self.dimension
                )
                
                # OpenAI sẽ trả về danh sách vector theo đúng thứ tự mảng input
                for data in response.data:
                    vector = data.embedding
                    normalized_vector = self._normalize(vector)

                    all_embeddings.append(normalized_vector)
                '''
                vectors = await asyncio.to_thread(
                    self.encoder.encode,
                    clean_texts,
                    batch_size=self.batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=True
                )
                return vectors.tolist()
                    
            except Exception as e:
                logger.error(f"Lỗi khi embed batch với {self.model}: {e}")
                raise
                
        return all_embeddings

    # def _normalize(self, vector: list[float]) -> list[float]:
    #     """Normalize vector về unit length (L2 normalization).

    #     Cần thiết cho cosine similarity tương đương dot product.

    #     Args:
    #         vector: Vector gốc.

    #     Returns:
    #         Vector đã normalize.
    #     """
    #     # 1. Tính độ dài (magnitude) của vector dựa trên công thức L2 Norm
    #     magnitude = math.sqrt(sum(x * x for x in vector))
        
        if magnitude == 0:
            return vector
        return [x / magnitude for x in vector]

    # def estimate_tokens(self, text: str) -> int:
    #     """Ước tính số token của text dùng tiktoken.

    #     Args:
    #         text: Văn bản cần đếm token.

    #     Returns:
    #         Số token ước tính.
    #     """
    #     if not text:
    #         return 0
            
    #     try:
    #         # Lấy bộ từ điển (encoding) tương ứng với model bạn đang dùng.
    #         # Đa số các model đời mới (GPT-4, text-embedding-3) đều dùng bộ "cl100k_base"
    #         encoding = tiktoken.encoding_for_model(self.model)
    #     except KeyError:
    #         # Nếu truyền sai tên model hoặc model quá mới chưa cập nhật,
    #         # hệ thống sẽ fallback (lùi về) dùng bộ đếm mặc định chuẩn nhất hiện nay
    #         encoding = tiktoken.get_encoding("cl100k_base")
            
    #     # Mã hóa đoạn text thành một mảng các con số (mỗi số là ID của 1 token)
    #     # Ví dụ: [1234, 567, 8910]
    #     tokens = encoding.encode(text)
        
    #     # Đếm số lượng phần tử trong mảng chính là số token
    #     return len(tokens)

    def estimate_tokens(self, text: str) -> int:
        """Ước tính số token của text dựa trên Tokenizer của BGE-M3."""
        if not text:
            return 0
            
        try:
            # Sử dụng tokenizer chuẩn đi kèm với mô hình
            tokens = self.encoder.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Lỗi khi đếm token: {e}")
            return 0
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
