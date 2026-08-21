---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [fastapi, python, uv, docker, pydantic, pytest, service-auth, healthcheck]

# Dependency graph
requires:
  - phase: 00-init
    provides: project structure, stack research (STACK.md), repo conventions (backend/Makefile, backend/Dockerfile)
provides:
  - uv-bootstrappable FastAPI skeleton at ai-engine/ (Python 3.13, pinned pyproject.toml, committed uv.lock)
  - GET /health (unauthenticated, container healthcheck target) + token-protected GET /v1/health
  - Multi-stage python:3.13-slim Dockerfile serving uvicorn on :8000
  - Service-token auth contract: X-AI-Engine-Token header, 401 on missing/wrong token
affects: [FND-02 compose service, FND-03 Go EngineClient seam, FND-04 config, FND-05 CI, Phase 3 Python endpoints]

# Tech tracking
tech-stack:
  added: [uv 0.12, fastapi 0.140.13, pydantic-settings, pytest 9, pytest-asyncio 1.4, ruff 0.16, pyright, httpx, uvicorn]
  patterns:
    - "Module-level settings singleton (app/config.py) shared by app + tests for deterministic auth tests"
    - "Token dependency via FastAPI Depends(require_token) — header-only auth, never URL param"
    - "Multi-stage uv Dockerfile: builder uv sync --frozen --no-dev, runtime venv copy"
    - "Makefile conventions from backend: .PHONY header, ##-documented targets, help as DEFAULT_GOAL"

key-files:
  created:
    - ai-engine/pyproject.toml
    - ai-engine/uv.lock
    - ai-engine/.python-version
    - ai-engine/.gitignore
    - ai-engine/README.md
    - ai-engine/Makefile
    - ai-engine/app/__init__.py
    - ai-engine/app/config.py
    - ai-engine/app/main.py
    - ai-engine/tests/__init__.py
    - ai-engine/tests/test_health.py
    - ai-engine/Dockerfile
    - ai-engine/.dockerignore
  modified: []

key-decisions:
  - "Test fixture wires the module-level settings singleton (app_settings.AI_ENGINE_TOKEN = test token) so the valid-token test reads the SAME instance the app's require_token dependency uses — deterministic, per plan note"
  - "Async fixture annotated AsyncGenerator[AsyncClient] (pyright-correct) instead of AsyncClient; ruff UP043 drops the redundant None send-type in Py3.13"
  - "Empty AI_ENGINE_TOKEN default is intentional (T-01-04): routes 401 when unset — no insecure default bypass"

patterns-established:
  - "Pattern 1: every /v1/* route declares dependencies=[Depends(require_token)] — future Phase 3 routes inherit auth by construction"
  - "Pattern 2: uv-managed Python service — pyproject.toml pins, uv.lock committed, clean `uv sync` reproducible bootstrap"
  - "Pattern 3: container healthcheck target is unauthenticated GET /health returning static JSON (no side effects)"

requirements-completed: [FND-01]

# Metrics
duration: 10min
completed: 2026-07-31
---

# Phase 1 Plan 1: ai-engine Skeleton Summary

**uv-bootstrappable FastAPI service skeleton at ai-engine/ — Python 3.13 pinned project, committed uv.lock, unauthenticated GET /health (container healthcheck target), token-protected GET /v1/health via X-AI-Engine-Token, 4/4 smoke tests green, and a multi-stage python:3.13-slim Docker image verified serving health checks**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-31T17:23:45Z
- **Completed:** 2026-07-31T17:34:18Z
- **Tasks:** 3 (Task 2 was TDD: RED + GREEN commits)
- **Files modified:** 13 created

## Accomplishments
- `ai-engine/` bootstraps from scratch with `uv sync` (Python 3.13.1 via uv-managed env, fastapi 0.140.13, pydantic-settings) — verified from a clean `.venv` state, no manual dependency steps
- FastAPI skeleton serves `GET /health` → 200 `{"status":"ok","service":"ai-engine"}` (no auth — container healthcheck target) and `GET /v1/health` → 401 without/wrong token, 200 with valid `X-AI-Engine-Token`
- Multi-stage Dockerfile (`python:3.13-slim` + uv from `ghcr.io/astral-sh/uv`): image `academio-ai-engine:test` builds, container serves /health 200 and /v1/health 401 without token; test container cleaned up
- Service-token auth contract locked for downstream plans: header-only (`X-AI-Engine-Token`), 401 detail `invalid service token`, empty token → always 401 (threat register T-01-01/T-01-02/T-01-04 mitigations in place)

## Task Commits

Each task was committed atomically:

1. **Task 1: Bootstrap ai-engine/ Python project with uv** - `722dc0a` (feat)
2. **Task 2: Implement FastAPI app skeleton with /health + token auth** - `6758bf1` (test, RED) + `9a93f95` (feat, GREEN)
3. **Task 3: Create multi-stage Dockerfile for the service** - `7dfe636` (feat)

**Plan metadata:** pending (SUMMARY/STATE/ROADMAP metadata commit)

_Note: TDD task 2 produced 2 commits (test → feat), no refactor commit needed — implementation matched plan, gates clean._

## Files Created/Modified
- `ai-engine/pyproject.toml` - Pinned manifest: requires-python >=3.13, fastapi[standard]>=0.140,<0.141, pydantic-settings, dev group (pytest, pytest-asyncio, ruff, pyright), pytest asyncio_mode=auto, ruff/pyright config
- `ai-engine/uv.lock` - Committed lockfile — reproducible bootstrap (contains fastapi 0.140.13)
- `ai-engine/.python-version` - Pins Python 3.13
- `ai-engine/.gitignore` - .venv, caches, .env, build artifacts
- `ai-engine/README.md` - Bootstrap commands + submodule-ready note (extract to Playbits/Academio-AI when remote exists)
- `ai-engine/Makefile` - help/sync/run/test/lint/typecheck, backend-Makefile conventions
- `ai-engine/app/__init__.py` - Package marker (empty)
- `ai-engine/app/config.py` - pydantic-settings Settings (AI_ENGINE_TOKEN empty default) + module-level singleton
- `ai-engine/app/main.py` - FastAPI app: /health unauthenticated, /v1/health behind require_token dependency
- `ai-engine/tests/__init__.py` - Package marker (empty)
- `ai-engine/tests/test_health.py` - 4 smoke tests (200 unauth health, 401 no token, 401 wrong token, 200 valid token)
- `ai-engine/Dockerfile` - Multi-stage: uv builder (uv sync --frozen --no-dev --no-install-project) → slim runtime, uvicorn :8000
- `ai-engine/.dockerignore` - Keeps venv/caches/tests/docs out of image context

## Decisions Made
- **Same-instance token wiring:** The plan's note required the token dependency to read the same settings instance the client fixture uses. The fixture mutates the module-level singleton (`app_settings.AI_ENGINE_TOKEN = "test-token-123"`) so `require_token` (which imports the singleton) validates the test token deterministically — app and tests share one instance.
- **Async fixture annotation:** Plan's snippet annotated the async generator fixture `-> AsyncClient`, which pyright rejects; corrected to `-> AsyncGenerator[AsyncClient]` (ruff UP043 then drops the redundant `None` send-type on Python 3.13).
- **Intentional empty token default:** `AI_ENGINE_TOKEN: str = ""` per plan/interface contract — routes fail-safe to 401 when unset (threat register T-01-02/T-01-04), .env is gitignored.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pyright-invalid async fixture annotation in plan's test snippet**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** Plan's test code annotated `async def client(...) -> AsyncClient` on an async generator fixture — pyright errors (`AsyncGenerator` not assignable to `AsyncClient`), breaking the mandatory pyright gate.
- **Fix:** Changed annotation to `-> AsyncGenerator[AsyncClient]`, then applied ruff UP043 (drop redundant `None` send-type, Py3.13 default).
- **Files modified:** ai-engine/tests/test_health.py
- **Verification:** `uv run pyright` exits 0; `uv run ruff check .` exits 0; 4/4 tests still pass
- **Committed in:** 9a93f95 (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Ruff I001 import ordering in test file**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** `from app.config import Settings, settings as app_settings` flagged un-sorted by ruff (I001)
- **Fix:** `uv run ruff check . --fix` split into two imports per isort ordering
- **Files modified:** ai-engine/tests/test_health.py
- **Verification:** `uv run ruff check .` exits 0
- **Committed in:** 9a93f95 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - Bug)
**Impact on plan:** Both fixes were required to satisfy the plan's own mandatory gates (ruff + pyright exit 0). No scope creep; behavior unchanged.

## Issues Encountered
- **Docker Hub network flakiness (Task 3):** First `docker build` failed pulling `python:3.13-slim` ("connection reset by peer"), and an explicit `docker pull` hit a TLS handshake timeout. Retried the pull — succeeded on the next attempt — then the build completed. Transient infrastructure issue, not a code problem. Residual risk: docker builds depend on Docker Hub reachability; CI environment should be retry-tolerant.

## User Setup Required
None - no external service configuration required. (Local dev needs `uv` installed; `AI_ENGINE_TOKEN` is read from env/`.env` when the Go seam or compose wires it in later plans.)

## Next Phase Readiness
- FND-01 satisfied: `ai-engine/` bootstrappable with `uv sync` (verified from clean state), starts, passes 4/4 smoke tests, ruff + pyright clean
- Container image contract ready for Plan 03 compose: listens on :8000, exposes unauthenticated GET /health for the healthcheck, `python:3.13-slim` base
- Auth contract ready for the Go seam (FND-03/04): `X-AI-Engine-Token` header, 401 `invalid service token` on missing/wrong token
- Ready for Plan 02 (Go EngineClient seam) and Plan 03 (compose service) — no blockers

---
*Phase: 01-foundation*
*Completed: 2026-07-31*

## Self-Check: PASSED
- All 13 planned ai-engine/ files exist on disk (pyproject.toml, uv.lock, .python-version, .gitignore, README.md, Makefile, app/{__init__,config,main}.py, tests/{__init__,test_health}.py, Dockerfile, .dockerignore)
- All 4 task commits present: `722dc0a` (Task 1 feat), `6758bf1` (Task 2 RED test), `9a93f95` (Task 2 GREEN feat), `7dfe636` (Task 3 feat)
- Plan verification: uv sync + pytest 4 passed, ruff clean, pyright 0 errors, docker image built and served /health 200 + /v1/health 401, no Phase-3 dependencies in pyproject
