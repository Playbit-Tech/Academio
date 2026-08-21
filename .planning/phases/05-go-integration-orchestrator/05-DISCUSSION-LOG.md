# Phase 5: Go Integration & Orchestrator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-01
**Phase:** 5-go-integration-orchestrator
**Areas discussed:** Rate limiting, Quota & spend governance, One cost ledger, Caching semantics, Two-level failover (all 5 gray areas **delegated to agent discretion** — user selected "you decide for all")

---

## Rate limit enforcement model

| Option | Description | Selected |
|--------|-------------|----------|
| AI-specific middleware reusing Redis RateLimiter | New middleware on the `ai` route group, per-school + per-user keys, layered over global RedisRateLimit | ✓ |
| Per-endpoint quota checks in handlers | Inline checks per handler — duplicates middleware work | |
| Plan-tier variability in v1 | Vary limits by school plan via RateLimitConfig.Tiers | (deferred) |

**User's choice:** You decide for all (delegated to agent)
**Notes:** Agent selected AI-specific middleware (D-02), flat defaults in v1 (D-03), 429 + Retry-After envelope (D-04). Grounded in existing `middleware.RateLimiter` (sliding window Redis) — reuse, never build a second limiter.

---

## Quota & spend governance

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight check + post-call atomic increment | Redis counter per school/day; hard 429 before spend when exhausted | ✓ |
| Post-spend alarm only | Allow overage, alert after | |
| Hard 429 vs soft warn | Block vs warn-and-continue | ✓ (hard 429) |

**User's choice:** You decide for all (delegated to agent)
**Notes:** D-05 (per-school daily cap via Redis, default 0=unlimited, config `AI_QUOTA_DAILY_SPEND_CENTS`), D-06 (per-request pre-call estimated cap from MaxTokens worst-case via CalculateCost), D-07 (hard 429 + logger.Warnf + Prometheus counter; dashboards deferred to Phase 6). OWASP LLM guardrail rationale from INT-03.

---

## One cost ledger

| Option | Description | Selected |
|--------|-------------|----------|
| DB-persisted shared `ai_usage_log` + Redis fast counters | Durable audit-grade ledger + fast pre-flight quota checks | ✓ |
| Redis counters only | Fast, lossy, not auditable | |
| Merge into B11 audit trail | One table for both | (rejected — separate concerns) |

**User's choice:** You decide for all (delegated to agent)
**Notes:** D-08 (new shared/public `ai_usage_log` core migration, `ai_conversations` precedent, columns school_id/user_id/provider/model/tokens/cost_cents/request_id/created_at; Python normalized usage translated to same shape), D-09 (retention all-in-v1, Phase 6 dashboards; audit events and cost ledger are separate tables).

---

## Caching semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Tenant-scoped Redis cache: chat + search + providers(short) | Key `ai:cache:{school_id}:{endpoint}:{sha256(prompt+model)}`; TTL chat 10m/search 5m/providers 15s | ✓ |
| Cache everything incl. streaming | SSE cache = broken | (rejected) |
| Reveal cache hits to client | `X-Cache` header vs transparent | ✓ (X-Cache header, transparent body) |

**User's choice:** You decide for all (delegated to agent)
**Notes:** D-10 (cacheable set), D-11 (tenant-scoped keys, user NOT in key, cross-user within school is the win), D-12 (write-after-success, log-and-continue on Redis errors B9).

---

## Two-level failover semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Python as discrete providerEntries in ModelRouter | One entry per Python provider (python:anthropic, python:deepseek...), Go platform-level failover, error classification at Go boundary | ✓ |
| Python as single opaque entry | Go doesn't see individual providers — loses failover granularity | |
| Failover to Go-native on Python failure | gemini/openai as final fallback layer | ✓ (as last-resort entries, not first) |

**User's choice:** You decide for all (delegated to agent)
**Notes:** D-13 (pythonProvider adapter over EngineClient seam; ProviderType grows with python:subtype), D-14 (two-level routing — Go never peers inside Python; 429 → failover-no-retry-same, 5xx/timeout → retry once then failover, other 4xx permanent), D-15 (timeout layering invariant Go→Python > Python→LLM, ~35s Go guard vs 30s Python chat), D-16 (streaming: failover only before first byte, committed after — matches Phase 4 in-band error contract).

## the agent's Discretion

User delegated all 5 gray areas ("you decide for all"). Locked decisions recorded in CONTEXT.md with explicit rationale grounded in the codebase scout:
- Reuse existing `middleware.RateLimiter` (D-02)
- Flat limits v1, no plan tiers (D-03)
- Default quota 0 = unlimited unless configured (D-05)
- New shared `ai_usage_log` table (D-08)
- Cache key excludes user, includes school_id (D-11)
- Python = discrete providerEntries with `python:` subtype (D-13)
- Timeout layering ~35s guard vs 30s Python (D-15)
- Stream failover only pre-first-byte (D-16)

## Deferred Ideas

- Admin dashboard for quotas/spend (Phase 6 — OBS-01)
- Per-school quota override UI (Phase 6)
- Plan-tier-based AI rate limits (flat in v1)
- Cache invalidation on document re-ingest
- `ai_usage_log` retention/pruning (Phase 6)
