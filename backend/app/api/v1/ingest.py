"""
app/api/v1/ingest.py
---------------------
POST /api/v1/ingest — upload và index tài liệu vào knowledge base.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.logging import get_logger
from app.db.bm25_store import BM25Store, get_bm25_store
from app.db.vector_db import VectorDBClient, get_vector_db
from app.models import IngestResponse
from app.rag.chunker import DocumentChunker
from app.rag.embedder import Embedder, get_embedder

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingestion"])

ALLOWED_TYPES = {"application/pdf", "text/html", "text/plain", "text/markdown"}
ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".txt", ".md"}


@router.post(
    "",
    response_model=IngestResponse,
    summary="Upload và index tài liệu",
)
async def ingest_document(
    file: UploadFile = File(..., description="File PDF, TXT, MD hoặc HTML"),
    chunk_size: int = Form(512, ge=64, le=4096, description="Kích thước chunk (ký tự)"),
    chunk_overlap: int = Form(50, ge=0, le=512, description="Overlap giữa các chunk"),
    source_label: str = Form("", description="Nhãn nguồn tài liệu (tuỳ chọn)"),
    embedder: Embedder = Depends(get_embedder),
    vector_db: VectorDBClient = Depends(get_vector_db),
    bm25_store: BM25Store = Depends(get_bm25_store),
) -> IngestResponse:
    """Upload file và index vào knowledge base (Vector DB + BM25).

    **Quá trình xử lý:**
    1. Validate file type và extension.
    2. Đọc file bytes.
    3. Chunk bằng DocumentChunker.
    4. Embed tất cả chunks theo batch.
    5. Upsert vào Vector DB (dense).
    6. Update BM25 index (sparse).
    7. Trả về số chunks đã index.

    Args:
        file: File upload từ multipart form.
        chunk_size: Kích thước mỗi chunk.
        chunk_overlap: Overlap giữa chunks.
        source_label: Label để tag nguồn trong metadata.
        embedder: Injected Embedder.
        vector_db: Injected Vector DB client.
        bm25_store: Injected BM25 store.

    Returns:
        IngestResponse với document_id, chunks_indexed, filename.

    Raises:
        HTTPException 400: File type không được hỗ trợ.
        HTTPException 422: File rỗng.
        HTTPException 500: Lỗi khi index.
    """
    ...
