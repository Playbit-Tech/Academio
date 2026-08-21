# Stack Research: Academio AI Engine (Python)

**Component:** `ai-engine/` — Python 3.13 FastAPI microservice (root submodule, `Playbits/Academio-AI`)
**Researched:** 2026-07-31
**Overall confidence:** HIGH (all critical versions verified against official sources / PyPI / Docker Hub, July 2026)

## Executive Summary

The Academio AI Platform adds a Python FastAPI service for document intelligence (OCR/PDF/DOCX/PPTX parsing), chunking/embeddings, and multi-provider LLM streaming. The existing Go stack (Gin/GORM/PostgreSQL 18/Redis/asynq) is **unchanged** — Python is additive, called over REST/JSON + SSE from Go workers and the frontend, with a gRPC-ready seam. Vector storage migrates from Qdrant to pgvector on the existing PostgreSQL 18 instance via the `pgvector/pgvector` image.

The stack is deliberately **small and modern**: FastAPI 0.140.x (native SSE since 0.135.0, so `sse-starlette` is obsolete), `uv` as the 2026-standard package manager, direct provider SDKs (`anthropic` + `openai`) instead of LiteLLM (Go's ModelRouter already owns routing/failover — LiteLLM would add ~7.5ms latency and duplicate logic), Docling for structured document parsing with its built-in `HybridChunker`, psycopg 3 + `pgvector-python` for async pgvector access (no SQLAlchemy — Go owns the schema), and pytest + testcontainers for testing.

Two critical constraints drive the design: **(1)** the pgvector HNSW index caps at 2000 dimensions on the `vector` type (text-embedding-3-large is 3072 → requires `halfvec` or a smaller embedding model), and **(2)** the `VECTOR(n)` column dimension is fixed at DDL time, so Go and Python **must** agree on a single embedding model/dimension when writing to the same `ai_vectors` table.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why |
|---|---|---|---|
| Python | 3.13.x | Runtime | FastAPI 0.140, Pydantic 2.13, Docling 2.x, anthropic 0.120, pytesseract, prometheus-fastapi-instrumentator 8.x all verified Python 3.13 compatible. Py3.13 is the current stable line in 2026. |
| FastAPI | 0.140.x | HTTP framework | Async-native, Pydantic v2 validation, OpenAPI docs out of the box, **native SSE** (`fastapi.sse.EventSourceResponse`) since 0.135.0. Verified latest 0.140.13 (2026-07-28). |
| Uvicorn | via `fastapi[standard]` | ASGI server | Standard extras bundle (uvloop, http-tools). Use `uvicorn` with multiple workers behind a proxy in prod; single process fine in container. |
| Pydantic | 2.13.x | Validation + settings | FastAPI 0.140 requires Pydantic ≥2.7; v2.13.4 is current stable (2026-05). `pydantic-settings` (bundled in `fastapi[standard]`) for env-var config, matching Go's fail-fast config philosophy (Rule B12). |
| uv | latest (0.7.x) | Package/project manager | The 2026 standard (Astral). Replaces pip+venv+poetry+pyenv: `pyproject.toml` + `uv.lock`, 10–100x faster, manages Python versions itself. |
| psycopg (v3) + `pgvector-python` | 3.2.x + 0.4.x | Async Postgres + pgvector client | First-class pgvector support (INSERT/Search/Delete with metadata filters), native `AsyncConnectionPool`, no ORM needed. |
| anthropic SDK | 0.120.x | Claude client | Official SDK, native async, Python ≥3.9 (verified 0.120.2, 2026-07-28). Claude 4.x models. |
| openai SDK | latest (1.x+) | OpenAI + Azure + DeepSeek + OpenRouter + Ollama | One SDK, five providers: Azure (`AzureOpenAI`), DeepSeek (`base_url=https://api.deepseek.com`), OpenRouter (`base_url=.../api/v1`), Ollama (`base_url=http://host:11434/v1`) are all OpenAI-compatible. Also used for embeddings (`text-embedding-3-*`, Azure, Ollama nomic-embed-text). |
| Docling | 2.x | Structured document parsing + chunking | PDF/DOCX/PPTX/HTML → typed `DoclingDocument` → Markdown with layout/reading-order/tables. Built-in `HybridChunker` (tokenizer-aligned chunking with heading metadata). MIT license, LF AI & Data. Python 3.13 supported. Heavy: pulls torch (~2.5 GB image). |
| PyMuPDF | 1.25.x | Fast digital-PDF text + rendering | ~10x faster than pypdf on digital PDFs; render pages to images for OCR fallback. |
| pytesseract | 0.3.13 | Image OCR | Python 3.13 support confirmed (madmaze/pytesseract#567). Needs `tesseract-ocr` system package (with `tesseract-ocr-eng`, plus optional language packs). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---|---|---|---|
| prometheus-fastapi-instrumentator | 8.0.2 | `/metrics` endpoint | Always (verified 2026-06, Python ≥3.10, starlette-1.0 compatible) |
| structlog | 25.x | Structured JSON logging | Always — matches Go `pkg/logger` philosophy (Rule B3); X-Request-ID propagation middleware |
| orjson | latest | Fast JSON | Optional hot paths; FastAPI `default_response_class=ORJSONResponse` |
| tiktoken | latest | Token counting for HybridChunker | With OpenAI-compatible embedders (`docling-core[chunking-openai]` extra) |
| httpx | latest | Async HTTP client + test client | Tests (ASGITransport) and outbound calls |
| pytest + pytest-asyncio | 8.x | Testing | `asyncio_mode=auto`; httpx `AsyncClient` replaces TestClient (per FastAPI discussion #8415) |
| testcontainers[postgres] | latest | Integration tests | Spin up `pgvector/pgvector:0.8.6-pg18` for pgvector integration tests |
| redis-py | latest | Embedding/response cache, event publish | Only if Python needs direct Redis (Go owns queueing; INT-03 caching may live in Go) — optional in v1 |

### Development Tools

| Tool | Version | Purpose |
|---|---|---|
| ruff | latest | Lint + format (2026 standard, replaces black/isort/flake8) |
| pyright | latest | Type checking (better Pydantic v2 support than mypy) |
| pre-commit | latest | Hook consistency |
| make | — | Wrap `uv sync`, `uv run pytest`, docker build (matches repo Makefile convention) |

---

## Installation

```bash
# Bootstrap (uv manages Python 3.13 itself)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13

# In ai-engine/ submodule
cd ai-engine
uv init --python 3.13
uv add "fastapi[standard]"           # FastAPI + uvicorn + pydantic-settings
uv add psycopg[binary] pgvector-python
uv add anthropic openai
uv add docling[chunking-openai]      # HybridChunker with tiktoken; swap to [chunking] for HF tokenizers
uv add pymupdf pytesseract
uv add prometheus-fastapi-instrumentator structlog orjson httpx
uv add --dev pytest pytest-asyncio pytest-cov pytest-httpx testcontainers[postgres] ruff pyright

# System deps (Dockerfile apt layer)
apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng
```

Dockerfile base: `python:3.13-slim`, uv via `ghcr.io/astral-sh/uv:latest` multi-stage; cache `uv sync --no-dev` before copying source. If Docling's torch weight is a concern, see the light-path variant below.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Package manager | uv | poetry / pip | uv is the 2026 standard; poetry/pip are slower and don't manage Python versions |
| LLM gateway | Direct SDKs (anthropic + openai) | LiteLLM | Go ModelRouter already owns routing/failover/circuit-breaking. LiteLLM adds ~7.5ms overhead per call and duplicates that role. Direct SDKs = fewer deps, full control of cost/token accounting. **Revisit LiteLLM only** if a 100+ provider breadth is needed later. |
| SSE | FastAPI native (`fastapi.sse`) | sse-starlette | Native since FastAPI 0.135.0; one less dependency; `ServerSentEvent` covers `event:` + `data:` framing for token/done events |
| Document parsing | Docling | Marker / MinerU | Marker/MinerU are GPU-bound and heavier; Docling is CPU-viable and the balanced 2026 choice for structured extraction |
| Chunking | Docling HybridChunker | LangChain/LlamaIndex text splitters | Framework weight for ~50 lines of logic; HybridChunker is tokenizer-aligned with the embedder and emits heading metadata for free |
| Vector client | psycopg 3 + pgvector-python | asyncpg | pgvector-python has first-class psycopg3 support; asyncpg lacks server-side binding depth and COPY; no SQLAlchemy needed since Go owns DDL |
| ORM / migrations | none | SQLAlchemy + Alembic | Go owns schema + migrations (PGV-04 `ai_vectors`). Python only inserts/queries vectors. SQLAlchemy = dead weight. |
| OCR | pytesseract | OCRmyPDF | OCRmyPDF wraps ghostscript+tesseract for PDF/A artifacts — add only if searchable-PDF deliverables are confirmed |
| Task queue | none (HTTP + SSE sync call) | Celery | Go/asynq owns the queue; Python is invoked over HTTP (locked decision). Celery would invert the architecture. |
| RAG framework | none (Docling + direct SDKs) | LangChain / LlamaIndex | Orchestration pipeline is owned by our Go workers + thin Python services; frameworks add weight without value here |

---

## What NOT to Use

| Item | Why |
|---|---|
| `sse-starlette` | Superseded by FastAPI native SSE (0.135+) |
| poetry / pipenv | uv replaces both |
| asyncpg as primary | psycopg3 + pgvector-python is the better-fit path; pgvector-python supports asyncpg only as fallback |
| SQLAlchemy / Alembic | Go owns schema; Python is a data-plane client |
| LangChain / LlamaIndex | Framework weight; our pipeline is Go-orchestrated |
| LiteLLM as primary path | Latency overhead + routing duplication with Go ModelRouter (keep as documented fallback) |
| Celery / Dramatiq | Go/asynq owns the queue |
| WebSockets for streaming | Locked transport is SSE (unidirectional LLM streaming, proxy-friendly, Go `text/event-stream` consumer) |
| pypdf | Slow pure-Python; PyMuPDF is ~10x faster |
| textract | Unmaintained |
| unstructured | Heavy, unstable dependency tree; Docling is the stable choice |

---

## Stack Patterns by Variant

### Standard (quality-first, default)
- **Docling** full pipeline for PDF/DOCX/PPTX/HTML → Markdown + `HybridChunker`
- torch CPU wheels; image ~2.5 GB
- Chunk metadata (headings, provenance) → `ai_vectors.metadata` JSONB

### Light path (image-size-constrained)
- PyMuPDF (`pymupdf4llm`) for digital PDFs + `python-docx`/`python-pptx`/`openpyxl` native parsing; pytesseract for images only
- No torch, image < 600 MB
- Custom chunker (~50 lines) or Docling `docling-core` without torch when structure is not needed

### Streaming
- `/v1/chat/stream` → `EventSourceResponse` yielding `ServerSentEvent(event="token", data=...)` and final `event="done", data="[DONE]"`; heartbeat ping every 15s
- Go consumer: `text/event-stream` reader with `X-Request-ID` propagation

### Testing
- pytest + `pytest-asyncio` (`asyncio_mode=auto`) + httpx `AsyncClient`
- `pytest-httpx` to mock outbound LLM calls; `testcontainers[postgres]` with `pgvector/pgvector:0.8.6-pg18` for vector integration tests
- Match Go integration-test convention (`backend/scripts/test_endpoint.sh` analog)

---

## Version Compatibility (Python 3.13 + pgvector-on-PG18)

| Component | Py 3.13 | PG 18 | pgvector | Verified |
|---|---|---|---|---|
| FastAPI 0.140.x | ✅ (3.10+) | — | — | PyPI (2026-07-28) |
| Pydantic 2.13.x | ✅ | — | — | PyPI |
| anthropic 0.120.x | ✅ (≥3.9) | — | — | PyPI (2026-07-28) |
| openai SDK | ✅ | — | — | PyPI |
| psycopg 3.2.x | ✅ | ✅ | ✅ | official |
| pgvector-python 0.4.x | ✅ | ✅ | ✅ | PyPI (2026-07-06) |
| Docling 2.x | ✅ (issue #136 closed) | — | — | GitHub |
| pytesseract 0.3.13 | ✅ (issue #567) | — | — | GitHub |
| prometheus-fastapi-instrumentator 8.0.2 | ✅ (3.10–3.14) | — | — | PyPI |
| pgvector/pgvector image | — | ✅ `0.8.6-pg18-trixie` | 0.8.x | Docker Hub (updated ~1 day ago) |

### Critical compatibility constraints

1. **HNSW 2000-dim cap** — pgvector `vector` type HNSW index supports max 2000 dims. `text-embedding-3-large` (3072) **cannot** use HNSW on `vector`. Either: default to `text-embedding-3-small` (1536) / Gemini 768, or use `halfvec` (pgvector 0.7+, HNSW to 4000 dims). **Default: 1536-dim embeddings.**
2. **Fixed column dimension** — `VECTOR(n)` dim is locked at DDL. Go embedder and Python embedder writing to the same `ai_vectors` table **must share one embedding model + dimension**. Coordinate via shared config (env var) — a mismatch causes silent insert failures.
3. **CVE-2026-3172** — pgvector < 0.8.2 affected. Pin `pgvector/pgvector:0.8.6-pg18` (>= 0.8.2).
4. **No multi-statement Exec** — psycopg 3 `execute()` does not batch; irrelevant here since Go owns DDL, but keep for any Python-side DDL.
5. **SSE behind proxies** — disable proxy buffering for `/v1/chat/stream` if a reverse proxy sits between Go and Python; internal docker network is fine as-is.

---

## Sources

| Source | Confidence |
|---|---|
| PyPI: FastAPI 0.140.13 (2026-07-28), native SSE docs page, Pydantic 2.13.4 | HIGH |
| PyPI: anthropic 0.120.2 (2026-07-28), Python >=3.9 | HIGH |
| Docker Hub: `pgvector/pgvector:0.8.6-pg18-trixie` (updated 2026-07-30), 0.8.x supports PG 13–18 | HIGH |
| PyPI: pgvector-python (2026-07-06), supports psycopg 3/asyncpg/SQLAlchemy | HIGH |
| IBM Docling docs: HybridChunker, chunking extras, Py3.13 issue #136 | HIGH |
| GitHub: madmaze/pytesseract#567 (Py3.13) | HIGH |
| PyPI: prometheus-fastapi-instrumentator 8.0.2 (2026-06), Py >=3.10 | HIGH |
| Astral uv docs (FastAPI integration guide) | HIGH |
| FastAPI discussion #8415 (AsyncClient over TestClient) | MEDIUM |
| PyMuPDF vs Docling benchmark article | MEDIUM (direction corroborated by multiple sources) |

**Confidence: HIGH overall.** Every pinned version verified against PyPI/Docker Hub/GitHub in July 2026. Remaining MEDIUM items are behavioral (not version) claims: async-client guidance and parsing benchmarks.
