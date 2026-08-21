---
phase: 04-go-streaming-pipeline
reviewed: 2026-08-01T16:10:00Z
depth: standard
files_reviewed: 35
files_reviewed_list:
  - backend/internal/router/setup.go
  - backend/internal/router/router.go
  - backend/internal/queue/tasks.go
  - backend/internal/queue/client.go
  - backend/internal/queue/config.go
  - backend/internal/queue/worker.go
  - backend/internal/queue/metrics.go
  - backend/internal/queue/handlers/doc_ingest_handler.go
  - backend/internal/queue/handlers/doc_ingest_handler_test.go
  - backend/internal/queue/tasks_test.go
  - backend/internal/ai/engine/engine.go
  - backend/internal/ai/engine/client.go
  - backend/internal/ai/engine/sse.go
  - backend/internal/ai/engine/client_test.go
  - backend/internal/ai/engine/client_ingest_test.go
  - backend/internal/database/models/ai_document.go
  - backend/internal/database/migrations/core/ai_documents.go
  - backend/internal/database/migrations/core/core.go
  - backend/internal/modules/ai/dto.go
  - backend/internal/modules/ai/handler.go
  - backend/internal/modules/ai/service.go
  - backend/internal/modules/ai/repository.go
  - backend/internal/modules/ai/stream.go
  - backend/internal/modules/ai/stream_test.go
  - backend/internal/modules/notifications/service.go
  - backend/internal/modules/notifications/repository.go
  - backend/internal/database/migrations/school/school.go
  - backend/internal/database/tenant/schema_db.go
  - backend/internal/config/config.go
  - backend/internal/helpers/helpers.go
  - ai-engine/app/api/extract.py
  - ai-engine/app/documents/pipeline.py
  - ai-engine/tests/test_documents.py
  - backend/.env.example
  - backend/docker-compose.yml
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 04: Code Review Report — SSE Streaming + Document Pipeline

**Reviewed:** 2026-08-01T16:10:00Z
**Depth:** standard (full per-file reads + cross-file verification against AGENTS.md rules B1–B12 and plan decisions D-01..D-09)
**Files Reviewed:** 35
**Status:** issues_found

## Summary

Reviewed the Phase 04 Go backend (ai-engine client seam, `ai:doc-ingest` asynq worker, `ai_documents` shared-schema model/migration, upload + status API, SSE chat relay) and the ai-engine Python `document_id` passthrough. Overall the implementation is high quality: Rule B1/B2/B3/B4/B7/B8/B9/B11/B12 compliance is consistently maintained, the SSE relay (bounded 64-cap channel, heartbeat, slow-client abort, single `done` synthesis, in-band errors) and the worker's permanent-vs-transient classification are both well-reasoned and well-tested.

However, there is **one critical startup-blocking bug** (duplicate asynq handler registration panics at boot) and **four warnings** that undermine three of the phase's core contracts: the upload allowlist (docx/pptx/txt/csv rejected by content sniffing), the D-04 terminal-failure guarantee (rows stuck in `extracting` after retry exhaustion), the D-08 notification path (writes to the wrong schema, so notifications never land), and the SSE route verb (GET vs the plan's required POST).

## Critical Issues

### CR-01: Duplicate asynq handler registration panics at server startup

**File:** `backend/internal/router/setup.go:602` (first registration at `:319`)

**Issue:** `queue.RegisterTaskHandlers(queueWorker.Mux(), taskHandlers)` is called twice on the same `asynq.ServeMux`. The first call (line 319) registers `email:send`, `sms:send`, `whatsapp:send`, `report:generate`, `ai:scoring`, `provisioning:school`. The second call (line 602, after `taskHandlers.DocIngest` is set) re-registers every non-nil handler. asynq v0.26.0's `ServeMux.Handle` panics on duplicate patterns — verified with a minimal reproduction:

```
PANIC: asynq: multiple registrations for email:send
```

`NewRouter` runs this unconditionally (no `cfg.AI.Enabled` gate), and `main.go` calls it without recovery — **the server crashes at startup and Phase 04 never boots**. The comment at 597-599 ("the asynq mux is live, so this late registration is safe") is wrong: it is safe with respect to task delivery, but the *mux* itself rejects the second `HandleFunc` call.

**Fix:** Register only the single new pattern on the second call:

```go
// setup.go:600-602
docIngestHandler := handlers.NewDocIngestTaskHandler(db, engineClient, notificationService)
queueWorker.Mux().HandleFunc(queue.TypeDocIngest, docIngestHandler.HandleDocIngest)
logger.Info("Doc ingest task handler registered")
```

Alternatively, set `taskHandlers.DocIngest` before the first `RegisterTaskHandlers` call at line 319 (requires moving `notificationService` construction earlier, since the handler depends on it).

## Warnings

### WR-01: Content-type sniff rejects txt/csv/docx/pptx uploads (allowlist is only half functional)

**File:** `backend/internal/modules/ai/service.go:60-69, 121-124`

**Issue:** The sniff check compares `http.DetectContentType(buf[:n])` for exact membership in `allowedContentTypes`. Verified behavior of Go's sniffer (reproduced in a test program):

- `.txt` / `.csv` → `text/plain; charset=utf-8` — the bare `text/plain` key never matches.
- `.docx` / `.pptx` → `application/zip` (OOXML files are ZIP containers) — the `application/vnd.openxmlformats-...` keys are never produced by the stdlib sniffer.
- `application/octet-stream` is accepted, but browsers send the real types for these files, not octet-stream.

Net effect: of the 9 advertised extensions (`allowedExts`, and the handler swagger), only **pdf/png/jpg/jpeg/gif** actually pass. Any real `.docx`, `.pptx`, `.txt`, or `.csv` upload returns 400 `upload_failed` — four of the six document formats the pipeline exists to ingest are rejected before they reach the engine.

**Fix:** Normalize the sniffed type before the map lookup:

```go
contentType := http.DetectContentType(buf[:n])
// text/* comes back with a charset param; docx/pptx sniff as zip containers
if strings.HasPrefix(contentType, "text/plain") {
    contentType = "text/plain"
}
if contentType == "application/zip" && (ext == ".docx" || ext == ".pptx") {
    contentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}
if !allowedContentTypes[contentType] && contentType != "application/octet-stream" {
    return nil, fmt.Errorf("%w: %q", ErrUnsupportedContentType, contentType)
}
```

(Simpler alternative: since `ext` already passed the allowlist, treat any sniffed type that is either allowlisted or `application/zip`/`text/*` as acceptable and let the engine do the real validation.)

### WR-02: Transient retry exhaustion never marks the row failed — docs hang in `extracting` (D-04 gap)

**File:** `backend/internal/queue/handlers/doc_ingest_handler.go:109`

**Issue:** On transient errors the handler returns the error and asynq retries (correct). But when retries are exhausted, asynq archives the task **without invoking the handler again** — so the final-failure transition never runs. The `ai_documents` row stays in `extracting` with no `error_reason`, no failure notification (D-08), and no `QueueProcessedTotal{failed}`/`QueueFailedTotal` metric (D-09). This violates D-04's own requirement ("neither can spin forever"; "final fail → status failed + JSON reason") and the user is never told their document failed.

**Fix:** On the last attempt, mark the row failed before returning the transient error:

```go
// doc_ingest_handler.go:109
if asynq.GetRetryCount(ctx) >= asynq.GetMaxRetry(ctx) {
    doc.Status = models.DocumentStatusFailed
    doc.ErrorReason = fmt.Sprintf("transient (retries exhausted): %s", err)
    if uerr := h.saveDoc(ctx, &doc); uerr != nil {
        return fmt.Errorf("doc ingest mark failed: %w", uerr)
    }
    h.recordFailure(ctx, &doc)
}
return fmt.Errorf("doc ingest transient: %w", err)
```

### WR-03: D-08 notifications always fail — `notifications` table is tenant-schema, worker writes via core DB

**File:** `backend/internal/queue/handlers/doc_ingest_handler.go:179` (with `backend/internal/modules/notifications/service.go` `Create` and `backend/internal/database/migrations/school/school.go:185`)

**Issue:** The worker calls `h.notifications.Create(ctx, nil, ...)` with a nil tenantDB. `NotificationService.Create` falls back to `s.repo.GetDB()` — the **core DB** (`NewNotificationRepository(db)` at `setup.go:589`) — so the INSERT targets the **public** schema. The `notifications` table is created only in tenant schemas (school migration group, `school.go:185`; no public-schema equivalent exists). Every insert fails with `relation "notifications" does not exist`, which is silently swallowed by the best-effort handler (B9). The `ws.UserRoom` broadcast (inside `Create`, after the insert) never fires. **No "Document ready" / "Document processing failed" notification is ever delivered** — D-08 is dead in production, despite the plan's assertion that "`Create` with a nil tenantDB is fine — it broadcasts via the hub."

**Fix:** Derive a tenant-scoped `*gorm.DB` from the row's `SchoolID` (the same mechanism the `GetTenantDB` middleware uses) and pass it as the tenantDB:

```go
// doc_ingest_handler.go notify()
tenantDB := tenant.NewSchemaDB(h.db, "school_"+strconv.FormatUint(uint64(doc.SchoolID), 10)).DB()
if _, err := h.notifications.Create(ctx, tenantDB, doc.UploadedBy, doc.SchoolID, title, message, "ai_document"); err != nil {
    logger.Warnf("doc ingest: notification failed (best-effort): %v", err)
}
```

### WR-04: SSE route registered as GET, plan requires POST — GET-with-JSON-body is a fragile contract

**File:** `backend/internal/router/router.go:278` vs `04-05-PLAN.md:280, 297`

**Issue:** The plan's own verification criterion (`04-05-PLAN.md:297`) requires `api.POST("/ai/chat/stream", aiHandler.StreamChat)`, and its smoke test uses `curl -d` (which forces POST). The implementation registers `ai.GET("/chat/stream", ...)` and binds a JSON body on a GET request. GET-with-body is legal in Go and works through nginx/Vite proxies, but it is stripped by several CDNs/WAFs and HTTP client stacks, cannot be used with `EventSource`, and deviates from the documented plan. The 04-05 summary's justification ("per plan must_have GET") misreads the plan — the grep-able string `chat/stream` matches both verbs, but the explicit code snippet and criterion say POST.

**Fix:** Register POST to match the plan (and the `curl -d` smoke instructions):

```go
// router.go:278
ai.POST("/chat/stream", aiHandler.StreamChat) // SSE relay (INT-01, D-05)
```

If GET is intentionally preferred (e.g., to allow `EventSource`-style consumption without a body), the plan's criterion must be amended to match, and the frontend integration must be constrained to clients that carry GET bodies.

## Info

### IN-01: `docIngestDBTimeout = 100ms` is very tight for a shared Postgres

**File:** `backend/internal/queue/handlers/doc_ingest_handler.go:23`

**Issue:** Every DB op in the worker (`loadDoc`, `saveDoc`) is bounded at 100 ms. Deliberate per the comment, but a momentary DB stall under load will fail the `mark extracting` write, fail the task, and burn one of the 5 retries — noisy flap for no user value.

**Fix:** Raise to ~1-2s (still far below the 6-minute task timeout) so only genuinely hung DB operations fail the task.

### IN-02: `GetDocumentStatus` maps every error to 404

**File:** `backend/internal/modules/ai/handler.go:357-361`

**Issue:** DB failures (e.g., an outage) are reported as `document_not_found`, masking server-side problems from the client and from monitoring.

**Fix:** Distinguish not-found (`gorm.ErrRecordNotFound` → 404) from other errors (→ 500 `document_status_failed`).

### IN-03: Dead code — empty `UploadDocumentRequest` struct

**File:** `backend/internal/modules/ai/dto.go:8`

**Issue:** `UploadDocumentRequest struct{}` is unused (the upload endpoint consumes `multipart/form-data` via `c.FormFile`, not a JSON body). Remove it.

### IN-04: `.gif` in the allowlist beyond the D-06 spec's 8 extensions

**File:** `backend/internal/modules/ai/service.go:53`

**Issue:** `.gif` was added to `allowedExts` (and to the handler swagger) though the D-06 spec allowlist lists 8 extensions (pdf/docx/pptx/txt/csv/png/jpg/jpeg). Harmless, but the spec and implementation should agree — either keep and document `.gif` or remove it for strict D-06 conformance. (Note: the ai-engine Python extract path must accept GIFs if it is retained.)

---

## Verified-Clean Highlights (no findings)

- **SSE relay** (`stream.go`): bounded 64-cap channel, `default`-branch slow-client abort that cancels upstream ctx, engine-`done` dedup + single synthesized terminal `done`, `: ping` heartbeat ≤ 30s, `X-Accel-Buffering: no`, `data: {json}\n\n` framing, in-band error events, nil-client guard before header flush. Tests cover the full-buffer abort path.
- **Worker classification** (`doc_ingest_handler.go`): permanent 4xx → `failed` + `SkipRetry`; transient → retry; poisoned payload / missing job → `SkipRetry`; nil-response guard; row re-read per attempt (restart-safe, exactly-once ingest via `document_id` + Python `ON CONFLICT DO NOTHING`).
- **Upload pipeline** (`service.go`): ext allowlist before reading bytes, `MaxBytesReader` + `header.Size` cap, server-generated `{id}.{ext}` path (no traversal), row-before-file ordering, post-create failures always mark the row failed, enqueue with `asynq.Timeout(6m)` + `MaxRetry(5)` (correctly noting the server does not apply `QueueConfig.MaxRetries`).
- **Rules B1-B13**: no error discards, no `context.Background()` in request/worker code, `pkg/logger` only, no multi-statement `Exec`, no `fmt.Sprintf` SQL, tenant queries via schema prefix, B12 fail-fast config validation (`AI_ENGINE_URL` URL-validated, `AI_UPLOADS_DIR` absolute, `AI_MAX_DOC_MB` capped at 200), B11 audit log on upload.
- **D-01**: `ai_documents` correctly lives in the shared public schema (core migration), school-scoped reads via `GetByIDAndSchoolID`; worker derives `X-School-Schema` from the row, never from the payload.

---

_Reviewed: 2026-08-01T16:10:00Z_
_Reviewer: gsd-code-reviewer agent_
_Depth: standard_

---

## Fix Report (iteration 1 — applied 2026-08-01)

All findings from this review were fixed by the gsd-code-fixer agent and committed atomically inside `backend/` (submodule branch `dev`). Info findings (IN-01..IN-04) were deferred per scope (critical + warnings only).

### Fixed

| Finding | Commit | Summary |
|---|---|---|
| CR-01 | `e6f9671` | Second `RegisterTaskHandlers` call replaced with a single `queueWorker.Mux().HandleFunc(queue.TypeDocIngest, ...)` — the first call (line 319) still registers all other handlers; asynq v0.26.0 `ServeMux.Handle` duplicate-pattern panic eliminated, server boots. |
| WR-01 | `9bc56b1` | `normalizeContentType` in `internal/modules/ai/service.go` strips `; charset=utf-8` from text sniff results and maps `application/zip` → OOXML types for `.docx`/`.pptx`; extension allowlist remains the primary gate. New `service_test.go` proves txt/csv/docx/pptx pass sniffing and reach row creation. |
| WR-02 | `f9fa70a` | `doc_ingest_handler.go`: new `retryExhausted(ctx)` guard (`asynq.GetRetryCount >= GetMaxRetry`, both presence-checked) + shared `markFailed` helper. On the final transient attempt the row is marked `failed` with `transient (retries exhausted): ...` and the D-08/D-09 failure signals fire before the transient error returns (asynq then archives an already-finalized row). Verified end-to-end with a real asynq server integration test (`MaxRetry(0)` → row `failed`, task archived). |
| WR-03 | `f9fa70a` | `notify()` now builds a tenant-scoped handle via `tenant.NewSchemaDB(h.db, "school_"+SchoolID).DB()` and passes it to `NotificationService.Create` — inserts land in the tenant schema's `notifications` table instead of failing against public schema. Best-effort (B9) log-and-continue retained. |
| WR-04 | `db633db` | `router.go` line 278: `ai.GET("/chat/stream", ...)` → `ai.POST("/chat/stream", ...)`; swagger annotation in `stream.go` updated to `[post]`. Handler already binds the JSON body via `ShouldBindJSON` (same as `POST /chat`). |

### Verification results

- `go build ./...` — PASS
- `go test ./internal/modules/ai/... ./internal/queue/... ./internal/config/... ./internal/ai/engine/...` — PASS (all packages ok; new tests: `TestNormalizeContentType`, `TestUploadDocumentSniffingAllowsTxtCSVDocxPptx`, `TestRetryExhausted_PlainContext`, `TestDocIngestHandler_TransientRetryExhausted_MarksFailedAndArchives`)
- `golangci-lint run ./internal/modules/ai/... ./internal/queue/...` — clean (exit 0)
- Grep-verify: `RegisterTaskHandlers` called exactly once in `setup.go`; `ai:doc-ingest` registered exactly once via `HandleFunc`; `chat/stream` route is POST; `retryExhausted`/`markFailed` present in handler; `normalizeContentType` present and used in `service.go`.

### Deferred (Info, not in scope)

- IN-01 `docIngestDBTimeout = 100ms` — defer
- IN-02 `GetDocumentStatus` 404 masking — defer
- IN-03 dead `UploadDocumentRequest` struct — defer
- IN-04 `.gif` allowlist vs D-06 spec — defer

---

_Fixed: 2026-08-01_
_Fixer: gsd-code-fixer agent_
_Iteration: 1_
