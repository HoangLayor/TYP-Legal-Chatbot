"""
app/api/v1/ingest.py
---------------------
POST /api/v1/ingest — upload và index tài liệu vào knowledge base.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

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
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    content_type = (file.content_type or "").lower()

    # 1. Validate file type / extension
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không được hỗ trợ: {suffix}",
        )

    # Cho phép pass nếu content_type trống (một số client gửi không chuẩn)
    if content_type and content_type not in ALLOWED_TYPES:
        logger.warning(
            "Upload file với content_type lạ nhưng extension hợp lệ",
            filename=filename,
            content_type=content_type,
        )

    # 2. Đọc file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        logger.exception("Không thể đọc file upload", filename=filename, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Không thể đọc file upload: {str(e)}",
        ) from e

    if not file_bytes:
        raise HTTPException(status_code=422, detail="File rỗng")

    logger.info(
        "Bắt đầu ingest tài liệu",
        filename=filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source_label=source_label or None,
    )

    try:
        # 3. Chunk bằng DocumentChunker
        chunker = DocumentChunker(
            default_chunk_size=chunk_size,
            default_chunk_overlap=chunk_overlap,
        )

        # Ưu tiên chunk_bytes nếu project của bạn có hỗ trợ
        if hasattr(chunker, "chunk_bytes"):
            chunks = chunker.chunk_bytes(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source_label=source_label,
            )
        else:
            # Fallback: nếu chunker của bạn chưa có chunk_bytes
            # -> báo lỗi rõ ràng để bạn bổ sung method trong chunker
            raise RuntimeError(
                "DocumentChunker chưa hỗ trợ chunk_bytes(). "
                "Hãy thêm method chunk_bytes(...) hoặc đổi flow sang lưu file tạm rồi gọi chunk_file(...)."
            )

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Không thể trích xuất nội dung hoặc không tạo được chunk từ file.",
            )

        logger.info("Chunking hoàn tất", filename=filename, chunks_count=len(chunks))

        # 4. Embed tất cả chunks theo batch
        chunk_texts = [chunk.text for chunk in chunks]

        # Hỗ trợ cả async embed_documents hoặc sync embed
        if hasattr(embedder, "embed_documents"):
            embeddings = await embedder.embed_documents(chunk_texts)
        elif hasattr(embedder, "embed_texts"):
            embeddings = await embedder.embed_texts(chunk_texts)
        else:
            raise RuntimeError(
                "Embedder không có method embed_documents() hoặc embed_texts()."
            )

        if not embeddings or len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Số lượng embeddings không khớp số chunks "
                f"({len(embeddings) if embeddings else 0} != {len(chunks)})."
            )

        logger.info("Embedding hoàn tất", filename=filename, embeddings_count=len(embeddings))

        # 5. Upsert vào Vector DB (dense)
        # Chuyển chunk -> dict để vector db dễ xử lý
        chunk_dicts = [asdict(chunk) for chunk in chunks]

        # Gắn source_label vào metadata nếu có
        if source_label.strip():
            for doc in chunk_dicts:
                metadata = doc.get("metadata", {}) or {}
                metadata["source_label"] = source_label.strip()
                doc["metadata"] = metadata

        # Hỗ trợ nhiều kiểu API vector db
        document_id: str | None = None

        if hasattr(vector_db, "upsert_documents"):
            result = await vector_db.upsert_documents(
                documents=chunk_dicts,
                embeddings=embeddings,
            )
            if isinstance(result, str):
                document_id = result

        elif hasattr(vector_db, "upsert"):
            result = await vector_db.upsert(
                documents=chunk_dicts,
                embeddings=embeddings,
            )
            if isinstance(result, str):
                document_id = result

        else:
            raise RuntimeError(
                "VectorDBClient không có method upsert_documents() hoặc upsert()."
            )

        logger.info(
            "Upsert Vector DB hoàn tất",
            filename=filename,
            collection=getattr(vector_db, "collection_name", None),
            chunks_count=len(chunk_dicts),
        )

        # 6. Update BM25 index (sparse)
        bm25_store.add_documents(chunk_dicts)

        logger.info(
            "Cập nhật BM25 hoàn tất",
            filename=filename,
            chunks_count=len(chunk_dicts),
        )

        # 7. Trả về số chunks đã index
        if not document_id:
            # Fallback: lấy document_id từ chunk đầu nếu có
            first_chunk = chunk_dicts[0]
            metadata = first_chunk.get("metadata", {}) or {}
            document_id = (
                metadata.get("document_id")
                or metadata.get("doc_id")
                or first_chunk.get("id")
                or filename
            )

        logger.info(
            "Ingest thành công",
            filename=filename,
            document_id=document_id,
            chunks_indexed=len(chunk_dicts),
        )

        return IngestResponse(
            document_id=document_id,
            chunks_indexed=len(chunk_dicts),
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Lỗi khi ingest tài liệu", filename=filename, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi index tài liệu: {str(e)}",
        ) from e