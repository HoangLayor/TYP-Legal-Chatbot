"""
app/rag/hybrid_search.py
-------------------------
Hybrid Search: kết hợp Dense (ANN vector) và Sparse (BM25) search,
merge kết quả bằng Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.bm25_store import BM25Store, get_bm25_store
from app.db.vector_db import VectorDBClient, get_vector_db
from app.rag.embedder import Embedder, get_embedder

logger = get_logger(__name__)
settings = get_settings()

# Hằng số RRF
RRF_K = 60
"""Hằng số k trong công thức RRF: score = Σ 1 / (k + rank_i)."""


@dataclass
class SearchResult:
    """Kết quả từ hybrid search.

    Attributes:
        id: ID của document/chunk.
        score: RRF score (hoặc dense/sparse score nếu chỉ dùng một nhánh).
        text: Nội dung văn bản của chunk.
        metadata: Metadata đi kèm (nguồn, trang, ...).
        dense_rank: Thứ hạng từ dense search (None nếu không trong top-k dense).
        sparse_rank: Thứ hạng từ sparse search (None nếu không trong top-k sparse).
    """

    id: str
    score: float
    text: str
    metadata: dict[str, Any]
    dense_rank: int | None = None
    sparse_rank: int | None = None


class HybridSearcher:
    """Thực hiện hybrid search kết hợp dense và sparse.

    Chạy cả hai nhánh song song (asyncio.gather) để giảm latency,
    sau đó merge bằng RRF.

    Attributes:
        vector_db (VectorDBClient): Client truy vấn dense ANN.
        bm25_store (BM25Store): Sparse BM25 index.
        embedder (Embedder): Encode query thành vector.
        rrf_k (int): Hằng số k cho công thức RRF.
    """

    def __init__(
        self,
        vector_db: VectorDBClient | None = None,
        bm25_store: BM25Store | None = None,
        embedder: Embedder | None = None,
        rrf_k: int = RRF_K,
    ) -> None:
        """Khởi tạo HybridSearcher với các dependency.

        Args:
            vector_db: Vector DB client. Mặc định dùng singleton từ ``get_vector_db()``.
            bm25_store: BM25 store. Mặc định dùng singleton từ ``get_bm25_store()``.
            embedder: Embedder. Mặc định dùng singleton từ ``get_embedder()``.
            rrf_k: Hằng số k cho RRF. Mặc định 60.
        """
        self.vector_db = vector_db or get_vector_db()
        self.bm25_store = bm25_store or get_bm25_store()
        self.embedder = embedder or get_embedder()
        self.rrf_k = rrf_k

    async def _dense_search(
        self,
        query: str,
        top_k: int,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Nhánh dense search: embed query → ANN lookup.

        Args:
            query: Query text.
            top_k: Số kết quả.
            filter: Metadata filter cho Vector DB.

        Returns:
            List kết quả từ Vector DB, đã có ``rank`` field.
        """
        try:
            # 1. Dịch câu hỏi: Gọi Embedder để biến câu hỏi text thành Vector (mảng float)
            query_vector = await self.embedder.embed_text(query)

            # 2. Tìm kiếm nội bộ: Gửi Vector xuống cơ sở dữ liệu (Vector DB)
            # Giả định self.vector_db.search() trả về danh sách các dictionary:
            # [{"id": "...", "score": 0.85, "text": "...", "metadata": {...}}, ...]
            raw_results = await self.vector_db.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter
            )
            
            '''
            rank_results có dạng:
            [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",  # ID duy nhất của Chunk
                    "score": 0.895,                                # Điểm độ tương đồng Vector (Cosine Similarity)
                    "text": "Điều 15: Người lao động được nghỉ thai sản 6 tháng...", # Nội dung chữ
                    "metadata": {                                  # Thông tin phụ trợ (lấy từ lúc Chunker cắt)
                        "filename": "Luat_Lao_Dong_2019.pdf",
                        "page": 12,
                        "chunk_index": 45
                    }
                },
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "score": 0.752,
                    "text": "Khoản 2: Chế độ thai sản áp dụng cho lao động nữ...",
                    "metadata": {
                        "filename": "Nghi_Dinh_145.pdf",
                        "page": 5,
                        "chunk_index": 12
                    }
                }
                # ... các kết quả khác
            ]
            '''

            # 3. Tiền xử lý cho thuật toán RRF: Đánh số thứ hạng (Rank)
            ranked_results = []
            
            # raw_results mặc định đã được Vector DB sắp xếp từ điểm cao xuống thấp
            for i, res in enumerate(raw_results):
                # Tạo một bản sao của dict để tránh dính tham chiếu bộ nhớ (Side effect)
                processed_res = dict(res)
                
                # Gắn thêm trường "rank" (Thứ hạng 1, 2, 3...)
                # Đây là con số quan trọng nhất để lát nữa nhồi vào công thức toán học RRF
                processed_res["rank"] = i + 1 
                
                ranked_results.append(processed_res)

            return ranked_results

        except Exception as e:
            # Bắt lỗi an toàn: Nếu Vector DB bị sập hoặc Embedder lỗi mạng
            logger.error(f"Lỗi nhánh Dense Search: {e}")
            # Trả về mảng rỗng để hệ thống không sập, lát nữa BM25 (Sparse) sẽ gánh tạ thay!
            return []



    def _sparse_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Nhánh sparse search: BM25 keyword matching.

        Args:
            query: Query text.
            top_k: Số kết quả.

        Returns:
            List kết quả từ BM25Store, đã có ``rank`` field.
        """
        try:
            # 1. Gọi hệ thống lưu trữ BM25 để tìm kiếm từ khóa
            # Khác với Vector DB thường phải gọi qua mạng (API), BM25 thường được
            # load trực tiếp trên RAM (ví dụ: thư viện rank_bm25) nên nó chạy đồng bộ (sync) và cực kỳ nhanh.
            raw_results = self.bm25_store.search(
                query=query, 
                top_k=top_k
            )

            # 2. Tiền xử lý cho thuật toán RRF (Giống hệt nhánh Dense)
            ranked_results = []
            
            # Kết quả từ BM25 mặc định đã được sắp xếp theo điểm số BM25 giảm dần
            for i, res in enumerate(raw_results):
                # Chuyển đổi an toàn thành dictionary
                processed_res = dict(res)
                
                # Gắn thêm trường "rank" (Thứ hạng 1, 2, 3...)
                # Điểm BM25 thô thường là những con số rất kỳ cục (ví dụ: 12.5, 45.2, 0.8), 
                # nên ta chỉ quan tâm đến thứ hạng (rank) của nó thôi.
                processed_res["rank"] = i + 1 
                
                ranked_results.append(processed_res)

            return ranked_results

        except Exception as e:
            # Bắt lỗi an toàn: Nếu file index BM25 bị hỏng hoặc load lỗi
            logger.error(f"Lỗi nhánh Sparse Search (BM25): {e}")
            # Trả về mảng rỗng. Nhánh Dense (Vector) vẫn sẽ gánh team!
            return []

    def _rrf_merge(
        self,
        dense_results: list[dict[str, Any]],
        sparse_results: list[dict[str, Any]],
    ) -> list[SearchResult]:
        """Merge dense và sparse results bằng Reciprocal Rank Fusion.

        Công thức: RRF_score(doc) = Σ 1 / (k + rank_i)
        với k = ``self.rrf_k`` và rank_i là thứ hạng trong mỗi nhánh.

        Docs không có trong một nhánh được bỏ qua trong nhánh đó.

        Args:
            dense_results: Kết quả từ dense search (đã có ``rank``).
            sparse_results: Kết quả từ sparse search (đã có ``rank``).

        Returns:
            List[SearchResult] đã sort theo RRF score giảm dần.
        """
        # Dùng một dictionary tạm để gộp điểm theo ID của tài liệu
        # Cấu trúc: {doc_id: {"score": float, "text": str, "metadata": dict, ...}}
        merged_docs: dict[str, dict[str, Any]] = {}

        # 1. Tính điểm RRF cho các tài liệu từ nhánh Dense (Vector)
        for res in dense_results:
            doc_id = res["id"]
            rank = res["rank"]
            
            # Công thức cốt lõi: 1 / (60 + thứ_hạng)
            rrf_score = 1.0 / (self.rrf_k + rank)
            
            merged_docs[doc_id] = {
                "score": rrf_score,
                "text": res.get("metadata", {}).get("text", ""),
                "metadata": res.get("metadata", {}),
                "dense_rank": rank,
                "sparse_rank": None  # Khởi tạo mặc định là None vì chưa biết BM25 có tìm thấy không
            }

        # 2. Tính điểm RRF cho các tài liệu từ nhánh Sparse (BM25)
        for res in sparse_results:
            doc_id = res["id"]
            rank = res["rank"]
            rrf_score = 1.0 / (self.rrf_k + rank)

            if doc_id in merged_docs:
                # TRÚNG MÁNH: Nếu tài liệu đã có trong danh sách Dense, ta CỘNG DỒN điểm RRF!
                merged_docs[doc_id]["score"] += rrf_score
                # Cập nhật thêm thứ hạng bên nhánh Sparse
                merged_docs[doc_id]["sparse_rank"] = rank
            else:
                # Nếu tài liệu chỉ được tìm thấy bởi BM25 (chưa có trong dictionary)
                merged_docs[doc_id] = {
                    "score": rrf_score,
                    "text": res["text"],
                    "metadata": res.get("metadata", {}),
                    "dense_rank": None, # Không có trong Dense
                    "sparse_rank": rank
                }

        # 3. Đóng gói lại thành chuẩn SearchResult mà hệ thống mong đợi
        final_results = []
        for doc_id, data in merged_docs.items():
            final_results.append(
                SearchResult(
                    id=doc_id,
                    score=data["score"], # Điểm bây giờ là tổng RRF siêu chuẩn
                    text=data["text"],
                    metadata=data["metadata"],
                    dense_rank=data["dense_rank"],
                    sparse_rank=data["sparse_rank"]
                )
            )

        # 4. Sắp xếp danh sách cuối cùng theo điểm RRF từ cao xuống thấp
        final_results.sort(key=lambda x: x.score, reverse=True)

        return final_results

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filter: dict | None = None,
    ) -> list[SearchResult]:
        """Thực hiện hybrid search tổng hợp.

        Chạy dense và sparse song song, merge bằng RRF.

        Args:
            query: Query text của user.
            top_k: Số kết quả trả về sau RRF.
            filter: Metadata filter (chỉ áp dụng cho dense search).

        Returns:
            List[SearchResult] sorted theo RRF score giảm dần,
            giới hạn ``top_k`` phần tử.
        """
        logger.info(f"Bắt đầu Hybrid Search cho truy vấn: '{query}'")

        # 1. Khởi tạo 2 luồng công việc (Tasks)
        # Nhánh 1: Gọi thẳng vì nó đã là hàm async
        dense_task = self._dense_search(query=query, top_k=top_k, filter=filter)
        
        # Nhánh 2: Đẩy hàm đồng bộ (sync) sang một luồng (thread) khác để không khóa Event Loop
        sparse_task = asyncio.to_thread(self._sparse_search, query, top_k)

        # 2. Phát súng lệnh: Cho 2 nhánh chạy ĐỒNG THỜI và đợi tụi nó mang kết quả về
        # Giả sử Dense mất 200ms, Sparse mất 50ms, thì tổng thời gian chờ ở dòng này chỉ là 200ms
        # (thay vì 250ms nếu chạy tuần tự). Rất tối ưu!
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)

        logger.debug(
            f"Số lượng tìm thấy: Dense ({len(dense_results)}), Sparse ({len(sparse_results)})"
        )

        # 3. Chuyển hồ sơ cho "Thẩm phán" RRF gộp điểm và xếp hạng lại
        merged_results = self._rrf_merge(
            dense_results=dense_results,
            sparse_results=sparse_results
        )

        # 4. Trả về đúng số lượng top_k xuất sắc nhất mà hệ thống yêu cầu
        final_results = merged_results[:top_k]
        
        logger.info(f"Hybrid Search hoàn tất. Trả về {len(final_results)} tài liệu.")
        return final_results


if __name__ == "__main__":
    import asyncio
    import pprint
    async def main():
        searcher = HybridSearcher()
        # tmp = await searcher._dense_search(query = "Luật lao động là gì?", top_k = 3)
        tmp = searcher._sparse_search(query = "Luật lao động là gì?", top_k = 3)
        pprint.pprint(tmp[0])
    asyncio.run(main())
