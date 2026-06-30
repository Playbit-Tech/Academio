# Phase 5: Backup & Recovery System — Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated pg_dump-based backup of every tenant database to S3 (S3-compatible storage) with point-in-time restore capability. Includes scheduled backups via the existing Asynq queue, retention management (keep 14 most recent per school), and restore validation.

Does NOT include: migration rollback automation, schema comparison tools, or multi-region replication — those are separate concerns.

</domain>

<decisions>
## Implementation Decisions

### Storage Target
- **D-01:** S3 only (primary storage). No local filesystem fallback.
- **D-02:** Add `Endpoint` field to `S3Config` for S3-compatible stores (MinIO, DigitalOcean Spaces, etc.).
- **D-03:** Use existing `storage.Driver` interface or create a dedicated `S3BackupStorage` — planner decides based on pg_dump output handling.

### Scheduling
- **D-04:** Use Asynq queue (existing infrastructure) for periodic backup scheduling.
- **D-05:** Backups enqueued as recurring Asynq tasks. Configurable interval (default: daily).
- **D-06:** No per-school scheduling granularity in this phase — same schedule applies to all active tenant databases.

### Retention & Cleanup
- **D-07:** Keep 14 most recent backups per school. Auto-delete oldest on new successful backup.
- **D-08:** Mark backups as `failed` instead of deleting on pg_dump errors. Failed backups count towards retention limit.

### the agent's Discretion
- **pg_dump strategy** — planner may choose `os/exec`, shell wrapper, or Go library. Evaluate connection string extraction from `ConnectionManager` and choose the simplest reliable approach.
- **Compression format** — pg_dump custom format (built-in compression) is the default. Planner may choose differently if performance testing shows issues.
- **Restore validation** — at minimum: verify backup file exists + run `pg_restore --list` to check archive integrity. Planner may add row-count or sample-query checks.
- **Error handling** — implement retry with exponential backoff for transient failures (S3 timeout, pg_dump connection drop). Hard failures (missing tenant DB, corrupt backup) should alert via existing notification channels.

### Folded Todos
None — no backlog items were folded into this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Models & Schema
- `backend/internal/database/models/multitenant.go` — `TenantBackup` model already defined (SchoolID, BackupName, BackupPath, Size, Status, RestorePoint)
- `backend/internal/database/migrations/core/multitenant.go` — `tenant_backups` table creation migration (Phase 1)

### Storage Infrastructure
- `backend/internal/config/config.go` — `S3Config` (add `Endpoint` field) and `StorageConfig`
- `backend/pkg/storage/local.go` — `Driver` interface (Save, Delete, URL) for reference pattern

### Scheduling Infrastructure
- `backend/internal/queue/` — Asynq client, worker, task handlers (existing patterns to follow)

### Requirements
- `.planning/REQUIREMENTS.md` — GSD-R12 (BackupService), GSD-R13 (RestoreService)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TenantBackup` model — already defined with all needed fields
- `tenant_backups` table — already migrated in core migrations
- Asynq queue system — client, worker, and task handler patterns exist
- `ConnectionManager.GetConnection(schoolID)` — resolves tenant DB connections for pg_dump
- `S3Config` — already has Region, Bucket, AccessKey, SecretKey (needs Endpoint)

### Established Patterns
- Background task handlers: `backend/internal/queue/handlers/` — handler registered via `queue.RegisterTaskHandlers()`
- `gorm.DB` connection access via `*sql.DB` for pg_dump connection strings
- Config is loaded from env vars in `config.go`

### Integration Points
- New S3 backup client needs to be initialized in `setup.go` (alongside existing storage init)
- Backup/restore task handlers registered in existing Asynq mux
- `TenantBackup` DB operations via GORM (core DB, not tenant DB — backup metadata is global)
- API endpoints for manual backup trigger and restore (Phase 5 scope includes API? planner decides)

</code_context>

<specifics>
## Specific Ideas

- pg_dump should use the connection string (host, port, dbname, user, password) extracted from `ConnectionManager` — not re-derive from config
- S3 key structure: `backups/{school_id}/{timestamp}/{dump_name}.dump`
- Each tenant backup should be a single pg_dump custom-format file (`.dump`) — not split files
- Restore verification: at minimum check `pg_restore --list` exit code before marking restore as successful

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-backup-recovery-system*
*Context gathered: 2026-06-30*
