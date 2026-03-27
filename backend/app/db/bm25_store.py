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
import string
from pyvi import ViTokenizer
from rank_bm25 import BM25Okapi
from dataclasses import asdict

from app.rag.chunker import Chunk
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
        if not text or not text.strip():
            return []

        text = text.lower() # chuẩn hóa Luật = luật = LUẬT

        # Loại bỏ dấu câu (Punctuation removal)
        # Thay thế các dấu (, . ? ! : ...) bằng khoảng trắng để các từ không bị dính vào nhau
        translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
        clean_text = text.translate(translator)

        # Phân tách từ tiếng Việt (Word Segmentation)
        # Hàm này sẽ tự động phân tích ngữ pháp và nối các từ ghép bằng dấu gạch dưới '_'
        # Ví dụ: "bồi thường thiệt hại" -> "bồi_thường thiệt_hại"
        segmented_text = ViTokenizer.tokenize(clean_text)

        # Cắt chuỗi thành một list các tokens dựa trên khoảng trắng
        tokens = segmented_text.split()

        return tokens



    def fit(self, documents: list[dict[str, Any]]) -> None:
        """Fit BM25 index từ danh sách documents.

        Args:
            documents: List dict gồm ít nhất ``{"id": str, "text": str, "metadata": dict}``.
                       ``text`` là nội dung chunk sẽ được index.
        """
        if not documents:
            logger.warning("Danh sách documents rỗng. Bỏ qua quá trình build BM25.")
            return

        logger.info(f"Bắt đầu build BM25 index cho {len(documents)} documents...")

        # Khởi tạo/Reset lại danh sách tokens và metadata
        tokenized_corpus = []
        self.doc_metadata = []

        # Lặp qua từng tài liệu để xử lý
        for doc in documents:
            # Lấy thông tin an toàn bằng hàm .get()
            doc_id = doc.get("id", "")
            text = doc.get("text", "")
            meta = doc.get("metadata", {})

            # 1. Băm văn bản thành các tokens (áp dụng thư viện pyvi tiếng Việt)
            tokens = self._tokenize(text)
            tokenized_corpus.append(tokens)

            # 2. Lưu lại metadata vào mảng để sau này search còn biết id gốc là gì
            self.doc_metadata.append({
                "id": doc_id,
                "text": text,        # Lưu lại một bản text gốc (optional nhưng hữu ích)
                "metadata": meta
            })

        # 3. Nạp toàn bộ dữ liệu đã băm vào mô hình BM25Okapi để nó học (tính điểm)
        self.bm25 = BM25Okapi(tokenized_corpus)

        logger.info("Hoàn tất build BM25 index.")



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


if __name__ == "__main__":
    # xau = "1. Người lao động là người làm việc cho người sử dụng lao động theo thỏa thuận, được trả lương và chịu sự quản lý, điều hành, giám sát của người sử dụng lao động."
    # bm25 = BM25Store()
    # tokens = bm25._tokenize(xau)
    # print(tokens)
    from app.rag.chunker import DocumentChunker
    import pprint
    chunker = DocumentChunker()
    documents = chunker.chunk_file(file_path = "/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/rag/data/luat_lao_dong.txt") # kiểu Chunk trong chunker.py
    dict_documents = [asdict(chunk) for chunk in documents] 
    # pprint.pprint(dict_documents[0])

