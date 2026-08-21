---
phase: 04-go-streaming-pipeline
plan: 04
subsystem: api
tags: [go, gin, multipart-upload, asynq, file-upload, config, docker-compose]

# Dependency graph
requires:
  - phase: 04-go-streaming-pipeline
    provides: "04-01 EngineClient.IngestDocument seam + StatusError; 04-03 shared public-schema ai_documents table + AIDocument model; 04-02 ai:doc-ingest asynq worker (TypeDocIngest, DocIngestPayload, handler wired in setup.go)"
provides:
  - "POST /api/v2/ai/documents multipart upload (202 Accepted + job_id) with extension/content-type/size validation, shared-volume persistence under {AI_UPLOADS_DIR}/school_{id}/{id}.{ext}, queued-row create + ai:doc-ingest enqueue with asynq.Timeout(6m)+MaxRetry(5)"
  - "GET /api/v2/ai/documents/:id/status school-scoped D-03 state + quality metrics (pages/ocr_pages/chars/chunks)"
  - "AI_UPLOADS_DIR (required absolute path) + AI_MAX_DOC_MB (default 50, hard cap 200) config with fail-fast startup validation; env example + compose wiring on BOTH api and ai-engine services"
affects: [04-05, INT-01 SSE relay, frontend AI assistant, PIP-02 verification]

# Tech tracking
tech-stack:
  added: [asynq enqueue-time options (Timeout/MaxRetry), http.MaxBytesReader multipart bounding]
  patterns:
    - "Standard 4-file module layout (dto/handler/service/repository) with repository interface at top"
    - "Setter-based DI on AIHandler (WithDocumentService / WithSearchEngine / WithAuditLogger) — NewAIHandler signature untouched"
    - "Upload safety: ext allowlist + content-type sniff + MaxBytesReader + server-generated {id}.{ext} filename (original name = metadata only)"
    - "Post-create failure hygiene: repo.SetFailed + error propagation (B9) — no silent queue drop"
    - "202 Accepted async-acceptance precedent (restore/handler.go)"
    - "Audit via middleware.LogMutation on mutation (B11) — ai route group has no AuditLogging middleware"

key-files:
  created:
    - backend/internal/modules/ai/dto.go
    - backend/internal/modules/ai/service.go
    - backend/internal/modules/ai/repository.go
  modified:
    - backend/internal/modules/ai/handler.go
    - backend/internal/router/router.go
    - backend/internal/router/setup.go
    - backend/internal/config/config.go
    - backend/internal/config/config_test.go
    - backend/.env.example
    - backend/docker-compose.yml

key-decisions:
  - "WithDocumentService(docs *DocumentService) setter takes a composed service; setup.go builds NewDocumentService(cfg.AI, queueClient, repo) — delivers the queueClient+cfg.AI+repo wiring the plan's key_links require, resolving the plan's setter-signature ambiguity in favor of the Task 1 spec text"
  - "config.go (a Task 3 file) pulled forward into the Task 1 commit — service.go compiles against cfg.AI.UploadsDir/MaxDocMB, so the fields + fail-fast validation shipped with the service that consumes them"
  - "uploaded file saved under 0700 dir per the messages-module pattern; original filename stored as FileName metadata only"
  - "Doc ID generated server-side (uuid.NewString(), same format as DB gen_random_uuid()) so FilePath (NOT NULL) is written in the single Create call; doubles as engine document_id + queue JobID"

patterns-established:
  - "Upload endpoints: MaxBytesReader bounding before FormFile, allowlist validation in service (sentinel errors → 4xx), persistence/enqueue failures → 5xx with SetFailed"
  - "Config: absolute-path + bounds validation unconditionally at startup (Rule B12), no silent fallback"

requirements-completed: [PIP-01, PIP-02]

# Metrics
duration: 25min
completed: 2026-08-01
---

# Phase 04 Plan 04: Upload + Status API Surface Summary

**Multipart document upload API (202 Accepted → shared volume → ai:doc-ingest with Timeout(6m)+MaxRetry(5)) plus school-scoped D-03 status endpoint, with fail-fast AI_UPLOADS_DIR/AI_MAX_DOC_MB config and compose/env wiring on both api and ai-engine services**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-01T14:11:00Z
- **Completed:** 2026-08-01T14:36:15Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- `POST /api/v2/ai/documents` — multipart `file` upload (PIP-01 criterion 3): extension allowlist (pdf/docx/pptx/txt/csv/png/jpg/jpeg/gif), content-type sniff on first 512 bytes, `http.MaxBytesReader` + header.Size cap (AI_MAX_DOC_MB, default 50), server-generated `{id}.{ext}` filename, queued-row create, save to `{AI_UPLOADS_DIR}/school_{id}/{id}.{ext}`, enqueue `ai:doc-ingest` with `asynq.Timeout(6*time.Minute)` + `asynq.MaxRetry(5)` (D-04: server does not apply QueueConfig.MaxRetries), 202 Accepted with `job_id` + `status`.
- `GET /api/v2/ai/documents/:id/status` — school-scoped read (`WHERE id = ? AND school_id = ?`, JWT-derived school ID, never the id alone), reports D-03 state + quality metrics (pages/ocr_pages/chars/chunks) + error_reason.
- All 7 STRIDE threats mitigated (allowlists + MaxBytesReader + generated filenames T-04-04-01, numeric school dir from JWT T-04-04-02, scoped read T-04-04-03, SetFailed + propagate on enqueue failure T-04-04-04, dual-layer size cap T-04-04-05, auth-group routes + audit T-04-04-06, identical AI_UPLOADS_DIR on both containers + startup validation T-04-04-07).
- Config: `AIConfig.UploadsDir` (AI_UPLOADS_DIR, required + absolute, B12) + `MaxDocMB` (AI_MAX_DOC_MB, default 50, hard cap 200); config_test.go updated with 6 new cases. Compose sets `AI_UPLOADS_DIR: /app/uploads` on the api AND ai-engine env blocks (shared `uploads_data` volume, existing mounts untouched); `.env.example` documents both vars.
- Mutation audit-logged via `WithAuditLogger` + `middleware.LogMutation` (Rule B11 — ai group has no AuditLogging middleware).

## Task Commits

Each task was committed atomically:

1. **Task 1: Upload + status DTOs, service, repository (D-06)** - `6842f70` (feat)
2. **Task 2: Handlers + router registration + setup wiring** - `6bccbba` (feat)
3. **Task 3: Config + env + compose wiring** - `ccd126a` (chore)

**Plan metadata:** not committed (`.planning/` gitignored, `commit_docs: false`)

_Note: Task 1 (6842f70) also carried `config.go` + `config_test.go` forward as a blocking dependency; Task 3's config.go portion therefore shipped inside the Task 1 commit and only `.env.example` + `docker-compose.yml` landed in Task 3._

## Files Created/Modified

- `backend/internal/modules/ai/dto.go` - `UploadDocumentRequest` (multipart marker) + `DocumentStatusResponse` (D-03 state + quality metrics)
- `backend/internal/modules/ai/service.go` - `DocumentService`: allowlists, size cap, path construction, queued-row create, save, enqueue (Timeout 6m + MaxRetry 5), `SetFailed` on post-create failures, status fetch
- `backend/internal/modules/ai/repository.go` - `AIDocumentRepository` interface + `aiDocumentRepo` (Create / GetByIDAndSchoolID / SetFailed) on core public-schema db
- `backend/internal/modules/ai/handler.go` - `AIHandler.docs` field, `WithDocumentService`/`WithAuditLogger` setters, `UploadDocument` (202) + `GetDocumentStatus` handlers (extended additively — chat/search/agents untouched)
- `backend/internal/router/router.go` - `api.POST("/ai/documents", ...)` + `api.GET("/ai/documents/:id/status", ...)` inside the JWT-protected `ai` group (authGroup)
- `backend/internal/router/setup.go` - `NewAIDocumentRepository(db)` + `NewDocumentService(cfg.AI, queueClient, aiDocRepo)` wired via `WithDocumentService` + `WithAuditLogger`
- `backend/internal/config/config.go` - `UploadsDir` + `MaxDocMB` in AIConfig with env tags, defaults, and fail-fast validation (absolute path; 0 < MaxDocMB <= 200)
- `backend/internal/config/config_test.go` - 6 new validation cases
- `backend/.env.example` - AI_UPLOADS_DIR + AI_MAX_DOC_MB documented next to the AI_* block
- `backend/docker-compose.yml` - `AI_UPLOADS_DIR: /app/uploads` + `AI_MAX_DOC_MB: "${AI_MAX_DOC_MB:-50}"` on api and ai-engine services

## Decisions Made

- **Setter signature:** `WithDocumentService(docs *DocumentService)` per Task 1 spec text; setup.go composes `NewDocumentService(cfg.AI, queueClient, aiDocRepo)` — satisfies the plan's key_link (`WithDocumentService(queueClient, cfg.AI, repo)`) via composition, name standardized everywhere (grep-verified in handler.go + setup.go).
- **config.go pulled forward into Task 1 commit:** the service cannot compile without `cfg.AI.UploadsDir`/`MaxDocMB`; shipping them together keeps every commit buildable.
- **Audit without middleware:** the ai route group does not mount `AuditLogging`; mutation audit is done explicitly via `middleware.LogMutation` guarded on `WithAuditLogger` being wired (best-effort, per the existing pattern).
- **Dirs created 0700** (execute bit for worker/container traversal) with `nolint:gosec` comment, mirroring the messages module.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written. All three tasks' files and behaviors match the plan spec; the only ordering adjustment (config.go in the Task 1 commit) is documented above as a decision, not a defect.

---

**Total deviations:** 0 auto-fixed
**Impact on plan:** None — implementation matches plan intent exactly.

## Issues Encountered

- **Live smoke test not run:** the running dev server (`./bin/server`, PID 1011168) was started at 08:00 — before this plan's changes — so both new routes return 404 on it, and Air is not running to hot-reload. A fresh binary would also fail-fast at boot because `AI_UPLOADS_DIR` is absent from the local `backend/.env` (gitignored, out of this plan's file scope). Restarting the user's dev server / editing local `.env` was deliberately avoided. When the server is next restarted with `AI_UPLOADS_DIR` set, the plan's smoke commands apply:
  - `curl -F "file=@test.pdf" -H "Authorization: Bearer <token>" http://localhost/api/v2/ai/documents` → 202 with `job_id`
  - `curl http://localhost/api/v2/ai/documents/<job_id>/status` → `queued` state
- Pre-existing golangci-lint findings in unrelated files (`internal/modules/lessonplan/service.go`, `service_test.go`) confirmed and logged to `deferred-items.md` (not fixed — out of scope). `golangci-lint run ./internal/modules/ai/...` is clean.

## User Setup Required

None — no external service configuration required. Note: local dev (`backend/.env`) must set `AI_UPLOADS_DIR` before the server will boot with this plan's config validation.

## Next Phase Readiness

- PIP-01 criterion 3 and PIP-02 endpoint surface complete and verified (`go build ./...`, `go vet ./internal/modules/ai/...`, `go test ./internal/config/...`, `docker compose -f backend/docker-compose.yml config --quiet` all pass; module lint clean).
- 04-05 (next plan) can proceed: the pipeline now has a full request path (upload → queue → worker [04-02] → engine [04-01] → status), enabling end-to-end integration tests and the SSE relay work (INT-01).
- Ready for the verifier to check must_haves (all grep-verified) and, if desired, the live smoke test after a server restart.

---
*Phase: 04-go-streaming-pipeline*
*Completed: 2026-08-01*

## Self-Check: PASSED

- Files: all 9 plan files + SUMMARY exist on disk (FOUND: dto.go, service.go, repository.go, handler.go, router.go, setup.go, config.go, .env.example, docker-compose.yml).
- Commits: 6842f70 (Task 1), 6bccbba (Task 2), ccd126a (Task 3) all present in backend submodule history.
- Verification: `go build ./...` exit 0; `go vet ./internal/modules/ai/...` clean; `go test ./internal/config/...` ok; `docker compose -f backend/docker-compose.yml config --quiet` exit 0; `golangci-lint run ./internal/modules/ai/...` clean.
- Must_haves grep-verified: `UploadDocumentRequest` (dto.go:8), `func (h *AIHandler) UploadDocument` (handler.go:269), `allowedExts = map[string]bool` (service.go:44), `func (r *aiDocumentRepo) GetByIDAndSchoolID` (repository.go:41), `documents/:id/status` (router.go:281), `WithDocumentService` (setup.go:829); `asynq.Timeout(6*time.Minute)` + `asynq.MaxRetry(5)` (service.go:193), `http.StatusAccepted` (handler.go:323), `Where("id = ? AND school_id = ?"` (repository.go:45), `AI_UPLOADS_DIR` in config.go + .env.example + both compose env blocks.
