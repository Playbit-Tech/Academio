---
phase: 05-go-integration-orchestrator
plan: 02
subsystem: api
tags: [go, ai, model-router, failover, python, sse, circuit-breaker, provider]

# Dependency graph
requires:
  - phase: 05-go-integration-orchestrator
    provides: "05-01 AI orchestrator (rate limiting, quota, cost ledger, cache) + AIEngine seam with Embed endpoint"
provides:
  - "Python engine providers (anthropic, deepseek, openrouter, azure-openai, ollama) wired into the Go ModelRouter with two-level routing"
  - "StreamChat SSE relay routed through the provider router with D-16 failover-before-first-byte"
  - "Full D-05 envelope passthrough (delta/citation/usage/error/done) from Python engine to browser frames"
  - "Hermetic end-to-end streaming test (real ModelRouter + engine SSE stub)"
affects: [05-go-integration-orchestrator, frontend-ai-stream]

# Tech tracking
tech-stack:
  added: [contextkeys leaf package for request-ID context, OpenAIBaseURL override for OpenAI-compatible gateways]
  patterns:
    - "Import-cycle avoidance: engine package never imports internal/ai; adapter in package ai bridges via exported engine.PythonProvider interface"
    - "Two-level routing: Go ModelRouter picks python:{name} by longest-match strings.Contains; Python makes internal provider choices"
    - "D-16 streaming failover: switch providers only BEFORE first byte; after first byte error is returned as-is"
    - "Envelope passthrough: StreamChunk.EventType/EventData relayed verbatim; terminal done synthesized by relay"

key-files:
  created:
    - backend/internal/ai/gateway_test.go
    - backend/internal/ai/engine/embed_spike_test.go
    - backend/internal/contextkeys/contextkeys.go
  modified:
    - backend/internal/ai/gateway.go
    - backend/internal/ai/engine/python_provider.go
    - backend/internal/ai/model_router.go
    - backend/internal/ai/cost.go
    - backend/internal/ai/config.go
    - backend/internal/ai/openai.go
    - backend/internal/ai/engine/client.go
    - backend/internal/middleware/requestid.go
    - backend/internal/modules/ai/stream.go
    - backend/internal/modules/ai/handler.go
    - backend/internal/modules/ai/stream_test.go
    - backend/internal/router/setup.go
    - backend/internal/config/config.go

key-decisions:
  - "Longest-match provider resolution: strings.Contains(model, pType) with max-length wins — fixes azure-openai vs openai substring collision (D-13)"
  - "pythonProvider adapter lives in package ai (gateway.go), not engine — breaks the ai → engine → middleware → ai import cycle via new leaf contextkeys package"
  - "OpenAIBaseURL (AI_OPENAI_BASE_URL) added: self-hosted/OpenAI-compatible gateway support AND hermetic CI failover tests without real network"
  - "D-16 streaming failover tracked via wrapped callback: EventType passthrough chunks count as delivered, so failover never duplicates sent frames"

patterns-established:
  - "Leaf context-key package (internal/contextkeys) for cross-package context values without import cycles"
  - "Adapter-bridge pattern: unexported engine-side provider + exported interface + adapter in consumer package"
  - "SSE stub server pattern for hermetic end-to-end AI streaming tests"

requirements-completed: [INT-04]

# Metrics
duration: 43min
completed: 2026-08-02
---

# Phase 05 Plan 02: Python Providers in Go ModelRouter Summary

**Go ModelRouter now routes to five Python engine providers (anthropic, deepseek, openrouter, azure-openai, ollama) with two-level failover, and the StreamChat SSE relay streams through the provider router with D-16 failover-before-first-byte and full D-05 envelope passthrough**

## Performance

- **Duration:** 43 min (task commits 2026-08-02T00:24:54Z → 01:07:40Z)
- **Started:** 2026-08-02T00:24:54Z (first task commit)
- **Completed:** 2026-08-02T01:07:40Z (last task commit)
- **Tasks:** 5 (4 implementation + summary)
- **Files modified:** 17 backend files (9 created/modified in Task 4 commit)

## Accomplishments
- NewProvider appends 5 discrete Python provider entries after Gemini/OpenAI when AI_ENGINE_URL + AI_ENGINE_TOKEN are set; each gets its own circuit breaker; embeddings/count-tokens stay on providers[0] (T-05-06)
- resolveProvider uses longest-match (D-13) so python: subtypes always beat substring-colliding primaries (fixed azure-openai vs openai bug)
- pythonProviderAdapter bridges the engine seam to ai.Provider: GenerateText (D-08 cost ledger), GenerateTextStream (full envelope relay), GenerateEmbeddings (canonical 1536-dim, D-05 order), CountTokens (local estimate)
- ModelRouter.GenerateTextStream implements D-16: failover only before first byte; envelope passthrough chunks count as delivered
- StreamChat now dual-path: provider path (preferred, D-16 failover) + engine-direct fallback (preserves original D-05 tests)
- StreamChunk extended with EventType/EventData for verbatim envelope passthrough (delta/citation/usage; error aborts; done deduped)
- Setup wires WithAIProvider so /ai/chat/stream flows through the router
- Test suite: TestNewProvider_withPythonEntries (5 subtests), TestModelRouterStreamingFailover* (D-16), TestPythonProviderEmbedSpike, TestStreamChatThroughProvider (3 subtests incl. real end-to-end)

## Task Commits

Each task was committed atomically:

1. **Task 1: pythonProvider engine seam + EngineClient.Embed** - `c410e26` (feat)
2. **Task 2: pythonProvider adapter + cost + routing** - `c410e26` (part of Task 1 commit — combined in execution)
3. **Task 3: wire python providers into ModelRouter + adapter** - `7e28bc0` (feat)
4. **Task 4: route StreamChat through ModelRouter provider** - `8eccad2` (feat)

**Plan metadata:** pending (docs commit auto-skipped — commit_docs=false)

## Files Created/Modified
- `backend/internal/ai/gateway.go` - ProviderPython const, pythonProviderSubtypes, ParseProvider python cases, NewProvider python entries, pythonProviderAdapter (GenerateText/Stream/Embeddings/CountTokens/Close), StreamChunk EventType/EventData, optsModel/optsSystemPrompt helpers
- `backend/internal/ai/engine/python_provider.go` - exported PythonProvider interface, NewPythonProvider, modelPrefix composite naming
- `backend/internal/ai/model_router.go` - longest-match resolveProvider, D-16 stream failover, delivered tracking for envelope chunks
- `backend/internal/ai/cost.go` - defaultCosts python subtype pricing
- `backend/internal/ai/config.go` - OpenAIBaseURL field + FromAppConfig mapping
- `backend/internal/ai/openai.go` - OpenAIBaseURL option wiring
- `backend/internal/config/config.go` - AI_OPENAI_BASE_URL env
- `backend/internal/ai/engine/client.go` - contextkeys-based request-ID, StatusError wrapping on Chat/Embed
- `backend/internal/contextkeys/contextkeys.go` - leaf context key package (import-cycle fix)
- `backend/internal/middleware/requestid.go` - stores request ID under both legacy and contextkeys keys
- `backend/internal/modules/ai/stream.go` - dual-path StreamChat (provider preferred, engine fallback)
- `backend/internal/modules/ai/handler.go` - aiProvider field + WithAIProvider setter
- `backend/internal/modules/ai/stream_test.go` - TestStreamChatThroughProvider + 2 subtests
- `backend/internal/router/setup.go` - WithAIProvider wiring
- `backend/internal/ai/gateway_test.go` (new) - provider selection + D-16 streaming tests
- `backend/internal/ai/engine/embed_spike_test.go` (new) - TestPythonProviderEmbedSpike

## Decisions Made
- **Adapter in consumer package (not engine):** pythonProviderAdapter lives in gateway.go so package engine never imports internal/ai — breaks the ai → engine → middleware → ai cycle. The engine exposes only the exported PythonProvider interface.
- **Longest-match provider resolution:** fixes the azure-openai/openai substring collision where a python:azure-openai model would incorrectly route to the openai primary.
- **OpenAIBaseURL override:** added AI_OPENAI_BASE_URL for OpenAI-compatible gateways (LiteLLM, Azure, OpenRouter proxies) — also enables hermetic CI failover tests via httptest without real network.
- **D-16 failover semantics:** wrapped callback tracks delivered on Text/Done/EventType; failover only before first byte; after first byte errors propagate wrapped with "no failover (D-16)" context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Azure-openai vs openai substring collision in provider matching**
- **Found during:** Task 3 (ModelRouter provider selection)
- **Issue:** First-match resolveProvider routed "python:azure-openai:..." to primary "openai" (strings.Contains substring collision)
- **Fix:** Longest-match wins; python: subtypes always beat primaries
- **Files modified:** backend/internal/ai/model_router.go, gateway_test.go
- **Verification:** TestNewProvider_withPythonEntries subtests
- **Committed in:** 7e28bc0

**2. [Rule 3 - Blocking] ai → engine → middleware → ai import cycle**
- **Found during:** Task 3 (pythonProvider adapter referencing middleware)
- **Issue:** engine/client.go used middleware.GetRequestIDFromCtx, and engine is imported by internal/ai → cycle
- **Fix:** New leaf package internal/contextkeys; engine reads ctx value directly; middleware stores under both keys
- **Files modified:** backend/internal/contextkeys/contextkeys.go (new), engine/client.go, middleware/requestid.go, engine tests
- **Verification:** go build ./... + full test suite
- **Committed in:** 7e28bc0

**3. [Rule 2 - Missing Critical] OpenAIBaseURL override**
- **Found during:** Task 4 (hermetic failover test)
- **Issue:** openai primary hardcoded to api.openai.com — end-to-end failover test would need real network
- **Fix:** Added OpenAIBaseURL config (AI_OPENAI_BASE_URL) — standard for OpenAI-compatible gateways, also enables httptest-based failover tests
- **Files modified:** config.go (both), ai/config.go, ai/openai.go
- **Verification:** TestStreamChatThroughProviderPythonEndToEnd
- **Committed in:** 8eccad2

---

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing capability)
**Impact on plan:** All fixes necessary for correctness (matching bug), buildability (cycle), and hermetic testability (base URL). No scope creep.

## Issues Encountered
- **Idle-connection goroutine leak in end-to-end test:** engine client's transport kept keep-alive connections to the httptest stub, tripping assertNoGoroutineLeak. Fixed by closing the stub server explicitly before the leak check.
- **buildTag safety:** NewProvider guards python appending with `if cfg.EngineURL != "" && cfg.EngineToken != ""` — no accidental single-provider regression.

## User Setup Required

None - no external service configuration required. AI_ENGINE_URL/AI_ENGINE_TOKEN already exist; AI_OPENAI_BASE_URL is optional (defaults to official OpenAI endpoint).

## Next Phase Readiness
- ModelRouter now covers Gemini, OpenAI, and 5 Python providers — ready for phase 05-03 (verification/cross-cutting concerns)
- Frontend AI streaming can rely on the unified envelope contract (delta/citation/usage/error/done) regardless of provider
- Integration test: `make db-init && make migrate && make seed && ./bin/server` + `backend/scripts/test_endpoint.sh` remains the full-flow gate

## Self-Check: PASSED

- [x] SUMMARY.md exists: `.planning/phases/05-go-integration-orchestrator/05-02-SUMMARY.md`
- [x] Commit c410e26 exists (Task 1: pythonProvider engine seam + Embed)
- [x] Commit 7e28bc0 exists (Task 3: python providers in ModelRouter + adapter)
- [x] Commit 8eccad2 exists (Task 4: StreamChat through provider router)
- [x] `verify artifacts` — all 4 pass
- [x] `verify key-links` — all 3 verified
- [x] go build ./... + go vet + full test suites green

**Note on plan `<verification>` test names:** the plan's verification block lists
`TestModelRouter_withPython` and `TestAIEndpoints`, but its own authoritative
requirements specify `TestNewProvider_withPythonEntries` (artifact `contains:`) and
`TestStreamChatThroughProvider` (Task 4 `<verify>`). Both exist and pass; the
verification-block names were superseded during planning (provider-selection test
was renamed to match the artifact contract; the handler test was scoped to the
streaming path). No behavioral gap — full suites run green.

---
*Phase: 05-go-integration-orchestrator*
*Completed: 2026-08-02*
