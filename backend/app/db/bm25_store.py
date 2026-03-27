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
        # print(tokenized_corpus[0])
        # print("\n\n\n")
        # print(self.doc_metadata[0])
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
        # 1. Kiểm tra xem mô hình đã được nạp dữ liệu (fit/load) chưa
        if self.bm25 is None:
            logger.error("BM25 index chưa được khởi tạo. Hãy gọi fit() hoặc load() trước.")
            raise RuntimeError("BM25 index chưa được khởi tạo.")

        # 2. Băm câu hỏi (query) thành các tokens tương tự như lúc băm documents
        query_tokens = self._tokenize(query)
        
        # Nếu câu hỏi rỗng sau khi tokenize, trả về list rỗng
        if not query_tokens:
            return []

        # 3. Lấy điểm số BM25 cho tất cả các documents trong corpus
        # Hàm get_scores trả về một list điểm số, vị trí tương ứng với self.doc_metadata
        scores = self.bm25.get_scores(query_tokens)

        # 4. Ghép điểm số với vị trí (index) của nó để chuẩn bị sắp xếp
        # Ví dụ: [(0, 1.2), (1, 0.5), (2, 3.4)...] trong đó số đầu là index, số sau là score
        scored_indices = [(i, score) for i, score in enumerate(scores)]

        # 5. Sắp xếp giảm dần theo điểm số (score nằm ở phần tử thứ 1 của tuple)
        scored_indices.sort(key=lambda x: x[1], reverse=True)

        # 6. Cắt lấy top_k kết quả có điểm cao nhất
        # Lọc bỏ các kết quả có điểm số <= 0 (không chứa từ khóa nào)
        top_results = []
        for rank, (idx, score) in enumerate(scored_indices[:top_k], start=1):
            if score <= 0:
                continue # Bỏ qua nếu document không khớp bất kỳ token nào
                
            doc_info = self.doc_metadata[idx]
            top_results.append({
                "id": doc_info["id"],
                "score": float(score),
                "metadata": doc_info["metadata"],
                "rank": rank,
                "text": doc_info["text"] # Trả về text để RAG pipeline lấy làm context
            })

        return top_results

    def save(self) -> None:
        """Persist BM25 index và metadata ra disk (pickle).

        Tạo thư mục nếu chưa tồn tại.
        """
        # 1. Kiểm tra xem có dữ liệu để lưu không
        if self.bm25 is None or not self.doc_metadata:
            logger.warning("Không có dữ liệu BM25 để lưu (index đang trống). Hãy gọi hàm fit() trước.")
            return

        try:
            # 2. Tạo thư mục nếu nó chưa tồn tại (tương đương mkdir -p trong Linux)
            self.store_path.mkdir(parents=True, exist_ok=True)
            
            # 3. Định nghĩa đường dẫn file sẽ lưu
            file_path = self.store_path / "bm25_index.pkl"
            
            # 4. Gộp mô hình và metadata vào một dictionary để lưu chung vào 1 file cho gọn
            data_to_save = {
                "bm25": self.bm25,
                "doc_metadata": self.doc_metadata
            }
            
            # 5. Ghi dữ liệu ra file dưới dạng nhị phân (binary)
            with open(file_path, "wb") as f:
                pickle.dump(data_to_save, f)
                
            logger.info(f"Đã lưu thành công BM25 index và metadata tại: {file_path}")
            
        except Exception as e:
            logger.error(f"Lỗi trong quá trình lưu BM25 index: {e}")
            raise



    def load(self) -> bool:
        """Load BM25 index từ disk.

        Returns:
            True nếu load thành công, False nếu file không tồn tại.
        """
        # 1. Xác định đường dẫn file đã lưu
        file_path = self.store_path / "bm25_index.pkl"
        
        # 2. Kiểm tra xem file có tồn tại trên ổ cứng không
        if not file_path.exists():
            logger.info(f"Không tìm thấy file BM25 index tại {file_path}. Có thể hệ thống cần chạy fit() để build lại từ đầu.")
            return False

        try:
            # 3. Mở file dưới dạng đọc nhị phân (rb - read binary)
            with open(file_path, "rb") as f:
                loaded_data = pickle.load(f)
            
            # 4. Phục hồi lại các thuộc tính cho class
            self.bm25 = loaded_data.get("bm25")
            self.doc_metadata = loaded_data.get("doc_metadata", [])
            
            # Kiểm tra tính toàn vẹn cơ bản
            if self.bm25 is None:
                logger.warning("File index bị hỏng hoặc không chứa mô hình BM25 hợp lệ.")
                return False
                
            logger.info(f"Đã load thành công BM25 index với {len(self.doc_metadata)} documents từ disk.")
            return True
            
        except Exception as e:
            # Bắt các lỗi như file bị hỏng (corrupt), sai định dạng pickle...
            logger.error(f"Lỗi khi load BM25 index từ {file_path}: {e}")
            return False



    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Thêm documents mới vào index (rebuild từ đầu với tất cả docs).

        Args:
            documents: Danh sách documents mới (cùng format với ``fit``).
        """
        # 1. Kiểm tra đầu vào
        if not documents:
            logger.info("Không có document mới nào để thêm. Bỏ qua.")
            return

        logger.info(f"Đang chuẩn bị thêm {len(documents)} document(s) mới vào BM25 index...")

        # 2. Lấy lại danh sách các documents cũ
        # Rất may là trong hàm fit() trước đó, ta đã lưu nguyên bản 'id', 'text', 'metadata' 
        # vào trong self.doc_metadata, nên giờ chỉ cần lôi ra xài lại.
        old_documents = []
        if self.doc_metadata:
            # Copy để tránh tham chiếu bộ nhớ khi hàm fit() reset lại self.doc_metadata
            old_documents = self.doc_metadata.copy() 

        # 3. Gộp luật cũ và luật mới thành một danh sách duy nhất
        all_documents = old_documents + documents

        # 4. Tái sử dụng hàm fit() để đập đi xây lại toàn bộ index
        # Hàm fit() sẽ tự động dọn dẹp biến cũ và tạo lại BM25Okapi mới
        logger.info(f"Bắt đầu rebuild index với tổng cộng {len(all_documents)} documents...")
        self.fit(all_documents)

        # 5. Lưu đè file mới xuống ổ cứng luôn để đảm bảo đồng bộ
        self.save()
        
        logger.info(f"Hoàn tất cập nhật. Tổng số docs hiện tại trong BM25: {len(self.doc_metadata)}")

    def delete_documents(self, ids: list[str]) -> None:
        """Xoá documents theo ID và rebuild index.

        Args:
            ids: Danh sách document ID cần xoá.
        """
        # 1. Kiểm tra đầu vào và trạng thái hiện tại
        if not ids or not self.doc_metadata:
            logger.info("Không có ID nào để xoá hoặc index hiện đang trống. Bỏ qua.")
            return

        logger.info(f"Yêu cầu xoá {len(ids)} document(s) khỏi BM25 index...")

        # 2. Chuyển list ID thành set để tăng tốc độ tìm kiếm (O(1) thay vì O(N))
        ids_to_remove = set(ids)

        # 3. Lọc giữ lại những document KHÔNG NẰM TRONG danh sách bị xoá
        remaining_documents = [doc for doc in self.doc_metadata if doc.get("id") not in ids_to_remove]

        # 4. Kiểm tra xem có thực sự xoá được document nào không
        # Nếu số lượng trước và sau khi lọc giống hệt nhau, nghĩa là các ID truyền vào không tồn tại
        if len(remaining_documents) == len(self.doc_metadata):
            logger.info("Không tìm thấy document nào khớp với các ID cung cấp. Bỏ qua quá trình rebuild.")
            return

        docs_deleted = len(self.doc_metadata) - len(remaining_documents)
        logger.info(f"Đã xác định {docs_deleted} document(s) cần xoá. Bắt đầu rebuild index với {len(remaining_documents)} documents còn lại...")

        # 5. Đập đi xây lại (rebuild) index với danh sách đã được lọc
        self.fit(remaining_documents)

        # 6. Lưu đè trạng thái mới xuống ổ cứng
        self.save()
        
        logger.info(f"Hoàn tất xoá. Tổng số docs hiện tại trong BM25: {len(self.doc_metadata)}")


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
    bm25 = BM25Store()
    # tokens = bm25._tokenize(xau)
    # print(tokens)
    from app.rag.chunker import DocumentChunker
    import pprint
    import os
    chunker = DocumentChunker()
    documents = chunker.chunk_file(file_path = "/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/rag/data/luat_lao_dong.txt") # kiểu Chunk trong chunker.py
    dict_documents = [asdict(chunk) for chunk in documents] 
    # pprint.pprint(dict_documents[0])
    bm25.fit(documents = dict_documents)
    # res = bm25.search(query = "Luật lao động là gì", top_k = 5)
    # pprint.pprint(res[0])
    bm25.save()

    '''
    # code để đẩy nhiều file vào cùng lúc
    data_path = "/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/rag/data"
    all_dict_documents = []
    for file in os.listdir(data_path):
        file = os.path.join(data_path, file)
        documents = chunker.chunk_file(file_path = file)
        dict_documents = [asdict(chunk) for chunk in documents]
        all_dict_documents.extend(dict_documents)
    if all_dict_documents:
        print("Bắt đầu nhồi toàn bộ dữ liệu vào BM25...")
        bm25.fit(documents=all_dict_documents)
        
        # 6. Lưu xuống ổ cứng
        bm25.save()
        print("Đã hoàn tất build và lưu BM25 index tổng hợp!")
        
        # (Tùy chọn) Test thử luôn xem nó tìm có chuẩn không
        # res = bm25.search(query="quy định về hợp đồng lao động", top_k=3)
        # print("\nKết quả test nhanh:")
        # pprint.pprint(res)
    else:
        print("Không có dữ liệu nào để xử lý.")
    '''
