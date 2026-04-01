"""
app/db/vector_db.py
--------------------
Factory và abstract interface cho Vector Database.
Hỗ trợ Pinecone, Weaviate và Qdrant.
Chọn provider qua biến môi trường ``VECTOR_DB_PROVIDER``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import qdrant_client
from qdrant_client.models import PointStruct, PointIdsList, Filter, FieldCondition, MatchValue

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ── Abstract interface ────────────────────────────────────────────────────────


class VectorDBClient(ABC):
    """Abstract base class cho tất cả Vector DB clients."""

    @abstractmethod
    async def upsert(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Upsert danh sách vector vào index.

        Args:
            vectors: List dict gồm ``id``, ``values`` (embedding), ``metadata``.

        Returns:
            Dict chứa kết quả upsert (ví dụ: ``{"upserted_count": 10}``).
        """
        ...

    @abstractmethod
    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Truy vấn ANN (Approximate Nearest Neighbor) theo vector.

        Args:
            vector: Query embedding vector.
            top_k: Số kết quả trả về.
            filter: Metadata filter (tuỳ provider).

        Returns:
            List dict kết quả, mỗi phần tử gồm ``id``, ``score``, ``metadata``.
        """
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Xoá các vector theo danh sách ID.

        Args:
            ids: Danh sách ID cần xoá.
        """
        ...


    @abstractmethod
    async def check_exists(self, doc_id: str) -> bool:
        """Kiểm tra xem một file/document đã được index vào Qdrant chưa.
        Dựa vào field 'source_id' lưu trong metadata.
        """
        ...


# ── Pinecone ──────────────────────────────────────────────────────────────────


class PineconeClient(VectorDBClient):
    """Vector DB client sử dụng Pinecone serverless."""

    def __init__(self) -> None:
        """Khởi tạo Pinecone client và kết nối tới index."""
        ...

    async def upsert(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Upsert vectors vào Pinecone index.

        Args:
            vectors: List ``{"id": str, "values": list[float], "metadata": dict}``.

        Returns:
            ``{"upserted_count": int}``
        """
        ...

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Truy vấn Pinecone ANN.

        Args:
            vector: Embedding của query.
            top_k: Số kết quả tối đa.
            filter: Pinecone metadata filter dict.

        Returns:
            List ``{"id": str, "score": float, "metadata": dict}``.
        """
        ...

    async def delete(self, ids: list[str]) -> None:
        """Xoá vectors khỏi Pinecone index theo ID.

        Args:
            ids: Danh sách vector ID.
        """
        ...

    async def check_exists(self, doc_id: str) -> bool:
        """Kiểm tra xem một file/document đã được index vào Qdrant chưa.
        Dựa vào field 'source_id' lưu trong metadata.
        """
        ...

# ── Weaviate ──────────────────────────────────────────────────────────────────


class WeaviateClient(VectorDBClient):
    """Vector DB client sử dụng Weaviate."""

    def __init__(self) -> None:
        """Khởi tạo Weaviate client và đảm bảo class schema tồn tại."""
        ...

    async def upsert(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Upsert objects vào Weaviate class.

        Args:
            vectors: List ``{"id": str, "values": list[float], "metadata": dict}``.

        Returns:
            ``{"upserted_count": int}``
        """
        ...

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Truy vấn nearVector trong Weaviate.

        Args:
            vector: Embedding của query.
            top_k: Số kết quả.
            filter: Where filter của Weaviate GraphQL.

        Returns:
            List ``{"id": str, "score": float, "metadata": dict}``.
        """
        ...

    async def delete(self, ids: list[str]) -> None:
        """Xoá objects khỏi Weaviate theo UUID.

        Args:
            ids: Danh sách UUID string.
        """
        ...

    async def check_exists(self, doc_id: str) -> bool:
        """Kiểm tra xem một file/document đã được index vào Qdrant chưa.
        Dựa vào field 'source_id' lưu trong metadata.
        """
        ...

# ── Qdrant ────────────────────────────────────────────────────────────────────


class QdrantClient(VectorDBClient):
    """Vector DB client sử dụng Qdrant."""

    def __init__(self) -> None:
        """Khởi tạo Qdrant client và tạo collection nếu chưa có."""
        """Khởi tạo Qdrant client."""
        # Đọc cấu hình từ settings (bạn cần thêm các biến này vào file config của bạn)
        # Nếu url là ":memory:", Qdrant sẽ chạy trực tiếp trên RAM (tiện cho test)
        self.url = getattr(settings, "qdrant_url", "http://localhost:6333")
        self.api_key = getattr(settings, "qdrant_api_key", None)
        self.collection_name = getattr(settings, "qdrant_collection_name", "legal_chatbot_collection")
        
        # Sử dụng AsyncQdrantClient để tương thích với các hàm async (bất đồng bộ)
        self.client = qdrant_client.AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
        )
        # print(self.client.get_collections())
        logger.info(f"Đã khởi tạo kết nối Async Qdrant tới collection: {self.collection_name}")

    async def upsert(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Upsert points vào Qdrant collection.

        Args:
            vectors: List ``{"id": str, "values": list[float], "metadata": dict}``.

        Returns:
            ``{"upserted_count": int}``
        """
        if not vectors:
            return {"upserted_count": 0}

        # Qdrant sử dụng khái niệm PointStruct để lưu trữ 1 vector 
        points = [
            PointStruct(
                id=v["id"],               # ID của chunk (chuỗi UUID hoặc số nguyên)
                vector=v["values"],       # Mảng float (embedding)
                payload=v.get("metadata", {}) # Metadata (ID luật, text gốc,...)
            )
            for v in vectors
        ]

        # Đẩy dữ liệu lên Qdrant
        operation_info = await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"Đã upsert {len(points)} vectors vào Qdrant. Trạng thái: {operation_info.status}")
        return {"upserted_count": len(points), "status": operation_info.status}

    async def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Truy vấn nearest vectors trong Qdrant.

        Args:
            vector: Query embedding.
            top_k: Số kết quả.
            filter: Qdrant Filter object.

        Returns:
            List ``{"id": str, "score": float, "metadata": dict}``.
        """
        # Đã cập nhật sang API mới nhất của Qdrant (query_points)
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=vector,          # Chú ý: Tên tham số đổi từ query_vector thành query
            limit=top_k,
            query_filter=filter,                     # type: ignore
            with_payload=True, 
        )

        # Chuyển đổi định dạng kết quả của Qdrant về chuẩn chung của Interface
        results = [
            {
                "id": str(hit.id),
                "score": hit.score,
                "metadata": hit.payload or {}
            }
            for hit in response.points  # Kết quả giờ được bọc bên trong thuộc tính .points
        ]
        return results

    async def delete(self, ids: list[str]) -> None:
        """Xoá points khỏi Qdrant theo ID.

        Args:
            ids: Danh sách point ID.
        """
        if not ids:
            return

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=ids)                       # type: ignore
        )
        logger.info(f"Đã xoá {len(ids)} vectors khỏi Qdrant.")


    async def check_exists(self, doc_id: str) -> bool:
        """Kiểm tra xem một file/document đã được index vào Qdrant chưa.
        Dựa vào field 'source_id' lưu trong metadata.
        """
        # Sử dụng API scroll của Qdrant để tìm xem có bất kỳ chunk nào 
        # mang payload (metadata) chứa source_id khớp với doc_id không.
        records, _ = await self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="filename", # Tên field trong metadata
                        match=MatchValue(value=doc_id)
                    )
                ]
            ),
            limit=1, # Chỉ cần tìm thấy 1 cái là đủ kết luận True
            with_payload=False,
            with_vectors=False
        )
        
        is_exist = len(records) > 0
        return is_exist

# ── Factory ───────────────────────────────────────────────────────────────────

_vector_db_instance: VectorDBClient | None = None


def get_vector_db() -> VectorDBClient:
    """Factory function — trả về Vector DB client phù hợp với config.

    Singleton: client chỉ được khởi tạo một lần.

    Returns:
        VectorDBClient: Pinecone, Weaviate hoặc Qdrant client.

    Raises:
        ValueError: Nếu ``VECTOR_DB_PROVIDER`` không được hỗ trợ.
    """
    global _vector_db_instance
    if _vector_db_instance is not None:
        return _vector_db_instance

    provider = settings.vector_db_provider
    logger.info("vector_db_init", provider=provider)

    if provider == "pinecone":
        _vector_db_instance = PineconeClient()
    elif provider == "weaviate":
        _vector_db_instance = WeaviateClient()
    elif provider == "qdrant":
        _vector_db_instance = QdrantClient()
    else:
        raise ValueError(f"Unsupported vector DB provider: {provider}")

    return _vector_db_instance
