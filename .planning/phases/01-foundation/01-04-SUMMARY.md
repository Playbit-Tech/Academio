---
phase: 01-foundation
plan: 04
subsystem: config
tags: [go, config, env, fail-fast, ai-engine, service-auth]
requires:
  - phase: 01-foundation
    provides: Go↔Python engine seam decision (Plan 02 research): engine carries ALL AI traffic; token travels in X-AI-Engine-Token header only
provides:
  - AIConfig.EngineURL/EngineToken with unconditional fail-fast validate() checks (Rule B12, FND-04)
  - AIServiceConfig + FromAppConfig pass-through for future EngineClient consumers (Phase 4/5)
  - .env.example documents AI_ENGINE_URL/AI_ENGINE_TOKEN as REQUIRED; local .env has working dev values
affects: [Plan 03 compose api env, FND-03 EngineClient seam, Phase 4 document pipeline, Phase 5 orchestrator]

tech-stack:
  added: []
  patterns:
    - "Unconditional fail-fast config validation for required infrastructure vars (no AI_ENABLED gate)"
    - "Secrets use empty getEnv fallback — never insecure defaults (Rule B6)"
    - "url.Parse + scheme whitelist (http/https) + non-empty Host for service URLs"

key-files:
  created: []
  modified:
    - backend/internal/config/config.go
    - backend/internal/config/config_test.go
    - backend/internal/ai/config.go
    - backend/.env.example
    - backend/.env (gitignored, local-only)

key-decisions:
  - "AI engine seam validation is UNCONDITIONAL in validate() — not gated on AI_ENABLED, not in validateProduction() — because the seam carries all future AI traffic (FND-04/SC4, decision resolved from RESEARCH.md)"

patterns-established:
  - "Required infrastructure config (service seams) validates unconditionally at startup; provider-optional config stays gated"

requirements-completed: [FND-04]

duration: 5min
completed: 2026-07-31
---

# Phase 01 Foundation Plan 04: AI Engine Seam Config Summary

**Unconditional fail-fast AI_ENGINE_URL/AI_ENGINE_TOKEN config validation in the Go backend (Rule B12), with AIServiceConfig pass-through and documented required vars in .env.example and local .env**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-31T21:16:02Z
- **Completed:** 2026-07-31T21:17:48Z
- **Tasks:** 2
- **Files modified:** 5 (4 committed + .env gitignored local)

## Accomplishments

- `AIConfig` gains `EngineURL`/`EngineToken` (`env:"AI_ENGINE_URL"` / `env:"AI_ENGINE_TOKEN"`) bound via `getEnv` with `""` fallback — no insecure default for the token (Rule B6)
- `validate()` now rejects, unconditionally and in ALL environments: empty `AI_ENGINE_URL`, non-http(s) `AI_ENGINE_URL` (via `url.Parse` + scheme whitelist + non-empty Host), and empty `AI_ENGINE_TOKEN` — satisfying FND-04 (fails fast at startup when either var is missing or invalid)
- `AIServiceConfig` + `FromAppConfig` expose both values so the future EngineClient (FND-03, Phase 4/5) can build the engine client
- `.env.example` header now lists all four required vars; AI block documents both vars as REQUIRED with dev values; local `.env` has matching `AI_ENGINE_URL=http://localhost:8000` + `AI_ENGINE_TOKEN=local-dev-token` (matches Plan 03 compose default `${AI_ENGINE_TOKEN:-local-dev-token}`)
- Config test suite extended: valid fixture now includes AI values; 3 new negative subtests (missing URL, missing token, invalid URL) — all green alongside existing JWT/Encryption negative tests (error-precedence preserved)

## Task Commits

Each task was committed atomically in the backend submodule repo (branch `dev`):

1. **Task 1: Add EngineURL/EngineToken to AIConfig + unconditional validate()** - `c5b43a9` (feat)
2. **Task 2: Extend AIServiceConfig + document vars in .env.example and .env** - `45b8977` (feat)

## Files Created/Modified

- `backend/internal/config/config.go` - AIConfig struct fields (111-112), fromEnv bindings (319-320), unconditional validate() checks (428-437)
- `backend/internal/config/config_test.go` - updated valid fixture + 3 new negative subtests in TestLoad_Validation
- `backend/internal/ai/config.go` - AIServiceConfig EngineURL/EngineToken fields + FromAppConfig pass-through
- `backend/.env.example` - required-vars header update + active AI engine seam block (lines 106-114)
- `backend/.env` - matching active dev values appended (gitignored, local-only)

## Decisions Made

- **Unconditional validation placement (locked in this plan):** The engine seam checks live in `validate()` — not `validateProduction()`, not gated on `c.AI.Enabled`. Rationale: SC4 states fail-fast with no AI_ENABLED qualifier, and the seam is required infrastructure like the Gotenberg URL family. This resolves the open question flagged in RESEARCH.md section "Config + fail-fast".

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. (One minor edit-disambiguation: the initial validate() edit matched both validate() and validateProduction() blocks; resolved by adding surrounding context — no code change impact.)

## User Setup Required

None - no external service configuration required. The local `.env` already carries the working dev values; production must supply real values via secrets (documented in .env.example).

## Next Phase Readiness

- FND-04 satisfied: backend fails fast at startup when `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` missing or invalid, in all environments
- Plan 03 compose `api` env carries the vars (`AI_ENGINE_URL=http://ai-engine:8000` + shared token default) — validation passes in compose
- AIServiceConfig now carries the seam values for FND-03 EngineClient construction (Phase 4/5 consumers)
- Token is config/env-only — never in code, never in URL (X-AI-Engine-Token header contract enforced in Plan 02 / Phase 4)

## Threat Surface

No new network endpoints, auth paths, file access, or schema changes introduced — config-only change at the env→config trust boundary. All four threats in the plan register (T-04-01 empty token, T-04-02 invalid URL, T-04-03 dev placeholder token in gitignored .env, T-04-05 validation ordering) are mitigated as specified; T-04-04 (token in memory) accepted per existing API-key pattern.

---
*Phase: 01-foundation*
*Completed: 2026-07-31*

## Self-Check: PASSED

- FOUND: backend/internal/config/config.go, backend/internal/config/config_test.go, backend/internal/ai/config.go, backend/.env.example
- FOUND: 01-04-SUMMARY.md
- FOUND: commit c5b43a9 (Task 1), commit 45b8977 (Task 2) in backend submodule (branch dev)
- FOUND: .env contains active AI_ENGINE_URL + AI_ENGINE_TOKEN dev values
