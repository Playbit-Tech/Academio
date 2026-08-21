# Deferred Items — Phase 06 Plan 01 (observability/metrics)

Out-of-scope pre-existing issues discovered during execution of 06-01. Not
caused by this plan's changes and left unfixed per the GSD scope boundary rule.

## Pre-existing golangci-lint failures (would fail `golangci-lint run ./...`)

These existed on the backend `dev` branch before 06-01 and are unrelated to the
metrics/request_id/dashboard work in this plan. Confirmed untouched by 06-01
(via `git diff HEAD` empty for every file below). A future hardening task
should resolve them.

| File | Linter | Finding |
|------|--------|---------|
| `backend/internal/services/ai_orchestrator_service_test.go` | contextcheck | `newTestOrchestrator -> testRedisClient` should pass context |
| `backend/internal/services/ai_orchestrator_service_test.go` | errcheck | unchecked `_ = svc.RecordUsage(...)` return values (2 sites) |
| `backend/internal/services/ai_orchestrator_service_test.go` | gosimple (S1024) | prefer `time.Until` over `deadline.Sub(time.Now())` (2 sites) |
| `backend/internal/ai/engine/python_provider.go` | staticcheck (SA5011) | possible nil deref `req.Prompt` (lines 116, 143) — pattern guarded by `req != nil` below already |
| `backend/internal/ai/providers_status.go` | gofmt | file not formatted |

Additional pre-existing `gofmt -l` unformatted files (not modified by 06-01):
`backend/internal/ai/config.go`, `backend/internal/ai/engine/client.go`,
`backend/internal/ai/providers_status.go`.

### Recommendation
These should be fixed in a dedicated lint-hardening task (collect the 
errcheck/contextcheck/gosimple/gofmt cleanups together) rather than mixed into
observability work.

## Deferred by design: Python→LLM request_id header propagation

The Go→Python `X-Request-ID` seam is already sent by the Go `EngineClient`
(`RequestIDHeader` in `backend/internal/ai/engine/engine.go`). Python-side
provider clients (`AsyncAnthropic`/`AsyncOpenAI`) are module-level singletons
in `ai-engine/app/providers/`, so per-request `X-Request-ID` headers on the
Python→LLM leg would require per-request client construction (an architectural
change). Plan 06-01 scopes Python work to the log side (D-02: JSON logs carry
request_id), so LLM-call header propagation is recorded here for a future
plan.