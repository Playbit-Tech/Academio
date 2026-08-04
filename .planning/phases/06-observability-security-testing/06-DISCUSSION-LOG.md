# Phase 6: Observability, Security & Testing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-04
**Phase:** 06-observability-security-testing
**Areas discussed:** PII masking boundary, AI config encryption, RAG eval harness, cross-tenant probe scope, metrics/log correlation

---

## Discussion Mode

The user invoked `/gsd-next` which routed to discuss-phase for Phase 6. When presented with the five gray areas, the user responded **"you decide"** — delegating all decisions to the agent. All decisions below were therefore made by the agent, grounded in the existing codebase (scouted: metrics.go, crypto/encryption.go, monitoring/, test suites, CI workflows) and prior-phase context (Phase 5 CONTEXT.md + REVIEW.md).

## PII Masking Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Log-layer only | Mask document/prompt content in logs (sizes/hashes) | ✓ |
| Also mask API responses | Sanitize error messages returned to clients | ✓ (via existing `_sanitize_error_message` + Go error sanitization) |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-04 — document contents and prompt bodies never appear in logs (Go or Python); sizes/hashes only. Error messages sanitized. Student/teacher PII not logged in AI observability paths.

## AI Config Encryption

| Option | Description | Selected |
|--------|-------------|----------|
| Encrypt DB-persisted AI secrets | Use existing crypto.Service (AES-256-GCM) for any AI secret stored in DB | ✓ |
| Python provider keys stay env-injected | Container secrets, never committed/logged, fail-fast validation | ✓ |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-05 — reuse `crypto/encryption.go`. Python provider keys remain env-injected (not DB-stored in v1); add startup fail-fast validation. `AI_ENGINE_TOKEN` env-only, never logged.

## RAG Eval Harness

| Option | Description | Selected |
|--------|-------------|----------|
| Hermetic pytest suite in ai-engine/tests/rag_eval/ | Golden JSONL set, deterministic context precision + LLM-judge faithfulness | ✓ |
| CI on chunking/embedding/prompt changes | New rag-eval.yml workflow, gates ≥0.85/≥0.75 | ✓ |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-07 — context precision deterministic (no LLM); faithfulness via LLM-as-judge with stub for hermetic CI, real judge nightly (deferred).

## Cross-Tenant Probe Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Hermetic seeded tenants in CI | school_1/school_2, adversarial queries across all retrieval entry points | ✓ |
| Go probes package + Python pytest | backend/internal/security/probes + DB-gated pytest | ✓ |
| Kill-worker-mid-pipeline in Go | asynq worker test: zero duplicate vectors, exactly one notification | ✓ |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-08 — covers search, cache, reranking, agent tools, worker paths. Load via existing k6 at 10× peak.

## Metrics/Log Correlation

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing promauto registry | Add cache_hits, fallback, cost_per_task, quota_rejections families | ✓ |
| request_id in JSON logs end-to-end | Go slog + Python JSON formatter, propagated via existing seam | ✓ |
| Grafana dashboard provisioning | AI Pipeline Health dashboard in monitoring/grafana/ | ✓ |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-01/D-02/D-03 — extend metrics.go, correlate via request_id, ship Grafana dashboard.

## Phase 5 Review Hardening

| Option | Description | Selected |
|--------|-------------|----------|
| Fold in MA-01/MA-02/MA-03 | Fix cost-cap dead code, stream error classification, pythonProvider param drops | ✓ |
| ai_usage_log retention + quota panels | Configurable retention (keep-all default), Grafana quota/spend panels | ✓ |

**User's choice:** Agent discretion ("you decide")
**Notes:** D-09 — hardening fixes carried into this phase; not new capabilities.

## Deferred Ideas

- Per-school quota override admin UI (Phase 5 deferred)
- Plan-tier-based AI rate limits
- Cache invalidation on document re-ingest
- Real LLM-judge faithfulness in CI (nightly)
- `ai_usage_log` retention pruning job