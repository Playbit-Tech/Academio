# Architecture Research: AI Platform for Academio (Python ai-engine + pgvector RAG)

**Domain:** Multi-tenant school ERP with an additive Python AI compute service behind an existing Go modular monolith
**Researched:** 2026-07-31
**Confidence:** HIGH for pgvector multi-tenancy and SSE relay patterns; MEDIUM for Go↔Python seam specifics (fewer authoritative sources, pattern is emergent but converging)

## Executive Position

Academio's AI platform should be a **two-runtime modular monolith**: Go stays the single entry point, the brain, and the owner of all state (auth, tenancy, queue, audit, cost); Python `ai-engine` is a **stateless AI compute service** that Go calls over REST/JSON + SSE. The 2026 ecosystem strongly validates this split: production AI agent systems increasingly use Go at the edge (concurrency, memory footprint, SSE relay) and Python for LLM/doc intelligence (provider SDK maturity, OCR, ecosystem), with Redis as the async shock absorber between them. The critical architectural insight from multi-tenant RAG research is that **the tenant boundary should be structural, not a WHERE clause** — and Academio already has the perfect structural boundary: **schema-per-tenant**. The `ai_vectors` table should live in `school_{id}` schemas, which eliminates the entire class of HNSW tenant-filter recall and cross-tenant leakage problems that plague shared-table pgvector deployments. The single biggest cross-cutting constraint: **one canonical embedding model and dimension for the entire platform**, because Go's existing RAG and Python's new document pipeline write into the same store.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER (never talks to Python)                  │
│   React web app  ·  Flutter mobile app                                        │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │ HTTPS (user JWT)
┌───────────────────────────────────▼──────────────────────────────────────────┐
│                        GO MONOLITH — the brain (single entry point)          │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  Auth +  │  │  Tenant  │  │  AI Orches-  │  │  asynq worker (ai:doc-    │ │
│  │  RBAC    │  │ resolver │  │  trator      │  │  ingest) — Go runtime     │ │
│  │  JWT     │  │ school_  │  │  (rate limit,│  │  calls Python, owns       │ │
│  │          │  │  {id}    │  │  quota,      │  │  retries, events, notify  │ │
│  │          │  │          │  │  audit,      │  │                           │ │
│  │          │  │          │  │  cost ledger)│  │                           │ │
│  └──────────┘  └──────────┘  └──────┬───────┘  └────────────┬──────────────┘ │
│                                     │                        │                │
│  ┌──────────────────────────────────┼────────────────────────┼──────────────┐ │
│  │  EXISTING Go AI (unchanged)      │                        │              │ │
│  │  ModelRouter (gemini↔openai) ────┼── + python entry ──────┼── new        │ │
│  │  10 agents · RAG · NL search     │                        │              │ │
│  │  vector.Store (Qdrant→pgvector)  │                        │              │ │
│  └──────────────────────────────────┼────────────────────────┼──────────────┘ │
│  EngineClient (HTTP/JSON + SSE,     │                        │                │
│  gRPC-ready interface)              │                        │                │
└─────────────────────────────────────┼────────────────────────┼────────────────┘
                                      │ REST/JSON + SSE        │ REST/JSON
                                      │ X-AI-Engine-Token      │ X-AI-Engine-Token
                                      │ X-Request-ID           │ X-Request-ID
┌─────────────────────────────────────▼────────────────────────▼────────────────┐
│                    PYTHON ai-engine — stateless AI compute                     │
│                                                                               │
│  ┌────────────┐ ┌────────────┐ ┌─────────────┐ ┌───────────────────────────┐  │
│  │ Chat       │ │ Providers  │ │ Extraction  │ │ Tenant-aware RAG          │  │
│  │ /v1/chat   │ │ (LiteLLM   │ │ /v1/extract │ │ hybrid search, rerank,    │  │
│  │ /v1/chat/  │ │  Router)   │ │ OCR         │ │ citations, compression    │  │
│  │ stream SSE │ │ Anthropic  │ │ PDF/DOCX/   │ │ /v1/search               │  │
│  │            │ │ DeepSeek   │ │ PPTX/img    │ │                           │  │
│  │ /v1/embed  │ │ OpenRouter │ │ chunking    │ │                           │  │
│  │            │ │ Azure,     │ │ embeddings  │ │                           │  │
│  │            │ │ Ollama     │ │             │ │                           │  │
│  └────────────┘ └────────────┘ └──────┬──────┘ └────────────┬──────────────┘  │
│                                       │                     │                 │
│  No auth, no tenant decisions, no queue, no business rules — pure compute     │
└───────────────────────────────────────┼─────────────────────┼─────────────────┘
                                        │ direct DB (trusted   │
                                        │ schema-qualified)    │
┌───────────────────────────────────────▼─────────────────────▼─────────────────┐
│                        SHARED INFRASTRUCTURE                                  │
│  PostgreSQL (public + school_{id} schemas)  ·  pgvector  ·  Redis/asynq       │
│  uploads volume (api ↔ ai-engine both mount) · Prometheus · Grafana           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Boundary / Key Rule |
|-----------|----------------|---------------------|
| **Go API + AI Orchestrator** (`internal/modules/ai`, `internal/ai/orchestrator/`) | JWT auth, tenant resolution, RBAC, rate limiting, quota, audit every AI request, cost ledger, Redis cache, retries/circuit breakers on Python calls, event publish | Only component that talks to clients. Never delegates auth/tenancy to Python |
| **Go EngineClient** (`internal/ai/engine/`) | Interface `EngineClient` + `httpClient` impl (REST/JSON + SSE). gRPC-ready: swap impl later, callers unchanged | Service-token auth (`AI_ENGINE_TOKEN`), `X-Request-ID` correlation. Mirror existing `StreamCallback` pattern from `gateway.go` |
| **Go ModelRouter** (existing) | Platform-level provider routing + failover (gemini ↔ openai ↔ python) | Python added as one `providerEntry` via the existing (currently unused) `addProvider` hook — **two-level routing** |
| **Go asynq worker** (`ai:doc-ingest`) | Dequeue, resolve tenant DB by school ID (audit-middleware `tenantDBResolver` pattern), call Python `/v1/documents`, update `ai_documents` status, publish event, notify | Owns the queue. Python never touches asynq. Payload carries `{documentID, schoolID, userID, requestID}` |
| **Python ai-engine** | LLM integrations (5 new providers), embeddings, OCR/extraction, chunking, tenant-aware hybrid RAG, reranking, citations, versioned prompt library | Stateless. No user auth, no queue, no business rules. Re-enforces tenancy by validating `schema_name` (`^school_\d+$`) and scoping all pgvector access to it |
| **pgvector store** (`school_{id}.ai_vectors`) | Single source of truth for chunks (both Go RAG and Python RAG read/write it) | Tenant schema = structural isolation. `collection` maps to a column, not a namespace, because the schema already scopes the tenant |
| **Shared infra** (Postgres, Redis/asynq, uploads volume, Prometheus/Grafana) | State, queue, file passing, observability | `api` and `ai-engine` containers both mount the uploads volume — files are passed by path, not re-transferred over HTTP |

### Two Critical Locked-in-Advance Decisions

These two decisions shape everything below and must be locked before Phase 1 (pgvector) starts.

#### Decision 1: `ai_vectors` lives in the **tenant schema** (`school_{id}`), not `public`

The implementation plan's PGV-04 ("tenant-scoped partial indexes") implies a shared `public.ai_vectors` table. **Recommendation: put the table in the tenant schema instead.** Rationale:

1. **It matches Academio's hard pattern.** AGENTS.md: all school-specific models live in tenant schemas via `SchemaTablePrefix`; the pgvector Store impl gets a schema-scoped `*gorm.DB` and gets isolation for free — no `WHERE tenant_id = ?` to forget, no RLS to misconfigure, no `SET LOCAL app.tenant_id` plumbing.
2. **It eliminates the HNSW tenant-filter problem entirely.** The single biggest pgvector multi-tenancy failure mode (documented by pgvector itself and every 2026 multi-tenant RAG source): with a shared table, HNSW applies the tenant filter *after* the index scan → "under-return" (a tenant with 10% of rows gets ~4 results at default `ef_search=40`), and per-tenant partial indexes must be created/dropped/rebuilt operationally. A per-schema HNSW index only ever contains that tenant's vectors — correct recall, no tuning, no lifecycle management.
3. **It closes a latent isolation gap.** The current Qdrant store uses global collections (`curriculum`, `policies`) with **no tenant namespacing** — today, all schools share one vector pool. Schema-per-tenant pgvector fixes this structurally.
4. **Cost of the choice is low.** Index creation on a fresh schema is instant; HNSW index overhead is proportional to rows, so thousands of small tenant schemas cost little.

Keep `school_id`, `collection`, `document_id`, etc. as columns for reporting/audit; `tenant_id` column becomes redundant (the schema *is* the tenant) but harmless.

Consequence: the existing `vector.Store` interface (`Insert(ctx, collection, docs)`, `Search(ctx, collection, query, limit)`, `Delete`, `Close`) has no tenant parameter. The pgvector implementation resolves tenancy from context: `middleware.GetSchoolIDFromCtx(ctx)` + a tenant-DB resolver injected at construction (same pattern as `middleware/audit.go`'s `tenantDBResolver`). The `collection` parameter maps to a `collection`/`module` column filter within the tenant schema. Zero changes to the RAG pipeline or agents — the interface contract is preserved.

**This changes PGV-04's migration**: table + HNSW index created in each tenant schema migration (and in the school-migration runner used at provisioning), not one shared table with partial indexes. Flag for the roadmap.

#### Decision 2: One canonical embedding model + dimension for the whole platform

Go's existing RAG and Python's document pipeline both write to `school_{id}.ai_vectors`. pgvector columns are dimension-fixed (`vector(1536)` — you cannot mix 768 and 3072 in one column). Therefore:

- **One canonical embedding provider/model** (e.g., `text-embedding-3-small`, 1536d — recommended: whatever the existing Go pipeline already uses, to avoid re-embedding) is used by **both** runtimes.
- Dimension pinned in config (`AI_EMBEDDING_DIM`), with a startup validation that the configured model's output dimension matches the column type (Go B12-style fail-fast).
- Store `embedding_model` on every chunk and on `ai_documents`; a migration/validation guard rejects mismatches.

Two embedding models = two incompatible vector spaces in one table = silent RAG quality collapse. This is the highest-severity silent-failure risk in the whole effort.

---

## Recommended Project Structure

### New: `ai-engine/` (private submodule, root of monorepo)

```
ai-engine/
├── pyproject.toml               # Python 3.13, uv/pip, pinned deps
├── Dockerfile                   # multi-stage, non-root, healthcheck
├── proto/
│   └── aiengine.proto           # THE gRPC contract (v1: reference only, REST serves it)
├── app/
│   ├── main.py                  # FastAPI app, middleware, route mounting
│   ├── config.py                # pydantic-settings: provider keys, pgvector DSN,
│   │                            # AI_ENGINE_TOKEN, embedding model/dim, timeouts
│   ├── api/                     # HTTP layer only — thin, delegates to core/
│   │   ├── chat.py              # /v1/chat, /v1/chat/stream (SSE)
│   │   ├── embed.py             # /v1/embed
│   │   ├── documents.py         # /v1/extract, /v1/documents (ingest)
│   │   ├── search.py            # /v1/search (hybrid, rerank, citations)
│   │   └── providers.py         # /v1/providers (status for Go INT-02)
│   ├── core/                    # service layer — NO HTTP deps → gRPC can call it later
│   │   ├── chat.py              # ChatService: RAG context build → provider call
│   │   ├── extraction.py        # PDF/DOCX/PPTX/TXT/CSV/OCR (Tesseract)
│   │   ├── chunking.py          # semantic/recursive chunkers (800 tok / 200 overlap)
│   │   ├── embedding.py         # canonical embedding model wrapper
│   │   ├── rag.py               # tenant-aware hybrid search, metadata filters,
│   │   │                        # reranking, citations, context compression
│   │   └── providers.py         # multi-provider abstraction (LiteLLM Router)
│   ├── db/
│   │   └── pgvector.py          # schema-qualified access to school_{id}.ai_vectors
│   │                            # + schema_name validation (^school_\d+$)
│   ├── schemas/                 # pydantic request/response models (the wire contract)
│   ├── prompts/                 # versioned prompt library: v1/report_comments.py, ...
│   └── telemetry.py             # JSON logs, request-id middleware, /metrics
├── tests/                       # pytest: unit, integration, RAG-accuracy,
│                               # cross-tenant probe suite, load
└── monitoring/                  # Grafana dashboard json (optional)
```

Rationale: `core/` has zero HTTP imports so a future gRPC server (`grpc_aiengine.py`) calls the same services — this is the concrete meaning of "gRPC-ready seam" on the Python side. `proto/aiengine.proto` is committed now as the interface contract even though v1 transports over REST; it prevents contract drift and makes the gRPC swap mechanical.

### Go additions (additive, no rewrites)

```
backend/internal/ai/
├── engine/                      # NEW — the seam
│   ├── client.go                #   EngineClient interface (Chat, ChatStream w/ StreamCallback,
│   │                            #   Embed, Extract, IngestDocument, Search, Providers, Health)
│   ├── http.go                  #   REST/JSON + SSE implementation
│   └── sse.go                   #   SSE-aware bufio scanner (event-boundary splitting)
├── vector/
│   ├── store.go                 # existing interface — unchanged
│   ├── qdrant.go                # existing — kept behind interface during cutover
│   └── pgvector.go              # NEW — tenant-context-resolving Store impl
├── orchestrator/                # NEW — rate limit, quota, audit, cache, retry-on-Python
└── (model_router.go gains a "python" providerEntry; addProvider hook already exists)
```

Also new: `backend/internal/modules/ai/documents.go` (upload + status endpoints), `backend/internal/queue/` gains `TypeDocIngest = "ai:doc-ingest"` + `NewDocIngestTask` (mirror `NewAIScoringTask`), `backend/internal/router/setup.go` gains `newDocIngestHandler`.

---

## Architectural Patterns

### Pattern 1: Orchestrator / Compute Split ("Go is the brain, Python is the engine")

**What:** Go owns everything that must be fast, correct, and secure (edge, auth, tenancy, orchestration, queueing, audit, cost); Python owns everything that needs AI libraries (LLM SDKs, OCR, chunking, reranking). Python is never exposed to clients and never owns state.
**When to use:** Any AI capability added to an existing business system. Validated by 2026 production patterns: Go-edge/Python-worker gateways (Sentinel, gomlx), and every "AI agent API" architecture guide (orchestrator layer mandatory; never call LLMs from frontends; queue as the shock absorber between fast and slow work).
**Trade-offs:** Two runtimes to operate — mitigated by Python being stateless (all state is shared Postgres/Redis), health-checked, and scaled independently. The alternative (all-AI-in-Go) fails on OCR/doc-intelligence library maturity; the alternative (all-AI-in-Python) regresses on concurrency, memory footprint, and forces moving auth/tenancy/queue that already work in Go.
**Example:** Go worker for `ai:doc-ingest` calls `POST /v1/documents`; Python does parse→chunk→embed→store and returns a manifest; Go updates status, publishes `document.ingested` event, notifies the user. Python's entire world is "a request came in with a trusted school_id + a file path".

### Pattern 2: Two-level provider routing (Go ModelRouter → Python LiteLLM Router)

**What:** Level 1 = Go's existing `ModelRouter` routes at the platform level: `gemini ↔ openai ↔ python` as failover chain entries (each entry wrapped in its existing circuit breaker). Level 2 = inside Python, a provider abstraction routes across Anthropic/DeepSeek/OpenRouter/Azure OpenAI/Ollama. Go treats Python as **one** provider with its own internal failover.
**Why two levels:** Go keeps the single platform-level failover/cost/audit decision point (existing behavior, no rewrite — INT-04 wires Python in as a `providerEntry`). Python gets provider breadth without exposing individual Python providers to Go's routing logic.
**Implementation:** Use **LiteLLM Router (SDK mode, not the proxy server)** for Python's abstraction. It natively supports exactly the five target providers (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama), plus streaming, cooldowns, TPM/RPM via Redis, and cost calculation — all of which the plan (PYE-01) would otherwise hand-roll in ~300 fragile lines. Do **not** run the LiteLLM proxy server: it brings its own auth/DB/UI that would compete with Go's orchestrator (which must remain the single authz/audit point).
**Trade-offs:** Failover logic exists in two places — mitigated by strict timeouts: Go→Python call timeout (e.g., 120s chat) must be **larger** than Python→LLM timeout (e.g., 90s), so Go's circuit breaker sees timeouts as Python failures and can fail over to Gemini, while Python's own cooldown handles transient provider 429s. Layered like this, the two levels don't fight.
**Cost rule:** Python must return `provider`, `model`, `input_tokens`, `output_tokens`, `cost` in every response (JSON and the final SSE `usage` event). **Go centralizes the cost ledger** — Python never writes cost/audit records itself; it reports usage, Go records it (matches existing `cost.go`/audit).

### Pattern 3: SSE relay with context propagation, bounded buffering, in-band errors

**What:** The SSE chain is browser ← Go `/api/v2/ai/chat/stream` ← Python `/v1/chat/stream` ← LLM provider. Both hops must be real-time relays, not buffers. Production-proven Go relay mechanics (Preto.ai at 5,000+ streaming req/s, <50ms p95 overhead; also stream-relay-go, cc-relay):

1. **Event-boundary-aware reader**: parse upstream SSE with a `bufio.Scanner` + custom split on `\n\n` — never blind `io.Copy` (chunk-boundary corruption: one SSE event split across TCP packets = corrupted JSON delta).
2. **Context cancellation on client disconnect**: Go handler's `r.Context()` is cancelled when the browser disconnects; pass it into the upstream Python HTTP call (`http.NewRequestWithContext(ctx, ...)`). Without this, Python keeps generating and the user is billed for tokens nobody receives. On the Python side, FastAPI `StreamingResponse` cancellation propagates to httpx → provider (standard async/await, no extra code).
3. **Bounded backpressure**: reader goroutine → buffered channel (`cap 64`) → writer goroutine; if the writer can't consume within a timeout (e.g., 5s — slow client), abort the stream instead of buffering unboundedly (OOM under slow-client load).
4. **In-band errors after 200**: once the HTTP 200 is sent you cannot change the status; a mid-stream failure must be a final SSE event `data: {"error":{...}}`. Clients check every event for an `error` key, not just the status code.
5. **Headers**: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`; heartbeat comment (`: ping\n\n`) every 25–30s to survive proxies/firewalls.

**One SSE event envelope, shared everywhere:** define event types once (Python → Go → browser use the same JSON shape): `delta` (token text), `tool_call` (agent tool events, if applicable), `citation` (RAG source references), `usage` (final: tokens + cost), `error`, `done`. The Go relay passes events through with optional annotation (e.g., injecting request_id), never re-parsing provider formats. This is INT-01's core: today streaming exists only at the provider layer; this pattern lifts it to an HTTP route without changing provider code.

### Pattern 4: gRPC-ready seam (interface now, transport later)

**What:** The contract is the interface, not the wire protocol.
- **Go:** `EngineClient` interface with methods mirroring the existing `Provider` shape (`ChatStream(ctx, req, cb StreamCallback)` maps 1:1 to a gRPC server-streaming `recv` loop). `httpClient` implements it today; a future `grpcClient` swaps in without touching callers.
- **Python:** all logic lives in `app/core/` with zero HTTP imports; routes are thin adapters. A future `grpc/` server imports the same service classes.
- **Proto as contract:** commit `proto/aiengine.proto` now (service `AIEngine { rpc Chat(...) / ChatStream(...) / Embed(...) / Extract(...) / IngestDocument(...) / Search(...) }`). REST endpoints must satisfy the proto semantics 1:1 (same request/response field names), so the gRPC swap is a translation layer, not a redesign.
**When to use:** When the service is expected to outlive the transport choice — here, FastAPI-native REST + SSE is debuggable and matches existing conventions; gRPC adds nothing for the current single-service scale but the seam costs ~nothing.
**Trade-offs:** Some double-maintenance (proto + pydantic schemas) — acceptable; skip gRPC entirely if you never expect to add a second Python service or heavy internal traffic.

### Pattern 5: Async job pipeline (queue → Go worker → Python → vector → event → notify)

**What:** The spec's exact flow, refined: upload → Go validates + saves file to uploads volume → insert `ai_documents` row (status `queued`) → enqueue asynq `ai:doc-ingest` → Go worker resolves tenant DB by schoolID (audit `tenantDBResolver` pattern) → calls Python `/v1/documents` (extract+chunk+embed+store in **one** call) → Python writes `school_{id}.ai_vectors`, returns manifest → Go updates status + publishes `document.ingested` / `document.failed` event → notification engine notifies.
**Key refinement vs plan (PIP-01):** make it **one Go→Python call**, not `/v1/extract` then a second chunk/embed step. Python is stateless compute; splitting adds a second round-trip, a mid-pipeline state handoff, and duplicate failure handling for no benefit. `/v1/extract` (parse-only) still exists as a standalone endpoint for future features (preview, re-extract), but the pipeline uses `/v1/documents`.
**Retry semantics:** asynq retry (3 attempts, exponential backoff) for transient failures (timeouts, 5xx, provider 429s); **no retry** for permanent failures (corrupt PDF, unsupported type — mark `failed` with the error message, notify immediately). This is the difference between a self-healing pipeline and a poison-message loop.
**File passing:** both `api` and `ai-engine` containers mount the shared uploads volume; the worker passes a file path + schoolID, Python reads it locally. Avoids multipart re-transfer, works for large PDFs, keeps Python containers stateless (a replica can pick up any file).

### Pattern 6: Tenant boundary in the schema; Python re-enforces, never re-decides

**What:** Tenancy is resolved **once**, in Go, from the verified JWT (never from a request body or LLM tool argument). Go passes `school_id` + `schema_name` to Python inside the service-to-service call. Python (a) validates `schema_name` against `^school_\d+$` (SQL-injection guard — schema names are identifiers that cannot be parameterized), (b) scopes every pgvector query to that schema, (c) throws if the schema is missing — it never falls back to a global index (the `tenantOnlyMode` invariant from production B2B LMS research).
**Why:** every 2026 multi-tenant RAG source converges on the same three rules: resolve tenancy at the edge from the session; make the unscoped query un-expressible (schema prefix in Go, mandatory schema arg in Python); and prove isolation with a **cross-tenant probe test suite in CI** (seed tenants A and B with canary chunks, query A with B's canary terms, assert zero hits — through every path: RAG search, cached retrievals, reranking, agent tool calls, background jobs). Isolation is measured on every deploy, not asserted once.

---

## Data Flow

### Flow 1: Chat (non-stream)

```
Browser ──POST /api/v2/ai/chat (JWT)──▶ Go handler
  → middleware: auth, school_id, tenant schema DB, rate limit, quota check
  → Orchestrator: audit event, load conversation (shared schema), build context
  → ModelRouter.resolveProvider → providerEntry "python" (or gemini/openai)
  → EngineClient.Chat(ctx, {school_id, agent, messages, prompt_version, request_id})
  → Python /v1/chat → ChatService → RAG retrieval (school_{id}.ai_vectors, metadata
    filters) → prompt assembly (versioned library) → LiteLLM Router → LLM provider
  → usage {provider, model, tokens, cost} returned in response
  → Go: records cost/audit, caches response (Redis, key includes school_id!)
  → browser receives JSON
```

### Flow 2: Chat (streaming) — SSE relay

```
Browser (EventSource/fetch) ──POST /api/v2/ai/chat/stream──▶ Go
  → Go handler: validate, set SSE headers (X-Accel-Buffering: no), flush 200
  → EngineClient.ChatStream(ctx=request ctx, cb) → http.go: POST Python /v1/chat/stream
  → Python: StreamingResponse → provider SSE → re-emits events: delta/citation/usage/done/error
  → Go: SSE-aware scanner → bounded channel → cb() → write+flush per event
  → Browser parses the shared event envelope (checks every event for "error")
  On disconnect: r.Context() cancelled → upstream Python call cancelled → provider
  generation stops → no token leak. Python final `usage` event → Go records cost async.
```

### Flow 3: Document ingestion (async pipeline)

```
Browser ──POST /api/v2/ai/documents (multipart, JWT)──▶ Go
  → validate perms, file type/size → save to uploads volume
  → insert ai_documents (school_{id} schema, status=queued)
  → asynq.Enqueue(NewDocIngestTask{documentID, schoolID, userID, requestID}) → 202 Accepted
  → [asynq] Go worker (newDocIngestHandler):
        resolve tenant DB via dbManager.ForSchoolSchema(ctx, schoolID, schemaName)
        call Python POST /v1/documents {file_path, school_id, schema_name, metadata, request_id}
        Python: validate schema_name → parse/OCR → chunk (semantic 800/200)
                → embed (canonical model) → INSERT school_{id}.ai_vectors (batched)
                → return {chunk_count, pages, status:"ready", embedding_model}
  → Go worker: UPDATE ai_documents status=ready + chunk_count
        → publish event document.ingested → notification engine → user notified
  On failure (permanent): status=failed + error message, event document.failed, notify. No retry.
  Browser polls GET /api/v2/ai/documents/:id/status (or frontend listens for the notification)
```

### Flow 4: Search / RAG (both runtimes, one store)

- **Go path (existing agents):** agent tool → `rag.Pipeline.SearchText` → `vector.Store.Search` → **pgvector.go** resolves schoolID from ctx → schema-scoped DB → `school_{id}.ai_vectors WHERE collection = ? ORDER BY embedding <=> ? LIMIT k`. Interface-compatible, zero RAG/agent changes.
- **Python path:** browser → Go `/v1/search` (or chat w/ RAG) → Python `/v1/search` → hybrid search (vector + full-text, e.g., `pg_trgm`/tsvector on chunk text) → metadata filters (collection, document_type, academic_calendar_id, visibility) → rerank → citations. Both paths hit the same table.

### Flow 5: Provider status

```
GET /api/v2/ai/providers ──▶ Go: merges local provider state (gemini/openai circuit
  breaker status) + EngineClient.Providers() → Python /v1/providers (LiteLLM Router
  deployment status, cooldowns) → single combined response for the frontend.
```

### State management

| State | Owner | Where |
|-------|-------|-------|
| Conversations, messages | Go | `public` shared schema (`ai_conversations`, `ai_messages`), school-scoped — existing |
| Documents + status | Go | tenant schema `school_{id}.ai_documents` (status: queued→extracting→chunking→embedding→storing→ready/failed) |
| Chunks + embeddings | Python writes, Go reads (and vice versa) | tenant schema `school_{id}.ai_vectors` (the single source of truth) |
| Queue jobs | Go (asynq) | Redis |
| Rate limits, quota, response/embedding cache | Go | Redis — **cache keys MUST include school_id** (shared-cache cross-tenant leak is the most common real-world RAG breach) |
| Cost/usage/audit ledger | Go | existing audit + cost tables; Python reports usage only |
| Provider config + keys | Both, independently | Go `AI_*` env; Python `config.py` from env — encrypted at rest (SEC-01) |

---

## Multi-Tenant Isolation (explicit)

**Isolation model: silo (schema-per-tenant), the strongest tier of the AWS SaaS Lens silo/pool/bridge taxonomy.** Academio already ships this; the AI platform must not regress it.

| Layer | Mechanism |
|-------|-----------|
| Vector storage | `ai_vectors` in `school_{id}` schema; per-schema HNSW index (structurally tenant-scoped; no partial-index management, no RLS needed, no `SET LOCAL` plumbing) |
| Go queries | `middleware.GetTenantDB(c)` / worker `dbManager.ForSchoolSchema(ctx, schoolID, schemaName)` — schema prefix plugin qualifies every table |
| Python queries | Mandatory `schema_name` (validated `^school_\d+$`) on every pgvector statement; missing schema ⇒ error, **never** global fallback; parameterized queries only (Rule B7 discipline in Python) |
| Chat/context | RAG retrieval scoped to the request's school; citations only from that school's chunks |
| Cache | Redis keys prefixed with `school_id` |
| AuthZ | Python sees no user JWT; service token (`AI_ENGINE_TOKEN`) only; Go enforces RBAC per endpoint |
| Files | Uploads stored under school-scoped paths; Python only reads paths Go supplies |
| Logs | Request logs carry school_id; never log document contents or prompt bodies verbatim (PII masking per SEC-01) |
| Audit | Every AI mutation audited by Go (Rule B11) with SchoolID, UserID, Action, ResourceType, RequestID |
| Test | CI cross-tenant probe suite: canary chunks per tenant, query across all retrieval entry points (search, cached retrieval, rerank, agent tools, worker paths), assert zero leakage; delete-probe after offboarding |

Threat model note: Go is the trusted authority; Python trusts Go (service-token + internal network + schema validation). The residual risk — a compromised Python — is bounded by Python having no user-auth surface and holding only the shared DB role with schema-scoped access. Do not give Python a superuser DB role.

---

## Build Order (dependencies for the roadmap)

```
Phase 0  Foundation (seam)          EngineClient interface + http impl, config,
                                    docker-compose service, CI. No behavior change.
Phase 1  pgvector migration  ◄────── LOCK the two decisions (table placement,
                                    embedding canon) FIRST. Image swap, extension,
                                    tenant-schema table + index, pgvector Store impl
                                    (tenant-from-ctx), interface-conformance tests,
                                    Qdrant data copy, config swap, retire qdrant.
Phase 2  Python engine               FastAPI skeleton, service-token middleware,
                                    telemetry, /health, multi-provider (LiteLLM)
                                    /v1/chat + /v1/chat/stream, /v1/embed.
Phase 3  Chat streaming route  ────── depends on Phase 0 (client) + Phase 2 (Python
        (INT-01 SSE relay)           SSE). Independent of Phase 1.
Phase 4  Doc pipeline          ────── depends on Phase 1 (vectors exist) + Phase 2
        (upload, asynq task, worker, (extraction/embedding) + shared volume mount.
        /v1/documents, status,
        events, notify)
Phase 5  Python RAG + integration    /v1/search hybrid + rerank + citations
        (PYE-05, INT-02/03/04) ────── depends on Phase 4 (documents to search).
                                        ModelRouter python entry, /v1/providers,
                                        orchestrator hardening (rate limit, quota,
                                        cache, retries, audit).
Phase 6  Observability, security,    metrics/correlation across runtimes, PII
        testing                      masking, RAG-accuracy + cross-tenant probe
                                     suites, load tests.
```

Critical path: P0 → P1 → P2 → P4 → P5. P3 can proceed in parallel after P0+P2. P1 and P2 are independent of each other except for the embedding-canon decision (must be shared) and the shared volume (P4).

Phase 2 includes writing `proto/aiengine.proto` as the contract (cheap now, expensive to retrofit).

---

## Scaling Considerations

| Scale | Approach |
|-------|----------|
| 1–100 schools, dev/staging | Single Python replica, single Go API, per-school schemas are near-empty (HNSW index creation instant). REST/SSE + LiteLLM Router. No RLS/partial-index machinery needed at all (schema silo) |
| 100–1,000 schools | Python scales horizontally (stateless; replicas behind the compose network/health checks). HNSW per schema handles ~10M vectors per school before tuning (pgvector production ceiling per index); `hnsw.ef_search` tunable per query. Redis cache + rate limiting now mandatory (Go side) |
| 1,000+ schools / whale tenants | Partitioning inside the tenant schema (`ai_vectors` by `collection`) if a single school exceeds ~10M chunks; batch embedding with retry/backoff for ingestion; queue depth metrics + worker concurrency tuning; consider dedicated Python replicas for ingestion vs chat (different latency profiles — the "fast edge, smart compute" split, scaled independently) |

**First bottleneck:** chat streaming latency — fix by SSE relay correctness (flush per event, no buffering) + LiteLLM streaming. **Second:** ingestion throughput — fix by batch embeddings, asynq worker concurrency, and the shared-volume path (no multipart re-transfer). The research consensus: pgvector + HNSW is the reasonable default up to ~10M vectors per index — and schema-per-tenant means each index is a *school's* corpus, so this ceiling is far away per tenant.

---

## Anti-Patterns

### Anti-Pattern 1: Python touches the queue / owns async orchestration
**What people do:** FastAPI + Celery + Redis streams inside the AI service because "that's how Python AI services work."
**Why wrong:** Two queues (asynq + Celery), two consumer groups, split ownership of the job lifecycle; the spec and plan already lock asynq→Go worker→Python. Python must stay a pure HTTP compute service.
**Do instead:** asynq in Go is the only queue. Python's HTTP call is the async boundary. (Deviation from the generic 2026 "FastAPI+Celery" default is correct here because the queue already exists in Go.)

### Anti-Pattern 2: Python re-implements auth/tenancy, or trusts client-supplied tenant IDs
**What people do:** Python validates JWTs, or reads `tenant_id` from the request body/prompt/tool arguments.
**Why wrong:** Two auth implementations drift; a model-supplied tenant id is a confused deputy — the single most common multi-tenant RAG breach vector.
**Do instead:** Go resolves tenancy from the JWT; Python receives it from Go, validates the schema identifier, and enforces it structurally in every query.

### Anti-Pattern 3: Two embedding models / mixed dimensions in one store
**What people do:** Go RAG keeps Gemini embeddings while Python ingests with a different model. pgvector columns are dimension-fixed; mixing models = two incompatible vector spaces.
**Why wrong:** Silent, unrecoverable RAG quality collapse; the "10% match" bug looks like missing features.
**Do instead:** Lock the canonical embedding model + dimension (Decision 2), validate at startup and at ingest, store `embedding_model` per chunk.

### Anti-Pattern 4: Buffered SSE relay (blind `io.Copy`), no context cancellation
**What people do:** `io.Copy(w, resp.Body)`; forget `r.Context()`; buffer upstream in memory.
**Why wrong:** Chunk-boundary corruption, token leaks billed after client disconnect, OOM under slow clients (all four documented production SSE proxy failure modes).
**Do instead:** Pattern 3 mechanics (SSE-aware scanner, ctx propagation, bounded channel, in-band errors, `X-Accel-Buffering: no`, heartbeats).

### Anti-Pattern 5: Shared cache without tenant in the key
**What people do:** Cache prompt→response by question hash only. Tenant A's answer gets served to tenant B.
**Why wrong:** The most common real-world RAG leak; looks fine in demos.
**Do instead:** Cache key = `{school_id}:{user_scope}:{prompt_hash}`; cross-tenant probe tests include cache paths.

### Anti-Pattern 6: Duplicate vector stores (Go table + Python table)
**What people do:** Python writes its own "python_vectors" table because the Go interface looks limited.
**Why wrong:** Two sources of truth, chunk fragmentation, search results that disagree.
**Do instead:** One `school_{id}.ai_vectors` table. Go's interface maps `collection`→column; Python does the richer queries against the same table.

### Anti-Pattern 7: Per-request HTTP clients in Python
**What people do:** `httpx.AsyncClient()` inside every handler.
**Why wrong:** TLS handshake + connection churn per LLM call (100–150ms overhead each).
**Do instead:** One shared `httpx.AsyncClient` (connection pooling, HTTP/2 where supported) at app startup; same for the pgvector pool.

### Anti-Pattern 8: Shared-table pgvector with WHERE-clause tenancy and global HNSW
**What people do:** Follow generic pgvector tutorials: one `public` table, `WHERE tenant_id = ?`, one HNSW index.
**Why wrong:** Post-filter under-return (silent recall loss) + RLS/partial-index operational machinery + the whole class of forgotten-predicate leaks.
**Do instead:** Schema-per-tenant (Decision 1) — Academio's own strongest existing pattern. If a future reason forces a shared table, then and only then add RLS + `hnsw.iterative_scan = strict_order` (pgvector ≥0.8.0) + partial indexes + canary probe suite.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM providers (Gemini, OpenAI) | Go direct (existing) | Unchanged |
| LLM providers (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama) | Python via LiteLLM Router SDK | Config from env; keys encrypted at rest; TPM/RPM cooldowns via Redis (only cross-instance state Python may hold) |
| pgvector (PostgreSQL 18) | Go: schema-scoped GORM via `SchemaTablePrefix`; Python: psycopg3/asyncpg with validated schema-qualified SQL | `CREATE EXTENSION IF NOT EXISTS vector` in shared migration covers the database; tenant migration creates table + HNSW index per schema |
| Redis | Go: asynq queue, rate limits, cache (keys tenant-scoped) | Python: optional shared use only for LiteLLM cooldowns in multi-replica deployments |
| Uploads volume | `api` and `ai-engine` containers mount the same volume; files passed by path | No multipart re-transfer; keep paths school-scoped |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Go Orchestrator ↔ EngineClient | In-process interface call | gRPC-ready seam; callers never see transport |
| EngineClient ↔ Python `ai-engine` | REST/JSON + SSE, `X-AI-Engine-Token`, `X-Request-ID` | Timeouts: Go→Python > Python→LLM; SSE event envelope shared |
| Go asynq worker ↔ Python `/v1/documents` | REST/JSON (single call) | Worker resolves tenant DB by schoolID; retry only on transient errors |
| Go ModelRouter ↔ Python | Via EngineClient as one `providerEntry` | Two-level routing; Python reports usage, Go records cost |
| Python ↔ `school_{id}.ai_vectors` | Direct DB (trusted schema name) | The only state Python touches; schema validated, queries parameterized |
| Go RAG (existing agents) ↔ `school_{id}.ai_vectors` | Via pgvector Store impl (tenant from ctx) | Interface-identical to Qdrant; zero caller changes |
| Python ↔ frontend | **None** | Clients never talk to Python — enforced by internal-only network exposure |

---

## Sources

**pgvector multi-tenancy (HIGH confidence — multiple 2026 production sources converge):**
- Kawshik A. Ornob, "Secure Multi-Tenant RAG with pgvector and PostgreSQL RLS" (2026-07) — RLS + `FORCE ROW LEVEL SECURITY`, `set_config`/`SET LOCAL`, HNSW post-filter behavior, canary test suites
- Particula Tech, "Multi-Tenant RAG: Silo, Pool, or Bridge in Production" (2026-07) — AWS SaaS Lens taxonomy; iterative scans (`strict_order`) for recall; cache as tenant boundary; resolve tenancy once at the edge
- Folarin Akinloye, "Building a Multi-Tenant RAG System" (2026-06) — namespaces vs metadata filters; cache/log/prompt leakage points
- Studeia, "RAG per-tenant at scale: architecture for B2B LMS" (2026-05) — production 500K+ chunks, mandatory tenant filter, `tenantOnlyMode`, IVFFlat tuning, incremental re-ingestion, zero leakage in 6 months
- Pradeep Bhandari, "pgvector multi-tenancy: Hard Multi-Tenancy for pgvector" (2026-07) — partial indexes vs global HNSW, ghost-context problem
- Jacar, "RAG with Postgres and pgvector in production" (2026-06) — documents vs chunks tables, HNSW ~10M-vector ceiling
- pgxn.org / pg_trickle (2026) — per-tenant partial indexes, planner visibility of tenant predicates

**SSE relay (HIGH confidence — production-grade sources):**
- Preto.ai, "Streaming SSE Proxying for LLM APIs: The Hard Parts" (2026-04) — the four failure modes + ~50-line Go fixes; 5,000 req/s at <50ms p95
- server-sent-events.com, "Go Streaming Patterns for SSE" (2026-05) — hub/fan-out, Flush, `X-Accel-Buffering`, heartbeats, graceful shutdown
- jrajath94/token-streaming-proxy (2026) — Python httpx streaming relay, backpressure via TCP flow control, heartbeats
- golang-sse-forward, cc-relay, stream-relay-go — Go SSE forwarding reference implementations

**Go edge / Python compute split (MEDIUM-HIGH confidence — multiple 2026 sources, blog/dev-grade but converging):**
- Sentinel (Anhsirkm/sentinel, 2026) — Go edge gateway + Redis queue + Python AI workers; "fast layer vs smart layer" separation
- carmel/gomlx (2026) — Go OpenAI-compatible gateway driving Python inference via gRPC, native SSE
- CallSphere, "API Gateway Pattern for AI Agent Microservices" (2026-03) — gateway routing, SSE passthrough, tiered rate limiting
- Markaicode, "FastAPI System Design for AI Production" (2026-05) — when to use async+queue vs monolith; Redis streams vs pub/sub
- The Architect's Notebook Ep. 85, "The LLM as a Microservice" (2026-02) — orchestrator pattern, streaming properties, timeout layering

**Multi-provider routing (HIGH confidence — official docs):**
- BerriAI/litellm ARCHITECTURE.md + docs.litellm.ai (routing, spend tracking, provider budget routing) — Router SDK vs Proxy Server distinction; exactly the five target providers supported
- go-micro.dev Agent Integration Patterns (2026-07) — agent-as-consumer, scoped tokens, event-driven triggers

**In-repo ground truth (verified):**
- `backend/internal/ai/` — `Provider` interface + `StreamCallback`, `ModelRouter` with `providerEntry`/`addProvider`, `vector.Store` interface (Qdrant impl, no tenant namespacing — isolation gap), RAG pipeline (`IngestAndStore` stores `_doc_id`/`_chunk_index`/`_text` metadata), conversation store (shared schema)
- `backend/internal/middleware/` — `GetTenantDB(c)`, `GetSchemaName(c)`, `GetSchoolIDFromCtx(ctx)`, audit `tenantDBResolver` pattern (background-worker tenant resolution precedent)
- `backend/internal/queue/tasks.go` — `TypeAIScoring = "ai:scoring"`, `NewAIScoringTask`, `RegisterTaskHandlers` (pattern for `ai:doc-ingest`)
- `docs/plans/AI-platform-for-Academio.md` (spec), `docs/plans/AI-PLATFORM-IMPLEMENTATION-PLAN.md` (locked decisions), `.planning/PROJECT.md` (validated requirements)
- `backend/docker-compose.yml` — `postgres:alpine` (pgvector absent), qdrant (no live collections → migration risk LOW), shared uploads volume candidate

**Gaps / LOW confidence items:**
- No authoritative source for the exact "Go orchestrator ↔ Python FastAPI with gRPC seam" pattern at enterprise scale (emergent; the gomlx Go-gateway↔gRPC-Python-worker precedent is the closest) — treat the seam design as opinionated recommendation, validate during Phase 0/2 implementation
- Exact SSE event envelope (delta/citation/usage/done/error) is a design proposal, not an ecosystem standard — lock it in Phase 2 before the frontend integrates
- `ai_vectors` in tenant schema vs shared table is a real fork from the implementation plan's apparent intent (partial indexes) — flagged as a Phase 1 decision to lock early, with strong rationale above

---
*Architecture research for: Academio AI Platform (Python ai-engine + pgvector RAG)*
*Researched: 2026-07-31*
