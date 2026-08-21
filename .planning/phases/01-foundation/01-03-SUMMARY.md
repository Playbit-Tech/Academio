---
phase: 01-foundation
plan: 03
subsystem: infra
tags: [docker-compose, ai-engine, fastapi, internal-network, healthcheck, service-auth, uploads-volume]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: ai-engine Dockerfile serving uvicorn on :8000 with unauthenticated GET /health (Plan 01); unconditional AI_ENGINE_URL/AI_ENGINE_TOKEN fail-fast config validation on the Go side (Plan 04)
provides:
  - ai-engine service in the standard backend compose stack — internal-network only (NO published host port), health-checked via stdlib-urllib against unauthenticated /health
  - api service env wired with AI_ENGINE_URL=http://ai-engine:8000 + shared AI_ENGINE_TOKEN (default local-dev-token) so the FND-04 unconditional validation passes when the api container runs
  - shared uploads_data volume mounted at /app/uploads on BOTH api and ai-engine (file-passing by path for the future document pipeline)
  - live-verified container lifecycle: build -> healthy boot (~4s) -> no host port (docker inspect + host curl refused) -> 200/401/200 endpoint matrix -> scoped cleanup
affects: [FND-05 CI, Phase 3 Python endpoints (/v1/* behind token), Phase 4 document pipeline (PIP-01 shared volume), Phase 5 orchestrator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Internal-infrastructure compose service: NO ports: mapping — engine reachable only on the compose network by the Go backend (same posture as qdrant/gotenberg internal links)"
    - "Healthcheck with python stdlib urllib one-liner (python:3.13-slim ships no curl), timeout=3 + start_period — hung uvicorn boot detected without starving CPU"
    - "No depends_on api -> ai-engine — backend boots while engine is down; circuit breaker handles runtime outages (stack decoupling)"
    - "Shared named volume uploads_data mounted identically (/app/uploads) on both services — future doc-pipeline file passing by path"

key-files:
  created: []
  modified:
    - backend/docker-compose.yml

key-decisions:
  - "ai-engine gets NO published host port (T-03-02): multi-tenant security posture — an unauthenticated liveness endpoint and token-auth'd AI endpoints must never be reachable from host/internet"
  - "Healthcheck uses python urllib, not curl -f — python:3.13-slim ships no curl (unlike qdrant/gotenberg images); targets the unauthenticated GET /health so the check needs no token"
  - "No depends_on api -> ai-engine (T-03-05): Go backend starts even if engine is down — env-based config validation, not connectivity-based; circuit breaker handles runtime outages; engine build failure cannot take down the stack"
  - "api env carries AI_ENGINE_URL/AI_ENGINE_TOKEN because Plan 04 makes engine config validation unconditional — without them the api container would crash-loop on startup"
  - "Compose token default ${AI_ENGINE_TOKEN:-local-dev-token} matches the .env dev value from Plan 04, so host-run and compose-run tokens agree (T-03-01)"

patterns-established:
  - "Pattern: internal-only service definition — no ports, urllib healthcheck, shared uploads volume, env-driven service discovery by compose DNS name"
  - "Pattern: compose defaults for dev tokens via \${VAR:-default} interpolation, same value written to backend/.env (single source of truth)"

requirements-completed: [FND-02]

# Metrics
duration: 3min
completed: 2026-07-31
---

# Phase 01 Foundation Plan 03: ai-engine Compose Service Summary

**ai-engine wired into the backend compose stack as an internal-only, health-checked service (build ../ai-engine, no host port, python-urllib /health check, shared uploads_data volume) with api env carrying AI_ENGINE_URL=http://ai-engine:8000 + shared token — live-verified: image builds, container boots healthy in ~4s, host connection refused (no port leak), /health 200 / /v1/health 401→200 endpoint matrix passes, scoped cleanup leaves the shared stack untouched**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-31T21:33:20Z
- **Completed:** 2026-07-31T21:36:25Z
- **Tasks:** 2
- **Files modified:** 1 (backend/docker-compose.yml)

## Accomplishments
- `ai-engine` service added to `backend/docker-compose.yml`: build context `../ai-engine`, `container_name: academio-ai-engine`, `restart: unless-stopped`, `AI_ENGINE_TOKEN` env with `${AI_ENGINE_TOKEN:-local-dev-token}` default, `uploads_data:/app/uploads` volume, and a stdlib-urllib healthcheck against the unauthenticated `GET /health` (interval 10s, timeout 5s, retries 5, start_period 10s)
- **NO `ports:` mapping** — verified decisively in Task 2: `docker inspect` shows `HostConfig.PortBindings: {}` and `NetworkSettings.Ports: {"8000/tcp":null}`, and a host-level `curl localhost:8000/health` is refused (connection refused) — the engine is reachable only inside the compose network (T-03-02 mitigated)
- `api` service env extended with `AI_ENGINE_URL: http://ai-engine:8000` and `AI_ENGINE_TOKEN: "${AI_ENGINE_TOKEN:-local-dev-token}"` — required by Plan 04's unconditional fail-fast validation so the compose-run api container does not crash-loop
- **No `depends_on` added** — api's depends_on still lists only postgres/redis/gotenberg (T-03-05: stack decoupling; circuit breaker handles engine downtime)
- Live container lifecycle proven: `docker compose build ai-engine` exit 0 (multi-stage python:3.13-slim), `up -d ai-engine` started ONLY ai-engine (no other compose service pulled in), healthy in ~4s (budget 60s), in-container `/health` → 200 `{"status":"ok","service":"ai-engine"}`, `/v1/health` → 401 without token / 200 with `X-AI-Engine-Token`, then `rm -sf ai-engine` removed only the container (image kept for fast rebuilds)
- Shared stack untouched: `shared-postgres` (healthy) and `shared-redis` remained up for the entire run; no other compose container was ever started or stopped

## Task Commits

Each task was committed atomically in the backend submodule repo (branch `dev`):

1. **Task 1: Add ai-engine service + api env wiring** - `9e13eee` (feat)
2. **Task 2: Build, start, verify, and clean up the ai-engine container** - no commit (runbook verification task; zero file delta — compose file needed no further edits after Task 1)

**Plan metadata:** n/a — `.planning/` is gitignored and `commit_docs: false`; no metadata commit per repo policy.

_Note: Task 2 was a pure verification runbook (build → up → healthy → port/endpoint matrix → scoped cleanup). All acceptance criteria passed on the first run, so it produced no file changes to commit._

## Files Created/Modified
- `backend/docker-compose.yml` - +19 lines: api env additions (`AI_ENGINE_URL`, `AI_ENGINE_TOKEN`) and new `ai-engine` service block inserted between the api block and `prometheus:`

## Decisions Made
- Followed plan exactly — all architectural decisions were pre-locked in research and applied verbatim:
  - No `ports:` on ai-engine (internal network only; security posture)
  - urllib healthcheck instead of curl (python:3.13-slim ships no curl)
  - No `depends_on: api → ai-engine` (stack decoupling)
  - Shared `uploads_data` volume at `/app/uploads` on both services
  - Token default `${AI_ENGINE_TOKEN:-local-dev-token}` matches Plan 04's `.env` dev value

## Deviations from Plan

None - plan executed exactly as written.

One observation (not a deviation, no fix needed): the plan's Task 2 verification expected `docker compose port ai-engine 8000` to print nothing and exit non-zero. On Docker Compose v2.30.3 it prints `:0` and exits 0 (compose quirk for unpublished ports). The decisive verification used `docker inspect` port bindings (`{}` / `{"8000/tcp":null}`) plus a host-level `curl localhost:8000/health` → connection refused, which conclusively proves no host port exposure. The `:0` output is cosmetic and the security property (T-03-02) is confirmed by ground truth.

## Issues Encountered
- **One command-path slip (Task 2):** first `docker compose build` invocation used `-f backend/docker-compose.yml` while already inside `backend/`, producing a doubled path (`backend/backend/...`). Resolved immediately by running from the backend workdir with the default compose file. No impact on the plan outcome.
- **Docker Hub/network:** no flakiness this run — `python:3.13-slim` base was already cached from Plan 01's build, so the multi-stage build completed in ~17s.

## User Setup Required
None - no external service configuration required. `docker compose up -d ai-engine` (or the full `docker compose up`) now brings up the engine with the same default token the local `backend/.env` uses. Production must supply a real `AI_ENGINE_TOKEN` (documented in `.env.example` by Plan 04).

## Next Phase Readiness
- FND-02 satisfied: ai-engine runs in the standard compose stack, healthy, internal-only, token-protected — with the api service resolving it at `http://ai-engine:8000` with the shared token (satisfies FND-04's required env vars for the compose-run api)
- Ready for Plan 05 (CI workflow for ai-engine) — the compose file now serves as the canonical runtime definition; the built image (`backend-ai-engine:latest`) is cached locally for fast CI/rebuilds
- No blockers

## Threat Surface

No new trust boundaries beyond those registered in the plan. All five threats (T-03-01 spoofing via shared token, T-03-02 host exposure — verified closed by inspect + curl, T-03-03 token in compose — accepted dev artifact, T-03-04 hung healthcheck — timeout/retries, T-03-05 stack coupling — no depends_on) are mitigated as specified. The `:0` quirk of `docker compose port` in v2.30 does not alter the threat disposition — ground-truth port bindings are empty.

---
*Phase: 01-foundation*
*Completed: 2026-07-31*

## Self-Check: PASSED
- FOUND: backend/docker-compose.yml contains `ai-engine` service with build context `../ai-engine`, `container_name: academio-ai-engine`, NO `ports:` key, urllib `/health` healthcheck, `uploads_data:/app/uploads` volume
- FOUND: api env block contains `AI_ENGINE_URL: http://ai-engine:8000` and `AI_ENGINE_TOKEN: "${AI_ENGINE_TOKEN:-local-dev-token}"`; api `depends_on` lists only postgres/redis/gotenberg
- FOUND: commit `9e13eee` in backend submodule (branch dev) — `git log --oneline` shows it atop 33d661d
- VERIFIED LIVE: build exit 0; container healthy in ~4s; `docker inspect` PortBindings `{}`; host curl refused; /health 200; /v1/health 401 without token, 200 with token; `rm -sf` cleanup; shared-postgres/shared-redis untouched
- FOUND: `.planning/phases/01-foundation/01-03-SUMMARY.md` written
