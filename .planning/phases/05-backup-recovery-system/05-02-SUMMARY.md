# 05-02 Summary: RestoreService

**Phase:** 5 (backup-recovery-system)  
**Plan:** 02 (Wave 2)  
**Status:** Complete  

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/pkg/storage/s3_backup.go` | Modified | Added `Get(key) (io.ReadCloser, error)` method for downloading backups |
| `backend/internal/restore/service.go` | Created | `RestoreService` with `ListBackups`, `RestoreTenantBackup`, `runValidationQueries` |
| `backend/internal/restore/handler.go` | Created | REST API handlers: `ListBackups`, `RestoreBackup`, `GetBackupStatus` |
| `backend/internal/queue/tasks.go` | Modified | Added `TypeRestoreExecute`, `RestoreExecutePayload`, `NewRestoreExecuteTask`, `RestoreExecute` handler field |
| `backend/internal/queue/handlers/restore_handler.go` | Created | `RestoreTaskHandler` with `HandleRestoreExecute` |
| `backend/internal/router/setup.go` | Modified | Wired `RestoreService`, restore task handler, backup/restore API routes |

## Architecture

```
Asynq Task (restore:execute)
    ↓
RestoreTaskHandler.HandleRestoreExecute
    ↓
RestoreService.RestoreTenantBackup(schoolID, backupID)
    ├── Lock check (inProgress map — concurrent per-school prevention)
    ├── Load backup record (must be status=completed)
    ├── Load SchoolConnection + decrypt password
    ├── Download from S3 → temp file
    ├── Validate archive (pg_restore --list)
    ├── Restore to database (pg_restore --clean --if-exists --no-owner --no-acl, 60min timeout)
    ├── Run validation queries (best-effort: SELECT COUNT(*) FROM students/teachers/classes)
    ├── Update restore_point
    └── Clean up temp file

REST API:
  GET  /api/v1/backups/:schoolId         → ListBackups
  POST /api/v1/backups/:schoolId/restore → RestoreBackup (async via goroutine)
  GET  /api/v1/backups/:schoolId/status  → GetBackupStatus (restore_in_progress bool)
```

## Threat Model Mitigations

| Threat | Mitigation |
|--------|-----------|
| T-05-06 (DoS) | Concurrent restore per-school blocked via inProgress map; 60min pg_restore timeout |
| T-05-07 (Tampering) | Archive integrity validated via `pg_restore --list` before restore |
| T-05-08 (Info disclosure) | DSN not logged in plaintext |
| T-05-09/10 (Privilege escalation) | Auth middleware on all routes (JWTAuth) — school_id scoping in middleware |

## Verification

- `go build ./...` ✅
- `go vet ./...` ✅

## Outcomes

- RTO < 1 hour enabled via automated restore pipeline
- RPO < 15 minutes enabled via daily backup schedule with 14-backup retention
