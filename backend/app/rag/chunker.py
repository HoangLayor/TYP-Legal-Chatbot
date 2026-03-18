"""
app/rag/chunker.py
------------------
Document chunking — chia tài liệu thành các đoạn nhỏ (chunks) để index.
Hỗ trợ PDF, HTML, TXT, Markdown.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class Chunk:
    """Đơn vị văn bản sau khi chunk.

    Attributes:
        id: ID duy nhất của chunk (UUID v4).
        text: Nội dung văn bản của chunk.
        metadata: Thông tin bổ sung (tên file, trang, thứ tự chunk, ...).
        token_count: Số token ước tính (dùng cho trim context).
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    token_count: int = 0

    def __post_init__(self) -> None:
        """Tính token_count nếu chưa được set."""
        if self.token_count == 0:
            # Ước tính thô: 1 token ≈ 4 ký tự
            self.token_count = len(self.text) // 4


class DocumentChunker:
    """Chia tài liệu thành Chunk với overlap.

    Sử dụng LangChain RecursiveCharacterTextSplitter bên dưới,
    nhưng wrap lại để trả về list[Chunk] với metadata thống nhất.

    Attributes:
        chunk_size (int): Số ký tự tối đa mỗi chunk.
        chunk_overlap (int): Số ký tự overlap giữa các chunk liên tiếp.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """Khởi tạo chunker với tuỳ chỉnh kích thước.

        Args:
            chunk_size: Kích thước chunk. Mặc định từ config (``DEFAULT_CHUNK_SIZE``).
            chunk_overlap: Overlap giữa chunks. Mặc định từ config (``DEFAULT_CHUNK_OVERLAP``).
        """
        self.chunk_size = chunk_size or settings.default_chunk_size
        self.chunk_overlap = chunk_overlap or settings.default_chunk_overlap

    def _load_file(self, file_path: Path) -> str:
        """Load và extract text từ file theo extension.

        Hỗ trợ: ``.pdf``, ``.html``, ``.htm``, ``.txt``, ``.md``.

        Args:
            file_path: Đường dẫn tới file.

        Returns:
            Văn bản raw đã được extract.

        Raises:
            ValueError: Nếu extension không được hỗ trợ.
            FileNotFoundError: Nếu file không tồn tại.
        """
        ...

    def _split_text(self, text: str) -> list[str]:
        """Chia text thành list string theo chunk_size và chunk_overlap.

        Args:
            text: Toàn bộ văn bản cần chia.

        Returns:
            List string, mỗi phần tử là nội dung một chunk.
        """
        ...

    def chunk_text(
        self,
        text: str,
        base_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk một đoạn text thô thành list Chunk.

        Args:
            text: Văn bản cần chunk.
            base_metadata: Metadata base sẽ được merge vào mỗi chunk.

        Returns:
            List[Chunk] đã được gán ID và metadata.
        """
        ...

    def chunk_file(
        self,
        file_path: str | Path,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Load file và chunk thành list Chunk.

        Args:
            file_path: Đường dẫn tới file (PDF, HTML, TXT, MD).
            extra_metadata: Metadata bổ sung sẽ được merge vào mỗi chunk
                            (ví dụ: ``{"source": "legal_code", "year": 2024}``).

        Returns:
            List[Chunk] với metadata gồm ``filename``, ``file_type``,
            ``chunk_index``, ``total_chunks`` và các extra_metadata.
        """
        ...

    def chunk_bytes(
        self,
        content: bytes,
        filename: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        """Chunk từ bytes (dùng khi nhận file upload qua API).

        Args:
            content: Nội dung file dạng bytes.
            filename: Tên file gốc (dùng để detect extension).
            extra_metadata: Metadata bổ sung.

        Returns:
            List[Chunk].
        """
        ...
