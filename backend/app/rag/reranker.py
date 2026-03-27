"""
app/rag/reranker.py
--------------------
Cross-encoder reranking để tăng độ chính xác sau hybrid search.
Hỗ trợ Cohere Rerank API và BAAI/bge-reranker-v2-m3 (local).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.hybrid_search import SearchResult

import cohere
# from cohere.errors import CohereAPIError
import asyncio
from sentence_transformers import CrossEncoder

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class RankedResult:
    """Kết quả sau khi rerank.

    Attributes:
        id: Chunk ID.
        rerank_score: Score từ cross-encoder (0–1, càng cao càng liên quan).
        text: Nội dung chunk.
        metadata: Metadata của chunk.
        original_rank: Thứ hạng trước khi rerank (từ RRF).
    """

    id: str
    rerank_score: float
    text: str
    metadata: dict[str, Any]
    original_rank: int


# ── Abstract interface ────────────────────────────────────────────────────────


class BaseReranker(ABC):
    """Abstract base class cho tất cả reranker implementations."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],   
        top_n: int,
    ) -> list[RankedResult]:
        """Rerank danh sách SearchResult theo relevance với query.

        Args:
            query: Query text gốc của user.
            results: Kết quả từ hybrid search cần rerank.
            top_n: Số kết quả giữ lại sau rerank.

        Returns:
            List[RankedResult] sorted theo rerank_score giảm dần,
            giới hạn top_n phần tử.
        """
        ...


# ── Cohere Reranker ───────────────────────────────────────────────────────────


class CohereReranker(BaseReranker):
    """Reranker sử dụng Cohere Rerank API.

    Model mặc định: ``rerank-multilingual-v3.0`` (hỗ trợ tiếng Việt).

    Attributes:
        client: Cohere AsyncClient.
        model (str): Tên model rerank của Cohere.
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Khởi tạo Cohere client.

        Args:
            api_key: Cohere API key. Mặc định từ config.
        """
        self.api_key = api_key or settings.cohere_api_key
        if not self.api_key:
            raise ValueError("Chưa cấu hình COHERE_API_KEY")
        self.model = "rerank-multilingual-v3.0"
        # Khởi tạo Client bất đồng bộ (Async) để không làm nghẽn FastAPI
        self.client = cohere.AsyncClient(self.api_key)
        
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Gọi Cohere Rerank API để score lại kết quả.

        Args:
            query: Query text.
            results: Danh sách SearchResult cần rerank (tối đa RERANK_TOP_K).
            top_n: Số kết quả giữ lại.

        Returns:
            List[RankedResult] sorted theo Cohere score.

        Raises:
            cohere.CohereAPIError: Nếu API call thất bại.
        """
        if not results:
            return []

        # 2. Chuẩn bị dữ liệu gửi lên Cohere
        # Cohere API chỉ cần một mảng chứa toàn chữ (text) của các tài liệu
        documents = [res.text for res in results]

        try:
            # 3. Gọi API chấm điểm lại
            response = await self.client.rerank(
                query=query,
                documents=documents,
                model=self.model,
                top_n=top_n  
            )

            ranked_results: list[RankedResult] = []

            # 4. Ráp kết quả trả về với metadata gốc ban đầu
            # response.results tự động được Cohere sắp xếp từ điểm cao xuống điểm thấp
            # COhere trả về index của các documents sau khi rerank
            for item in response.results:
                # Lấy ra vị trí (index) của tài liệu trong mảng gốc ban đầu
                original_index = item.index
                # Trích xuất đoạn tài liệu gốc tương ứng
                original_res = results[original_index]
                
                # Tạo bản ghi RankedResult mới với điểm số của Cohere
                ranked_res = RankedResult(
                    id=original_res.id,
                    rerank_score=item.relevance_score, # Điểm mới từ Cohere (0 -> 1)
                    text=original_res.text,
                    metadata=original_res.metadata,
                    original_rank=original_index + 1   # Thứ hạng cũ (ví dụ: ngày xưa xếp thứ 5)
                )
                ranked_results.append(ranked_res)

            return ranked_results

        except Exception as e:
            logger.error(f"Lỗi Cohere Rerank API: {e}")
            # Nếu API lỗi (ví dụ hết tiền, nghẽn mạng), thay vì sập app,
            # ta fallback (lùi về) dùng luôn Passthrough (lấy top_n kết quả cũ)
            logger.warning("Fallback về kết quả Hybrid Search gốc vì Reranker lỗi.")
            return self._fallback_rerank(results, top_n)
            
    def _fallback_rerank(self, results: list[SearchResult], top_n: int) -> list[RankedResult]:
        """Hàm nội bộ: Cứu cánh khi API Cohere bị lỗi"""
        ranked_results = []
        for i, res in enumerate(results[:top_n]):
            ranked_results.append(RankedResult(
                id=res.id,
                rerank_score=res.score, # Trả về điểm RRF cũ
                text=res.text,
                metadata=res.metadata,
                original_rank=i + 1
            ))
        return ranked_results


# ── BGE Reranker (local) ──────────────────────────────────────────────────────


class BGEReranker(BaseReranker):
    """Reranker sử dụng BAAI/bge-reranker-v2-m3 chạy local.

    Không cần API key, nhưng cần GPU hoặc CPU đủ mạnh.
    Model được load lần đầu và giữ trong memory.

    Attributes:
        model_name (str): HuggingFace model ID.
        tokenizer: HuggingFace tokenizer.
        model: Cross-encoder model.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """Load BGE reranker model từ HuggingFace Hub.

        Args:
            model_name: Model ID. Mặc định ``BAAI/bge-reranker-v2-m3`` từ config.
        """
        self.model_name = model_name or settings.bge_reranker_model
        logger.info(f"Đang tải mô hình Reranker cục bộ: {self.model_name}...")
        # Tải mô hình vào RAM/VRAM. 
        # CrossEncoder sẽ tự động nhận diện nếu máy bạn có GPU (CUDA) để tăng tốc
        # max_length=512: Giới hạn số token tối đa cho mỗi cặp (query + chunk) để tránh hết RAM
        self.model = CrossEncoder(self.model_name, max_length=512)
        
        logger.info("Tải mô hình Reranker thành công!")
        
        
    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Score từng cặp (query, chunk) bằng BGE cross-encoder.

        Chạy trong executor để không block event loop.

        Args:
            query: Query text.
            results: Danh sách SearchResult.
            top_n: Số kết quả giữ lại.

        Returns:
            List[RankedResult] sorted theo BGE score.
        """
        if not results:
            return []

        # 1. Ghép cặp (Pairing): Cross-encoder yêu cầu đầu vào là một mảng các cặp [Câu hỏi, Tài liệu]
        # Ví dụ: [ ["Luật lao động là gì?", "Tài liệu A..."], ["Luật lao động là gì?", "Tài liệu B..."] ]
        sentence_pairs = [[query, res.text] for res in results]

        # 2. Chấm điểm (Inference) NHƯNG phải đẩy ra một luồng (thread) riêng
        # self.model.predict là một hàm chạy đồng bộ (chạy rất nặng toán học).
        # Nếu không dùng asyncio.to_thread, nó sẽ đóng băng toàn bộ server FastAPI của bạn!
        scores = await asyncio.to_thread(self.model.predict, sentence_pairs)

        ranked_results: list[RankedResult] = []

        # 3. Ráp điểm số trả về với tài liệu gốc
        # Điểm số trả về là một mảng Numpy array (vd: [0.12, 0.98, -0.45]), 
        # vị trí của điểm tương ứng đúng với vị trí của tài liệu lúc truyền vào
        for i, (res, score) in enumerate(zip(results, scores)):
            ranked_res = RankedResult(
                id=res.id,
                rerank_score=float(score), # Ép kiểu về float chuẩn của Python
                text=res.text,
                metadata=res.metadata,
                original_rank=i + 1
            )
            ranked_results.append(ranked_res)

        # 4. Sắp xếp thủ công (Vì chạy Local nên ta phải tự xếp hạng từ cao xuống thấp)
        ranked_results.sort(key=lambda x: x.rerank_score, reverse=True)

        # 5. Cắt lấy số lượng top_n mong muốn
        return ranked_results[:top_n]


# ── No-op Reranker ────────────────────────────────────────────────────────────


class PassthroughReranker(BaseReranker):
    """Reranker giả — chỉ convert SearchResult → RankedResult không đổi thứ tự.

    Dùng khi ``RERANKER_PROVIDER=none`` hoặc để test.
    """

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int,
    ) -> list[RankedResult]:
        """Convert SearchResult thành RankedResult, giữ nguyên thứ tự RRF.

        Args:
            query: Không dùng.
            results: Danh sách SearchResult.
            top_n: Số phần tử giữ lại.

        Returns:
            List[RankedResult] với score = RRF score gốc, giới hạn top_n.
        """
        if not results:
            return []

        ranked_results: list[RankedResult] = []
        
        # Duyệt qua danh sách kết quả (chỉ lấy đúng số lượng top_n)
        for i, res in enumerate(results[:top_n]):
            # Tạo object RankedResult từ SearchResult
            # Vì đây là "giả cầy", ta lấy luôn điểm RRF (hoặc điểm vector) làm rerank_score
            ranked_res = RankedResult(
                id=res.id,
                rerank_score=res.score, # Dùng luôn điểm cũ
                text=res.text,
                metadata=res.metadata,
                original_rank=i + 1     # Lưu lại thứ hạng ban đầu (1, 2, 3...)
            )
            ranked_results.append(ranked_res)

        return ranked_results


# ── Factory ───────────────────────────────────────────────────────────────────

_reranker: BaseReranker | None = None


def get_reranker() -> BaseReranker:
    """Factory — trả về reranker phù hợp với config.

    Singleton: chỉ khởi tạo một lần.

    Returns:
        BaseReranker: Cohere, BGE hoặc Passthrough reranker.

    Raises:
        ValueError: Nếu ``RERANKER_PROVIDER`` không hợp lệ.
    """
    global _reranker
    if _reranker is not None:
        return _reranker

    provider = settings.reranker_provider
    logger.info("reranker_init", provider=provider)

    if provider == "cohere":
        _reranker = CohereReranker()
    elif provider == "bge":
        _reranker = BGEReranker()
    elif provider == "none":
        _reranker = PassthroughReranker()
    else:
        raise ValueError(f"Unsupported reranker provider: {provider}")

    return _reranker
