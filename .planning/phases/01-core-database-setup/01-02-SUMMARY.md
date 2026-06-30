# 01-02: Schema Migration (Schools Enhancement + New Tables)

**Status:** Complete
**Completed:** 2026-06-29

## What was built

- `backend/internal/database/migrations/phase_multitenant.go` — 3 raw-SQL migrations
- `backend/internal/database/models/multitenant.go` — 3 models (SchoolConnection, DatabaseConnection, TenantBackup)
- `backend/internal/database/migrations/migrations.go` — registered `MultiTenantMigrations()`

## Migration details

1. **`2026_06_29_000001_enhance_schools_database_columns`**: Adds 7 columns to `schools` table via `ALTER TABLE ADD COLUMN IF NOT EXISTS` (database_name, database_host, database_port, database_username, database_password_encrypted, database_status, connection_pool_size)

2. **`2026_06_29_000002_create_database_connections`**: Creates `database_connections` table with indexes on school_id and status

3. **`2026_06_29_000003_create_tenant_backups`**: Creates `tenant_backups` table with JSONB metadata, indexes on school_id and status

## Model design

- `SchoolConnection`: Read-only projection of `schools` table — only DB connection fields, not GORM-managed (avoids FK-owner issue with Laravel-owned schools table)
- `DatabaseConnection`: Full GORM model for `database_connections` table, `password_encrypted` field tagged `json:"-"` to prevent serialization
- `TenantBackup`: Full GORM model for `tenant_backups` table with JSONB metadata

## Key decisions

- Used raw SQL for all schema changes (schools table is Laravel-owned, AutoMigrate would FK-enforce and fail)
- `ADD COLUMN IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` for idempotency
- `uint` IDs match existing codebase convention
- Rollback functions provided for all 3 migrations
