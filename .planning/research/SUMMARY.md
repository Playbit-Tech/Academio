# Research Summary: Multi-Tenant Database Migration

## Source Material
- `multi_tenant_db_migration_plan.md` — Full 14-week phased plan
- `docs/architecture/2-ARCHITECTURE-OVERVIEW.md` — Architecture reference
- `docs/architecture/3-DATABASE-SCHEMA.md` — Schema reference
- `backend/internal/` — Current codebase analysis

## Current State Analysis

### Existing Multi-Tenant Foundation (Already Working)
- **SchoolID-based row isolation**: Every tenant-scoped table has `school_id` column. `EnforceSchoolID` middleware extracts school_id from JWT and scopes all queries.
- **Tenant configuration**: `TenantResolver` middleware loads plan/features/limits from Redis → DB per request.
- **Clean architecture**: Handler → Service → Repository layers with DI.
- **39 modules**: Across academic, finance, HR, alumni, inventory, pastoral care, etc.
- **Auth**: JWT-based with RBAC via `EnforceRole` middleware. Redis blacklist for token revocation.
- **Config**: Single `DBConfig` with DSN() method, global `database.DB` variable.

### Current Limitations
- Single PostgreSQL database — all schools sharing one DB with `SchoolID` foreign key isolation.
- No database-level isolation — potential for cross-tenant data access issues.
- Limited scalability — shared connection pool, no per-tenant connection tuning.
- No per-tenant backups — cannot restore individual school data independently.
- No credential encryption — DB credentials for per-tenant databases would be plaintext.

## Architecture Implications

### Go/Gin/GORM Stack
- GORM connection: `gorm.Open(postgres.Open(dsn), ...)` with connection pooling (MaxOpenConns, MaxIdleConns, ConnMaxLifetime)
- Current global `database.DB` variable — needs refactoring to support dynamic connections
- Repository pattern: `*gorm.DB` injected via constructor — needs factory pattern for per-tenant DBs

### Key Files to Modify
| File | Impact |
|------|--------|
| `internal/database/postgres.go` | Add DatabaseConnectionManager, keep existing Connect() for core DB |
| `internal/database/models/school.go` | Add database connection fields to School model |
| `internal/config/config.go` | Add multi-DB config (core DB + per-tenant config template) |
| `internal/middleware/schoolid.go` | Enhance to carry tenant DB context |
| `internal/middleware/tenant.go` | Already has TenantResolver pattern — extend for DB resolution |
| `internal/middleware/auth.go` | Enhance JWT claims to carry tenant DB routing info |
| `internal/router/router.go` | Update DI wiring for RepositoryFactory |
| `internal/modules/*/repository.go` | All 39 modules — refactor to use factory pattern |

### Implications for Roadmap

**Phase clustering**: The natural delivery boundaries align with the existing plan:
1. **Foundation** (infrastructure): encryption, schema, connection manager, factory — no user-facing changes, all backend plumbing
2. **Refactoring** (adoption): repositories + services + middleware — the largest effort, modifying 39 modules
3. **Migration** (tooling): migration system for core vs school databases
4. **Auth enhancement** (resolution): tenant resolution from JWT, error handling
5. **Backup/Recovery** (reliability): backup + restore services
6. **Validation** (quality): comprehensive testing + documentation

**Key risk**: Phase 2 is the highest-effort — every module's repository needs to accept tenant DB connections. This is mechanical but touches 39 modules.

**Backward compatibility**: The existing `EnforceSchoolID` and single-DB pattern must continue working during and after migration. The `DatabaseConnectionManager` should fall back to core DB for modules not yet migrated.

**Credential security**: AES-256 encryption for DB passwords stored in the `schools` table is mandatory — never store plaintext database credentials.
