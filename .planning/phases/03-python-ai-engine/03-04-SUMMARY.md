---
phase: 03-python-ai-engine
plan: 04
subsystem: api
tags: [fastapi, pydantic, openai, tenacity, httpx, asyncio, embeddings]

# Dependency graph
requires:
  - phase: 03-02
    provides: ProviderInfo registry (registry.py), pydantic settings with AI_* env gates, tenacity presets (util/retry.py)
provides:
  - GET /v1/providers health contract (D-10) consumed by Go INT-02 in Phase 5
  - POST /v1/embed canonical 1536-dim embedding endpoint (D-05)
  - ProviderHealth TTL cache + fail-streak cooldown (D-10)
  - require_token service-token dependency (app/security.py) reused by later route plans
affects: [03-05, 03-06, 03-07, backend INT-02 (Phase 5)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service-token dependency in a dedicated app/security.py module (breaks main<->api import cycles)"
    - "Module-level health singleton: TTL cache + single-in-flight asyncio lock + fail-streak cooldown"
    - "_retried() Any-pin helper for tenacity decorators (pyright overload workaround)"
    - "Route-layer fail-loud mapping: 503 unconfigured / 400 validation / 502 provider error / 500 pipeline"

key-files:
  created:
    - ai-engine/app/providers/healthcheck.py
    - ai-engine/app/providers/embedding.py
    - ai-engine/app/api/embed.py
    - ai-engine/app/api/providers.py
    - ai-engine/app/api/__init__.py
    - ai-engine/app/security.py
    - ai-engine/tests/test_embedding.py
  modified:
    - ai-engine/app/main.py
    - ai-engine/tests/test_providers.py

key-decisions:
  - "Extracted require_token to app/security.py so api route modules import it without a main<->api circular import (plan sketch imported from app.main)"
  - "tenacity decorators applied via _retried() helper returning Any — pins the dual-mode retry() to the correct overload for pyright"
  - "Route tests replace the module-level _health singleton with a fresh ProviderHealth after patching settings (TTL/threshold are read at construction)"

patterns-established:
  - "Health ping endpoints per provider kind, model-less (Anthropic /v1/models, OpenAI-compat /models, Azure deployments + 1-token chat fallback, Ollama /api/tags)"
  - "Boundary validation before returning embeddings: dim == AI_EMBEDDING_DIM and non-zero norm (D-14 parity, RESEARCH Pitfall 2)"

requirements-completed: [PYE-04]

# Metrics
duration: 14min
completed: 2026-08-01
---

# Phase 03 Plan 04: Provider Health + Embedding Endpoints Summary

**FastAPI service endpoints for the AI engine: GET /v1/providers returning the D-10 per-provider health contract (TTL-cached pings with fail-streak cooldown) and POST /v1/embed producing canonical text-embedding-3-small 1536-dim vectors with fail-loud dimension/norm boundary asserts**

## Performance

- **Duration:** 14 min
- **Started:** 2026-08-01T08:47:34Z
- **Completed:** 2026-08-01T09:01:19Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- `ProviderHealth` (app/providers/healthcheck.py): model-less health pings per provider kind, 30s TTL cache, single-in-flight asyncio lock per provider, 3-strike fail-streak -> 60s cooldown; unconfigured providers report `unavailable`, never raise (RESEARCH Pitfall 5/A3)
- POST /v1/embed: 1..256 texts, per-text 8000-char cap, batch <= 128, tenacity retries, 1536-dim + zero-norm boundary assert on every vector (D-05/D-14 parity), clean 503/400/502/500 error mapping (T-03-04-03)
- GET /v1/providers: stable D-10 contract `{provider, status, latency_ms, last_checked, cooldown_until}` for all five providers (anthropic, deepseek, openrouter, azure, ollama); never 500s on missing keys (Pitfall 5)
- 16 new tests (8 embed route, 5 ProviderHealth unit, 4 providers route) — all hermetic (monkeypatched httpx client, no network); full suite 42 passed + 1 live-key skip
- Full-tree gates green: ruff clean, pyright 0 errors, pytest 42 passed

## Task Commits

1. **Task 1: ProviderHealth TTL cache + cooldown (healthcheck.py)** - `355a023` (feat)
2. **Task 2: POST /v1/embed endpoint + EmbeddingClient** - `059a8ce` (feat)
3. **Task 3: GET /v1/providers route** - `dca7bbd` (feat)

**Plan metadata:** pending final docs commit

## Self-Check: PASSED

- All 8 created/verified files exist on disk (healthcheck.py, embedding.py, embed.py, providers.py, api/__init__.py, security.py, test_embedding.py, 03-04-SUMMARY.md)
- All 3 task commits present in git log: `355a023`, `059a8ce`, `dca7bbd`

## Files Created/Modified
- `ai-engine/app/providers/healthcheck.py` - ProviderStatus/ProviderHealth: model-less pings, 30s TTL cache, in-flight dedup, fail-streak cooldown (D-10)
- `ai-engine/app/providers/embedding.py` - EmbeddingClient (AsyncOpenAI, batch <= 128, 8000-char cap), validate_vector (1536-dim + zero-norm), `_retried()` tenacity helper
- `ai-engine/app/api/embed.py` - POST /v1/embed: EmbedRequestIn/EmbedResponseOut, fail-loud 503/400/502/500 mapping, X-School-Schema accepted
- `ai-engine/app/api/providers.py` - GET /v1/providers: D-10 contract list, module-level ProviderHealth singleton
- `ai-engine/app/security.py` - require_token (X-AI-Engine-Token only) extracted from app.main
- `ai-engine/app/api/__init__.py` - package marker
- `ai-engine/app/main.py` - includes embed + providers routers; /health, /v1/health
- `ai-engine/tests/test_embedding.py` - 8 route tests (401, 422 empty, missing-key 503, live 1536-dim skip, zero-vector/dim/char/text-count guards)
- `ai-engine/tests/test_providers.py` - Part 1: 5 unit tests; Part 2: 4 route tests (401, no-keys 5x unavailable, healthy + latency, cooldown flow)

## Decisions Made
- **require_token lives in app/security.py, not app.main** — the plan sketch had api modules import it from app.main, which is circular when an api module is the first import (`app.main` imports the router before it is defined). Extracted to a shared module; verified with an entry-point import smoke test.
- **tenacity decorators applied via `_retried(preset) -> Any`** — pyright resolves tenacity's dual-mode `retry()` to the `RetryCallState` overload for `@retry(**preset)`, typing the decorated method as bool/float and breaking every call site. The helper pins the decorator to `Any`; same friction 03-03 hit (they used a pyright ignore; the helper is the call-site-safe variant).
- **Route tests construct a fresh ProviderHealth singleton** after patching settings — TTL/cooldown-threshold are read at `__init__`, so monkeypatching the settings object alone is insufficient; the route module's `_health` is replaced per test for hermeticity and order-independence.
- **No-keys route test blanks AI_OLLAMA_BASE_URL** — the config default (`http://localhost:11434`) would make ollama "configured" and ping localhost in CI; blanking keeps the test fully hermetic.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import app.main <-> app.api.embed**
- **Found during:** Task 2 (embed route verification)
- **Issue:** embed.py imported `require_token` from app.main (per plan sketch), but main.py must import the embed router — importing `app.api.embed` first raised `ImportError: cannot import name 'router'`.
- **Fix:** Extracted `require_token` to new `app/security.py`; embed.py and providers.py import from there; main.py imports routers at top.
- **Files modified:** app/security.py (new), app/api/embed.py, app/api/providers.py, app/main.py
- **Verification:** entry-point import smoke test + all route tests pass
- **Committed in:** 059a8ce, dca7bbd

**2. [Rule 1 - Bug] pyright mis-types tenacity-decorated method**
- **Found during:** Task 2 verification (pyright on embedding.py)
- **Issue:** `@retry(**embed_retry)` resolved to the wrong tenacity overload -> decorated method typed bool/float -> `reportArgumentType` at the decorator plus "bool/float not callable" at the call site.
- **Fix:** Added `_retried(preset: dict[str, Any]) -> Any` helper in embedding.py and applied `@_retried(embed_retry)`; the helper returns Any so call sites type-check.
- **Files modified:** app/providers/embedding.py
- **Verification:** pyright 0 errors on embedding.py
- **Committed in:** 059a8ce

**3. [Rule 1 - Bug] Over-strict test assertion on 503 detail**
- **Found during:** Task 2 verification (pytest)
- **Issue:** test asserted `"embedding" in detail` but the unconfigured path returns `"AI_OPENAI_API_KEY is not configured"`.
- **Fix:** Assert `"ai_openai_api_key" in detail.lower()` — matches actual API output.
- **Files modified:** tests/test_embedding.py
- **Verification:** pytest green
- **Committed in:** 059a8ce

---

**Total deviations:** 3 auto-fixed (2 Rule 1, 1 Rule 3)
**Impact on plan:** All fixes were necessary for correctness (import cycle, type safety) or test accuracy. No scope creep — response shapes and threat mitigations match the plan exactly.

## Issues Encountered
- **Concurrent execution with 03-03 in the same tree:** 03-03's in-flight provider client files made the full-tree ruff/pyright red mid-execution. My work was verified file-scoped and stayed out of 03-03's files (base.py, sse.py, retry.py, *_provider.py). 03-03 landed their clients (`23033a9`, `55e90d1`) before my final gate, so the full-tree gate (ruff/pyright/pytest) is green.
- **healthcheck.py ownership ambiguity:** STATE.md/03-03-PLAN text and this plan's own `read_first` both allocate healthcheck.py + TTL/cooldown to 03-04; executed under that reading (plan's `files_modified` agrees). No conflict resulted.

## User Setup Required

None - no external service configuration required. Live embedding test skips cleanly without `AI_OPENAI_API_KEY`; provider status reports `unavailable` without keys (intended, D-10).

## Next Phase Readiness
- `/v1/embed` is ready for 03-06's `/v1/search` (embedding consumer) — 1536-dim contract with boundary asserts is locked
- `/v1/providers` D-10 contract is ready for Go INT-02 consumption in Phase 5 (field names stable: provider, status, latency_ms, last_checked, cooldown_until)
- `require_token` in app/security.py is the shared dependency for all remaining route plans (03-05, 03-06, 03-07)
- Live verification deferred: no real provider keys in this environment — embeddings and pings verified via hermetic monkeypatched tests only

---
*Phase: 03-python-ai-engine*
*Completed: 2026-08-01*
