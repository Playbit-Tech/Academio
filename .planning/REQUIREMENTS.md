# Requirements: AI Platform for Academio

**Defined:** 2026-07-31
**Core Value:** Document intelligence that works: users upload documents and get extract → chunk → embed → searchable knowledge, surfaced through the AI assistant with tenant isolation intact — without breaking the existing Go AI layer.

## v1 Requirements

### Foundation

- [x] **FND-01**: `ai-engine/` FastAPI submodule created (Python 3.13, `pyproject.toml`, dependency bootstrap via uv)
- [x] **FND-02**: docker-compose `ai-engine` service added (internal port only, health-checked, shared uploads volume)
- [x] **FND-03**: Go `EngineClient` seam (`backend/internal/ai/engine/client.go`) with HTTP/JSON + SSE, gRPC-ready interface
- [x] **FND-04**: `AI_ENGINE_URL` + `AI_ENGINE_TOKEN` config (service-to-service auth, never user JWT)
- [x] **FND-05**: CI workflow for `ai-engine` (lint, test, build)

### pgvector Migration

- [x] **PGV-01**: Postgres image swapped to `pgvector/pgvector:pg18` (pin ≥0.8.2, CVE-2026-3172)
- [x] **PGV-02**: `CREATE EXTENSION IF NOT EXISTS vector` in shared + tenant migrations
- [x] **PGV-03**: `internal/ai/vector/pgvector.go` implementing existing `vector.Store` interface (zero RAG/agent changes)
- [x] **PGV-04**: `ai_vectors` table in `school_{id}` TENANT schemas + metadata columns + HNSW index (schema-per-tenant; NOT shared+partial-indexes)
- [x] **PGV-04a**: Canonical embedding model + dimension locked BEFORE DDL (Go+Python share; 1536-dim default; Nigerian-language multilingual eval first)
- [x] **PGV-05**: Qdrant → pgvector data migration tool (low risk: no live collections)
- [x] **PGV-06**: Config swapped `AI_QDRANT_*` → pgvector DSN, Qdrant container retired after cutover

### Python AI Engine

- [x] **PYE-01**: Python multi-provider abstraction (Anthropic, DeepSeek, OpenRouter, Azure OpenAI, Ollama) via direct SDKs; NO Python gateway, NO LiteLLM
- [x] **PYE-02**: Document intelligence: PDF, DOCX, PPTX, TXT, CSV, image OCR (Tesseract), chunking, embeddings, semantic search, re-ranking, knowledge indexing
- [x] **PYE-03**: Versioned prompt library (report comments, lesson plans, questions, rubrics, behaviour summary, attendance analysis, parent letters, meeting minutes, translation)
- [x] **PYE-04**: Python endpoints: `/health`, `/v1/chat`, `/v1/chat/stream` (SSE), `/v1/embed`, `/v1/extract`, `/v1/documents`, `/v1/search`, `/v1/providers`
- [x] **PYE-04a**: `proto/aiengine.proto` gRPC contract written in Phase 2 (transports over REST in v1)
- [x] **PYE-05**: Tenant-aware RAG in Python (hybrid search, metadata filtering, chunk ranking, citations, context compression)

### Document Pipeline

- [x] **PIP-01**: Document pipeline: upload → Go validates → save → asynq enqueue (`ai:doc-ingest`) → Go worker → single Python `/v1/documents` call → extract/chunk/embed → pgvector → event → notify
- [x] **PIP-02**: `POST /api/v2/ai/documents` + `GET /api/v2/ai/documents/:id/status` endpoints

### Go Integration & API Surface

- [x] **INT-01**: `POST /api/v2/ai/chat/stream` SSE route with failure-mode-safe relay (SSE-aware scanner, context propagation, bounded channel, in-band errors, `X-Accel-Buffering: no`, heartbeats, shared event envelope)
- [x] **INT-02**: `GET /api/v2/ai/providers` multi-provider status endpoint
- [ ] **INT-03**: AI Orchestrator: rate limiting, quota enforcement, AI-usage audit events, Redis prompt/response caching, retries/circuit breakers on Python calls, strict timeout layering (Go→Python > Python→LLM)
- [ ] **INT-04**: Python providers wired into Go `ModelRouter` as additional `providerEntry`s (two-level routing)

### Observability, Security, Testing

- [ ] **OBS-01**: Prometheus metrics + JSON logs + `X-Request-ID` correlation across Go→Python; token usage/cost/latency/cache metrics; Grafana dashboard
- [ ] **SEC-01**: PII masking, AI config encryption, audit every AI request, rate limit AI endpoints, tenant isolation, input validation; Python validates `schema_name` `^school_\d+$` on every query; shared uploads volume
- [ ] **TES-01**: Go + pytest test suites (unit, integration, AI-pipeline, embedding, RAG-accuracy, security, load, concurrency); RAG evaluation harness ships WITH pipeline; cross-tenant probe suite in CI

### Migration & Retirement

- [ ] **RET-01**: Feature-flagged Python capabilities, parallel Go AI + Python run, incremental migration
- [ ] **RET-02**: `academio-qdrant` container retired once pgvector cutover verified
- [ ] **RET-03**: `docs/architecture/5-AI-ARCHITECTURE.md` + FSD updated to reflect the Python engine

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Capabilities

- **QUO-01**: Hierarchical budgets — platform → school → role quota hierarchies (per-school flat quotas ship in v1)
- **EMB-01**: Embedding model upgrade path — corpus re-embed tooling when canonical model changes post-DDL
- **MULTI-01**: Multilingual embedding expansion beyond canonical model (Nigerian language family coverage)
- **SEARCH-01**: Searchable-PDF artifact output (OCRmyPDF) for document downloads (OCR-for-extraction ships v1; artifact output deferred)
- **TUTOR-01**: Student-facing tutor — deferred (industry results weak)
- **RERANK-01**: Reranker selection benchmark — Cohere API vs self-hosted BGE-reranker-v2-m3 (data-residency driven)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Rewriting Go AI layer in Python | Additive Python only; Go agents/RAG/search/gateway stay |
| Python AI gateway / LiteLLM proxy | Go ModelRouter already owns platform-level failover |
| Celery in Python | asynq in Go is the only queue; Python is stateless compute |
| gRPC transport in v1 | REST/JSON + SSE now; `proto/aiengine.proto` written in P2, transport later |
| Student-facing tutor | Industry results weak (Khanmigo founder: "non-event") |
| AI-graded final scores | Academic-integrity risk; human-in-the-loop required |
| AI detection tooling | Low accuracy, adversarial arms race, no defensible value |
| Synchronous document processing | Always async via asynq pipeline |
| Handwriting OCR in v1 | Low accuracy; defer |
| Mobile AI features | Frontend scope is existing web AI assistant |
| Replacing Postgres/shared infra | `ai-engine` reuses shared pgvector, Redis, docker-compose |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| FND-04 | Phase 1 | Complete |
| FND-05 | Phase 1 | Complete |
| PGV-01 | Phase 2 | Complete |
| PGV-02 | Phase 2 | Complete |
| PGV-03 | Phase 2 | Complete |
| PGV-04 | Phase 2 | Complete |
| PGV-04a | Phase 2 | Complete |
| PGV-05 | Phase 2 | Complete |
| PGV-06 | Phase 2 | Complete |
| PYE-01 | Phase 3 | Complete |
| PYE-02 | Phase 3 | Complete |
| PYE-03 | Phase 3 | Complete |
| PYE-04 | Phase 3 | Complete |
| PYE-04a | Phase 3 | Complete |
| PYE-05 | Phase 3 | Complete |
| INT-01 | Phase 4 | Complete |
| PIP-01 | Phase 4 | Complete |
| PIP-02 | Phase 4 | Complete |
| INT-02 | Phase 5 | Complete |
| INT-03 | Phase 5 | Pending |
| INT-04 | Phase 5 | Pending |
| OBS-01 | Phase 6 | Pending |
| SEC-01 | Phase 6 | Pending |
| TES-01 | Phase 6 | Pending |
| RET-01 | Phase 7 | Pending |
| RET-02 | Phase 7 | Pending |
| RET-03 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 30 total (enumerated REQ-IDs; prior "31" header was an arithmetic artifact)
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-31*
*Last updated: 2026-07-31 after roadmap creation (traceability re-based to Phase 1-7)*
