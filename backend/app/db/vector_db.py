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


# ── Qdrant ────────────────────────────────────────────────────────────────────


class QdrantClient(VectorDBClient):
    """Vector DB client sử dụng Qdrant."""

    def __init__(self) -> None:
        """Khởi tạo Qdrant client và tạo collection nếu chưa có."""
        ...

    async def upsert(self, vectors: list[dict[str, Any]]) -> dict[str, Any]:
        """Upsert points vào Qdrant collection.

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
        """Truy vấn nearest vectors trong Qdrant.

        Args:
            vector: Query embedding.
            top_k: Số kết quả.
            filter: Qdrant Filter object.

        Returns:
            List ``{"id": str, "score": float, "metadata": dict}``.
        """
        ...

    async def delete(self, ids: list[str]) -> None:
        """Xoá points khỏi Qdrant theo ID.

        Args:
            ids: Danh sách point ID.
        """
        ...


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
