# Task Context: Phase 4 — SSE Streaming + Document Pipeline

Phase: 04-go-streaming-pipeline
Status: planning
Created: 2026-08-01 (after Phase 3 verified 5/5)

## Goal

Users can stream AI chat responses token-by-token and upload documents that
become searchable, cited knowledge — the Core Value — through a safe,
idempotent, failure-transparent pipeline. Phase 3 built the stateless Python
engine (`/v1/chat/stream`, `/v1/documents`, `/v1/search`); Phase 4 integrates
it into Go: an SSE relay route, an async document-ingestion pipeline with a
status state machine, and completion notifications.

## Requirements (from REQUIREMENTS.md)

- **INT-01**: `POST /api/v2/ai/chat/stream` SSE route with failure-mode-safe relay (SSE-aware scanner, context propagation, bounded channel, in-band errors, `X-Accel-Buffering: no`, heartbeats, shared event envelope)
- **PIP-01**: Document pipeline: upload → Go validates → save → asynq enqueue (`ai:doc-ingest`) → Go worker → single Python `/v1/documents` call → extract/chunk/embed → pgvector → event → notify
- **PIP-02**: `POST /api/v2/ai/documents` + `GET /api/v2/ai/documents/:id/status` endpoints

## ROADMAP Success Criteria (what must be TRUE)

1. `POST /api/v2/ai/chat/stream` streams the shared event envelope (delta/citation/usage/error/done) to the browser with `X-Accel-Buffering: no`, heartbeats ≤30s, and no compression on `text/event-stream`; a client disconnect cancels the upstream Python call so generation stops and no tokens are billed for unread output.
2. The SSE relay survives all four failure modes: event-boundary-safe parsing (SSE-aware scanner with buffer beyond the 64 KB default), `r.Context()` propagation into the upstream call, bounded channel (cap 64) with slow-client abort, and in-band `error` events after HTTP 200 that every client checks.
3. `POST /api/v2/ai/documents` accepts PDF/DOCX/PPTX/TXT/CSV/images, validates type/size/permissions, saves to the shared uploads volume, enqueues asynq `ai:doc-ingest`, and returns 202; `GET /api/v2/ai/documents/:id/status` reports the state machine (queued → extracting → chunking → embedding → ready/failed) plus quality metrics (pages, OCR'd pages, char count, confidence).
4. The Go worker calls Python's `/v1/documents` exactly ONCE per file (single call: extract+chunk+embed+store); ingest is idempotent — unique constraint + `INSERT ... ON CONFLICT DO NOTHING`, transient-vs-permanent retry classification (`asynq.SkipRetry` for permanent), DLQ/archive monitored as an SLO.
5. When a document reaches `ready`, searching that school's corpus returns its chunks with citations (source doc + page); on failure the user sees a clear reason and can retry — no silent drops, no duplicate vectors after worker restarts.

## Existing State (verified this session)

### Python engine (Phase 3, complete — do NOT rewrite)
- `ai-engine/app/main.py`: FastAPI app; routes `/health`, `/v1/health`, `/v1/chat`, `/v1/chat/stream`, `/v1/embed`, `/v1/extract`, `/v1/documents`, `/v1/providers`, `/v1/search`
- `ai-engine/app/api/chat.py`: `POST /chat` + `POST /chat/stream` (SSE, `: ping` heartbeats, no gzip); `_resolve_messages` handles prompt_type; `_sanitize_error_message`
- `ai-engine/app/api/extract.py`: `POST /extract` + `POST /documents`; `_school_header(x_school_schema)` validates `^school_\d+$`; `_assert_within_uploads(req.document_path)` — 400 if path outside AI_UPLOADS_DIR; `DocumentsRequestIn` = `{document_path, collection}`; returns `{status, document_id, chunks, pages, ocr_pages, chars, warnings}`; 400 ValueError, 503 EmbeddingNotConfiguredError, 502 unexpected
- `ai-engine/app/documents/pipeline.py`: `ingest_document(path, schema_name, collection="default")` — extract → chunk → embed → store in ONE call; **`document_id = str(uuid.uuid4())` generated INTERNALLY** (gap for retry idempotency — see D-04)
- `ai-engine/app/db/vectors.py`: `insert_chunks(...)` with `ON CONFLICT (document_id, chunk_index) DO NOTHING` — returns inserted count
- `ai-engine/app/config.py`: 27 fields incl. `AI_UPLOADS_DIR` (empty = containment disabled for local dev), `AI_HEARTBEAT_INTERVAL_SECONDS=25.0`
- `ai-engine/app/security.py`: `require_token` (X-AI-Engine-Token)

### Go EngineClient seam (Phase 1/3, FROZEN in Phase 3 — Phase 4 EXTENDS deliberately)
- `backend/internal/ai/engine/engine.go`: `EngineClient` interface — `Chat`, `ChatStream(ctx, req, cb StreamCallback)`, `Extract`, `Health`; `EngineEvent{Type string, Data json.RawMessage}` (delta | citation | usage | error | done); `ChatRequest{Model, Messages, Stream}`; `ExtractRequest{DocumentPath}`; `ExtractResponse{Status}`; headers `EngineTokenHeader = "X-AI-Engine-Token"`, `RequestIDHeader = "X-Request-ID"`
- **GAP**: no `IngestDocument` method yet; Python `/v1/documents` response shape (document_id/chunks/pages/ocr_pages/chars/warnings) not modeled in Go
- `backend/internal/ai/engine/sse.go`: `scanSSEEvents`, `splitSSEEvent` (blank-line split), `parseSSEBlock`, comment tolerance, ctx cancellation, **buffer 1MB cap over 64KB default**
- `backend/internal/ai/engine/client.go`: `httpClient` — chatTimeout 30s, extractTimeout 5m, healthTimeout 10s; **ChatStream NO timeout (context-bound by design FND-03)**
- `backend/internal/ai/engine/client_test.go`, `sse_test.go` (httptest)
- `engine.NewClient` is defined but **NEVER instantiated anywhere** — Phase 4 wires it in setup.go

### Backend wiring / infrastructure
- `backend/internal/config/config.go`: `AI.Enabled`, `AI.EngineURL`, `AI.EngineToken` — unconditional fail-fast validation (`AI_ENGINE_URL must be set (Go↔Python engine seam)`, `AI_ENGINE_TOKEN must be set (service-to-service auth)`); also `AI_EMBEDDING_DIM` bounded
- `backend/docker-compose.yml`: `uploads_data` named volume mounted to `/app/uploads` on api, worker, and ai-engine services (shared); **`AI_UPLOADS_DIR` NOT set in compose** (Phase 4 must add `AI_UPLOADS_DIR=/app/uploads` so F2 containment works in deployed env)
- asynq v0.26.0 (`github.com/hibiken/asynq`)
- `backend/internal/queue/tasks.go`: task type constants — TypeEmailSend, TypeSMSSend, TypeWhatsAppSend, TypeReportGen, TypeAIScoring, TypeBackupCreate, TypeRestoreExecute, TypeProvisionSchool; **NO TypeAIDocIngest yet**; `TaskHandlers` struct + `TaskPayload` helpers
- `backend/internal/queue/worker.go`: `QueueWorker` (asynq.Server + ServeMux), queues `{"default": 3, "provisioning": 1}`, exponential `RetryDelayFunc`, `IsFailure: true` for all errors (returns false never — all errors count as failures); `asynq.SkipRetry` NOT used anywhere yet
- `backend/internal/router/setup.go` (~line 290): `taskHandlers := queue.TaskHandlers{...}` wiring; `newAIScoringHandler(db, aiProvider)` is the pattern (unmarshal payload → logger.Info with school_id → nil provider = warn+skip → gorm fetch → wrapped errors)
- `backend/internal/router/router.go`: `ai := authGroup(v2, "/ai", jwtService, rdb, tenantResolutionService, auditLogger)` with `ai.POST("/chat", aiHandler.Chat)`, `ai.GET("/agents", aiHandler.ListAgents)`, `ai.POST("/search", aiHandler.Search)`; `authGroup` = JWTAuth + EnforceSchoolID + TenantResolution + TenantDBResolver + AuditLogging
- `backend/internal/middleware/tenant.go`: `GetTenantDB(c) *gorm.DB`, `GetSchemaName(c) string`, `GetSchemaDB(c)`
- `backend/pkg/response`: `Success(c, data)`, `SuccessWithPagination`, `Error(c, status, code, message, category)`, `ErrorWithDetails`
- `backend/internal/helpers/helpers.go`: `ParsePagination(c) (int, int)`
- `backend/internal/ws/hub.go` + `room.go`: `Hub.Broadcast(roomName, msg)`, `ws.UserRoom(schoolID, userID)`, `ws.NewNotification(roomName, payload)`
- `backend/internal/modules/notifications/service.go`: `NotificationService.Create(ctx, tenantDB, userID, schoolID, title, message, notifType)` — creates DB row + `hub.Broadcast` + FCM push + audit — **the "event → notify" pattern**
- `backend/internal/modules/media/service.go` + `handler.go`: `c.FormFile("file")`, `storage.Driver` (local.go `NewLocalStorage(basePath, baseURL)`), school-scoped path prefix — upload pattern reference
- `backend/internal/modules/ai/handler.go`: `AIHandler` (runner, agents, store, searchEngine); `WithSearchEngine` setter

### Schema / data model precedents
- **Shared/public precedent**: `backend/internal/database/migrations/core/ai.go` `2026_07_27_000000_create_ai_conversation_tables` — `ai_conversations` + `ai_messages` AutoMigrate `conversation.ConversationRecord`/`MessageRecord`, `school_id` scoping, "infrastructure data, not per-tenant" — **recommended pattern for `ai_documents` status table (D-01)**
- **Per-tenant precedent**: `backend/internal/database/migrations/school/school.go` Group 28 `2026_08_01_000001_create_ai_vectors` — id VARCHAR(255) PK, collection, embedding `public.vector(1536)` QUALIFIED, document_id, chunk_index, text, created_at/updated_at; `search_path SET LOCAL school_N`, public NOT on path → tables QUALIFIED (`public.vector`, `public.vector_cosine_ops`)
- `backend/internal/ai/conversation/models.go`: `ConversationRecord`/`MessageRecord` (shared-schema models)
- No `AiDocument` model exists anywhere yet (grep verified) — new model needed
- `backend/internal/database/postgres.go`: `PrepareStmt FALSE` (SchemaTablePrefix corrupts field-index mappings when true)

### Decisions already locked (carry into Phase 4)
- SSE envelope = Go `EngineEvent{type, data}` single `data:` line; heartbeats `: ping` ≤30s; no gzip on text/event-stream (D-02)
- Service token only (`X-AI-Engine-Token`); Python validates `^school_\d+$` with NO fallback (D-07/D-09)
- `ai_vectors` per-tenant, embedding canon 1536-dim text-embedding-3-small, HNSW, `score = 1 - distance`, `ON CONFLICT (document_id, chunk_index) DO NOTHING` (Phase 2 D-01/D-09/D-14)
- Go seam FROZEN during Phase 3 (verified zero-diff); Phase 4 extension must stay interface-conformant
- `.planning/` gitignored, `commit_docs: false`; coarse granularity, sequential execution
- No new infra (Redis/Postgres shared-postgres already running; uploads volume exists)

## Open questions for discussion (04-DISCUSSION-LOG.md)

Gray-area decisions the planner/executor will need (agent picks recommended option, records rationale):

1. **`ai_documents` status table placement**: shared/public schema (ai_conversations precedent, school_id scoped) vs per-tenant schema (ai_vectors precedent)? Worker writes + GET scoping both matter.
2. **`document_id` contract**: Python generates uuid4 internally — for retry idempotency the Go worker must pass a stable `document_id`. Extend Python `DocumentsRequestIn` with optional `document_id` passthrough? (small Python change; required by ROADMAP criterion 4 "no duplicate vectors after worker restarts")
3. **State machine granularity**: 5 states queued → extracting → chunking → embedding → ready/failed — but Python `/v1/documents` is ONE call with no progress callbacks. Coarse mapping (queued→processing→ready/failed) vs fine-grained? What quality metrics to store?
4. **`ai:doc-ingest` retry classification**: which errors are permanent (`asynq.SkipRetry` + mark failed) vs transient (retry with backoff)? 400 ValueError → permanent; 503 EmbeddingNotConfigured → transient; 502/network/timeout → transient; file-not-found → permanent.
5. **SSE relay route placement + slow-client handling**: extend `modules/ai/handler.go` with new method + bounded channel (cap 64) + `c.Stream` + write-flush pattern? Where does the abort-on-slow-client logic live?
6. **Upload validation & path scheme**: accepted types (PDF/DOCX/PPTX/TXT/CSV + images), size cap, `c.FormFile("file")` + save to `/app/uploads/{school_id}/{uuid}.{ext}`? Permissions, overwrite policy?
7. **EngineClient wiring**: instantiate in setup.go when `AI.Enabled`; inject into AIHandler + asynq worker handler; `IngestDocument` added to interface (transport stays REST).
8. **Notification payload**: which users get notified on ready/failed (uploader only? admins?)? Reuse `NotificationService.Create` + `ws.UserRoom`?
9. **DLQ/archive SLO**: asynq archives exhausted-retry tasks to `asynq:{queue}:archived` — is monitoring via metrics/log only in Phase 4 (Phase 6 owns full dashboards)?
10. **`/v1/documents` response → Go**: map Python response to `IngestDocumentResponse` (document_id, chunks, pages, ocr_pages, chars, warnings) for status + quality metrics.

## Exit Criteria

- [ ] All 5 ROADMAP success criteria demonstrated (streaming envelope + 4 failure modes; 202 + status state machine; exactly-once worker call; idempotent ingest; ready → search returns chunks with citations)
- [ ] PIP-01, PIP-02, INT-01 checked in REQUIREMENTS.md
- [ ] Go suite passes (all tests incl. new SSE relay + pipeline tests); ruff/pyright clean for any Python touch
- [ ] Phase 4 VERIFICATION passed (verifier agent), STATE.md/ROADMAP.md updated
