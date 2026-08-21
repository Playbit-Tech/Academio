# Task Context: Phase 3 — Python AI Engine

Phase: 03-python-ai-engine
Status: context-gathering
Created: 2026-08-01 (after Phase 2 verified 5/5)

## Goal

A stateless Python compute service provides multi-provider LLM access, document
intelligence, embeddings, and tenant-aware RAG behind a gRPC-ready contract —
the engine the Go pipeline and streaming layers call into. Phase 1 laid the
skeleton (`/health` + token-protected `/v1/health`); Phase 3 builds the full
engine: chat (5 providers), SSE streaming, extract/documents, embeddings,
search, providers status, and the versioned prompt library.

## Requirements (from REQUIREMENTS.md)

- **PYE-01**: Python multi-provider abstraction (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama) via direct SDKs; NO Python gateway, NO LiteLLM
- **PYE-02**: Document intelligence: PDF, DOCX, PPTX, TXT, CSV, image OCR (Tesseract), chunking, embeddings, semantic search, re-ranking, knowledge indexing
- **PYE-03**: Versioned prompt library (report comments, lesson plans, questions, rubrics, behaviour summary, attendance analysis, parent letters, meeting minutes, translation)
- **PYE-04**: Python endpoints: `/health`, `/v1/chat`, `/v1/chat/stream` (SSE), `/v1/embed`, `/v1/extract`, `/v1/documents`, `/v1/search`, `/v1/providers`
- **PYE-04a**: `proto/aiengine.proto` gRPC contract written at START of phase (transports over REST in v1)
- **PYE-05**: Tenant-aware RAG in Python (hybrid search, metadata filtering, chunk ranking, citations, context compression)

## ROADMAP Success Criteria (what must be TRUE)

1. `proto/aiengine.proto` committed as the gRPC contract (Chat, ChatStream, Embed, Extract, IngestDocument, Search) at the START of the phase; every REST endpoint satisfies its request/response semantics 1:1 (transport stays REST/JSON + SSE in v1).
2. `/v1/chat` and `/v1/chat/stream` (native SSE: `text/event-stream`, heartbeats ≤30s, no gzip) serve conversations through all five new providers — Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama — via direct SDKs (`anthropic` + `openai` with `base_url`), returning a normalized usage payload (provider, model, input/output tokens, cost) on every response; NO LiteLLM, NO Python gateway.
3. `/v1/providers` returns live per-provider status (health, cooldowns) for Go's INT-02; `/v1/embed` produces canonical-model embeddings matching `ai_vectors`' locked dimension (1536).
4. `/v1/extract` and `/v1/documents` parse PDF/DOCX/PPTX/TXT/CSV/images with per-page routing (digital → fast text parser, scanned → Tesseract OCR at ≥300 DPI) and quality gates; `/v1/documents` performs extract → chunk → embed → store in ONE call, writing to the validated `school_{id}` schema; every DB access validates `schema_name` against `^school_\d+$` with no global fallback.
5. `/v1/search` returns hybrid retrieval (dense + BM25/RRF) with metadata filters, chunk ranking, citations, and context compression, scoped to the request's schema; the versioned prompt library (Git-backed YAML, dev/staging/prod aliases) serves every PYE-03 template; the service stays stateless (no Celery, no user auth, no queue — service token only).

## Existing State (verified)

### ai-engine/ (Phase 1 skeleton, committed)
- `app/main.py`: FastAPI app, `require_token` dependency (X-AI-Engine-Token header, 401 if empty/mismatch — service token only, never user JWT)
- `app/config.py`: pydantic-settings `Settings` with `AI_ENGINE_TOKEN`
- `pyproject.toml`: Python 3.13, `fastapi[standard]>=0.140,<0.141`, `pydantic-settings>=2.13`; dev: pytest, pytest-asyncio, ruff (E,F,W,I,UP,B), pyright; asyncio_mode=auto
- `tests/test_health.py`: health tests
- `Dockerfile`: multi-stage, python:3.13-slim, uv
- `Makefile`, `uv.lock` committed, `.python-version`
- Phase 1 CI: root `ai-engine.yml` (setup-uv v9.0.0, uv sync --frozen)

### Go EngineClient seam (Phase 1, must stay compatible)
- `backend/internal/ai/engine/engine.go`: `EngineClient` interface — `Chat(ctx, ChatRequest)`, `ChatStream(ctx, ChatRequest, cb)`, `Extract(ctx, ExtractRequest)`, `Health(ctx)`
- `ChatRequest{Model, Messages[]ChatMessage{Role,Content}, Stream}`, `ChatResponse{Message}`, `ExtractRequest{DocumentPath}` (absolute path in shared uploads volume), `ExtractResponse{Status}`
- `client.go` routes: POST `/v1/chat`, POST `/v1/chat/stream`, POST `/v1/extract`, GET `/v1/health`
- Go tests in `client_test.go`, `sse_test.go` (httptest client)

### Backend wiring
- `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` unconditional fail-fast config
- compose `ai-engine` service: internal network only (no host port), shared `uploads_data` volume at `/app/uploads`, urllib healthcheck, no `depends_on: api→ai-engine`
- `AI_PGVECTOR_DSN` + `AI_EMBEDDING_DIM=1536` now exist (Phase 2); shared-postgres on localhost:5432 (db academio, user postgres/postgres)
- pgvector extension in `public`, `school_{id}.ai_vectors` tables in all 12 tenant schemas with `public.vector(1536)` + HNSW (`vector_cosine_ops`) + `UNIQUE(document_id, chunk_index)`
- Column contract (Phase 2 D-09): `id, collection, embedding public.vector(1536), document_id, chunk_index, text, embedding_model, model_version, chunking_version, created_at, updated_at`
- Qdrant retired from compose/k8s; `qdrant.go` retained as behavioral ref
- Asynq `ai:scoring` handler is the pattern for Go→Python doc-ingest

### Decisions already locked (carry into Phase 3)
- Direct SDKs only (`anthropic` + `openai` base_url); NO LiteLLM, NO Python gateway, NO Celery
- `/v1/providers` added to PYE-04 (required by Go INT-02)
- `proto/aiengine.proto` written at start of Python phase; REST satisfies it 1:1
- Service token only (`X-AI-Engine-Token`); never user JWT
- `.planning/` gitignored, `commit_docs: false`
- Coarse granularity, sequential execution

## Open questions for discussion (03-DISCUSSION-LOG.md)

Gray-area decisions the planner/executor will need (agent picks recommended option, records rationale):

1. **Provider SDKs & keys**: Anthropic via `anthropic` SDK; DeepSeek/OpenRouter/Azure OpenAI via `openai` SDK with base_url; Ollama via `openai` compat or httpx? Config via `AI_ANTHROPIC_API_KEY`, `AI_OPENROUTER_API_KEY`, `AI_DEEPSEEK_API_KEY`, `AI_AZURE_OPENAI_*`, `AI_OLLAMA_BASE_URL`?
2. **SSE wire format**: exact event shape for `ChatStream` (data-only vs event: + data:, heartbeats as `: ping` or data JSON?) matching Go sse.go scanner.
3. **Chat request schema**: does Go send `model` as the *provider:model* composite (e.g. `anthropic:claude-3-5-sonnet`) or separate? Normalized usage/cost payload shape.
4. **Document parsing**: which Python libs (pypdf, python-docx, python-pptx, openpyxl, pdfplumber for digital PDFs; pytesseract + pdf2image for scanned)? Tesseract availability (apt in Dockerfile?) + ≥300 DPI.
5. **Embeddings**: use `openai` SDK with base_url for text-embedding-3-small, or an HTTP call? Batch size, retries?
6. **RAG search**: hybrid dense + BM25 — `pgvector` HNSW for dense (via psycopg3/pgvector-python) + what for BM25? RRF merge formula; metadata filters shape; citations format.
7. **IngestDocument write**: Python connects to Postgres directly (psycopg3 + pgvector-python) with schema-qualified writes validated `^school_\d+$`? Connection pool (pgbouncer not needed; pool from psycopg_pool)?
8. **Prompt library**: Git-backed YAML in `ai-engine/prompts/` — structure, versioning, dev/staging/prod aliases, env override?
9. **Auth/tenancy from Go**: how does Go pass schema_name/tenant to Python (header `X-School-Schema`? body field?) — validated `^school_\d+$`.
10. **Provider status/cooldowns**: `/v1/providers` health check mechanism (lightweight ping per provider, TTL cache), cooldown state in-memory?
11. **proto file**: location `proto/aiengine.proto` at root or `ai-engine/proto/`? gRPC service method names matching REST 1:1.
12. **Testing**: pytest strategy — httpx AsyncClient for endpoints, live providers skipped without keys (env-gated), psycopg integration tests gated on DB_* env (mirror Phase 2 Go pattern)?

## Deferred (out of scope for this phase)

- gRPC transport itself (v1 = REST/JSON + SSE; proto is the contract seam only)
- Celery/queue in Python (stateless; Go asynq → Python HTTP)
- User auth in Python (service token only)
- Mobile/public API integration

## Exit Criteria

- [ ] All PYE-01..PYE-05 + PYE-04a planned, executed, code-reviewed, verified
- [ ] Phase 3 ROADMAP success criteria 1-5 all TRUE
