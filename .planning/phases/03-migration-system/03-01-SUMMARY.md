# 03-01: Split Migrations + ReusableMigrator

**Status:** Complete
**Completed:** 2026-06-30

## What was built

- `internal/database/migration/types.go` — Shared `Migration` struct in a cycle-safe package
- `internal/database/migrations/migrator.go` — Exported `ReusableMigrator` with configurable table name, `Run()`, `Rollback()`, `AppliedIDs()`, `PendingIDs()`
- `internal/database/migrations/core/` — 5 core migration files (phase1, auth_rewrite, auth_phase2, multitenant, rbac)
- `internal/database/migrations/school/` — 7 school migration files (phase2-5, core_models, modules, admissions)
- Updated `migrations.go` — Backward-compatible `New(db)` still runs all migrations; new `NewForCore()`, `NewForSchool()`, `CoreMigrations()`, `SchoolMigrations()` functions

## Key details

- Import cycle avoided: `Migration` type lives in `migration` package, re-exported via `type Migration = migration.Migration` alias
- Legacy accessors preserved: `Phase1Migrations()`, `Phase2Migrations()`, etc. all still work
- `migrations.New(db).Run()` unchanged — no `main.go` changes needed
- Core tracking table: `schema_migrations`; school tracking: `tenant_schema_migrations`
- Deleted 12 old flat files from `internal/database/migrations/`

## Verification

- `go build ./...` — zero errors
- All existing tests pass
