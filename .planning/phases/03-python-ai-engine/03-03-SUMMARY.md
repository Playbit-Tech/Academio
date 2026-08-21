---
phase: 03-python-ai-engine
plan: 03
subsystem: ai-engine-python
tags: [fastapi, sse, anthropic, openai, ollama, httpx, tenacity, pydantic]

# Dependency graph
requires:
  - phase: 03-python-ai-engine
    provides: plan 03-01 proto EngineEvent/ChatRequest contract (D-02/D-03)
  - phase: 03-python-ai-engine
    provides: plan 03-02 provider registry + config + retry presets
provides:
  - POST /v1/chat: provider:model composite routing (D-03) through ANY configured provider client, normalized usage {provider, model, input_tokens, output_tokens, cost} on every response (calculate_cost, D-03)
  - POST /v1/chat/stream: D-02 SSE envelope byte-compatible with Go sse.go scanner — single-line compact-JSON data: events, blank-line boundaries, ': ping' heartbeats, in-band error event after HTTP 200, no gzip, headers Cache-Control: no-cache + X-Accel-Buffering: no
  - Direct-SDK provider clients (D-01): anthropic SDK, openai SDK base_url (deepseek/openrouter/azure via AsyncAzureOpenAI), httpx for Ollama — NO LiteLLM, NO gateway
  - SSE error-message sanitization (T-03-03-03): configured secrets + Authorization/Bearer/api-key fragments redacted before echo
affects: 03-05 (documents), 03-06 (search), 03-07 (prompts — extends /v1/chat with prompt_type), Go seam (consumed by backend/internal/ai/engine client in Phase 5 relay)

# Tech tracking
tech-stack:
  added: []
  patterns: [provider:model first-colon routing (D-03), StreamingResponse SSE envelope via app/sse.py writers, per-request configured-only client build (_clients), DoS bounds (max_tokens cap + client-disconnect check), in-band error events after HTTP 200]

key-files:
  created: [ai-engine/app/api/chat.py, ai-engine/tests/test_chat.py]
  modified: [ai-engine/app/main.py]

key-decisions:
  - "require_token imported from app.security (03-04 extraction) — NOT from app.main as the 03-03 plan sketch said; importing from app.main reintroduces the main<->api circular import documented in the 03-04 SUMMARY deviation"
  - "SSE error events sanitize str(e) before echo (T-03-03-03): replace all configured AI_* secret values + redact Authorization/Bearer/api-key fragments — the plan sketch echoed the raw message"
  - "request.is_disconnected() is awaited per event (Starlette async API) — calling it without await yields a truthy coroutine object, silently disabling the disconnect bound (T-03-03-06)"
  - "Env-gated live tests ping /api/tags once at import (OLLAMA_REACHABLE); with the host Ollama up they RUN against deepseek-coder:latest (live D-02 wire proof); in CI they skip cleanly (D-12)"

patterns-established:
  - "SSE: heartbeat() first, format_event('delta', ...)/usage_event(...) per provider yield, done_event() last, format_event('error', ...) on exception — all single-line compact JSON"
  - "Provider routing: parse_model_composite -> _clients() (configured-only) -> 503 'provider not configured: {name}' before any client construction for missing providers"
  - "Testing: token-swap singleton fixture (test_health pattern) + hermetic monkeypatched _clients + env-gated live shape tests (skipif OLLAMA_REACHABLE)"

requirements-completed: [PYE-01, PYE-04]

# Metrics
duration: 15min
completed: 2026-08-01
---

# Phase 3 Plan 3: Multi-Provider Chat Endpoints Summary

**POST /v1/chat + POST /v1/chat/stream live behind require_token: provider:model routing through anthropic/openai-compat/ollama direct SDKs (D-01), normalized usage + cost on every response (D-03), D-02 SSE envelope byte-compatible with the Go scanner — live-verified against host Ollama with 33 events round-tripping through a Go-scanner-equivalent parse**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-01T09:00Z
- **Completed:** 2026-08-01T09:15Z
- **Tasks:** 1 of 4 executed in this session (Tasks 1-3 committed previously: 509803f, 33dc79f, 23033a9, 55e90d1)

## Artifacts Produced

- `ai-engine/app/api/chat.py` — `/v1/chat` (JSON) + `/v1/chat/stream` (SSE) routes; `ChatMessageIn/ChatRequestIn/ChatResponseOut`; `_clients()` configured-only per-request build; `_sanitize_error_message()`; max_tokens capped at `settings.AI_MAX_TOKENS`; in-band error events after HTTP 200
- `ai-engine/app/main.py` — `chat_router` imported + included (embed/providers routers and `app.security` import untouched)
- `ai-engine/tests/test_chat.py` — 8 tests

## Verification

- `uv run ruff check .` — clean (0 errors)
- `uv run pyright` — 0 errors, 0 warnings, 0 informations
- `uv run pytest tests/ -q` — **50 passed, 1 skipped** (baseline 42+1; +8 new tests, 2 live-shape tests RAN against host Ollama since it is reachable)
- SSE wire-format live proof (Ollama, deepseek-coder:latest): status 200, `content-type: text/event-stream; charset=utf-8`, `cache-control: no-cache`, `x-accel-buffering: no`, `content-encoding` absent (no gzip); body `: ping\n\n` then 33 single-line `data: {"type":"delta"...}` + `data: {"type":"done","data":{}}` events — every `data:` line parsed as compact JSON (Go-scanner-equivalent round-trip OK), no embedded newlines (RESEARCH Pitfall 3)
- Go seam untouched: no edits under `backend/internal/ai/engine/*`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `request.is_disconnected()` missing await**
- **Found during:** Task 4 implementation
- **Issue:** Starlette's `is_disconnected()` is an async coroutine; the plan sketch called it without `await`, which yields a truthy coroutine object — the disconnect check would never trigger, silently disabling the T-03-03-06 stream bound.
- **Fix:** `if await request.is_disconnected(): return` per event.
- **Files modified:** ai-engine/app/api/chat.py
- **Commit:** ffa240d

**2. [Rule 2 - Security] SSE error events sanitize secrets (T-03-03-03)**
- **Found during:** Task 4 threat-model check — the plan's `<threat_model>` assigns `mitigate` to T-03-03-03 ("sanitize to exclude headers/keys before `format_event("error", ...)`") but the action-block sketch echoed `str(e)` raw.
- **Issue:** SDK error strings may embed the request URL/headers (`Authorization: Bearer sk-...`, `?api_key=...`).
- **Fix:** `_sanitize_error_message()` replaces every configured secret value and redacts Authorization/Bearer/api-key fragments with `[REDACTED]`; added hermetic `test_stream_error_in_band_sanitized` proving the secret never reaches the SSE body.
- **Files modified:** ai-engine/app/api/chat.py, ai-engine/tests/test_chat.py
- **Commit:** ffa240d

**3. [Rule 2 - Security] Hermetic max_tokens-cap + usage-shape test (T-03-03-02)**
- **Found during:** Task 4 test design — the usage-shape assertions were only env-gated on live Ollama; the DoS cap (max_tokens bounded at AI_MAX_TOKENS) had no hermetic proof.
- **Fix:** `test_chat_max_tokens_capped` monkeypatches `chat_api._clients` with a recording provider — asserts cap applied and the full 5-key normalized usage payload (no network).
- **Files modified:** ai-engine/tests/test_chat.py
- **Commit:** ffa240d

### Pre-existing deviation honored (documented in 03-04, not re-introduced)

- `require_token` imported from `app.security` (NOT `app.main` as the plan sketch's action block showed). The compatibility note for this task mandated this; importing from `app.main` would reintroduce the main<->api circular import fixed by 03-04.

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 2). No scope creep — all fixes implement mitigations already in the plan's own threat register or correct the sketch to match the Starlette API.

## Known Stubs

None. The streaming `usage` event is emitted only when a provider yields usage (Ollama in this build sends usage on the non-stream path only) — `done` always terminates the stream and usage is additive per D-03, so this is the intended contract, not a stub.

## Threat Flags

None — both routes are the exact surface the plan's threat register models (T-03-03-01..07); the sanitizer implements the T-03-03-03 mitigation already registered.

## Issues Encountered

- **Pre-staged `.planning/` docs swept into the first commit:** the first `git commit` (unscoped) included the previously-staged `.planning/REQUIREMENTS.md`/`ROADMAP.md`/`STATE.md` modifications alongside the task files. Soft-reset and re-committed with an explicit pathspec so the final commit (`ffa240d`) contains only the 3 task files; the `.planning/` staged state was restored exactly as found. `.gitignore` modification left untouched.

## User Setup Required

None — no API keys needed. The two live-shape tests run against the host Ollama when reachable (present in this dev environment) and skip cleanly in CI (D-12). Env-gated skip count: 1 (embed live-key) + 2 (Ollama shape tests when unreachable).
