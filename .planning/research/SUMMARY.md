# Project Research Summary

**Project:** AI Platform for Academio (Python ai-engine + pgvector RAG)
**Domain:** Multi-tenant school ERP AI layer — document intelligence, multi-provider LLM routing, education AI, SSE streaming, usage governance
**Researched:** 2026-07-31
**Confidence:** HIGH overall (all stack versions verified against PyPI/Docker Hub; production patterns corroborated across multiple 2026 sources). MEDIUM on the Go↔Python seam specifics (emergent pattern) and Nigerian-edtech competitive claims (vendor marketing).

## Executive Summary

Academio is extending its existing Go-native AI stack (Gemini/OpenAI gateway, 10 agents, RAG, NL search) with an **additive Python AI engine** and a **Qdrant→pgvector migration**. Research confirms the locked architecture: Go stays the brain (auth, tenancy, queue, audit, cost), Python `ai-engine` is a stateless AI compute service called over REST/JSON + SSE behind a gRPC-ready seam. The 2026 ecosystem strongly validates this split — Go at the edge (concurrency, SSE relay, memory footprint), Python for LLM/doc-intelligence SDKs. The stack is deliberately small: FastAPI 0.140 (native SSE), uv, Docling 2.x for structured document parsing, direct provider SDKs (`anthropic` + `openai` covering all 5 new providers via `base_url`), psycopg 3 + pgvector-python (no SQLAlchemy — Go owns DDL).

Three decisions shape everything and must be locked **before Phase 1 starts**: **(1)** `ai_vectors` lives in the **`school_{id}` tenant schemas** (schema-per-tenant silo), not a shared table with tenant-scoped partial indexes as the implementation plan's PGV-04 implied — this makes isolation structural and eliminates the HNSW post-filter recall-collapse and cross-tenant leakage class of bugs entirely. **(2)** One canonical embedding model + dimension for the whole platform (recommended `text-embedding-3-small`, 1536-dim — but multilingual quality for Nigerian languages must be verified first, since a later model change means re-embedding the entire corpus). **(3)** The doc pipeline is **one Go→Python `/v1/documents` call** (parse→chunk→embed→store), not extract-then-ingest twice; and Python is a pure HTTP compute service — **no Celery, no auth/tenancy decisions, no queue** (asynq in Go is the only queue).

The core value is **grounded, tenant-safe document intelligence**: Nigerian school documents (policies, handbooks, lesson notes, past WAEC/NECO papers) searchable and quotable through the AI assistant with citations. RAG is a multi-stage pipeline — structure-aware chunking → hybrid dense + BM25 (Postgres tsvector/GIN, no new infra) + RRF fusion → cross-encoder reranker → citation-grounded generation → **evaluation harness that ships with the pipeline, not after**. The most expensive shortcuts are skipping the reranker, deferring the eval harness, and treating quotas/audit as a phase-5 bolt-on — the last is an OWASP-ranked security control (unbounded consumption) and must ship with the first AI endpoints. The single riskiest piece of new Go code is the SSE relay (four documented failure modes), followed by tenant isolation (the trust boundary) — both have concrete, research-backed mitigations below.

## Key Findings

### Recommended Stack

**Detail:** [STACK.md](./STACK.md)

Python 3.13 + FastAPI 0.140 (native SSE since 0.135 — `sse-starlette` obsolete), managed by `uv`. Direct provider SDKs, not LiteLLM: Go's `ModelRouter` already owns platform-level routing/failover, and LiteLLM would add ~7.5ms/call and duplicate that role. Docling 2.x is the 2026 document-intelligence standard with its built-in `HybridChunker` (tokenizer-aligned, heading metadata). **Image constraint:** full Docling pulls torch (~2.5 GB image); a documented light-path variant (PyMuPDF + `python-docx`/`python-pptx`/`openpyxl`, no torch, <600 MB) exists if the image is unacceptable.

**Core technologies:**
- **Python 3.13 + FastAPI 0.140.x**: async-native, Pydantic v2, native `EventSourceResponse` SSE — verified current stable (2026-07-28)
- **uv**: 2026-standard package/project manager; replaces pip/venv/poetry
- **Direct SDKs (`anthropic` 0.120.x + `openai` 1.x)**: one SDK covers Azure/DeepSeek/OpenRouter/Ollama via `base_url`; the second covers Claude — **NOT a Python gateway, NOT LiteLLM proxy** (both ruled out: latency + duplicated routing logic)
- **Docling 2.x + `HybridChunker`**: PDF/DOCX/PPTX/HTML → typed doc → Markdown with layout/reading-order/tables; chunking with heading metadata for citations
- **PyMuPDF 1.25.x + pytesseract 0.3.13**: fast digital-PDF text (~10x pypdf); Tesseract OCR for scanned/images (needs `tesseract-ocr-eng` system package)
- **psycopg 3 + pgvector-python**: async Postgres + pgvector client; no ORM (Go owns schema/migrations)
- **pgvector image `pgvector/pgvector:0.8.6-pg18-trixie`**: verified on Docker Hub (2026-07-30); **pin ≥0.8.2** (CVE-2026-3172)
- **pytest + testcontainers[postgres] + ruff + pyright**: test with `pgvector/pgvector:0.8.6-pg18`; lint/type-check with 2026 standards

**Critical stack constraints:**
- HNSW caps at **2000 dims on the `vector` type** — 3072-dim `text-embedding-3-large` requires `halfvec`; **default to 1536-dim**
- `VECTOR(n)` dimension is locked at DDL → Go and Python **must share one embedding model** (config-locked with startup fail-fast validation)
- No multi-statement `db.Exec()` (pgx v5) — applies to Python-side DDL too (irrelevant here: Go owns DDL)

### Expected Features

**Detail:** [FEATURES.md](./FEATURES.md)

RAG is a multi-stage pipeline (offline ingest strictly separated from online query), 72% of enterprises run RAG in production, and the quality levers are table stakes: structure-aware chunking, hybrid dense+BM25 with RRF fusion, a cross-encoder reranker, citations, and an evaluation harness. Teacher-side education AI is a crowded market — the floor is report-comment generation, lesson plans, quiz generation, rubrics, parent-communication drafts — **all human-in-the-loop, all grounded in the school's own data** (which is what no competitor combines with document intelligence).

**Must have (table stakes, P1):**
- **Async document pipeline** (upload → queue → extract → chunk → embed → indexed + notify) with status + failure/retry visibility — the Core Value
- **Multi-format parsing + OCR routing** (digital PDF / scanned PDF / DOCX / PPTX / TXT / CSV / image) with per-page extractor routing and quality gates
- **Structure-aware chunking** (Docling HybridChunker; 256–512 tokens for factual Q&A, 512–1024 for narrative) with metadata on every chunk
- **Hybrid retrieval: dense + BM25 with RRF** — implement BM25 via **Postgres full-text search (tsvector + GIN), NOT new infrastructure**; ~17% recall gain for <6ms
- **Citations in every RAG answer** (chunk IDs / source doc + page)
- **RAG evaluation harness** (golden set of 50–100 school-realistic QA pairs; faithfulness ≥0.85, context precision ≥0.75) — **ships WITH the pipeline, not after**
- **SSE streaming chat** (typed events, heartbeats, abort-on-disconnect, three timeouts, partial-response honesty)
- **Per-school usage audit + quotas/rate limits** — a security control (OWASP LLM top-ten: unbounded consumption), not a reporting feature
- **Multi-provider abstraction + fallback chains** (5 new providers behind existing Go ModelRouter)
- **Report comment generation** — grounded in student scores/attendance/behaviour, bulk-batch, mandatory human review
- **Versioned prompt library** (Git-backed YAML + dev/staging/prod aliases)

**Should have (differentiators, P2):**
- **Re-ranking (cross-encoder)** — the single highest-ROI quality addition after basic retrieval (10–30% precision lift); Cohere Rerank API or self-hosted BGE-reranker-v2-m3 (torch already present via Docling)
- Cross-lingual support (English + Yoruba/Hausa/Igbo/Pidgin) — **verify embedding model multilingual quality before locking it**
- Lesson plan generation (NERDC/WAEC/NECO-grounded), question/quiz generation from documents, parent-communication drafts (WhatsApp-ready), rubric generation, semantic caching (tenant-scoped keys), eval-gated prompt promotion, confidence-gated document processing (low-confidence OCR → human-review queue)

**Defer (v2+):**
- Exam paper intelligence (structured question banks — P3, needs table-extraction maturity)
- Student-facing tutor (evidence says impact is modest; separate guardrails product — defer deliberately)
- **Anti-features (do not build in v1):** AI detection tooling, AI-graded final scores, synchronous doc processing, RAG-on-every-query, silent ungrounded fallback (fail closed instead), handwriting OCR, transparent mid-stream provider failover, durable resumable streams, AI proctoring/surveillance

### Architecture Approach

**Detail:** [ARCHITECTURE.md](./ARCHITECTURE.md)

Two-runtime modular monolith: **Go is the brain, Python is the engine.** Go owns the edge (JWT auth, tenant resolution, RBAC, rate limiting, quotas, audit, cost ledger, asynq queue, SSE relay); Python is a stateless compute service with no user-auth surface, no queue, no business rules. **Tenant boundary is structural, not a WHERE clause**: `ai_vectors` lives in `school_{id}` schemas (schema-per-tenant silo — Academio's existing strongest pattern), and Python re-enforces tenancy by validating `schema_name` against `^school_\d+$` on every query with **no global fallback**. Both runtimes read/write the same `school_{id}.ai_vectors` table; Go's existing `vector.Store` interface is preserved via a tenant-from-context pgvector implementation (zero RAG/agent changes).

**Major components:**
1. **Go API + AI Orchestrator** (`internal/modules/ai`, new `internal/ai/orchestrator/`) — the only component that talks to clients; auth/tenancy/quotas/audit/cost; never delegates auth to Python
2. **Go EngineClient** (`internal/ai/engine/`) — `EngineClient` interface + HTTP/JSON+SSE impl, gRPC-ready; service-token auth (`AI_ENGINE_TOKEN`), `X-Request-ID` correlation
3. **Go ModelRouter (existing, unchanged logic)** — platform-level failover (gemini ↔ openai ↔ python); Python wired in as one `providerEntry`. **Two-level routing**: Go stays the platform-level failover point; Python uses direct SDKs internally. **Strict timeout layering: Go→Python timeout > Python→LLM timeout** so the two levels never fight
4. **Go asynq worker (`ai:doc-ingest`)** — resolves tenant DB by schoolID, calls Python **`/v1/documents` in one call**, updates status, publishes events, notifies
5. **Python ai-engine** — LLM integrations (5 providers), embeddings, OCR/extraction, chunking, tenant-aware hybrid RAG (with `/v1/providers` status endpoint for INT-02), reranking, citations, versioned prompts; `core/` has zero HTTP imports so a future gRPC server reuses the same services
6. **`school_{id}.ai_vectors`** — single source of truth for chunks; per-schema HNSW index (structurally tenant-scoped, no partial-index management, no RLS needed)
7. **Shared infra** — Postgres 18 + pgvector, Redis/asynq, shared uploads volume (both containers mount it — files passed by path, no multipart re-transfer), Prometheus/Grafana

**Key architecture patterns:** orchestrator/compute split; two-level provider routing with direct SDKs; SSE relay with SSE-aware scanner + context propagation + bounded channel + in-band errors (the 4 failure modes and fixes below); gRPC-ready seam (`proto/aiengine.proto` written in Phase 2 — cheap now, expensive to retrofit); async job pipeline with retry classification (transient → retry, permanent → fail-fast); cross-tenant probe suite in CI.

### Critical Pitfalls

**Detail:** [PITFALLS.md](./PITFALLS.md)

1. **Tenant data leakage via app-layer-only vector filtering** — the trust boundary. A 2026 study measured 62–100% cross-tenant leakage under adversarial probing; embeddings are near-reversible (~92% recovery), so a mis-scoped read is a *content* leak. *Avoid:* `ai_vectors` in tenant schemas (structural isolation); resolve tenancy once in Go from the JWT; Python re-asserts `^school_\d+$` with no fallback; tenant-scoped cache keys; **cross-tenant probe suite in CI** (canary chunks per tenant, assert zero hits across every entry point — search, cache, reranking, agent tools, workers)
2. **SSE relay failure modes (the riskiest new Go code)** — four documented failures: chunk-boundary corruption (SSE event split across TCP packets → corrupted JSON), token leaks after client disconnect (upstream keeps billing), unbounded buffering under slow clients (OOM), mid-stream errors after HTTP 200 (status can't change). *Avoid:* SSE-aware `bufio.Scanner` (custom `\n\n` split, larger buffer than the 64 KB default), `r.Context()` propagation into the upstream call, bounded channel (cap 64) + abort on slow writer, in-band `error` events every client must check, `X-Accel-Buffering: no`, heartbeats ≤30s, one shared event envelope (delta/tool_call/citation/usage/error/done)
3. **HNSW post-filter recall collapse** — with a shared table, HNSW walks all tenants' graph nodes then filters; a tenant with 10% of rows gets ~4/40 candidates at default `ef_search`. *Avoid:* schema-per-tenant tables (per-schema index contains only that school's vectors — zero dilution); if a shared table is ever forced: `hnsw.iterative_scan = strict_order` (pgvector ≥0.8.0) + over-fetch
4. **Qdrant→pgvector semantics mismatch** — dimension mismatch, inverted distance (Qdrant similarity vs pgvector `<=>` distance: `similarity = 1 - distance`), ID collisions, dropped metadata payloads, mixed embedding models. *Avoid:* reconcile semantics before writing code; `COUNT(*)`/dimension/ops-class parity asserts; keep Qdrant behind the interface until cutover verified; interface-conformance tests; version every vector
5. **Doc-ingest not idempotent** — asynq is at-least-once; a crash between embed and notify re-runs extract→chunk→embed→insert → duplicate vectors. *Avoid:* unique constraint on `(document_id, chunk_index)` + `INSERT ... ON CONFLICT DO NOTHING`; status state machine (`queued→extracting→chunking→embedding→completed/failed`); `asynq.SkipRetry` for permanent failures; monitor the archive (DLQ) as an SLO
6. **Embedding model unversioned** — two vector spaces in one column = silent, undiagnosable retrieval collapse; upgrade requires full rebuild. *Avoid:* `embedding_model` + `model_version` + `chunking_version` columns on `ai_vectors` from day one; scope queries to one active version
7. **LLM failover cost explosion + silent regression** — fallback to expensive models, reroute tax, confident-but-worse fallback output with zero error rate. *Avoid:* classify errors (429 → failover, never retry same provider; 5xx/timeout → retry once then failover; other 4xx → permanent, no failover); per-request cost caps + per-tenant daily spend caps; cost-per-successful-task in currency (tokens vary ~40% across tokenizers); dialect translation layer (stream event shapes differ per provider)

## Implications for Roadmap

The implementation plan's P0–P6 phases stand, with **refinements that must be reflected in roadmap requirements**. The critical path is P0 → P1 → P2 → P4 → P5, with P3 (SSE relay) parallelizable after P0+P2. P1 and P2 are independent except for the shared embedding-canon decision and the shared volume.

### Phase 0: Foundation (seam + infra)
**Rationale:** Everything depends on the Go↔Python seam existing with correct timeout/auth discipline before any AI traffic flows. Also the cheapest place to fix ingress buffering.
**Delivers:** `EngineClient` interface + HTTP impl (`internal/ai/engine/`), `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` config with fail-fast validation (Rule B12), docker-compose `ai-engine` service (internal network only, health-checked), CI workflow for Python.
**Avoids:** Pitfall 8 (Go↔Python seam: bare `http.Client` with no timeouts, token in URL, contract drift). Per-endpoint timeout budgets: `/v1/extract` minutes, `/v1/chat` seconds, stream path no overall cap.
**Research flag:** MEDIUM confidence on seam specifics — validate the emergent pattern during implementation.

### Phase 1: pgvector migration — **two decisions locked FIRST**
**Rationale:** The single highest-leverage phase. The two locked-in-advance decisions gate everything and must be resolved *before* any pgvector DDL:
1. **`ai_vectors` lives in `school_{id}` tenant schemas** (schema-per-tenant), NOT a shared table with tenant-scoped partial indexes as PGV-04 implied. Migration change: table + HNSW index created in each tenant-schema migration (and the school-migration runner at provisioning). This is a **critical Phase-1 decision** — it eliminates the entire class of HNSW post-filter recall and cross-tenant leakage problems.
2. **One canonical embedding model + dimension** (recommend 1536-dim, `text-embedding-3-small` — but **verify multilingual quality for Nigerian languages first**; `text-embedding-3-*` is documented weak there; evaluate Cohere embed-v3 / BGE-m3 before locking, since a change later = full re-embed). Config-pinned (`AI_EMBEDDING_DIM`) with startup validation that model output matches the column type.
**Delivers:** Postgres image swap to `pgvector/pgvector:0.8.6-pg18-trixie` (pin ≥0.8.2 for CVE-2026-3172), `CREATE EXTENSION vector` in shared + tenant migrations, tenant-schema `ai_vectors` + HNSW index (`vector_cosine_ops` + `<=>`; raise `maintenance_work_mem` to 8–16 GB for the build), pgvector `Store` impl (tenant-from-ctx), interface-conformance tests, Qdrant copy + config swap + retirement.
**Avoids:** Pitfalls 1, 2, 3, 4, 10 (isolation model, recall collapse, migration semantics, silent seq-scan, unversioned embeddings — add `embedding_model`/`model_version`/`chunking_version` to the DDL).
**Research flag:** Lock decisions 1+2 in the first requirements session — everything else in this phase is standard, well-documented pgvector work (skip research-phase for the mechanics; the *decisions* need product/engineering sign-off).

### Phase 2: Python engine (FastAPI + direct SDKs)
**Rationale:** Python must exist before any pipeline or streaming work. Include two refinements from research: **write `proto/aiengine.proto` now** as the gRPC contract (cheap now, expensive to retrofit — REST endpoints must satisfy proto semantics 1:1), and **add `/v1/providers`** to the endpoint list (PYE-04) — it is required by INT-02.
**Delivers:** FastAPI skeleton, service-token middleware, telemetry (`/metrics`, structlog, request-ID middleware), `/health`, **direct-SDK multi-provider layer (anthropic + openai via `base_url`, covering Anthropic/DeepSeek/OpenRouter/Azure/Ollama — NOT a Python gateway, NOT LiteLLM proxy)**, `/v1/chat`, `/v1/chat/stream` (native SSE), `/v1/embed`, extraction with per-page routing (digital → PyMuPDF, scanned → Tesseract at ≥300 DPI, quality gates), chunking (HybridChunker), `/v1/providers`.
**Avoids:** Pitfall 5 (scanned/mixed PDF silent loss — page-level routing + quality gates), Pitfall 6 (provider dialect normalization, error classification), Pitfall 7 (Python SSE endpoint correctness: headers, heartbeats, no gzip).
**Research flag:** Cross-lingual embedding verification is a Phase-2 blocker for the Phase-1 DDL — run it as a small spike during planning. Docling image weight (~2.5 GB torch) needs an explicit accept/light-path decision.

### Phase 3: SSE relay route (INT-01) — parallelizable after P0+P2
**Rationale:** Independent of Phase 1 (no vectors needed for chat streaming). This is the **riskiest new Go code** — budget real review/test time.
**Delivers:** `POST /api/v2/ai/chat/stream` with the full relay playbook: SSE-aware scanner (event-boundary splitting, larger buffer), `r.Context()` cancellation → upstream abort, bounded channel (cap 64) + slow-client abort, in-band `error` events after 200, `X-Accel-Buffering: no` + compression excluded for `text/event-stream`, heartbeats, one shared event envelope (delta/citation/usage/error/done).
**Avoids:** Pitfall 7 (buffered tokens, 60-second deaths, garbled relay). Test through a real proxy in CI.
**Research flag:** Lock the shared SSE event envelope in the Phase 2/3 requirements — the frontend integration depends on it (design proposal, not ecosystem standard).

### Phase 4: Document pipeline (PIP-01/02) — **with quotas/audit and eval harness pulled forward**
**Rationale:** The Core Value. Research refinement: the pipeline is **one Go→Python `/v1/documents` call** (extract+chunk+embed+store), not `/v1/extract` then a second ingest step — `/v1/extract` stays as a standalone endpoint for future preview/re-extract features only. Files pass by shared uploads volume path. **Pull forward INT-03's security controls (rate limits, quotas, audit log) and the small RAG evaluation harness (golden set 50–100 QA pairs) into this phase** — quotas/audit are an OWASP-ranked security control that must ship with the first AI endpoints (a noisy tenant must not starve others the day the pipeline goes live), and the eval harness gates every subsequent quality change.
**Delivers:** Upload endpoint + status endpoint (surfacing pages/OCR'd/char count/confidence), asynq `ai:doc-ingest` task + worker, idempotent ingest (unique constraint + `ON CONFLICT DO NOTHING`, status state machine, transient-vs-permanent retry classification, DLQ monitoring), `document.ingested`/`document.failed` events + notification, usage audit rows + per-school quotas/rate limits in Redis, versioned prompt library (Git-backed).
**Avoids:** Pitfalls 9 (non-idempotent ingest), 8 (timeout budgets: `asynq.Timeout` ≥ worst-case OCR), plus the governance gap (quotas/audit deferred = unbounded consumption risk from day one).
**Research flag:** Docling extraction quality needs fixture-based validation (scanned/multi-column/table/CID-encoded fonts in the pytest corpus).

### Phase 5: RAG + integration (PYE-05, INT-02/03/04)
**Rationale:** Depends on Phase 4 (documents to search). Hybrid search is the full multi-stage pipeline: hybrid dense + Postgres FTS/BM25 (tsvector + GIN, RRF k=60) → metadata filters → **cross-encoder reranker** (Cohere API or BGE-reranker-v2-m3 — skipping it is the most expensive shortcut) → citation-grounded generation → evaluation harness gates. Wire Python into ModelRouter as one `providerEntry`, `/v1/providers` status endpoint, orchestrator hardening (retries/circuit breakers on Python calls, tenant-scoped semantic cache).
**Delivers:** `/v1/search` hybrid retrieval with citations, reranking, eval harness integration (CI gate on faithfulness/context precision), `/api/v2/ai/providers`, ModelRouter two-level routing with strict timeout layering (Go→Python > Python→LLM), cost-per-task metrics.
**Avoids:** Pitfalls 6 (cost explosion — cost caps, currency-based accounting) and the retrieval-quality anti-patterns (RAG-on-every-query, silent ungrounded fallback — fail closed).
**Research flag:** Reranker choice (API vs self-hosted) is a cost/latency/quality trade-off — decide with a benchmark on the golden set, not on paper.

### Phase 6: Observability, security, cross-tenant proof
**Rationale:** Proves what earlier phases built. Not optional — the cross-tenant probe suite is the measurable isolation guarantee.
**Delivers:** Metrics/correlation across runtimes (`X-Request-ID` end-to-end), PII masking (never log document contents or prompt bodies), **cross-tenant probe suite in CI** (canary chunks per tenant, query across all entry points — search, cache, rerank, agent tools, workers — assert zero leakage), RAG-accuracy + load + concurrency tests, Grafana dashboard, Qdrant retirement (RET-02), architecture docs update (RET-03).
**Avoids:** Pitfall 1 verification gap — "looks done but isn't" checklist: EXPLAIN assertions, kill-worker-mid-pipeline test, proxy-in-the-middle streaming test, provider failover cost tests.

### Phase Ordering Rationale

- **Embedding canon and table placement gate Phase 1 DDL** — both are one-way doors (column dimension is fixed at DDL; schema placement determines the isolation model). Resolve them in requirements, verify multilingual quality as a Phase-2-spawned spike, then ship the migration.
- **P0→P1→P2→P4→P5 is the dependency spine** — the seam (P0) before any traffic; vectors (P1) and Python (P2) before the pipeline (P4); documents before RAG (P5). P3 (SSE) runs in parallel after P0+P2 since it needs neither vectors nor documents.
- **Security controls ride the first AI endpoints, not a later phase** — quotas/audit are cheap while traffic is low and expensive to retrofit under load; the eval harness is similarly cheap with a 50–100-pair golden set and gates every later quality change.
- **Tenant isolation is proven structurally, then measured** — Phase 1 makes the boundary physical (schema-per-tenant); Phase 6 proves it continuously in CI. Neither replaces the other.

### Research Flags

Phases needing deeper research during planning:
- **Phase 1 (decision lock):** multilingual embedding model selection for Nigerian languages (Yoruba/Hausa/Igbo/Pidgin) — `text-embedding-3-*` is documented weak; run a small evaluation spike before DDL. Also confirm exact Qdrant payload fields to migrate.
- **Phase 2 (Python engine):** cross-lingual embedding verification (same spike); Docling full-vs-light image decision; `proto/aiengine.proto` method surface (lock before frontend integration).
- **Phase 3 (SSE):** shared event envelope design (delta/citation/usage/error/done) — design proposal, not ecosystem standard; frontend `fetch` + ReadableStream parsing approach.
- **Phase 5 (RAG):** reranker selection benchmark (Cohere API vs BGE-reranker-v2-m3) on the golden set; BM25/tsvector configuration vs metadata filters.
- **Go↔Python seam overall:** emergent pattern, MEDIUM confidence — validate during Phase 0 implementation, keep the gRPC seam mechanical.

Phases with standard patterns (skip research-phase):
- **Phase 0:** HTTP client seam, service-token auth, docker-compose service — well-documented, established patterns (follow existing `ai:scoring` handler pattern).
- **Phase 1 mechanics:** pgvector image swap, extension creation, HNSW DDL, `Store` interface conformance — all standard pgvector documentation (the *decisions* are the flag, not the mechanics).
- **Phase 4:** asynq task patterns, status endpoints, notification events — direct analogs already exist in the codebase (`ai:scoring`).
- **Phase 6:** Prometheus metrics, pytest/Go test tooling, Grafana — standard observability work.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every version pinned and verified against PyPI/Docker Hub/GitHub (July 2026); pgvector 0.8.6-pg18-trixie image confirmed; CVE-2026-3172 pin documented |
| Features | HIGH (MEDIUM on Nigerian-edtech) | RAG pipeline, gateway, SSE, quotas patterns consistent across 7+ independent 2026 sources; Nigerian competitor claims are vendor marketing (feature-fabric comparison only) |
| Architecture | HIGH (MEDIUM on Go↔Python seam) | pgvector multi-tenancy + SSE relay patterns HIGH (production sources converge); the exact Go-orchestrator↔FastAPI-with-gRPC-seam pattern is emergent — opinionated recommendation, validate in P0/P2 |
| Pitfalls | HIGH (MEDIUM on tuning numbers) | Multi-source agreement on failure modes; exact tuning numbers (HNSW m/ef_construction, OCR CER) are single-source — measure on own data |

**Overall confidence: HIGH** — decisions are safe to make from this research. Treat seam details, event-envelope shape, and embedding-model selection as validation items during planning, not blockers.

### Gaps to Address

- **Embedding model multilingual quality**: the canonical-model decision (Phase 1 blocker) needs a small evaluation against Nigerian-language queries before DDL — schedule as a planning-phase spike, not during the migration.
- **SSE event envelope is a proposal**: lock the exact JSON shapes (delta/tool_call/citation/usage/error/done) in Phase 2 requirements before any frontend work.
- **Reranker choice (Cohere API vs BGE-reranker-v2-m3)**: unresolved in research — decide via benchmark on the golden set (cost/latency/quality trade-off).
- **Docling image weight**: torch ~2.5 GB — make an explicit full-vs-light-path decision in Phase 2; the light path is a documented fallback, not a compromise on structure-aware chunking if full is acceptable.
- **Exact Qdrant payload fields**: verify `_doc_id`/`_chunk_index`/`_text` metadata mapping to `ai_vectors` columns during Phase 1 (migration semantics, not volume, is the risk).
- **Tuning numbers (HNSW m/ef_construction, chunk sizes)**: sources disagree; benchmark on production-shaped data per tenant, gate via the eval harness.

## Sources

### Primary (HIGH confidence)
- **PyPI / Docker Hub / GitHub (2026-07-28..30)**: FastAPI 0.140.13, Pydantic 2.13.4, anthropic 0.120.2, pgvector-python 0.4.x, Docling 2.x (Py3.13 issue #136 closed), pytesseract 0.3.13 (#567), `pgvector/pgvector:0.8.6-pg18-trixie`, prometheus-fastapi-instrumentator 8.0.2, astral uv docs
- **pgvector multi-tenancy**: "Secure Multi-Tenant RAG with pgvector and PostgreSQL RLS" (2026-07), Particula Tech "Multi-Tenant RAG: Silo, Pool, or Bridge" (2026-07), "Hard Multi-Tenancy for pgvector" (2026-07), "Your WHERE clause is not a security boundary" (2026-06), pgvector official README/CHANGELOG (iterative scan, defaults)
- **SSE relay**: Preto.ai "Streaming SSE Proxying for LLM APIs: The Hard Parts" (2026-04, 5,000 req/s <50ms p95), server-sent-events.com Go patterns (2026-05), FastAPI official SSE docs, "Why your LLM SSE stream dies after 60 seconds" (2026-05)
- **RAG production patterns**: Datarmatics, MetafiedLab (72% enterprise adoption), Unstructured, Prompt20 — 7 independent 2026 sources agreeing on pipeline structure
- **Multi-provider routing**: BerriAI/litellm ARCHITECTURE.md + docs, DevOpsNess "Multi-Provider LLM Routing" (2026-05), OpenRouter/LiteLLM comparisons (2026-06)
- **In-repo ground truth (verified)**: `backend/internal/ai/` (Provider/ModelRouter/vector.Store/RAG), `backend/internal/middleware/` (GetTenantDB, tenantDBResolver), `backend/internal/queue/tasks.go` (`ai:scoring` pattern), docker-compose, `docs/plans/AI-PLATFORM-IMPLEMENTATION-PLAN.md`, `AGENTS.md`

### Secondary (MEDIUM confidence)
- **Go edge / Python compute split**: Sentinel, carmel/gomlx (Go-gateway↔Python-worker precedent), "API Gateway Pattern for AI Agent Microservices" (2026-03), "FastAPI System Design for AI Production" (2026-05) — converging blog/dev-grade, not enterprise-scale authoritative
- **Nigerian edtech**: EDVES, Eedu, Oponeko, Provsy, Acceede, Mariobee, EduTek, Schoogle — vendor marketing claims, feature-fabric comparison only
- **Tuning numbers**: HNSW m/ef_construction ranges, OCR CER figures — sources disagree; measure on own data
- **PyMuPDF vs Docling benchmark**: direction corroborated by multiple sources

### Tertiary (LOW confidence)
- Exact "Go orchestrator ↔ Python FastAPI with gRPC seam" enterprise pattern — emergent; closest precedent is gomlx; treat seam design as opinionated recommendation
- SSE event envelope (delta/citation/usage/error/done) — design proposal, not ecosystem standard

---
*Research completed: 2026-07-31*
*Ready for roadmap: yes*
