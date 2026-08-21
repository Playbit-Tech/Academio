# Phase 4 Research

Date: 2026-08-01
Sources: live repo inspection (backend/), asynq v0.26.0 docs (Context7), Phase 3 verification artifacts

## 1. asynq v0.26.0 semantics (Context7)

- **`asynq.SkipRetry`**: wrap permanent errors — `return fmt.Errorf("...: %w", asynq.SkipRetry)`. The task is NOT retried; it moves to **archived** state (`asynq:{queue}:archived` in Redis). Used for deterministic client errors (bad payload, validation failure).
- **`IsFailure`** in `asynq.Config`: `func(err error) bool` — if it returns `false` for an error, the task does NOT consume a retry count. Current `worker.go` has `IsFailure: func(err error) bool { return true }` — all errors count as failures. **Keep this** for doc-ingest: transient pipeline errors (503/502/network) SHOULD consume retries and back off. `asynq.SkipRetry` takes precedence at the task level.
- **`RetryDelayFunc`**: existing exponential `delay := cfg.RetryDelayBase * (1 << n)` in `worker.go` — reuse as-is for transient retries.
- **`asynq.MaxRetry(n)`**: enqueue-time option; existing code uses `asynq.MaxRetry(3)` for reportcard/admission AI tasks. Doc-ingest should use a slightly higher bound (e.g. `asynq.MaxRetry(5)`) because embedding config (503) may need a fix window; final failure → archived → status `failed`.
- **`asynq.Timeout(d)`**: enqueue-time per-task timeout. Python `/v1/documents` budget is `extractTimeout` 5m; set `asynq.Timeout(6 * time.Minute)` on the enqueue to give the Python call room within the worker's task timeout. Without it, the default server timeout applies (check `QueueConfig` — `Timeout` field? verify).
- **`asynq.Retention(d)`**: keep task info in Redis after completion for inspection (nice-to-have for DLQ audit; optional — Phase 6 owns dashboards).
- **Queue names**: current `Queues` map `{"default": 3, "provisioning": 1}`. `ai:doc-ingest` should enqueue to **`default`** (weight 3) — it's a normal workload, not provisioning. No new queue needed.
- **TaskInfo inspection**: `asynq.Inspector` (client side) can list archived tasks — this is the DLQ query API for ops; Phase 4 only logs/archives, Phase 6 builds the dashboard on top.

## 2. SSE relay design (gin v1.12.0)

- **Route pattern**: `ai.POST("/chat/stream", aiHandler.StreamChat)` under the existing `authGroup(v2, "/ai", ...)` chain (JWTAuth + EnforceSchoolID + TenantResolution + TenantDBResolver + AuditLogging) — verified in `router.go`.
- **Headers for SSE**: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`, and `X-Accel-Buffering: no` (tells nginx/reverse proxies not to buffer — ROADMAP criterion 1). No `Content-Encoding: gzip` — gin's default `gin.Logger`/`gin.Recovery` do not gzip; gzip middleware must NOT wrap this route (Python side also emits no gzip — D-02). Verify no global gzip middleware wraps `/api/v2/ai` in `setup.go` (check).
- **Writing events**: gin `c.Stream(func(w io.Writer) bool { ... })` is the idiomatic loop (write + return false to stop). Each `EngineEvent` → `data: {json}\n\n`; comment heartbeats `: ping\n\n`; flush via `c.Writer.Flush()` (gin's ResponseWriter supports Flush — SSE requires it).
- **Bounded channel cap 64** (criterion 2): producer goroutine (`ChatStream` callback) does `select { case ch <- ev: case <-ctx.Done(): return }`; the consumer `c.Stream` loop does `select { case ev := <-ch: write; case <-ctx.Done(): return false }`. **Slow-client abort**: if `c.Writer` write blocks (client not reading), the consumer can't drain the channel → channel fills → producer blocks in `select` → but producer must still watch ctx; additionally use a writer-level timeout — if a write can't complete within a grace period, cancel `ctx` (context.WithCancel from `c.Request.Context()`) so upstream Python stops. This is the "slow-client abort" of criterion 2.
- **`r.Context()` propagation**: `ChatStream(ctx, req, cb)` receives `ctx := c.Request.Context()` — client disconnect cancels it → goroutine A's `ChatStream` returns → Python generation stops (no billed unread tokens — criterion 1).
- **In-band error after HTTP 200** (criterion 2): when upstream errors mid-stream (ChatStream returns error), producer pushes `EngineEvent{Type: "error", Data: {message}}` before `done`. When `ChatStream` returns cleanly, producer pushes `done`. Client contract: always check for in-band `error` before `done`.
- **Go-side heartbeat fallback**: Python emits `: ping` ≤25s (F4, `AI_HEARTBEAT_INTERVAL_SECONDS=25.0`). Go relay forwards comment lines verbatim. Defense in depth: if upstream is silent >30s, consumer writes a Go-side `: ping` (ticker goroutine). Belt-and-suspenders against a hung upstream without killing the client connection.
- **SSE-aware scanner**: `engine/sse.go` already implements `scanSSEEvents` with a **1MB buffer cap** (over 64KB default) + comment tolerance + blank-line event boundary + ctx cancellation — satisfies criterion 2's "SSE-aware scanner with buffer beyond the 64 KB default" with ZERO new scanner code.

## 3. Document pipeline (asynq + Python `/v1/documents`)

- **Worker flow** (per PIP-01): upload handler validates+saves+creates row (queued) → enqueues `ai:doc-ingest` → returns 202. Worker: unmarshal payload → set status `extracting` → call `engineClient.IngestDocument(ctx, req)` with `X-School-Schema` header → on success record metrics + status `ready` → notify uploader. On permanent error → `asynq.SkipRetry` + status `failed`. On transient error → return error (retry) leaving status at `extracting`.
- **Idempotency**: `ai_vectors` `UNIQUE(document_id, chunk_index)` + `ON CONFLICT DO NOTHING` (Phase 2 D-09 / Phase 3 verified). Go passes stable `document_id = ai_documents.id` (D-02) so retries after partial write re-ingest with `inserted=0` — no duplicates (criterion 4). Verified in Phase 3: live writes into `school_1.ai_vectors`, idempotency proven.
- **Python response** (`ingest_document` returns): `{status: "success", document_id, chunks, pages, ocr_pages, chars, warnings}` — map to Go `IngestDocumentResponse` for status + quality metrics (D-03/D-07). `chunks=0` + warning "no text extracted" is a SUCCESS (empty doc, not failure) — worker should treat as `ready` with `chunks: 0`, or `failed` if policy requires content (decide: treat as ready-with-0-chunks — matches Python semantics; user sees warning).
- **Timing**: Python call budget 5m (`extractTimeout`). asynq task Timeout must exceed it: `asynq.Timeout(6 * time.Minute)` on enqueue.
- **Upload path safety**: Python `_assert_within_uploads` (F2) rejects paths outside `AI_UPLOADS_DIR`. Go must write inside `/app/uploads` using the SAME env `AI_UPLOADS_DIR=/app/uploads` (currently MISSING from compose — add for backend, worker, ai-engine). Path scheme `/app/uploads/{school_id}/{id}.{ext}`; `id` = `ai_documents.id` UUID. `filepath.Clean` + verify `strings.HasPrefix` (defense against traversal; Rule B7 — no SQL concat; Rule F-adjacent path hygiene).
- **Notification** (event → notify): `NotificationService.Create(ctx, tenantDB=nil, userID, schoolID, title, message, "ai_document_ready"/"ai_document_failed")` — handles DB row + `hub.Broadcast(ws.UserRoom(schoolID,userID), ...)` + FCM + audit (verified in service.go). Worker needs school_id + user_id from payload/row. Best-effort: notification error → `logger.Warnf` + continue (Rule B9).

## 4. Go seam extension (D-07)

- `EngineClient` interface gains `IngestDocument(ctx, IngestDocumentRequest) (*IngestDocumentResponse, error)`.
- `client.go`: POST `/v1/documents` with headers `EngineTokenHeader`, `RequestIDHeader` (from ctx), `X-School-Schema` (header, from caller). JSON body `{document_path, collection, document_id}`. Budget: `extractTimeout` (5m) — reuse the existing per-method timeout plumbing.
- `engine.go`: add `IngestDocumentRequest{DocumentPath, Collection, DocumentID}` + `IngestDocumentResponse{Status, DocumentID, Chunks, Pages, OcrPages, Chars, Warnings}`.
- Wire in `setup.go`: `engineClient := engine.NewClient(cfg.AI.EngineURL, cfg.AI.EngineToken)` when `cfg.AI.Enabled`; inject into `AIHandler` (`WithEngineClient`) and into the doc-ingest handler factory `newAIDocIngestHandler(db, engineClient, notifier)`.
- `proto/aiengine.proto` already declares `IngestDocument` (Phase 3 criterion 1) — REST 1:1 preserved.

## 5. Existing patterns to reuse (verified)

| Concern | File | Pattern |
|---|---|---|
| asynq client | `backend/internal/queue/client.go` | `QueueClient.Enqueue(task, opts...)` |
| task payload types | `backend/internal/queue/tasks.go` | `TypeXxx` constants + `XxxPayload` structs; `TaskHandlers` func fields |
| worker wiring | `backend/internal/router/setup.go:290` + `newAIScoringHandler` | factory funcs registered on mux |
| tenant headers | `backend/internal/middleware/tenant.go` | `GetSchoolIDFromCtx`, `GetUserIDFromCtx` |
| response helpers | `backend/pkg/response` | `Success`, `Error(status, code, msg, category)` |
| authGroup | `backend/internal/router/router.go` | full JWT+school+audit chain |
| notifications | `backend/internal/modules/notifications/service.go` | `Create` handles tenantDB nil, hub broadcast, FCM, audit |
| upload pattern | `backend/internal/modules/media/handler.go` | `c.FormFile("file")` |
| prometheus metrics | `backend/internal/ai/metrics.go`, `backend/internal/ws/metrics.go` | `promauto.NewCounterVec` (Phase 4 terminal-state counters if any) |
| core migration | `backend/internal/database/migrations/core/ai.go` | AutoMigrate pattern for shared-schema AI tables |
| SSE scanner | `backend/internal/ai/engine/sse.go` | 1MB cap, comment tolerance, blank-line events |
| config fail-fast | `backend/internal/config/config.go` | `AI.Enabled/EngineURL/EngineToken` unconditional validation |

## 6. Open risks / verification hooks

- **gin gzip**: confirm no global gzip middleware wraps `/api/v2/ai` — if present, must be bypassed for `text/event-stream` (check `setup.go` middleware stack).
- **asynq default task timeout**: verify `QueueConfig` in `worker.go`/`setup.go` — if no default, asynq defaults to 30s which would KILL long doc-ingest; must enqueue with `asynq.Timeout(6m)`.
- **`AI_UPLOADS_DIR` in compose**: absent today — add to backend + worker + ai-engine services so F2 containment + Go write path align.
- **`c.Stream` flush**: gin's ResponseWriter implements `http.Flusher`; verify `c.Writer.Flush()` used inside the loop (SSE requires manual flush).
- **Live smoke**: Phase 4 verification will run the full stack (backend + ai-engine via air/docker) and curl `POST /api/v2/ai/chat/stream` + upload a PDF through `POST /api/v2/ai/documents` → poll status → `POST /api/v2/ai/search` returns cited chunks (criterion 5). Requires Ollama or an AI_* key env for generation; embed via `AI_OPENAI_API_KEY` or local embedding (check Phase 3 env-gating — live embed test skipped without key; document-pipeline live test will need the key OR a fake).
