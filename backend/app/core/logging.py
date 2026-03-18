"""
app/core/logging.py
-------------------
Cấu hình structured logging với structlog.
Hỗ trợ JSON output (production) và console pretty-print (development).
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """Khởi tạo cấu hình logging cho toàn bộ ứng dụng.

    - ``development``: Pretty-print có màu ra stdout.
    - ``production``: JSON structured log ra stdout để ingest vào log aggregator.

    Gọi hàm này một lần duy nhất khi khởi động app (trong ``main.py``).
    """
    settings = get_settings()
    is_dev = settings.app_env == "development"

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Sync với stdlib logging để bắt log từ thư viện khác
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if is_dev else logging.INFO,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Tạo logger có tên module.

    Args:
        name: Tên logger, thường là ``__name__`` của module gọi.

    Returns:
        structlog BoundLogger đã được cấu hình.

    Example::

        logger = get_logger(__name__)
        logger.info("chunk_indexed", doc_id="abc", chunks=42)
    """
    return structlog.get_logger(name)
