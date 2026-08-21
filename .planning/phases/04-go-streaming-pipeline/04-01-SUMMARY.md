---
phase: 04-go-streaming-pipeline
plan: 01
subsystem: api
tags: [go, fastapi, pydantic, pgvector, engine-client, document-ingest, idempotency]

# Dependency graph
requires:
  - phase: 03-python-ai-engine
    provides: Python /v1/documents one-call ingest (extract→chunk→embed→store) with UNIQUE(document_id, chunk_index) + ON CONFLICT DO NOTHING in ai_vectors
  - phase: 02-pgvector-migration
    provides: tenant ai_vectors DDL (HNSW index, idempotency constraint) in school_{id} schemas
provides:
  - Go EngineClient.IngestDocument seam method (POST /v1/documents, 5m budget, X-School-Schema header) with typed StatusError for permanent/transient classification
  - Python /v1/documents optional document_id passthrough — retries reuse ai_documents.id → idempotent ingest (ROADMAP criterion 4)
affects: [04-02 SSE relay (error typing), 04-03 asynq worker (calls IngestDocument exactly once per file, classifies StatusError), 04-04 upload handler (saves under AI_UPLOADS_DIR/{school_id}/{id}.{ext})]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StatusError{StatusCode, Body} typed error for engine non-200s — errors.As-safe permanent/transient classification (D-04)"
    - "json:\"-\" struct field → header-only transport (SchoolSchema never in body, D-09)"
    - "Caller-wins document_id: Python uses provided id INSTEAD of uuid4, uuid4 as fallback only (D-02)"

key-files:
  created:
    - backend/internal/ai/engine/client_ingest_test.go
  modified:
    - backend/internal/ai/engine/engine.go
    - backend/internal/ai/engine/client.go
    - ai-engine/app/api/extract.py
    - ai-engine/app/documents/pipeline.py
    - ai-engine/tests/test_documents.py

key-decisions:
  - "SchoolSchema is a json:\"-\" field sent as X-School-Schema header only — no fallback schema exists in Python (D-09), absent header → 400"
  - "IngestDocument reuses the 5m extractTimeout budget to match Python's /v1/documents budget (D-07, Rule B2 ctx propagation)"
  - "document_id passthrough is optional (str | None = None) — Phase 3 uuid4 default preserved for callers that don't supply one"
  - "No-text early return echoes the caller document_id so Go records chunks:0 against the same ai_documents row"

patterns-established:
  - "Engine seam extension is purely additive — existing Chat/ChatStream/Extract/Health signatures byte-identical"
  - "Non-200 engine responses always surface as *StatusError (never string-parsed)" 

requirements-completed: [PIP-01]

# Metrics
duration: 38min
completed: 2026-08-01
---

# Phase 04 Plan 01: EngineClient.IngestDocument Seam + Idempotent document_id Passthrough Summary

**Go EngineClient gains IngestDocument (POST /v1/documents, X-School-Schema header, typed StatusError for permanent/transient classification) and Python /v1/documents accepts an optional stable document_id so worker retries hit ON CONFLICT DO NOTHING — no duplicate vectors after restarts**

## Performance

- **Duration:** 38 min (2026-08-01T13:03Z → 2026-08-01T13:41Z)
- **Started:** 2026-08-01T13:03:00Z
- **Completed:** 2026-08-01T13:41:19Z
- **Tasks:** 2
- **Files modified:** 6 (3 Go, 3 Python)

## Accomplishments

- `EngineClient` interface extended additively with `IngestDocument(ctx, IngestDocumentRequest) (*IngestDocumentResponse, error)` — `Chat`/`ChatStream`/`Extract`/`Health` signatures byte-identical (interface-conformant, gRPC-ready)
- `httpClient.IngestDocument` posts `{document_path, collection, document_id}` to `/v1/documents` via `newRequest()` (X-AI-Engine-Token + X-Request-ID always set), adds `X-School-Schema` from the `json:"-"` `SchoolSchema` field, and runs under the 5m `extractTimeout` budget
- Every non-200 response returns a typed `*StatusError{StatusCode, Body}` (errors.As-safe for the 04-03 worker classifier); non-200 body-read errors handled per Rule B1 (no `_` discard)
- `SchoolSchemaHeader = "X-School-Schema"` constant exported alongside `EngineTokenHeader`/`RequestIDHeader`
- Python `DocumentsRequestIn` accepts `document_id: str | None = None`, passed through `ingest_document(path, schema, collection, document_id)`; pipeline uses the caller id instead of `uuid4` (`doc_id = document_id or str(uuid.uuid4())`) and echoes it in the no-text early return too
- Retry idempotency PROVEN against the live DB: re-POST with the same `document_id` returns `chunks == 0` (ON CONFLICT DO NOTHING) — ROADMAP criterion 4
- 6 new Go httptest cases + 4 new Python tests (2 ungated no-text passthrough, gated idempotency, uuid4-default regression)

## Task Commits

Each task was committed atomically:

1. **Task 1: Go seam — IngestDocumentRequest/Response + StatusError + httpClient.IngestDocument (D-07)** - `5e1f4a9` (feat, backend submodule `dev`)
2. **Task 2: Python document_id passthrough (D-02)** - `55e99af` (feat, root repo `main`)

**Plan metadata:** not committed — `.planning/` is gitignored and `commit_docs: false`.

## Files Created/Modified

- `backend/internal/ai/engine/engine.go` - `SchoolSchemaHeader` const; `IngestDocumentRequest` (json:"-" SchoolSchema)/`IngestDocumentResponse`/`StatusError` types; `IngestDocument` added to `EngineClient` interface after `Extract`
- `backend/internal/ai/engine/client.go` - `httpClient.IngestDocument` implementation: 5m budget, newRequest → /v1/documents, X-School-Schema header, `&StatusError` on non-200 with handled body-read error
- `backend/internal/ai/engine/client_ingest_test.go` - httptest fake-engine coverage: 200 full-field parse + header/body asserts, 400/503 → `*StatusError` via `errors.As`, closed-server network error → non-StatusError, absent schema → header omitted, ctx request-id propagation
- `ai-engine/app/api/extract.py` - `DocumentsRequestIn.document_id: str | None = None`; route passes it to `ingest_document`
- `ai-engine/app/documents/pipeline.py` - `ingest_document` signature gains `document_id`; `doc_id = document_id or str(uuid.uuid4())`; no-text early return echoes caller id
- `ai-engine/tests/test_documents.py` - ungated no-text unit passthrough + route-level echo test; `@LIVE_DB` idempotent-retry test (2nd insert `chunks == 0`, pre/post cleanup) + uuid4-default regression test

## Decisions Made

- **Typed status errors (D-04):** `StatusError{StatusCode, Body}` instead of string-wrapped errors — the 04-03 worker classifies 400 (permanent) vs 502/503/network (transient) via `errors.As`, never by parsing messages
- **Header-only schema (D-09):** `SchoolSchema string \`json:"-"\`` → X-School-Schema header; Python validates `^school_\d+$` with no fallback — absent header → 400, never a default schema
- **Caller-wins document_id (D-02):** provided id replaces uuid4; uuid4 only as fallback — preserves Phase 3 behavior for callers that don't send one (regression-tested)
- **Echo id in no-text path:** the 0-chunk success response carries the caller document_id so Go records `chunks: 0` against the same `ai_documents` row (no orphaned document rows)

## Deviations from Plan

None - plan executed exactly as written.

**Note on pre-existing state:** the `engine.go`/`client.go` edits specified by Task 1 were already present in the backend working tree (uncommitted) at execution start. They matched the plan's spec verbatim; this plan's work completed them (wrote `client_ingest_test.go`, verified build/test/lint, committed all three files atomically in `5e1f4a9`).

## Issues Encountered

- **Ruff E501 (line too long)** on the `ingest_document(...)` call in `extract.py` (101 chars) — wrapped the call across lines; re-ran ruff + pyright + full test suite, all clean
- **DB-gated tests:** without `AI_PGVECTOR_DSN` the gated tests skip cleanly (9 passed, 4 skipped — acceptable per plan). Additionally ran the full suite WITH the live `AI_PGVECTOR_DSN` from `backend/.env` against the running shared-postgres: **13 passed**, proving idempotency (2nd insert `chunks == 0`) and the uuid4 regression against real `school_1.ai_vectors` rows (cleaned up after)

## Known Stubs

None - the no-text response `document_id: None` (when no caller id supplied) is the intentional pre-existing Phase 3 behavior, preserved by design.

## User Setup Required

None - no external service configuration required. Tests use the existing shared-postgres (pgvector) + FakeEmbeddingClient (no live AI_OPENAI_API_KEY needed).

## Next Phase Readiness

- 04-02 (SSE relay) can rely on `*StatusError` typing for in-band error events
- 04-03 (asynq worker) has the exact contract it needs: call `IngestDocument` once per file with `ai_documents.id` as `document_id` + `school_{id}` schema; classify 400 permanent vs 502/503/network transient via `errors.As(err, &se)`
- 04-04 (upload handler) just needs to save under `{AI_UPLOADS_DIR}/{school_id}/{id}.{ext}` and store the id — Python re-checks containment (`_assert_within_uploads`) as defense in depth
- No blockers

---
*Phase: 04-go-streaming-pipeline*
*Completed: 2026-08-01*

## Self-Check: PASSED

- FOUND: `backend/internal/ai/engine/client_ingest_test.go`
- FOUND: `.planning/phases/04-go-streaming-pipeline/04-01-SUMMARY.md`
- FOUND: commit `5e1f4a9` (backend submodule — Task 1 Go seam)
- FOUND: commit `55e99af` (root repo — Task 2 Python passthrough)
