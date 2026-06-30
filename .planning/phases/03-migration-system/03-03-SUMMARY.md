# 03-03: Tenant Migration Tools (MigrateAllTenants)

**Status:** Complete
**Completed:** 2026-06-30

## What was built

- `MigrationService.MigrateAllTenants(ctx, concurrency)` — parallel tenant migration

| Feature | Detail |
|---------|--------|
| School filtering | Only schools with `database_name` set and `database_status = 'active'` |
| Concurrency | Worker pool via buffered channel semaphore (default 5) |
| Context support | Cancellable — respects `ctx.Err()` mid-migration |
| Reporting | Returns `*MigrationReport` with per-school results |
| Error handling | Per-school isolation — one failure doesn't block others |

## Result types

```go
type MigrationReport struct {
    Total     int
    Succeeded int
    Failed    int
    Skipped   int
    Results   []SchoolMigrationResult
}

type SchoolMigrationResult struct {
    SchoolID   uint
    SchoolName string
    Status     string   // "success", "failed", "skipped"
    Error      string
}
```

## Usage

```go
svc := tenant.NewMigrationService(coreDB, connManager)
report, err := svc.MigrateAllTenants(ctx, 10) // 10 concurrent
```

## Verification

- `go build ./...` — zero errors
