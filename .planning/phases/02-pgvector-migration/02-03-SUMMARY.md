---
phase: 02-pgvector-migration
plan: 03
subsystem: database
tags: [pgvector, ai_vectors, hnsw, tenant-schema, migrations, gorm, pgv-04]

# Dependency graph
requires:
  - phase: 02-pgvector-migration
    provides: 02-01 canon lock (AI_EMBEDDING_DIM=1536, D-01/D-14), 02-02 vector extension in public schema + pgvector image
provides:
  - `ai_vectors` table in every school_{id} TENANT schema (12/12) with 1536-dim HNSW index
  - Versioned idempotent tenant migration 2026_08_01_000001_create_ai_vectors (schema-qualified public.vector(1536) + public.vector_cosine_ops)
  - Flattened Qdrant payload parity contract documented in-DDL (document_id/chunk_index/text ↔ _doc_id/_chunk_index/_text)
affects: [02-04 (PGVectorStore writes/reads ai_vectors), 02-05 (copy tool maps parity keys), 02-06 (config swap)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tenant migration DDL MUST schema-qualify extension types/opclasses (public.vector(1536), public.vector_cosine_ops) because ApplySchoolMigrationsForSchema sets schema-only SET LOCAL search_path (public not on path)"
    - "Single-statement Exec per Rule B4/B13 (pgx v5 prepared-statement mode); SQL comment + CREATE TABLE as one statement"
    - "SET LOCAL maintenance_work_mem = '128MB' inside the migration tx before the HNSW build (D-10)"

key-files:
  created: []
  modified:
    - backend/internal/database/migrations/school/school.go

key-decisions:
  - "D-09 executed as flattened columns (document_id/chunk_index/text, no jsonb) per agent discretion — matches Qdrant payload keys _doc_id/_chunk_index/_text, preventing payload-key drift between store (02-04) and copy tool (02-05); created_at AND updated_at both included per D-09 timestamps"
  - "Applied the new migration to all existing provisioned schemas via ApplySchoolMigrationsForSchema (temp gitignored runner in backend/tmp/) instead of cmd/migrate-schemas, which only handles schema_name IS NULL schools and is pre-existing-broken (database_name column)"

patterns-established:
  - "Tenant ai_vectors DDL pattern: CREATE TABLE (public.vector(1536), unique (document_id, chunk_index)) → collection btree index → SET LOCAL maintenance_work_mem → HNSW (embedding public.vector_cosine_ops) WITH (m=16, ef_construction=64)"
  - "Pending tenant migrations on already-provisioned schemas are applied via MigrateAllSchemaTenants/ApplySchoolMigrationsForSchema (runs all pending per schema, tracked in tenant_schema_migrations)"

requirements-completed: [PGV-04]

# Metrics
duration: 8min
completed: 2026-08-01
---

# Phase 02 Plan 03: Tenant ai_vectors DDL Migration Summary

**Per-tenant `ai_vectors` storage table with schema-qualified `public.vector(1536)` HNSW cosine index and flattened Qdrant payload-parity columns, applied and verified across all 12 `school_{id}` schemas via the versioned school migration `2026_08_01_000001_create_ai_vectors`**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-01T07:06:00Z
- **Completed:** 2026-08-01T07:11:00Z
- **Tasks:** 2
- **Files modified:** 1 in repo (backend submodule)

## Accomplishments
- `ai_vectors` table created in **all 12 `school_N` tenant schemas** (never `public` — verified 0 rows in public.pg_tables), with the full D-09 column set (11 columns incl. `embedding_model`, `model_version`, `chunking_version`) and `CONSTRAINT uq_ai_vectors_doc_chunk UNIQUE (document_id, chunk_index)`.
- Per-schema **HNSW index** `idx_ai_vectors_embedding_hnsw USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)` — verified `amname=hnsw` in every schema — plus `idx_ai_vectors_collection` btree, built under raised `SET LOCAL maintenance_work_mem = '128MB'` (D-10).
- Schema-qualified DDL proven live: `embedding` column type resolves to `public.vector` namespace (0 `vector` types in school_% schemas — T-PGV-04-04 cross-schema bleed control holds); unqualified lookup would have failed loudly under the schema-only search_path (T-PGV-04-01).
- Mandatory D-09 deviation SQL comment is the FIRST line of the CREATE TABLE Exec, self-documenting the parity contract (`_doc_id`/`_chunk_index`/`_text` ↔ `document_id`/`chunk_index`/`text`, jsonb omitted, timestamps included).
- Functional smoke test: 1536-dim insert works, wrong-dim insert rejected (`expected 1536 dimensions, not 3` — D-04 guard live), `1 - (embedding <=> ?)` cosine search returns correct scores, collection index exercised.
- Migration recorded in `tenant_schema_migrations` for every schema; re-run is a clean no-op (idempotency verified).

## Task Commits

Each task was committed atomically in the backend submodule (branch `dev`):

1. **Task 1: Add tenant ai_vectors DDL migration (PGV-04)** - `342d46e` (feat)
2. **Task 2: Apply migration to every existing tenant schema (PGV-04)** - no repo commit (migration applied via temporary gitignored runner in `backend/tmp/`, removed after use; zero tracked-file changes)

**Plan metadata:** `docs(02-pgvector-03): complete tenant ai_vectors DDL migration plan` (final commit, root repo)

## Files Created/Modified
- `backend/internal/database/migrations/school/school.go` - Appended versioned tenant migration `2026_08_01_000001_create_ai_vectors` to `SchoolMigrations()`: CREATE TABLE ai_vectors (id/collection/embedding public.vector(1536)/document_id/chunk_index/text/embedding_model/model_version/chunking_version/created_at/updated_at + uq_ai_vectors_doc_chunk), collection index, `SET LOCAL maintenance_work_mem = '128MB'`, HNSW index with `public.vector_cosine_ops`; Rollback `DROP TABLE IF EXISTS ai_vectors`; one Exec per statement (Rule B4/B13)

## Decisions Made
- **D-09 flattening (agent discretion):** `metadata jsonb` omitted; the three parity columns `document_id`/`chunk_index`/`text` map 1:1 to the real pipeline contract at `internal/ai/rag/pipeline.go:116-118` (Qdrant payload keys `_doc_id`/`_chunk_index`/`_text`). This is the exact mapping the copy tool (02-05) uses, so flattened columns prevent payload-key drift. `created_at` AND `updated_at` both included per D-09 "timestamps" (`updated_at` defaults to now() and is present for write-path updates even though v1 store only inserts).
- **Application mechanism (Rule 3 fix):** `cmd/migrate-schemas` only processes schools with `schema_name IS NULL` and is broken pre-existing (queries nonexistent `database_name`). Applied pending migration to all 12 schemas via `ApplySchoolMigrationsForSchema` (the machinery named in the plan) from a temporary runner in `backend/tmp/` (gitignored, deleted after use). Server binary rebuilt + restarted so future tenant provisioning includes the new migration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan's prescribed `cmd/migrate-schemas` cannot apply pending migrations to already-provisioned schemas**
- **Found during:** Task 2 (Apply migration to existing tenant schemas)
- **Issue:** The plan directed `go run ./cmd/migrate-schemas --dry-run` then run, expecting it to route through `MigrateAllSchemaTenants`. In reality `cmd/migrate-schemas/main.go` only selects schools with `schema_name IS NULL` (legacy dedicated-DB schools) — all 12 current schemas already have `schema_name` set, so it would apply nothing. It also crashes pre-existing with `ERROR: column "database_name" does not exist` (column removed from `schools` in an earlier schema-per-tenant migration; CLI not updated).
- **Fix:** Created a temporary gitignored runner (`backend/tmp/apply-tenant-migrations/main.go`) that enumerates ALL `school_%` schemas from `information_schema` and calls the project's own `ApplySchoolMigrationsForSchema` per schema (same `SET LOCAL search_path` + `tenant_schema_migrations` tracking machinery the plan names). Ran it (12/12 OK), re-ran to prove idempotency, then deleted it. No repo files added.
- **Files modified:** none in repo (runner was in gitignored `backend/tmp/`, removed)
- **Verification:** `pg_tables` shows `ai_vectors` in all 12 schemas; `tenant_schema_migrations` records the new ID in each; re-run applied 0 migrations
- **Committed in:** no commit (transient tooling; task had no tracked-file changes)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation changed only the application mechanism to the machinery the plan itself named (`ApplySchoolMigrationsForSchema`/`MigrateAllSchemaTenants`). No scope creep; no DDL change. The broken `cmd/migrate-schemas` CLI is a pre-existing out-of-scope bug logged to `deferred-items.md`.

## Issues Encountered
- **`cmd/migrate-schemas` broken pre-existing** (`database_name` column missing) — worked around via the per-schema machinery; logged to `deferred-items.md` (out of scope, do-not-fix per scope boundary rule).
- **Orphaned schemas school_10/11/12** (no `schools` row; leftover from deleted schools) — still migrated: `ApplySchoolMigrationsForSchema` ran against them with school_id=0; all three now have `ai_vectors`. Documented here for 02-04/02-05 awareness.
- **`format_type` shows unqualified `vector(1536)`** in the plan's verify command — expected: `format_type` omits the schema when it's on the query session's search_path. Confirmed via `pg_namespace` join that the type is `public.vector` (0 vector types in school_% namespaces).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- **02-04 (PGVectorStore):** `ai_vectors` is live in every tenant schema with the exact column set the store writes (id/collection/embedding/document_id/chunk_index/text/embedding_model/model_version/chunking_version/timestamps). Store queries should use `repos.TenantDB()` (schema-scoped, Rule B8) with the app's default search_path (`"$user", public`) so `<=>` resolves via public — verified working in the runtime context (`SET LOCAL search_path TO school_1, public`).
- **02-05 (copy tool):** parity keys `_doc_id`/`_chunk_index`/`_text` ↔ `document_id`/`chunk_index`/`text` mapping is documented in the DDL comment — the copy tool can rely on it.
- **No blockers.** Server is running the rebuilt binary (includes the new migration for future provisioning).

---
*Phase: 02-pgvector-migration*
*Completed: 2026-08-01*

## Self-Check: PASSED

- FOUND: `.planning/phases/02-pgvector-migration/02-03-SUMMARY.md`
- FOUND: backend commit `342d46e` (feat(02-03): add tenant ai_vectors DDL migration with HNSW index)
- FOUND: root commit `70b1bf6` (feat(02-03): bump backend submodule to 342d46e)
- FOUND: requirements frontmatter `requirements-completed: [PGV-04]`
