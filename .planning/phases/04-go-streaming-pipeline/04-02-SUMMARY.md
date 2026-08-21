---
phase: 04-go-streaming-pipeline
plan: 02
subsystem: queue-worker
tags: [asynq, ai-ingest, pip-01, worker]
requires: [04-01, 04-03]
provides: [ai:doc-ingest task, DocIngestTaskHandler, setup wiring]
affects: [04-04, 04-05]
tech-stack:
  added:
    - "backend/internal/queue/handlers/doc_ingest_handler.go — DocIngestTaskHandler (core-db status writes, engine seam call, D-04 classification)"
    - "backend/internal/queue/handlers/doc_ingest_handler_test.go — fake EngineClient (embedded interface) + gorm sqlite :memory: harness"
  patterns:
    - "queue.TaskHandlers field + RegisterTaskHandlers (existing pattern, no handler_set.go)"
    - "single shared engine client injected at startup (never constructed inside handler/factory)"
    - "100ms bounded ctx on every status write (Rule B2); best-effort notifications (B9)"
key-files:
  created:
    - backend/internal/queue/handlers/doc_ingest_handler.go
    - backend/internal/queue/handlers/doc_ingest_handler_test.go
  modified:
    - backend/internal/queue/tasks.go
    - backend/internal/queue/tasks_test.go
    - backend/internal/router/setup.go
decisions:
  - "Worker retry semantics live per-error in the handler: permanent 4xx → asynq.SkipRetry + failed row; transient 5xx/network/timeout → returned error so asynq backoff retries (MaxRetry(5) caps total attempts) — no infinite spin (D-04)"
  - "Row is set to 'extracting' BEFORE the engine call so a worker crash resumes from committed state and retries reuse the same document_id → Python ON CONFLICT DO NOTHING prevents duplicate vectors (PIP-01)"
  - "DocIngest registered AFTER notificationService creation (wiring order — taskHandlers block at ~line 290 precedes service at ~line 586); asynq mux is live so late registration is safe before 04-04 enqueues"
  - "Single engine.NewClient(cfg.AI.EngineURL, cfg.AI.EngineToken) constructed in setup.go and injected into the handler factory — factory never constructs internally; same instance reused by 04-05 chat relay"
  - "Quality metrics (Pages/OcrPages/Chars/Chunks) copied from IngestDocumentResponse into the row on success (D-03)"
  - "Terminal-state metrics only: QueueProcessedTotal{success|failed} + QueueFailedTotal — no signal on intermediate states (D-09)"
metrics:
  duration: "7m39s"
  completed: "2026-08-01T14:03:31Z"
  files_changed: 5
  commits: 3
---

# Phase 04 Plan 02: ai:doc-ingest Queue Worker Summary

One-liner: asynq `ai:doc-ingest` worker handler that loads the shared-schema `ai_documents` row, calls the engine seam exactly once per file, classifies permanent vs transient failures (D-04), transitions the row through extracting → ready/failed with quality metrics, emits terminal-state metrics (D-09) and best-effort notifications (D-08).

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | TypeDocIngest + DocIngestPayload in tasks.go (+ round-trip test) | `3c01b74` | tasks.go, tasks_test.go |
| 2 | DocIngestTaskHandler — load row, classify error, update status, notify | `fe73971` | doc_ingest_handler.go (new) |
| 3 | Wire into TaskHandlers + setup.go + unit tests with fake engine | `aed9a7c` | tasks.go, tasks_test.go, doc_ingest_handler_test.go (new), setup.go |

## Key Implementation Details

- **Task contract**: `TypeDocIngest = "ai:doc-ingest"` const + `DocIngestPayload{JobID string}` — JobID is the `ai_documents.id`, passed to the engine as `document_id` so retries (and worker restarts) reuse the same ID and the Python `ON CONFLICT DO NOTHING` never duplicates vectors.
- **Handler flow** (strict order, each stage commits so a crash resumes from the last committed state):
  1. Unmarshal payload → poisoned/malformed → `asynq.SkipRetry` (dies fast, never retries forever)
  2. Load row by `id` only (schema header derived from the row's own SchoolID, never from payload)
  3. `extracting` + save (100ms bounded ctx, Rule B2; write errors propagate — B9)
  4. Exactly ONE `IngestDocument` call per file (PIP-01)
  5. Error classification via `errors.As(err, &se)`:
     - 4xx → `failed` + `ErrorReason "permanent: <body>"` + `asynq.SkipRetry`
     - 5xx/network/timeout/nil-response → returned error (asynq backoff retry, MaxRetry(5) caps)
  6. Success → `ready` + quality metrics from response, then notify + metric
- **Wiring**: `TaskHandlers.DocIngest` field + `RegisterTaskHandlers` registration (same path as all existing handlers; no `handler_set.go`). setup.go constructs the single shared `engineClient` and injects it via `NewDocIngestTaskHandler(db, engineClient, notificationService)`.
- **Tests (9 scenarios)**: malformed payload, empty job_id, row-not-found, permanent 400 (failed + SkipRetry + reason + exactly-once), transient 503 (error + row stays extracting), network error (error + row stays extracting), nil response without error (transient), success (ready + quality metrics + exactly-once + `school_7` schema header derived from row), plus a registration test proving `TypeDocIngest` routes via `mux.ProcessTask` (mux.Handler would return NotFoundHandler otherwise).

## Verification

```
go build ./...                          ✔
go test ./internal/queue/...            ✔ (queue 0.018s, handlers 0.053s)
golangci-lint run ./internal/queue/...  ✔
grep must_haves (all three artifacts)   ✔
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Nil-response guard added**
- **Found during:** Task 2
- **Issue:** The seam interface returns `*IngestDocumentResponse`; a contract-violating nil response with a nil error would panic on `resp.Pages`.
- **Fix:** Treat nil-response-without-error as a transient error (`fmt.Errorf("doc ingest: engine returned nil response without error")`) so asynq retries instead of crashing the worker.
- **Files modified:** doc_ingest_handler.go
- **Commit:** `fe73971`

**2. [Rule 3 - Blocking] Wiring order: notificationService created after the taskHandlers block**
- **Found during:** Task 3
- **Issue:** `taskHandlers := queue.TaskHandlers{...}` + `RegisterTaskHandlers` sit at ~line 290/313, but `notificationService` is created at ~line 586 — the doc-ingest handler needs the service for D-08 notifications, so it cannot be wired in the original block.
- **Fix:** Registered the DocIngest handler after `notificationService` creation (single extra `queue.RegisterTaskHandlers(queueWorker.Mux(), taskHandlers)` call — idempotent for already-registered handlers). The asynq mux is live, so this is safe: no `ai:doc-ingest` task can exist until 04-04's upload endpoint enqueues one.
- **Files modified:** setup.go
- **Commit:** `aed9a7c`

### Not Deviations (minor nits)

- `DocIngest` field uses named params `func(ctx context.Context, t *asynq.Task) error` vs the plan's unnamed `func(context.Context, *asynq.Task) error` — identical type.
- Plan pseudo-code referenced `metrics.QueueProcessedTotal`; actual metrics live in the `queue` package (`queue.QueueProcessedTotal`) — used the real symbols.
- Pre-existing lint/todo noise (tasks.go:115 "placeholder" comment, `context.Background` usages in unrelated handlers) is out of scope and unchanged.

## Auth Gates

None — no external service credentials were required.

## Known Stubs

None — the handler is fully functional end-to-end. The engine client points at the configured `AI.EngineURL`/`AI.EngineToken` (fail-fast validated at startup, B12); a live engine is not required for the queue worker to run (transient errors simply retry until MaxRetry(5), then fail the row with a reason).

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surfaces introduced. The handler consumes the existing queue and calls the existing engine seam; notifications reuse the existing `NotificationService.Create` path.

## Self-Check: PASSED

Verified: doc_ingest_handler.go, doc_ingest_handler_test.go, 04-02-SUMMARY.md exist; commits `3c01b74`, `fe73971`, `aed9a7c` present on `backend` branch `dev`.
