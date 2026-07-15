# Database Architecture: Multi-DB → Schema-Per-Tenant Migration

> **Objective**: Replace the current one-database-per-tenant architecture with a single PostgreSQL database using one schema per tenant, enabling real foreign keys across shared/tenant tables and eliminating connection management complexity.
>
> **Current State**: 1 shared database (`academio`) + N tenant databases (`academio_tenant_1`, `academio_tenant_2`, …) — no cross-DB foreign keys possible.
>
> **Target State**: 1 database with `public` schema for shared tables + `school_{id}` schemas for tenant tables — real FK constraints across schemas.
>
> **Risk Level**: HIGH — core infrastructure change with zero-downtime requirement.
> **Total Effort**: ~200-280 engineering hours.

---

## Architecture Comparison

| Concern | Current (Multi-DB) | Target (Schema-Per-Tenant) |
|---|---|---|
| **Foreign keys** | Impossible across shared/tenant DBs. Workaround: app-level referential integrity. | Real FK constraints: `public.users.id → school_1.students.user_id` |
| **Connection management** | One `*gorm.DB` pool per school (N pools). `ConnectionManager` with LRU cache + health goroutine. | Single pool for the whole database. `SET search_path TO school_{id}` per request. |
| **Provisioning** | `CREATE DATABASE` + run all migrations + store encrypted DSN on school record. Async via asynq. | `CREATE SCHEMA school_{id}` + run migrations on schema. Near-instant. |
| **Query complexity** | Separate DB handles; joins across shared/tenant require 2 queries + app-level merge. | Single connection; joins work naturally with schema-qualified or search_path tables. |
| **Backup/restore** | Per-DB `pg_dump` per tenant + shared DB. Complex orchestration. | Single `pg_dump` of the whole database. Simpler. |
| **Connection pool** | 20 conns × N schools = 20N connections. High overhead at scale. | `MaxOpenConns` is total for the whole app. Much lower overhead. |
| **Connection string** | Per-school encrypted DSN stored in `schools.connection_string`. | One DSN for everything. No encryption needed for per-school DB credentials. |

---

## Current Architecture (in detail)

### Database Split
- **Shared DB** (`academio` — `public` schema):
  - `users`, `schools`, `roles`, `role_user`, `tenants`, `tenant_connections`
  - Auth tokens, avatar, s3_path, totp_settings, validation_tokens, uuid_columns
  - `audit_logs` (maybe — check)

- **Per-Tenant DB** (`academio_tenant_{id}` — default `public` schema):
  - `user_infos`, `subjects`, `levels`, `curriculums`, `assessments`, `sessions`
  - `students`, `teachers`, `student_parents`, `grade_items`, `scores`, `results`
  - `timetables`, `attendance` records
  - CBA, admissions, communication, LMS, finance, HR, alumni tables
  - Every table that references `user_id` cannot have FK to `public.users`

### Connection Flow
1. Request arrives → JWT auth resolves `school_id` from token claims
2. `TenantDBResolver` middleware calls `RepositoryFactory.ForSchool(ctx, schoolID)`
3. `ForSchool` calls `ConnectionManager.GetTenantDB(ctx, schoolID)`
4. `GetTenantDB` looks up the encrypted DSN from core DB → decrypts → opens a new `*gorm.DB` pool (or returns cached one)
5. Each handler or repository calls `middleware.GetTenantDB(c)` to get the connection
6. Cross-DB queries (e.g. "find all students for user X") require: query users in shared DB → resolve user_infos in tenant DB

### Provisioning Flow
1. Admin creates school → record inserted in `schools` table with `database_status = 'pending'`
2. Async asynq task triggers `ProvisioningService.ProvisionSchool()`
3. Generates DB name `academio_tenant_{schoolID}`
4. `CREATE DATABASE academio_tenant_{schoolID}` via raw SQL
5. Encrypts connection details → stores on school record
6. Connects to new DB via ConnectionManager → runs school migrations
7. Seeds defaults (levels, subjects, grade items)
8. Sets `database_status = 'active'`

### Key Pain Points
- **No FKs across shared/tenant boundary** — `students.user_id` can't FK to `users.id`. Bug: students can reference non-existent users.
- **Connection pool explosion** — 20 conns/school × 100 schools = 2000 connections just for tenant DBs.
- **Complex provisioning** — async, error-prone, slow (CREATE DATABASE blocks).
- **No JOINs across domains** — e.g. "list all students with their user emails" needs 2 queries + app merge.
- **Encrypted DSN storage** — adds crypto dependency, rotation complexity, and a failure point.
- **Backup complexity** — must backup 1+N databases separately and ensure consistency.

---

## Target Architecture

### Single Database with Schemas

```
Database: academio
├── public schema (shared tables — was core DB)
│   ├── users
│   ├── schools
│   ├── roles, role_user
│   ├── tenants, tenant_connections
│   ├── auth_tokens, avatar, s3_path, totp_settings, validation_tokens
│   └── uuid_columns
│
├── school_1 schema (tenant 1 — was academio_tenant_1)
│   ├── user_infos           ──┐
│   ├── students              │  ALL have real FK to public.users.id
│   ├── teachers              │
│   ├── subjects, levels     ──┘
│   ├── curriculums, assessments, sessions
│   ├── grade_items, scores, results
│   ├── timetables, attendance
│   ├── cba_*, admissions_*, communication_*
│   ├── lms_*, finance_*, hr_*, alumni_*
│   └── ...all current tenant tables
│
├── school_2 schema (tenant 2)
│   └── ...same structure as school_1
│
└── school_N schema (tenant N)
```

### Connection Flow (simplified)

```
1. Request arrives → JWT auth resolves school_id
2. Tenant middleware: get `*gorm.DB` (single shared pool)
3. Schema resolution:
   a. Call `db.Set("search_path", "school_{id},public")` — or use a session-level SET
   b. Or: use a GORM callback that prefixes all queries with `SET search_path TO school_{id}, public;`
4. All queries now automatically hit the correct schema
5. No per-school connection pool, no caching, no DSN lookup
```

### Provisioning Flow (simplified)

```
1. Admin creates school → record in schools
2. Sync task: `CREATE SCHEMA IF NOT EXISTS school_{id};`
3. Run migrations with search_path = `school_{id}`
4. Set `database_status = 'active'` — near-instant
```

---

## Migration Strategy

### Guiding Principles
1. **Zero downtime** — old and new paths coexist during migration
2. **No data loss** — all existing tenant DBs preserved; migrated in-place or scripted
3. **Backward compatibility** — `GetTenantDB()` and `GetTenantRepos()` continue working during transition
4. **Rollback capability** — every step reversible until the cutover

### Approach: Two-Phase Migration

#### Phase 1: Schema Creation & Dual-Write (Parallel Running)
- Create schemas in the shared DB mirroring each existing tenant DB
- Run all existing tenant migrations into the schemas (using `search_path`)
- Implement a **dual-write interceptor** that writes to both the old tenant DB and the new schema
- All reads still come from old tenant DBs (safe, unchanged path)
- Verification: compare row counts between old DBs and new schemas

#### Phase 2: Read Migration & Cutover
- Switch reads to the new schema (configurable per-school for gradual rollout)
- Remove dual-write interceptor
- Decommission old tenant DB connections
- Drop `ConnectionManager`, `RepositoryFactory` multi-DB logic, encrypted DSN code
- Drop old per-tenant databases (after verification + backup)

---

## Phase Breakdown

### Phase 0: Foundation (40-50 hrs)

**Goal**: Prepare the codebase for schema-based multi-tenancy without changing behavior.

| ID | Task | Description | Files | Verification |
|---|---|---|---|---|
| 0.1 | Add `schema` field to school model | Add `schema_name` column (default `school_{id}`) to `schools` table. Nullable; `NULL` = legacy per-DB school. | `models/school.go`, core migration | `go build ./...` |
| 0.2 | Create schema-aware GORM connection | Build a `SchemaDB` wrapper that sets `search_path` on a shared pool. Single `*gorm.DB` with session config. Single `MaxOpenConns` pool. | `database/tenant/schema_db.go` | Unit test: query in `school_1` returns only school_1 data |
| 0.3 | Add schema-aware migration runner | Modify `MigrationService` to run migrations against a schema (not a separate database). Accept `schemaName` parameter, `SET search_path TO schema_name` + run migrations. | `database/tenant/migration_service.go` | Existing school migration tests pass |
| 0.4 | Update provisioning service | `ProvisionSchool` alternative path: `CREATE SCHEMA school_{id}` (instead of `CREATE DATABASE`). Mark `database_status = 'active'` after schema migrations. Keep old `CREATE DATABASE` path for backward compat. | `database/tenant/provisioning.go` | New school provisions via schema |
| 0.5 | Add `schema_name` to `TenantContext` | Include `schema_name` in the resolved tenant context. `TenantResolutionService` populates it from the school record. | `database/tenant/tenant_context.go`, `resolution_service.go` | `go vet ./...` |
| 0.6 | Add schema-aware `GetTenantDB` path | In `TenantDBResolver` middleware: if school has a `schema_name`, return a single shared pool connection with `search_path` set — skipping the per-school DSN lookup. Keep fallback to `ConnectionManager` for legacy schools. | `middleware/tenant.go`, `database/tenant/factory.go` | Integration test: request with schema school returns correct data |
| 0.7 | Benchmark connection pool | Measure current connection count with 1 school, 5 schools, 20 schools. Establish baseline for Phase 3 cleanup. | N/A (script) | Document baseline metrics |

### Phase 1: Schema Creation & Data Migration (60-80 hrs)

**Goal**: Create schemas for all existing tenant databases, copy data into them, verify correctness.

| ID | Task | Description | Verification |
|---|---|---|---|
| 1.1 | Build schema migration CLI command | `go run cmd/migrate-schemas/main.go` — iterates all schools with `database_status = 'active'`, creates `school_{id}` schema, runs migrations. | Dry-run mode lists schools without creating schemas. |
| 1.2 | Build data copy CLI command | `go run cmd/copy-tenant-data/main.go` — for each school, reads from old tenant DB, writes to new schema. Table-by-table with progress. | Row counts match between old DB and new schema. |
| 1.3 | Build verification command | Auto-verify row counts per table, check for orphaned FKs (records in new schema that reference non-existent `public.users.id`). | Zero orphan violations. |
| 1.4 | Run migration for all production schools | Execute schema creation + data copy + verification. | All schools verified. Report generated. |
| 1.5 | Build dual-write shim | For each repository's `Create`/`Update` method: write to both old tenant DB and new schema. Transactional? Best-effort (log errors). Configurable per-school. | Dual writes don't slow down critical path. |
| 1.6 | Deploy dual-write | Release the dual-write shim to production. All new data flows to both old DB and new schema. | Monitor error logs for dual-write failures. |

### Phase 2: Read Cutover (40-50 hrs)

**Goal**: Switch all reads to the new schema, verify correctness, keep dual-write for safety.

| ID | Task | Description | Verification |
|---|---|---|---|
| 2.1 | Add read-source toggle per school | `read_source` field: `"legacy"` (old tenant DB) or `"schema"` (new schema). Controlled per-school for gradual rollout. | Toggle per school, verify correct data returned. |
| 2.2 | Roll out read migration — pilot schools | Select 2-3 low-traffic schools, switch reads to schema. Monitor error rates, latency, data freshness. | Zero regressions. |
| 2.3 | Roll out read migration — all schools | Gradually switch all schools to schema reads. Monitor closely. | All schools reading from schema. |
| 2.4 | Disable dual-write | Remove dual-write shim after verifying schema is getting all writes. | All data writes go to schema only. |
| 2.5 | Add FK constraints | Alter all tenant tables to add real FK constraints to `public.users`, `public.schools`, etc. | `ALTER TABLE ... ADD FOREIGN KEY` succeeds. |

### Phase 3: Cleanup & Decommission (40-60 hrs)

**Goal**: Remove all legacy multi-DB code, drop old databases, simplify the codebase.

| ID | Task | Description | Files | Verification |
|---|---|---|---|---|
| 3.1 | Remove `ConnectionManager` | Delete connection caching, health loop, per-school DSN management. Replace all callers with single pool + schema resolution. | `database/tenant/connection_manager.go` | `go build ./...` |
| 3.2 | Remove encrypted DSN code | Delete DSN encryption, `crypto.Service` dependency in tenant package, `connection_string` field from school model. | `database/tenant/config.go`, `crypto/*` | No encrypted DSNs needed. |
| 3.3 | Simplify `RepositoryFactory` | `ForSchool()` sets search path on shared pool, never calls `GetTenantDB()`. Return single-pool `TenantRepositories`. | `database/tenant/factory.go` | `go vet ./...` |
| 3.4 | Update `middleware.GetTenantDB()` | Always returns shared pool with schema set. Remove `GetTenantContext()` fallback. | `middleware/tenant.go` | All handlers still get correct DB. |
| 3.5 | Simplify `TenantResolutionService` | Remove `connManager` dependency. No more per-school DSN lookup. | `database/tenant/resolution_service.go` | All tests pass. |
| 3.6 | Remove `ProvisioningService` async complexity | `ProvisionSchool` becomes synchronous (schema creation is instant). Remove asynq task, polling loop, `database_status` state machine. | `database/tenant/provisioning.go` | School creation completes immediately. |
| 3.7 | Drop old tenant databases | For each school, `DROP DATABASE IF EXISTS academio_tenant_{id}` after backup + verification. | DB admin script | `\l` in psql shows no `academio_tenant_*` databases. |
| 3.8 | Remove per-school `DBConfig` | Delete `DBConfig` struct, `DSN()` method, `ProvisiningConfig.DatabaseHost/Port/Username/Password`. | `database/tenant/config.go` | Compiles clean. |
| 3.9 | Simplify `factory_test.go`, `connection_manager_test.go`, `isolation_test.go` | Update tests to work with schema-based isolation instead of separate DBs. | `database/tenant/*_test.go` | All tests pass. |
| 3.10 | Remove `migration_service.go` dual-DB logic | Migration runner works on a schema, not a separate DB connection. | `database/tenant/migration_service.go` | All migration tests pass. |
| 3.11 | Clean up `AGENTS.md` | Remove multi-DB warnings, tenant-DB-vs-shared-DB decision trees. Simplify the mental model. | `AGENTS.md` | Documentation matches architecture. |

### Phase 4: Polish & Foreign Key Audit (20-40 hrs)

**Goal**: Add real FK constraints everywhere, surface and fix any orphaned data, remove workaround code.

| ID | Task | Description | Verification |
|---|---|---|---|
| 4.1 | Audit all model FK relationships | For each model in `database/models/`, verify FK targets exist in the correct schema. | `students.user_id → public.users.id`, etc. |
| 4.2 | Add FK migration | Generate `ALTER TABLE` statements for all tenant tables referencing shared tables. Run after data cleanup. | `\d+ school_1.students` shows FK constraint. |
| 4.3 | Fix GORM model tags | Add `constraint:OnUpdate:CASCADE,OnDelete:SET NULL` tags to all FK fields in models. | GORM AutoMigrate adds constraints. |
| 4.4 | Remove app-level FK workarounds | Delete any manual referential integrity checks in service code that existed because of the DB separation. | Review each module for orphan-handling code. |
| 4.5 | Migrate `user_infos` to proper FK | `user_infos.user_id` can now have a real FK to `public.users.id`. Add constraint. | FK added successfully. |
| 4.6 | Simplify `CreateUserWithChecks` | The advisory-lock-based user creation was partly needed because of the multi-DB split. Simplify if possible. | Auth tests pass. |

---

## File Change Inventory

### Files to Create
- `database/tenant/schema_db.go` — single-pool schema-aware DB wrapper
- `cmd/migrate-schemas/main.go` — schema creation CLI
- `cmd/copy-tenant-data/main.go` — data copy CLI
- `docs/plans/DB-SCHEMA-MIGRATION.md` — this plan

### Files to Modify

**Phase 0:**
- `backend/internal/database/models/school.go` — add `SchemaName` field
- `backend/internal/database/migrations/core/` — add `schema_name` column migration
- `backend/internal/database/tenant/migration_service.go` — schema-aware runner
- `backend/internal/database/tenant/provisioning.go` — `CREATE SCHEMA` path
- `backend/internal/database/tenant/tenant_context.go` — add `SchemaName`
- `backend/internal/database/tenant/resolution_service.go` — populate `SchemaName`
- `backend/internal/middleware/tenant.go` — schema-aware `GetTenantDB`
- `backend/internal/database/tenant/factory.go` — schema-aware `ForSchool`

**Phase 3 (deletions):**
- `backend/internal/database/tenant/connection_manager.go` — **DELETE**
- `backend/internal/database/tenant/connection_manager_test.go` — **DELETE** (or rewrite as schema isolation test)
- `backend/internal/database/tenant/config.go` — **DELETE** or drastically simplify
- `backend/internal/database/tenant/isolation_test.go` — rewrite
- `backend/internal/crypto/` — may no longer need tenant DSN encryption code
- `backend/internal/database/migrations/core/tenant_connections.go` — may simplify

**All Phases:**
- `backend/internal/database/tenant/factory_test.go`
- `backend/internal/modules/*/handler.go` — simplify if they do explicit DB switching
- `backend/internal/modules/*/service.go` — simplify cross-DB app-level joins

---

## Sample Code: Schema-Aware DB

```go
// database/tenant/schema_db.go

package tenant

import (
 "context"
 "fmt"
 "gorm.io/gorm"
)

// SchemaDB wraps a shared *gorm.DB pool with per-request schema resolution.
// It uses SET search_path to route queries to the correct tenant schema.
type SchemaDB struct {
 pool *gorm.DB // single shared connection pool
}

// NewSchemaDB creates a SchemaDB backed by the given pool.
func NewSchemaDB(pool *gorm.DB) *SchemaDB {
 return &SchemaDB{pool: pool}
}

// ForSchema returns a *gorm.DB session with search_path set to the given schema.
// All queries on this session will hit the tenant schema + public schema.
func (s *SchemaDB) ForSchema(schemaName string) *gorm.DB {
 return s.pool.Session(&gorm.Session{
  Context: context.WithValue(
   context.Background(),
   "search_path",
   fmt.Sprintf("%s,public", schemaName),
  ),
 }).Exec(fmt.Sprintf("SET search_path TO %s,public", schemaName))
}

// ForSchool returns a *gorm.DB for the given school's schema.
func (s *SchemaDB) ForSchool(schoolID uint) (*gorm.DB, error) {
 schemaName := fmt.Sprintf("school_%d", schoolID)
 return s.ForSchema(schemaName), nil
}
```

### Example: Adding FK constraint

```sql
-- Before (multi-DB): No FK possible
CREATE TABLE school_1.students (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- no FK to public.users!
    ...
);

-- After (schema-per-tenant): Real FK constraint
ALTER TABLE school_1.students
    ADD CONSTRAINT fk_students_user_id
    FOREIGN KEY (user_id)
    REFERENCES public.users(id)
    ON DELETE CASCADE;
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Data copy misses rows | Low | High | Verify row counts per table; checksum sample rows; test with production data |
| Dual-write inconsistency | Medium | Medium | Log errors, alert on divergence, reconciliation script |
| FK constraint failures on existing data | Medium | Medium | Audit step (1.3) catches orphans before adding constraints |
| Schema name collision | Low | High | Prefix with `school_` + ID; validate with regex `^school_\d+$` |
| Rollback complexity | Low | Medium | Keep old tenant DBs untouched until Phase 3; toggle per school |
| Performance regression with search_path | Low | Medium | Benchmark before/after; GORM session pooling overhead is negligible |
| Connection pooling changes cause latency | Low | Medium | Keep `MaxOpenConns` same as current per-DB pool total; monitor |

---

## Migration Checklist

### Pre-Migration
- [ ] Backup all existing tenant databases
- [ ] Record current row counts per table per school
- [ ] Audit current FK orphanage (records referencing non-existent users)
- [ ] Deploy Phase 0 code changes (schema-aware infrastructure)
- [ ] Run benchmark (0.7)

### Migration Execution
- [ ] Run data migration for all schools (1.1-1.4)
- [ ] Verify all schools — row counts match
- [ ] Deploy dual-write (1.5-1.6)
- [ ] Switch pilot schools to schema reads (2.2)
- [ ] Switch all schools to schema reads (2.3)
- [ ] Disable dual-write (2.4)
- [ ] Add FK constraints (2.5)

### Post-Migration
- [ ] Remove legacy ConnectionManager (3.1)
- [ ] Remove encrypted DSN code (3.2)
- [ ] Simplify RepositoryFactory (3.3)
- [ ] Update middleware (3.4)
- [ ] Simplify TenantResolutionService (3.5)
- [ ] Simplify provisioning (3.6)
- [ ] Drop old tenant databases after verification (3.7)
- [ ] Clean up config (3.8-3.10)
- [ ] Update AGENTS.md and developer documentation (3.11)
- [ ] Run full FK audit (4.1-4.6)
- [ ] Run full integration test suite
- [ ] Monitor for 1 week post-cutover

---

## Summary

This migration eliminates the single biggest architectural constraint in the current system — the inability to use foreign keys across shared and tenant data. The result is a simpler, faster, and more maintainable codebase:

- **Before**: 2 query patterns + app-level joins + N connection pools + encrypted DSNs + async provisioning
- **After**: 1 query pattern + real FK joins + 1 connection pool + no encryption needed + sync provisioning

The phased approach ensures zero downtime: old paths stay live until new paths are verified, and every step is reversible.
