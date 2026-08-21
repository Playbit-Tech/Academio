# Deferred Items — Phase 02 (pgvector-migration)

Out-of-scope discoveries logged during plan execution (per GSD scope boundary rule —
do NOT auto-fix, track for a future owner).

## 1. `cmd/migrate-schemas` queries a nonexistent `database_name` column

- **Found during:** 02-03 Task 2 (applying the `ai_vectors` migration to existing schemas)
- **Issue:** `backend/cmd/migrate-schemas/main.go:58-68` selects `id, name, database_name` from `schools`, but the `schools` table has no `database_name` column → hard failure `ERROR: column "database_name" does not exist (SQLSTATE 42703)`. This is a PRE-EXISTING bug (the column was removed in an earlier schema-per-tenant migration; the CLI was not updated).
- **Impact:** `make migrate-schemas` / `go run ./cmd/migrate-schemas` is broken for ALL invocations. It also only processes schools with `schema_name IS NULL` (legacy dedicated-DB schools), so it was not the right tool for applying pending migrations to already-provisioned schema tenants anyway — that path is `MigrateAllSchemaTenants`/`ApplySchoolMigrationsForSchema` (used in 02-03 via a temporary gitignored runner in `backend/tmp/`).
- **Who should fix:** A maintenance plan touching `cmd/migrate-schemas` (or Phase 7 RET-02 qdrant/cutover sweep that audits migration tooling). Suggested fix: drop `database_name` from the SELECT or make it optional; consider extending the CLI with a `--apply-pending` mode that calls `MigrateAllSchemaTenants`.
- **Why deferred:** Out of scope for PGV-04 (ai_vectors DDL); 02-03 was unblocked via the existing per-schema machinery without modifying the CLI.
