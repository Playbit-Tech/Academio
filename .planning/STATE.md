---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 05 context gathered (all 5 gray areas decided by agent discretion)
last_updated: "2026-08-01T19:18:59.292Z"
last_activity: 2026-08-01 -- Phase 05 execution started
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 26
  completed_plans: 23
  percent: 88
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-01)

**Core value:** Document intelligence that works — upload documents, get extract → chunk → embed → searchable knowledge through the AI assistant, tenant isolation intact, without breaking the existing Go AI layer.
**Current focus:** Phase 05 — go-integration-orchestrator

## Current Position

Phase: 05 (go-integration-orchestrator) — EXECUTING
Plan: 1 of 3
Status: Executing Phase 05
Last activity: 2026-08-01 -- Phase 05 execution started

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 11
- Average duration: 10min
- Total execution time: 10min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 5 | - | - |
| 04 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01-foundation P01 | 10min | 3 tasks | 13 files |
| Phase 01-foundation P04 | 5 | 2 tasks | 5 files |
| Phase 01-foundation P02 | 25 | 2 tasks | 5 files |
| Phase 01-foundation P03 | 3 | 2 tasks | 1 files |
| Phase 01-foundation P05 | 3 | 2 tasks | 1 files |
| Phase 02-pgvector-migration P02 | 5 | 2 tasks | 4 files |
| Phase 02-pgvector-migration P02-01 | 15 | 2 tasks | 6 files |
| Phase 02-pgvector-migration P03 | 8 | 2 tasks | 1 files |
| Phase 02 P04 | 15 | 2 tasks | 5 files |
| Phase 02-pgvector-migration P05 | 7 | 1 tasks | 1 files |
| Phase 02-pgvector-migration P06 | 10 | 3 tasks | 8 files |
| Phase 03-python-ai-engine P01 | 12 | 2 tasks | 1 files |
| Phase 03-python-ai-engine P03-02 | 14 | 4 tasks | 12 files |
| Phase 03-python-ai-engine P04 | 14 | 3 tasks | 9 files |
| Phase 03-python-ai-engine P05 | 25 | 3 tasks | 17 files |
| Phase 03-python-ai-engine P03-06 | 14 | 3 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: ai-engine/ is a tracked root directory (submodule-ready; no remote exists yet — .gitmodules only has backend/frontend/mobile)
- [Phase 1]: EngineClient seam is the backbone of ALL AI traffic → AI_ENGINE_URL/TOKEN validation is UNCONDITIONAL in config.validate() (Rule B12), not gated on AI_ENABLED; config_test.go fixture updated accordingly
- [Phase 1]: ai-engine compose service has NO published host port — internal network only; healthcheck uses python urllib (python:3.13-slim ships no curl), targets unauthenticated GET /health
- [Phase 1]: No `depends_on: api → ai-engine` — backend boots while engine is down; circuit breaker handles runtime outages
- [Phase 1]: Compose api env carries AI_ENGINE_URL=http://ai-engine:8000 + shared token (default local-dev-token) so unconditional validation passes in compose
- [Phase 1]: Root CI workflow ai-engine.yml mirrors docs.yml conventions; setup-uv pinned to v9.0.0 commit SHA; uv sync --frozen (lockfile committed)
- [Phase 2, blocker]: `ai_vectors` lives in `school_{id}` TENANT schemas (structural isolation; NOT shared + partial indexes)
- [Phase 2, blocker]: Canonical embedding model + dimension locked BEFORE pgvector DDL (PGV-04a; 1536-dim default, ≤2000 for HNSW; Nigerian-language multilingual eval first)
- [Phase 2]: pgvector image pinned ≥0.8.2 (CVE-2026-3172)
- [Phase 3]: `proto/aiengine.proto` written at start of Python phase; REST satisfies it 1:1
- [Phase 3]: `/v1/providers` added to PYE-04 (required by INT-02)
- [Phase 3]: Direct SDKs only (`anthropic` + `openai` base_url); NO LiteLLM, NO Python gateway, NO Celery
- [Phase 4]: Doc pipeline = ONE Go→Python `/v1/documents` call (PIP-01)
- [Phase 4]: SSE relay = riskiest new Go code; 4 failure modes with fixes (INT-01)
- [Phase 5]: INT-03 quota/audit/rate-limit ship WITH first endpoints — first plan in phase, not a bolt-on
- [Phase 6]: RAG eval harness + cross-tenant probe suite ship in CI (TES-01)
- [Phase 01-foundation]: ai-engine/ bootstraps via uv sync (Python 3.13, fastapi 0.140.13, committed uv.lock) — verified clean-state; smoke tests + ruff + pyright gates clean
- [Phase 01-foundation]: Service-token auth contract: X-AI-Engine-Token header only (never URL/JWT); empty token -> 401 on every protected route (no insecure bypass); /health unauthenticated by design for container healthchecks
- [Phase 01-foundation]: AI engine seam (AI_ENGINE_URL/TOKEN) validation is UNCONDITIONAL in config.validate() (Rule B12/FND-04) — not gated on AI_ENABLED, not in validateProduction(); .env.example documents both as REQUIRED; dev token local-dev-token matches compose default
- [Phase 01-foundation]: ChatStream carries NO overall timeout — context-bound by design (FND-03); caller cancels on client disconnect via NewRequestWithContext
- [Phase 01-foundation]: Timeouts applied per-endpoint via context.WithTimeout (chat 30s, extract 5m, health 10s), not http.Client.Timeout — transport stays budget-agnostic
- [Phase 01-foundation]: X-Request-ID sourced from middleware.GetRequestIDFromCtx; uuid.NewString() fallback when absent (never blindly attacker-controlled)
- [Phase 01-foundation]: SSE reader primitive: bufio.Scanner custom split on blank lines with 1MB buffer (>64KB default) — never blind io.Copy; comment/heartbeat tolerance
- [Phase 01-foundation]: ai-engine compose service has NO published host port — internal network only; verified live via docker inspect PortBindings {} + host curl refused (T-03-02)
- [Phase 01-foundation]: Healthcheck uses python stdlib urllib one-liner (python:3.13-slim ships no curl), timeout=3, start_period 10s — targets unauthenticated GET /health
- [Phase 01-foundation]: Root CI workflow ai-engine.yml mirrors docs.yml conventions; setup-uv pinned to v9.0.0 commit SHA; uv sync --frozen (lockfile committed)
- [Phase 01-foundation]: docker-build job has no uv steps and no registry login — proves multi-stage Dockerfile on clean runner; workflow sets no secrets (T-05-03)
- [Phase 02-pgvector-migration]: Pinned pgvector/pgvector:0.8.6-pg18-trixie (>=0.8.2, CVE-2026-3172); verified PGDATA /var/lib/postgresql/18/docker identical to running postgres:alpine 18.4 so shared-postgres-data volume survives the swap with zero data loss
- [Phase 02-pgvector-migration]: Vector extension installed via core migration 2026_08_01_000000_enable_vector_extension into public schema (default search_path at core-migration time, precedes school DDL); tenant migration repeats IF NOT EXISTS as harmless no-op
- [Phase 02-pgvector-migration]: PGV-04a canon locked: AI_EMBEDDING_DIM=1536 (text-embedding-3-small) in config with fail-fast validate() (<=0 or >2000 error, Rule B12); Nigerian-language adequacy spike test added (skips cleanly without AI_OPENAI_API_KEY, D-01 canon stands pending eval, T-PGV-01-03)
- [Phase 02-pgvector-migration]: D-09 executed as flattened parity columns (document_id/chunk_index/text, no jsonb) in ai_vectors — matches Qdrant payload keys _doc_id/_chunk_index/_text at rag/pipeline.go:116-118, preventing payload-key drift between store (02-04) and copy tool (02-05); created_at AND updated_at included per D-09
- [Phase 02-pgvector-migration]: Applied the ai_vectors migration to all 12 existing school_N schemas via ApplySchoolMigrationsForSchema (temp gitignored runner in backend/tmp/) instead of cmd/migrate-schemas, which is pre-existing-broken (queries nonexistent database_name column) and only handles schema_name IS NULL schools; server binary rebuilt so future tenant provisioning includes the migration
- [Phase 02]: Fixed SchemaTablePrefix plugin to rewrite Statement.TableExpr: GORM v1.31.2 QuoteTo prefers TableExpr over the plugin-mutated Statement.Table, so .Table('ai_vectors') silently hit the unqualified table; now resolves to school_{id}.ai_vectors (plan 02-04)
- [Phase 02]: tenantFor returns validated schema string; Search/Delete build qualified names from it instead of repos.SchemaName() which is empty on ForSchoolSchema path (plan 02-04)
- [Phase 02-pgvector-migration]: Qdrant unreachable no-ops with exit 0 (safe no-op); only transport failures classify as no-op, all other failures exit non-zero
- [Phase 02-pgvector-migration]: Copy is idempotent: clear-then-copy per collection (DELETE WHERE collection = ? then CreateInBatches 500) through the tenant factory schema-scoped session
- [Phase 02-pgvector-migration]: AI_PGVECTOR_DSN required unconditionally in config.validate() (mirrors AI_ENGINE_URL precedent; no default, Rule B6/B12) — server never starts without a vector backend
- [Phase 02-pgvector-migration]: Config swap + router wiring landed in the SAME commit (T-PGV-06-03) so there is no window where RAG is silently disabled (RESEARCH pitfall 6)
- [Phase 02-pgvector-migration]: D-14 startup probe: embedder invoked with probe text; error or dimension mismatch vs AI_EMBEDDING_DIM -> logger.Fatal (fail-fast, cmd/server precedent)
- [Phase 03-python-ai-engine]: Proto lives at repo ROOT (proto/aiengine.proto), sibling of backend/ and ai-engine/ — single source of truth importable by both submodules (D-11)
- [Phase 03-python-ai-engine]: Service AiEngine exposes exactly 6 RPCs mapped 1:1 to REST: Chat, ChatStream, Embed, Extract, IngestDocument, Search
- [Phase 03-python-ai-engine]: GET /v1/health and GET /v1/providers are deliberately NOT proto RPCs — infrastructure/ops surface, not domain calls
- [Phase 03-python-ai-engine]: ChatRequest.Model carries provider:model composite; Usage normalized (provider, model, input/output tokens, cost) on every ChatResponse (D-03, ROADMAP criterion 2)
- [Phase 03-python-ai-engine]: IngestDocumentRequest/SearchRequest carry schema_name with ^school_[0-9]+$ + existence validation semantics (D-07/D-09) — no global fallback
- [Phase 03-python-ai-engine]: No gRPC runtime, no codegen, zero changes to backend/internal/ai/engine/* in this plan (PYE-04a, T-03-01-02)
- [Phase 03-python-ai-engine]: All 13 Phase 3 deps uv-locked (anthropic/openai/psycopg/pgvector/tenacity/doc parsers); fastapi pin <0.141 preserved
- [Phase 03-python-ai-engine]: Settings exposes 25 AI_* fields with locked defaults + http(s):// base_url fail-fast (T-03-02-03)
- [Phase 03-python-ai-engine]: parse_model_composite splits provider:model on first colon (D-03); registry knows configured providers
- [Phase 03-python-ai-engine]: Compose provider keys are empty-safe ${VAR:-}; AI_ENABLED NOT wired (Phase 5 gate)
- [Phase 03-python-ai-engine]: AI_OLLAMA_BASE_URL compose default host.docker.internal + host-gateway extra_hosts (Linux W4)
- [Phase 03-python-ai-engine]: require_token extracted to app/security.py to break app.main<->api circular import (plan sketch imported from app.main)
- [Phase 03-python-ai-engine]: tenacity decorators applied via _retried() Any-helper — pyright overload workaround (call-site safe)
- [Phase 03-python-ai-engine]: GET /v1/providers returns D-10 contract {provider, status, latency_ms, last_checked, cooldown_until}; unconfigured providers report unavailable inside 200, never 500
- [Phase 03-python-ai-engine]: Schema identifier interpolated via psycopg sql.Identifier (not raw f-string) - pyright-typed AND defense-in-depth quoting over the ^school_[0-9]+$ allowlist
- [Phase 03-python-ai-engine]: Pillow bomb guard set on Image.MAX_IMAGE_PIXELS (Pillow 12.3.0 reads Image module global, NOT ImageFile)
- [Phase 03-python-ai-engine]: require_token imported from app.security (not app.main - circular import, 03-04 pattern)
- [Phase 03-python-ai-engine]: chunker test expectation corrected: stride-800 algorithm yields 4 chunks for 2500 chars; 2400 chars is the 3-chunk case
- [Phase 03-python-ai-engine]: /v1/documents maps EmbeddingNotConfiguredError -> 503 (fail-loud, parity with /v1/embed)
- [Phase 03-python-ai-engine]: Hybrid search (D-06): HNSW <=> dense + PG ts_rank BM25 fused with RRF k=60 behind POST /v1/search, schema-validated per request (D-07/D-09)
- [Phase 05-01-go-integration-orchestrator]: AI Orchestrator middleware (ai_orchestrator.go) enforces per-school 300 req/min / per-user 60 req/min / stream 20 req/min via the SHARED Redis sliding-window RateLimiter with ai:rl:{scope}:{school_id} and ai:rl:{scope}:{school_id}:{user_id} keys; returns 429 + Retry-After (D-02/D-03/D-04); applied to the whole /api/v2/ai group in router.go after auth, before handlers
- [Phase 05-01]: AIOrchestratorService handles quota pre-flight (D-05/D-06: daily cap + per-request cost via ai.CalculateCost), tenant-scoped cache (D-10/D-11: ai:cache:{school}:{endpoint}:{sha256(prompt+model)}, chat 10m/search 5m/providers 15s), post-call RecordUsage (D-05/D-08: Redis INCRBY atomic counter + ai_usage_log ledger row), and D-15 timeout layering (Go 35s > Python 30s); fail-open on Redis for quota pre-flight, fail-loud on ledger writes (B9)
- [Phase 05-01]: ai_usage_log migration + model in public schema (shared, no PII, T-05-03): school_id, user_id, provider, model, input_tokens, output_tokens, cost_cents, request_id, created_at; registered in core.go and models/schema.go AllModels(); cost converted USD float -> integer cents round-half-up so SUM(cost_cents) == Redis counter (A3)
- [Phase 05-01]: Config adds AI_RATE_LIMIT_PER_SCHOOL (300), AI_RATE_LIMIT_PER_USER (60), AI_RATE_LIMIT_STREAM_PER_USER (20), AI_QUOTA_DAILY_SPEND_CENTS (0=unlimited), AI_QUOTA_MAX_REQUEST_CENTS (0=unlimited); validate() fails fast on <=0 rate limits and negative quota (Rule B12)
- [Phase 05-01]: Handler post-call RecordUsage wired on Chat (real tokens + cost from engine usage) and Search (zero-cost ledger row for observability); WithOrchestrator attaches service; router setup instantiates orchestrator when AI enabled + Redis present
- [Phase 05-01]: Streaming stays on the engine relay seam (engine.ChatStream) — context-bound (FND-03), preserves Phase 4 SSE envelope (delta/citation/usage); orchestrator GenerateText/GenerateTextStream wrappers are the D-16 routing seam that becomes active in 05-02 when Python providers join the ModelRouter (fixed Go-side timeout on a whole SSE session would kill legitimately long streams)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 2] PGV-04a canonical embedding decision must be locked during Phase 2 planning, before any `ai_vectors` DDL — includes a Nigerian-language eval spike.
- [Phase 5] INT-03 controls must be the first plan in Phase 5; do not defer to Phase 6 hardening.

## Session Continuity

Last session: 2026-08-01T16:10:11.055Z
Stopped at: Phase 05-01 (AI Orchestrator) implemented — middleware, service, ledger, config, router wiring, tests all green (go build + go vet clean; middleware/services/models/config/ai/modules-ai suites pass)
Resume file: .planning/phases/05-go-integration-orchestrator/05-01-PLAN.md
