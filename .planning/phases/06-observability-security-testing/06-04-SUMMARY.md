---
phase: 06-observability-security-testing
plan: 04
subsystem: security
tags: [cross-tenant, probes, cost-cap, failover, status-error, streaming, k6, ci, pgvector, testcontainers, max-tokens, temperature]

# Dependency graph
requires:
  - phase: 02-pgvector-migration
    provides: per-tenant ai_vectors table, vector(1536) contract, schema-qualified tenant access
  - phase: 03-python-ai-engine
    provides: /v1/chat, /v1/search, /v1/documents (extract), X-School-Schema gating, embedding/chat providers
  - phase: 06-01
    provides: AI pipeline health, pgvector DSN config, CI patterns for AI engine
  - phase: 06-03
    provides: rag-eval workflow (.github/workflows/rag-eval.yml), DB-gated pytest pattern, school_1 provisioning step
provides:
  - "Go-side adversarial cross-tenant probe suite (security/probes, -tags=integration) proving search/tool/doc-ingest-worker isolation on real testcontainers pgvector + Redis"
  - "Python-side cross-tenant probe suite (test_cross_tenant.py) hitting REAL ASGI /v1/search + /v1/documents with marker-chunk seeding in school_1 + school_2"
  - "MA-01: request-level cost caps — CheckQuota pre-flight on Chat (max_tokens) and Search (token estimate + margin) → 429 with Retry-After"
  - "MA-02: ChatStream non-200 responses now wrap *StatusError{StatusCode,Body} so D-14 classification (429→failover, 5xx→retry, 4xx→permanent) reaches the relay; SSE in-band error event carries status_code"
  - "MA-03: temperature/max_tokens passthrough from Go API → engine → Python providers (openai/anthropic/ollama) with nil-omission"
  - "PIP-01: kill-worker crash-safety test proving asynq re-delivery after 'ready' produces zero duplicate vectors + exactly one notification"
  - "CI: integration-tests job covers ./internal/security/... ./internal/queue/... with redis service; rag-eval workflow provisions school_2 and runs cross-tenant probes"
  - "k6 ai-10x soak script + workflow job (50 req/s, 2 min, workflow_dispatch only)"
affects: [future billing/quotas, streaming UI error surfacing, model router failover tuning]

# Tech tracking
tech-stack:
  added: [testcontainers-go in security/probes, datatypes.JSON in probe seed, redis service container in CI integration-tests, k6-ai-10x workflow job]
  patterns: [school-row-before-provisioning parity, DB-gated pytest skip, pointer-field nil omission, kwargs-dict over inline conditional unpack, in-band SSE error event]

key-files:
  created:
    - backend/internal/security/probes/doc.go
    - backend/internal/security/probes/probes_test.go
    - backend/internal/queue/handlers/kill_worker_test.go
    - backend/scripts/k6/ai-10x.js
    - ai-engine/tests/test_cross_tenant.py
  modified:
    - backend/internal/ai/engine/client.go
    - backend/internal/ai/engine/client_test.go
    - backend/internal/ai/engine/engine.go
    - backend/internal/ai/engine/python_provider.go
    - backend/internal/ai/engine/python_provider_test.go
    - backend/internal/modules/ai/handler.go
    - backend/internal/modules/ai/stream.go
    - backend/internal/modules/ai/stream_test.go
    - backend/internal/middleware/ai_orchestrator.go
    - backend/internal/queue/handlers/doc_ingest_handler.go
    - backend/.github/workflows/ci.yml
    - backend/.github/workflows/load-test.yml
    - .github/workflows/rag-eval.yml
    - ai-engine/app/api/chat.py
    - ai-engine/app/providers/base.py
    - ai-engine/app/providers/openai_compat.py
    - ai-engine/app/providers/anthropic_provider.py
    - ai-engine/app/providers/ollama_provider.py
    - ai-engine/tests/test_chat.py
    - backend/scripts/k6/README.md

key-decisions:
  - "Probe env seeds School rows in the public schema BEFORE ProvisionSchool — production creates the school first (modules/school/service.go:210) then provisions; omitting it made tenant seeds fail with fk_levels_schools (SQLSTATE 23503), and a missing school_type broke NOT NULL (23502). Parity with the production call order is what makes the probes honest"
  - "ChatStream non-200 wraps *StatusError with the response body (mirroring Chat), so the D-14 classification survives the Go boundary — a bare fmt.Errorf with only the status code killed classification and left the relay unable to surface the provider's reason"
  - "In-band SSE error event now carries status_code alongside message (payload map gains the key only when errors.As matches *StatusError) — non-StatusError shape unchanged so existing drainer test semantics hold"
  - "temperature/max_tokens are pointer fields with json omitempty: nil → omitted from the engine JSON, keeping old requests byte-identical; Python side uses kwargs-dict (create(**kwargs)) instead of inline conditional **{...} unpacking because the inline form failed pyright against OpenAI SDK overloads (65 errors)"
  - "CI integration-tests gained a redis service container (matches endpoint-tests) so the Redis-gated doc-ingest/asynq tests actually run in CI instead of silently skipping"
  - "rag-eval workflow provisions school_2 alongside school_1 (loop over both schemas) — test_cross_tenant requires BOTH, otherwise it skips and the adversarial pair never runs"
  - "k6-ai-10x is workflow_dispatch-only (stress/soak, never PR) mirroring the k6-stress-test gate; PyYAML safe_load still reports a pre-existing embedded-Python parse quirk at load-test.yml:118 which the GitHub Actions parser tolerates"

patterns-established:
  - "School-row-before-provisioning: any test that provisions a tenant schema must create the school row first, exactly as the production service does"
  - "DB-gated skip with explicit reason: probes skip when Docker/testcontainers is unavailable; Python cross-tenant skips unless AI_PGVECTOR_DSN AND both tenant schemas exist"
  - "Pointer-field nil omission for optional API params — backward-compatible JSON contract"
  - "In-band SSE terminal error with status code: relay never fails the stream, never switches provider after first byte (D-16), emits error + done"
  - "kwargs-dict construction over conditional dict-unpacking for typed SDK call sites"

# Verification evidence
verification:
  backend:
    - go build ./... (exit 0)
    - go vet ./... + go vet -tags=integration (exit 0)
    - go test ./internal/ai/engine/ ./internal/modules/ai/ ./internal/queue/handlers/ ./internal/security/ -count=1 (ok)
    - go test ./internal/security/probes/ -tags=integration (ok against real testcontainers pgvector + redis)
    - go test ./internal/queue/handlers/ -count=1 incl TestKillWorkerMidPipeline, TestDocIngestHandler_ReadyStatusSkipsReingest, TestDocIngestHandler_ExtractingStatusResumes (all pass)
  ai-engine:
    - ruff check . (clean), pyright (0 errors)
    - pytest tests/test_cross_tenant.py → 1 passed, 2 skipped (school_2 absent locally; provisioned in CI)
    - pytest tests/test_chat.py → 9 passed; full suite 122 passed / 17 skipped
  ci:
    - YAML parse clean for ci.yml and rag-eval.yml
    - grep acceptance criteria for internal/security, internal/queue, -tags=integration, test_cross_tenant all satisfied

known-limitations:
  - "Cross-tenant Python suite's two DB-gated tests skip locally (no school_2 schema); CI provisions both schemas so they run on deploy"
  - "load-test.yml PyYAML safe_load failure at line 118 is pre-existing (embedded Python in run block); GitHub Actions parses it fine — noted, not fixed"
