# Phase 3 Discussion Log

Mode: auto
Date: 2026-08-01

## D-01: Provider SDKs & keys

- Selected: `anthropic` SDK for Anthropic; `openai` SDK (AsyncOpenAI with base_url) for DeepSeek, OpenRouter, Azure OpenAI; httpx directly for Ollama (OpenAI-compat `/v1/chat/completions` also acceptable but httpx keeps Ollama local + dependency-light)
- Alternatives: (a) single `openai` client for everything via base_url override; (b) raw httpx for all five; (c) a homegrown provider interface
- Rationale: ROADMAP criterion 2 mandates "direct SDKs (`anthropic` + `openai` with `base_url`)". `anthropic` SDK has first-class async + SSE. `openai` SDK accepts `base_url` for DeepSeek (`https://api.deepseek.com`), OpenRouter (`https://openrouter.ai/api/v1`), Azure (`https://{resource}.openai.azure.com/openai/v1` with api-key). Ollama speaks OpenAI-compatible chat completions but is local + has no cost field; httpx keeps it explicit. NO LiteLLM, NO gateway (PYE-01).
- Keys (env, pydantic-settings): `AI_ANTHROPIC_API_KEY`, `AI_DEEPSEEK_API_KEY`, `AI_OPENROUTER_API_KEY`, `AI_AZURE_OPENAI_API_KEY` + `AI_AZURE_OPENAI_ENDPOINT` + `AI_AZURE_OPENAI_DEPLOYMENT`, `AI_OLLAMA_BASE_URL` (default `http://localhost:11434`). Embeddings: `AI_OPENAI_API_KEY` (canonical text-embedding-3-small via openai SDK).

## D-02: SSE wire format

- Selected: Match the EXISTING Go contract exactly — each event is a `data:` line whose payload is the JSON `EngineEvent{type: "delta"|"citation"|"usage"|"error"|"done", data: <object>}` envelope. Event boundaries on blank lines. Heartbeats as comment lines `: ping` (Go `scanSSEEvents` tolerates/ignores comment-only blocks).
- Alternatives: (a) `event: <type>` + `data: <json>` SSE field separation (also valid but requires Go-side changes); (b) JSON-lines stream
- Rationale: `backend/internal/ai/engine/sse.go` + `engine.go` (EngineEvent at line 20) already define the envelope with `type` as the discriminator field INSIDE JSON. Keeping the single-`data:`-line shape means ZERO Go changes to the Phase 1 SSE scanner — the seam stays compatible (Phase 3 goal). `data: {"type":"delta","data":{...}}`. Heartbeats `: ping` every ≤30s (ROADMAP criterion 2).

## D-03: Chat request schema / model composite

- Selected: Go `ChatRequest.Model` carries a `provider:model` composite string (e.g. `anthropic:claude-3-5-sonnet-latest`, `openrouter:openai/gpt-4o-mini`, `ollama:llama3.2`); Python splits on first `:` to route to the provider client. Response includes normalized usage: `{provider, model, input_tokens, output_tokens, cost}`.
- Alternatives: (a) separate `provider` + `model` JSON fields (requires Go DTO change); (b) model-only with provider registry mapping
- Rationale: `ChatRequest{Model, Messages, Stream}` is locked in `engine.go:32-36` — no `provider` field. A `provider:model` composite keeps the Go DTO unchanged and unambiguous (model names may contain `/` like `openai/gpt-4o-mini`, but `:` is not used in model IDs). Cost computed from provider price tables in `cost.py` (mirrors Go `cost.go`).

## D-04: Document parsing

- Selected: `pypdf` (digital PDF text), `pdf2image` + `pytesseract` (scanned pages OCR at ≥300 DPI), `python-docx` (DOCX), `python-pptx` (PPTX), `openpyxl` (XLSX/CSV via csv stdlib), Pillow (image preprocessing for OCR). Tesseract binary installed in Dockerfile via apt (`tesseract-ocr` + `tesseract-ocr-eng`; lang packs as needed).
- Alternatives: (a) `pdfplumber` for digital (better tables but heavier); (b) `unstructured` (heavy dependency tree)
- Rationale: ROADMAP criterion 4 mandates per-page routing "digital → fast text parser, scanned → Tesseract OCR at ≥300 DPI". `pypdf` is fast + maintained; `pdf2image` renders pages for OCR when no text layer. Tesseract must be apt-installed in the Docker image (python:3.13-slim has no OCR). Decision per page: if extracted text length > threshold (e.g. 20 chars) treat as digital, else OCR.

## D-05: Embeddings

- Selected: `openai` AsyncOpenAI SDK with `base_url` default `https://api.openai.com/v1`, model `text-embedding-3-small` (canonical, 1536-dim, locked in Phase 2 D-01/PGV-04a). Batch ≤ 128 texts per call, `tenacity` retry with exponential backoff (respecting 429/rate-limit), dimension assert == 1536 (D-14 parity) with fail-loud error.
- Alternatives: (a) raw httpx POST to `/embeddings`; (b) embedding provider abstraction
- Rationale: ROADMAP criterion 3 requires "canonical-model embeddings matching `ai_vectors`' locked dimension". The openai SDK handles auth + batching + errors; we assert `len(embedding)==1536` on every response (mirrors Phase 2 D-14 dimension guard). Retry policy: 3 attempts, backoff_factor 2.

## D-06: RAG search (hybrid dense + BM25/RRF)

- Selected: Dense via pgvector HNSW `<=>` in `school_{id}.ai_vectors` (SQL through psycopg3); BM25 via PostgreSQL `tsvector`/`ts_rank` over `text` (needs a generated column or runtime to_tsvector — runtime `to_tsvector('english', text)` in SQL is simplest, configurable language); RRF merge `score = Σ 1/(k + rank)` with k=60. Metadata filters as AND clauses on `collection`, `document_id`/`chunk_index` ranges, `embedding_model`.
- Alternatives: (a) rank_bm25 library over in-memory corpus (not scalable to thousands of docs); (b) dedicated search index (OpenSearch) — violates no-new-infra
- Rationale: ROADMAP criterion 5 mandates "hybrid retrieval (dense + BM25/RRF)". We already have pgvector; PG's built-in `ts_rank` gives BM25-like scoring without new infra. RRF (Reciprocal Rank Fusion) merges the two ranked lists — standard, robust to score-scale differences. k=60 is the common default. All schema access validates `^school_\d+$` (D-07).

## D-07: IngestDocument write / DB access

- Selected: psycopg3 (`psycopg[binary]`) + `pgvector` Python package + `psycopg_pool` connection pool. Every query targets a validated schema: `validate_schema_name()` enforcing `^school_[0-9]+$` + existence check via `information_schema.schemata`; then schema-qualified writes `INSERT INTO {schema}.ai_vectors (...)`. No global fallback schema. Async: psycopg3 AsyncConnection + AsyncConnectionPool.
- Alternatives: (a) SQLAlchemy ORM (heavy); (b) direct `asyncpg` (no pgvector type integration)
- Rationale: ROADMAP criterion 4: "every DB access validates `schema_name` against `^school_\d+$` with no global fallback". psycopg3 + pgvector-python handles the `vector` type cleanly; `psycopg_pool` gives async pooling. DSN from `AI_PGVECTOR_DSN` (or DB_* vars) shared with Go. No hardcoded schema names (AGENTS.md B8 spirit; Python-side equivalent).

## D-08: Prompt library

- Selected: Git-backed YAML at `ai-engine/prompts/` — directory per prompt type (report-comments/, lesson-plans/, questions/, rubrics/, behaviour-summary/, attendance-analysis/, parent-letters/, meeting-minutes/, translation/), each with `prompt.yaml` (metadata: name, version, description, model_hint) + `template.txt` (Jinja2 template). `prompt_library.py` loads + caches, supports version aliases (`dev`, `staging`, `prod` map to version numbers in config), env override `AI_PROMPTS_DIR`.
- Alternatives: (a) DB-backed prompts (overkill; no admin UI yet); (b) Python string constants (not versioned/editable)
- Rationale: ROADMAP criterion 5 mandates "versioned prompt library (Git-backed YAML, dev/staging/prod aliases)". Git versioning is free; YAML metadata + Jinja2 templates are editable without code changes. dev/staging/prod aliases resolved via config map (default: prod = latest tagged, dev = working tree). Jinja2 for variable substitution (existing `jinja2` dep).

## D-09: Auth/tenancy from Go

- Selected: Go passes the tenant schema as header `X-School-Schema` (e.g. `school_1`) on every `/v1/documents`, `/v1/search`, `/v1/embed` (where tenant-scoped) request. Python validates `^school_[0-9]+$` + existence before any DB access; rejects with 400 if absent for tenant-scoped routes. Service auth remains `X-AI-Engine-Token` only.
- Alternatives: (a) schema in request body; (b) JWT passthrough (explicitly rejected — service token only)
- Rationale: ROADMAP criterion 4 "writes to the validated `school_{id}` schema". A header keeps body schemas clean (chat/extract bodies are provider-facing), matches the Go side's existing header-based auth pattern, and cannot collide with user-supplied body fields. Never trust user JWT in Python (D-01/PYE-05 state).

## D-10: Provider status/cooldowns

- Selected: `/v1/providers` returns per-provider: `{provider, status: healthy|degraded|unavailable|cooldown, latency_ms, last_checked, cooldown_until?}`. Health check = lightweight model-less ping (for OpenAI-compat: `GET /v1/models` or 1-token chat; for Anthropic: `GET /v1/models`; for Ollama: `GET /api/tags`). In-memory TTL cache (30s) + cooldown state (provider marked cooldown after N consecutive failures for configurable window, e.g. 60s).
- Alternatives: (a) live check on every request (slow, rate-limit risk); (b) static config-based status
- Rationale: ROADMAP criterion 3: "`/v1/providers` returns live per-provider status (health, cooldowns) for Go's INT-02". TTL-cached lightweight pings keep it live without hammering providers. In-memory cooldown per provider instance — stateless service, cooldown is per-process (acceptable; single replica dev).

## D-11: proto file location

- Selected: `proto/aiengine.proto` at repo ROOT (sibling of backend/, ai-engine/) — single source of truth, importable by both Go and Python. Service `AiEngine` with methods `Chat`, `ChatStream`, `Embed`, `Extract`, `IngestDocument`, `Search` (ROADMAP criterion 1 lists exactly these six). REST paths map 1:1: `POST /v1/chat` → Chat, `POST /v1/chat/stream` → ChatStream, `POST /v1/embed` → Embed, `POST /v1/extract` → Extract, `POST /v1/documents` → IngestDocument, `POST /v1/search` → Search.
- Alternatives: (a) `ai-engine/proto/` (Python-only visibility); (b) `backend/proto/` (Go-only)
- Rationale: The contract spans Go (caller) + Python (server). Root `proto/` is the conventional location in monorepos, importable from both submodules. gRPC method names match REST endpoints 1:1 (criterion 1). No gRPC server in v1 — proto is the contract seam (PYE-04a).

## D-12: Testing

- Selected: pytest with `pytest-asyncio` + `httpx.AsyncClient(transport=ASGITransport)` for endpoint tests; provider tests env-gated (skip cleanly without `AI_*_API_KEY` — mirrors Phase 2 Go spike pattern); DB integration tests gated on `AI_PGVECTOR_DSN`/DB_* env (skip without it) and use a dedicated test schema; ruff + pyright gates in CI (already in Phase 1 workflow). `tenacity` mocked in tests.
- Alternatives: (a) Testcontainers (heavy for dev); (b) mocking at transport layer only
- Rationale: Matches the Phase 2 Go testing discipline (integration tests skip cleanly without live env; unit tests fast). httpx ASGITransport avoids live network for route tests. Env-gated provider tests make CI green without API keys while allowing real verification locally. pyright strictness catches type errors (pyproject already configures it).

---

## Decisions that MUST reach the planner

| ID | Decision |
|----|----------|
| D-01 | anthropic SDK + openai SDK base_url + httpx Ollama; keys `AI_*_API_KEY`/`AI_AZURE_OPENAI_*`/`AI_OLLAMA_BASE_URL` |
| D-02 | SSE events are `data: {"type":...}` matching Go EngineEvent (delta/citation/usage/error/done); `: ping` heartbeats ≤30s |
| D-03 | `provider:model` composite in ChatRequest.Model; normalized usage payload `{provider, model, input_tokens, output_tokens, cost}` |
| D-04 | pypdf + pdf2image/pytesseract (≥300 DPI) + python-docx + python-pptx + openpyxl; tesseract via apt in Dockerfile |
| D-05 | openai SDK text-embedding-3-small, batch ≤128, tenacity retries, 1536-dim assert |
| D-06 | HNSW `<=>` dense + PG `ts_rank` BM25 + RRF k=60; metadata AND filters; schema-validated |
| D-07 | psycopg3 + pgvector-python + psycopg_pool; schema validated `^school_[0-9]+$` + existence; no fallback |
| D-08 | Git-backed YAML prompts at ai-engine/prompts/ (prompt.yaml + Jinja2 template.txt); dev/staging/prod aliases |
| D-09 | Tenant schema via `X-School-Schema` header; validated `^school_[0-9]+$` + existence |
| D-10 | /v1/providers live status via model-less ping, 30s TTL cache, in-memory cooldown |
| D-11 | Root `proto/aiengine.proto`, service AiEngine, 6 methods mapped 1:1 to REST |
| D-12 | pytest-asyncio + httpx ASGITransport; env-gated provider/DB tests skip cleanly |
