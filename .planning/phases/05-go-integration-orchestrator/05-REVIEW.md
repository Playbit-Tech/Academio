---
status: findings
phase: 05-go-integration-orchestrator
reviewed_at: 2026-08-02T00:00:00Z
findings:
  critical: 1
  major: 4
  minor: 5
  total: 10
---

# Phase 05 Code Review: Go Integration Orchestrator

**Scope:** AI provider abstraction (`backend/internal/ai/`), AI engine seam
(`backend/internal/ai/engine/`), AI orchestrator service + middleware
(`backend/internal/services/ai_orchestrator_service.go`,
`backend/internal/middleware/ai_orchestrator.go`), AI module handlers
(`backend/internal/modules/ai/`), router wiring, config, tenant schema
isolation, and the `ai_usage_log` ledger (D-08).

**Method:** Full file reads, cross-reference of the multi-tenant schema
plugin (`SchemaTablePrefix`), trace of the request context through
`TenantDBResolver` → `RecordUsage` → ledger write, and verification of the
rate-limit key construction and circuit-breaker fallback paths.

## Findings

| # | Severity | File | Issue | Recommendation |
|---|----------|------|-------|----------------|
| CR-01 | critical | `backend/internal/services/ai_orchestrator_service.go:217-221` | `aiUsageLogRepository.Create` uses `r.db.WithContext(ctx)` where `ctx` is the request context carrying the tenant schema (injected by `TenantDBResolver` via `tenant.InjectSchemaToContext`). The `SchemaTablePrefix` plugin (registered on the same shared core DB in `setup.go:197`) reads the schema from `db.Statement.Context` and will rewrite the ledger INSERT to `school_{id}.ai_usage_log`, which does not exist (the ledger table lives only in the public schema). Every ledger write fails, silently (handler logs best-effort and continues), so D-08's `SUM(cost_cents) == Redis counter` invariant is broken and audit/quota data is lost. | Strip the tenant schema from the context before the ledger write, e.g. `r.db.WithContext(tenant.ClearSchemaContext(ctx)).Create(entry)` — the `ClearSchemaContext` helper already exists in `schema_db.go:203` and is exactly designed for shared-public-schema writes. |
| MA-01 | major | `backend/internal/middleware/ai_orchestrator.go:165-169` | Per-request cost cap (D-06) is dead code: the only `CheckQuota` caller passes `maxTokensEstimate=0`, so `CalculateCost(0,0)=0` and `ErrRequestCostExceeded` can never be returned. The comment claims "the handler-level wrapper enforces the exact MaxRequestCents" but no such wrapper exists anywhere. | Either implement the enforcement where token counts are known (the module handler after the response), or remove `MaxRequestCents`/`ErrRequestCostExceeded` and the middleware branch handling it. |
| MA-02 | major | `backend/internal/ai/engine/client.go:91-93` | `ChatStream` does not classify non-200 responses into `*engine.StatusError` (unlike `Chat`/`Embed`/`GetProvidersStatus`), and it discards the response body. This breaks the D-14 error-classification contract (429→failover / 5xx→retry / 4xx→permanent) for the streaming path — the python provider and the adapter cannot `errors.As` a `*StatusError` from a stream failure, so stream failover decisions (D-16) cannot distinguish transient vs permanent errors. | Mirror the `Chat` path: read the body, wrap non-200s in `&StatusError{StatusCode: ..., Body: ...}` (optionally redacted), and have `pythonProvider.GenerateTextStream` return it wrapped so `errors.As` works. |
| MA-03 | major | `backend/internal/ai/gateway.go:269-274, 330-334` | The python provider adapter drops `opts.Temperature` and `opts.MaxTokens` — `engine.ProviderOptions` has no such fields, and `engine.ChatRequest`/`pythonProvider` never forward them. Native Gemini/OpenAI providers honor both (gemini.go:53-59, openai.go:53-59). The module passes `Temperature` (stream.go:126) but it silently has no effect on python-backed models. | Add `Temperature`/`MaxTokens` to `engine.ChatRequest` and map `opts.Temperature`/`opts.MaxTokens` into `engine.ProviderOptions` in the adapter; forward to the Python `ChatRequest`. |
| MA-04 | major | `backend/internal/ai/model_router.go:57-75` | When `opts.Model` is set, `resolveProvider` returns the model-matched provider WITHOUT checking its circuit breaker, so a tripped (open) provider keeps receiving every request for that model until the provider call itself errors and fallback kicks in. This defeats the circuit breaker's fast-fail purpose and adds latency/error churn during outages. | After model matching, check the breaker: `if entry.breaker != nil && !entry.breaker.Allow() { continue }` — or at least prefer a closed-breaker candidate among matches. |
| MI-01 | minor | `backend/internal/middleware/ai_orchestrator.go:155-157` | The `X-RateLimit-*` headers are set from the per-user limiter's `remaining/limit/reset` values even though the per-school limiter is the "hard guard"; when the school limit is the binding constraint the headers over-report headroom. | Set headers from the school limiter (or whichever check was the binding one), or document that headers reflect the per-user limit only. |
| MI-02 | minor | `backend/internal/middleware/ai_orchestrator.go:112-114` | `NewRateLimiter` + `Allow` are constructed per-request for both school and user limiters. The constructor is cheap, but the school limiter object is recreated per request with the same prefix — harmless functionally (Redis-backed), but redundant allocation per request. | Hoist limiter construction to middleware setup (single limiter instance per scope), or accept as-is if the alloc cost is negligible. |
| MI-03 | minor | `backend/internal/services/ai_orchestrator_service.go:239-241` | TTL handling comment says "Set TTL only on first creation (INCRBY on a fresh key returns 1)" but the code calls `Expire` unconditionally on every increment (result discarded). With a 48h TTL and daily key rotation this is harmless, but the comment/code mismatch is misleading and the documented "Pitfall 6" avoidance is not actually implemented. | Either branch on `incrResult == 1` to set TTL only on creation, or update the comment to reflect unconditional refresh (which is also fine given daily key rotation). |
| MI-04 | minor | `backend/internal/ai/model_router.go:39-43` | `addProvider` is dead code with a `//nolint:unused` suppression. If providers are registered elsewhere, this is stale API surface; if it is the intended registration path, it is never called. | Remove the dead method, or wire it to the actual registration path and drop the nolint. |
| MI-05 | minor | `backend/internal/middleware/ai_orchestrator.go:123-130` | School-limit rejection sets `Retry-After` but the user-limit rejection path (line 143-149) uses `time.Until(reset)` where `reset` may be zero-valued if `Allow` returned remaining from a fresh counter — the header could be `0`/negative. Minor, but a negative `Retry-After` is invalid per RFC 7231. | Clamp: `if retryAfter < 1s { retryAfter = 1s }` before formatting. |

## Critical Detail (CR-01)

The trigger chain for CR-01:

1. `/api/v2/ai/...` routes go through `authGroup` (router.go:74-87) which
   includes `TenantDBResolver` (router.go:83).
2. For schema-per-tenant schools, `TenantDBResolver` injects the schema into
   the request context via `tenant.InjectSchemaToContext(ctx, tc.SchemaName)`
   (tenant.go:316).
3. `AIHandler.recordUsage` passes that request context straight into
   `AIOrchestratorService.RecordUsage` (handler.go:341-342).
4. `aiUsageLogRepository.Create` calls `r.db.WithContext(ctx)` on the shared
   core DB handle — the same handle on which `SchemaTablePrefix` is
   registered (setup.go:197).
5. The plugin's `Before("*")` callback reads the schema from
   `db.Statement.Context` (schema_db.go:157) and rewrites the table to
   `school_{id}.ai_usage_log`.
6. The table exists only in the public schema (migration in
   `internal/database/migrations/core/ai_usage_log.go`), so the INSERT fails
   with a "relation does not exist" error on every AI call for
   schema-per-tenant schools.

**Fix:** use `tenant.ClearSchemaContext(ctx)` (already defined at
`schema_db.go:203-205`) for the ledger write:

```go
func (r *aiUsageLogRepository) Create(ctx context.Context, entry *models.AIUsageLog) error {
    // Ledger lives in the public schema — must NOT be tenant-schema-prefixed.
    return r.db.WithContext(tenant.ClearSchemaContext(ctx)).Create(entry).Error
}
```

## Verified Working

- D-15 timeout layering (35s Go guard > 30s Python→LLM) is correctly
  applied only to the provider path, not the engine-direct path (stream.go:91-99).
- D-16 streaming failover: `delivered` first-byte tracking is correct; no
  failover after any chunk (model_router.go:140-148).
- SSE envelope contract: all frames are `data: {json}\n\n`; heartbeat comment
  frames; single synthesized terminal `done` on channel close (stream.go:174-208).
- Bounded relay channel with slow-client abort and no goroutine leak
  (stream.go:87-119).
- Rate-limit key namespaces are school/user-separated and match the docs.
- `usdToCents` uses `math.Round` (round-half-up) consistent with A3.
- `DailyQuotaKey` daily rotation and 48h TTL are correct.
