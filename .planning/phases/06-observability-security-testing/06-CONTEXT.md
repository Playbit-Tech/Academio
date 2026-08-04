# Task Context: Phase 6 — Observability, Security & Testing

Phase: 06-observability-security-testing
Status: planning
Created: 2026-08-04 (after Phase 5 verified PASSED)

## Goal

The platform is provably observable, PII-safe, and tenant-isolated — the RAG eval harness and cross-tenant probe suite in CI prove what earlier phases built.

## Requirements (from REQUIREMENTS.md)

- **OBS-01**: Prometheus metrics + JSON logs + `X-Request-ID` correlation across Go→Python; token usage/cost/latency/cache metrics; Grafana dashboard
- **SEC-01**: PII masking, AI config encryption, audit every AI request, rate limit AI endpoints, tenant isolation, input validation; Python validates `schema_name` `^school_\d+$` on every query; shared uploads volume
- **TES-01**: Go + pytest test suites (unit, integration, AI-pipeline, embedding, RAG-accuracy, security, load, concurrency); RAG evaluation harness ships WITH pipeline; cross-tenant probe suite in CI

## ROADMAP Success Criteria (what must be TRUE)

1. Prometheus metrics (tokens, cost, latency, cache hits, provider/model per request) and JSON logs carry `X-Request-ID` end-to-end across Go → Python; a Grafana visualization shows pipeline health, fallback rate, and cost-per-successful-task.
2. PII masking is enforced (document contents and prompt bodies never appear in logs — sizes/hashes only); AI config secrets are encrypted at rest; every AI request is audited; all inputs validated; Python's `^school_\d+$` schema check runs on every query with no fallback.
3. The RAG evaluation harness ships and runs in CI on every chunking/embedding/prompt change: golden set of 50-100 school-realistic QA pairs (collected from Phase 4's pipeline corpus), gating faithfulness ≥0.85 and context precision ≥0.75.
4. The cross-tenant probe suite runs in CI on every deploy: canary chunks per tenant, adversarial queries across every retrieval entry point (search, cache, reranking, agent tools, worker paths) assert ZERO cross-tenant hits; the kill-worker-mid-pipeline test asserts zero duplicate vectors and exactly one notification; load/concurrency tests pass at 10× expected peak.

## Decisions (locked this discussion — all gray areas delegated to agent, recorded below)

### Observability (OBS-01)
- **D-01:** Extend the EXISTING `backend/internal/ai/metrics.go` promauto registry (do NOT create a second registry). Add metric families beyond the current 5 (requests, duration, tokens, cost, errors): `ai_cache_hits_total` (label: hit/miss), `ai_fallback_total` (label: from_provider, to_provider), `ai_cost_per_task` histogram, `ai_quota_rejections_total` (label: school_id). `/metrics` endpoint already wired at `router.go:119` — keep it.
- **D-02:** JSON logs carry `X-Request-ID` end-to-end. Go uses slog JSON handler (already in `pkg/logger`); ensure the request-id middleware injects `request_id` into every log line. Python engine adds a `request_id` field to its JSON logs (structlog or stdlib logging with a JSON formatter) and echoes the `X-Request-ID` header it receives from Go. Correlation key is the request_id string, propagated via the existing `EngineTokenHeader`/`RequestIDHeader` seam.
- **D-03:** Grafana dashboard ships as a JSON provisioning file in `backend/monitoring/grafana/` (dashboards dir already exists). One dashboard: "AI Pipeline Health" showing request rate, latency p95, token/cost totals, fallback rate, cache hit ratio, cost-per-successful-task. Provisioned via the existing compose grafana service (datasource = prometheus). No admin UI work in this phase beyond the dashboard + quota/spend panels (see D-09).

### Security (SEC-01)
- **D-04:** PII masking boundary: document contents and prompt bodies NEVER appear in logs (Go or Python) — log sizes/hashes only. This is enforced at the log layer: any log call that would include document text or prompt text is replaced with `{len: N, sha256: <hash>}`. Error messages returned to clients are sanitized (Python already has `_sanitize_error_message`; Go must not echo raw provider/doc content in `response.Error`). Student/teacher names, emails, phones are NOT logged in AI request/response paths (they may appear in non-AI audit logs per B11, but AI observability logs are content-free).
- **D-05:** AI config secrets encrypted at rest using the EXISTING `backend/internal/crypto/encryption.go` AES-256-GCM `Service` (with `ENCRYPTION_KEY`). Scope: any AI provider secret persisted to the DB (e.g., per-school provider API keys if/when stored) is encrypted before write and decrypted at read. The Python engine's provider keys (anthropic, deepseek, openrouter, azure-openai, ollama) remain env-injected container secrets (never committed, never logged) — they are NOT stored in the DB in v1, so no DB encryption needed for them; instead add startup validation that they are present when the corresponding provider is enabled, and fail-fast (B12) if a required key is missing. `AI_ENGINE_TOKEN` stays env-only, never logged.
- **D-06:** Every AI request is audited (B11 already covers this via `AuditLogger` + handler-level audit on the `ai` route group from Phase 5). Confirm the audit event includes SchoolID, UserID, Action, ResourceType, RequestID for ALL AI endpoints including the new providers-status and streaming paths. Input validation: all AI request bodies validated (existing DTO binding); Python `^school_\d+$` schema check runs on every query with NO fallback (already implemented in `_school_header` — add a test asserting no fallback path exists). Shared uploads volume containment already enforced (Phase 4 `_assert_within_uploads`).

### Testing (TES-01)
- **D-07:** RAG eval harness lives in `ai-engine/tests/rag_eval/` as a pytest suite. Golden set: 50-100 school-realistic QA pairs stored as JSONL (`ai-engine/tests/rag_eval/golden.jsonl`), each `{question, expected_sources: [doc_ids], expected_answer_fragments}`. Metrics: **context precision** computed deterministically (fraction of expected_sources present in retrieved context — no LLM needed); **faithfulness** via LLM-as-judge using a configured judge provider (skip-if-no-key, gated in CI with a stub judge for hermetic runs). Gates: faithfulness ≥0.85, context precision ≥0.75. Runs in CI on every change to `ai-engine/app/prompts/`, `ai-engine/app/documents/chunker.py`, `ai-engine/app/documents/embedder.py`, `ai-engine/app/db/vectors.py` (new `rag-eval.yml` workflow).
- **D-08:** Cross-tenant probe suite: hermetic, seeded tenants `school_1`/`school_2` in CI (pgvector DB available via `AI_PGVECTOR_DSN`). Adversarial queries across every retrieval entry point — Go search, Go cache (assert tenant-scoped keys never cross), reranking, agent tools, worker paths, and Python search/extract — assert ZERO cross-tenant hits. Go side: new `backend/internal/security/probes` test package run in CI (new workflow or extended `ci.yml`). Python side: pytest gated on `AI_PGVECTOR_DSN` (pattern already in `test_search.py`). The kill-worker-mid-pipeline test lives in Go (asynq worker) asserting zero duplicate vectors and exactly one notification (extends Phase 4's doc-ingest worker tests). Load/concurrency via the existing k6 `load-test.yml` at 10× expected peak.

### Phase 5 review hardening (carried into this phase)
- **D-09:** Fold in the Phase 5 review findings that are in-scope for hardening: MA-01 (per-request cost cap dead code — `CheckQuota` called with `maxTokensEstimate=0`; wire the token-budget estimate from `opts.MaxTokens`), MA-02 (ChatStream non-200 not classified into `*StatusError` — fix so streaming path gets D-14 error classification), MA-03 (pythonProvider drops Temperature/MaxTokens — pass them through). These are hardening fixes, not new capabilities. Also add `ai_usage_log` retention/pruning (D-09 from Phase 5) — a simple retention policy (e.g., configurable retention window, default keep-all in v1, prune job deferred) and the quota/spend Grafana panels (D-05/D-07 from Phase 5).

## Agent's Discretion (explicitly delegated this discussion)
- Exact metric names/labels for the new promauto families (D-01)
- Exact JSON log field names for request_id correlation (D-02)
- Whether faithfulness judge uses a specific provider or a stub in CI (D-07 — recommend stub for hermetic CI, real judge for nightly)
- Exact probe test file layout in `backend/internal/security/probes` (D-08)
- Retention window default for `ai_usage_log` (D-09 — recommend keep-all in v1, configurable)

## Existing State (verified this session)

### Observability (already present — EXTEND, do NOT rewrite)
- `backend/internal/ai/metrics.go`: promauto registry with `AIRequestsTotal`, `AIRequestDurationSeconds`, `AITokensTotal`, `AICostTotal`, `AIErrorsTotal` (5 families)
- `backend/internal/router/router.go:119`: `r.GET("/metrics", gin.WrapH(promhttp.Handler()))` — already wired
- `backend/monitoring/prometheus.yml` + `backend/monitoring/grafana/` — compose services `prometheus` + `grafana` already declared in `backend/docker-compose.yml`
- `backend/pkg/logger` — slog wrapper (Infof/Warnf/Errorf/Fatalf)
- `backend/internal/middleware/requestid.go` — X-Request-ID middleware (uses `internal/contextkeys.RequestID`)

### Security (already present — EXTEND)
- `backend/internal/crypto/encryption.go`: AES-256-GCM `Service` with `Encrypt(plaintext, aad)` / `Decrypt(ciphertextB64, aad)`; `NewService(encryptionKey)`; tests `encryption_test.go`, `security_test.go`
- `backend/internal/middleware/audit.go`: `AuditLogger` + `LogMutation` (B11)
- Python `ai-engine/app/security.py`: `require_token` (X-AI-Engine-Token); `ai-engine/app/api/extract.py`: `_school_header(x_school_schema)` validates `^school_\d+$`, `_assert_within_uploads` containment
- `backend/internal/config/config.go`: `AI.Enabled`, `AI.EngineURL`, `AI.EngineToken` with fail-fast validation

### Testing (already present — EXTEND)
- Python: `ai-engine/tests/` — 17 files incl. `test_search.py` (DB-gated via `AI_PGVECTOR_DSN` pattern), `test_hybrid.py`, `test_schema.py`, `test_sse.py`, `test_providers.py`
- Go: `backend/internal/modules/ai/` tests (stream_test.go, providers_test.go), `backend/internal/services/ai_orchestrator_service_test.go`, `backend/internal/middleware/` tests
- CI: `.github/workflows/ai-engine.yml`, `docs.yml`; `backend/.github/workflows/ci.yml`, `deploy.yml`, `load-test.yml` (k6)

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Observability (read before extending)
- `backend/internal/ai/metrics.go` — existing promauto registry to extend (D-01)
- `backend/internal/router/router.go` — /metrics endpoint wiring (line 119)
- `backend/monitoring/prometheus.yml` + `backend/monitoring/grafana/` — compose + dashboard provisioning (D-03)
- `backend/pkg/logger` — slog wrapper for JSON logs (D-02)
- `backend/internal/middleware/requestid.go` + `backend/internal/contextkeys/contextkeys.go` — request_id correlation (D-02)

### Security (read before extending)
- `backend/internal/crypto/encryption.go` — AES-256-GCM Service to reuse (D-05)
- `backend/internal/middleware/audit.go` — AuditLogger (D-06)
- `ai-engine/app/security.py`, `ai-engine/app/api/extract.py` — token + schema validation + containment (D-06)
- `backend/internal/config/config.go` — AI config validation (D-05)

### Testing (read before extending)
- `ai-engine/tests/test_search.py` — DB-gated pytest pattern to reuse (D-08)
- `backend/internal/modules/ai/stream_test.go`, `providers_test.go` — Go AI test patterns
- `backend/.github/workflows/load-test.yml` — k6 load test to extend (D-08)
- `backend/internal/queue/worker.go` + `backend/internal/queue/tasks.go` — asynq worker for kill-worker-mid-pipeline test (D-08)

### Phase 5 review findings (read before hardening)
- `.planning/phases/05-go-integration-orchestrator/05-REVIEW.md` — MA-01/MA-02/MA-03 hardening items (D-09)

### No external specs
- No external specs — requirements fully captured in decisions above.

## Deferred Ideas

- Per-school quota override admin UI (Phase 5 deferred; still not in this phase's scope — Grafana panels + config default only)
- Plan-tier-based AI rate limits (D-03 Phase 5 — flat in v1)
- Cache invalidation on document re-ingest (post-Phase 5; TTL-based in v1)
- Real LLM-judge faithfulness in CI (D-07 recommends stub for hermetic CI, real judge nightly — nightly judge deferred to Phase 7 ops)
- `ai_usage_log` retention pruning job (D-09 — keep-all default in v1, prune job deferred)

## Exit Criteria

- [ ] All 4 ROADMAP success criteria demonstrated (metrics + request_id correlation + Grafana; PII masking + config encryption + audit + schema check; RAG eval harness gating ≥0.85/≥0.75 in CI; cross-tenant probes + kill-worker test + 10× load in CI)
- [ ] OBS-01, SEC-01, TES-01 checked in REQUIREMENTS.md
- [ ] Go suite passes (all tests incl. new metrics/crypto/probes tests); ruff/pyright clean for any Python touch; pytest suite passes
- [ ] Phase 6 VERIFICATION passed (verifier agent), STATE.md/ROADMAP.md updated