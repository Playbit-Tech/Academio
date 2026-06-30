# Phase 3 — Migration System Plan

## Goal

Split the flat migration system into core/school directories, extract a reusable migrator, and build a MigrationService that can apply school migrations to all tenants in parallel.

**Depends on**: Phase 1 (ConnectionManager, EncryptionService)
**Estimated waves**: 3

---

## Wave 1: Extract ReusableMigrator + Core/School Migration Files

### What

1. Rename existing `migrator` struct to `ReusableMigrator` (exported) with configurable table name
2. Create `internal/database/migrations/migrator.go` with the refactored code
3. Create `internal/database/migrations/core/core.go` — all core migration definitions
4. Create `internal/database/migrations/school/school.go` — all school migration definitions
5. Update `migrations.New(db)` to use both (backward compatible)

### Files to create

- `internal/database/migrations/migrator.go` — Refactored `ReusableMigrator`
- `internal/database/migrations/core/core.go` — Core migrations
- `internal/database/migrations/school/school.go` — School migrations

### Files to modify

- `internal/database/migrations/migrations.go` — Use `ReusableMigrator` inside; keep `New(db)` working

### Verification

- `go build ./...` — zero errors
- `go test ./internal/database/migrations/...` — pass (or no tests)

---

## Wave 2: MigrationService

### What

1. Create `internal/database/tenant/migration_service.go` with the fully-featured MigrationService
2. `ApplyCoreMigrations()` — runs core migrator on core DB
3. `ApplySchoolMigrations(tenantDB, schoolID)` — runs school migrator on a single tenant DB
4. `GetCoreStatus()` / `GetSchoolStatus(tenantDB)` — lists applied/pending migrations

### Files to create

- `internal/database/tenant/migration_service.go` — MigrationService

### Files to modify

- (none — extension, no changes to existing files)

### Verification

- `go build ./...` — zero errors
- Unit tests pass

---

## Wave 3: Tenant Migration Tools (MigrateAllTenants)

### What

1. `MigrateAllTenants(ctx, concurrency)` — iterates all active schools from core DB
2. For each school: gets tenant DB via `ConnectionManager.GetTenantDB()`, applies school migrations
3. Uses worker pool pattern (configurable concurrency, default 5)
4. Returns `MigrationReport` with per-school status
5. Respects school status: only migrates schools with `database_status = 'active'`

### Files to modify

- `internal/database/tenant/migration_service.go` — Add `MigrateAllTenants` + helpers

### Verification

- `go build ./...` — zero errors
- Unit tests for MigrateAllTenants logic (mocked ConnectionManager)

---

## Success Criteria

1. `ReusableMigrator` can run any `[]Migration` on any `*gorm.DB` with any tracking table name
2. `migrations.New(db).Run()` continues to work without changes to `main.go`
3. `MigrationService` correctly applies core migrations once and school migrations per-tenant
4. `MigrateAllTenants` runs in parallel with configurable concurrency, reports per-school results
5. All existing tests pass, no behavioral changes to existing migration flow

## Rollback

If Wave 1 breaks existing migration behavior: the `ReusableMigrator` is a mechanical refactor of the same logic — just revert the file changes. `migrations.New(db)` still runs the same migrations in the same order.
