# Roadmap: Multi-Tenant Database Migration

## Overview

Transform SchoolCare v2 from single-database row-level isolation (SchoolID scoping) to database-per-tenant architecture. The migration builds on the existing sophisticated multi-tenant foundation — JWT auth, RBAC, EnforceSchoolID middleware, and TenantResolver — and adds dynamic connection management, credential encryption, per-school database provisioning, and enterprise backup/recovery. Six phases executed over 14 weeks, with backward compatibility maintained throughout.

## Phases

- [ ] **Phase 1: Core Database Setup** - Encryption service, schema enhancements, connection manager, and repository factory
- [ ] **Phase 2: Repository Layer Refactoring** - All 39 modules' repositories accept tenant DB connections via factory pattern
- [ ] **Phase 3: Migration System** - Core vs school migration directories and tenant migration tools
- [ ] **Phase 4: Enhanced Auth & Tenant Resolution** - JWT → tenant DB resolution with enhanced error handling
- [ ] **Phase 5: Backup & Recovery System** - Automated backup (pg_dump + S3) and point-in-time restore
- [ ] **Phase 6: Testing & Validation** - Comprehensive integration, load, security testing and documentation

## Phase Details

### Phase 1: Core Database Setup
**Goal**: The foundation for multi-tenant database management is in place — credentials are encrypted, the schools schema supports database-per-tenant, and a connection manager can dynamically resolve and cache per-tenant GORM connections.
**Depends on**: Nothing (first phase)
**Requirements**: GSD-R1, GSD-R2, GSD-R3, GSD-R4
**Success Criteria** (what must be TRUE):
  1. `EncryptionService` can encrypt/decrypt database credentials using AES-256-GCM; encrypted values are safe to store in the schools table
  2. `schools` table has all database connection fields (database_name, database_host, database_port, database_username, database_password_encrypted, database_status, connection_pool_size); `database_connections` and `tenant_backups` tables exist with proper foreign keys
  3. `DatabaseConnectionManager` returns a configured GORM connection for any given school ID within <50ms (cache hit) using `sync.Map`; health checks run periodically and stale connections are evicted
  4. `RepositoryFactory` creates tenant-aware repository instances from a school ID; unimplemented repository types return clear errors
**Plans**: 4 plans

Plans:
- [x] 01-01: EncryptionService (AES-256-GCM encrypt/decrypt)
- [x] 01-02: Schema migration (schools enhancement + new tables)
- [x] 01-03: DatabaseConnectionManager (sync.Map cache, GORM pool, health checks)
- [x] 01-04: RepositoryFactory pattern + core DB wiring
**UI hint**: no

### Phase 2: Repository Layer Refactoring
**Goal**: All 39 module repositories accept tenant database connections via the factory, the service layer injects tenant context, and middleware propagates the resolved tenant DB to downstream handlers.
**Depends on**: Phase 1
**Requirements**: GSD-R5, GSD-R6, GSD-R7
**Success Criteria** (what must be TRUE):
  1. Every module's repository constructor accepts a `*gorm.DB` parameter; repositories are instantiated via `RepositoryFactory` with a school ID, not via direct `New*Repository(coreDB)` calls
  2. Service layer receives tenant context (school ID, tenant DB connection) from the request context and passes it to the repository
  3. Tenant context middleware extracts the school from JWT claims, resolves the tenant DB via `DatabaseConnectionManager`, and stores the connection in the Gin request context before handlers execute
  4. Enhanced auth middleware validates that the school_id in the JWT matches the resolved tenant DB's school_id (cross-check)
  5. All existing SchoolID-based row isolation queries continue working unchanged alongside the new tenant-aware paths
**Plans**: TBD

Plans:
- [x] 02-01: Tenant context middleware + factory accessors
- [x] 02-02: Handler updates (middleware-based, minimal changes)
- [x] 02-03: Router wiring (middleware registration, factory init)
**UI hint**: no

### Phase 3: Migration System
**Goal**: Database migrations are split between core (shared schema) and school (per-tenant schema); a migration service and CLI tool can apply migrations to individual schools or all schools in parallel.
**Depends on**: Phase 2
**Requirements**: GSD-R8, GSD-R9
**Success Criteria** (what must be TRUE):
  1. Two migration directories exist: `migrations/core/` for shared tables (schools, users, roles, tenants) and `migrations/school/` for per-tenant tables (students, teachers, classes, finance, HR, etc.)
  2. `MigrationService.ApplyCoreMigrations()` migrates the core database; `MigrationService.ApplySchoolMigrations(tenantDB)` migrates a single school's database
  3. `MigrateAllTenants()` iterates all active schools in parallel (configurable concurrency), applies school migrations, and reports per-school status (success/failure/reason)
  4. Migration status is tracked per school in the `schools.database_status` field; failed migrations are recorded with error details for retry
  5. Rollback scripts exist for all Phase 1 schema changes
**Plans**: TBD

Plans:
- [x] 03-01: Split migrations into core/ and school/ directories
- [x] 03-02: MigrationService (apply, rollback, status tracking)
- [x] 03-03: Tenant migration tools (MigrateAllTenants, parallel, CLI)
**UI hint**: no

### Phase 4: Enhanced Auth & Tenant Resolution
**Goal**: JWT tokens carry tenant routing information; `TenantResolutionService` resolves a JWT to the correct tenant database with caching; errors are tenant-aware and logging includes school context.
**Depends on**: Phase 3
**Requirements**: GSD-R10, GSD-R11
**Success Criteria** (what must be TRUE):
  1. `TenantResolutionService.ResolveTenantFromToken(token)` validates the JWT, looks up user + school from core DB, checks school status (database_status, subscription_status), gets the tenant DB connection from `DatabaseConnectionManager`, and returns a `TenantContext` with TenantID, SchoolName, DB connection, User, and Permissions
  2. Tenant context is cached in Redis with TTL; subsequent requests from the same user reuse the cached context without hitting the core DB
  3. All API errors returned to clients include tenant-aware error codes (e.g., `TENANT_DISABLED`, `TENANT_DB_UNAVAILABLE`, `SUBSCRIPTION_EXPIRED`)
  4. Structured logs include `school_id`, `request_id`, and `tenant_db_host` for every request; connection failures are logged with school context
**Plans**: TBD

Plans:
- [ ] 04-01: TenantResolutionService (JWT → tenant DB resolution)
- [ ] 04-02: Enhanced error handling + tenant-aware logging
**UI hint**: no

### Phase 5: Backup & Recovery System
**Goal**: Every tenant database is backed up automatically via pg_dump with S3 upload; individual schools can be restored to any backup point with validation.
**Depends on**: Phase 4
**Requirements**: GSD-R12, GSD-R13
**Success Criteria** (what must be TRUE):
  1. `BackupService.CreateTenantBackup(schoolID)` runs pg_dump (custom format), compresses the dump, uploads it to S3 under `backups/{schoolID}/{timestamp}/`, and records metadata in the `tenant_backups` table
  2. Backup scheduling is configurable per school (default: daily at 02:00); backup status is monitored and failed backups are retried with exponential backoff
  3. `RestoreService.RestoreTenantBackup(schoolID, backupID)` downloads the backup from S3, validates the archive checksum, restores to the school's database, and verifies data integrity by running a pre-defined validation query set
  4. Point-in-time recovery is supported by listing available backups for a school; recovery time objective (RTO) < 1 hour and recovery point objective (RPO) < 15 minutes
  5. All backup/restore operations are logged with duration, size, and status; concurrent restore operations are prevented
**Plans**: TBD

Plans:
- [ ] 05-01: BackupService (pg_dump, S3 upload, scheduling)
- [ ] 05-02: RestoreService (point-in-time recovery, validation)
**UI hint**: no

### Phase 6: Testing & Validation
**Goal**: The full migration is validated through comprehensive integration, load, and security testing; operations teams have deployment guides and runbooks.
**Depends on**: Phase 5
**Requirements**: GSD-R14, GSD-R15
**Success Criteria** (what must be TRUE):
  1. Integration test suite covers: tenant DB connection lifecycle, cross-tenant isolation (school A cannot access school B's data), credential encryption/decryption, repository factory for all module types, migration system (core + school), backup/restore workflows
  2. Load test suite validates: 1000+ concurrent tenant connections, <50ms cache-hit connection time, <500ms cache-miss connection time, migration of 100+ schools in parallel completes within 30 minutes
  3. Security test suite validates: AES-256-GCM encryption is FIPS-compliant, no plaintext credentials in logs, no cross-tenant data leakage via connection manager, JWT claims cannot be forged to access another tenant's DB
  4. Deployment guides exist for: provisioning a new school database, migrating an existing school from shared to dedicated DB, rolling back a school migration, backup/restore operations, monitoring and alerting setup
  5. Runbooks exist for: tenant DB connection failures, migration failures, backup failures, point-in-time recovery, scaling connection pools
**Plans**: TBD

Plans:
- [ ] 06-01: Comprehensive integration testing
- [ ] 06-02: Load testing (1000+ concurrent tenants)
- [ ] 06-03: Security testing (encryption, isolation, JWT)
- [ ] 06-04: Documentation + deployment guides
**UI hint**: no

## Progress

**Execution Order:** Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Database Setup | 4/4 | ✅ Complete | 2026-06-29 |
| 2. Repository Layer Refactoring | 3/3 | ✅ Complete | 2026-06-30 |
| 3. Migration System | 3/3 | ✅ Complete | 2026-06-30 |
| 4. Enhanced Auth & Tenant Resolution | 0/1 | Planned    |  |
| 5. Backup & Recovery System | 0/2 | Not started | - |
| 6. Testing & Validation | 0/4 | Not started | - |
