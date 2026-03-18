"""
app/core/config.py
------------------
Cấu hình ứng dụng sử dụng Pydantic Settings.
Tất cả biến môi trường được load từ file .env.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Toàn bộ cấu hình ứng dụng.

    Các giá trị được đọc từ biến môi trường (hoặc file .env).
    Sử dụng ``get_settings()`` thay vì khởi tạo trực tiếp để tận dụng cache.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = Field(..., min_length=32)
    allowed_origins: list[str] = ["http://localhost:5173"]
    api_rate_limit: str = "60/minute"

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""

    # ── Embedding ────────────────────────────────────────────
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 3072
    embedding_batch_size: int = 100

    # ── Vector DB ────────────────────────────────────────────
    vector_db_provider: Literal["pinecone", "weaviate", "qdrant"] = "pinecone"

    ## Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "rag-chatbot"
    pinecone_environment: str = "us-east-1-aws"

    ## Weaviate
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = ""
    weaviate_class_name: str = "Document"

    ## Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "rag-chatbot"

    # ── BM25 ─────────────────────────────────────────────────
    bm25_store_path: str = "./data/bm25_index"

    # ── Reranker ─────────────────────────────────────────────
    reranker_provider: Literal["cohere", "bge", "none"] = "cohere"
    cohere_api_key: str = ""
    bge_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 20
    rerank_top_n: int = 5

    # ── Tavily Web Search ────────────────────────────────────
    tavily_api_key: str = ""
    tavily_search_depth: Literal["basic", "advanced"] = "advanced"
    tavily_max_results: int = 5
    web_search_threshold: float = Field(0.4, ge=0.0, le=1.0)

    # ── MongoDB ──────────────────────────────────────────────
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "rag_chatbot"
    sessions_collection: str = "sessions"
    history_max_messages: int = Field(20, ge=1)
    history_max_tokens: int = Field(4096, ge=256)

    # ── Chunking ─────────────────────────────────────────────
    default_chunk_size: int = Field(512, ge=64)
    default_chunk_overlap: int = Field(50, ge=0)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        """Chuyển đổi chuỗi comma-separated thành list nếu cần."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về instance Settings được cache (singleton).

    Returns:
        Settings: Instance cấu hình duy nhất cho toàn bộ ứng dụng.
    """
    return Settings()
