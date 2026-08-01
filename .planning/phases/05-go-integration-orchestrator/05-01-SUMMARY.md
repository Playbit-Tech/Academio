---
phase: 05-go-integration-orchestrator
plan: 01
subsystem: ai
tags: [ai, rate-limit, quota, cost-ledger, cache, go, gin, redis, gorm]

# Dependency graph
requires:
  - phase: 04-go-streaming-pipeline
    provides: SSE relay seam (engine.ChatStream), ai route group, AIHandler, engine client
provides:
  - AI Orchestrator middleware (per-school/user rate limiting, D-02/D-03/D-04)
  - AIOrchestratorService (quota pre-flight D-05/D-06, tenant-scoped cache D-10/D-11, cost ledger D-08, timeout layering D-15)
  - ai_usage_log migration + model (unified cost ledger, public schema)
  - Post-call RecordUsage wiring on Chat and Search handlers
  - Orchestrator-routed GenerateText/GenerateTextStream wrappers (D-16 seam for 05-02)
affects: [05-go-integration-orchestrator plans 02 and 03, frontend AI UI, python ai engine]

# Tech tracking
tech-stack:
  added: none (reuses go-redis, gorm, existing ai.CalculateCost, existing CacheService)
  patterns:
    - Middleware-as-guard: fine-grained rate limiting layered after auth, before handler
    - Service-as-orchestrator: quota pre-flight + cache + ledger + timeout all in one DI service
    - Post-call ledger: RecordUsage called from handler after successful provider response

key-files:
  created:
    - backend/internal/middleware/ai_orchestrator.go
    - backend/internal/middleware/ai_orchestrator_test.go
    - backend/internal/services/ai_orchestrator_service.go
    - backend/internal/services/ai_orchestrator_service_test.go
    - backend/internal/database/migrations/core/ai_usage_log.go
    - backend/internal/database/models/ai_usage_log.go
    - backend/internal/database/models/ai_usage_log_test.go
  modified:
    - backend/internal/config/config.go
    - backend/internal/config/config_test.go
    - backend/internal/database/migrations/core/core.go
    - backend/internal/database/models/schema.go
    - backend/internal/modules/ai/handler.go
    - backend/internal/router/router.go
    - backend/internal/router/setup.go

key-decisions:
  - "Streaming stays on the engine relay seam (engine.ChatStream) in this plan — it is context-bound (FND-03), preserves the Phase 4 SSE envelope (delta/citation/usage), and provider-routing only becomes correct in 05-02 when Python providers join the ModelRouter. Applying a fixed Go-side timeout to the whole SSE session would kill legitimately long streams."
  - "Rate limiting uses the existing shared Redis RateLimiter (sliding window) with ai:rl:{scope}:{school_id} and ai:rl:{scope}:{school_id}:{user_id} keys — never a second limiter."
  - "Quota counters use Redis INCRBY (atomic, T-05-02); ledger is source of truth; Redis increment errors are log-and-continue (B9)."
  - "Config validation fails fast on <=0 rate limits and negative quota caps (Rule B12); 0 quota = unlimited by design."
  - "Cost ledger in public schema (shared, no PII) per T-05-03; audit trail (B11) remains the who-did-what record."

patterns-established:
  - "Middleware-guard pattern: rate limit + quota pre-flight live in middleware; cache read/write, ledger write, and timeout layering live in the service; handlers do post-call RecordUsage."
  - "Fail-open on Redis availability for quota pre-flight but fail-loud on ledger writes (durable audit, B9 state-mutation rule)."
  - "Provider seam: orchestrator holds ai.Provider interface; WithProvider attaches it; GenerateText/GenerateTextStream are the D-16 routing entry points for 05-02."
