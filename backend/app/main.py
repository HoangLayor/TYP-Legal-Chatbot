"""
app/main.py
-----------
FastAPI application entry point.
Khởi tạo app, đăng ký routers, middleware và lifecycle events.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import chat, history, ingest, search
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.security import setup_cors, setup_rate_limiter
from app.db.mongo import close_mongo_client, ping_mongo

# Khởi tạo logging trước mọi thứ khác
setup_logging()
logger = get_logger(__name__)
settings = get_settings()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Quản lý startup/shutdown của ứng dụng.

    Startup:
    - Ping MongoDB để xác nhận kết nối.
    - Log thông tin khởi động.

    Shutdown:
    - Đóng Motor MongoDB client.

    Args:
        app: FastAPI application instance.

    Yields:
        None (FastAPI pattern).
    """
    # --- Startup ---
    logger.info(
        "app_starting",
        env=settings.app_env,
        host=settings.app_host,
        port=settings.app_port,
    )
    mongo_ok = await ping_mongo()
    if not mongo_ok:
        logger.warning("mongo_connection_failed_app_continues")

    yield

    # --- Shutdown ---
    logger.info("app_shutting_down")
    await close_mongo_client()
    logger.info("app_shutdown_complete")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Tạo và cấu hình FastAPI application.

    Factory function để dễ test và tái sử dụng.

    Returns:
        FastAPI: Application instance đã cấu hình đầy đủ.
    """
    app = FastAPI(
        title="RAG Chatbot API",
        description=(
            "Hệ thống chatbot pháp lý sử dụng RAG pipeline với "
            "Hybrid Search, Reranking, Tavily Web Search và MongoDB Memory."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware
    setup_cors(app)
    setup_rate_limiter(app)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Routers
    API_PREFIX = "/api/v1"
    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(ingest.router, prefix=API_PREFIX)
    app.include_router(history.router, prefix=API_PREFIX)
    app.include_router(search.router, prefix=API_PREFIX)

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Kiểm tra trạng thái ứng dụng.

        Returns:
            dict: ``{"status": "ok"}`` nếu app đang chạy bình thường.
        """
        return {"status": "ok", "env": settings.app_env}

    return app


# ── Entry point ───────────────────────────────────────────────────────────────

app = create_app()
"""ASGI application instance — dùng cho uvicorn: ``uvicorn app.main:app``."""
