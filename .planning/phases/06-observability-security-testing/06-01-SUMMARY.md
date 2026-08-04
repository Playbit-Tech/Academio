---
phase: 06-observability-security-testing
plan: 01
subsystem: observability
tags: [prometheus, promauto, slog, request-id, grafana, json-logs, fastapi, python-logging]

# Dependency graph
requires:
  - phase: 05-go-integration-orchestrator
    provides: AI Orchestrator service (quota/cache/ledger), ModelRouter provider failover, EngineClient X-Request-ID seam
provides:
  - Extended promauto AI metric families (cache hits, fallbacks, cost/task, quota rejections)
  - request_id injected into every Go slog JSON log line via context handler
  - Python engine JSON logging + request_id middleware (X-Request-ID echo)
  - Grafana "AI Pipeline Health" dashboard provisioning (7 panels) + datasource uid
affects: 06-02, 06-03, 06-04, Phase 7 ops (dashboard tuning, Python→LLM header propagation)

# Tech tracking
tech-stack:
  added: [grafana dashboard provisioning JSON, python stdlib JSON log formatter + contextvars]
  patterns:
    - "slog contextHandler wrapper injecting request_id from contextkeys.RequestID"
    - "contextvar-based per-request log correlation in FastAPI middleware"
    - "recordFallback helper: failover metric incremented at the ModelRouter decision site"

key-files:
  created:
    - backend/monitoring/grafana/ai-pipeline-health.json
    - backend/monitoring/grafana/dashboards/ai-pipeline-health.json
  modified:
    - backend/internal/ai/metrics.go
    - backend/internal/services/ai_orchestrator_service.go
    - backend/internal/ai/gateway.go
    - backend/internal/ai/model_router.go
    - backend/pkg/logger/logger.go
    - backend/monitoring/grafana/datasources/datasource.yml
    - ai-engine/app/main.py

key-decisions:
  - "Golint comments for the 4 new metric families are placed inline on the declaration line so the plan's hard verification grep -c == 4 holds (each family name on exactly one line); golangci-lint has no comment-style linter"
  - "AIFallbackTotal is recorded at the genuine D-14 failover sites in model_router.go via a recordFallback helper in gateway.go (python_provider.go cannot import internal/ai — package cycle); the from/to labels come from the known ProviderType enumerations"
  - "pkg/logger gains a contextHandler wrapper (not a middleware) so request_id flows into every slog line from the request context; WithContext fixed to read the typed contextkeys.RequestID key (the plain-string lookup never matched the middleware's typed key)"
  - "Grafana dashboard JSON shipped at the plan path AND an identical copy in dashboards/ because compose mounts only ./monitoring/grafana/dashboards; datasource.yml gets explicit uid: prometheus so panel refs resolve"

patterns-established:
  - "Pattern: slog context handler in pkg/logger for automatic request_id injection on every JSON log line"
  - "Pattern: FastAPI http middleware + contextvar for per-request request_id in stdlib logging JSON formatter"
  - "Pattern: metric recording at decision sites (quota rejection before error return, failover on successful fallback)"

requirements-completed: [OBS-01]

# Metrics
duration: 17min
completed: 2026-08-04
---

# Phase 06 Plan 01: Observability Metrics Summary

**Extended promauto AI metrics (cache hits/fallbacks/cost-per-task/quota rejections), request_id injected into every Go slog JSON line and Python JSON logs via a FastAPI contextvar middleware, and a provisioned 7-panel Grafana "AI Pipeline Health" dashboard**

## Performance

- **Duration:** 17 min
- **Started:** 2026-08-04T07:47:08Z
- **Completed:** 2026-08-04T08:04:19Z
- **Tasks:** 4/4
- **Files modified:** 14 (8 backend + 1 ai-engine + 5 root)

## Accomplishments

- Extended the existing promauto registry in `backend/internal/ai/metrics.go` with 4 new families: `ai_cache_hits_total{hit}`, `ai_fallback_total{from_provider,to_provider}`, `ai_cost_per_task_usd{provider}` histogram (0.001–5 USD buckets), `ai_quota_rejections_total{school_id}` — the existing 5 families untouched, `/metrics` endpoint (router.go:119) serves the extended registry via the same promhttp handler.
- Wired metrics at the correct call sites: `AIQuotaRejectionsTotal` incremented before returning `ErrQuotaExceeded`/`ErrRequestCostExceeded` in `CheckQuota`; `AICacheHitsTotal` hit/miss in `GetCache`; `AICostPerTask` observed in `RecordUsage` (costCents/100); `AIFallbackTotal` recorded at the real D-14 failover sites in `ModelRouter.GenerateText`/`GenerateTextStream` via a `recordFallback` helper.
- Go `pkg/logger` now wraps every JSON handler in a `contextHandler` that injects `request_id` from the request context (typed `contextkeys.RequestID` key) into every log line; `WithContext` fixed to actually find the middleware-stored ID (previously read a mismatched plain-string key); 8 new `*Context` helpers added for request-scoped logging.
- Python engine (`ai-engine/app/main.py`) now emits single-line JSON logs with a `request_id` field driven by a contextvar, set by a FastAPI http middleware that reads `X-Request-ID` (uuid4 hex fallback), resets the context after the request and echoes the header back on the response. PII-safe: no doc/prompt bodies (D-04).
- Shipped Grafana provisioning: `ai-pipeline-health.json` (7 panels: Request Rate, Latency p95, Token Usage, Cost per Task, Fallback Rate, Cache Hit Ratio, Quota Rejections), an identical copy under `dashboards/` matching the compose volume mount, and an explicit `uid: prometheus` on the datasource so panel references resolve.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Prometheus metrics registry** - `0c7c7a5` (feat)
2. **Task 2: Wire metrics into orchestrator and engine paths** - `433fc80` (feat)
3. **Task 3: request_id correlation in Go and Python JSON logs** - `867c913` (feat, Go) + `2286273` (feat, root repo — ai-engine/app/main.py)
4. **Task 4: Grafana dashboard provisioning** - `fb4f31d` (feat)

**Plan metadata:** `state-update` (docs: complete 06-01 plan — root commit)

All backend commits on `dev`, pushed to `origin/dev` (`1fadf5e..fb4f31d`). Root repo commit on `main` includes the ai-engine change, the backend submodule gitlink bump, STATE/ROADMAP/REQUIREMENTS updates and this SUMMARY.

## Files Created/Modified

Backend submodule (`github.com/Playbits/Academio-Be`, branch `dev`):
- `backend/internal/ai/metrics.go` - 4 new promauto families (OBS-01 D-01)
- `backend/internal/services/ai_orchestrator_service.go` - quota-rejection/cache/cost-per-task recording
- `backend/internal/ai/gateway.go` - `recordFallback` helper (AIFallbackTotal)
- `backend/internal/ai/model_router.go` - failover metric at D-14 decision sites (GenerateText + Stream)
- `backend/pkg/logger/logger.go` - contextHandler + requestIDFromContext + context-aware helpers
- `backend/monitoring/grafana/ai-pipeline-health.json` - canonical dashboard (new)
- `backend/monitoring/grafana/dashboards/ai-pipeline-health.json` - provisioned copy (new)
- `backend/monitoring/grafana/datasources/datasource.yml` - explicit `uid: prometheus`

ai-engine (root repo, `main`):
- `ai-engine/app/main.py` - JSON logging + request_id contextvar middleware

Root:
- `.planning/phases/06-observability-security-testing/06-01-SUMMARY.md` - this summary (new)
- `.planning/phases/06-observability-security-testing/deferred-items.md` - out-of-scope pre-existing lint findings (new, gitignored)
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` - plan/requirement state
- `backend` - submodule gitlink bump to fb4f31d

## Decisions Made

- **Inline golint comments for new metric families**: the plan requires both golint-format comments ("name starts with the metric name") AND the hard verification `grep -c ... == 4` (each name on exactly one line). Separate comment lines would make the count 8, so comments are placed inline on each declaration line. golangci-lint's enabled linters contain no comment-style rule, so CI is unaffected.
- **`recordFallback` in gateway.go instead of python_provider.go**: the plan's Task 2 named `backend/internal/ai/engine/python_provider.go` as the fallback site, but that package (`engine`) cannot import `internal/ai` (import cycle with the adapter). The genuine D-14 failover decision lives in `model_router.go` (package ai). The helper lives in gateway.go (package ai) and is called from both `ModelRouter` failover loops — satisfying the acceptance grep (`AIFallbackTotal.*Inc` in gateway.go) with correct behavior.
- **Context handler (not middleware) in pkg/logger**: a slog `contextHandler` wrapper injects `request_id` from the record context at the handler boundary, so any log call that receives the request context (via `WithContext(ctx)` or the new `*Context` helpers) is correlated. The old `WithContext` read a plain-string key that never matched the middleware's typed `contextKey` storage — fixed to read `contextkeys.RequestID` (which the middleware also stores).
- **Dashboard JSON in two locations**: compose mounts only `./monitoring/grafana/dashboards`, so the dashboard is shipped both at the plan's canonical path (acceptance `test -f`) and as an identical copy in `dashboards/` for real provisioning. `uid: prometheus` added to the datasource because Grafana otherwise auto-generates a uid that would break the dashboard's datasource references.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Token Usage panel grouped by non-existent label**
- **Found during:** Task 4 (Grafana dashboard provisioning)
- **Issue:** Plan's PromQL `rate(ai_tokens_total[5m]) by (type)` references a label `type` that does not exist — the family is `ai_tokens_total{provider, token_type}`. `by (type)` silently returns ungrouped series.
- **Fix:** Group by the actual label: `rate(ai_tokens_total[5m]) by (token_type)`.
- **Files modified:** backend/monitoring/grafana/ai-pipeline-health.json (+ copy)
- **Verification:** JSON valid; PromQL matches metric schema
- **Committed in:** fb4f31d (Task 4 commit)

**2. [Rule 2 - Missing Critical] Datasource uid for dashboard provisioning**
- **Found during:** Task 4 (Grafana dashboard provisioning)
- **Issue:** `datasource.yml` had no `uid`, so Grafana auto-generates one; the dashboard's panels reference `{"type":"prometheus","uid":"prometheus"}` and would show "datasource not found" in a provisioned install.
- **Fix:** Added explicit `uid: prometheus` to the datasource provisioning.
- **Files modified:** backend/monitoring/grafana/datasources/datasource.yml
- **Verification:** Provisioning refs now resolve; datasource yaml still valid
- **Committed in:** fb4f31d (Task 4 commit)

**3. [Rule 3 - Blocking] Detached HEAD in backend submodule**
- **Found during:** Task 1 commit
- **Issue:** The backend submodule was checked out on a detached HEAD at `64a6f0b` (dev tip); my commit landed on a detached commit, which the root submodule gitlink could not track cleanly and would be lost on checkout.
- **Fix:** Checked out `dev`, fast-forwarded it to include the commit, continued all subsequent commits on `dev`, pushed to `origin/dev`.
- **Files modified:** none (git branch state)
- **Verification:** `git log --oneline dev -4` shows the full 06-01 chain
- **Committed in:** n/a (branch hygiene)

---

**Total deviations:** 3 auto-fixed (1 bug, 1 missing critical, 1 blocking)
**Impact on plan:** All fixes required for correctness/provisioning. No scope creep.

## Issues Encountered

- Pre-existing golangci-lint failures surfaced while verifying my changes (`contextcheck`/`errcheck`/`gosimple` in `ai_orchestrator_service_test.go`, `SA5011` in `python_provider.go`, `gofmt` in `providers_status.go`/`config.go`/`client.go`). All are in files 06-01 did not touch — confirmed via `git diff HEAD` empty — and are logged to `deferred-items.md` per the scope boundary rule (left unfixed, recommended for a dedicated lint-hardening task).
- `pkg/logger.WithContext` never actually attached `request_id`: the middleware stores the ID under typed keys (`contextkeys.RequestID`, `middleware.contextKey`) while the old code read `ctx.Value("request_id")` with a plain string key — Go context keys match on type AND value, so the lookup always failed. Fixed by reading the typed key.

## User Setup Required

None - no external service configuration required. (Grafana datasource/dashboard provisioning ships in-repo and is picked up by the existing compose grafana service mount.)

## Next Phase Readiness

- 06-02 (security) can build on the same metrics/logger patterns; `contextHandler` and the `*Context` log helpers are available for any request-scoped security logging.
- The Grafana dashboard will populate once the API is scraped by Prometheus (compose `prometheus` service already scrapes `api:8080/metrics`).
- Python→LLM `X-Request-ID` header propagation deferred by design (provider clients are module singletons; per-request headers need client lifecycle changes) — tracked in deferred-items.md for a future plan.

## Self-Check: PASSED

All 9 created/modified files verified present on disk; all 4 backend commits
(`0c7c7a5`, `433fc80`, `867c913`, `fb4f31d`) and the root commit (`2286273`)
verified in git history.

---

*Phase: 06-observability-security-testing*
*Completed: 2026-08-04*
