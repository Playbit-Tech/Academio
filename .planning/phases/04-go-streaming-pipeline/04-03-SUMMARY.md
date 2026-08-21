---
phase: 04-go-streaming-pipeline
plan: 03
subsystem: database
tags: [go, gorm, postgres, migration, uuid, document-ingest, ai-documents]

# Dependency graph
requires:
  - phase: 04-go-streaming-pipeline
    plan: 01
    provides: EngineClient.IngestDocument seam + Python /v1/documents document_id passthrough (the worker and endpoints this table supports)
provides:
  - shared/public-schema `ai_documents` status table (D-01) keyed by UUID id — the row contract for the queue worker (04-02), upload/status handlers (04-04), and the engine document_id
  - 6-state const-guarded enum (queued|extracting|chunking|embedding|ready|failed) + quality metrics + ErrorReason JSON column (D-03)
  - `id` UUID doubles as engine document_id and enqueue JobID — one stable key across queue/table/engine (D-02)
affects: [04-02 asynq doc-ingest worker (writes status via models.AIDocument), 04-04 upload + status endpoints (school-scoped reads WHERE id = ? AND school_id = ?)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared-schema model convention: TableName() override + uuid string PK with gen_random_uuid() default + SchoolID uint indexed (NOT schema-per-tenant — D-01)"
    - "Status enum drift prevention: exported consts (DocumentStatus*) used instead of string literals (D-03)"
    - "Migration registration: one-per-domain file in migrations/core/, registered in CoreMigrations() via append(AIDocumentsMigrations()...) — core/ai.go left untouched"

key-files:
  created:
    - backend/internal/database/models/ai_document.go
    - backend/internal/database/migrations/core/ai_documents.go
  modified:
    - backend/internal/database/migrations/core/core.go

key-decisions:
  - "ai_documents lives in the SHARED public schema (D-01), not a tenant schema — the queue worker is not tenant-scoped and updates status without a tenant DB handle; school scoping via indexed school_id column"
  - "id (uuid, gen_random_uuid() default) is the single stable key reused as engine document_id and enqueue JobID (D-02)"
  - "Status enum declared as exported consts to prevent misspelled-state drift between worker and API"
  - "Failed rows carry ErrorReason as JSON text (D-03/D-04); quality metrics (pages, ocr_pages, chars, chunks) stored on the row"

patterns-established:
  - "Core migration files are one-per-domain: ai.go (conversations) unchanged, ai_documents.go added alongside — do not fold new domains into existing files"
  - "Migration struct has NO Name field — only {ID, Migrate, Rollback} (migration/types.go)"

requirements-completed: [PIP-01]

# Metrics
duration: 3min
completed: 2026-08-01
---

# Phase 04 Plan 03: Shared-Schema `ai_documents` Status Table + AIDocument Model Summary

**Shared `public.ai_documents` table created via a new core migration (`2026_07_27_000100_create_ai_documents`) with a UUID PK, indexed school_id, 6 const-guarded status values, quality columns, and ErrorReason text — registered in CoreMigrations() after AIMigrations() with core/ai.go untouched**

## Performance

- **Duration:** 3 min (2026-08-01T13:45:39Z → 2026-08-01T13:48:49Z)
- **Started:** 2026-08-01T13:45:39Z
- **Completed:** 2026-08-01T13:48:49Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified) in `backend/` submodule

## Accomplishments

- `AIDocument` model with 6 exported status consts (queued/extracting/chunking/embedding/ready/failed), uuid string PK (`gen_random_uuid()`), indexed `SchoolID` (not null), `Status` (size:32, indexed, default `'queued'`), `ErrorReason` text, and quality columns (Pages/OcrPages/Chars/Chunks)
- New core migration file `ai_documents.go` registered in `CoreMigrations()` right after `AIMigrations()` — verified against a fresh database
- Live DB verification: `public.ai_documents` exists with `ai_documents_pkey`, `idx_ai_documents_school_id`, `idx_ai_documents_status`; full `db-init DROP_TENANT=true → migrate → seed` chain still passes (no regression)

## Task Commits

Each task was committed atomically inside the `backend/` submodule:

1. **Task 1: AIDocument model in models/ (D-01, D-03)** - `5424519` (feat)
2. **Task 2: Core migration ai_documents.go + registration in core.go (D-01)** - `d22306c` (feat)

## Files Created/Modified

- `backend/internal/database/models/ai_document.go` - AIDocument model (shared public schema, TableName override, D-03 state enum + quality columns)
- `backend/internal/database/migrations/core/ai_documents.go` - AIDocumentsMigrations() with ID `2026_07_27_000100_create_ai_documents`; rollback drops only `ai_documents`
- `backend/internal/database/migrations/core/core.go` - one-line registration: `all = append(all, AIDocumentsMigrations()...)` after `AIMigrations()` (line 28)

## Decisions Made

- Followed plan exactly — shared public schema for the status table (D-01) with school scoping via `school_id` column, `id` as the single stable key across queue/table/engine (D-02), const-guarded enum + ErrorReason (D-03).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `psql` interactive password prompt — resolved by sourcing `DB_PASSWORD` from `backend/.env` for verification queries (non-issue).
- golangci-lint reports pre-existing failures in `models/lessonplan.go`, `models/session.go`, `tenant/provisioning.go` (gofmt/misspell, including false positives on French curriculum terms). All are unrelated files; the plan's verification falls back to `go vet ./internal/database/...` which passes clean. Changed files are lint-clean. Logged to `deferred-items.md`.

## Known Stubs

None.

## Next Phase Readiness

- The `models.AIDocument` row contract now exists at compile time — 04-02 (asynq doc-ingest worker, wave 3) can implement `db.Model(&models.AIDocument{})` status writes against the public schema, and 04-04 (upload/status endpoints, wave 4) can implement `WHERE id = ? AND school_id = ?` reads.
- Table verified live: uuid PK default `gen_random_uuid()`, `status` default `'queued'`, `school_id` + `status` indexes present.
- No blockers.

---
*Phase: 04-go-streaming-pipeline*
*Completed: 2026-08-01*

## Self-Check: PASSED

- FOUND: `backend/internal/database/models/ai_document.go`
- FOUND: `backend/internal/database/migrations/core/ai_documents.go`
- FOUND: `.planning/phases/04-go-streaming-pipeline/04-03-SUMMARY.md`
- FOUND: commit `5424519` (Task 1, feat(04-03))
- FOUND: commit `d22306c` (Task 2, feat(04-03))
