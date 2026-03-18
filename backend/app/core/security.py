"""
app/core/security.py
--------------------
CORS, rate limiting và authentication middleware.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

# ── Rate Limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])
"""Limiter dùng IP address của client để đếm request."""


def setup_rate_limiter(app: FastAPI) -> None:
    """Gắn rate limiter vào FastAPI app.

    Args:
        app: FastAPI application instance.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── CORS ─────────────────────────────────────────────────────────────────────


def setup_cors(app: FastAPI) -> None:
    """Cấu hình CORS middleware cho FastAPI app.

    Cho phép các origin được khai báo trong ``ALLOWED_ORIGINS``.

    Args:
        app: FastAPI application instance.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ── API Key Auth (đơn giản) ───────────────────────────────────────────────────


def get_api_key(request: Request) -> str | None:
    """Trích xuất API key từ header ``X-API-Key``.

    Args:
        request: FastAPI Request object.

    Returns:
        API key string nếu có, None nếu không.
    """
    return request.headers.get("X-API-Key")


def verify_api_key(api_key: str | None) -> bool:
    """Xác thực API key.

    Hiện tại kiểm tra so với SECRET_KEY trong config.
    Có thể mở rộng để lookup database sau này.

    Args:
        api_key: Key cần xác thực.

    Returns:
        True nếu key hợp lệ, False nếu không.
    """
    if not api_key:
        return False
    return api_key == settings.secret_key
