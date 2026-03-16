# Multi-LLM RAG Agent

A production-ready, fully containerized **Retrieval-Augmented Generation (RAG)** chatbot that intelligently routes queries between OpenAI GPT-4o and Google Gemini based on query complexity, with human feedback (RLHF) continuously improving retrieval quality.

---

## Table of Contents

1. [Features](#features)
2. [Architecture Overview](#architecture-overview)
3. [Component Breakdown](#component-breakdown)
   - [Frontend](#frontend-react--vite)
   - [Backend API](#backend-api-fastapi)
   - [Document Ingestion Pipeline](#document-ingestion-pipeline)
   - [Chunking Strategy](#chunking-strategy-semantic--adaptive)
   - [Vector Store](#vector-store-chromadb)
   - [Retrieval Service](#retrieval-service)
   - [LLM Gateway & Complexity Routing](#llm-gateway--complexity-routing)
   - [RLHF Feedback Loop](#rlhf-feedback-loop)
4. [Key Design Decisions](#key-design-decisions)
5. [API Reference](#api-reference)
6. [Configuration](#configuration)
7. [Quick Start](#quick-start)
8. [Local Development (without Docker)](#local-development-without-docker)
9. [Extending the System](#extending-the-system)
10. [Project Structure](#project-structure)
11. [License](#license)

---

## Features

| Capability | Detail |
|---|---|
| **Document Upload** | PDF, Word (`.docx`, `.doc`) via drag-and-drop |
| **Web Ingestion** | Any public URL — scraped and embedded |
| **Live Ingestion Status** | Polling UI with status badges (Queued → Processing → Completed / Failed) |
| **Multi-turn Chat** | Conversation history maintained per browser session |
| **Clear Chat History** | One-click session reset (client + server) |
| **Dual-LLM Routing** | GPT-4o for complex queries, Gemini Flash for simple ones |
| **RLHF Feedback** | 👍 / 👎 per response — adjusts future retrieval scores |
| **Source Attribution** | Every answer links back to the exact chunks it was drawn from |
| **Containerised** | Full Docker Compose stack — single command to run |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (React SPA)                         │
│                                                                     │
│  ┌───────────────────────┐   ┌───────────────────────────────────┐  │
│  │     Upload Panel      │   │          Chat Window              │  │
│  │  - Drag & drop files  │   │  - Multi-turn conversation        │  │
│  │  - URL input          │   │  - Markdown rendering             │  │
│  │  - Ingestion status   │   │  - Source attribution             │  │
│  │    (live polling)     │   │  - 👍/👎 RLHF feedback buttons    │  │
│  └──────────┬────────────┘   └──────────────┬────────────────────┘  │
└─────────────┼──────────────────────────────┼───────────────────────┘
              │ HTTP (nginx proxy)            │ HTTP
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                               │
│                                                                     │
│  POST /ingest/document   POST /ingest/url   GET /ingest/status/:id  │
│  POST /chat              POST /chat/clear                           │
│  POST /feedback                                                     │
│                                                                     │
│  ┌─────────────────────┐   ┌────────────────────────────────────┐  │
│  │  Ingestion Pipeline │   │          Chat Pipeline             │  │
│  │                     │   │                                    │  │
│  │  DocumentProcessor  │   │  RetrievalService                  │  │
│  │   ├─ PyPDFLoader    │   │   ├─ similarity_search (K=6)       │  │
│  │   ├─ Docx2txtLoader │   │   ├─ RLHF score lookup (SQLite)    │  │
│  │   └─ WebBaseLoader  │   │   └─ Re-rank → top K=3            │  │
│  │                     │   │                                    │  │
│  │  ChunkingService    │   │  LLMGateway                        │  │
│  │   ├─ SemanticChunker│   │   ├─ calculate_complexity()        │  │
│  │   └─ Recursive fallb│   │   ├─ score ≥ 0.4 → GPT-4o         │  │
│  │                     │   │   └─ score < 0.4 → Gemini Flash    │  │
│  │  VectorStoreService │   │                                    │  │
│  │   └─ ChromaDB       │   │  FeedbackService                   │  │
│  │                     │   │   └─ SQLite (chunk_feedback table)  │  │
│  └─────────────────────┘   └────────────────────────────────────┘  │
└───────────────────┬──────────────────────────────┬─────────────────┘
                    │                              │
          ┌─────────▼────────┐          ┌──────────▼──────────┐
          │    ChromaDB      │          │      SQLite DB       │
          │  (Docker volume) │          │   (Docker volume)    │
          │                  │          │                      │
          │  Collection:     │          │  Tables:             │
          │  rag_documents   │          │  - chunk_feedback    │
          │  Distance: cosine│          │  - responses         │
          └──────────────────┘          │  - feedback_events   │
                                        └──────────────────────┘
```

---

## Component Breakdown

### Frontend (React + Vite)

**Stack:** React 18, Vite, Axios, react-dropzone, react-markdown, uuid

The UI is a two-panel layout:

- **Left sidebar — Upload Panel**
  - Drag-and-drop zone for PDF / Word files (multiple at once)
  - URL input field for webpage ingestion
  - Live job cards that poll `/ingest/status/:id` every 2 seconds and display animated status badges

- **Right panel — Chat Window**
  - Multi-turn conversation with Markdown rendering (code blocks, lists, etc.)
  - Per-message source accordion showing retrieved chunk content, source name, and relevance score
  - Complexity score display (what percentage of the routing threshold was hit)
  - 👍 / 👎 RLHF feedback buttons below every assistant message
  - "Clear History" button (resets both browser state and backend session)

Each browser tab gets its own UUID-based `session_id` stored in `sessionStorage`. This is sent with every chat request so the backend can maintain per-session conversation history.

In Docker, nginx serves the static build and proxies all `/ingest`, `/chat`, `/feedback`, and `/health` paths to the FastAPI backend — so the frontend never needs to know the backend URL.

---

### Backend API (FastAPI)

**Stack:** FastAPI, uvicorn, Pydantic v2, LangChain, aiosqlite

Three routers, all async:

| Router | Endpoints |
|---|---|
| `ingest` | `POST /ingest/document`, `POST /ingest/url`, `GET /ingest/status/{job_id}` |
| `chat` | `POST /chat`, `POST /chat/clear` |
| `feedback` | `POST /feedback` |

Ingestion jobs run as FastAPI `BackgroundTasks` — the response returns immediately with a `job_id`, and the client polls for status. This keeps upload requests from timing out on large documents.

Conversation history is held in an in-memory dict keyed by `session_id`, capped at the last 10 turns (20 messages) to keep context window usage bounded.

---

### Document Ingestion Pipeline

```
Upload / URL
     │
     ▼
DocumentProcessor          (services/document_processor.py)
  ├─ .pdf  → PyPDFLoader   (langchain_community)
  ├─ .docx → Docx2txtLoader
  └─ URL   → WebBaseLoader (BeautifulSoup HTML parser)
     │
     ▼  documents: List[Document]  (with source metadata)
     │
ChunkingService            (services/chunking_service.py)
  └─ see Chunking Strategy below
     │
     ▼  chunks: List[Document]  (with chunk_id in metadata)
     │
VectorStoreService         (services/vector_store.py)
  └─ Chroma.add_documents(chunks, ids=[chunk.metadata["chunk_id"]])
```

Each chunk receives a **stable, deterministic `chunk_id`** generated as:
```python
chunk_id = f"{source}__{md5(page_content)[:12]}"
```
This ID is stored both in ChromaDB metadata and referenced by the SQLite feedback tables, creating the link between retrieval and RLHF scoring.

---

### Chunking Strategy (Semantic + Adaptive)

`services/chunking_service.py`

Two-phase approach:

**Phase 1 — Semantic Chunking**

Uses LangChain's `SemanticChunker` (`langchain_experimental`) with a **percentile breakpoint** strategy. Splits happen at sentence boundaries where the cosine distance between adjacent sentence embeddings exceeds a threshold percentile. This produces chunks that are semantically coherent rather than arbitrarily cut at a character limit.

**Phase 2 — Adaptive Parameters**

Parameters are automatically tuned based on document type:

| Source Type | Chunk Size | Overlap | Semantic Threshold |
|---|---|---|---|
| PDF | 1,000 chars | 150 | 85th percentile |
| Word (docx) | 800 chars | 100 | 80th percentile |
| Web (URL) | 500 chars | 75 | 75th percentile |

_Rationale:_ PDFs tend to be denser and more structured, so a higher threshold merges more content into each chunk. Web pages are shorter and more varied, so a lower threshold splits more aggressively to avoid mixing unrelated sections.

If any chunk exceeds `chunk_size × 2` after semantic splitting, a secondary `RecursiveCharacterTextSplitter` pass is applied. If `SemanticChunker` is unavailable or fails entirely, the system falls back to `RecursiveCharacterTextSplitter` with the same adaptive parameters.

---

### Vector Store (ChromaDB)

`services/vector_store.py`

- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` via `langchain_huggingface.HuggingFaceEmbeddings`
  - Free, no API key required
  - Pre-downloaded into the Docker image at build time (no cold-start delay)
  - 384-dimensional embeddings, normalised to unit vectors
- **Distance metric:** cosine similarity (`hnsw:space: cosine` in collection metadata)
- **Persistence:** ChromaDB runs in embedded mode with a Docker-managed volume at `/app/chroma_db`
- **Retrieval:** `similarity_search_with_relevance_scores` returns scores in [0, 1] where 1 = identical

**Swapping the vector store** is intentionally simple — all interaction is isolated in `VectorStoreService`. To switch to Qdrant, replace `get_store()` with a `QdrantVectorStore` instance; no other file changes are needed.

---

### Retrieval Service

`services/retrieval_service.py`

```
Query
  │
  ▼
ChromaDB similarity_search_with_relevance_scores(query, k=6)
  │   returns 6 candidates (2× final K)
  ▼
FeedbackService.get_chunk_scores(chunk_ids)
  │   SQLite lookup: net_score ∈ [-1.0, 1.0] per chunk
  ▼
Re-ranking formula per candidate:
  combined_score = 0.7 × cosine_similarity
                 + 0.3 × ((net_score + 1) / 2)
                          └─ maps [-1,1] to [0,1]
  ▼
Sort descending → return top K=3
```

The over-fetch (K=6) is necessary to give RLHF re-ranking room to reorder results. Without it, a highly-rated chunk that cosine-similarity ranked 4th would never be surfaced.

---

### LLM Gateway & Complexity Routing

`services/llm_gateway.py`

Every query is scored before an LLM is selected:

```python
complexity_score = calculate_complexity(query)  # → float in [0.0, 1.0]

if complexity_score >= 0.4:   # COMPLEXITY_THRESHOLD (configurable)
    llm = ChatOpenAI(model="gpt-5")
else:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
```

**Scoring factors** (all additive, clamped to [0.0, 1.0]):

| Factor | Score adjustment |
|---|---|
| Query length (per 50 words) | +0.0 → +0.20 |
| High-complexity keywords (`troubleshoot`, `architecture`, `kubernetes`, `deadlock`, …) | +0.12 each, capped at +0.36 |
| Medium-complexity keywords (`error`, `database`, `migrate`, …) | +0.06 each, capped at +0.18 |
| Analytical language (`compare`, `trade-off`, `best practice`, …) | +0.12 each, capped at +0.24 |
| Starts with `why` / `how to` / `how does` | +0.15 |
| Starts with `what is` / `define` / `list` / `who is` | −0.20 |
| Starts with `what` / `who` / `when` / `where` | −0.05 |
| Each additional `?` beyond the first | +0.15 |

**To tweak routing** without touching logic, edit the four constant sets at the top of `llm_gateway.py`:
- `_HIGH_COMPLEXITY_TERMS`
- `_MEDIUM_COMPLEXITY_TERMS`
- `_SIMPLE_STARTERS`
- `_ANALYTICAL_TERMS`

Or adjust `COMPLEXITY_THRESHOLD` in `.env`.

**RAG Chain (LangChain LCEL):**

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", _RAG_SYSTEM_PROMPT),   # injects retrieved context
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])
chain = prompt | llm | StrOutputParser()
answer = await chain.ainvoke({...})
```

---

### RLHF Feedback Loop

`services/feedback_service.py` + SQLite

**Storage schema:**

```sql
-- Per-chunk aggregate scores
chunk_feedback (
    chunk_id       TEXT PRIMARY KEY,
    positive_count INTEGER,
    negative_count INTEGER,
    net_score      REAL,   -- (pos - neg) / (pos + neg + 1) ∈ (-1, 1)
    last_updated   TIMESTAMP
)

-- Response registry (links response_id → chunk_ids)
responses (
    response_id    TEXT PRIMARY KEY,
    query          TEXT,
    answer         TEXT,
    llm_used       TEXT,
    chunk_ids      TEXT,   -- JSON array
    complexity_score REAL,
    session_id     TEXT,
    created_at     TIMESTAMP
)

-- Raw audit log for analysis / future fine-tuning
feedback_events (
    id          INTEGER PRIMARY KEY,
    response_id TEXT,
    rating      INTEGER,  -- +1 or -1
    query       TEXT,
    chunk_ids   TEXT,
    created_at  TIMESTAMP
)
```

**Flow:**

1. Each chat response is saved to `responses` with its `response_id` and `chunk_ids`
2. The frontend renders 👍 / 👎 buttons, storing `response_id` and `chunk_ids` in React state
3. On user click, `POST /feedback` → `record_feedback()` updates `chunk_feedback` for every chunk in that response
4. `net_score` uses a Laplace-smoothed formula:
   ```
   net_score = (positive - negative) / (positive + negative + 1)
   ```
   The `+1` denominator prevents division-by-zero and adds mild skepticism on sparse data
5. On the next retrieval for a similar query, those chunks receive the `FEEDBACK_WEIGHT × normalized_rlhf_score` boost (or penalty), reshaping the ranking without discarding cosine similarity entirely

**Future RLHF improvements** the `feedback_events` table enables:
- Export to a dataset for supervised fine-tuning of the LLM
- Preference-pair construction for DPO / PPO training
- Query-level analysis to auto-adjust the complexity threshold

---

## Key Design Decisions

### 1. Over-fetch then Re-rank (not post-filter)
Retrieving `K × 2 = 6` candidates before RLHF re-ranking ensures that a highly-rated chunk ranked 4th or 5th by cosine similarity is not silently discarded. The re-ranking step is O(K) and adds negligible latency.

### 2. Deterministic Chunk IDs
`chunk_id = f"{source}__{md5(content)[:12]}"` means the same content always gets the same ID. This makes re-ingestion idempotent (ChromaDB `add_documents` with explicit IDs upserts rather than duplicating) and keeps the SQLite feedback table stable across re-runs.

### 3. HuggingFace Embeddings (not OpenAI)
`all-MiniLM-L6-v2` is free, fast, and good enough for most RAG use cases. Embedding is done at ingest time and at query time — both use the same model, which is critical for cosine similarity to be meaningful. The model is baked into the Docker image at build time to eliminate first-request latency.

### 4. Embeddings Pre-downloaded at Build Time
The backend `Dockerfile` runs `SentenceTransformer('all-MiniLM-L6-v2')` during `docker build`. This adds ~80 MB to the image but means the first request is fast and the container starts without internet access.

### 5. Isolated Vector Store Layer
All ChromaDB interaction is in `services/vector_store.py` behind a small interface (`add_documents`, `similarity_search_with_scores`, `document_count`). To swap to Qdrant or Weaviate, only this file changes.

### 6. LCEL over Legacy LangChain Chains
`RetrievalQA` and `ConversationalRetrievalChain` are legacy patterns. The LCEL approach (`prompt | llm | StrOutputParser()`) is composable, async-native, and easier to extend with streaming or middleware.

### 7. Ingestion as Background Tasks
FastAPI's `BackgroundTasks` runs ingestion after the HTTP response is sent. This avoids gateway timeouts on large PDFs and gives the frontend a `job_id` to poll. The trade-off is that job state is in-memory (lost on restart), acceptable for a single-instance Docker deployment.

### 8. Complexity Threshold is a Single Float
`COMPLEXITY_THRESHOLD=0.4` in `.env` is the sole knob for LLM routing. Tuning is a one-line environment change; no code redeploy needed.

### 9. Session-scoped History, Capped at 10 Turns
Conversation history is kept in a server-side dict keyed by UUID session ID. Capping at 10 turns (20 messages) limits context window bloat and keeps inference costs predictable. The oldest messages are dropped first (sliding window).

---

## API Reference

### `POST /ingest/document`
Upload a PDF or Word file.

**Request:** `multipart/form-data`, field `file`

**Response:**
```json
{ "job_id": "uuid", "status": "pending", "message": "Job queued." }
```

---

### `POST /ingest/url`
Ingest a web page by URL.

**Request:**
```json
{ "url": "https://example.com/page" }
```

**Response:**
```json
{ "job_id": "uuid", "status": "pending", "message": "Job queued." }
```

---

### `GET /ingest/status/{job_id}`
Poll ingestion job status.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",          // pending | processing | completed | failed
  "message": "Successfully ingested 'report.pdf'.",
  "chunks_created": 42,
  "source": "report.pdf",
  "error": null
}
```

---

### `POST /chat`
Send a message and receive a RAG-grounded answer.

**Request:**
```json
{ "query": "How does TLS handshake work?", "session_id": "uuid" }
```

**Response:**
```json
{
  "response_id": "uuid",
  "answer": "TLS handshake begins with...",
  "sources": [
    { "content": "...(first 300 chars)...", "source": "networking-guide.pdf", "score": 0.87, "chunk_id": "..." }
  ],
  "llm_used": "gpt-5",
  "complexity_score": 0.53,
  "chunk_ids": ["id1", "id2", "id3"],
  "session_id": "uuid"
}
```

---

### `POST /chat/clear`
Clear conversation history for a session.

**Request:**
```json
{ "session_id": "uuid" }
```

---

### `POST /feedback`
Submit thumbs up (+1) or thumbs down (−1) on a response.

**Request:**
```json
{
  "response_id": "uuid",
  "rating": 1,
  "query": "How does TLS handshake work?",
  "chunk_ids": ["id1", "id2", "id3"]
}
```

---

## Configuration

All settings live in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `GOOGLE_API_KEY` | *(required)* | Google AI Studio API key |
| `OPENAI_MODEL` | `gpt-5` | OpenAI model for complex queries |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model for simple queries |
| `COMPLEXITY_THRESHOLD` | `0.4` | Score above which queries go to OpenAI |
| `RETRIEVAL_K` | `3` | Final number of chunks sent to LLM |
| `RETRIEVAL_CANDIDATES` | `6` | Candidates fetched before RLHF re-rank |
| `SIMILARITY_WEIGHT` | `0.7` | Weight of cosine similarity in final score |
| `FEEDBACK_WEIGHT` | `0.3` | Weight of RLHF score in final score |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace sentence-transformer model |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `CHROMA_COLLECTION_NAME` | `rag_documents` | ChromaDB collection name |
| `MAX_FILE_SIZE_MB` | `50` | Max upload file size |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API key ([platform.openai.com](https://platform.openai.com))
- Google AI Studio API key ([aistudio.google.com](https://aistudio.google.com))

### Steps

```bash
# 1. Clone / navigate to the project
cd multi-llm-rag-agent-chat

# 2. Configure API keys
cp .env.example .env
# Edit .env and fill in OPENAI_API_KEY and GOOGLE_API_KEY

# 3. Build and start all services
docker compose up --build

# First build downloads the embedding model (~80 MB).
# Subsequent starts are fast.
```

Open **http://localhost:3000** in your browser.

| Service | URL |
|---|---|
| Frontend (React) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

### Stopping

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop + wipe ChromaDB and feedback data
```

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env     # fill in keys
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                  # → http://localhost:5173
```

The Vite dev server proxies all `/ingest`, `/chat`, `/feedback` calls to `localhost:8000` automatically (configured in `vite.config.js`).

---

## Extending the System

### Swap the Vector Database

Replace the contents of `backend/services/vector_store.py`. The rest of the system uses only:
- `add_documents(chunks: List[Document]) -> List[str]`
- `similarity_search_with_scores(query: str, k: int) -> List[Tuple[Document, float]]`
- `get_embeddings() -> Embeddings`

**Example — Qdrant:**
```python
from langchain_qdrant import QdrantVectorStore
self._store = QdrantVectorStore.from_existing_collection(
    embedding=self._get_embeddings(),
    collection_name=settings.CHROMA_COLLECTION_NAME,
    url="http://qdrant:6333",
)
```

### Add a New LLM

In `services/llm_gateway.py`, extend `_build_llm()`:
```python
elif complexity_score >= 0.7:
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model="claude-opus-4-6"), "claude-opus-4-6"
```

### Add a New Document Type

In `services/document_processor.py`, add a loader to `load_file()`:
```python
elif ext == ".txt":
    from langchain_community.document_loaders import TextLoader
    loader = TextLoader(tmp_path)
    return loader.load(), "text"
```
Then add adaptive chunk params in `chunking_service.py`'s `CHUNK_PARAMS` dict.

### Enable Streaming Responses

Replace the LCEL chain output parser with a streaming approach in `llm_gateway.py` and add a `StreamingResponse` in the chat router.

---

## Project Structure

```
multi-llm-rag-agent-chat/
│
├── .env.example                   # Template for all config vars
├── docker-compose.yml             # Orchestrates backend + frontend
│
├── backend/
│   ├── Dockerfile                 # python:3.12-slim, pre-downloads embedding model
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app, CORS, router registration, DB init
│   ├── config.py                  # Pydantic Settings — all env vars in one place
│   ├── database.py                # SQLite schema + async init
│   │
│   ├── models/
│   │   └── schemas.py             # All Pydantic request/response models
│   │
│   ├── routers/
│   │   ├── ingest.py              # /ingest/document, /ingest/url, /ingest/status/:id
│   │   ├── chat.py                # /chat, /chat/clear
│   │   └── feedback.py            # /feedback
│   │
│   └── services/
│       ├── document_processor.py  # PDF / Word / URL loaders
│       ├── chunking_service.py    # SemanticChunker + adaptive fallback
│       ├── vector_store.py        # ChromaDB wrapper (swap here to change DB)
│       ├── retrieval_service.py   # Cosine search + RLHF re-ranking
│       ├── llm_gateway.py         # Complexity scoring + LLM routing + RAG chain
│       └── feedback_service.py    # SQLite read/write for RLHF scores
│
└── frontend/
    ├── Dockerfile                 # Multi-stage: node build → nginx serve
    ├── nginx.conf                 # SPA routing + API proxy to backend
    ├── package.json
    ├── vite.config.js             # Dev proxy config
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                # Two-panel layout (sidebar + chat)
        ├── App.css                # Dark theme, layout, animations
        ├── api/
        │   └── client.js          # Axios wrappers for all backend endpoints
        └── components/
            ├── UploadPanel.jsx    # Drag-drop, URL input, job cards, polling
            ├── ChatWindow.jsx     # Message list, input, session management
            ├── MessageBubble.jsx  # Single message with sources + feedback
            ├── FeedbackButtons.jsx # 👍/👎 with one-shot submit logic
            └── StatusBadge.jsx    # Animated status pill (pending/processing/…)
```

---

## License

This project is licensed under the [MIT License](LICENSE).
