---
phase: 04-go-streaming-pipeline
verified: 2026-08-01T15:33:29Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification:
  - test: "Live SSE streaming: POST /api/v2/ai/chat/stream against the running ai-engine + Ollama, consuming via EventSource"
    expected: "Deltas render token-by-token; heartbeat `: ping` comments every ≤30s; an engine error after HTTP 200 surfaces as an in-band `error` event; closing the tab stops generation"
    why_human: "Real-time streamed behavior and browser EventSource consumption cannot be verified by static/grep checks"
  - test: "End-to-end document pipeline: upload a PDF via POST /api/v2/ai/documents, poll GET /api/v2/ai/documents/:id/status to `ready`, then run a school-scoped search and confirm citations (document_id#chunk_index)"
    expected: "202 with job id → status walks queued → extracting → ready; search returns chunks with source-doc citations; a re-uploaded/retried document produces no duplicate vectors"
    why_human: "Requires the full running stack (Postgres + Redis + Go server + Python engine); only a smoke script can exercise the live path"
---

# Phase 4: SSE Streaming + Document Pipeline Verification Report

**Phase Goal:** Users can stream AI chat responses token-by-token and upload documents that become searchable, cited knowledge — the Core Value — through a safe, idempotent, failure-transparent pipeline.
**Verified:** 2026-08-01T15:33:29Z
**Status:** PASSED-WITH-NOTES (all 5 ROADMAP success criteria and all plan must-haves verified; minor spec-detail deviations documented below, none contradicting ROADMAP promises)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /api/v2/ai/chat/stream` streams the shared event envelope (delta/citation/usage/error/done) with `X-Accel-Buffering: no`, heartbeats ≤30s, no compression; client disconnect cancels the upstream Python call (SC1) | ✓ VERIFIED | `stream.go:81` sets `X-Accel-Buffering: no`; `heartbeatEvery = 25 * time.Second` (stream.go:29, ≤30s); heartbeat written as `": ping\n\n"` comment frame (stream.go:137); relay uses `r.Context()` (c.Request.Context()) → `aiClient.ChatStream(ctx, …)`, so disconnect cancels upstream and stops token billing; no gzip middleware registered on the route (checked router middleware chain — only Recovery/RequestID/Tracing/ErrorHandler/Logger at router.go:98-103) |
| 2 | SSE relay survives all four failure modes: SSE-aware scanner beyond 64 KB default, `r.Context()` propagation, bounded channel (cap 64) with slow-client abort, in-band `error` events after HTTP 200 (SC2) | ✓ VERIFIED | `sse.go:16-17`: `bufio.NewScanner` + `scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)` (1 MB cap, beyond 64 KB default); `relayBufferSize = 64` with bounded channel (stream.go:28,87); full-buffer abort: `select { case ch <- evt: default: cancelUpstream() }`; in-band error passthrough + synthesized terminal `done` on close; covered by `stream_test.go` (6 tests: envelope passthrough, buffer-full abort, context cancel, in-band errors, drainer error, heartbeat) |
| 3 | `POST /api/v2/ai/documents` accepts PDF/DOCX/PPTX/TXT/CSV/images, validates type/size/permissions, saves to shared uploads volume, enqueues asynq `ai:doc-ingest`, returns 202; `GET /api/v2/ai/documents/:id/status` reports the 5-state machine + quality metrics (SC3) | ✓ VERIFIED | `service.go`: `allowedExts` allowlist + `maxUploadBytes(config.MaxDocMB)` + sniff normalization; `handler.go`: `UploadDocument` returns 202 + job id, `GetDocumentStatus` returns enum + Pages/OcrPages/Chars/Chunks + ErrorReason; `router.go:277-282` registers both under `authGroup` (JWTAuth → EnforceSchoolID → TenantResolution → TenantDBResolver → AuditLogging); shared volume `uploads_data:/app/uploads` mounted on both api (compose:81) and ai-engine (compose:112) |
| 4 | Worker calls Python `/v1/documents` exactly ONCE per file; idempotent (unique constraint + `ON CONFLICT DO NOTHING`); transient-vs-permanent retry classification (`asynq.SkipRetry` for permanent); DLQ/archive monitored as SLO (SC4) | ✓ VERIFIED | `doc_ingest_handler.go`: single `h.aiClient.IngestDocument(...)` call (exactly-once); `StatusError` 4xx → `markFailed` + `SkipRetry`; transient → error return so asynq retries; WR-02 guard persists `failed` on retry exhaustion; idempotency: `ai_vectors` unique constraint `uq_ai_vectors_doc_chunk` + Python `ON CONFLICT (document_id, chunk_index) DO NOTHING`; metrics counters QueueEnqueuedTotal/QueueProcessedTotal/QueueFailedTotal/QueueRetriedTotal in `metrics.go` |
| 5 | On `ready`, school-corpus search returns chunks with citations (source doc + page); on failure user sees a clear reason and can retry; no silent drops, no duplicate vectors after restarts (SC5) | ✓ VERIFIED | Python `/v1/search` returns `document_id#chunk_index` citations (`ai-engine/app/rag/rerank.py` rank_and_cite) + compressed context; status endpoint returns `ErrorReason` verbatim (clear failure reason); retry = re-upload/re-enqueue; idempotent retry proven by Python `test_documents.py` (idempotent-retry case) and Go handler tests (exactly-one-call, nil-response, exhaustion) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `backend/internal/ai/engine/engine.go` | IngestDocumentRequest/Response + StatusError | ✓ VERIFIED | `IngestDocumentRequest{DocumentPath, Collection, DocumentID, SchoolSchema}`, `IngestDocumentResponse{Status, DocumentID, Chunks, Pages, OcrPages, Chars, Warnings}`, typed `StatusError` |
| `backend/internal/ai/engine/client.go` | `IngestDocument` POST /v1/documents, X-School-Schema, 5m extractTimeout | ✓ VERIFIED | Headers X-School-Schema + X-Request-ID; `extractTimeout = 5m`; `X-AI-Engine-Token` |
| `backend/internal/ai/engine/sse.go` | SSE-aware scanner beyond 64 KB default | ✓ VERIFIED | 64 KB initial / 1 MB max buffer (sse.go:17) |
| `backend/internal/ai/engine/client_ingest_test.go` | I1/I2 test coverage | ✓ VERIFIED | StatusError surfacing + exactly-once + header assertions |
| `backend/internal/database/models/ai_document.go` | AIDocument, 5-state enum, quality columns | ✓ VERIFIED | 6 consts (queued/extracting/chunking/embedding/ready/failed); Pages/OcrPages/Chars/Chunks; uuid PK with `gen_random_uuid()` |
| `backend/internal/database/migrations/core/ai_documents.go` | Core (shared schema) migration | ✓ VERIFIED | `2026_07_27_000100_create_ai_documents`, `AutoMigrate(&models.AIDocument{})`; registered at `core.go:28` |
| `backend/internal/queue/tasks.go` | TypeDocIngest + DocIngestPayload + TaskHandlers.DocIngest | ✓ VERIFIED | `TypeDocIngest = "ai:doc-ingest"`, `DocIngestPayload{JobID}` |
| `backend/internal/queue/handlers/doc_ingest_handler.go` | Worker: retry classification, terminal metrics, notifications | ✓ VERIFIED | 4xx permanent → failed+SkipRetry; transient → retry; retry-exhaustion guard; D-09 metrics; D-08 best-effort notify (tenant-scoped via WR-03 fix) |
| `backend/internal/queue/handlers/doc_ingest_handler_test.go` | Worker test suite | ✓ VERIFIED | 12 tests: malformed payload, permanent, transient, exhaustion→failed+archived, nil-response, success, exactly-once |
| `backend/internal/modules/ai/{dto,handler,service,repository}.go` | Upload/status endpoints + validation + repo | ✓ VERIFIED | allowlist/size/sniff validation; `GetByIDAndSchoolID` school-scoped; 202 + status |
| `backend/internal/modules/ai/stream.go` | SSE relay: bounded channel, heartbeat, X-Accel-Buffering, in-band errors | ✓ VERIFIED | cap 64, heartbeat 25s, header, done dedup, POST route (WR-04) |
| `backend/internal/modules/ai/stream_test.go` | Relay unit tests | ✓ VERIFIED | 6 tests passing |
| `backend/internal/router/router.go` | Routes registered in authGroup | ✓ VERIFIED | `ai.POST("/chat/stream")` (:282), `ai.POST("/documents")` + `ai.GET("/documents/:id/status")` (:277-282) |
| `backend/internal/router/setup.go` | Single shared engine client + one mux registration | ✓ VERIFIED | `engine.NewClient` once (setup.go:294); `queueWorker.Mux().HandleFunc(TypeDocIngest, …)` once (setup.go:604, CR-01) |
| `backend/internal/config/config.go` | AI_UPLOADS_DIR + AI_MAX_DOC_MB + startup validation | ✓ VERIFIED | Required absolute path + cap ≤200, fail-fast (Rule B12); default 50 |
| `backend/docker-compose.yml` | Shared uploads volume on api + ai-engine | ✓ VERIFIED | `uploads_data:/app/uploads` on both services; `AI_UPLOADS_DIR=/app/uploads` + `AI_MAX_DOC_MB` on both (lines 67-112) |
| `ai-engine/app/api/extract.py` | document_id passthrough + containment | ✓ VERIFIED | `document_id: str | None = None`; `_assert_within_uploads` |
| `ai-engine/app/documents/pipeline.py` | Caller document_id honored | ✓ VERIFIED | Uses caller id else uuid4; `ON CONFLICT (document_id, chunk_index) DO NOTHING` |
| `ai-engine/app/db/vectors.py` | Unique constraint + DO NOTHING | ✓ VERIFIED | `uq_ai_vectors_doc_chunk UNIQUE (document_id, chunk_index)` + upsert |
| `ai-engine/tests/test_documents.py` | Python document_id tests | ✓ VERIFIED | 9 passed, 4 skipped (DB-gated), 7.39s: idempotent retry, no-text echo, default uuid4, token/schema gates |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | -- | ------ | ------- |
| `stream.go StreamChat` | `engine.EngineClient.ChatStream` | `aiClient.ChatStream(r.Context(), …)` | WIRED | Context propagated from request; relay callback in `stream.go` |
| `stream.go` heartbeat | browser SSE stream | `": ping\n\n"` comment frame | WIRED | stream.go:137, ≤30s (25s) |
| `stream.go` bounded channel | slow-client guard | `select { case ch <- evt: default: cancelUpstream() }` | WIRED | cap 64, full buffer aborts upstream |
| `doc_ingest_handler.go` | `engine.IngestDocument` | single call with `DocumentID: doc.ID` + `SchoolSchema: "school_{id}"` | WIRED | exactly-once; schema header derived from row's SchoolID |
| `service.go UploadDocument` | asynq queue | `q.Enqueue(NewDocIngestTask(jobID), Timeout(6m), MaxRetry(5))` | WIRED | job carries ai_documents.id |
| Go worker `doc.ID` | Python `/v1/documents` document_id | HTTP JSON body `document_id` | WIRED | D-02; Python upserts with caller id |
| Python `ON CONFLICT DO NOTHING` | `ai_vectors` unique constraint | `uq_ai_vectors_doc_chunk` | WIRED | idempotent retry, no duplicates |
| `AIHandler.UploadDocument` | `aiDocumentRepo.Create` → `GetByIDAndSchoolID` | `WHERE id = ? AND school_id = ?` | WIRED | school-scoped status reads |
| `authGroup` | AI routes | JWTAuth → EnforceSchoolID → TenantResolution → TenantDBResolver → AuditLogging | WIRED | router.go:73-85; all AI routes inside |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `UploadDocument` (202 + job id) | `doc` | `aiDocumentRepo.Create` after validation; path `{AI_UPLOADS_DIR}/{school_id}/{id}.{ext}` | Yes — real file on shared volume | ✓ FLOWING |
| `GetDocumentStatus` | `doc.Status/Pages/…` | `GetByIDAndSchoolID` → GORM query (school-scoped) | Yes — DB row | ✓ FLOWING |
| `HandleDocIngest` | `doc` | `loadDoc` (core DB by id) → engine resp → `saveDoc` | Yes — real DB read/write | ✓ FLOWING |
| `StreamChat` | `engine.EngineEvent` | `aiClient.ChatStream` SSE → relay → `c.Writer` | Yes — live engine stream | ✓ FLOWING |
| `search` citations | `document_id#chunk_index` | `ai-engine/app/rag/rerank.py` | Yes — real vector rows | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Backend compiles | `go build ./...` (backend) | exit 0 | ✓ PASS |
| Vet clean | `go vet` on changed packages | exit 0 | ✓ PASS |
| AI module tests | `go test -count=1 ./internal/modules/ai/...` | 7 tests pass | ✓ PASS |
| Queue + handler tests | `go test -count=1 ./internal/queue/... ./internal/queue/handlers/...` | 4 + 12+ tests pass (incl. DocIngest) | ✓ PASS |
| Config tests | `go test -count=1 ./internal/config/...` | pass | ✓ PASS |
| Engine seam tests | `go test -count=1 ./internal/ai/engine/...` | pass | ✓ PASS |
| Python document tests | `uv run pytest tests/test_documents.py -q` (ai-engine) | 9 passed, 4 skipped (DB-gated), 7.39s | ✓ PASS |
| Migration registration | `grep` core.go:28 | `AIDocumentsMigrations()` appended | ✓ PASS |
| Single engine client | `grep` setup.go | `engine.NewClient` appears once (setup.go:294) | ✓ PASS |
| Single mux registration | `git show e6f9671` (CR-01) | `HandleFunc(TypeDocIngest, …)` once (setup.go:604) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| PIP-01 | 04-01/02/03/04 | Document pipeline: upload → validate → save → enqueue → worker → single Python call → extract/chunk/embed → pgvector → event → notify | ✓ SATISFIED | Full chain verified: service.go → asynq → doc_ingest_handler.go (single IngestDocument) → Python pipeline → `ai_vectors` upsert → D-08 notifications + D-09 metrics |
| PIP-02 | 04-04 | `POST /api/v2/ai/documents` + `GET /api/v2/ai/documents/:id/status` | ✓ SATISFIED | router.go:277-282 inside authGroup; handler.go UploadDocument + GetDocumentStatus |
| INT-01 | 04-05 | `POST /api/v2/ai/chat/stream` SSE route, failure-mode-safe relay (scanner buffer, context, bounded channel, in-band errors, X-Accel-Buffering, heartbeats, shared envelope) | ✓ SATISFIED | stream.go + sse.go + stream_test.go; POST route per WR-04 |
| INT-02/03/04 (Phase 5) | — | Multi-provider status, orchestrator, provider routing | — | Explicitly Phase 5 scope — not in this phase's plan requirements |

> Note: `.planning/REQUIREMENTS.md` lines 37-38, 42 still show PIP-01/PIP-02/INT-01 unchecked. Per the verification task constraints, REQUIREMENTS.md was NOT modified; the checkboxes are a state-tracking artifact, and the implementation evidence above satisfies each requirement.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `backend/internal/queue/tasks.go` | 115 | Stale doc comment (references outdated payload shape) | ℹ️ Info | None — comment-only |
| `models/ai_document.go` | — | `collection` + `completed_at` columns absent vs D-01 column spec | ⚠️ Warning | Non-blocking deviation; worker hardcodes `Collection: "default"` and never stores it; `CompletedAt` has no consumer in Phase 4 (status endpoint returns enum + metrics only). No ROADMAP criterion requires these columns. |
| `service.go` allowedExts | — | `.gif` in allowlist beyond D-06's listed png/jpg | ⚠️ Warning | Additive and safe — D-06 listed a subset; ROADMAP SC3 says "PDF/DOCX/PPTX/TXT/CSV/images", and GIF is an image. Acceptable deviation. |

No FIXME/TODO/XXX/HACK/placeholder patterns found in changed files. No hardcoded empty data or empty handlers.

### Decisions Verified (D-01..D-10)

| Decision | Verified? | Evidence |
| -------- | ---------- | -------- |
| D-01 shared/public schema for ai_documents | ✓ | core migration (`migrations/core/ai_documents.go`), model comment, handler uses core DB |
| D-02 document_id passthrough for idempotency | ✓ | Go passes `doc.ID`; Python honors optional id; `ON CONFLICT DO NOTHING`; unique constraint; root commit `55e99af` |
| D-03 5-state enum + coarse transition + quality metrics | ✓ (note) | All 6 consts; worker transitions extracting → ready/failed (chunking/embedding are logical milestones, never separately persisted — matches D-03's "logical milestones, not separately observed" consequence); metrics stored on ready/failed |
| D-04 retry classification | ✓ | 4xx permanent → SkipRetry + failed row; transient → backoff; WR-02 exhaustion guard |
| D-05 SSE relay design | ✓ | cap 64, heartbeat 25s, `: ping`, context propagation, in-band errors; WR-04 made route POST |
| D-06 upload validation/storage | ✓ (note) | allowlist + size cap + shared volume `uploads_data`; `.gif` additive (see notes) |
| D-07 EngineClient single instance | ✓ | setup.go:294 once; injected into AIHandler + doc-ingest handler |
| D-08 notification payload | ✓ | best-effort `notify()` on ready/failed; WR-03 fix: tenant-scoped DB (notifications live in tenant schema) |
| D-09 DLQ/archive monitoring | ✓ | Queue*Total metric counters + per-transition logging |
| D-10 testing strategy | ✓ | Go unit tests (fake engine/httptest) + env-gated asynq/Redis tests + Python pytest; no new infra |

### Human Verification Required

1. **Live SSE streaming** — `POST /api/v2/ai/chat/stream` against the running ai-engine + Ollama, consumed via EventSource: deltas render token-by-token; heartbeat comment frames every ≤30s; an engine error after HTTP 200 arrives as an in-band `error` event; closing the browser tab stops upstream generation (no tokens billed for unread output).
   - Why human: real-time streaming behavior and browser EventSource semantics can't be proven by static analysis.

2. **End-to-end document pipeline smoke** — upload a real PDF via `POST /api/v2/ai/documents`, poll `GET /api/v2/ai/documents/:id/status` to `ready`, then run a school-scoped search and confirm `document_id#chunk_index` citations; verify a retried upload produces no duplicate vectors.
   - Why human: requires the full running stack (Postgres + Redis + Go server + Python engine + shared volume); D-10 deferred a live smoke script to verification-time execution.

### Gaps Summary

**No blocking gaps.** All 5 ROADMAP success criteria and all plan must-haves are satisfied by the code, with passing builds, vet, Go test suites, and Python pytest. Two minor, non-blocking spec deviations are documented (not gaps_found material):

1. `ai_documents` omits `collection`/`completed_at` columns from D-01's column sketch — the worker hardcodes `Collection: "default"` and nothing consumes `completed_at` in this phase. If a future phase needs per-document collection tracking or completion timestamps, a follow-up migration adds them.
2. Upload allowlist includes `.gif` in addition to D-06's listed set — additive and consistent with ROADMAP SC3's "images".

Neither contradicts any ROADMAP promise; both are deliberate simplifications consistent with the phase's stated scope.

## Verdict: PASSED-WITH-NOTES

The phase goal — streamed chat + idempotent, failure-transparent document pipeline — is achieved. All 5 ROADMAP success criteria verified in code; all 5 plans' must-haves verified; all test suites green; both gaps are informational deviations, not goal-blockers. Awaiting the two live-stack human verifications above before declaring the phase fully shippable.

---

_Verified: 2026-08-01T15:33:29Z_
_Verifier: the agent (gsd-verifier)_
