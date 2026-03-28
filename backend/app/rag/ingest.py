"""
app/rag/ingest.py
-----------------
Kịch bản (Script) nạp dữ liệu (Data Ingestion) cho hệ thống RAG.
Chạy độc lập để quét các file tài liệu, băm nhỏ, tính toán vector và lưu vào Qdrant & BM25.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from dataclasses import asdict
from typing import Any

from torch._dynamo.symbolic_convert import ReturnValueOp

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.chunker import DocumentChunker
from app.rag.embedder import get_embedder
from app.db.vector_db import get_vector_db
from app.db.bm25_store import get_bm25_store

logger = get_logger(__name__)
settings = get_settings()


class DataIngestor:
    """Quản lý toàn bộ quy trình nạp dữ liệu từ file vào các Database.
    
    Quy trình:
    1. Quét thư mục tìm file hợp lệ.
    2. Kiểm tra xem file đã được nạp (index) vào Qdrant chưa (chống trùng lặp).
    3. Nếu là file mới: Cắt nhỏ (Chunking).
    4. Tính toán Vector (Embedding) theo lô (batch).
    5. Đẩy Vector + Text vào Qdrant (Dense DB).
    6. Gom tất cả text mới đẩy vào BM25 (Sparse DB) một lần ở cuối để tối ưu.
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """Khởi tạo Ingestor với các công cụ cần thiết.

        Args:
            data_dir: Đường dẫn tới thư mục chứa file. Mặc định dùng thư mục 'data' trong 'rag'.
        """
        # Trỏ mặc định tới app/rag/data
        base_dir = Path(__file__).parent.parent.parent.parent / "data"
        self.data_dir = Path(data_dir) if data_dir else base_dir
        
        self.chunker = DocumentChunker()
        self.embedder = get_embedder()
        self.vector_db = get_vector_db()
        self.bm25_store = get_bm25_store()

    async def ingest_all(self) -> None:
        """Thực thi luồng quét và nạp toàn bộ dữ liệu trong thư mục."""
        if not self.data_dir.exists():
            logger.error(f"Thư mục dữ liệu không tồn tại: {self.data_dir}")
            return

        # 1. Quét tất cả các file có đuôi được hỗ trợ
        valid_extensions = [".txt", ".pdf", ".md", ".docx", ".html", ".htm"]
        all_files = [
            f for f in self.data_dir.rglob("*") 
            if f.is_file() and f.suffix.lower() in valid_extensions
        ] #PosixPath('/teamspace/studios/this_studio/TYP-Legal-Chatbot/data/luat_doanh_nghiep.txt'

        logger.info(f"Tìm thấy {len(all_files)} file tài liệu trong {self.data_dir}")
        # print(all_files[0].name)
        # return
        
        # Biến chứa toàn bộ luật mới để sau cùng update BM25 một lần cho nhanh
        all_new_chunks_for_bm25: list[dict[str, Any]] = []
        total_upserted_vectors = 0

        for file_path in all_files:
            file_name = file_path.name #luat_doanh_nghiep.txt
            
            # 2. Kiểm tra trùng lặp (Dedup)
            # Hàm này ta đã comment để sẵn bên trong QdrantClient (vector_db.py)
            is_exist = await self.vector_db.check_exists(doc_id=file_name)
            if is_exist:
                logger.info(f"Bỏ qua: '{file_name}' (Đã tồn tại trong Database)")
                continue
                
            logger.info(f"Đang xử lý file mới: '{file_name}'...")
            
            try:
                # 3. Cắt tài liệu thành các Chunk
                # Gắn thêm source_id chính là tên file để lần sau check trùng lặp
                chunks = self.chunker.chunk_file(
                    file_path=file_path, 
                    # extra_metadata={"source_id": file_name}
                )
                
                if not chunks:
                    logger.warning(f"File '{file_name}' rỗng hoặc không trích xuất được text.")
                    continue

                # Rút trích list text thô để đưa cho Embedder
                texts_to_embed = [chunk.text for chunk in chunks]
                
                # 4. Chuyển Text thành Vector bằng BGE-M3 (chạy batch cho nhanh)
                embeddings = await self.embedder.embed_batch(texts_to_embed)
                
                # 5. Lắp ráp dữ liệu chuẩn bị đẩy lên Qdrant
                qdrant_points = []
                bm25_docs = []
                
                for chunk, vector in zip(chunks, embeddings):
                    # Định dạng cho BM25 (Yêu cầu list dict có text, id, metadata)
                    chunk_dict = asdict(chunk)
                    bm25_docs.append(chunk_dict)
                    
                    # Định dạng cho Qdrant (Yêu cầu list dict có id, values, metadata)
                    # Ta gộp luôn text vào metadata để lúc Search Qdrant trả text về cho LLM
                    meta = chunk_dict["metadata"].copy()
                    meta["text"] = chunk.text 
                    
                    qdrant_points.append({
                        "id": chunk.id,
                        "values": vector,
                        "metadata": meta
                    })
                
                # 6. Đẩy vào Qdrant Vector DB
                res = await self.vector_db.upsert(qdrant_points)
                total_upserted_vectors += res.get("upserted_count", 0)
                
                # Gom dữ liệu BM25 lại để lát nữa xử lý 1 cục
                all_new_chunks_for_bm25.extend(bm25_docs)
                
                logger.info(f"Đã nạp xong '{file_name}' ({len(chunks)} chunks).")

            except Exception as e:
                logger.error(f"Lỗi khi xử lý file '{file_name}': {e}")
                
        # 7. Cập nhật BM25 Index (Chỉ chạy nếu có dữ liệu mới)
        if all_new_chunks_for_bm25:
            logger.info(f"Bắt đầu cập nhật BM25 Index cho {len(all_new_chunks_for_bm25)} chunks mới...")
            # Hàm add_documents đã tích hợp sẵn logic gộp dữ liệu cũ, build lại và tự lưu file pickle
            self.bm25_store.add_documents(all_new_chunks_for_bm25)
            logger.info("Cập nhật BM25 Index thành công!")
            
        logger.info("-" * 50)
        logger.info(f"HOÀN TẤT INGESTION! Đã đẩy {total_upserted_vectors} vectors mới vào Qdrant.")


if __name__ == "__main__":
    async def main():
        ingestor = DataIngestor()
        await ingestor.ingest_all()

    asyncio.run(main())