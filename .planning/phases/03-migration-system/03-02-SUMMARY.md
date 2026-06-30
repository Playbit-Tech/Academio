# 03-02: MigrationService

**Status:** Complete
**Completed:** 2026-06-30

## What was built

- `internal/database/tenant/migration_service.go` — `MigrationService` with:

| Method | Description |
|--------|-------------|
| `ApplyCoreMigrations()` | Runs core migrations on shared DB |
| `ApplySchoolMigrations(tenantDB, schoolID)` | Runs school migrations on a tenant's DB |
| `CoreMigrationStatus()` | Returns `[]MigrationStatus` (applied/pending) |
| `SchoolMigrationStatus(tenantDB)` | Returns `[]MigrationStatus` for a tenant |

## Key details

- `MigrationStatus` has `ID` (string) + `Applied` (bool)
- Status preserves migration registration order
- `buildStatusList()` helper compares applied IDs against full migration set
- Uses `ReusableMigrator` under the hood for all migration execution
- No existing files modified — pure extension

## Verification

- `go build ./...` — zero errors
