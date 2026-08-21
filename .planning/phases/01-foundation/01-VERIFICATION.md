---
phase: 01-foundation
verified: 2026-07-31T21:59:52Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "First authoritative CI run on GitHub Actions"
    expected: "Pushing any change under ai-engine/** to main (or opening a PR) triggers .github/workflows/ai-engine.yml; all 4 jobs (lint, typecheck, test, docker-build) complete green on a clean runner"
    why_human: "GitHub Actions execution is an external service — cannot be executed from this environment. Every command the workflow runs (uv sync --frozen, ruff check ., pyright, pytest, docker build ./ai-engine) was verified green locally against the same artifacts, and the workflow YAML parses with correct triggers/pins, but the first real runner execution requires a push/PR."
---

# Phase 1: Foundation Verification Report

**Phase Goal:** The Go↔Python seam, service infrastructure, and CI exist so all AI traffic flows over an authenticated, timeout-disciplined, health-checked boundary.
**Verified:** 2026-07-31T21:59:52Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Truths are the 5 ROADMAP.md Success Criteria (the phase contract), cross-checked against PLAN frontmatter must-haves.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A developer can bootstrap ai-engine/ from scratch with `uv sync` (Python 3.13, pinned pyproject.toml), start the FastAPI service, and run a passing smoke test — no manual dependency steps (SC1 / FND-01) | ✓ VERIFIED | `ai-engine/pyproject.toml` has `requires-python = ">=3.13"` + `fastapi[standard]>=0.140,<0.141`; `uv.lock` committed (164KB, contains fastapi `>=0.140,<0.141`); `.python-version` = `3.13`. `uv run pytest -q` → **4 passed**; `uv run ruff check .` → clean; `uv run pyright` → 0 errors. |
| 2 | `docker compose up` starts an ai-engine container that passes its health check, is reachable only on the internal Docker network (no published host port), and mounts the shared uploads volume api also mounts (SC2 / FND-02) | ✓ VERIFIED | `backend/docker-compose.yml` ai-engine block (lines 96-111): build `../ai-engine`, NO `ports:` key, urllib healthcheck on `/health` (timeout 3s), `uploads_data:/app/uploads` on BOTH api (line 94) and ai-engine (line 105). `docker compose config --quiet` exit 0; composed ai-engine config has no ports. **Live spot-check**: built image `academio-ai-engine:test` booted, `/health` → 200 `{"status":"ok","service":"ai-engine"}`, `/v1/health` → 401 (no token) / 200 (valid token); container cleaned up. Plan 03 summary records host-level `curl localhost:8000` refused + `docker inspect` PortBindings `{}`. |
| 3 | Go code can call a running Python engine through the EngineClient seam for both JSON (Chat, Extract) and SSE (ChatStream) responses, with per-endpoint timeout budgets (extract minutes, chat seconds, stream no overall cap) and X-Request-ID propagated on every call (SC3 / FND-03) | ✓ VERIFIED | `engine.go` (EngineClient interface: Chat/ChatStream/Extract/Health + header constants), `sse.go` (bufio.Scanner, 1MB buffer), `client.go` (chatTimeout 30s, extractTimeout 5m, healthTimeout 10s — exactly 3 `context.WithTimeout` calls, ChatStream has none; token header-only; X-Request-ID from `middleware.GetRequestIDFromCtx` or `uuid.NewString()`). **All 12 engine test functions pass** including `TestChatEnforcesDeadline`, `TestChatStreamParsesSSE`, `TestChatStreamNoOverallTimeout`, `TestRequestIDFromCtx`, `TestRequestIDGeneratedWhenAbsent`. `go vet` + `go build ./...` exit 0. |
| 4 | The backend fails fast at startup when AI_ENGINE_URL or AI_ENGINE_TOKEN is missing or invalid (Rule B12), in ALL environments; every internal call authenticates with the service token in a header — never in a URL, never a user JWT (SC4 / FND-04) | ✓ VERIFIED | `config.go` `validate()` lines 427-437: unconditional checks (empty URL, non-http(s) URL, empty token) — NOT gated on AI_ENABLED. `config_test.go`: valid fixture includes AI fields + 3 negative subtests (missing URL, missing token, invalid URL) — all pass. `AIServiceConfig` + `FromAppConfig` expose EngineURL/EngineToken. `.env.example` documents both as REQUIRED; `.env` has dev values. `client.go` sends token via `X-AI-Engine-Token` header only. |
| 5 | CI for ai-engine (ruff lint, pyright type-check, pytest, Docker build) runs on every push and blocks on failure; the existing Go build, lint, and test suites stay green with the new seam and config in place (SC5 / FND-05) | ✓ VERIFIED | `.github/workflows/ai-engine.yml`: 4 jobs (lint/typecheck/test/docker-build), path-scoped triggers `ai-engine/**` + workflow file on push AND pull_request, `workflow_dispatch`, `uv sync --frozen` in every uv job, setup-uv pinned to commit SHA `c771a70e` (v9.0.0), `permissions: contents: read`. YAML parses with correct jobs/triggers. Backend Go CI untouched (`backend/.github/workflows/ci.yml` exists); Go test/vet/build all green locally. Root workflows: only `ai-engine.yml` added beside existing `docs.yml`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `ai-engine/pyproject.toml` | Pinned manifest (requires-python >=3.13, fastapi[standard] 0.140.x) | ✓ VERIFIED | Exact match to plan; no Phase-3 deps (docling/anthropic/openai/psycopg/pgvector grep = zero) |
| `ai-engine/uv.lock` | Committed lockfile | ✓ VERIFIED | 164KB, contains fastapi `>=0.140,<0.141` |
| `ai-engine/app/main.py` | FastAPI app: /health + token-protected /v1/health | ✓ VERIFIED | `require_token` dependency, header-only auth, 401 `invalid service token` |
| `ai-engine/tests/test_health.py` | 4 smoke tests | ✓ VERIFIED | 4/4 pass; covers 200 unauth, 401 no token, 401 wrong token, 200 valid token |
| `ai-engine/Dockerfile` | Multi-stage python:3.13-slim + uv | ✓ VERIFIED | `uv sync --frozen --no-dev --no-install-project`; uvicorn on :8000; image built + live-booted |
| `backend/internal/ai/engine/engine.go` | EngineClient interface + DTOs + header constants | ✓ VERIFIED | Matches plan contract exactly |
| `backend/internal/ai/engine/sse.go` | SSE reader primitive (>64KB buffer) | ✓ VERIFIED | bufio.Scanner, 1MB buffer, custom split, comment tolerance, ctx-cancel |
| `backend/internal/ai/engine/client.go` | httpClient with per-endpoint timeouts | ✓ VERIFIED | 3 WithTimeout calls (Chat/Extract/Health); ChatStream context-bound; %w wrapping everywhere |
| `backend/internal/ai/engine/client_test.go` | httptest suite | ✓ VERIFIED | 271 lines, 12 test functions, all pass |
| `backend/internal/ai/engine/sse_test.go` | Split/parse/scan/ctx-cancel tests | ✓ VERIFIED | 171 lines, table-driven, all pass |
| `backend/docker-compose.yml` | ai-engine service + api env wiring | ✓ VERIFIED | No ports, urllib healthcheck, shared volume, API_ENGINE_URL wiring, no depends_on coupling |
| `backend/internal/config/config.go` | EngineURL/EngineToken + unconditional validate() | ✓ VERIFIED | Fields 111-112, bindings 319-320, checks 427-437 |
| `backend/internal/config/config_test.go` | Updated fixture + 3 negative subtests | ✓ VERIFIED | All pass |
| `backend/internal/ai/config.go` | AIServiceConfig pass-through | ✓ VERIFIED | EngineURL/EngineToken fields + FromAppConfig |
| `backend/.env.example` | Documents both vars REQUIRED | ✓ VERIFIED | Header line 9 + active AI block lines 106-112 |
| `.github/workflows/ai-engine.yml` | 4-job CI workflow | ✓ VERIFIED | Path-scoped, pinned setup-uv, uv sync --frozen, no secrets |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| ai-engine/Dockerfile | ai-engine/pyproject.toml | `uv sync --frozen` in build | WIRED | Line 6 of Dockerfile |
| ai-engine/app/main.py | ai-engine/app/config.py | `from app.config import settings` | WIRED | Module-level singleton shared by app + tests |
| ai-engine/tests/test_health.py | ai-engine/app/main.py | httpx ASGITransport AsyncClient | WIRED | Tests exercised app directly; 4/4 green |
| backend/internal/ai/engine/client.go | middleware.GetRequestIDFromCtx | import + call in newRequest | WIRED | Line 149; ctx-derived ID, uuid fallback |
| backend/internal/ai/engine/client.go | X-AI-Engine-Token header | `hreq.Header.Set` | WIRED | Line 148 — token in header, never URL |
| api service env | ai-engine service | `AI_ENGINE_URL: http://ai-engine:8000` | WIRED | compose lines 84-85; `docker compose config` confirms exactly 1 |
| ai-engine healthcheck | GET /health (unauthenticated) | urllib `localhost:8000/health` | WIRED | compose lines 106-111; live boot confirmed 200 |
| ai-engine volumes | uploads_data | `uploads_data:/app/uploads` | WIRED | Both api (line 94) and ai-engine (line 105) |
| .github/workflows/ai-engine.yml | ai-engine/** path filter | `paths:` on push + pull_request | WIRED | Lines 5, 7 |
| .github/workflows/ai-engine.yml | uv.lock | `uv sync --frozen` in every uv job | WIRED | Lines 29, 44, 59 |
| backend/internal/config/config.go | AI_ENGINE_URL env var | `getEnv("AI_ENGINE_URL", "")` | WIRED | Line 319 |
| backend/internal/config/config.go | validate() | unconditional error returns | WIRED | Lines 429-436 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| client.go (transport seam) | Request payloads | httptest mocks implementing the Python wire contract | Yes — real HTTP requests/responses through a real `http.Client`; JSON decode + SSE parse verified against live server responses | ✓ FLOWING (seam-level; Python `/v1/chat` etc. are Phase 3 scope by design — DTOs target the locked wire contract) |
| app/main.py | /health + /v1/health responses | Live uvicorn container | Yes — real HTTP verified 200/401/200 | ✓ FLOWING |
| config.go validate() | EngineURL/EngineToken | env bindings + tests | Yes — 3 negative subtests prove fail-fast paths | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Python smoke tests pass | `uv run pytest -q` (ai-engine/) | 4 passed in 0.52s | ✓ PASS |
| Python lint clean | `uv run ruff check .` | All checks passed | ✓ PASS |
| Python typecheck clean | `uv run pyright` | 0 errors, 0 warnings | ✓ PASS |
| Go seam + config + ai tests | `go test ./internal/config/... ./internal/ai/...` | config ok, engine ok | ✓ PASS |
| Go seam behavior (deadline/SSE/request-ID) | `go test ./internal/ai/engine/... -v` | 12/12 PASS incl. TestChatEnforcesDeadline, TestChatStreamNoOverallTimeout, TestRequestIDFromCtx/Generated | ✓ PASS |
| Go vet | `go vet ./internal/ai/engine/... ./internal/config/... ./internal/ai/` | exit 0 | ✓ PASS |
| Go build | `go build ./...` | exit 0 | ✓ PASS |
| Compose file valid | `docker compose config --quiet` | exit 0 (only pre-existing obsolete `version` warning) | ✓ PASS |
| No host port on ai-engine | `docker compose config` ai-engine block | no `ports:`/`expose:` in composed config | ✓ PASS |
| Container serves health + auth matrix | `docker run` + curl /health, /v1/health | 200 ok / 401 / 200; container removed | ✓ PASS |
| Workflow YAML valid | python yaml parse + job assertions | 4 jobs, working-directory ai-engine, push+PR+dispatch triggers | ✓ PASS |
| No Phase-3 deps in pyproject | grep docling/anthropic/openai/psycopg/pgvector | zero matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| FND-01 | 01-01-PLAN | ai-engine/ FastAPI submodule (Python 3.13, pyproject.toml, uv bootstrap) | ✓ SATISFIED | pyproject/uv.lock/.python-version exist; uv sync + pytest + ruff + pyright green; Dockerfile builds |
| FND-02 | 01-03-PLAN | docker-compose ai-engine service (internal port only, health-checked, shared uploads volume) | ✓ SATISFIED | compose lines 96-111; no ports; urllib healthcheck; uploads_data shared; live-boot verified |
| FND-03 | 01-02-PLAN | Go EngineClient seam (HTTP/JSON + SSE, gRPC-ready interface) | ✓ SATISFIED | engine.go/sse.go/client.go + 20-test suite green |
| FND-04 | 01-04-PLAN | AI_ENGINE_URL + AI_ENGINE_TOKEN config (service-to-service auth, never user JWT) | ✓ SATISFIED | unconditional validate() checks + negative tests; header-only auth |
| FND-05 | 01-05-PLAN | CI workflow for ai-engine (lint, test, build) | ✓ SATISFIED | ai-engine.yml 4 jobs, path-scoped, blocks on failure |

**Traceability check:** All 5 FND-01..05 IDs claimed by plans, marked `[x] Complete` in REQUIREMENTS.md, and mapped to Phase 1 in the traceability table. No orphaned requirements: every Phase-1 ID in REQUIREMENTS.md appears in a plan's `requirements:` field.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TODO/FIXME/placeholder stubs in any phase source file | ℹ️ none | — |
| — | — | No `context.Background` in engine package (Rule B2); no `fmt.Printf`/`log.Print` (Rule B3) | ℹ️ none | greps zero-match |
| backend/internal/ai/engine/*_test.go | multiple | `context.TODO()` in tests | ℹ️ Info (not a stub) | Deliberate, documented decision — idiomatic test root that keeps the Rule B2 grep literally zero-match; tests only |
| backend/docker-compose.yml | 130-132 | WR-01 (review): prometheus `depends_on: api: condition: service_healthy` but api has no healthcheck | ⚠️ Warning (pre-existing, out of phase scope) | Pre-existing stack issue predating this phase; ai-engine (this phase's service) has a working healthcheck. Prometheus/Grafana boot is not a Phase-1 SC. Track for follow-up. |
| backend/internal/config/config.go | 427-437 | WR-02 (review): unconditional fail-fast also applies to DB migrate/seed tooling | ⚠️ Warning (documented config decision) | Intentional per FND-04/SC4 (explicitly "in ALL environments"); backend/.env now carries both vars so documented flows work; plan decision locked in RESEARCH.md/STATE.md |

### Human Verification Required

### 1. First authoritative CI run on GitHub Actions

**Test:** Push any change under `ai-engine/**` to `main` (or open a PR touching it) and observe `.github/workflows/ai-engine.yml`.
**Expected:** All 4 jobs (lint → ruff, typecheck → pyright, test → pytest -v, docker-build) run on a clean ubuntu-latest runner and complete green; the path filter triggers only on ai-engine changes; `uv sync --frozen` fails the build if the lockfile drifts.
**Why human:** GitHub Actions execution is an external service that cannot be run from this environment. Every command the workflow executes was verified green locally against the same committed artifacts (`uv sync --frozen`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q`, `docker build -t ai-engine:ci ./ai-engine` — image builds; both engine images exist locally), and the YAML structure/triggers/pins are validated, but the first runner execution requires a real push. Same residual risk documented in 01-05-SUMMARY.

### Gaps Summary

No gaps found. All 5 roadmap Success Criteria and all plan-level must-haves verified against the live filesystem and executable gates:

- **FND-01** — ai-engine bootstraps (uv sync, pinned pyproject, committed lockfile), 4/4 smoke tests, ruff + pyright clean, Docker image built and live-booted.
- **FND-02** — compose service internal-only (no published port), urllib healthcheck green, shared uploads volume on api + ai-engine, api env wired with AI_ENGINE_URL + shared token, no depends_on coupling.
- **FND-03** — EngineClient seam with per-endpoint timeouts (30s/5m/10s; stream uncapped — exactly 3 WithTimeout calls), header-only token auth, X-Request-ID from ctx with uuid fallback; 12/12 behavioral tests incl. deadline enforcement and no-overall-cap proof.
- **FND-04** — unconditional fail-fast config validation in all environments with 3 negative tests; AIServiceConfig pass-through; .env.example/.env document dev values.
- **FND-05** — root CI workflow (4 jobs, path-scoped, pinned setup-uv, frozen lockfile) with backend Go CI untouched and locally green (go test/vet/build).

Known warnings WR-01 (pre-existing prometheus healthcheck gap) and WR-02 (documented unconditional-validation decision) are carried from the code review; neither blocks any Phase-1 success criterion. The only unresolvable-from-here item is the CI workflow's first GitHub runner execution → status `human_needed` pending that confirmation.

---

_Verified: 2026-07-31T21:59:52Z_
_Verifier: the agent (gsd-verifier)_
