---
phase: 03-python-ai-engine
plan: 05
subsystem: api, database
tags: [fastapi, psycopg3, pgvector, pypdf, pytesseract, pdf2image, python-docx, python-pptx, openpyxl, tesseract-ocr]

# Dependency graph
requires:
  - phase: 03-python-ai-engine (03-02)
    provides: AI_PGVECTOR_DSN config, doc-parser deps in pyproject, AI_CHUNK_SIZE/OVERLAP + AI_MAX_DOC_* bounds
  - phase: 03-python-ai-engine (03-04)
    provides: EmbeddingClient.embed_texts (1536-dim asserted), require_token in app/security.py
  - phase: 02-pgvector-migration
    provides: school_{id}.ai_vectors tenant tables (D-09 column contract, UNIQUE(document_id, chunk_index))
provides:
  - app/db/ layer: lazy AsyncConnectionPool (register_vector_async), validate_schema_name gate, idempotent insert_chunks
  - Extractor suite: PDF per-page digital/OCR routing, DOCX/PPTX/XLSX/CSV/TXT, image OCR
  - chunker.py (1000/200 overlap) + one-call ingest_document pipeline
  - POST /v1/extract (Go ExtractRequest seam) + POST /v1/documents (tenant-scoped, X-School-Schema)
affects: [03-06 (search consumes app/db), Phase 4 PIP-01 (Go asynq → /v1/documents)]

# Tech tracking
tech-stack:
  added: [no new deps — all pre-installed in 03-02; psycopg sql.SQL identifier composition pattern]
  patterns:
    - "Tenant gate: regex + information_schema existence check on EVERY DB access, no fallback (D-07)"
    - "Schema-qualified INSERT via psycopg sql.Identifier (defense-in-depth over allowlist)"
    - "Per-page document routing: digital text layer > 20 chars vs OCR at 300 DPI (D-04)"
    - "Size bounds before parsing: 200 pages / 50MB / 80MP image pixels (T-03-05-03)"
    - "env-gated tests: DB tests skip without AI_PGVECTOR_DSN; OCR tests skip without tesseract (D-12)"

key-files:
  created: [app/db/pool.py, app/db/schema.py, app/db/vectors.py, app/documents/extractors/__init__.py, app/documents/extractors/pdf.py, app/documents/extractors/office.py, app/documents/extractors/image.py, app/documents/chunker.py, app/documents/pipeline.py, app/api/extract.py, tests/test_schema.py, tests/test_extract.py, tests/test_chunker.py, tests/test_documents.py]
  modified: [app/main.py]

key-decisions:
  - "Schema identifier interpolated via psycopg sql.Identifier (not raw f-string) — pyright-typed AND defense-in-depth quoting over the ^school_[0-9]+$ allowlist"
  - "Pillow bomb guard set on Image.MAX_IMAGE_PIXELS (Pillow 12.3.0 reads Image module global, NOT ImageFile)"
  - "require_token imported from app.security (not app.main — circular import, 03-04 pattern)"
  - "chunker test expectation corrected: stride-800 algorithm yields 4 chunks for 2500 chars; 2400 chars is the 3-chunk case"
  - "/v1/documents maps EmbeddingNotConfiguredError -> 503 (fail-loud, parity with /v1/embed)"

patterns-established:
  - "Pattern: validate_schema_name(schema, conn) called on the SAME pooled connection before any SQL; single allowlisted identifier"
  - "Pattern: ON CONFLICT (document_id, chunk_index) DO NOTHING gives exactly-once ingest for Phase 4 PIP-01"
  - "Pattern: lazy-import extractor modules inside the dispatcher (breaks extractors package circular import)"

requirements-completed: [PYE-02, PYE-04]

# Metrics
duration: 25min
completed: 2026-08-01
---

# Phase 3 Plan 05: Document Intelligence Summary

**Tenant-gated document intelligence: /v1/extract (pure parse, Go seam) + /v1/documents (one-call extract→chunk→embed→store), psycopg3+pgvector tenant DB layer with no-fallback schema validation, per-page digital/OCR PDF routing, and size-bounded extractors**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-01T09:11:00Z
- **Completed:** 2026-08-01T09:36:33Z
- **Tasks:** 3 (all `type="auto"`, plan is autonomous — no checkpoints)
- **Files modified:** 17 (16 created, 1 modified)

## Accomplishments

- `app/db/` tenant layer: lazy `AsyncConnectionPool` from `AI_PGVECTOR_DSN` with `configure=register_vector_async` (min 1 / max 4), `validate_schema_name` enforcing `^school_[0-9]+$` + `information_schema.schemata` existence on every DB access with NO fallback (D-07/D-09), and `insert_chunks` — idempotent `ON CONFLICT (document_id, chunk_index) DO NOTHING` writes qualified via psycopg `sql.Identifier`.
- Extractor suite with per-page routing (D-04): digital pages (>20 chars) parsed by pypdf, scanned pages OCR'd via pdf2image at 300 DPI + pytesseract with Pillow grayscale/autocontrast preprocessing; DOCX/PPTX/XLSX/CSV/TXT via python-docx/pptx/openpyxl/csv; image OCR with an 80-megapixel decompression-bomb guard.
- DoS bounds enforced before parsing (T-03-05-03): 200-page PDF cap, 50MB file-size cap, 80MP image-pixel cap, type allowlist.
- One-call pipeline `ingest_document` (PIP-01-ready for the Go asynq worker) and both routes wired into `main.py`: `/v1/extract` (no tenant header — pure parse, satisfies Go `ExtractResponse{Status}`) and `/v1/documents` (hard-requires `X-School-Schema`, 400 without/with invalid schema).
- Live DB verification against shared-postgres: real writes into `school_1.ai_vectors`, idempotency confirmed (second insert of same document_id/chunk_index returns 0 rows), cleanup after tests.

## Task Commits

Each task was committed atomically (single-repo root, explicit pathspec — pre-staged `.planning/`/`.gitignore` changes excluded):

1. **Task 1: Tenant DB layer — pool.py, schema.py, vectors.py (D-07)** - `66e3768` (feat)
2. **Task 2: Extractor suite — PDF per-page routing (D-04), office, images** - `422f727` (feat)
3. **Task 3: Chunker + pipeline + /v1/extract + /v1/documents (PYE-02/PYE-04)** - `8612478` (feat)

**Plan metadata:** final docs commit intentionally NOT created — per execution instructions, `.planning/` changes (SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md) are left in the working tree for the orchestrator (pre-staged changes from prior phase processes must not be swept in).

## Files Created/Modified

- `ai-engine/app/db/__init__.py` - Tenant DB layer package docstring
- `ai-engine/app/db/pool.py` - Lazy AsyncConnectionPool singleton (AI_PGVECTOR_DSN, register_vector_async)
- `ai-engine/app/db/schema.py` - validate_schema_name: ^school_[0-9]+$ + existence, no fallback
- `ai-engine/app/db/vectors.py` - insert_chunks: idempotent schema-qualified INSERT (sql.Identifier + Vector)
- `ai-engine/app/documents/__init__.py` - Documents package docstring
- `ai-engine/app/documents/extractors/__init__.py` - ExtractionResult + extract_document dispatcher (size/type gates)
- `ai-engine/app/documents/extractors/pdf.py` - Per-page digital (pypdf) vs OCR (pdf2image 300 DPI + pytesseract)
- `ai-engine/app/documents/extractors/office.py` - DOCX/PPTX/XLSX/CSV/TXT extractors
- `ai-engine/app/documents/extractors/image.py` - Image OCR with Image.MAX_IMAGE_PIXELS guard
- `ai-engine/app/documents/chunker.py` - Fixed-size 1000/200 overlap chunker
- `ai-engine/app/documents/pipeline.py` - ingest_document: extract → chunk → embed → store
- `ai-engine/app/api/extract.py` - POST /v1/extract + POST /v1/documents routes
- `ai-engine/app/main.py` - Wired extract_router (modified)
- `ai-engine/tests/test_schema.py` - Regex gate (8 cases), existence probe, live-DSN validate + idempotency
- `ai-engine/tests/test_extract.py` - Dispatcher gates, txt/csv/docx/xlsx, real digital-PDF routing, gated OCR
- `ai-engine/tests/test_chunker.py` - Chunk boundaries, overlap guard, full-coverage reconstruction
- `ai-engine/tests/test_documents.py` - Route 401/400/200 + live-DB pipeline store test (stubbed embedder)

## Decisions Made

- Schema identifier composed with psycopg `sql.Identifier` instead of the plan's raw f-string — required for the pyright gate AND adds proper identifier quoting as defense-in-depth over the regex allowlist (T-03-05-01).
- Decompression-bomb guard set on `Image.MAX_IMAGE_PIXELS` — Pillow 12.3.0's `_decompression_bomb_check` reads the `Image` module global; `ImageFile.MAX_IMAGE_PIXELS` does not exist in this version (the plan's snippet was a silent no-op).
- `require_token` imported from `app.security` per the 03-04 circular-import deviation (plan snippet said `app.main`).
- `/v1/documents` maps `EmbeddingNotConfiguredError` → 503 (fail-loud, parity with `/v1/embed`); the plan only handled ValueError (would have 500'd).
- `.xls` routed to the office extractor but wrapped so openpyxl's rejection of legacy `.xls` becomes a clean 400 ValueError.
- Legacy `.xls` + chunker test expectations corrected (see deviations).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] psycopg execute() rejects f-string SQL under pyright**
- **Found during:** Task 1 (vectors.py)
- **Issue:** `conn.execute(f"INSERT INTO {schema}.ai_vectors ...")` — psycopg types `execute(query: QueryNoTemplate)` (`LiteralString | SQL | Composed`); the f-string with a runtime `{schema}` is plain `str` → pyright gate failed.
- **Fix:** Composed the statement with `psycopg.sql.SQL("INSERT INTO {}...").format(sql.Identifier(schema))` — satisfies pyright AND quotes the identifier (defense-in-depth over the allowlist; all values stay `%s`).
- **Files modified:** ai-engine/app/db/vectors.py
- **Verification:** pyright 0 errors; live insert still passes; idempotency test green.
- **Committed in:** 66e3768 (Task 1)

**2. [Rule 1 - Bug] ExtractionResult(text) without default broke pdf.py construction**
- **Found during:** Task 2 (pdf.py)
- **Issue:** Plan's dataclass declared `text: str` (no default) but pdf.py constructs `ExtractionResult(pages=pages)` → TypeError at runtime.
- **Fix:** Defaulted `text: str = ""` (dataclass field ordering stays valid).
- **Files modified:** ai-engine/app/documents/extractors/__init__.py
- **Verification:** PDF digital-routing test passes.
- **Committed in:** 422f727 (Task 2)

**3. [Rule 1 - Bug] Pillow bomb guard referenced the wrong module**
- **Found during:** Task 2 (image.py)
- **Issue:** Plan set `ImageFile.MAX_IMAGE_PIXELS` — in Pillow 12.3.0 `_decompression_bomb_check` reads `Image.MAX_IMAGE_PIXELS` (module global in Image.py); `ImageFile` has no such attribute (silent no-op + pyright attr error).
- **Fix:** `Image.MAX_IMAGE_PIXELS = 80_000_000` (verified against installed Pillow source).
- **Files modified:** ai-engine/app/documents/extractors/image.py
- **Verification:** pyright 0 errors; T-03-05-03 guard actually engaged at runtime.
- **Committed in:** 422f727 (Task 2)

**4. [Rule 1 - Bug] Plan's chunker test expectation arithmetically wrong**
- **Found during:** Task 3 (test_chunker.py)
- **Issue:** Plan asserted "2500 chars → 3 chunks" for the stride-800 algorithm — the loop yields 4 chunks (starts 0/800/1600/2400, trailing partial [2400:2500]).
- **Fix:** Tests assert the algorithm's true behavior: 2400 chars → exactly 3 chunks (the plan's intended case, full coverage) plus 2500 chars → 4 chunks with the 100-char tail.
- **Files modified:** ai-engine/tests/test_chunker.py
- **Verification:** chunker tests pass (6/6).
- **Committed in:** 8612478 (Task 3)

**5. [Rule 2 - Missing Critical] require_token import + unhandled EmbeddingNotConfiguredError**
- **Found during:** Task 3 (api/extract.py)
- **Issue:** Plan snippet imported `require_token` from `app.main` (circular import — 03-04 moved it to `app.security`); `/v1/documents` also didn't map the embed-not-configured error (would 500 instead of a clean 503).
- **Fix:** Import from `app.security`; added `EmbeddingNotConfiguredError → 503`.
- **Files modified:** ai-engine/app/api/extract.py
- **Verification:** route tests green (401/400/200); no circular import at app startup.
- **Committed in:** 8612478 (Task 3)

**6. [Rule 3 - Blocking] pyright type errors in extractors/tests**
- **Found during:** Tasks 1-3
- **Issue:** pptx `shape.text` unknown on `BaseShape` stubs; pytest `tmp_path` fixture mis-typed as `TempPathFactory`; unused imports in plan snippets (schema.py pool import, test `os`); ruff `zip()` B905; line-length on strict=True.
- **Fix:** `getattr(shape, "text", None)`; `tmp_path: Path`; removed unused imports; `zip(..., strict=True)`; reformatted.
- **Files modified:** app/documents/extractors/office.py, tests/test_extract.py, app/documents/pipeline.py
- **Verification:** `ruff check .` + `pyright` clean (0 errors).
- **Committed in:** 422f727, 8612478

**7. [Rule 3 - Blocking] Invalid-schema route test needs the DB path**
- **Found during:** Task 3 (test_documents.py)
- **Issue:** `insert_chunks` calls `get_pool()` before `validate_schema_name`, so the invalid-regex test (b) requires AI_PGVECTOR_DSN (RuntimeError otherwise).
- **Fix:** Gated test (b) with `@pytest.mark.skipif(not os.getenv("AI_PGVECTOR_DSN"))` — it exercises the real validation path when a DSN is present.
- **Files modified:** ai-engine/tests/test_documents.py
- **Verification:** skips cleanly without DSN; 400 with DSN.
- **Committed in:** 8612478 (Task 3)

---

**Total deviations:** 7 auto-fixed (4 bug, 3 blocking)
**Impact on plan:** All fixes necessary for the ruff/pyright gates and runtime correctness/security. No scope creep — no architectural changes, no new deps, Go seam untouched.

## Issues Encountered

- Chunker test expected-count arithmetic (deviation 4) — resolved by asserting the algorithm's real behavior.
- Sparse-file trick (open + truncate) used for the >50MB size-gate test instead of mocking `os.path.getsize` — no test-pollution risk.
- The OCR test and the live-key embed test skip on this host (no tesseract binary, no AI_OPENAI_API_KEY) — both are Docker/live-env gated per D-12 and RESEARCH Pitfall 6.

## User Setup Required

None - no external service configuration required. `AI_PGVECTOR_DSN` already present in `backend/.env`; tesseract/poppler installed in the Docker image (03-02 Dockerfile apt layer).

## Next Phase Readiness

- `app/db/` layer (pool/schema/vectors) ready for 03-06 (`/v1/search` — hybrid dense `<=>` + ts_rank BM25 + RRF), which reuses `get_pool()` and `validate_schema_name()`.
- `/v1/documents` is the single call Phase 4's Go asynq worker (PIP-01) will POST — exactly-once via ON CONFLICT.
- `/v1/extract` satisfies the Go `ExtractRequest/ExtractResponse` seam (extra fields additive — Go ignores unknown JSON).
- No blockers. Host-side OCR verification requires the Docker image (tesseract only exists there).

---
*Phase: 03-python-ai-engine*
*Completed: 2026-08-01*

## Self-Check: PASSED

All 17 files verified present; all 3 task commits verified in `git log` (66e3768, 422f727, 8612478). Full suite with live DSN: 81 passed / 2 skipped; without DSN: 77 passed / 6 skipped (all env-gated skips clean). `ruff check .` and `pyright` both clean.
