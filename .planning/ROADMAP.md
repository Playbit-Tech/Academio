# Roadmap: AI Platform for Academio

## Overview

This milestone adds an **additive Python AI engine** to the existing Go education ERP: a stateless FastAPI service (`ai-engine/`) that brings OCR, document intelligence, and five new LLM providers, while the working Go AI layer (Gemini+OpenAI gateway, ModelRouter, 10 agents, RAG, NL search) stays untouched. Vector storage migrates from Qdrant to **schema-per-tenant pgvector** (structurally isolated, one canonical embedding model), and new Go API surface delivers SSE streaming chat plus an async document-intelligence pipeline — the Core Value: upload documents, get extract → chunk → embed → searchable knowledge, tenant-safe, without breaking anything existing. Seven sequential phases: Foundation seam → pgvector migration → Python engine → SSE + document pipeline → Go orchestration → observability/security/testing → migration & retirement. All 30 v1 requirements map to exactly one phase.

**Phase Numbering:**
- Integer phases (1-7): planned milestone work, executed sequentially
- Decimal phases: reserved for urgent insertions after approval (none expected)

## Phases

- [x] **Phase 1: Foundation** - `ai-engine/` submodule, docker-compose service, Go EngineClient seam, service-token config, CI (completed 2026-07-31)
- [x] **Phase 2: pgvector Migration** - image swap, tenant-schema `ai_vectors` + HNSW, canonical embedding lock, Store impl, Qdrant cutover (completed 2026-08-01)
- [x] **Phase 3: Python AI Engine** - FastAPI service, multi-provider SDKs, document intelligence, prompt library, gRPC proto, tenant RAG (completed 2026-08-01)
- [x] **Phase 4: SSE Streaming + Document Pipeline** - SSE relay route, async ingest pipeline, document endpoints (completed 2026-08-01)
- [x] **Phase 5: Go Integration & Orchestrator** — providers status, rate limit/quota/audit/cache, ModelRouter wiring (completed 2026-08-02)
- [ ] **Phase 6: Observability, Security & Testing** - metrics/correlation, PII masking, RAG eval harness, cross-tenant probes
- [x] **Phase 7: Migration & Retirement** - feature flags, parallel run, Qdrant retirement, docs update (completed 2026-08-21)

## Phase Details

### Phase 1: Foundation
**Goal**: The Go↔Python seam, service infrastructure, and CI exist so all AI traffic flows over an authenticated, timeout-disciplined, health-checked boundary.
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, FND-05
**Success Criteria** (what must be TRUE):
  1. A developer can bootstrap the `ai-engine/` submodule from scratch with `uv sync` (Python 3.13, pinned `pyproject.toml`), start the FastAPI service, and run a passing smoke test — no manual dependency steps.
  2. `docker compose up` starts an `ai-engine` container that (a) passes its health check, (b) is reachable only on the internal Docker network (no published host port), and (c) mounts the shared uploads volume that `api` also mounts.
  3. Go code can call a running Python service through the `EngineClient` seam for both JSON and SSE responses, with per-endpoint timeout budgets (extract: minutes, chat: seconds, stream: no overall cap) and `X-Request-ID` propagated on every call.
  4. The backend fails fast at startup when `AI_ENGINE_URL` or `AI_ENGINE_TOKEN` is missing or invalid (Rule B12); every internal call authenticates with the service token in a header — never in a URL, never a user JWT.
  5. CI for `ai-engine` (ruff lint, pyright type-check, pytest, Docker build) runs on every push and blocks on failure; the existing Go build, lint, and test suites stay green with the new seam and config in place.
**Plans**: 5 plans

Plans:
- [x] 01-01-PLAN.md — FND-01: ai-engine/ uv bootstrap, FastAPI skeleton, Dockerfile (wave 1)
- [x] 01-04-PLAN.md — FND-04: AI_ENGINE_URL/TOKEN config + unconditional fail-fast (wave 1)
- [x] 01-02-PLAN.md — FND-03: Go EngineClient seam (interface + SSE primitives + TDD client) (wave 2)
- [x] 01-03-PLAN.md — FND-02: docker-compose ai-engine service + api wiring (wave 2)
- [x] 01-05-PLAN.md — FND-05: root .github/workflows/ai-engine.yml CI (wave 2)

### Phase 2: pgvector Migration
**Goal**: Vector storage moves from Qdrant to per-tenant pgvector behind the existing `vector.Store` interface, with a locked embedding canon and a structurally isolated table — zero RAG/agent changes.
**Depends on**: Phase 1
**Requirements**: PGV-01, PGV-02, PGV-03, PGV-04, PGV-04a, PGV-05, PGV-06
**Success Criteria** (what must be TRUE):
  1. Postgres runs the pinned `pgvector/pgvector:pg18` image (≥0.8.2 — CVE-2026-3172 fixed); `CREATE EXTENSION IF NOT EXISTS vector` succeeds in both shared and tenant migrations, and `pg_available_extensions` lists `vector`.
  2. A canonical embedding model + dimension is locked in config (`AI_EMBEDDING_DIM`) and verified for Nigerian-language multilingual quality **BEFORE any `ai_vectors` DDL** (PGV-04a is a hard Phase-2 blocker); the dimension is ≤2000 so HNSW on `vector` works (default 1536-dim).
  3. `ai_vectors` exists in each `school_{id}` TENANT schema (not `public`) with metadata columns including `embedding_model`, `model_version`, `chunking_version`, a unique constraint on `(document_id, chunk_index)`, and a per-schema HNSW index (`vector_cosine_ops` + `<=>`) built with raised `maintenance_work_mem` — structurally tenant-scoped, no partial-index machinery.
  4. The existing Go RAG pipeline and all 10 agents work unchanged against pgvector: the pgvector `Store` resolves tenancy from context, passes the same interface-conformance tests as the Qdrant implementation (insert/search/delete/filter parity), and `EXPLAIN` shows HNSW `Index Scan` (no silent seq-scan).
  5. Qdrant → pgvector data copy completes with count/dimension/distance-semantics parity asserts (`similarity = 1 - distance` for cosine); config swaps `AI_QDRANT_*` → pgvector DSN behind the interface; startup validates the embedder's output dimension against the column type and fails fast on mismatch.
**Plans**: 6 plans
Plans:
- [x] 02-01-PLAN.md — PGV-04a: canonical embedding lock (text-embedding-3-small / 1536) + Nigerian-language eval spike + AI_EMBEDDING_DIM fail-fast (wave 1)
- [x] 02-02-PLAN.md — PGV-01/02: pgvector image swap + versioned core `CREATE EXTENSION IF NOT EXISTS vector` (wave 1)
- [x] 02-03-PLAN.md — PGV-04: tenant `school_{id}.ai_vectors` DDL + HNSW index + unique(doc, chunk) (wave 2)
- [x] 02-04-PLAN.md — PGV-03: PGVectorStore behind `vector.Store` (tenancy from ctx, 1 - distance, metadata contract) + tests (wave 3)
- [x] 02-05-PLAN.md — PGV-05: Qdrant → pgvector copy tool with parity asserts (wave 3)
- [x] 02-06-PLAN.md — PGV-06: AI_QDRANT_* → AI_PGVECTOR_DSN swap, PGVectorStore wiring + dim probe, Qdrant retirement from compose/k8s (wave 4)

### Phase 3: Python AI Engine
**Goal**: A stateless Python compute service provides multi-provider LLM access, document intelligence, embeddings, and tenant-aware RAG behind a gRPC-ready contract — the engine the pipeline and streaming layers call into.
**Depends on**: Phase 2 (embedding canon PGV-04a; `school_{id}.ai_vectors` for ingest writes)
**Requirements**: PYE-01, PYE-02, PYE-03, PYE-04, PYE-04a, PYE-05
**Success Criteria** (what must be TRUE):
  1. `proto/aiengine.proto` is committed as the gRPC contract (Chat, ChatStream, Embed, Extract, IngestDocument, Search) at the START of the phase, and every REST endpoint satisfies its request/response semantics 1:1 (transport stays REST/JSON + SSE in v1).
  2. `/v1/chat` and `/v1/chat/stream` (native SSE: `text/event-stream`, heartbeats ≤30s, no gzip) serve conversations through all five new providers — Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama — via direct SDKs (`anthropic` + `openai` with `base_url`), returning a normalized usage payload (provider, model, input/output tokens, cost) on every response; NO LiteLLM, NO Python gateway.
  3. `/v1/providers` returns live per-provider status (health, cooldowns) for Go's INT-02; `/v1/embed` produces canonical-model embeddings matching `ai_vectors`' locked dimension.
  4. `/v1/extract` and `/v1/documents` parse PDF/DOCX/PPTX/TXT/CSV/images with per-page routing (digital → fast text parser, scanned → Tesseract OCR at ≥300 DPI) and quality gates; `/v1/documents` performs extract → chunk → embed → store in ONE call, writing to the validated `school_{id}` schema; every DB access validates `schema_name` against `^school_\d+$` with no global fallback.
  5. `/v1/search` returns hybrid retrieval (dense + BM25/RRF) with metadata filters, chunk ranking, citations, and context compression, scoped to the request's schema; the versioned prompt library (Git-backed YAML, dev/staging/prod aliases) serves every PYE-03 template; the service stays stateless (no Celery, no user auth, no queue — service token only).
**Plans**: TBD

### Phase 4: SSE Streaming + Document Pipeline
**Goal**: Users can stream AI chat responses token-by-token and upload documents that become searchable, cited knowledge — the Core Value — through a safe, idempotent, failure-transparent pipeline.
**Depends on**: Phase 3 (Python `/v1/chat/stream` + `/v1/documents`; transitively Phase 1 seam, Phase 2 vectors)
**Requirements**: INT-01, PIP-01, PIP-02
**Success Criteria** (what must be TRUE):
  1. `POST /api/v2/ai/chat/stream` streams the shared event envelope (delta/citation/usage/error/done) to the browser with `X-Accel-Buffering: no`, heartbeats ≤30s, and no compression on `text/event-stream`; a client disconnect cancels the upstream Python call so generation stops and no tokens are billed for unread output.
  2. The SSE relay survives all four failure modes: event-boundary-safe parsing (SSE-aware scanner with buffer beyond the 64 KB default), `r.Context()` propagation into the upstream call, bounded channel (cap 64) with slow-client abort, and in-band `error` events after HTTP 200 that every client checks.
  3. `POST /api/v2/ai/documents` accepts PDF/DOCX/PPTX/TXT/CSV/images, validates type/size/permissions, saves to the shared uploads volume, enqueues asynq `ai:doc-ingest`, and returns 202; `GET /api/v2/ai/documents/:id/status` reports the state machine (queued → extracting → chunking → embedding → ready/failed) plus quality metrics (pages, OCR'd pages, char count, confidence).
  4. The Go worker calls Python's `/v1/documents` exactly ONCE per file (single call: extract+chunk+embed+store); ingest is idempotent — unique constraint + `INSERT ... ON CONFLICT DO NOTHING`, transient-vs-permanent retry classification (`asynq.SkipRetry` for permanent), DLQ/archive monitored as an SLO.
  5. When a document reaches `ready`, searching that school's corpus returns its chunks with citations (source doc + page); on failure the user sees a clear reason and can retry — no silent drops, no duplicate vectors after worker restarts.
**Plans**: TBD

### Phase 5: Go Integration & Orchestrator
**Goal**: Python capabilities are governed and routed from Go: provider status, platform-level ModelRouter failover, and the AI Orchestrator (rate limiting, quotas, audit, caching, retries) — with security controls shipping with the first endpoints, not as a phase-6 bolt-on.
**Depends on**: Phase 4 (endpoints to govern; transitively Phase 3 `/v1/providers`)
**Requirements**: INT-02, INT-03, INT-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/v2/ai/providers` returns combined status for Gemini + OpenAI (Go local circuit-breaker state) and the five Python providers (via `/v1/providers`), in one response with cooldown info.
  2. Python is wired into the existing `ModelRouter` as one `providerEntry`, giving platform-level failover across gemini ↔ openai ↔ python (two-level routing: Go platform-level, Python internal); strict timeout layering (Go→Python > Python→LLM) keeps the levels from fighting; Python reports usage, Go records cost — one cost ledger.
  3. Rate limiting, per-school quota enforcement, and AI-usage audit events (SchoolID, UserID, Action, ResourceType, RequestID) are enforced on EVERY AI endpoint — existing and new — from the first orchestrator delivery (INT-03's controls are the FIRST plan of this phase, not a hardening bolt-on); a noisy school cannot starve others; violations return clear 429s.
  4. Redis prompt/response caching is tenant-scoped (`school_id` in every key); retries + circuit breakers protect Python calls with error classification (429 → failover, never retry same provider; 5xx/timeout → retry once then failover; other 4xx → permanent, no failover); per-request cost caps and per-tenant daily spend caps trip before spend.
**Plans**: TBD

### Phase 6: Observability, Security & Testing
**Goal**: The platform is provably observable, PII-safe, and tenant-isolated — the RAG eval harness and cross-tenant probe suite in CI prove what earlier phases built.
**Depends on**: Phase 5 (all endpoints + orchestrator in place to observe/test)
**Requirements**: OBS-01, SEC-01, TES-01
**Success Criteria** (what must be TRUE):
  1. Prometheus metrics (tokens, cost, latency, cache hits, provider/model per request) and JSON logs carry `X-Request-ID` end-to-end across Go → Python; a Grafana visualization shows pipeline health, fallback rate, and cost-per-successful-task.
  2. PII masking is enforced (document contents and prompt bodies never appear in logs — sizes/hashes only); AI config secrets are encrypted at rest; every AI request is audited; all inputs validated; Python's `^school_\d+$` schema check runs on every query with no fallback.
  3. The RAG evaluation harness ships and runs in CI on every chunking/embedding/prompt change: golden set of 50-100 school-realistic QA pairs (collected from Phase 4's pipeline corpus), gating faithfulness ≥0.85 and context precision ≥0.75.
  4. The cross-tenant probe suite runs in CI on every deploy: canary chunks per tenant, adversarial queries across every retrieval entry point (search, cache, reranking, agent tools, worker paths) assert ZERO cross-tenant hits; the kill-worker-mid-pipeline test asserts zero duplicate vectors and exactly one notification; load/concurrency tests pass at 10× expected peak.
**Plans**: 06-01 (OBS-01, complete), 06-02 (SEC-01, complete), 06-03 (TES-01 RAG eval), 06-04 (TES-01 probes + hardening)

### Phase 7: Migration & Retirement
**Goal**: Python capabilities go live safely behind feature flags with Go AI + Python running in parallel, Qdrant fully retired, and architecture docs reflecting the new engine.
**Depends on**: Phase 6 (pgvector cutover verified, probes green)
**Requirements**: RET-01, RET-02, RET-03
**Success Criteria** (what must be TRUE):
  1. Python capabilities are feature-flagged (global and per-school); operators enable/disable without redeploy; Go AI and Python run in parallel with doc ingestion migrated incrementally.
  2. `academio-qdrant` is removed from docker-compose and Qdrant code paths are retired ONLY after pgvector cutover is verified (interface-conformance + parity checks green in CI); disabling the flags restores pre-migration behavior for all AI endpoints (demonstrated rollback path).
  3. `docs/architecture/5-AI-ARCHITECTURE.md` and the FSD are updated to reflect the Python engine, two-level routing, schema-per-tenant pgvector, and the async document pipeline.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute sequentially: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 5/5 | Complete   | 2026-07-31 |
| 2. pgvector Migration | 6/6 | Complete   | 2026-08-01 |
| 3. Python AI Engine | 7/7 | Complete   | 2026-08-01 |
| 4. SSE Streaming + Document Pipeline | 5/5 | Complete   | 2026-08-01 |
| 5. Go Integration & Orchestrator | 3/3 | Complete   | 2026-08-02 |
| 6. Observability, Security & Testing | 1/4 | In Progress | - |
| 7. Migration & Retirement | N/A | Complete   | 2026-08-21 |
