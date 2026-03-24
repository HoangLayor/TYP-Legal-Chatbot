"""
app/rag/retriever.py
--------------------
Orchestrate hybrid search pipeline:
Wrapper mỏng quanh HybridSearcher để chuẩn hóa interface cho pipeline.py.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.rag.hybrid_search import HybridSearcher, SearchResult

logger = get_logger(__name__)


class Retriever:
    """Orchestrate retrieval: chạy hybrid search và trả về danh sách kết quả.

    Là interface trung gian giữa ``pipeline.py`` và ``HybridSearcher``.
    Có thể mở rộng để thêm pre/post-processing (query expansion, metadata filter, ...).

    Attributes:
        searcher (HybridSearcher): Underlying hybrid search engine.
    """

    def __init__(self, searcher: HybridSearcher | None = None) -> None:
        """Khởi tạo Retriever.

        Args:
            searcher: HybridSearcher instance. Mặc định tạo mới.
        """
        self.searcher = searcher or HybridSearcher()

    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Lấy top-k documents liên quan nhất với query.

        Args:
            query: Query text của user (đã qua query rewriting nếu có).
            top_k: Số documents trả về. Mặc định 20 (sẽ qua reranker sau).
            filter: Metadata filter tùy chọn (ví dụ lọc theo loại văn bản pháp luật).

        Returns:
            List[SearchResult] đã sort theo RRF score, giới hạn top_k.
        """
        logger.info(f"Retriever nhận lệnh tìm kiếm. Query: '{query}', Top K: {top_k}")
        
        try:
            # TƯƠNG LAI: Nếu bạn muốn làm Query Rewriting (viết lại câu hỏi) 
            # hoặc kiểm tra chính tả, bạn sẽ nhét code xử lý 'query' ở ngay dòng này!
            # rewritten_query = await self._rewrite_query(query)
            
            # Giao phó công việc nặng nhọc cho Đội đặc nhiệm HybridSearcher
            results = await self.searcher.search(
                query=query, 
                top_k=top_k, 
                filter=filter
            )
            
            logger.info(f"Retriever hoàn tất. Lấy về {len(results)} kết quả.")
            return results
            
        except Exception as e:
            # Chốt chặn sinh tử: Nếu DB sập, mạng đứt, code ở đây sẽ hứng hết
            # Không làm sập API của FastAPI, trả về mảng rỗng để luồng Chat vẫn đi tiếp được
            logger.error(f"Lỗi nghiêm trọng tại Retriever khi xử lý query '{query}': {e}")
            return []

    async def retrieve_for_ingestion_check(self, doc_id: str) -> bool:
        """Kiểm tra xem document đã tồn tại trong index chưa (dedup check).

        Args:
            doc_id: ID của document cần kiểm tra.

        Returns:
            True nếu document đã được index, False nếu chưa.
        """
        logger.debug(f"Kiểm tra trùng lặp cho tài liệu có ID: {doc_id}")
        
        try:
            # Truy cập xuyên qua searcher để gọi thẳng vào VectorDB.
            # Lưu ý: Hàm check_exists() này cần được bạn định nghĩa bên trong class VectorDBClient.
            # Nó thường sẽ query DB với điều kiện: tìm xem có bất kỳ chunk nào có metadata.doc_id == doc_id không.
            is_exists = await self.searcher.vector_db.check_exists(doc_id)
            
            if is_exists:
                logger.info(f"Tài liệu '{doc_id}' ĐÃ TỒN TẠI trong Database. Bỏ qua bước Ingestion.")
            else:
                logger.info(f"Tài liệu '{doc_id}' là mới. Tiến hành Ingestion...")
                
            return is_exists
            
        except AttributeError:
            # Nếu trong file vector_db.py bạn quên chưa viết hàm check_exists
            logger.warning(
                "Lớp VectorDBClient chưa có hàm check_exists(doc_id). "
                "Hệ thống mặc định cho phép Ingestion (có rủi ro trùng lặp dữ liệu)."
            )
            return False
            
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra tồn tại cho doc_id '{doc_id}': {e}")
            # Rớt mạng DB lúc check -> Trả về False để chạy tiếp (hoặc bạn có thể raise lỗi tùy logic nghiệp vụ)
            return False