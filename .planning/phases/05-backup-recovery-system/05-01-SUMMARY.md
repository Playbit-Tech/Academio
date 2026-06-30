# 05-01 Summary: BackupService

**Phase:** 5 (backup-recovery-system)  
**Plan:** 01 (Wave 1)  
**Status:** Complete  

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/internal/config/config.go` | Modified | Added `Endpoint` field to `S3Config`; added `S3_ENDPOINT` env loading |
| `backend/pkg/storage/s3_backup.go` | Created | `S3BackupStorage` adapter implementing `Save`, `Delete`, `URL` methods via AWS SDK v2 |
| `backend/internal/backup/errors.go` | Created | Sentinel errors: `ErrSchoolNotFound`, `ErrBackupInProgress`, `ErrRestoreInProgress`, `ErrS3UploadFailed`, `ErrPGDumpFailed` |
| `backend/internal/backup/service.go` | Created | `BackupService` with `CreateTenantBackup` (pg_dump → temp → S3 → metadata → retention) |
| `backend/internal/queue/tasks.go` | Modified | Added `TypeBackupCreate`, `BackupCreatePayload`, `NewBackupCreateTask`, `BackupCreate` handler field |
| `backend/internal/queue/handlers/backup_handler.go` | Created | `BackupTaskHandler` with `HandleBackupCreate` |
| `backend/internal/router/setup.go` | Modified | Wired `BackupService`, backup task handler; conditional init (S3 creds required) |

## Architecture

```
Asynq Task (backup:create)
    ↓
BackupTaskHandler.HandleBackupCreate
    ↓
BackupService.CreateTenantBackup(schoolID)
    ├── Lock check (inProgress map)
    ├── Load SchoolConnection + decrypt password
    ├── Create tenant_backups record (status=running)
    ├── pg_dump -Fc → temp file (30min timeout)
    ├── S3 upload (backups/{schoolID}/{timestamp}/backup-{timestamp}.dump)
    ├── Update record (status=completed)
    └── Enforce retention (keep 14 newest)
```

## Dependencies Added

- `github.com/aws/aws-sdk-go-v2` + config, credentials, service/s3

## Key Decisions Applied

- **D-01**: S3 only — no local fallback
- **D-02**: `Endpoint` field on `S3Config` for MinIO/DO Spaces
- **D-07**: Keep 14 most recent backups per school
- **D-08**: Failed backups marked as `failed`, not deleted

## Verification

- `go build ./...` ✅
- `go vet ./...` ✅
