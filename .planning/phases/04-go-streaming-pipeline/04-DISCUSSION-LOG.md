# Phase 4 Discussion Log

Mode: auto
Date: 2026-08-01

## D-01: `ai_documents` status table placement

- Selected: **Shared/public schema** (core migration, like `ai_conversations`/`ai_messages`), with `school_id` column for scoping. Table `ai_documents`: `id` (PK, UUID string), `school_id` (indexed), `user_id`, `document_id` (Python's stable id), `original_name`, `storage_path` (relative to uploads root), `collection`, `content_type`, `size_bytes`, `status` (queued|extracting|chunking|embedding|ready|failed), `error_reason`, quality metrics (`pages`, `ocr_pages`, `chars`, `chunks`, `confidence`), `attempts`, `created_at`, `updated_at`, `completed_at`.
- Alternatives: (a) per-tenant schema `school_{id}.ai_documents` (ai_vectors precedent); (b) hybrid — status in shared, vectors per-tenant
- Rationale: The status row is **infrastructure/job-tracking data**, not per-tenant business data. The asynq worker runs OUTSIDE a request context — writing to a per-tenant schema from the worker requires schema resolution per task payload (doable but more plumbing and more failure surface). The `ai_conversations` precedent (core/ai.go: "infrastructure data, not per-tenant") already established shared-schema AI infrastructure with `school_id` scoping. The `GET /api/v2/ai/documents/:id/status` endpoint runs in a request context and scopes by the authenticated school via `GetSchoolIDFromCtx` — the shared table with `school_id` satisfies this with a simple `WHERE id=? AND school_id=?`. Per-tenant `ai_vectors` stays as-is (embedding payload is genuinely tenant business data). A shared status table also makes DLQ/SLO monitoring (criterion 4) a single query across schools.
- Consequence: `ai_documents` model lives in `backend/internal/database/models/` (shared), migration in `backend/internal/database/migrations/core/` as a NEW file (do not touch `core/ai.go` — it AutoMigrates only conversation models; add `core/ai_documents.go` or append a new AutoMigrate call). Worker uses the **core** DB (already injected) — no tenant DB needed for status writes; it still needs the tenant DB for nothing (Python writes vectors directly to the tenant schema itself via psycopg3).

## D-02: `document_id` idempotency contract (Python change)

- Selected: Extend Python `DocumentsRequestIn` with **optional `document_id: str | None = None`**. When provided, `ingest_document` uses it INSTEAD of `uuid.uuid4()`; when absent, current behavior (uuid4) stays. Go worker always passes the `ai_documents.id` (UUID string) as the stable document_id.
- Alternatives: (a) Go stores Python's returned uuid4 and reconciles after the call (breaks retry idempotency — a retry after partial write generates a NEW document_id → duplicate vectors); (b) deterministic hash of file content as document_id (changing file content on re-upload would orphan chunks; not per-upload unique)
- Rationale: ROADMAP criterion 4: "no duplicate vectors after worker restarts." The `UNIQUE(document_id, chunk_index)` + `ON CONFLICT DO NOTHING` idempotency (Phase 2/3) only works if the SAME document_id is used on retry. If Python keeps generating uuid4, a worker crash mid-ingest followed by retry produces a second uuid4 → all chunk rows inserted again → duplicates. Passing the ai_documents row id through makes retries hit `ON CONFLICT DO NOTHING` (inserted=0) — the exact Phase 2 behavior proven in Phase 3 verification. The `document_id` column in `ai_vectors` then links back to `ai_documents.id` for citation "source doc" lookup (criterion 5).
- This is a **small, additive Python change** (one optional field + passthrough + test). It does NOT violate "Phase 3 complete" — it's a Phase 4 contract extension required by PIP-01/04. Keep it in its own commit with a clear message.
- Consequence: `DocumentsRequestIn` gains `document_id`; `ingest_document(path, schema_name, collection, document_id=None)`; tests updated (default still generates; explicit respected).

## D-03: State machine granularity vs one-call Python

- Selected: **Coarse 5-state mapping with a single transition on the Python call**: `queued` (enqueue) → `extracting` (worker starts, before calling Python) → `chunking` (set after Python returns, before validating/recording) → `embedding` → `ready`/`failed`. In practice the worker records `extracting` at start, then `chunking`+`embedding` as a single set immediately before the final result, then `ready` or `failed` — the fine-grained extracting/chunking/embedding states are **logical milestones, not separately observed** because Python `/v1/documents` is one atomic HTTP call (by design, criterion 4).
- Alternatives: (a) Python SSE-progress callback (rejected — violates single-call criterion, adds a second transport); (b) only 3 states (queued/processing/ready|failed) (works but ROADMAP criterion 3 names the 5-state machine explicitly)
- Rationale: ROADMAP criterion 3 names the state machine `queued → extracting → chunking → embedding → ready/failed` — the enum must contain all five so the API contract matches. The worker sets `extracting` before the call and `chunking` immediately after (the call returned; chunk+embed already happened inside Python), then `embedding` → `ready` in the same write when quality metrics are recorded. A crash mid-pipeline leaves `extracting` — on retry the worker continues from `queued`/`extracting` (it doesn't gate on prior state; idempotency is the protection). Quality metrics (pages, ocr_pages, chars, chunks) come from Python's response and are stored on `ready`/`failed` (partial metrics even on failure, if Python returned them).
- Consequence: state enum constant + validation; worker transition helper; status endpoint returns the enum verbatim.

## D-04: `ai:doc-ingest` retry classification

- Selected: **Permanent errors → `asynq.SkipRetry` + mark status `failed` with clear reason.** Classification:
  - `400` (Python ValueError: bad file, unsupported type, no text, path outside uploads) → permanent → SkipRetry → failed "reason"
  - file-not-found / path-not-within-uploads / unmarshal payload error → permanent → SkipRetry → failed
  - `503` EmbeddingNotConfiguredError → **transient** (embedding config may be fixed) → retry with backoff
  - `502`/network error/timeout/connection refused → transient → retry with backoff
  - context deadline exceeded (asynq Timeout) → transient
  - After max retries exhausted → asynq archives to `asynq:{queue}:archived` (DLQ) — worker marks status `failed` (best-effort final write) and logs; archived task monitored as SLO (Phase 4: log + metric; Phase 6: full dashboard).
- Alternatives: (a) all errors transient (retry storms on permanently-bad files); (b) all errors permanent (no self-healing for 503/transient outages)
- Rationale: asynq best practice (Context7): `asynq.SkipRetry` signals "do not retry" — used for deterministic client errors (bad payload, validation failure). Transient (5xx/timeouts) should retry with the existing exponential `RetryDelayFunc`. This exactly matches ROADMAP criterion 4 "transient-vs-permanent retry classification (`asynq.SkipRetry` for permanent)". `IsFailure` in worker.go currently returns `true` for all errors — keep it (SkipRetry takes precedence at task level; IsFailure=false would suppress retry counting, which we do NOT want for transient pipeline errors).
- Consequence: new error sentinel(s) in the doc-ingest handler; handler returns `fmt.Errorf("...: %w", asynq.SkipRetry)` for permanent; status row updated before returning.

## D-05: SSE relay route placement + slow-client abort

- Selected: New method `StreamChat` on the existing `AIHandler` (in `modules/ai/handler.go` or a new `stream_handler.go` in the same package), route registered as `ai.POST("/chat/stream", aiHandler.StreamChat)`. Pattern:
  1. Bind `engine.ChatRequest` (model, messages) — reuse existing DTO.
  2. Create a **bounded buffered channel cap 64** of `engine.EngineEvent` plus a `done` channel.
  3. Goroutine A: call `engineClient.ChatStream(ctx, req, cb)` where `ctx = c.Request.Context()` (propagates client disconnect) and `cb` pushes events into the channel, dropping/blocking with a select that also watches ctx; on error pushes an in-band `error` event, always pushes final `done`.
  4. Main: `c.Stream` writes each event as `data: {json}\n\n` via `c.Writer.Write` + `c.Writer.Flush()`; set headers `Content-Type: text/event-stream`, `X-Accel-Buffering: no`, `Cache-Control: no-cache`, no compression (gin disables gzip for SSE by checking content-type; verify).
  5. **Slow-client abort**: if the writer can't flush within a grace period (channel full + select timeout) OR `c.Request.Context()` is done, cancel the upstream call (goroutine A sees ctx cancel → ChatStream returns → Python stops → no billed unread tokens). Heartbeats: rely on Python's `: ping` ≤25s (F4) — relay comment lines verbatim; also emit a Go-side `: ping` if upstream is silent >30s (defense in depth).
- Alternatives: (a) standalone `modules/ai-stream/` module (overkill — same authGroup, same package); (b) wrap Python stream bytes raw (breaks the event-envelope contract + blocks in-band error injection)
- Rationale: ROADMAP criteria 1+2. `AIHandler` already holds the injected deps (add `engineClient` field + `WithEngineClient` setter, mirroring `WithSearchEngine`). Reusing `engine.ChatStream` (existing SSE scanner, 1MB buffer >64KB default — criterion 2 "SSE-aware scanner with buffer beyond the 64 KB default" already satisfied by `sse.go`) keeps transport logic in the seam. Bounded channel cap 64 prevents unbounded buffering; select-on-full with ctx watch provides the slow-client abort. `r.Context()` propagation satisfies criterion 2.
- Consequence: `modules/ai/` gains a stream route + tests (httptest with a fake engine server emitting the envelope).

## D-06: Upload validation & storage scheme

- Selected: Extend `modules/ai/` (new `document_handler.go` + `document_service.go` + `document_repository.go` following the module layout convention). `POST /api/v2/ai/documents`:
  - `c.FormFile("file")` (multipart, same as media module).
  - Validate: extension allowlist (`.pdf`, `.docx`, `.pptx`, `.txt`, `.csv`, `.png`, `.jpg`, `.jpeg`), content-type match, **size cap** (config `AI_MAX_DOC_MB`, default 50 MB — mirrored in Python's gates).
  - Save to shared uploads volume: path scheme `/app/uploads/{school_id}/{uuid}.{ext}` — the storage base dir is `AI_UPLOADS_DIR` config in Go (add `AI.UploadsDir` reading `AI_UPLOADS_DIR`, default `/app/uploads`); `uuid` = `ai_documents.id` generated BEFORE save.
  - Create `ai_documents` row (status `queued`, user_id from ctx, school_id from ctx, storage_path relative).
  - Enqueue `ai:doc-ingest` with payload `{school_id, document_id (ai_documents.id), collection (default "default"), storage_path (absolute), document_type}`.
  - Return `202` with `{id, status: "queued"}`.
  - Storage write errors → 500; validation errors → 400 with clear message (Rule B9: state mutation → return error).
- Alternatives: (a) reuse `storage.Driver` (media module) — its local.go base path is a Go-side dir, not necessarily the shared uploads volume; the ai-engine reads from the SAME volume by absolute path, so writing to `/app/uploads/...` directly (respecting `AI_UPLOADS_DIR`) is simpler and keeps Python's `_assert_within_uploads` working; (b) async save via worker (adds latency + failure window before 202).
- Rationale: ROADMAP criterion 3. `uploads_data` is already a shared named volume mounted at `/app/uploads` on api, worker, and ai-engine (verified in compose). Python's `_assert_within_uploads` (F2 review fix) requires the path to live under `AI_UPLOADS_DIR` — Go must write there with the SAME env so containment passes. School-scoped subdir prevents cross-tenant filename collisions. Save-before-enqueue means the worker never sees a missing file (idempotency holds).
- Consequence: Go `AI.UploadsDir` config + validation helper + `document_repository` for `ai_documents` rows; compose already mounts the volume — set `AI_UPLOADS_DIR=/app/uploads` for backend+worker services in compose (and `AI_UPLOADS_DIR=/app/uploads` for ai-engine — currently absent!).

## D-07: EngineClient wiring + `IngestDocument` method

- Selected: Add `IngestDocument(ctx, req IngestDocumentRequest) (*IngestDocumentResponse, error)` to the `EngineClient` interface and implement it in `client.go` as POST `/v1/documents` (JSON body `{document_path, collection, document_id}`, headers `X-AI-Engine-Token` + `X-School-Schema` + `X-Request-ID`). New Go types in `engine.go`: `IngestDocumentRequest{DocumentPath, Collection, DocumentID}` and `IngestDocumentResponse{Status, DocumentID, Chunks, Pages, OcrPages, Chars, Warnings}`. Budget: `extractTimeout` (5m).
- Alternatives: (a) use generic POST helper (loses type safety); (b) leave the interface frozen and have the worker call Python via raw HTTP (violates the seam — future gRPC swap would break)
- Rationale: ROADMAP criterion 4 (worker calls `/v1/documents` exactly once). The seam exists precisely so callers never see transport. Python returns the full quality-metrics payload — Go must model it for status (D-03). Instantiate `engine.NewClient(cfg.AI.EngineURL, cfg.AI.EngineToken)` in `setup.go` when `cfg.AI.Enabled` (already required config), inject into `AIHandler` (stream + document routes) and into the asynq doc-ingest handler (via the `TaskHandlers` wiring). This is the FIRST real instantiation of the seam.
- Consequence: `engine.go` + `client.go` + `client_test.go` additions; setup.go wiring.

## D-08: Notification payload on pipeline events

- Selected: On `ready`: notify the **uploader** (user_id from `ai_documents.user_id`) via `NotificationService.Create` with type `"ai_document_ready"`, message including doc name + chunk count; then `hub.Broadcast(ws.UserRoom(schoolID, userID), msg)` (WebSocket live update) — the notifications service already does both (DB + FCM + hub). On `failed`: notify uploader with `"ai_document_failed"` + reason. Best-effort — notification failures must NOT fail the pipeline (Rule B9: notifications are secondary; log + continue).
- Alternatives: (a) notify all admins/teachers of the school (noisy; no recipient list plumbing); (b) skip WebSocket, DB-only (loses real-time UI update)
- Rationale: PIP-01 ends with "event → notify"; criterion 5 says "the user sees a clear reason" — a DB notification + live ws event is the existing platform pattern (notifications/service.go). The worker runs outside request context, so it must call `NotificationService.Create` with an explicit tenantDB=nil (core DB path) or a resolved tenant DB — notifications.Create already handles `tenantDB==nil` → uses repo core DB (verified). The worker needs `school_id` + `user_id` from the payload/status row (both stored in `ai_documents`).
- Consequence: worker injects a `notifier` (interface with `NotifyDocReady/NotifyDocFailed`), backed by `NotificationService` + `hub`; best-effort with `logger.Warnf` on failure.

## D-09: DLQ / archive monitoring in Phase 4

- Selected: Phase 4 ships **logging + a Prometheus-style counter** (or the existing metrics hook if present) for `ai_documents` terminal states and asynq archived queue depth; a periodic (e.g. hourly or on-startup) scan of `asynq:{queue}:archived` is NOT added in Phase 4 (Phase 6 owns full Grafana dashboards + SLO alerts per OBS-01). Worker logs archived transitions with task id + school_id + reason so ops can inspect. The status row `failed` (after max retries) is the user-facing DLQ signal; the asynq archive is the internal one.
- Alternatives: (a) add asynqmon container (new infra — violates no-new-infra); (b) build full DLQ alerting now (Phase 6 scope creep)
- Rationale: ROADMAP criterion 4 "DLQ/archive monitored as an SLO" — minimal viable monitoring in Phase 4 = logs + metrics counter + status rows; dashboards/alerts are Phase 6 (OBS-01). Keeps this phase focused on the pipeline correctness that makes the DLQ empty in practice (idempotency + SkipRetry classification).
- Consequence: worker records terminal-state metrics via the app's metrics/monitoring hook if one exists (verify); otherwise `logger.Warnf`/`logger.Infof` per terminal transition.

## D-10: Testing strategy

- Selected: Go — unit tests for: SSE relay (fake engine server emitting envelope incl. in-band error after 200, slow-client abort via tiny client buffer + ctx cancel), document service (validation matrix: bad ext, oversize, missing file), repository CRUD + state machine transitions, worker handler (fake EngineClient: success/permanent/transient/network error → SkipRetry assertions, notification calls). Integration (env-gated): real Python running? No — Phase 4 integration uses **httptest fake engine** for Go tests + a live smoke script `backend/scripts/test_endpoint.sh`-style for the full stack (needs running engine). Python change (document_id passthrough) covered by existing pytest suite + new test. All new Go tests must pass `go test ./...`; lint via `golangci-lint` (repo's existing config); Python via `ruff` + `pyright`.
- Alternatives: (a) docker-compose integration tests for the whole pipeline (slow, env-heavy); (b) no worker-level tests (risky — classification logic is the critical path)
- Rationale: Matches Phase 2/3 discipline (fast unit tests + env-gated integration). The four failure modes (criterion 2) are each unit-testable against a fake engine. Worker retry classification (criterion 4) is pure logic with a fake client. Real end-to-end verified via the smoke script during verification (like Phase 3's live Ollama + DB checks).
- Consequence: new test files: `modules/ai/stream_handler_test.go`, `modules/ai/document_handler_test.go`, `queue/doc_ingest_test.go`, `ai/engine/client_ingest_test.go` (+ Python `test_extract.py` update).

---

## Decisions that MUST reach the planner

| ID | Decision |
|----|----------|
| D-01 | `ai_documents` status table in SHARED/public schema (core migration, school_id scoped) — not per-tenant |
| D-02 | Python `DocumentsRequestIn` gains optional `document_id`; Go passes `ai_documents.id` for retry idempotency |
| D-03 | 5-state enum (queued→extracting→chunking→embedding→ready/failed); coarse transition on one Python call; store quality metrics |
| D-04 | `asynq.SkipRetry` for permanent (400/file/validation); transient (503/502/network/timeout) retry with backoff; final failure → status failed + archive log |
| D-05 | SSE relay = `AIHandler.StreamChat` + bounded channel cap 64 + select-full abort + `r.Context()` upstream cancel + Go-side `: ping` fallback; headers `X-Accel-Buffering: no` |
| D-06 | Upload: `c.FormFile("file")`, ext/content-type allowlist, size cap `AI_MAX_DOC_MB` (50), save to `/app/uploads/{school_id}/{id}.{ext}`, row queued, enqueue, 202 |
| D-07 | `IngestDocument` added to EngineClient + client.go POST `/v1/documents` (headers X-School-Schema + X-Request-ID); wire `engine.NewClient` in setup.go |
| D-08 | Notify uploader on ready/failed via NotificationService.Create + ws.UserRoom broadcast; best-effort |
| D-09 | DLQ monitoring = logs + terminal-state metrics in Phase 4; dashboards/alerts deferred to Phase 6 |
| D-10 | Go unit tests w/ httptest fake engine (4 failure modes, classification, state machine); env-gated integration; Python test for document_id passthrough |
