"""
app/db/bm25_store.py
---------------------
BM25 sparse index sử dụng rank-bm25.
Hỗ trợ persist/load index từ disk để không phải rebuild mỗi lần restart.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class BM25Store:
    """Lưu trữ và truy vấn BM25 sparse index.

    Corpus được tokenize và index bằng ``rank_bm25.BM25Okapi``.
    Index và metadata được persist ra disk (pickle) để reload nhanh.

    Attributes:
        store_path (Path): Đường dẫn thư mục lưu index.
        bm25 (BM25Okapi | None): Instance BM25 sau khi fit.
        doc_metadata (list[dict]): Metadata tương ứng với từng doc trong corpus.
    """

    def __init__(self, store_path: str | None = None) -> None:
        """Khởi tạo BM25Store.

        Args:
            store_path: Đường dẫn thư mục persist. Mặc định dùng ``BM25_STORE_PATH`` từ config.
        """
        self.store_path = Path(store_path or settings.bm25_store_path)
        self.bm25 = None
        self.doc_metadata: list[dict[str, Any]] = []

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text thành list tokens.

        Hiện tại dùng whitespace split đơn giản.
        Có thể thay bằng underthesea/pyvi cho tiếng Việt.

        Args:
            text: Văn bản đầu vào.

        Returns:
            List tokens.
        """
        ...

    def fit(self, documents: list[dict[str, Any]]) -> None:
        """Fit BM25 index từ danh sách documents.

        Args:
            documents: List dict gồm ít nhất ``{"id": str, "text": str, "metadata": dict}``.
                       ``text`` là nội dung chunk sẽ được index.
        """
        ...

    def search(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        """Tìm kiếm BM25 và trả về top-k kết quả.

        Args:
            query: Query string từ user.
            top_k: Số kết quả trả về.

        Returns:
            List dict ``{"id": str, "score": float, "metadata": dict, "rank": int}``
            đã sắp xếp theo score giảm dần.

        Raises:
            RuntimeError: Nếu index chưa được fit (``self.bm25 is None``).
        """
        ...

    def save(self) -> None:
        """Persist BM25 index và metadata ra disk (pickle).

        Tạo thư mục nếu chưa tồn tại.
        """
        ...

    def load(self) -> bool:
        """Load BM25 index từ disk.

        Returns:
            True nếu load thành công, False nếu file không tồn tại.
        """
        ...

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Thêm documents mới vào index (rebuild từ đầu với tất cả docs).

        Args:
            documents: Danh sách documents mới (cùng format với ``fit``).
        """
        ...

    def delete_documents(self, ids: list[str]) -> None:
        """Xoá documents theo ID và rebuild index.

        Args:
            ids: Danh sách document ID cần xoá.
        """
        ...


# ── Singleton ─────────────────────────────────────────────────────────────────

_bm25_store: BM25Store | None = None


def get_bm25_store() -> BM25Store:
    """Trả về singleton BM25Store instance.

    Load từ disk nếu có; nếu không, trả về empty store cần fit lại.

    Returns:
        BM25Store: Singleton instance.
    """
    global _bm25_store
    if _bm25_store is None:
        _bm25_store = BM25Store()
        loaded = _bm25_store.load()
        if loaded:
            logger.info("bm25_store_loaded", path=str(_bm25_store.store_path))
        else:
            logger.warning("bm25_store_empty_will_need_reindex")
    return _bm25_store
