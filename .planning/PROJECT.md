# AI Platform for Academio

## What This Is

The AI Platform is Academio's AI capability layer, extending the existing Go-native AI stack (Gemini + OpenAI gateway, 10 agents, RAG, NL search) with a Python AI Engine that adds OCR, document intelligence, and multi-provider breadth. It is additive to the current system: the working Go agents/RAG/search/gateway stay; Python handles document extraction and expanded provider coverage. Vector storage migrates from Qdrant to pgvector. The effort spans a new `ai-engine/` root submodule (FastAPI service), the existing `backend/` Go monolith (migrations, endpoints, orchestrator), and docker-compose infrastructure.

## Core Value

Document intelligence that works: users upload documents (PDFs, policies, handbooks, lesson notes, exam papers, images) and get extract → chunk → embed → searchable knowledge, surfaced through the AI assistant with tenant isolation intact — without breaking the existing Go AI layer.

## Requirements

### Validated

- ✓ Go AI gateway with Gemini + OpenAI providers, ModelRouter with failover + circuit breakers — existing (`backend/internal/ai/`)
- ✓ 10 agents (academic_tutor, teacher_assistant, parent_assistant, risk_analyzer, enrollment_forecaster, revenue_forecaster, career_guidance, proctoring_analyzer, alumni_insights, executive_summarizer) — existing
- ✓ RAG pipeline (chunker → embedder → `vector.Store`) — existing
- ✓ NL search engine (intent parser → query builder → formatter, tenant-isolated) — existing
- ✓ Conversation store (Postgres shared schema, school-scoped) — existing
- ✓ Agent API: `POST /api/v2/ai/chat`, `POST /api/v2/ai/search`, `GET /api/v2/ai/agents` — existing
- ✓ Frontend AI assistant (`ai-assistant.tsx`, `agent-selector.tsx`, `chat-interface.tsx`) — existing
- ✓ Qdrant-backed vector store with `curriculum`/`policies` collections — existing (to be retired)
- ✓ `ai-engine/` FastAPI service skeleton (Python 3.13, `uv sync` bootstrap, committed `uv.lock`) — FND-01, Validated in Phase 1
- ✓ docker-compose `ai-engine` service (internal-only, no host port, urllib healthcheck, shared `uploads_data`) — FND-02, Validated in Phase 1
- ✓ Go `EngineClient` seam (`backend/internal/ai/engine/`) with HTTP/JSON + SSE, per-endpoint timeouts, gRPC-ready interface — FND-03, Validated in Phase 1
- ✓ `AI_ENGINE_URL` + `AI_ENGINE_TOKEN` config with unconditional fail-fast validation (Rule B12) — FND-04, Validated in Phase 1
- ✓ Root CI workflow `.github/workflows/ai-engine.yml` (ruff, pyright, pytest, docker-build) — FND-05, Validated in Phase 1

### Active

- [ ] **PGV-01**: Postgres image swapped to `pgvector/pgvector:pg18` (pin ≥0.8.2, CVE-2026-3172)
- [ ] **PGV-02**: `CREATE EXTENSION IF NOT EXISTS vector` in shared + tenant migrations
- [ ] **PGV-03**: `internal/ai/vector/pgvector.go` implementing existing `vector.Store` interface (zero RAG/agent changes)
- [ ] **PGV-04**: **`ai_vectors` table in `school_{id}` TENANT schemas** (schema-per-tenant, matching existing architecture) + metadata columns + HNSW index; NOT shared+partial-indexes (research finding — prevents cross-tenant leaks + post-filter recall collapse)
- [ ] **PGV-04a**: **Canonical embedding model + dimension locked BEFORE DDL** (research blocker — Go+Python share `ai_vectors`; recommend 1536-dim, verify Nigerian-language multilingual quality first)
- [ ] **PGV-05**: Qdrant → pgvector data migration tool (low risk: no live collections)
- [ ] **PGV-06**: Config swapped `AI_QDRANT_*` → pgvector DSN, Qdrant container retired after cutover
- [ ] **PYE-01**: Python multi-provider abstraction (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama — additive to Go's Gemini/OpenAI) via direct SDKs (`anthropic` + `openai` base_url); NO Python gateway, NO LiteLLM
- [ ] **PYE-02**: Document intelligence: PDF, DOCX, PPTX, TXT, CSV, image OCR (Tesseract), chunking, embeddings, semantic search, re-ranking, knowledge indexing (Docling 2.x; light-path PyMuPDF variant if torch image too large)
- [ ] **PYE-03**: Versioned prompt library (report comments, lesson plans, questions, rubrics, behaviour summary, attendance analysis, parent letters, meeting minutes, translation)
- [ ] **PYE-04**: Python endpoints: `/health`, `/v1/chat`, `/v1/chat/stream` (SSE), `/v1/embed`, `/v1/extract`, `/v1/documents`, `/v1/search`, **`/v1/providers`** (added per research — needed by INT-02)
- [ ] **PYE-04a**: `proto/aiengine.proto` gRPC contract written in Phase 2 (v1 transports over REST; contract cheap now, expensive to retrofit)
- [ ] **PYE-05**: Tenant-aware RAG in Python (hybrid search, metadata filtering, chunk ranking, citations, context compression)
- [ ] **PIP-01**: Document pipeline: upload → Go validates → save → asynq enqueue (`ai:doc-ingest`) → Go worker → **single** Python `/v1/documents` call → extract/chunk/embed → pgvector → event → notify
- [ ] **PIP-02**: `POST /api/v2/ai/documents` + `GET /api/v2/ai/documents/:id/status` endpoints
- [ ] **INT-01**: `POST /api/v2/ai/chat/stream` SSE route (streaming currently only at provider layer); SSE-aware scanner, `r.Context()` propagation, bounded channel, in-band error events, `X-Accel-Buffering: no`, heartbeats, shared event envelope (delta/citation/usage/done/error)
- [ ] **INT-02**: `GET /api/v2/ai/providers` multi-provider status endpoint
- [ ] **INT-03**: AI Orchestrator: rate limiting, quota enforcement (OWASP LLM top-10 guardrail — ships with first endpoints), AI-usage audit events, Redis prompt/response caching, retries/circuit breakers on Python calls; strict timeout layering (Go→Python > Python→LLM)
- [ ] **INT-04**: Python providers wired into Go `ModelRouter` as additional `providerEntry`s (two-level routing: Go platform-level failover, Python reports usage only)
- [ ] **OBS-01**: Prometheus metrics + JSON logs + `X-Request-ID` correlation across Go→Python; token usage/cost/latency/cache metrics; Grafana dashboard
- [ ] **SEC-01**: PII masking, AI config encryption, audit every AI request, rate limit AI endpoints, tenant isolation, input validation; Python validates `schema_name` `^school_\d+$` on every query, no global fallback; shared uploads volume (no multipart re-transfer)
- [ ] **TES-01**: Go + pytest test suites (unit, integration, AI-pipeline, embedding, RAG-accuracy, security, load, concurrency) — **RAG evaluation harness ships WITH pipeline**; **cross-tenant probe suite in CI** (canary chunks per tenant, mandatory)
- [ ] **RET-01**: Feature-flagged Python capabilities, parallel Go AI + Python run, incremental migration
- [ ] **RET-02**: `academio-qdrant` container retired once pgvector cutover verified
- [ ] **RET-03**: `docs/architecture/5-AI-ARCHITECTURE.md` + FSD updated to reflect the Python engine

### Out of Scope

- Rewriting the existing Go AI layer in Python — Additive Python only; Go agents/RAG/search/gateway stay
- Replacing Gemini/OpenAI providers — Python adds providers; existing two remain
- gRPC transport in v1 — REST/JSON + SSE now, gRPC-ready interface seam only (proto written in Phase 2, transports over REST)
- Python-side AI gateway/LiteLLM — Go ModelRouter owns platform failover; Python uses direct SDKs
- Python queue (Celery) — asynq in Go is the only queue; Python is stateless compute
- Student-facing tutor — deferred (industry results weak; Khanmigo non-event)
- AI-graded final scores, AI detection tooling — academic-integrity risk
- Synchronous document processing — always async via asynq pipeline
- Handwriting OCR in v1 — low accuracy, defer
- Mobile AI features — frontend scope is the existing web AI assistant
- Replacing Postgres/shared infrastructure — `ai-engine` reuses shared pgvector, Redis, docker-compose

## Context

- **Phase 1 (Foundation) complete**: `ai-engine/` FastAPI skeleton (Python 3.13, `uv sync`, `/health` + token-protected `/v1/health`, multi-stage Dockerfile); Go `EngineClient` seam at `backend/internal/ai/engine/` (interface + SSE-aware scanner + httptest client, per-endpoint timeouts, X-Request-ID); `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` unconditional fail-fast config; compose `ai-engine` service (internal-only, urllib healthcheck, shared uploads volume); root CI `ai-engine.yml`.
- **Phase 2 (pgvector migration) complete — verified 5/5**: canonical embedding locked (`text-embedding-3-small`, `AI_EMBEDDING_DIM=1536`, fail-fast ≤2000, Nigerian-language spike); postgres pinned `pgvector/pgvector:0.8.6-pg18-trixie` (CVE-2026-3172) with versioned core `vector` extension migration; per-tenant `school_{id}.ai_vectors` DDL + HNSW (`vector_cosine_ops`, m=16/ef_construction=64, raised maintenance_work_mem) + `UNIQUE(document_id, chunk_index)`; `PGVectorStore` behind `vector.Store` (tenancy from ctx, `score = 1 - distance`, upsert parity) with zero RAG/agent changes; `cmd/copy-qdrant-vectors/` with parity asserts; `AI_QDRANT_*` → `AI_PGVECTOR_DSN` swap + D-14 startup dimension probe; Qdrant retired from compose/k8s (qdrant.go retained as behavioral ref → Phase 7 RET-02). Code review APPROVED (all MEDIUM/LOW findings fixed). Next: Phase 3 (Python AI Engine).
- **Current AI state (verified)**: `backend/internal/ai/` = 37 files; gateway.go, model_router.go, circuit_breaker.go, cost.go, metrics.go, tracing.go, gemini.go, openai.go; agents/ (10), rag/, vector/ (Qdrant), search/, conversation/. Agent API at `backend/internal/modules/ai/`. Existing asynq task `ai:scoring` (`newAIScoringHandler`) is the pattern to reuse for doc-ingest.
- **Infrastructure (verified)**: docker-compose = postgres (`postgres:alpine`, PostgreSQL 18.4, **pgvector verified ABSENT**), redis, qdrant (not running; **no live collections** → migration risk LOW), gotenberg, api, ai-engine, prometheus, grafana.
- **Tooling**: No Python in repo. `python3` 3.13.1 via pyenv; `uv`/`poetry` NOT installed (bootstrap with pyenv venv + pip or install uv).
- **Repo structure**: flat monorepo with git submodules — backend (`Playbits/Academio-be`), frontend (`Playbits/Academio-fe`), mobile (`academio-mobile`). **Visibility split: only the root repo is public on GitHub; all sub-repos (backend, frontend, mobile) are PRIVATE.** Internal docs + `.planning/` in the root are gitignored; code lives in the private submodules.
- **Rename coordination**: `github.com/playbits/schoolcare-v2` module rename is pending (`docs/plans/CODE-RENAME-PLAN.md`). New Go code should target the final path `github.com/playbits/academio` to avoid double-work.
- **Standards**: `AGENTS.md` rules B1–B13 (backend: no silent error discard, context propagation, logger not fmt.Printf, no multi-statement db.Exec, bounded queries, no hardcoded secrets, parameterized SQL, tenant DB via middleware, service-layer pagination, audit logs, startup config validation) and F1–F5 (frontend: entity names in Selects, Yarn 4+, Vite/TanStack Router, Sonner Toaster in root, NGN currency).

## Constraints

- **Tech stack**: Go (existing backend), FastAPI/Python 3.13 (new `ai-engine`), pgvector/PostgreSQL (replaces Qdrant), Redis + asynq (queue), docker-compose
- **Transport**: REST/JSON + SSE; gRPC-ready seam, not gRPC in v1
- **Compatibility**: Must not break existing Go AI endpoints (`/api/v2/ai/{chat,agents,search}`) — new endpoints are additive
- **Additive constraint**: Do not rewrite the Go AI layer; Python adds capabilities
- **Tenant isolation**: All tenant queries via `middleware.GetTenantDB(c)`; Python re-enforces via metadata filters; service auth via `AI_ENGINE_TOKEN`, never user JWT
- **Repo security**: Only the root repo is public. Sub-repos are private — code (including new `ai-engine` submodule) lives in private repos; never put secrets or internal docs in the root. `ai-engine` follows the same private-submodule pattern.
- **Module path**: Target `github.com/playbits/academio` in new Go code (rename pending)
- **pgvector migration**: Postgres image swap required (`pgvector/pgvector:pg18`); must verify extension in shared + tenant schemas

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Additive Python (keep Go AI) | Go layer works; Python adds OCR/doc intelligence/multi-provider; lowest risk | ✓ Locked |
| Migrate to pgvector | Spec requires it; `postgres:alpine` verified lacking the extension | ✓ Done (Phase 2) |
| New `ai-engine/` submodule | Matches backend/frontend/mobile submodule pattern; independently versionable | ✓ Locked |
| REST/JSON + SSE with gRPC seam | FastAPI-native, debuggable, drop-in gRPC swap later | ✓ Locked |
| Asynq → Go worker → Python HTTP | Spec-exact flow; reuses existing `ai:scoring` pattern | ✓ Locked |
| Coarse granularity, sequential execution | User preference for this effort | ✓ Locked |
| `.planning/` local-only (gitignored) | Root repo is public; matches internal-docs posture | ✓ Locked |

---
*Last updated: 2026-08-01 after Phase 2 (pgvector migration) completion*
