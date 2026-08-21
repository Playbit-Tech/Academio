<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
**Decisions already locked (carry into Phase 3):**
- Direct SDKs only (`anthropic` + `openai` base_url); NO LiteLLM, NO Python gateway, NO Celery
- `/v1/providers` added to PYE-04 (required by Go INT-02)
- `proto/aiengine.proto` written at start of Python phase; REST satisfies it 1:1
- Service token only (`X-AI-Engine-Token`); never user JWT
- `.planning/` gitignored, `commit_docs: false` — ⚠️ **VERIFIED OUTDATED**: `.planning/` is actually tracked in git (`.planning/REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md` are committed); commit the research file.
- Coarse granularity, sequential execution

**Discussion decisions that MUST reach the planner (D-01..D-12):**
- **D-01** — anthropic SDK + openai SDK base_url + httpx Ollama; keys `AI_ANTHROPIC_API_KEY`, `AI_OPENROUTER_API_KEY`, `AI_DEEPSEEK_API_KEY`, `AI_AZURE_OPENAI_API_KEY` + `AI_AZURE_OPENAI_ENDPOINT` + `AI_AZURE_OPENAI_DEPLOYMENT`, `AI_OLLAMA_BASE_URL` (default `http://localhost:11434`), `AI_OPENAI_API_KEY` for embeddings
- **D-02** — SSE events are `data: {"type":"delta"|"citation"|"usage"|"error"|"done","data":{...}}` matching Go `EngineEvent`; `: ping` heartbeats ≤30s; no gzip
- **D-03** — `provider:model` composite in `ChatRequest.Model`; normalized usage `{provider, model, input_tokens, output_tokens, cost}`
- **D-04** — pypdf + pdf2image/pytesseract (≥300 DPI) + python-docx + python-pptx + openpyxl; tesseract via apt in Dockerfile
- **D-05** — openai SDK text-embedding-3-small, batch ≤128, tenacity retries, 1536-dim assert
- **D-06** — HNSW `<=>` dense + PG `ts_rank` BM25 + RRF k=60; metadata AND filters; schema-validated
- **D-07** — psycopg3 + pgvector-python + psycopg_pool; schema validated `^school_[0-9]+$` + existence; no fallback
- **D-08** — Git-backed YAML prompts at `ai-engine/prompts/` (prompt.yaml + Jinja2 template.txt); dev/staging/prod aliases; env override `AI_PROMPTS_DIR`
- **D-09** — Tenant schema via `X-School-Schema` header; validated `^school_[0-9]+$` + existence
- **D-10** — `/v1/providers` live status via model-less ping, 30s TTL cache, in-memory cooldown
- **D-11** — Root `proto/aiengine.proto`, service `AiEngine`, 6 methods (Chat, ChatStream, Embed, Extract, IngestDocument, Search) mapped 1:1 to REST
- **D-12** — pytest-asyncio + httpx ASGITransport; env-gated provider/DB tests skip cleanly

### the agent's Discretion
*(None explicitly granted in CONTEXT.md beyond the 12 discussion decisions above, where the agent's recommended option was selected and rationale recorded.)*

### Deferred Ideas (OUT OF SCOPE)
- gRPC transport itself (v1 = REST/JSON + SSE; proto is the contract seam only)
- Celery/queue in Python (stateless; Go asynq → Python HTTP)
- User auth in Python (service token only)
- Mobile/public API integration
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PYE-01 | Python multi-provider abstraction (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama) via direct SDKs; NO gateway, NO LiteLLM | anthropic 0.120.2 + openai 2.52.0 SDKs verified on PyPI; DeepSeek/OpenRouter/Azure base_urls verified; Ollama OpenAI-compat live-tested |
| PYE-02 | Document intelligence: PDF, DOCX, PPTX, TXT, CSV, image OCR (Tesseract), chunking, embeddings, semantic search, re-ranking, knowledge indexing | pypdf 6.14.2, pdf2image 1.17.0, pytesseract 0.3.13, python-docx 1.2.0, python-pptx 1.0.2, openpyxl 3.1.5, Pillow 12.3.0 verified on PyPI; tesseract-ocr 5.5.0 + poppler-utils 25.03.0 verified as apt candidates in python:3.13-slim (trixie) |
| PYE-03 | Versioned prompt library (report comments, lesson plans, questions, rubrics, behaviour summary, attendance analysis, parent letters, meeting minutes, translation) | jinja2 3.1.6 already in uv.lock; D-08 design (Git-backed YAML, dev/staging/prod aliases) locked; template pattern verified live |
| PYE-04 | Python endpoints: `/health`, `/v1/chat`, `/v1/chat/stream` (SSE), `/v1/embed`, `/v1/extract`, `/v1/documents`, `/v1/search`, `/v1/providers` | FastAPI 0.140.13 + StreamingResponse SSE headers verified live (text/event-stream, no gzip); token auth pattern in existing skeleton |
| PYE-04a | `proto/aiengine.proto` gRPC contract written at START of phase (transports over REST in v1) | Root `proto/` dir confirmed non-existent → must be created; D-11 method↔REST mapping locked |
| PYE-05 | Tenant-aware RAG in Python (hybrid search, metadata filtering, chunk ranking, citations, context compression) | pgvector 0.5.0 + psycopg 3.3.4 + psycopg_pool 3.3.1 live round-trip test PASSED against shared-postgres (HNSW, cosine, ts_rank BM25, schema-qualified writes) |
</phase_requirements>

# Phase 3: Python AI Engine - Research

**Researched:** 2026-08-01
**Domain:** Python multi-provider LLM engine, SSE streaming, document intelligence, tenant-aware RAG (pgvector)
**Confidence:** HIGH (all critical claims live-verified against the actual environment)

## Summary

Phase 3 builds the Academio AI engine: a stateless FastAPI service in `ai-engine/` that fronts five LLM providers (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama) via direct SDKs, streams SSE to the Go backend using the exact `EngineEvent` envelope Go's `sse.go` scanner already parses, and delivers document intelligence + tenant-aware RAG backed by the pgvector tables Phase 2 created. This research live-verified every external dependency: package versions on PyPI, the SSE wire format 1:1 against Go's scanner, a full async pgvector round-trip (pool → insert → HNSW cosine search → BM25 ts_rank → schema-qualified write) against the real shared-postgres container, FastAPI's SSE response headers, tenacity/jinja2 APIs, and a live Ollama OpenAI-compat chat completion.

The engine's hard boundaries are locked: no LiteLLM, no Celery, no user auth (service token only), REST/JSON + SSE transport in v1 (proto is the contract seam), and every DB access must validate `schema_name` against `^school_[0-9]+$` with no global fallback. Three environment facts materially shape the plan: (1) the Go seam requires the `data: {"type":...}` single-line SSE envelope — heartbeats as `: ping` comment lines — so no Go changes are needed; (2) the local `.env` and compose DSNs use different credentials (`postgres:postgres@localhost` vs `academio:academio@postgres`), so the engine's DSN handling must not hardcode either; (3) Ollama is already installed and running on the host with usable models, giving a free always-available provider for CI-gated tests. A live-verified pitfall: pgvector cosine distance returns NaN for zero vectors — the embed pipeline must reject/normalize zero embeddings.

**Primary recommendation:** Implement Phase 3 exactly per locked decisions D-01..D-12 using the verified package versions below. Update `ai-engine/pyproject.toml` with `uv add` (all 14 packages resolve cleanly — proven in scratch copy), add `tesseract-ocr tesseract-ocr-eng poppler-utils` to the Dockerfile apt layer, use `psycopg3 AsyncConnectionPool` + `pgvector.Vector` for all DB work, and write `proto/aiengine.proto` first per ROADMAP criterion 1.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.140.13 (pin `<0.141` already locked) | HTTP framework, SSE via StreamingResponse | Already the project's Phase 1 choice; [VERIFIED: uv.lock] |
| anthropic | 0.120.2 | Anthropic Claude via first-class async SDK + `messages.stream()` | Mandated by D-01/PYE-01 [VERIFIED: PyPI live] |
| openai | 2.52.0 | DeepSeek/OpenRouter/Azure via `AsyncOpenAI(base_url=...)`; embeddings via text-embedding-3-small | Mandated by D-01/D-05 [VERIFIED: PyPI live] |
| httpx | 0.28.1 (already in lock) | Ollama OpenAI-compat calls (D-01) | Already transitive; D-01 chose httpx for Ollama |
| psycopg[binary] | 3.3.4 | Async Postgres access (AsyncConnection, schema-qualified writes) | D-07; [VERIFIED: PyPI live] |
| psycopg-pool | 3.3.1 | AsyncConnectionPool for tenant DB access | D-07; [VERIFIED: PyPI live] |
| pgvector | 0.5.0 | `pgvector.Vector` type + `register_vector_async` | D-07; [VERIFIED: PyPI live] |
| jinja2 | 3.1.6 (already in lock) | Prompt template rendering | D-08; [VERIFIED: uv.lock] |
| tenacity | 9.1.4 | Retry/backoff for provider + embed calls | D-05; [VERIFIED: PyPI live] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pypdf | 6.14.2 | Digital PDF text extraction | PDF with extractable text layer [VERIFIED: PyPI live] |
| pdf2image | 1.17.0 | Render PDF pages → PIL images for OCR | Scanned PDFs (≥300 DPI) [VERIFIED: PyPI live] |
| pytesseract | 0.3.13 | Tesseract OCR wrapper | Scanned pages / images [VERIFIED: PyPI live] |
| Pillow | 12.3.0 | Image preprocessing for OCR (grayscale, threshold, resize) | Images / OCR quality [VERIFIED: PyPI live] |
| python-docx | 1.2.0 | DOCX text extraction | Word documents [VERIFIED: PyPI live] |
| python-pptx | 1.0.2 | PPTX text extraction | PowerPoint [VERIFIED: PyPI live] |
| openpyxl | 3.1.5 | XLSX extraction (CSV via stdlib csv) | Spreadsheets [VERIFIED: PyPI live] |
| pydantic-settings | 2.14.2 (already in lock) | Env-based config | Already the skeleton's choice [VERIFIED: uv.lock] |
| uvicorn | 0.52.0 (already in lock) | ASGI server | Already in lock [VERIFIED: uv.lock] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pypdf | pdfplumber | pdfplumber better tables but heavier; pypdf is fast + maintained (D-04 rationale) |
| pypdf/pdf2image/pytesseract | unstructured | unstructured pulls a heavy dependency tree (D-04 rationale) |
| psycopg3 + pgvector-python | SQLAlchemy ORM / asyncpg | SQLAlchemy heavy; asyncpg lacks pgvector type integration (D-07 rationale) |
| PG ts_rank BM25 | rank_bm25 library | In-memory BM25 doesn't scale to thousands of docs (D-06 rationale) |
| PG ts_rank BM25 | OpenSearch | Violates no-new-infra (D-06 rationale) |
| openai SDK for Ollama | raw httpx for Ollama (SELECTED for Ollama) | httpx keeps Ollama local + dependency-light; but OpenAI-compat `/v1/chat/completions` live-verified working via openai SDK too |

**Installation:**
```bash
# In ai-engine/ (uv 0.12.0 verified; all resolve cleanly — scratch-verified 76 packages)
uv add "anthropic>=0.120.2" "openai>=2.52.0" "psycopg[binary]>=3.3.4" "psycopg-pool>=3.3.1" "pgvector>=0.5.0" "tenacity>=9.1.4" "pypdf>=6.14.2" "pdf2image>=1.17.0" "pytesseract>=0.3.13" "python-docx>=1.2.0" "python-pptx>=1.0.2" "openpyxl>=3.1.5" "pillow>=12.3.0"
```
(jinja2 and httpx already in uv.lock via fastapi — no explicit add needed; verify `uv add` does not bump fastapi past 0.141 — the `<0.141` pin is preserved in scratch resolution.)

**Version verification:** All versions above verified live against PyPI on 2026-08-01 via `pip index` in a scratch venv and `uv add` dry-run. The uv.lock pins (fastapi 0.140.13, pydantic-settings 2.14.2, uvicorn 0.52.0, jinja2 3.1.6, httpx 0.28.1) were read directly from the committed lockfile. **tenacity, anthropic, openai, httpx-sse are NOT currently in uv.lock (not transitive) — all must be explicitly added.**

## Architecture Patterns

### Recommended Project Structure
```
ai-engine/
├── pyproject.toml
├── uv.lock
├── Dockerfile              # + apt: tesseract-ocr tesseract-ocr-eng poppler-utils
├── app/
│   ├── main.py             # FastAPI app, require_token (existing skeleton)
│   ├── config.py           # pydantic-settings — extend with all AI_* keys
│   ├── api/                # route modules per endpoint
│   │   ├── chat.py         # POST /v1/chat, /v1/chat/stream
│   │   ├── embed.py        # POST /v1/embed
│   │   ├── extract.py      # POST /v1/extract, /v1/documents
│   │   ├── search.py       # POST /v1/search
│   │   └── providers.py    # GET /v1/providers
│   ├── providers/          # provider abstraction (D-01)
│   │   ├── base.py         # Provider protocol: chat(), stream(), health()
│   │   ├── anthropic_provider.py
│   │   ├── openai_compat.py    # DeepSeek/OpenRouter/Azure (base_url)
│   │   ├── ollama_provider.py  # httpx
│   │   ├── registry.py     # provider:model routing (split on first ':')
│   │   └── cost.py         # price tables → normalized cost
│   ├── sse.py              # EngineEvent envelope writer (matches Go engine.go)
│   ├── documents/          # extract → chunk → embed → store pipeline
│   │   ├── extractors/     # pypdf, pdf2image+ocr, docx, pptx, xlsx, csv, image
│   │   ├── chunker.py
│   │   └── pipeline.py     # /v1/documents one-call orchestration
│   ├── db/
│   │   ├── pool.py         # AsyncConnectionPool singleton (AI_PGVECTOR_DSN)
│   │   ├── schema.py       # validate_schema_name() ^school_[0-9]+$ + existence
│   │   └── vectors.py      # insert / search / delete on {schema}.ai_vectors
│   ├── rag/
│   │   ├── hybrid.py       # dense <=> + ts_rank BM25 + RRF merge (k=60)
│   │   └── rerank.py       # chunk ranking, citations, context compression
│   ├── prompts/            # Git-backed YAML (D-08)
│   │   ├── report-comments/prompt.yaml + template.txt
│   │   ├── lesson-plans/ … (9 types: report-comments, lesson-plans, questions,
│   │   │   rubrics, behaviour-summary, attendance-analysis, parent-letters,
│   │   │   meeting-minutes, translation)
│   │   └── prompt_library.py  # load + cache + dev/staging/prod aliases
│   └── util/
│       ├── retry.py        # tenacity presets
│       └── healthcheck.py  # per-provider ping (D-10)
├── tests/
└── proto/aiengine.proto    # REPO ROOT (sibling of backend/ and ai-engine/) — D-11
```

### Pattern 1: SSE envelope matching the Go scanner (D-02)
**What:** Every streamed event is exactly one `data:` line whose payload is the JSON `EngineEvent{type, data}` envelope; event boundaries are blank lines; heartbeats are `: ping` comment lines. No `event:` field.
**When to use:** All streaming responses from `/v1/chat/stream`.
**Example (Go contract at `backend/internal/ai/engine/engine.go:20-23`, scanner at `sse.go`):**
```text
: ping

data: {"type":"delta","data":{"content":"Hello"}}

data: {"type":"delta","data":{"content":" world"}}

data: {"type":"usage","data":{"provider":"deepseek","model":"deepseek-chat","input_tokens":12,"output_tokens":3,"cost":0.000012}}

data: {"type":"done","data":{}}
```
`[VERIFIED: 1:1 live probe — /tmp/opencode/sse_probe.py parsed Go-scanner-equivalent output; 4/4 events recognized, `: ping` and `event:`-less blocks tolerated; JSON must be compact (no literal newlines in data).]`

### Pattern 2: Tenant-scoped pgvector access (D-07)
**What:** One `AsyncConnectionPool` from `psycopg_pool` with `configure=register_vector_async`; every query schema-qualifies via validated `schema_name`; no global fallback.
**When to use:** All `/v1/documents`, `/v1/search`, `/v1/embed` (tenant-scoped) DB work.
**Example (live round-trip test PASSED 2026-08-01 against shared-postgres):**
```python
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async
from pgvector import Vector

pool = AsyncConnectionPool(
    "postgres://postgres:postgres@localhost:5432/academio?sslmode=disable",
    open=False, configure=register_vector_async, min_size=1, max_size=4,
)
await pool.open()
await pool.wait()

async with pool.connection() as conn:
    await conn.execute(
        f"INSERT INTO {schema}.ai_vectors (id, collection, embedding, document_id, chunk_index, text, embedding_model, model_version, chunking_version) "
        f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (doc_id, "collection", Vector(embedding), doc_id, "0", text,
         "text-embedding-3-small", "v1", "v1"),
    )

# Hybrid search: dense (HNSW <=>) + BM25 (ts_rank), RRF merge k=60 (D-06)
# Dense (parity with backend/internal/ai/vector/pgvector.go:244-247):
#   SELECT id, collection, 1 - (embedding <=> %s) AS score, document_id, chunk_index, text
#   FROM {schema}.ai_vectors WHERE collection = %s ORDER BY embedding <=> %s LIMIT 20
# BM25:
#   SELECT id, ts_rank(to_tsvector('english', text), plainto_tsquery('english', %s)) AS score ...
# Both verified live: vector_dims(embedding)=1536, cosine order correct (1.0 identical / -1.0 anti-parallel)
```
`[VERIFIED: live]`

### Pattern 3: Provider abstraction with provider:model routing (D-01/D-03)
**What:** `ChatRequest.Model` arrives as `provider:model` (e.g. `anthropic:claude-3-5-sonnet-latest`); split on first `:`; `:` never appears in model IDs (but `/` does — e.g. `openrouter:openai/gpt-4o-mini`). Each provider implements a common protocol; normalized usage `{provider, model, input_tokens, output_tokens, cost}` returned on every response.
**Example (anthropic streaming, official docs pattern):**
```python
from anthropic import AsyncAnthropic
client = AsyncAnthropic(api_key=settings.AI_ANTHROPIC_API_KEY)

async with client.messages.stream(
    model=model, max_tokens=1024, messages=messages,
) as stream:
    async for event in stream:
        if event.type == "text":
            yield event.text
```
`[CITED: official Anthropic SDK example (docs.anthropic.com); [VERIFIED: PyPI anthropic 0.120.2]]`

### Pattern 4: `/v1/providers` health + cooldown (D-10)
**What:** TTL-cached (30s) per-provider status `{provider, status: healthy|degraded|unavailable|cooldown, latency_ms, last_checked, cooldown_until?}`. Pings: OpenAI-compat → `GET /v1/models`; Anthropic → `GET /v1/models` (headers `x-api-key` + `anthropic-version: 2023-06-01`); Ollama → `GET /api/tags`; DeepSeek → `GET https://api.deepseek.com/models`; Azure → models-list API on endpoint. In-memory cooldown after N consecutive failures for a window (e.g. 60s).
`[VERIFIED: Anthropic /v1/models + anthropic-version header [CITED: docs.anthropic.com/en/api/models-list]; DeepSeek /models + OpenRouter /v1/models + Ollama /api/tags + OpenAI-compat /v1/models [VERIFIED: web docs]; Ollama /api/tags + /v1/chat/completions live-tested on host]`

### Anti-Patterns to Avoid
- **One provider class with if/elif chains:** breaks PYE-01's abstraction; use a common Provider protocol + registry.
- **Building SSE events with `event:` + `data:` fields:** Go's scanner ignores the `event:` field (empty type) — works by accident, but the D-02 envelope is the contract. Don't deviate.
- **Hardcoding either DSN credential:** local `.env` uses `postgres:postgres@localhost:5432`, compose uses `academio:academio@postgres:5432` — always read from `AI_PGVECTOR_DSN` env (Rule B6 spirit).
- **Embedding zero/near-zero vectors:** cosine distance → NaN (`1 - NaN`), silently poisoning search. Reject/normalize before insert [VERIFIED: live — 0-vector probe returned NaN].
- **Multi-statement `db.Exec`-style SQL:** pgx/GORM rule B4 doesn't apply to psycopg3 (it supports it), but keep statements single for parity and audit clarity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anthropic API access | raw httpx | `anthropic` SDK | First-class async + SSE streaming + retries [VERIFIED: 0.120.2] |
| DeepSeek/OpenRouter/Azure API access | per-provider clients | `openai` SDK with `base_url` | One SDK, standard chat.completions streaming [VERIFIED: 2.52.0] |
| Retry/backoff on rate limits | hand-written loops | `tenacity` | 429 handling, exponential backoff, jitter, reraise [VERIFIED: 9.1.4 AsyncRetrying] |
| pgvector `vector` type handling | manual hex/string encoding | `pgvector` Python package | Correct type adapter + register_vector_async [VERIFIED: 0.5.0 live round-trip] |
| Connection pooling | per-request connections | `psycopg_pool.AsyncConnectionPool` | Open/close per request kills throughput on 1000s of docs [VERIFIED: 3.3.1 live] |
| PDF text extraction | regex scraping | `pypdf` | Handles PDF structure, encodings, pagination [VERIFIED: 6.14.2] |
| PDF → image for OCR | custom renderer | `pdf2image` (poppler) | poppler-utils apt package verified in trixie [VERIFIED: 25.03.0-5+deb13u4] |
| OCR engine | hand-rolled CV | `pytesseract` + `tesseract-ocr` apt | tesseract-ocr 5.5.0-1+b1 + tesseract-ocr-eng verified in trixie |
| Prompt templating | f-strings with injection risk | Jinja2 | Auto-escaping, filters, includes; already a dependency [VERIFIED: 3.1.6] |
| Cost calculation | stale hardcoded rates | `cost.py` module + provider price tables | Mirrors Go `cost.go`; single source of truth (D-03) |

**Key insight:** Every "don't hand-roll" choice is a library the ecosystem standardizes on AND that is already live-verified to work in this exact environment (Python 3.13, PG 18.4, trixie base image). The only genuinely custom code is the provider routing (provider:model composite) and the hybrid RAG merge — both thin glue over verified primitives.

## Common Pitfalls

### Pitfall 1: Async cursor double-await
**What goes wrong:** `cursor = await conn.execute(...)` returns an `AsyncCursor` — results need a SECOND `await cursor.fetchall()`. Forgetting the second await yields `TypeError`/never-await warnings.
**Why it happens:** psycopg3 async is "explicit two-step"; differs from sync psycopg2 mental model.
**How to avoid:** Always `cur = await conn.execute(...)` then `await cur.fetchall()`. [VERIFIED: live during probe — this exact bug hit and fixed]
**Warning signs:** Test failures with "coroutine was never awaited" or fetch on wrong object.

### Pitfall 2: NaN cosine from zero vectors
**What goes wrong:** A zero embedding produces `embedding <=> 0-vector = NaN` → `1 - NaN = NaN` score → rows rank NaN and can't be compared.
**Why it happens:** Cosine distance is undefined at the origin.
**How to avoid:** After embed, assert `math.isclose(np.linalg.norm(vec), 0) == False`; reject or return 400 for zero vectors. [VERIFIED: live probe]
**Warning signs:** Search results with `NaN` in score column / `NULL::float8` casts.

### Pitfall 3: SSE JSON with newlines / wrong envelope
**What goes wrong:** Go's scanner (`splitSSEEvent`) splits on blank lines and `\n\n` — pretty-printed JSON containing literal newlines breaks event parsing or produces partial events.
**Why it happens:** The Go scanner assumes one `data:` line per event (compact JSON).
**How to avoid:** `json.dumps(obj, separators=(",", ":"), ensure_ascii=True)` and write `data: {json}\n\n` exactly. [VERIFIED: 1:1 probe]
**Warning signs:** Go client receives partial `delta` payloads or `invalid character` JSON errors.

### Pitfall 4: Compose vs local DSN mismatch
**What goes wrong:** Engine works locally (`postgres:postgres@localhost:5432`) but fails in compose (`academio:academio@postgres:5432`) — or vice versa — if DSN is hardcoded.
**Why it happens:** Two different credential sets exist in `.env` vs `docker-compose.yml`.
**How to avoid:** Read `AI_PGVECTOR_DSN` exclusively from env; compose already passes its own (must be added to the ai-engine service env — currently only `AI_ENGINE_TOKEN` is passed). [VERIFIED: both DSNs read from files]
**Warning signs:** `connection refused` in compose only; `password authentication failed` in one environment only.

### Pitfall 5: Provider keys absent → silent fallback
**What goes wrong:** A provider with no API key configured fails at runtime instead of being reported as unavailable.
**Why it happens:** D-10 status model + env-gated tests expect graceful absence.
**How to avoid:** `/v1/providers` must return `unavailable` for providers without keys (not error the whole endpoint); tests skip cleanly without keys (D-12). [ASSUMED: consistent with D-10/D-12]
**Warning signs:** `/v1/providers` returns 500 instead of per-provider statuses.

### Pitfall 6: Tesseract missing in runtime image
**What goes wrong:** OCR fails at runtime with `pytesseract.pytesseract.TesseractNotFoundError` because the binary isn't in the slim image.
**Why it happens:** `python:3.13-slim` has no OCR binaries; host has no tesseract either (`command -v tesseract` → nothing on dev host).
**How to avoid:** Dockerfile apt layer: `apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng poppler-utils` (verified candidates in trixie). [VERIFIED: host has NO tesseract; trixie HAS tesseract-ocr 5.5.0]
**Warning signs:** OCR path only fails in container; local dev can't test OCR without Docker.

## Code Examples

Verified patterns from live tests and official sources:

### Async pgvector insert + hybrid search
```python
# /tmp/opencode/pgv_probe.py — PASSED 2026-08-01 (psycopg 3.3.4 + pgvector 0.5.0)
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async
from pgvector import Vector

pool = AsyncConnectionPool(
    "postgres://postgres:postgres@localhost:5432/academio?sslmode=disable",
    open=False, configure=register_vector_async, min_size=1, max_size=4,
)
await pool.open(); await pool.wait()

async with pool.connection() as conn:
    # two-step async: execute THEN fetchall
    cur = await conn.execute("SELECT vector_dims(embedding) FROM school_1.ai_vectors LIMIT 1")
    dims = await cur.fetchone()
    # INSERT with pgvector.Vector via %s placeholder works
    await conn.execute(
        f"INSERT INTO {schema}.ai_vectors (...) VALUES (%s, %s, %s, ...)",
        (..., Vector(embedding), ...),
    )
```

### FastAPI SSE endpoint (verified response headers)
```python
from fastapi import StreamingResponse

@app.post("/v1/chat/stream", dependencies=[Depends(require_token)])
async def chat_stream(req: ChatRequest):
    async def gen():
        yield ': ping\n\n'  # heartbeat ≤30s (D-02)
        yield f"data: {json.dumps({'type': 'delta', 'data': {'content': 'Hi'}}, separators=(',', ':'))}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'data': {}}, separators=(',', ':'))}\n\n"
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
# LIVE-VERIFIED: content-type: text/event-stream; charset=utf-8; NO content-encoding
# (no gzip even with fastapi[standard]); NO content-length (chunked); both headers present
```

### Ollama OpenAI-compat (live-tested on host via httpx + verified via openai SDK)
```python
import httpx
resp = await httpx.AsyncClient(timeout=120).post(
    f"{settings.AI_OLLAMA_BASE_URL}/v1/chat/completions",
    json={"model": "deepseek-coder:latest", "messages": [{"role": "user", "content": "hi"}], "stream": False},
)
# 200 with choices[0].message.content — VERIFIED live on localhost:11434
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qdrant vector DB | pgvector HNSW in shared Postgres | Phase 2 (locked) | Engine writes `school_{id}.ai_vectors` via psycopg3; no separate vector service |
| LiteLLM / Python gateway | Direct SDKs (anthropic + openai base_url + httpx Ollama) | Phase 3 D-01 (locked) | No license/version drift from a proxy layer; 5 providers first-class |
| Custom chunking/embed orchestration in Go | Python `/v1/documents` one-call pipeline | Phase 3 PYE-02/4 | Go asynq handler just POSTs to engine (asynq `ai:scoring` pattern) |
| grpc-go transport | REST/JSON + SSE (proto as contract seam) | Phase 3 PYE-04a (locked) | v1 stays simple; proto allows future gRPC |

**Deprecated/outdated:**
- Qdrant: retired from compose/k8s in Phase 2; `qdrant.go` retained only as behavioral ref — do NOT reintroduce.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Azure models-list API for health ping works with `api-version` query param (exact value unverified — e.g. `2024-10-21`-style) | Pattern 4 | Health ping for Azure may 400; fallback to 1-token chat ping (D-10 alternative) |
| A2 | Anthropic `/v1/models` response shape `{data:[...]}` per official docs | Pattern 4 | Only affects status parsing, low risk |
| A3 | `/v1/providers` returns `unavailable` (not error) for providers lacking keys | Pitfall 5 | If planner/executor choose 400 instead, Go INT-02 breaks on partial config |
| A4 | Host Ollama (`localhost:11434`, models qwen3.5:9b, gemma4:latest, deepseek-coder:latest) remains running during dev/test | Environment | If Ollama stops, Ollama-gated tests skip; Chat with ollama provider fails — dev only |
| A5 | `python:3.13-slim` in Docker Hub tracks Debian trixie at build time (verified today; base image could drift) | Dockerfile | apt package names/versions stable in trixie; low risk |
| A6 | Zero-vector rejection should be a 400 error rather than silent normalization | Pitfall 2 | Conservative choice; consistent with Phase 2 dimension-assert fail-loud pattern |

## Open Questions (RESOLVED)

1. **Azure models-list `api-version` parameter value** (A1)
   - [RESOLVED — plan 03-02 Task 2 + 03-04 Task 1] `AI_AZURE_OPENAI_API_VERSION` defaults to `"2024-10-21"` and is configurable; `/v1/providers` uses the 1-token chat ping fallback for Azure health (D-10).
2. **Ollama as a test provider**
   - [RESOLVED — plan 03-04 Task 1 + D-12] Env-gated tests (`AI_OLLAMA_BASE_URL` present + reachable); Ollama stays out of CI.
3. **Cost table currency for `cost.py`**
   - [RESOLVED — plan 03-03 Task 2] Port Go `cost.go` tables to `providers/cost.py` now; shared source is a future refactor.
4. **AI_ENABLED default**
   - [RESOLVED — plan 03-02 Task 4] compose ai-engine env expanded with `AI_PGVECTOR_DSN`, provider keys, `AI_PROMPTS_DIR`; `AI_ENABLED=true` only flipped in E2E verification tasks.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | ai-engine runtime | ✓ | 3.13.1 (pyenv) | — |
| uv | package/dep management | ✓ | 0.12.0 (`/home/playbit/.local/bin/uv`) | — |
| ai-engine/.venv | local dev | ✓ | fully synced (fastapi, httpx, uvicorn, pyright, pytest, ruff) | `uv sync` |
| shared-postgres | all DB work | ✓ | PostgreSQL 18.4, pgvector 0.8.6 (pgvector/pgvector:0.8.6-pg18-trixie) | — |
| shared-redis | (Go side only) | ✓ | running | — |
| Docker | compose build/E2E | ✓ | 28.1.1 | — |
| Ollama | dev/test provider | ✓ | running on localhost:11434 (qwen3.5:9b, gemma4:latest, deepseek-coder:latest) | env-gated test skip |
| tesseract-ocr | OCR (PYE-02) | ✗ host / ✓ apt in trixie | 5.5.0-1+b1 (candidate) | OCR tests only in Docker; host lacks binary |
| poppler-utils (pdftoppm) | pdf2image | ✓ host / ✓ apt | 26.01.0 host; 25.03.0-5+deb13u4 (trixie candidate) | — |
| Provider API keys (Anthropic/OpenAI/DeepSeek/OpenRouter/Azure) | live provider tests | ✗ (absent from backend/.env — only AI_PGVECTOR_DSN, AI_ENGINE_URL, AI_ENGINE_TOKEN, AI_EMBEDDING_DIM active) | — | env-gated skips; Ollama covers live-path |

**Missing dependencies with no fallback:**
- None blocking: tesseract needed only inside the Docker image (apt install), which is the deployment path.

**Missing dependencies with fallback:**
- Provider API keys: absent from `.env`; tests must skip cleanly (D-12). Ollama provides the only live chat path today.
- Tesseract on host: not installed — OCR verified only via Docker build; local host dev cannot run OCR tests.

## Validation Architecture

Skipped — `workflow.nyquist_validation` is explicitly `false` in `.planning/config.json` (verified). No validation test-map section required. Phase 1 CI (`ai-engine.yml`, setup-uv v9.0.0, `uv sync --frozen`) plus pytest/ruff/pyright remain the project's existing gates; D-12 testing strategy applies as a plan detail.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Service token only: `X-AI-Engine-Token` header equality check (existing `require_token`); never user JWT (locked) |
| V3 Session Management | no | Stateless service; no sessions (locked) |
| V4 Access Control | yes | Tenant isolation: `X-School-Schema` header validated `^school_[0-9]+$` + schema existence check before ANY DB access; no global fallback (D-07/D-09) |
| V5 Input Validation | yes | pydantic request models; schema regexp validation; prompt injection mitigation via provider system-prompt boundaries (templates are Jinja2, user content never evaluated) |
| V6 Cryptography | no | No secrets stored or encrypted by engine; API keys read from env only (Rule B6) |

### Known Threat Patterns for {FastAPI + psycopg3 + LLM providers}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via schema_name/query params | Tampering | Never concatenate user input into SQL except validated schema regexp (single identifier allowlisted); all values via `%s` parameters [VERIFIED: parameterized INSERT live] |
| Tenant cross-schema access | Information Disclosure | `validate_schema_name()` on every tenant-scoped request + schema existence check; reject 400 if absent on tenant routes (D-09) |
| LLM prompt injection via document content | Tampering | RAG context marked as untrusted data in system prompt; templates via Jinja2 (no eval of user content); chunk content treated as data, not instructions |
| API key leakage | Information Disclosure | Keys only in env (`AI_*_API_KEY`); never logged; `logger` (slog-style) must redact headers; no secrets in compose values committed |
| Service token brute force | Spoofing | Constant-time comparison (`hmac.compare_digest`) rather than `!=` string compare in `require_token` |
| DoS via unbounded streaming/extract | Denial of Service | Cap document size/page count; chat max_tokens bounded; `ExtractTimeout=5m` parity on Python side; request size limits |

## Sources

### Primary (HIGH confidence)
- **PyPI registry (live, 2026-08-01):** anthropic 0.120.2, openai 2.52.0, tenacity 9.1.4, pypdf 6.14.2, pdf2image 1.17.0, pytesseract 0.3.13, python-docx 1.2.0, python-pptx 1.0.2, openpyxl 3.1.5, Pillow 12.3.0, psycopg 3.3.4, psycopg-pool 3.3.1, pgvector 0.5.0, fastapi 0.141.1 (latest; project pins 0.140.13)
- **Repo files (read directly):** `ai-engine/pyproject.toml`, `uv.lock`, `app/main.py`, `app/config.py`, `Dockerfile`; `backend/internal/ai/engine/engine.go`, `sse.go`, `client.go`; `backend/internal/ai/vector/pgvector.go`; `backend/internal/config/config.go`; `backend/internal/database/migrations/school/school.go` (Group 28, lines 1424-1486); `backend/docker-compose.yml`; `backend/.env`; `backend/internal/router/setup.go`
- **Live probes (2026-08-01, all PASS):** `/tmp/opencode/pgv_probe.py` (pgvector round-trip vs shared-postgres); `/tmp/opencode/sse_probe.py` (Go scanner parity); `/tmp/opencode/sse_fastapi_probe.py` (StreamingResponse headers); Ollama `/api/tags` + `/v1/models` + `/v1/chat/completions` live; `uv add` scratch resolution (76 packages, fastapi pin preserved)
- **Environment audit (live):** `python --version` 3.13.1, `uv --version` 0.12.0, `docker --version` 28.1.1, `psql` introspection (12 schemas, ai_vectors columns/indexes, 0 rows), apt-cache on python:3.13-slim (tesseract 5.5.0, poppler 25.03.0)

### Secondary (MEDIUM confidence)
- Anthropic API docs — models-list endpoint + `messages.stream()` async pattern [CITED: docs.anthropic.com]
- DeepSeek docs — `https://api.deepseek.com` base URL + `/models` [CITED: api-docs.deepseek.com]
- OpenRouter docs — `https://openrouter.ai/api/v1` base URL [CITED: openrouter.ai/docs]
- Azure OpenAI docs — `https://{resource}.openai.azure.com/openai/v1` + models-list API [CITED: learn.microsoft.com]
- Ollama docs — `/api/tags`, OpenAI-compat `/v1/chat/completions` [CITED: github.com/ollama/ollama — cross-verified live]

### Tertiary (LOW confidence)
- Azure models-list `api-version` exact parameter value (A1) — WebSearch only, needs config or fallback
- Provider cost table values for `cost.py` parity with Go `cost.go` — needs code comparison at implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified live on PyPI/uv.lock; `uv add` resolution proven
- Architecture: HIGH — SSE envelope + DB patterns proven 1:1/live; provider patterns from official docs
- Pitfalls: HIGH — 4 of 6 hit live during this research; remaining 2 from locked decisions
- Assumptions: LOW-MEDIUM — 6 items logged, all with mitigations, none blocking

**Research date:** 2026-08-01
**Valid until:** 2026-08-08 (fast-moving: package versions may bump; base image trixie stable; re-verify `uv add` pins if >7 days lapse)
