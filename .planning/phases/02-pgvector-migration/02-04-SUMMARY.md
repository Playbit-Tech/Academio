---
phase: 02-pgvector-migration
plan: 04
subsystem: api
tags: [pgvector, gorm, golang, vector-search, hnsw, multi-tenant]

# Dependency graph
requires:
  - phase: 02-01
    provides: pgvector extension + hstore research, pgvector-go v0.4.1 choice, tenancy resolution patterns
  - phase: 02-03
    provides: tenant `ai_vectors` DDL (flattened columns + HNSW vector_cosine_ops index) in all school_{id} schemas
provides:
  - PGVectorStore implementing vector.Store (Insert/Search/Delete/Close) with context-resolved tenancy
  - SchemaTablePrefix plugin fix: .Table() queries now schema-qualified (was silently broken in GORM v1.31.2)
  - Score parity contract: cosine similarity = 1 - cosine distance, matching Qdrant semantics
  - Unit + integration conformance tests for the store
affects: [02-05, 02-06, 02-07, agent runtime swap, RAG pipeline verification]

# Tech tracking
tech-stack:
  added: [github.com/pgvector/pgvector-go v0.4.1]
  patterns:
    - "Tenancy-from-context store pattern: resolve TenantRepositories via CtxKeyTenantRepos, fall back to GetSchoolIDFromCtx + deterministic school_{id} schema, regex-validate before any SQL interpolation"
    - "Fail-loud metadata contract: missing _doc_id/_chunk_index returns error, never silent default"
    - "Limit clamp in service layer: [1,1000] default 10 (Rule B5)"

key-files:
  created:
    - backend/internal/ai/vector/pgvector.go
    - backend/internal/ai/vector/pgvector_test.go
  modified:
    - backend/internal/database/tenant/schema_db.go (TableExpr rewrite in prefix callback)
    - backend/go.mod, backend/go.sum (pgvector-go direct require)

key-decisions:
  - "Fixed SchemaTablePrefix plugin to rewrite Statement.TableExpr: GORM v1.31.2 QuoteTo prefers TableExpr (captured at .Table() call time) over the plugin-mutated Statement.Table, so .Table('ai_vectors') silently hit the unqualified table; now resolves to school_{id}.ai_vectors exactly as the plan's key-link intended"
  - "tenantFor returns the validated schema string alongside repos — Search/Delete build qualified table names from it instead of repos.SchemaName(), which is empty on the ForSchoolSchema path (verified in factory.go)"
  - "Insert keeps repos.TenantDB().Table('ai_vectors') (plan key-link); Search/Delete use raw SQL with only the regex-validated schema interpolated (Rule B7), preserving ORDER BY embedding <=> ? for HNSW"

patterns-established:
  - "Pattern: schema name derived ONLY from ctx repos or validated schoolID (T-PGV-03-01), never from request input; single regex gate ^school_[0-9]+$ before SQL interpolation"
  - "Pattern: 1 - (embedding <=> ?) score conversion kept inline in SELECT so HNSW index applies (T-PGV-03-05)"

requirements-completed: [PGV-03]

# Metrics
duration: 15min
completed: 2026-08-01
---

# Phase 2 Plan 04: PGVectorStore Summary

**PGVectorStore over per-tenant `ai_vectors` with context-resolved tenancy, Qdrant-compatible cosine scores, and a SchemaTablePrefix plugin fix that makes `.Table()` queries schema-qualified**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-01T06:17:52Z
- **Completed:** 2026-08-01T06:32:29Z
- **Tasks:** 2
- **Files modified:** 5 (backend)

## Accomplishments
- `PGVectorStore` (Insert/Search/Delete/Close) implementing the existing `vector.Store` interface — zero changes to RAG pipeline or agents (`git diff --name-only internal/ai/rag/ internal/ai/agents/` is empty)
- Tenancy resolved per request from `context.Context` (D-08): `CtxKeyTenantRepos` repos first, then `GetSchoolIDFromCtx` → deterministic `school_{id}` schema, regex-validated (`^school_[0-9]+$`) before any SQL interpolation — never the core DB (Rule B8)
- Score parity (D-13): `1 - (embedding <=> ?)` with `ORDER BY embedding <=> ?` so the `vector_cosine_ops` HNSW index applies (T-PGV-03-05); `_doc_id`/`_chunk_index`/`_text` metadata preserved for the agent contract (D-09)
- Fail-loud guards (D-14): embedding dimension mismatch on Insert and Search errors; missing `_doc_id`/`_chunk_index` metadata errors — no silent truncation/defaults
- Integration test green against real `school_1.ai_vectors`: two orthogonal 1536-dim basis vectors, nearest-first ordering, score ≈ 1.0 / 0.0 (delta ≤ 0.001), collection isolation, idempotent delete + cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pgvector-go and write failing tests (RED)** - `1e30f9c` (test)
2. **Task 2: Implement PGVectorStore (GREEN)** - `5167d16` (feat)

**Plan metadata:** pending final docs commit (root repo)

_Note: TDD flow used (RED compile-failure → GREEN). The plugin fix in Task 2 touched an out-of-plan file — see Deviations._

## Files Created/Modified
- `backend/internal/ai/vector/pgvector.go` - PGVectorStore: tenancy resolution, row mapping, Insert/Search/Delete/Close
- `backend/internal/ai/vector/pgvector_test.go` - TestValidSchemaName, TestVectorDocumentMapping, TestPGVectorStoreIntegration (DSN-gated)
- `backend/internal/database/tenant/schema_db.go` - TableExpr rewrite in SchemaTablePrefix prefix() callback
- `backend/go.mod`, `backend/go.sum` - pgvector-go v0.4.1 (direct require after tidy)

## Decisions Made
- Fixed the tenant plugin rather than self-qualifying the Insert table: keeps the plan's key-link `repos.TenantDB().Table("ai_vectors")` intact and corrects the same silent mis-scoping for every other `.Table()` tenant query in the codebase (e.g. `user/handler.go:1230` subjects pluck).
- `tenantFor` returns the validated schema string for Search/Delete raw SQL instead of relying on `repos.SchemaName()` (verified empty on the `ForSchoolSchema` path in factory.go — the plan's suggested source would have produced an unqualified table).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking + Rule 1 - Bug] SchemaTablePrefix plugin ignored for `.Table()` queries**
- **Found during:** Task 2 (GREEN — integration test failed with `relation "ai_vectors" does not exist (SQLSTATE 42P01)`)
- **Issue:** The plan's mandated Insert path `repos.TenantDB().Table("ai_vectors")` relies on the SchemaTablePrefix plugin, but GORM v1.31.2's `.Table()` chainable captures the quoted table into `Statement.TableExpr` at call time, and `Statement.QuoteTo` (statement.go:96-103) prefers `TableExpr` over the plugin-mutated `Statement.Table` — so the prefix was silently dropped. Root-caused via debug callbacks (`[after] Table="school_1.ai_vectors"` yet SQL `FROM "ai_vectors"`) and GORM source reading.
- **Fix:** In `schema_db.go` `prefix()`: when `TableExpr` holds a simple quoted identifier (no spaces/parens, `strconv.Unquote` succeeds, no embedded dot), rewrite it to `Quote(schema + "." + name)`. Guards skip aliases, subqueries, and already-qualified tables (`"public"."users"` etc. — unchanged behavior).
- **Files modified:** `backend/internal/database/tenant/schema_db.go`
- **Verification:** Integration test passes (`INSERT INTO "school_1"."ai_vectors"`); `go test ./internal/database/tenant/` passes; `go build ./...` OK; probe confirmed all four tenancy paths resolve.
- **Committed in:** `5167d16` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking + 1 bug, same root cause)
**Impact on plan:** Necessary for the plan's core key-link to function. Strictly-correcting change — the previous behavior silently queried the wrong schema; already-qualified tables are untouched. No scope creep.

## Issues Encountered
- GORM v1.31.2 `.Table()` + plugin interplay (see deviation 1) — the plugin's own docstring (`schemaDB.Table("students").Count(...) // schema-qualified`) promised behavior the build path did not deliver.
- `ForSchoolSchema` does not populate `repos.schemaName`, so `repos.SchemaName()` returns "" — worked around by returning the deterministic validated schema from `tenantFor`.

## User Setup Required
None - no external service configuration required. Integration test self-gates on `PGVECTOR_TEST_DSN` (skips cleanly when unset).

## Next Phase Readiness
- Store is drop-in ready: same method set and collection-string semantics as the Qdrant implementation; RAG pipeline and agents untouched.
- 02-05 (store swap) can proceed: wire `NewPGVectorStore(factory, model, version, chunkingVersion, 1536)` where the Qdrant store is constructed and gate on the `<=>` HNSW path via EXPLAIN.
- Blocker cleared: `.Table()` tenant queries across the codebase now correctly schema-scoped (previously silent mis-scoping risk for future modules).

---
*Phase: 02-pgvector-migration*
*Completed: 2026-08-01*

## Self-Check: PASSED
- FOUND: backend/internal/ai/vector/pgvector.go
- FOUND: backend/internal/ai/vector/pgvector_test.go
- FOUND: 02-04-SUMMARY.md
- FOUND: commit 1e30f9c (RED)
- FOUND: commit 5167d16 (GREEN)
