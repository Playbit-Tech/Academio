# Phase 5: Go Integration & Orchestrator - Research

**Researched:** 2026-08-01
**Domain:** AI orchestration (Go), multi-tenant rate limiting/quota/caching, model routing
**Confidence:** HIGH

## Summary

Phase 5 governs Python AI capabilities from Go: a combined provider status endpoint (INT-02), the AI Orchestrator (INT-03 — rate limiting, per-school quota, audit events, Redis caching, retries/circuit breakers with strict timeout layering), and Python wired into the existing Go `ModelRouter` as additional `providerEntry`s (INT-04, two-level routing). Security controls ship WITH the first endpoints (locked decision D-01).

**Primary finding: Phase 5 needs ZERO new external Go dependencies.** Every building block already exists in-repo: the Redis-backed `middleware.RateLimiter`, `ai.CircuitBreaker`, `ai.CalculateCost`/`CostConfig`, the `engine.EngineClient` seam, `pkg/response`, `pkg/logger`, and `ai.Metrics` counters. The work is extension + wiring, not greenfield library selection.

**Primary recommendation:** Implement INT-04 first as the enabling layer (Python entries must exist before quota/audit/cost instrumentation has a provider to observe), then INT-03 (orchestrator: rate limit → quota → cache → provider call → cost ledger → audit), then INT-02 (providers endpoint merges Go breaker state + Python `/v1/providers`). INT-03's controls must wrap ALL `/api/v2/ai/*` endpoints including the streaming and documents ones (D-01).

## User Constraints

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**INT-03 ordering**
- **D-01:** INT-03 controls are the FIRST plan of Phase 5. No AI endpoint — existing (`/ai/chat`, `/ai/search`, `/ai/agents`) or new (`/ai/chat/stream`, `/ai/documents*`, `/ai/providers`) — is exposed without the orchestrator layer. This is a ROADMAP + STATE.md locked decision; do not re-argue.

**Rate limiting (INT-03)**
- **D-02:** AI-specific rate limiting lives in a NEW middleware/helper applied to the `ai` route group (all `/api/v2/ai/*` endpoints), layered ON TOP of the existing global `middleware.RedisRateLimit` (which stays as the coarse API-level guard). Reuse the existing Redis-backed `RateLimiter` (sliding window) — do NOT build a second limiter. Keys are `ai:rl:{scope}:{school_id}:{user_id}` and `ai:rl:{scope}:{school_id}` (per-school + per-user), and the per-school limit is the hard guard so a noisy school cannot starve others (ROADMAP criterion 3).
- **D-03:** Limits are configurable via `config.AI.RateLimit` (new fields: per-user-per-min, per-school-per-min, per-day school spend cap) with sane defaults (e.g. per-school 300 req/min, per-user 60 req/min for chat-class endpoints; streaming and docs get their own scope caps). No plan-tier variability in v1 — flat defaults, tier-based limits deferred (agent discretion: keep simple, the existing `RateLimitConfig.Tiers` is for the global middleware).
- **D-04:** Violations return `429 Too Many Requests` with `Retry-After` header and the standard `response.Error` envelope (`category: rate_limit`). Frontend gets one contract: 429 with a retry hint.

**Quota & spend governance (INT-03)**
- **D-05:** Per-school daily spend cap is enforced PRE-flight (check Redis counter before calling provider; 429 if exhausted) and POST-call (increment Redis counter atomically with the recorded cost). Counter key: `ai:quota:school:{school_id}:{YYYY-MM-DD}`. Default cap is `0` = unlimited unless `AI_QUOTA_DAILY_SPEND_CENTS` set or per-school override applied (deferred: per-school admin override is a Phase-6 admin surface; v1 ships the global default via config).
- **D-06:** Per-request cost cap (ROADMAP criterion 4) is enforced in the orchestrator BEFORE the call using an estimated cost cap from token budget (`opts.MaxTokens`) — reject pre-call if estimated spend > cap; exact post-call cost reconciliation still increments quota. Agent discretion on exact estimation math (use `CalculateCost` with max-tokens worst case).
- **D-07:** Overage behavior = hard 429 (same envelope as D-04) with `Retry-After`; violation is logged (logger.Warnf with school_id) and a Prometheus counter increments. Admin dashboard notification deferred to Phase 6.

**One cost ledger (INT-03/INT-04)**
- **D-08:** Cost recording is UNIFIED: Python's normalized usage payload (provider, model, input/output tokens, cost — Phase 3 contract) is translated into the SAME `ai.CostConfig`/`CalculateCost` shape Go already uses for Gemini/OpenAI, and ONE ledger records every AI call. Storage: shared `public` schema table `ai_usage_log` (new core migration, `ai_conversations` precedent) with columns school_id, user_id, provider, model, input_tokens, output_tokens, cost_cents, request_id, created_at. The table is the durable audit-grade ledger; Redis counters (D-05) are the fast pre-flight check. This is SEPARATE from the B11 audit trail — audit events record *who did what*; `ai_usage_log` records *what it cost*.
- **D-09:** Retention: keep all rows in v1 (no pruning); Phase 6 owns dashboards/retention. Every AI mutation already emits a B11 audit event — do not double-insert audit data into `ai_usage_log`.

**Redis caching (INT-03)**
- **D-10:** Cacheable: non-streaming chat (`/ai/chat`), search (`/ai/search`), and providers status (`/ai/providers`, short TTL). NOT cacheable: `/ai/chat/stream` (never cache SSE), `/ai/documents*` (mutations), `/ai/agents` (static, not worth it).
- **D-11:** Cache key is tenant-scoped ALWAYS: `ai:cache:{school_id}:{endpoint}:{sha256(prompt+model)}`. User is NOT in the key (cross-user cache within a school is the cost win; tenant isolation is the hard boundary — a school NEVER sees another school's cache). TTL: chat 10min, search 5min, providers 15s. Cache hit is transparent to the client (no "cached" marker) — identical response shape.
- **D-12:** Cache writes happen AFTER successful provider response; cache errors (Redis down) are log-and-continue (B9) — never fail the request on cache failure. `X-Cache: HIT/MISS` header optional (agent discretion — include it, costs nothing, aids debugging).

**Two-level failover / ModelRouter (INT-04)**
- **D-13:** Python is wired into `ModelRouter` as a set of `providerEntry`s — one per Python provider (anthropic, deepseek, openrouter, azure-openai, ollama) — implemented as a `pythonProvider` that adapts the `EngineClient` seam (`Chat`/`ChatStream`/`Embed`) to the `ai.Provider` interface. ProviderType grows: `ProviderPython` with a per-entry subtype (e.g. `python:anthropic`). Model matching in `resolveProvider` keeps working (it already does `strings.Contains(model, pType)`).
- **D-14:** Two-level routing: Go `ModelRouter` is the PLATFORM-level failover (gemini ↔ openai ↔ python:provider). Python's internal provider selection stays inside the Python engine — Go does NOT peer inside Python; Go picks `python:anthropic` or `python:deepseek` etc. as discrete entries and lets its own breaker/failover run. Error classification (ROADMAP criterion 4) at the Go boundary: 429 → mark breaker failure, failover to NEXT provider, NEVER retry same; 5xx/timeout → retry once, then failover; other 4xx → permanent, no failover, surface to caller.
- **D-15:** Strict timeout layering: Go→Python call budget MUST exceed Python→LLM budget. Python chat timeout 30s already set in client.go; orchestrator adds an overall Go-side guard on the provider call (e.g. 35s for chat, stream context-bound per FND-03) so the two levels never fight. Document the invariant in code.
- **D-16:** Streaming + failover: on SSE stream, if the selected Python provider fails BEFORE first byte, Go may failover to another provider transparently (reselect at ModelRouter level); after first byte, no failover — the stream is committed (Phase 4 relay already handles in-band errors).

### the agent's Discretion
- Exact config field names/defaults for `config.AI.RateLimit`/`AI_QUOTA_*`
- Estimation math for pre-call cost cap (D-06)
- Whether `pythonProvider` reuses `newGuardedProvider` or composes breaker directly (planner picks — must reuse `CircuitBreaker`)
- `X-Cache` header inclusion (D-12 recommends yes)
- Plan-tier rate variability (D-03 recommends flat in v1)

### Deferred Ideas (OUT OF SCOPE)
- Admin dashboard for quotas/spend (Phase 6 — OBS-01 Grafana + admin surface)
- Per-school quota override UI (Phase 6 admin surface)
- Plan-tier-based AI rate limits (D-03 — flat in v1)
- Cache invalidation on document re-ingest (post-Phase 5; cacheable search results are TTL-based in v1)
- `ai_usage_log` retention/pruning (Phase 6)
</user_constraints>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INT-02 | `GET /api/v2/ai/providers` multi-provider status endpoint | Go `CircuitBreaker.State()` per provider (Closed/Open/HalfOpen) + Python `GET /v1/providers` → `{providers:[{provider,status,latency_ms,last_checked,cooldown_until}]}` merged into one `response.Success` payload; TTL 15s cacheable (D-10), cache key per D-11 |
| INT-03 | AI Orchestrator: rate limiting, quota enforcement, AI-usage audit events, Redis prompt/response caching, retries/circuit breakers on Python calls, strict timeout layering (Go→Python > Python→LLM) | Reuse `middleware.RateLimiter` (Redis sliding window) with new `ai:rl:*` keys; Redis counter `ai:quota:school:{id}:{date}` pre-flight + post-call; new `ai_usage_log` core migration (shared schema); `ai:cache:*` tenant-scoped keys; `CircuitBreaker` + `newGuardedProvider`; Go 35s guard > Python 30s chat timeout |
| INT-04 | Python providers wired into Go `ModelRouter` as additional `providerEntry`s (two-level routing) | `ai.NewProvider` already returns `ModelRouter` when >1 entry; extend the entries slice with `pythonProvider` adapters (pType `python:{name}`); `resolveProvider`'s `strings.Contains(model, pType)` matching works as-is; embeddings/CountTokens stay on `providers[0]` (primary) — append Python entries LAST |

## Standard Stack

### Core — no new dependencies (all verified in `backend/go.mod`)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| gin-gonic/gin | v1.12.0 | HTTP router; `ai` route group | Existing project router |
| redis/go-redis/v9 | v9.21.0 | Redis rate limits, quota counter, prompt cache | Existing `rdb` wired in setup.go |
| gorm.io/gorm | v1.31.2 | `ai_usage_log` model + core migration | Existing ORM; shared `public` schema via core migrations |
| gorm.io/driver/postgres | v1.6.0 | Postgres driver (pgx-based) | Existing |
| google/uuid | v1.6.0 | `ai_usage_log` IDs (uuid string, matches `AIDocument`) | Existing |
| prometheus/client_golang | v1.19.1 | Quota-violation + orchestrator counters | Existing `ai.Metrics` (ai_requests_total, ai_cost_total) |
| hibiken/asynq | v0.26.0 | Queue (doc ingest) — untouched but present | Existing |

### Reused in-repo building blocks (do NOT re-implement)

| Component | Location | What it gives Phase 5 |
|-----------|----------|----------------------|
| `middleware.RateLimiter` (Redis sliding window) | `backend/internal/middleware/ratelimit.go` | `NewRateLimiter(client, limit, window, prefix)` + `Allow(ctx, key) (allowed, remaining, limit, reset, err)` — the exact primitive D-02 requires; key becomes `ratelimit:{prefix}:{key}` (verified ratelimit.go:138-180) |
| `ai.CircuitBreaker` | `backend/internal/ai/circuit_breaker.go` | `State()`, `Allow()`, `Success()`, `Failure()`; `DefaultCircuitBreakerConfig{Threshold:5, Cooldown:30s}` |
| `ai.CalculateCost` / `ai.CostConfig` / `defaultCosts` | `backend/internal/ai/cost.go` | The ONE cost shape for the unified ledger (D-08) |
| `ai.EstimateTokens` | `backend/internal/ai/cost.go` | len/4 heuristic for D-06 pre-call cost estimation |
| `engine.EngineClient` + `StatusError` | `backend/internal/ai/engine/client.go` | `Chat`, `ChatStream`, `Extract`, `IngestDocument`, `Health`; `StatusError{StatusCode, Body}` gives D-14 error classification |
| `ai.NewProvider` | `backend/internal/ai/gateway.go:116` | Already returns `*ModelRouter` when >1 provider configured — the INT-04 extension point |
| `pkg/response` | `backend/pkg/response/response.go` | `Error(c, status, code, message, category)`, `Success(c, data)` — D-04/D-07 429 envelope |
| `pkg/logger` | `backend/pkg/logger` | `logger.Warnf` for quota violations (D-07) |
| `services.CacheService` | `backend/internal/services/cache_service.go` | JSON Set/Get over `rdb`, nil-safe — prompt cache can reuse or mirror it |
| `middleware.GetUserID`/`GetSchoolID`/`GetRequestID` | `middleware/auth.go:162,189`; `middleware/requestid.go:46` | School/user/request context for keys + ledger + audit |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reusing `middleware.RateLimiter` | New bespoke limiter (e.g., token bucket lib) | D-02 explicitly forbids a second limiter; sliding window already fits per-user/per-school keys |
| Extending `ai.NewProvider` entries | Fresh `NewModelRouter` call in setup.go | `providerEntry` is unexported — entries can only be built inside the `ai` package; extend `NewProvider` (or add an exported `ai.NewProviderWithPython`) |
| New Redis client | Existing `rdb` | `rdb` already in setup.go; a second client doubles connections for no reason |

**Installation:** none. No `go get` required for Phase 5. (Verify before writing the plan: run `grep -n "internal/ai" backend/go.mod` — if the ai package is internal, no module change at all.)

**Version verification:** `go.mod` read directly this session — gin v1.12.0, go-redis v9.21.0, gorm v1.31.2, gorm-postgres v1.6.0, uuid v1.6.0, prometheus v1.19.1, asynq v0.26.0 — all [VERIFIED: codebase go.mod].

## Architecture Patterns

### INT-04 wiring pattern — extend `ai.NewProvider`, append Python entries LAST

```go
// backend/internal/ai/gateway.go — conceptual change (current verified shape)
func NewProvider(cfg AIServiceConfig) (Provider, error) {
    // ... existing gemini/openai entry building (lines 116-172) ...
    // NEW: if cfg.EngineURL != "" && cfg.EngineToken != "" {
    //     client := engine.NewClient(cfg.EngineURL, cfg.EngineToken)
    //     for _, py := range []string{"anthropic","deepseek","openrouter","azure-openai","ollama"} {
    //         entries = append(entries, providerEntry{
    //             provider: newGuardedProvider(newPythonProvider(client, py), ProviderType("python:"+py), breakerCfg),
    //             pType:    ProviderType("python:" + py),
    //         })
    //     }
    // }
    // if len(entries) == 1 { return entries[0].provider, nil }
    // return NewModelRouter(entries), nil
}
```

**Key verified facts:**
- `NewProvider` already returns `NewModelRouter(entries)` when `len(entries) > 1` (gateway.go:175-198) [VERIFIED: codebase].
- `providerEntry` and `addProvider` are UNEXPORTED (`//nolint:unused` at model_router.go:39) — Python entries MUST be appended inside the `ai` package. Do not try to call `addProvider` from setup.go [VERIFIED: codebase].
- `resolveProvider` matches via `strings.Contains(strings.ToLower(model), strings.ToLower(string(entry.pType)))` (model_router.go:58) — a request model like `"python:anthropic/claude-3-5-sonnet"` contains `"python:anthropic"` → matched entry [VERIFIED: codebase].
- `GenerateEmbedding(s)` and `CountTokens` ALWAYS delegate to `r.providers[0]` (model_router.go:158-196) — no routing. **Append Python entries after gemini/openai so embeddings keep hitting the canonical OpenAI/Gemini embedding provider.** [VERIFIED: codebase]
- `fallbackProviders(skip)` returns all entries except the failing pType (model_router.go:81) — failover already ordered by index [VERIFIED: codebase].

### `pythonProvider` adapter — implements `ai.Provider` over `EngineClient`

`ai.Provider` interface (gateway.go) requires: `GenerateText`, `GenerateTextStream`, `GenerateEmbedding`, `GenerateEmbeddings`, `CountTokens`, `Close` [VERIFIED: codebase].

```go
type pythonProvider struct {
    client engine.EngineClient
    name   string // "anthropic" | "deepseek" | ...
}
```

- `GenerateText` → `client.Chat(ctx, engine.ChatRequest{Model: name-prefixed, Messages:...})`; translate `ChatResponse.Message` → `ai.Response`; translate normalized usage payload (provider, model, input/output tokens, cost — Phase 3 contract) into `ai.CostConfig` shape so D-08's ledger records it [CITED: CONTEXT D-08; [VERIFIED: codebase] Python chat.py returns usage on every ChatResponse].
- `GenerateTextStream` → `client.ChatStream(ctx, req, cb)` (context-bound, no timeout — matches FND-03/D-16).
- `GenerateEmbedding(s)` → NEW `engine` method `Embed` (Python `/v1/embed` EXISTS — `POST /v1/embed` → `{model, dimension, embeddings}`; contract verified [VERIFIED: codebase ai-engine/app/api/embed.py]). **The Go `EngineClient` has no `Embed` method today — one must be added to `engine/client.go`** (chat.go's patterns apply: POST JSON + decode).
- `CountTokens` → local `ai.EstimateTokens(text)` (no Python token endpoint).
- `Close()` → no-op (stateless HTTP client).

### INT-03 orchestrator chain — middleware per endpoint group

Order per endpoint (verified against existing chain shape; `ai` group is created via `authGroup(v2, "/ai", ...)` at router.go, so JWT/school/tenant/audit-middleware already run BEFORE these [VERIFIED: codebase router.go:73-91]):

1. **Rate limit** (new middleware, applied on the `ai` subgroup): per-school key `ai:rl:{scope}:{school_id}` (hard guard) + per-user `ai:rl:{scope}:{school_id}:{user_id}` — both via the existing `RateLimiter.Allow`. Scope from route: `chat`, `chat_stream`, `search`, `agents`, `providers`, `documents`. 429 + `Retry-After: {retryAfterSec}` + `response.Error(c, 429, "rate_limit_exceeded", "...", "rate_limit")` (D-04).
2. **Quota pre-flight** (orchestrator service): `GET ai:quota:school:{school_id}:{YYYY-MM-DD}` (Redis `GET`/`INCR` with day-key), compare vs `cfg.AI.Quota.DailySpendCents` (0 = unlimited, D-05); per-request cap via `ai.CalculateCost(maxTokensEstimate, ...) > cfg.AI.Quota.MaxRequestCents` → 429 with `Retry-After` (D-06/D-07). Reject BEFORE provider call.
3. **Cache read** (chat/search/providers only — D-10): `GET ai:cache:{school_id}:{endpoint}:{sha256(prompt+model)}`. Hit → `X-Cache: HIT` + return; miss → `X-Cache: MISS` + continue (D-12).
4. **Provider call** via `aiProvider` (ModelRouter — now with Python entries). Go-side context deadline guard: `ctx, cancel := context.WithTimeout(c.Request.Context(), 35*time.Second)` for chat (D-15; stream uses request ctx, context-bound FND-03).
5. **Post-call**: increment `ai:quota:school:{school_id}:{YYYY-MM-DD}` atomically with recorded cost (`INCRBY cost_cents`), write `ai_usage_log` row, write cache (log-and-continue on Redis error, B9).

**Streaming path caveat (verified critical):** `StreamChat` in `modules/ai/stream.go` calls `h.aiClient.ChatStream(...)` DIRECTLY — it does NOT go through `aiProvider`/`ModelRouter` today. For D-16 failover-before-first-byte to work on `/ai/chat/stream`, the stream handler must route through the orchestrator (which selects a provider — Python entries via ModelRouter `GenerateTextStream` — or retains engine-direct as the Python-only path). Planner MUST decide: route streaming through `aiProvider.GenerateTextStream` (gets two-level failover + ledger) vs keep engine-direct (Python-only streaming, no Go-side failover). D-13/D-16 imply routing through the provider layer — flag as a plan-level decision.

### `ai_usage_log` — shared-schema core migration (D-08 precedent)

Follow the exact `ai_documents.go` pattern [VERIFIED: codebase]:
- File: `backend/internal/database/migrations/core/ai_usage_log.go` with header comment `2026_08_01_000000_create_ai_usage_log` (migration ID per phase-date convention).
- Register in `CoreMigrations()` list in `backend/internal/database/migrations/core/core.go`.
- Model in `backend/internal/database/models/ai_usage_log.go` (SHARED `public` schema — NOT tenant): `ID string` (uuid), `SchoolID uint` (index), `UserID uint`, `Provider string`, `Model string`, `InputTokens int`, `OutputTokens int`, `CostCents int64`, `RequestID string`, `CreatedAt time.Time`; `TableName()` → `ai_usage_log`.
- **BaseModel gotcha:** do NOT use `BaseModel` auto-create/update timestamps — the project found `PrepareStmt` + `SchemaTablePrefix` breaks GORM auto-timestamp writes; set `CreatedAt` explicitly (verified pattern in `ai_document.go`).
- Repository on the CORE `*gorm.DB` (public schema) — mirror `modules/ai/repository.go` (`AIDocumentRepository`): `Create(ctx, ...)`, `GetByIDAndSchoolID` forcing school scoping.

### Audit (B11) vs ledger (D-08) — two separate writes

- B11 audit events: already emitted via `AIHandler.WithAuditLogger` for existing endpoints [VERIFIED: codebase setup.go:830-840] — keep that; ensure the NEW endpoints (`/ai/providers`, `/ai/chat/stream`, `/ai/documents*`) also emit audit (provider status GET may be read-only audit per existing conventions — check how other read endpoints handle B11).
- `ai_usage_log`: cost-only ledger — do NOT insert audit descriptions (D-09).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI rate limiting | Second/parallel limiter | Existing `middleware.RateLimiter` (Redis sliding window) with `ai:rl:*` keys | D-02 locked; sliding window already returns retry-after |
| Circuit breaking on Python | New breaker logic | `ai.CircuitBreaker` + `newGuardedProvider` | Already tested, metrics-tied, `State()` feeds INT-02 |
| Cost calculation | New per-provider cost math | `ai.CalculateCost` / `CostConfig` (D-08 unified shape) | One ledger; Python usage payload is TRANSLATED into this shape, not parallel |
| Redis cache store | Raw `rdb` boilerplate per handler | `services.CacheService` (JSON Set/Get) or a thin `aiCache` mirror | Nil-safe, already used across codebase |
| 429 envelope | Custom error body | `pkg/response.Error(c, 429, code, msg, "rate_limit")` | D-04/D-07 one contract for frontend |
| SSE parsing | Custom scanner | `engine`'s existing SSE scan (blank-line split, 1MB cap, heartbeat-tolerant) | Phase 4 verified; `pythonProvider.GenerateTextStream` reuses `ChatStream` |
| SHA-256 cache key hashing | Custom hash | `crypto/sha256` stdlib (hex of `prompt+model`) | D-11 key format; stdlib |

**Key insight:** Phase 5 is an orchestration-and-wiring phase. Every hard problem (limiter, breaker, cost, SSE, cache, envelope) already has a verified in-repo solution. New code is adapters (`pythonProvider`, `aiCache`), middleware (rate limit), and a service (orchestrator + ledger). Deviating from these building blocks is the fastest way to introduce subtle multi-tenant bugs.

## Common Pitfalls

### Pitfall 1: Adding Python entries breaks embeddings routing
**What goes wrong:** `GenerateEmbedding(s)` and `CountTokens` always call `r.providers[0]` (model_router.go:158-196). If Python entries are prepended, RAG embedding calls (setup.go:719 `aiProvider.GenerateEmbeddings`) hit a `pythonProvider` and fail or return wrong-dimension vectors.
**Why it happens:** The router routes only text/stream by model; embeddings are hardcoded to primary.
**How to avoid:** Append Python entries AFTER gemini/openai in the `NewProvider` entries slice. Embeddings keep hitting the canonical provider.
**Warning signs:** pgvector writes fail after INT-04 lands; embedding dimension errors in tests.

### Pitfall 2: Retry-once semantics don't exist in ModelRouter yet
**What goes wrong:** D-14 requires "5xx/timeout → retry ONCE, then failover; 429 → failover NEVER retry." `ModelRouter.GenerateText` currently does: primary → try each fallback exactly once (model_router.go:101-128). No retry-once; no 429-vs-5xx discrimination (the `StatusError` from Python has `StatusCode`, but the router treats all errors alike).
**Why it happens:** ModelRouter was built before the Python seam had typed status codes.
**How to avoid:** Classify at the `pythonProvider` boundary (or a thin orchestrator wrapper): 429 → `breaker.Failure()` + return error (router moves to next entry); 5xx/timeout → retry same entry once via `NewGuardedProvider`-style wrapper, then let router fail over; other 4xx → return to caller without marking breaker (or mark per policy — decision: permanent errors should NOT trip the breaker on repeated 4xx, else one bad prompt kills the entry). [ASSUMED: exact retry placement — planner decides between wrapper vs router enhancement; must document]
**Warning signs:** A 429 from Python repeatedly retried against the same provider; a single bad 4xx prompt opening a circuit.

### Pitfall 3: Streaming bypasses the router entirely
**What goes wrong:** `/ai/chat/stream` calls `aiClient.ChatStream` directly — no provider selection, no breaker, no ledger, no D-16 failover.
**Why it happens:** Phase 4 wired streaming engine-direct (context-bound FND-03).
**How to avoid:** Route streaming through the orchestrator → `aiProvider.GenerateTextStream` (or a dedicated orchestrator stream method) so D-13/D-16 entries participate. Failover-before-first-byte requires the orchestrator to reselect on error before the first `delta` event is written.
**Warning signs:** Circuit opens on `python:anthropic` but streaming still hits it.

### Pitfall 4: SSE + gzip / buffering middleware
**What goes wrong:** If a global gzip/response-buffer middleware wraps the `ai` group, SSE chunks buffer and the client sees nothing until the stream ends (or connection timeout). Phase 4's stream.go sets `Cache-Control: no-cache` (verified line 80) but gzip is a separate concern.
**Why it happens:** Middleware ordering; the project already disables gzip for SSE (documented in Phase 4 notes).
**How to avoid:** Keep the `ai` stream route exempt from any gzip/buffering; confirm `SecurityHeaders`/`CORS` don't interfere with `text/event-stream` (they don't — verified they only set headers).
**Warning signs:** Streaming works in curl but browsers see a spinner; `Content-Encoding: gzip` on an SSE response.

### Pitfall 5: Non-atomic quota counters
**What goes wrong:** Pre-flight check then post-call `INCRBY` is two operations; concurrent requests from one school can overshoot the daily cap (or the counter can miss increments if a provider call errors after pre-flight).
**Why it happens:** Distributed increment without locking.
**How to avoid:** Use Redis `INCRBY` as the authoritative counter (atomic), and do the pre-flight as `GET` on the same key; accept that a burst may slightly overshoot (log + metric, D-07 pattern). NEVER `GET` → `SET` read-modify-write in Go.
**Warning signs:** Quota counter drift vs `ai_usage_log` SUM(cost_cents) at end of day.

### Pitfall 6: B4/B13 — multi-statement `db.Exec`
**What goes wrong:** Any migration or repo code combining `INCR` + `EXPIRE` or `CREATE TABLE ...; INSERT ...` in one `Exec` fails under pgx v5 prepared-statement mode.
**Why it happens:** pgx v5 does not support multiple statements in one prepared call.
**How to avoid:** Separate calls (Rule B4/B13). For quota key TTL: `INCRBY` then `EXPIRE` (only set EXPIRE when key was just created, to avoid sliding the TTL on every increment — use `SETNX` for the day key or track via the first `INCR` result == 1).
**Warning signs:** "cannot insert multiple commands into a prepared statement" runtime errors.

### Pitfall 7: Config fail-fast (Rule B12) must cover new fields
**What goes wrong:** `AI_QUOTA_DAILY_SPEND_CENTS` and `config.AI.RateLimit` defaults silently missing → unlimited spend (violates D-05's "0 = unlimited" being EXPLICIT, not accidental).
**Why it happens:** New config fields added without `validate()` entries.
**How to avoid:** Add fields to `AIConfig` (internal/config/config.go:98-124) + `.env.example` (lines 92-135 region) + `validate()` — fail fast if `AI_QUOTA_DAILY_SPEND_CENTS` is negative or non-numeric; document that `0` means unlimited by design.
**Warning signs:** Startup proceeds with a quota default that was never set.

## Code Examples

### 1. Provider status merge (INT-02) — Go breaker + Python health
```go
// Source: verified shapes — ai.CircuitBreaker.State() + Python /v1/providers contract
type providerStatus struct {
    Provider      string  `json:"provider"`
    Status        string  `json:"status"` // healthy | degraded | unavailable | cooldown (Python) / open | half_open | closed (Go)
    LatencyMs     int64   `json:"latency_ms,omitempty"`
    LastChecked   string  `json:"last_checked,omitempty"`
    CooldownUntil *string `json:"cooldown_until,omitempty"`
}
// Go local: for each entry in router, breaker.State() → status string
// Python: engine GET /v1/providers → []providerStatus (shape verified in ai-engine/app/api/providers.py:22-35)
// Merge: local entries first, Python entries second; wrap in response.Success(c, merged)
```
Source: [VERIFIED: codebase ai-engine/app/api/providers.py lines 22-35; backend/internal/ai/circuit_breaker.go]

### 2. Rate limit middleware skeleton (D-02/D-04)
```go
// Source: verified in backend/internal/middleware/ratelimit.go
// NewRateLimiter(client *redis.Client, limit int, window time.Duration, prefix string)
// Allow(ctx, key) (allowed bool, remaining int, limit int, reset time.Time, err error)
// Redis key built as: ratelimit:{prefix}:{key}
func AIRateLimit(cfg config.AIRateLimitConfig, rdb *redis.Client) gin.HandlerFunc {
    return func(c *gin.Context) {
        schoolID := middleware.GetSchoolID(c)
        userID := middleware.GetUserID(c)
        scope := aiScope(c) // from route path: chat | chat_stream | search | ...
        // Per-school hard guard (prefix keeps D-02 keys: ratelimit:ai:rl:{scope}:{school_id})
        rl := middleware.NewRateLimiter(rdb, cfg.PerSchoolPerMin, time.Minute, "ai:rl:"+scope)
        allowed, _, _, reset, err := rl.Allow(c.Request.Context(), fmt.Sprintf("%d", schoolID))
        if err != nil || !allowed {
            c.Header("Retry-After", fmt.Sprintf("%.0f", time.Until(reset).Seconds()))
            response.Error(c, http.StatusTooManyRequests, "rate_limit_exceeded", "rate limit exceeded, retry later", "rate_limit")
            c.Abort()
            return
        }
        // Per-user key likewise: NewRateLimiter(rdb, cfg.PerUserPerMin, time.Minute, "ai:rl:"+scope)
        //   + Allow(ctx, fmt.Sprintf("%d:%d", schoolID, userID)) -> ratelimit:ai:rl:{scope}:{school_id}:{user_id}
        c.Next()
    }
}
```
Source: [VERIFIED: codebase middleware/ratelimit.go:138-180 NewRateLimiter/Allow; response.Error signature response.go:140]

### 3. Unified cost recording (D-08) — Python usage → ledger
```go
// Python ChatResponse includes usage {provider, model, input_tokens, output_tokens, cost} [VERIFIED: codebase]
// Translate into the ONE Go shape:
cost := ai.CalculateCost(resp.InputTokens, resp.OutputTokens, provider, aiCfg)
// OR if Python reports its own cost: prefer Python's cost for python entries, but normalize to cents:
entry := models.AIUsageLog{
    ID: uuid.NewString(), SchoolID: schoolID, UserID: userID,
    Provider: pyUsage.Provider, Model: pyUsage.Model,
    InputTokens: pyUsage.InputTokens, OutputTokens: pyUsage.OutputTokens,
    CostCents:  costCentsFrom(pyUsage.Cost), RequestID: middleware.GetRequestID(c),
    CreatedAt: time.Now().UTC(),
}
// write via core-DB repository (public schema); INCRBY ai:quota:school:{id}:{date} costCents
```
Source: [VERIFIED: codebase cost.go CalculateCost; models/ai_document.go pattern; CONTEXT D-08]

### 4. Cache read/write (D-10/D-11/D-12)
```go
// Source: pattern verified in services/cache_service.go (JSON Set/Get, nil-safe)
key := fmt.Sprintf("ai:cache:%d:chat:%x", schoolID, sha256.Sum256([]byte(prompt+model)))
var cached aiResponse
if cacheService.Get(ctx, key, &cached) == nil {
    c.Header("X-Cache", "HIT")
    response.Success(c, cached)
    return
}
c.Header("X-Cache", "MISS")
// ... call provider ...
if err := cacheService.Set(ctx, key, resp, 10*time.Minute); err != nil {
    logger.Warnf("ai cache write failed (log-and-continue, B9): %v", err)
}
```
Source: [VERIFIED: codebase services/cache_service.go; CONTEXT D-10/D-11/D-12]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gemini/OpenAI only in `ModelRouter` | + 5 Python entries (`python:anthropic`, etc.) via `pythonProvider` | Phase 5 (INT-04) | Platform-level failover across ALL providers; two-level routing |
| No AI rate limiting beyond global API guard | `ai:rl:*` per-school + per-user limits on the `ai` group | Phase 5 (INT-03/D-02) | Noisy school cannot starve others (ROADMAP criterion 3) |
| No spend governance | `ai:quota:*` daily cap + `ai_usage_log` ledger | Phase 5 (D-05/D-08) | OWASP LLM guardrail ships with first endpoints |
| No prompt cache | `ai:cache:*` tenant-scoped TTL cache | Phase 5 (D-10/D-11) | Cost win: cross-user cache within school, hard tenant isolation |
| Streaming engine-direct (no failover) | Orchestrator-routed streaming with failover-before-first-byte | Phase 5 (D-16) | SSE resiliency |
| No provider health surface | `GET /api/v2/ai/providers` (Go breaker + Python health) | Phase 5 (INT-02) | Ops visibility |

**Deprecated/outdated:**
- `ai.addProvider` (`//nolint:unused`) — unexported; keep or remove. Python entries are wired via `NewProvider`, not runtime mutation [VERIFIED: codebase].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ~~`middleware` exposes a reusable `NewRateLimiter(rdb)`~~ **RESOLVED — verified:** `NewRateLimiter(client, limit, window, prefix)` exists (ratelimit.go:138); `Allow(ctx,key)` returns `(allowed, remaining, limit, reset time.Time, err)`; Redis key = `ratelimit:{prefix}:{key}` | Standard Stack / Code Example 2 | None — verified this session |
| A2 | `pythonProvider` reuses `newGuardedProvider` for breaker composition | INT-04 pattern | Low — CONTEXT explicitly gives planner discretion; both paths reuse `CircuitBreaker` |
| A3 | Cost from Python's normalized usage payload can be converted to integer cents for `cost_cents` | Code Example 3 | Medium — provider cost is a float; rounding policy (round-half-up) must be fixed to keep `ai_usage_log` SUM == Redis counter |
| A4 | Retry-once logic lives in a small wrapper around `pythonProvider` (not a ModelRouter change) | Pitfall 2 | Medium — D-14 semantic; if placed in router, shared by all providers; planner must pick one place and test |
| A5 | Streaming routes through the orchestrator/provider layer for D-16 | Pitfall 3 | HIGH — if streaming stays engine-direct, D-16 failover and ledger coverage for streams are NOT met; plan must explicitly wire it |
| A6 | `GetUserID` returns 0 for system/service contexts (unknown user) — ledger records user_id 0 | Code Example 3 | Low — verify handler always has auth user (JWTAuth runs before ai group) |

## Open Questions

1. **Streaming routing decision (A5 — HIGH):** does `/ai/chat/stream` go through `aiProvider.GenerateTextStream` (gains failover + ledger) or stay engine-direct (Python-only, simpler)?
   - What we know: stream.go currently calls `aiClient.ChatStream` directly; `ModelRouter.GenerateTextStream` exists (model_router.go:130) and routes + falls back.
   - What's unclear: whether Phase 4's stream contract (in-band `error`/`done` events, heartbeat 25s, relayBufferSize 64) survives routing through the router.
   - Recommendation: route through the provider layer; the router's `GenerateTextStream` can relay the same `EngineEvent` types. Keep heartbeat relay in stream.go.

2. **429 vs 5xx classification source:** `StatusError.StatusCode` exists on Python errors — but Gemini/OpenAI SDK errors are untyped.
   - What we know: D-14 classification is defined for the Go boundary; Python returns clean status codes (429/502/400 documented in embed.py).
   - What's unclear: whether classification applies only to Python entries (recommended) or must also classify direct SDK errors.
   - Recommendation: classify ONLY at the `pythonProvider` boundary using `StatusError.StatusCode`; direct SDK providers keep current behavior.

3. **Quota overage handling for cache hits:** if a chat request hits cache, does it still count against quota?
   - What we know: D-11 cache hit is transparent; D-05 increments post-call with recorded cost.
   - What's unclear: whether a cached response (cost 0 — no provider call) should skip quota increment (recommended: yes — cost was already recorded on first write).
   - Recommendation: cache hit → no quota increment (no provider spend); quota checks only gate provider calls.

4. **Read-only audit for `GET /ai/providers`:** does the new endpoint emit a B11 audit event?
   - What we know: B11 mandates audit on all mutation operations; existing AI handler emits via `WithAuditLogger`.
   - Recommendation: follow the codebase's existing convention for read endpoints (check how other GET endpoints handle audit); likely a lightweight `read` action or skip.

5. **`RateLimitConfig.Tiers` interaction:** D-03 says flat in v1, but `config.RateLimitConfig` has `Tiers map[string]RateLimitTier` + `GetTier(plan)`.
   - What we know: existing tiers machinery exists for the global limiter.
   - Recommendation: new `config.AI.RateLimit` is flat struct (per-user-per-min, per-school-per-min, per-day spend); do NOT wire into `GetTier` (deferred D-03).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Go toolchain | build + test | ✓ | go1.26.1 linux/amd64 | — |
| Docker (shared-postgres:5432, shared-redis:6379) | DB + Redis | ✓ | Docker 28.1.1; both containers running | — |
| Redis client (go-redis) | rate limit/quota/cache | ✓ (via Docker; no local redis-cli) | v9.21.0 in go.mod | Use `docker exec shared-redis redis-cli` for manual verification |
| Python ai-engine | INT-02 source (/v1/providers), INT-04 backend | ✗ NOT currently running | uv 0.12.0, Python 3.13.1 present | `uv run uvicorn app.main:app --port 8000` from ai-engine/ (per .env.example); docker-compose api profile uses http://ai-engine:8000 |
| Backend (:8080) | integration tests | ✓ running | — | `cd backend && ./bin/server` |

**Missing dependencies with no fallback:**
- None — toolchain fully present. Python engine must be started for live integration verification (intended: the ai-engine is part of the stack; INT-02/04 tests need it running).

**Missing dependencies with fallback:**
- redis-cli (not installed locally) → use `docker exec shared-redis redis-cli` or the backend's own client for verification.

**Notes:** `nyquist_validation: false` in `.planning/config.json` — no validation-architecture section included (per config). `security_enforcement` absent → treated as enabled → Security Domain below included.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (existing) | JWT via `authGroup` — already enforced on ai group |
| V3 Session Management | no (existing) | JWT + Redis token store — existing |
| V4 Access Control | yes | Tenant scoping: `school_id` in EVERY cache key (D-11), quota key (D-05), ledger row (D-08); `x-school-id` + `EnforceSchoolID` already in `authGroup` |
| V5 Input Validation | yes | `Options.Model` length/format validation before `resolveProvider` (model strings flow into cache keys — validate to prevent cache-key injection); prompt length cap at handler |
| V6 Cryptography | partial | No new crypto; `EngineTokenHeader` (X-AI-Engine-Token) service token travels over HTTP → HTTPS in prod; Redis keys are not secrets (but never log full prompts) |

### Known Threat Patterns for {go + redis + gin multi-tenant}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant cache leakage | Information Disclosure | D-11: `school_id` ALWAYS in cache key; tenant isolation is the hard boundary; never include user-only data in shared keys without school prefix |
| Quota bypass (noisy school starves others) | DoS | D-02 per-school hard guard `ai:rl:{scope}:{school_id}` + D-05 daily spend cap; both enforced pre-flight |
| Cost explosion (runaway token spend) | DoS / Financial | D-06 per-request cost cap (pre-call via `CalculateCost` worst case) + D-05 daily cap; Prometheus `ai_cost_total` |
| Prompt injection via cached content | Tampering | Cache stores RESPONSES of authenticated prompts only; never cache tool/agent outputs with side effects (D-10 excludes mutations); document that cache is trust-level of the school's own traffic |
| Redis key injection | Tampering | Validate/escape `school_id` (uint — safe), endpoint scope (enum), and hash model+prompt with sha256 (D-11) — no raw user strings in keys |
| Service token leakage | Spoofing | `X-AI-Engine-Token` only in `engine.NewClient` (env config, Rule B6); never echo in responses; HTTPS in prod (docker-compose local is HTTP — acceptable dev-only) |
| 429 flood as legit traffic (retry storms) | DoS | `Retry-After` header (D-04) honored by clients; rate limiter counts per-user AND per-school |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: codebase] `backend/internal/ai/model_router.go` — resolveProvider Contains-matching, fallback order, embeddings→providers[0], unexported addProvider
- [VERIFIED: codebase] `backend/internal/ai/gateway.go` — NewProvider entries building, NewModelRouter return, Provider interface + newGuardedProvider
- [VERIFIED: codebase] `backend/internal/ai/circuit_breaker.go` — State/Allow/Success/Failure, DefaultCircuitBreakerConfig{5, 30s}
- [VERIFIED: codebase] `backend/internal/ai/cost.go` — CalculateCost, CostConfig, defaultCosts, EstimateTokens
- [VERIFIED: codebase] `backend/internal/ai/engine/{client,engine,sse}.go` — EngineClient methods, headers, timeouts (chat 30s / extract 5m / health 10s), ChatStream context-bound, StatusError
- [VERIFIED: codebase] `backend/internal/middleware/ratelimit.go`, `audit.go`, `auth.go` (GetUserID/GetSchoolID), `tenant.go`, `requestid.go` (GetRequestID)
- [VERIFIED: codebase] `backend/internal/router/router.go` (authGroup helper l.73-91, v2 group l.124-133) + `router/setup.go` (NewRouter l.140, aiProvider l.178, engineClient l.294, WithEngineClient/AuditLogger l.830-840, GenerateEmbeddings l.719, newAIScoringHandler l.1021)
- [VERIFIED: codebase] `backend/internal/modules/ai/{handler,stream,service,repository,dto}.go` — existing endpoints, StreamChat engine-direct
- [VERIFIED: codebase] `backend/internal/database/migrations/core/{core,ai,ai_documents}.go` + `backend/internal/database/models/ai_document.go` — migration + shared-model precedent
- [VERIFIED: codebase] `backend/internal/config/config.go` (AIConfig l.98-124, validate) + `.env.example` (AI_* lines 92-135)
- [VERIFIED: codebase] `backend/pkg/response/response.go`, `backend/pkg/logger`, `backend/internal/services/cache_service.go`
- [VERIFIED: codebase] `ai-engine/app/api/providers.py`, `chat.py`, `embed.py` — Python contract shapes
- [VERIFIED: codebase] `backend/go.mod`, `backend/Makefile` (test-unit/test-integration), `backend/docker-compose.yml` (AI_ENGINE_URL, provider keys)
- [CITED: CONTEXT.md] D-01..D-16 decisions, ROADMAP success criteria, Exit Criteria
- [CITED: REQUIREMENTS.md] INT-02/INT-03/INT-04 definitions

### Secondary (MEDIUM confidence)
- None beyond the above — all critical claims verified directly in the codebase this session.

### Tertiary (LOW confidence)
- None. All claims sourced from codebase reads or locked decisions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every component verified in go.mod / codebase; zero new deps
- Architecture: HIGH — wiring points (NewProvider, authGroup, migrations, stream.go) all read directly; A1-A6 flagged where discretion remains
- Pitfalls: HIGH — B4/B13, SSE/gzip, embeddings-primary, and retry-semantics gaps verified against actual code

**Research date:** 2026-08-01
**Valid until:** 2026-09-01 (codebase-verified; re-verify only if Phase 4 or Python contract changes)
