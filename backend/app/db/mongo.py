"""
app/db/mongo.py
---------------
MongoDB async client sử dụng Motor (asyncio driver cho PyMongo).
Cung cấp singleton client và helper để truy cập database/collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import motor.motor_asyncio

from app.core.config import get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import (
        AsyncIOMotorClient,
        AsyncIOMotorCollection,
        AsyncIOMotorDatabase,
    )

logger = get_logger(__name__)
settings = get_settings()

# ── Singleton client ──────────────────────────────────────────────────────────

_client: "AsyncIOMotorClient | None" = None


def get_mongo_client() -> "AsyncIOMotorClient":
    """Trả về singleton Motor client.

    Client được tái sử dụng cho toàn bộ vòng đời ứng dụng.
    Kết nối thực sự được tạo lazy khi lần đầu tiên thực hiện request.

    Returns:
        AsyncIOMotorClient: Motor async MongoDB client.
    """
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
        logger.info("mongo_client_created", url=settings.mongodb_url)
    return _client


def get_database() -> "AsyncIOMotorDatabase":
    """Trả về database object tương ứng với ``MONGODB_DB_NAME``.

    Returns:
        AsyncIOMotorDatabase: Database instance.
    """
    client = get_mongo_client()
    return client[settings.mongodb_db_name]


def get_collection(name: str) -> "AsyncIOMotorCollection":
    """Trả về collection theo tên trong database mặc định.

    Args:
        name: Tên collection (ví dụ: ``"sessions"``).

    Returns:
        AsyncIOMotorCollection: Collection instance.
    """
    db = get_database()
    return db[name]


async def ping_mongo() -> bool:
    """Kiểm tra kết nối MongoDB bằng lệnh ping.

    Returns:
        True nếu kết nối thành công, False nếu lỗi.
    """
    try:
        client = get_mongo_client()
        await client.admin.command("ping")
        logger.info("mongo_ping_ok")
        return True
    except Exception as exc:
        logger.error("mongo_ping_failed", error=str(exc))
        return False


async def close_mongo_client() -> None:
    """Đóng Motor client khi ứng dụng shutdown.

    Gọi hàm này trong lifecycle event ``on_shutdown`` của FastAPI.
    """
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("mongo_client_closed")
