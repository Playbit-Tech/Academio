# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.0-alpha — Multi-Tenant Database Migration

**Shipped:** 2026-06-30
**Phases:** 6 | **Plans:** 15 | **Sessions:** ~8

### What Was Built
- **Multi-tenant infrastructure**: AES-256-GCM encrypted DB credentials, connection manager with sync.Map caching and health loops, repository factory pattern for all 39 modules
- **UUID identity system**: Dual-ID strategy (uint PK + uuid) through BaseModel, JWT tokens (schoolUUID + userUUID), auth middleware, and repository lookup methods
- **Migration system**: Core/school migration directories, ReusableMigrator with configurable table name, MigrateAllTenants with parallel worker pools
- **Auth & tenant resolution**: TenantResolutionService with Redis caching (5-min TTL), school UUID enforcement middleware, 5 tenant error codes
- **Backup & recovery**: pg_dump → S3 pipeline via Asynq workers, restore with validation queries, 14-backup retention policy
- **Testing & CI**: 41 test files (crypto security, backup/restore, middleware, tenant isolation, migration service), GitHub Actions CI with coverage enforcement, deployment runbooks

### What Worked
- **GSD workflow with wave-based execution**: Breaking Phase 2 into 2 waves (UUID Auth Flow → Core Repo Methods) kept each commit focused and reviewable
- **go-sqlmock for DB-layer tests**: Allowed testing backup/restore/migration service logic without real PostgreSQL, making tests fast and CI-friendly
- **ReusableMigrator extraction**: The refactored migrator with configurable table name was clean and testable, and the backward compatibility through `migrations.New(db)` meant zero main.go changes
- **Dual-ID strategy from the start**: Adding `uuid` columns alongside existing `uint` PKs avoided breaking changes while enabling new UUID-based code paths
- **Test coverage by concerns**: Splitting tests into crypto → backup/restore → middleware → tenant isolation → migration service let each layer be validated independently

### What Was Inefficient
- **Race condition hunting in middleware tests**: Pre-existing race conditions in parallel test execution cost extra debug cycles — these were pre-existing, not introduced by new code
- **go-sqlmock unexpected query noise**: The MigrateAllTenants test that exercises the full migration path logs several "unexpected query" warnings from the mock DB, which is noisy but correctly handled
- **S3 retry timeouts in backup tests**: Using an actual TCP port (127.0.0.1:9) for S3 error path testing triggers AWS SDK retries making the retention test take ~5s

### Patterns Established
- **Table-driven middleware tests** using `gin.CreateTestContext` + `httptest.NewRecorder`
- **Pre-populated ConnectionManager clients** for tenant isolation tests (avoids needing real Postgres)
- **Per-school inProgress maps** for concurrent backup/restore prevention
- **Security test patterns**: nonce uniqueness, AAD tampering, special chars roundtrips, large payload validation
- **GSD execution flow**: Plan → Research → Summaries → Verify → Complete with atomic commits per plan

### Key Lessons
1. Start with the migration files split BEFORE building the MigrationService — the ReusableMigrator extraction was a clean dependency inversion
2. go-sqlmock works well for GORM but unexpected SQL queries from GORM internals require either broader expectations or accepting the noise
3. CI integration tests with Postgres service containers are easy to set up but the `-tags=integration` convention must be consistently enforced from day one
4. Parallel tenant migration requires careful context cancellation propagation — the worker pool pattern with buffered channels worked well

### Cost Observations
- Mostly default model with occasional tool delegation
- Key efficiency: GSD execute-phase workflow with parallel batch execution
- Sessions: ~8 across the full milestone

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v2.0-alpha | ~8 | 6 | First milestone — established GSD workflow patterns |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v2.0-alpha | 41 test files | 54% (unit packages) | go-sqlmock (dev dep) |

### Top Lessons (Verified Across Milestones)

1. *First milestone — pattern observation pending next milestone*
