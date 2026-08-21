---
phase: 04-go-streaming-pipeline
plan: 05
subsystem: api
tags: [sse, gin, go, streaming, ai-engine, event-source]

# Dependency graph
requires:
  - phase: 04-go-streaming-pipeline
    provides: "04-01 EngineClient seam (ChatStream context-bound, StreamCallback func(EngineEvent) error, StatusError); 04-03 shared ai_documents; 04-02 ai:doc-ingest worker; 04-04 upload + status endpoints + AIHandler.WithDocumentService"
provides:
  - "GET /api/v2/ai/chat/stream — SSE relay streaming the shared envelope (delta | citation | usage | error | done) with bounded channel, heartbeat, slow-client abort, and in-band errors"
  - "AIHandler.StreamChat + engine.EngineClient wiring via non-breaking WithEngineClient setter (single shared engine client per process)"
  - "Unit test suite for the relay (D-10): envelope, buffer-full abort, context cancel, in-band error, heartbeat — all goroutine-leak guarded and -race clean"
affects: [frontend AI assistant streaming integration (INT-01 consumer), Phase 5 INT-03 orchestrator controls, OBS-01 observability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SSE relay pattern: drain upstream stream → bounded channel (cap 64) → select-forward loop; select-default on full buffer cancels upstream ctx (no goroutine leak)"
    - "done-dedup: engine done events dropped in callback; relay synthesizes exactly ONE terminal done on channel close"
    - "In-band error contract: failures after HTTP 200 surface as {\"event\":\"error\"} before the terminal done — one frontend contract for both pre-200 and post-200 failures (ROADMAP criterion 2)"
    - "Heartbeat: ': ping' comment frame ≤30s — safe under EventSource, never breaks SSE parsing"

key-files:
  created:
    - backend/internal/modules/ai/stream.go
    - backend/internal/modules/ai/stream_test.go
  modified:
    - backend/internal/modules/ai/handler.go
    - backend/internal/router/router.go
    - backend/internal/router/setup.go

key-decisions:
  - "Engine seam (04-01) kept behavior-identical — the relay lives in modules/ai, never rescanning the engine's already-parsed SSE stream"
  - "relayBufferSize + heartbeatEvery are package VARS (64, 25s) so tests shrink them — heartbeat ≤30s per D-05"
  - "Nil aiClient guard returns 500 BEFORE SSE headers flush — after the stream starts, failures must be in-band events (T-04-05-03)"
  - "WithEngineClient reuses the SINGLE engine.NewClient instance shared with the ai:doc-ingest worker — grep-verified exactly one call in setup.go"

patterns-established:
  - "SSE relay with bounded channel + slow-client abort + context-bound upstream cancellation"
  - "done-dedup contract between engine done_event (chat.py:197) and relay-synthesized terminal done"

requirements-completed: [INT-01]

# Metrics
duration: 7min
completed: 2026-08-01
---

# Phase 4 Plan 5: SSE Chat Relay Summary

**SSE relay endpoint GET /api/v2/ai/chat/stream bridging the 04-01 engine seam to the browser — bounded 64-cap channel, slow-client upstream abort, 25s heartbeat, and the single delta|citation|usage|error|done envelope with in-band errors (INT-01, D-05)**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-01T14:42:52Z
- **Completed:** 2026-08-01T14:50:12Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `AIHandler.StreamChat` drains `engine.ChatStream` through a bounded channel (cap 64, package var `relayBufferSize`), forwards every event as `data: {json}\n\n` frames in the shared envelope, with `X-Accel-Buffering: no` + `Cache-Control: no-cache` + `text/event-stream` + `keep-alive` headers flushed before the loop (nginx-safe, D-05).
- Slow-client guard: the relay callback's `select { case events <- ev: default: cancel(); return err }` aborts upstream when a client can't keep up — no goroutine leak; engine done events are deduped in the callback (Python emits done_event at chat.py:197) so the relay synthesizes exactly ONE terminal `done` on channel close.
- Heartbeat `: ping` comment frames every 25s (package var `heartbeatEvery`, ≤30s per D-05) keep EventSource/proxies alive; engine `error` events AND ChatStream failures after HTTP 200 both surface as in-band `{"event":"error"}` frames before the terminal done (ROADMAP criterion 2).
- Engine client wired via non-breaking `WithEngineClient` setter reusing the single `engine.NewClient` instance shared with the ai:doc-ingest worker (04-02); route registered `GET /api/v2/ai/chat/stream` inside the authenticated ai group (no unauthenticated streaming, T-04-05-03).
- Unit tests (D-10) prove relay semantics through a fake EngineClient + httptest recorder: envelope passthrough (exactly 5 frames, dedup verified), buffer-full abort (no deadlock), context cancel (no goroutine leak), in-band errors, and heartbeats — all pass with `-race`.

## Task Commits

Each task was committed atomically:

1. **Task 1: stream.go — StreamChat relay with bounded channel, heartbeat, abort, envelope (D-05)** - `b614f15` (feat)
2. **Task 2: Wire engine client into AIHandler + route registration + setup.go (D-05)** - `96a7205` (feat)
3. **Task 3: Unit tests for the relay — envelope, buffer-full abort, context cancel, error passthrough (D-10)** - `b41ef2b` (test)

**Follow-up:** `3975077` (style — gofmt struct alignment + misspell fixes surfaced by the plan's golangci-lint verification)

**Plan metadata:** 04-05 plan docs live in `.planning/` (gitignored, `commit_docs: false`) — not committed per workflow.

## Files Created/Modified
- `backend/internal/modules/ai/stream.go` - `StreamChat` SSE relay: module DTO binding → engine.ChatRequest mapping, bounded relay channel, drainer goroutine with done-dedup callback, heartbeat ticker, forward loop writing `data: {json}\n\n` frames + flush per event
- `backend/internal/modules/ai/stream_test.go` - fake EngineClient, blocking ResponseWriter (slow-client sim), envelope parser, goroutine-leak poller; 6 tests covering envelope, buffer-full abort, context cancel, engine-error event, ChatStream-failure in-band event, heartbeat
- `backend/internal/modules/ai/handler.go` - added `aiClient engine.EngineClient` field + `WithEngineClient` setter (NewAIHandler signature unchanged)
- `backend/internal/router/router.go` - `ai.GET("/chat/stream", aiHandler.StreamChat)` in the authenticated ai group
- `backend/internal/router/setup.go` - `aiHandlerImpl.WithEngineClient(engineClient)` reusing the single shared engine client

## Decisions Made
- Engine seam (engine.go/client.go/sse.go) left untouched — relay is pure-additive in modules/ai, matching the frozen-seam constraint.
- `relayBufferSize`/`heartbeatEvery` as package vars (not consts) so tests can shrink them — `heartbeatEvery = 25 * time.Second` satisfies D-05's ≤30s requirement.
- Nil-client guard placed BEFORE the SSE header flush so a misconfigured handler returns a normal 500 JSON error instead of corrupting a stream (T-04-05-03).
- Buffer-full abort cancels the upstream context immediately AND returns the error from the callback — both paths converge so the drainer goroutine terminates and the relay emits its terminal done.
- Router registered as GET (per plan must_have GET /api/v2/ai/chat/stream), matching the 04-01 engine client's POST /v1/chat/stream upstream call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] aiClient struct field added in Task 1 for compilation**
- **Found during:** Task 1 (stream.go relay)
- **Issue:** The plan's Task 1 code references `h.aiClient`, but the plan files the struct field under Task 2 — Task 1's verify (`go build ./internal/modules/ai/...`) would fail without the field.
- **Fix:** Added the `aiClient engine.EngineClient` field (+ import) to AIHandler in Task 1 as an enabling change; the `WithEngineClient` setter landed in Task 2 exactly as planned.
- **Files modified:** backend/internal/modules/ai/handler.go
- **Verification:** `go build ./internal/modules/ai/...` passes at the end of Task 1.
- **Committed in:** b614f15 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Bonus test for the ChatStream-failure in-band path**
- **Found during:** Task 3 (unit tests)
- **Issue:** The plan's test list covers engine `error` events forwarded mid-stream, but the second half of ROADMAP criterion 2 — "callback error from ChatStream also emits a terminal error event before closing" — had no test.
- **Fix:** Added `TestStreamChatDrainerErrorBecomesInBandEvent` asserting a ChatStream failure after 200 produces exactly [error, done] frames with the engine status in the message.
- **Files modified:** backend/internal/modules/ai/stream_test.go
- **Verification:** `go test ./internal/modules/ai/ -run TestStreamChat -count=1 -race` passes.
- **Committed in:** b41ef2b (Task 3 commit)

**3. [Rule 1 - Bug] setup.go comment broke the `engine.NewClient(` invariant grep**
- **Found during:** Task 2 verification
- **Issue:** My wiring comment contained the literal text `engine.NewClient(...)`, pushing `grep -c "engine.NewClient(" setup.go` from 1 to 2 and failing the plan's acceptance criterion.
- **Fix:** Reworded the comment to avoid the literal call pattern ("constructed exactly once per process").
- **Files modified:** backend/internal/router/setup.go
- **Verification:** `grep -c "engine.NewClient(" internal/router/setup.go` == 1; `go build ./...` passes.
- **Committed in:** 96a7205 (Task 2 commit)

**4. [Rule 1 - Bug] golangci-lint findings in new/changed files**
- **Found during:** Plan verification
- **Issue:** `gofmt` (struct comment alignment in handler.go) + `misspell` (`cancelling`/`cancelled` → `canceling`/`canceled`) in stream.go and stream_test.go.
- **Fix:** `gofmt -w` + spelling corrections. Post-fix `golangci-lint run ./internal/modules/ai/... ./internal/ai/engine/...` is clean (exit 0, no findings).
- **Files modified:** backend/internal/modules/ai/handler.go, stream.go, stream_test.go
- **Verification:** golangci-lint exit 0; tests still green.
- **Committed in:** 3975077 (follow-up style commit)

---

**Total deviations:** 4 auto-fixed (2 bug, 1 missing critical, 1 blocking)
**Impact on plan:** All auto-fixes were necessary for compilation, the plan's own acceptance greps, lint cleanliness, or coverage of a required behavior (ROADMAP criterion 2). No scope creep; the engine seam stayed frozen.

## Issues Encountered
- None — the relay design from 04-01/04-RESEARCH worked as specified. The pre-existing lint findings in unrelated modules (lessonplan.go, session.go, provisioning.go) were confirmed present and logged to `deferred-items.md` per the plan; they are untouched.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- INT-01 endpoint live: `GET /api/v2/ai/chat/stream` streams the shared envelope with heartbeats, bounded buffering, upstream cancellation, and in-band errors. The frontend AI assistant can now consume streaming deltas.
- Phase 5 (INT-03: rate limiting, quota, audit, caching on AI endpoints) has a concrete surface to attach controls to — the new route lives in the same authenticated ai group as 04-04's document routes.
- Manual smoke available once the engine is running: `curl -N -H "Authorization: Bearer <token>" -d '{"message":"hi"}' http://localhost/api/v2/ai/chat/stream` → event-stream headers, `data:` frames, `: ping` heartbeat, terminal done.

---

*Phase: 04-go-streaming-pipeline*
*Completed: 2026-08-01*

## Self-Check: PASSED

- `backend/internal/modules/ai/stream.go` exists ✓
- `backend/internal/modules/ai/stream_test.go` exists ✓
- `.planning/phases/04-go-streaming-pipeline/04-05-SUMMARY.md` exists ✓
- Commits verified in backend submodule: `b614f15` (Task 1), `96a7205` (Task 2), `b41ef2b` (Task 3), `3975077` (style) ✓
- Stub scan on new files: no placeholder/TODO/FIXME patterns ✓
- Backend working tree clean (all changes committed) ✓
