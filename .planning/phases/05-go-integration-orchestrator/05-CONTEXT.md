# Task Context: Phase 5 — Go Integration & Orchestrator

Phase: 05-go-integration-orchestrator
Status: planning
Created: 2026-08-01 (after Phase 4 verified PASSED-WITH-NOTES)

## Goal

Python capabilities are governed and routed from Go: a combined provider status endpoint (INT-02), the AI Orchestrator — rate limiting, per-school quota enforcement, AI-usage audit events, Redis prompt/response caching, retries/circuit breakers on Python calls with strict timeout layering (INT-03) — and Python wired into the existing Go `ModelRouter` as additional `providerEntry`s (INT-04, two-level routing). Security controls ship WITH the first endpoints, not as a Phase-6 bolt-on (locked roadmap decision).

## Requirements (from REQUIREMENTS.md)

- **INT-02**: `GET /api/v2/ai/providers` multi-provider status endpoint
- **INT-03**: AI Orchestrator: rate limiting, quota enforcement (OWASP LLM top-10 guardrail — ships with first endpoints), AI-usage audit events, Redis prompt/response caching, retries/circuit breakers on Python calls; strict timeout layering (Go→Python > Python→LLM)
- **INT-04**: Python providers wired into Go `ModelRouter` as additional `providerEntry`s (two-level routing: Go platform-level failover, Python reports usage only)

## ROADMAP Success Criteria (what must be TRUE)

1. `GET /api/v2/ai/providers` returns combined status for Gemini + OpenAI (Go local circuit-breaker state) and the five Python providers (via `/v1/providers`), in one response with cooldown info.
2. Python is wired into the existing `ModelRouter` as one `providerEntry`, giving platform-level failover across gemini ↔ openai ↔ python (two-level routing: Go platform-level, Python internal); strict timeout layering (Go→Python > Python→LLM) keeps the levels from fighting; Python reports usage, Go records cost — one cost ledger.
3. Rate limiting, per-school quota enforcement, and AI-usage audit events (SchoolID, UserID, Action, ResourceType, RequestID) are enforced on EVERY AI endpoint — existing and new — from the first orchestrator delivery (INT-03's controls are the FIRST plan of this phase, not a hardening bolt-on); a noisy school cannot starve others; violations return clear 429s.
4. Redis prompt/response caching is tenant-scoped (`school_id` in every key); retries + circuit breakers protect Python calls with error classification (429 → failover, never retry same provider; 5xx/timeout → retry once then failover; other 4xx → permanent, no failover); per-request cost caps and per-tenant daily spend caps trip before spend.

## Decisions (locked this discussion — all gray areas deferred to agent, recorded below)

### INT-03 ordering
- **D-01:** INT-03 controls are the FIRST plan of Phase 5. No AI endpoint — existing (`/ai/chat`, `/ai/search`, `/ai/agents`) or new (`/ai/chat/stream`, `/ai/documents*`, `/ai/providers`) — is exposed without the orchestrator layer. This is a ROADMAP + STATE.md locked decision; do not re-argue.

### Rate limiting (INT-03)
- **D-02:** AI-specific rate limiting lives in a NEW middleware/helper applied to the `ai` route group (all `/api/v2/ai/*` endpoints), layered ON TOP of the existing global `middleware.RedisRateLimit` (which stays as the coarse API-level guard). Reuse the existing Redis-backed `RateLimiter` (sliding window) — do NOT build a second limiter. Keys are `ai:rl:{scope}:{school_id}:{user_id}` and `ai:rl:{scope}:{school_id}` (per-school + per-user), and the per-school limit is the hard guard so a noisy school cannot starve others (ROADMAP criterion 3).
- **D-03:** Limits are configurable via `config.AI.RateLimit` (new fields: per-user-per-min, per-school-per-min, per-day school spend cap) with sane defaults (e.g. per-school 300 req/min, per-user 60 req/min for chat-class endpoints; streaming and docs get their own scope caps). No plan-tier variability in v1 — flat defaults, tier-based limits deferred (agent discretion: keep simple, the existing `RateLimitConfig.Tiers` is for the global middleware).
- **D-04:** Violations return `429 Too Many Requests` with `Retry-After` header and the standard `response.Error` envelope (`category: rate_limit`). Frontend gets one contract: 429 with a retry hint.

### Quota & spend governance (INT-03)
- **D-05:** Per-school daily spend cap is enforced PRE-flight (check Redis counter before calling provider; 429 if exhausted) and POST-call (increment Redis counter atomically with the recorded cost). Counter key: `ai:quota:school:{school_id}:{YYYY-MM-DD}`. Default cap is `0` = unlimited unless `AI_QUOTA_DAILY_SPEND_CENTS` set or per-school override applied (deferred: per-school admin override is a Phase-6 admin surface; v1 ships the global default via config). 
- **D-06:** Per-request cost cap (ROADMAP criterion 4) is enforced in the orchestrator BEFORE the call using an estimated cost cap from token budget (`opts.MaxTokens`) — reject pre-call if estimated spend > cap; exact post-call cost reconciliation still increments quota. Agent discretion on exact estimation math (use `CalculateCost` with max-tokens worst case).
- **D-07:** Overage behavior = hard 429 (same envelope as D-04) with `Retry-After`; violation is logged (logger.Warnf with school_id) and a Prometheus counter increments. Admin dashboard notification deferred to Phase 6 (D-09 pattern from Phase 4 — monitor via metrics/logs now, dashboards later).

### One cost ledger (INT-03/INT-04)
- **D-08:** Cost recording is UNIFIED: Python's normalized usage payload (provider, model, input/output tokens, cost — Phase 3 contract) is translated into the SAME `ai.CostConfig`/`CalculateCost` shape Go already uses for Gemini/OpenAI, and ONE ledger records every AI call. Storage: shared `public` schema table `ai_usage_log` (new core migration, `ai_conversations` precedent) with columns school_id, user_id, provider, model, input_tokens, output_tokens, cost_cents, request_id, created_at. The table is the durable audit-grade ledger; Redis counters (D-05) are the fast pre-flight check. This is SEPARATE from the B11 audit trail — audit events record *who did what*; `ai_usage_log` records *what it cost*.
- **D-09:** Retention: keep all rows in v1 (no pruning); Phase 6 owns dashboards/retention. Every AI mutation already emits a B11 audit event — do not double-insert audit data into `ai_usage_log`.

### Redis caching (INT-03)
- **D-10:** Cacheable: non-streaming chat (`/ai/chat`), search (`/ai/search`), and providers status (`/ai/providers`, short TTL). NOT cacheable: `/ai/chat/stream` (never cache SSE), `/ai/documents*` (mutations), `/ai/agents` (static, not worth it).
- **D-11:** Cache key is tenant-scoped ALWAYS: `ai:cache:{school_id}:{endpoint}:{sha256(prompt+model)}`. User is NOT in the key (cross-user cache within a school is the cost win; tenant isolation is the hard boundary — a school NEVER sees another school's cache). TTL: chat 10min, search 5min, providers 15s. Cache hit is transparent to the client (no "cached" marker) — identical response shape.
- **D-12:** Cache writes happen AFTER successful provider response; cache errors (Redis down) are log-and-continue (B9) — never fail the request on cache failure. `X-Cache: HIT/MISS` header optional (agent discretion — include it, costs nothing, aids debugging).

### Two-level failover / ModelRouter (INT-04)
- **D-13:** Python is wired into `ModelRouter` as a set of `providerEntry`s — one per Python provider (anthropic, deepseek, openrouter, azure-openai, ollama) — implemented as a `pythonProvider` that adapts the `EngineClient` seam (`Chat`/`ChatStream`/`Embed`) to the `ai.Provider` interface. ProviderType grows: `ProviderPython` with a per-entry subtype (e.g. `python:anthropic`). Model matching in `resolveProvider` keeps working (it already does `strings.Contains(model, pType)`).
- **D-14:** Two-level routing: Go `ModelRouter` is the PLATFORM-level failover (gemini ↔ openai ↔ python:provider). Python's internal provider selection stays inside the Python engine — Go does NOT peer inside Python; Go picks `python:anthropic` or `python:deepseek` etc. as discrete entries and lets its own breaker/failover run. Error classification (ROADMAP criterion 4) at the Go boundary: 429 → mark breaker failure, failover to NEXT provider, NEVER retry same; 5xx/timeout → retry once, then failover; other 4xx → permanent, no failover, surface to caller.
- **D-15:** Strict timeout layering: Go→Python call budget MUST exceed Python→LLM budget. Python chat timeout 30s already set in client.go; orchestrator adds an overall Go-side guard on the provider call (e.g. 35s for chat, stream context-bound per FND-03) so the two levels never fight. Document the invariant in code.
- **D-16:** Streaming + failover: on SSE stream, if the selected Python provider fails BEFORE first byte, Go may failover to another provider transparently (reselect at ModelRouter level); after first byte, no failover — the stream is committed (Phase 4 relay already handles in-band errors). This matches INT-01's "engine errors after HTTP 200 are in-band error events" contract.

### Agent's Discretion (explicitly delegated this discussion)
- Exact config field names/defaults for `config.AI.RateLimit`/`AI_QUOTA_*`
- Estimation math for pre-call cost cap (D-06)
- Whether `pythonProvider` reuses `newGuardedProvider` or composes breaker directly (planner picks — must reuse `CircuitBreaker`)
- `X-Cache` header inclusion (D-12 recommends yes)
- Plan-tier rate variability (D-03 recommends flat in v1)

## Existing State (verified this session)

### Go AI layer (Phase 1-4, EXTEND — do NOT rewrite)
- `backend/internal/ai/model_router.go`: `ModelRouter` (Provider impl), `providerEntry{provider, pType, breaker}`, `resolveProvider` (model-prefix match, else first non-open breaker), `fallbackProviders(skip)`, `addProvider` (**currently `//nolint:unused`** — INT-04 calls it)
- `backend/internal/ai/circuit_breaker.go`: `CircuitBreaker` — `State()` (Closed/Open/HalfOpen), `Allow()`, `Success()`, `Failure()`, `DefaultCircuitBreakerConfig{Threshold:5, Cooldown:30s}`
- `backend/internal/ai/gateway.go`: `ProviderType` (ProviderGemini, ProviderOpenAI — **no Python yet**), `Provider` interface (`GenerateText`, `GenerateTextStream`, `GenerateEmbedding(s)`, `CountTokens`, `Close`), `newGuardedProvider` wrapper
- `backend/internal/ai/cost.go`: `CostConfig{PromptTokens, CompletionTokens}`, `defaultCosts` (Gemini/OpenAI), `CalculateCost(inputTokens, outputTokens, provider, cfg)`; `AIServiceConfig.CostPerPromptToken/CompletionToken` overrides
- `backend/internal/ai/config.go`: `EngineURL`, `EngineToken`, `AI_EMBEDDING_DIM` etc.
- `backend/internal/ai/metrics.go`, `tracing.go`, `gateway.go` recordMetrics — metrics precedent
- `backend/internal/ai/engine/`: `EngineClient` seam — `Chat`, `ChatStream(ctx, req, cb)`, `Extract`, `Health`, `IngestDocument` (Phase 4); `EngineEvent{Type, Data}`; `StatusError{StatusCode, Body}`; `client.go` timeouts chat 30s/extract 5m/health 10s; **`ChatStream` NO timeout (context-bound FND-03)**
- `backend/internal/router/setup.go` (~line 170): `aiProvider ai.Provider` from provider config; `newAIScoringHandler(db, aiProvider)`; single `engine.NewClient` wired in Phase 4; AIHandler `WithEngineClient` + `WithDocumentService` + `WithAuditLogger`
- `backend/internal/modules/ai/`: `handler.go` (Chat/ListAgents/Search/UploadDocument/GetDocumentStatus/StreamChat), `stream.go` (SSE relay), `service.go`/`repository.go`/`dto.go` (Phase 4)

### Existing middleware / infra
- `backend/internal/middleware/ratelimit.go`: `SimpleLimiter` (in-memory legacy) + **`RateLimiter` Redis-backed sliding window** (`Allow(ctx, key) (bool, retryAfterSec, count, limit, error)`), `RateLimit(limit, window)` and `RedisRateLimit(cfg, rdb)` gin middlewares — applied globally at `router.go:128-130` (`v2.Use(RedisRateLimit)` + `RateLimit`) and `setup.go:936-938` (`api.Use`). `config.RateLimitConfig{DefaultIP RateLimitTier, Tiers map[string]RateLimitTier}` with `GetTier(plan)`.
- **NO quota code exists anywhere** (grep verified — `quota`/`Quota` zero matches in backend/internal)
- **NO AI cache exists** (grep verified — no Redis cache in modules/ai or engine client)
- Audit: `backend/internal/middleware/audit.go` `AuditLogger`; AIHandler has `WithAuditLogger` (B11) — the `ai` route group does NOT use the AuditLogging middleware (handler-level audit)
- `backend/pkg/response`: `Success`, `SuccessWithPagination`, `Error(c, status, code, message, category)`, `ErrorWithDetails`
- `backend/pkg/logger`: `logger.Infof/Warnf/Errorf/Fatalf`
- Redis client `rdb` already wired in setup.go/router.go

### Python engine (Phase 3, read-only for this phase)
- `ai-engine/app/api/providers.py`: `GET /v1/providers` → `{"providers": [{provider, status, latency_ms, last_checked, cooldown_until}]}` (D-10 contract)
- `ai-engine/app/api/chat.py`: `POST /chat` + `POST /chat/stream`; normalized usage payload `{provider, model, input/output tokens, cost}` on every ChatResponse (Phase 3 D-03)
- Providers: anthropic, deepseek, openrouter, azure-openai, ollama (direct SDKs, no gateway)

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Go AI layer (read before extending)
- `backend/internal/ai/model_router.go` — ModelRouter resolve/fallback logic INT-04 extends
- `backend/internal/ai/circuit_breaker.go` — breaker reused for Python entries
- `backend/internal/ai/gateway.go` — ProviderType/Provider interface/newGuardedProvider
- `backend/internal/ai/cost.go` — CalculateCost shape for the unified ledger
- `backend/internal/ai/engine/engine.go` + `client.go` — EngineClient seam (StatusError, timeouts)
- `backend/internal/middleware/ratelimit.go` — existing RateLimiter to reuse (D-02)
- `backend/internal/router/setup.go` + `router.go` — where aiProvider, engine client, rdb are wired; `ai` route group
- `backend/internal/modules/ai/{handler,stream,service,repository,dto}.go` — endpoints to govern
- `backend/internal/database/migrations/core/ai.go` — shared/public migration precedent for `ai_usage_log` (D-08)
- `backend/internal/database/migrations/core/ai_documents.go` — Phase 4 shared migration precedent
- `backend/internal/database/models/ai_document.go` — shared-schema model precedent
- `backend/pkg/response`, `backend/pkg/logger` — response/logging contracts

### Python engine (read for contract shapes)
- `ai-engine/app/api/providers.py` — /v1/providers response shape (INT-02 merge)
- `ai-engine/app/api/chat.py` — normalized usage payload (D-08 translation)

### No external specs
- No external specs — requirements fully captured in decisions above. (Prior decisions locked in STATE.md: INT-03 first plan, two-level routing, service token only, 429s, strict timeout layering.)

## Deferred Ideas

- Admin dashboard for quotas/spend (Phase 6 — OBS-01 Grafana + admin surface)
- Per-school quota override UI (Phase 6 admin surface)
- Plan-tier-based AI rate limits (D-03 — flat in v1)
- Cache invalidation on document re-ingest (post-Phase 5; cacheable search results are TTL-based in v1)
- `ai_usage_log` retention/pruning (Phase 6)

## Exit Criteria

- [ ] All 4 ROADMAP success criteria demonstrated (combined providers endpoint; Python in ModelRouter with two-level failover + timeout layering; rate limit + quota + audit on EVERY AI endpoint with clear 429s; tenant-scoped cache + error-classified retries + cost caps)
- [ ] INT-02, INT-03, INT-04 checked in REQUIREMENTS.md
- [ ] Go suite passes (all tests incl. new orchestrator/ModelRouter/cache/quota tests); ruff/pyright clean for any Python touch
- [ ] Phase 5 VERIFICATION passed (verifier agent), STATE.md/ROADMAP.md updated
