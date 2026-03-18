# RAG Chatbot

Hệ thống chatbot thông minh sử dụng kỹ thuật **Retrieval-Augmented Generation (RAG)** với pipeline nâng cao: Hybrid Search, Reranking, Tavily Web Search và MongoDB Memory.

**Stack:** React + Vite · FastAPI · Python 3.11+
**Vector DB:** Pinecone / Weaviate / Qdrant _(cấu hình theo môi trường)_
**Memory:** MongoDB · **Web Search:** Tavily · **Reranker:** Cohere / BGE

---

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Cây thư mục](#cây-thư-mục)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt & chạy local](#cài-đặt--chạy-local)
- [Biến môi trường](#biến-môi-trường)
- [API Reference](#api-reference)
- [Pipeline chi tiết](#pipeline-chi-tiết)
- [Chạy tests](#chạy-tests)
- [Deploy](#deploy)
- [Đóng góp](#đóng-góp)

---

## Tính năng

- **Hybrid Search** — kết hợp Dense (ANN vector) và Sparse (BM25) search, merge bằng Reciprocal Rank Fusion (RRF)
- **Reranking** — cross-encoder reranking (Cohere Rerank / `bge-reranker-v2`) để tăng độ chính xác
- **Tavily Web Search** — tự động tìm kiếm web khi knowledge base không đủ thông tin
- **MongoDB Memory** — lưu lịch sử hội thoại theo session, tự động cắt context khi vượt token limit
- **Streaming response** — trả lời theo dạng SSE stream, hiển thị realtime trên UI
- **Document ingestion** — hỗ trợ PDF, HTML, TXT, Markdown; tự động chunk và index
- **Source citation** — mỗi câu trả lời kèm nguồn tài liệu tham chiếu

---

## Kiến trúc hệ thống

```
User
 │
 ▼
React Frontend (Vite)
 │  POST /api/v1/chat/stream
 ▼
FastAPI Backend
 ├── Query Rewriting
 ├── Hybrid Search ──────────────── Vector DB (Dense ANN)
 │    └── RRF Merge               └── BM25 Store (Sparse)
 ├── Reranker (Cross-encoder)
 ├── Tavily Web Search (nếu cần)
 ├── Prompt Builder
 ├── LLM Generation (OpenAI / Anthropic)
 └── MongoDB ─── Session & History
```

**Query pipeline đầy đủ:**

```
User query
  → Load chat history (MongoDB)
  → Query rewriting
  → Embed query
  → Hybrid search (Dense + Sparse → RRF)
  → Rerank top-k → top-n
  → [Tavily web search nếu score thấp]
  → Build prompt (system + history + context + query)
  → LLM stream
  → Save message (MongoDB)
  → Stream về client
```

---

## Cây thư mục

```
rag-chatbot/
├── frontend/
│   ├── public/
│   └── src/
│       ├── assets/
│       ├── components/       # UI components tái sử dụng
│       ├── pages/            # ChatPage, HistoryPage, SettingsPage
│       ├── hooks/            # useChat, useStreaming, useChatHistory
│       ├── services/         # API client gọi FastAPI
│       ├── store/            # Zustand global state
│       ├── utils/
│       ├── types/
│       ├── main.tsx
│       └── App.tsx
│
├── backend/
│   └── app/
│       ├── api/v1/
│       │   ├── chat.py       # POST /chat/stream
│       │   ├── ingest.py     # POST /ingest
│       │   ├── history.py    # GET/DELETE /history
│       │   └── search.py     # GET /search (debug)
│       ├── core/
│       │   ├── config.py     # Pydantic Settings
│       │   ├── security.py   # Auth, CORS, rate limit
│       │   └── logging.py    # Structured logging
│       ├── rag/
│       │   ├── chunker.py
│       │   ├── embedder.py
│       │   ├── hybrid_search.py   # Dense + Sparse + RRF
│       │   ├── retriever.py       # Orchestrate hybrid search
│       │   ├── reranker.py        # Cross-encoder reranking
│       │   ├── web_search.py      # Tavily API client
│       │   ├── generator.py       # LLM + prompt builder
│       │   └── pipeline.py        # Orchestrate toàn bộ
│       ├── memory/
│       │   ├── mongo_store.py     # Motor async CRUD
│       │   ├── history_manager.py # Load & trim context
│       │   └── session.py         # Session lifecycle
│       ├── models/
│       ├── services/
│       ├── db/
│       │   ├── vector_db.py
│       │   ├── bm25_store.py
│       │   └── mongo.py
│       └── main.py
│
├── docker/
│   ├── Dockerfile.frontend
│   └── Dockerfile.backend
├── docker-compose.yml
├── .github/workflows/
└── .env.example
```

---

## Yêu cầu hệ thống

| Công cụ | Phiên bản tối thiểu |
|---------|---------------------|
| Python  | 3.11+               |
| Node.js | 18+                 |
| Docker  | 24+                 |
| Docker Compose | 2.20+        |

---

## Cài đặt & chạy local

### 1. Clone repo

```bash
git clone https://github.com/your-org/rag-chatbot.git
cd rag-chatbot
```

### 2. Cấu hình biến môi trường

```bash
cp .env.example .env
# Chỉnh sửa .env — xem mục Biến môi trường bên dưới

cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 3. Chạy với Docker Compose _(khuyến nghị)_

```bash
docker compose up --build
```

Sau khi khởi động:

| Service   | URL                        |
|-----------|----------------------------|
| Frontend  | http://localhost:5173      |
| Backend   | http://localhost:8000      |
| API Docs  | http://localhost:8000/docs |
| MongoDB   | mongodb://localhost:27017  |

### 4. Chạy từng service riêng lẻ _(development)_

**Backend:**

```bash
cd backend
pip install poetry
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

---

## Biến môi trường

### Backend (`backend/.env`)

```env
# LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...   # Nếu dùng Claude

# Embedding
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSION=3072

# Vector DB (chọn một)
VECTOR_DB_PROVIDER=pinecone    # pinecone | weaviate | qdrant
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=rag-chatbot

# BM25
BM25_STORE_PATH=./data/bm25_index

# Reranker (chọn một)
RERANKER_PROVIDER=cohere       # cohere | bge
COHERE_API_KEY=...
RERANK_TOP_N=5

# Tavily Web Search
TAVILY_API_KEY=tvly-...
TAVILY_SEARCH_DEPTH=advanced
WEB_SEARCH_THRESHOLD=0.4       # Score dưới ngưỡng này → gọi Tavily

# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=rag_chatbot
HISTORY_MAX_MESSAGES=20        # Số messages giữ trong context

# App
APP_ENV=development
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=http://localhost:5173
```

### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:8000
VITE_API_VERSION=v1
```

### Root (`.env`) — dùng cho Docker Compose

```env
COMPOSE_PROJECT_NAME=rag-chatbot
BACKEND_PORT=8000
FRONTEND_PORT=5173
MONGO_PORT=27017
```

---

## API Reference

### `POST /api/v1/chat/stream`

Gửi query và nhận response dạng SSE stream.

**Request body:**
```json
{
  "session_id": "uuid-v4",
  "query": "Tóm tắt tài liệu về chính sách bảo mật",
  "use_web_search": true
}
```

**Response:** `text/event-stream`
```
data: {"type": "chunk", "content": "Theo tài liệu..."}
data: {"type": "sources", "items": [{"title": "...", "url": "..."}]}
data: {"type": "done"}
```

---

### `POST /api/v1/ingest`

Upload và index tài liệu vào knowledge base.

**Request:** `multipart/form-data`
```
file: <file>          # PDF, TXT, MD, HTML
chunk_size: 512       # optional, default 512
chunk_overlap: 50     # optional, default 50
```

**Response:**
```json
{
  "status": "success",
  "chunks_indexed": 42,
  "document_id": "doc_abc123"
}
```

---

### `GET /api/v1/history/{session_id}`

Lấy lịch sử hội thoại của một session.

**Response:**
```json
{
  "session_id": "uuid-v4",
  "messages": [
    {"role": "user", "content": "...", "created_at": "2025-01-01T00:00:00Z"},
    {"role": "assistant", "content": "...", "sources": [...]}
  ]
}
```

---

### `DELETE /api/v1/history/{session_id}`

Xóa toàn bộ lịch sử của một session.

---

### `GET /api/v1/search?q={query}&top_k=10`

Endpoint debug — chạy hybrid search + rerank và trả kết quả raw, không qua LLM.

---

## Pipeline chi tiết

### Hybrid Search + RRF

`hybrid_search.py` chạy song song hai nhánh:

- **Dense search** — embed query, ANN lookup trong vector DB (cosine similarity)
- **Sparse search** — BM25 keyword matching trên BM25 store

Kết quả được merge bằng **Reciprocal Rank Fusion**:

```
RRF_score(doc) = Σ 1 / (k + rank_i)   với k=60
```

### Reranking

`reranker.py` nhận top-k từ RRF (mặc định 20), dùng cross-encoder để score lại từng cặp `(query, chunk)`, trả về top-n (mặc định 5) cho generator. Hỗ trợ Cohere Rerank và `BAAI/bge-reranker-v2-m3`.

### Tavily Web Search

`pipeline.py` gọi Tavily khi:
- Max rerank score < `WEB_SEARCH_THRESHOLD` (mặc định 0.4), hoặc
- Query chứa từ khoá liên quan thời sự (`"hôm nay"`, `"mới nhất"`, `"2025"`, ...)

Kết quả web được thêm vào context với nhãn `[Web]` để LLM phân biệt nguồn.

### MongoDB Memory

Mỗi conversation là một `Session` document. Messages được lưu embedded trong session. `history_manager.py` load N messages gần nhất (cấu hình qua `HISTORY_MAX_MESSAGES`) và tự động trim khi tổng token vượt ngưỡng context window của LLM.

---

## Chạy tests

```bash
cd backend

# Tất cả tests
poetry run pytest

# Chỉ RAG pipeline
poetry run pytest tests/rag/ -v

# Chỉ memory layer
poetry run pytest tests/memory/ -v

# Với coverage report
poetry run pytest --cov=app --cov-report=html
```

```bash
cd frontend

# Unit tests
npm run test

# Watch mode
npm run test:watch
```

---

## Deploy

### Docker Compose (production)

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Biến môi trường production cần thêm

```env
APP_ENV=production
SECRET_KEY=<random-64-char-string>
ALLOWED_ORIGINS=https://your-domain.com
MONGODB_URL=mongodb+srv://...   # MongoDB Atlas
```

### CI/CD

GitHub Actions tự động chạy khi push:
- `ci.yml` — chạy `pytest` + `vitest`, kiểm tra lint
- `deploy.yml` — build Docker image, push lên registry khi merge vào `main`

---

## Pre-commit hooks

Dự án dùng [pre-commit](https://pre-commit.com/) để tự động kiểm tra code trước mỗi commit.

```bash
pip install pre-commit
pre-commit install   # chạy một lần sau khi clone
```

Hooks được cấu hình trong [`.pre-commit-config.yaml`](.pre-commit-config.yaml):

| Hook | Mục đích |
|------|----------|
| `black` | Format code Python tự động |
| `trailing-whitespace` | Xóa khoảng trắng thừa cuối dòng |
| `end-of-file-fixer` | Đảm bảo file kết thúc bằng newline |

Chạy thủ công trên toàn bộ codebase:

```bash
pre-commit run --all-files
```

---

## Đóng góp

1. Fork repo và tạo branch mới: `git checkout -b feature/ten-tinh-nang`
2. Commit theo convention: `feat:`, `fix:`, `docs:`, `refactor:`
3. Mở Pull Request — mô tả rõ thay đổi và test đã chạy
4. Đảm bảo `pytest` và `vitest` pass trước khi tạo PR

---

## License

MIT © 2025 — RAG Chatbot Project
