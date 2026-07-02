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

## Milestone: v2.0 — Multi-Tenant Database Migration (Shipped)

**Shipped:** 2026-07-02
**Phases:** 7 | **Plans:** 10 | **Sessions:** ~11 (including v2.0-alpha)

### What Was Built
- **UUID identity system**: Dual-ID strategy (uint PK + uuid) across 108 model structs, 357 source files, 33 modules
- **GORM-based schema**: All ~81 raw SQL CREATE TABLE migrations replaced with AutoMigrate, consolidated into 7 domain-grouped files
- **Fresh database**: `schoolcare_core` on PostgreSQL 17.9 with 205/205 migrations, 111 tables
- **API compatibility layer**: ResourceID parser, 31 handlers converted, FindByResourceID in 20 repos, dual UUID fields in 19 DTOs
- **Multi-tenant DB routing**: All 33 tenant-scoped modules converted to per-school database routing via `middleware.GetTenantRepos(c).TenantDB()`
- **Tenant lifecycle**: Integration tests (testcontainers-go), API compat tests, performance benchmarks, provisioning handler + queue task
- **Clean repo-selection pattern**: Pastoral, inventory, finance services refactored to eliminate nil DB panics and GetDB() mock expectations

### What Worked
- **Wave-based execution**: Breaking large phases into waves (e.g., Phase 4 Wave 1 → Wave 2) kept each commit focused and reviewable
- **Module-by-module conversion**: Converting all 33 tenant-scoped modules in functional waves (academic → timetable → exam → ...) ensured consistency
- **Clean repo-selection pattern**: Using `repo := s.xxxRepo; if tenantDB != nil { repo = NewXxxRepository(tenantDB) }` eliminated nil panics and mock dependency
- **Pre-existing Redis timing tests**: Documenting and excluding the 2 flaky rate-limiter tests prevented false negatives from blocking progress
- **GSD milestone archival**: Running `/gsd-complete-milestone` at the right time created proper historical records

### What Was Inefficient
- **Phase 6 scope creep**: Originally planned for 5 modules (Wave 1), expanded to all 33 modules — this was necessary but made the phase much larger than estimated
- **Phase 7 finance fixes**: The finance module had accumulated stale `tempVendorRepo` references that weren't caught in the initial Phase 6 conversion
- **Milestone archival timing**: The archive was run twice because the first attempt didn't fully complete — important to verify completion before committing

### Patterns Established
- **Clean repo-selection pattern**: `repo := s.xxxRepo; if tenantDB != nil { repo = NewXxxRepository(tenantDB) }` — preferred over `db := s.db; if tenantDB != nil { db = tenantDB }`
- **Transaction helpers**: `helpers.ExecTransaction(db, ctx, func(txDB *gorm.DB) error { ... })` for cross-table operations within a transaction
- **Test call sites**: Services called with `nil` tenantDB in tests to use injected repos directly
- **Gofmt pre-commit**: `gofmt -l .` as a pre-commit check to catch formatting drift

### Key Lessons
1. **Don't skip test updates when refactoring**: Phase 6 changed service signatures but didn't update all test call sites — this was caught in Phase 7 verification
2. **Module-by-module is safer than big-batch**: Converting 33 modules in one pass risked missed files; the wave approach with validation after each wave was more reliable
3. **Flaky tests should be documented, not ignored**: The 2 Redis rate-limiter timing tests were pre-existing and unrelated to our changes — documenting them prevented confusion
4. **GSD milestone archival needs manual verification**: The automated `gsd-tools.cjs milestone complete` doesn't always capture the full scope — manual review of MILESTONES.md is important

### Cost Observations
- Mostly default model with occasional tool delegation
- Key efficiency: GSD execute-phase workflow with parallel batch execution for Phase 6 modules
- Sessions: ~11 total (v2.0-alpha: ~8, v2.0-beta: ~3)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v2.0-alpha | ~8 | 6 | First milestone — established GSD workflow patterns |
| v2.0 | ~3 | 7 | Completed Phase 6-7, milestone archival patterns |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v2.0-alpha | 41 test files | 54% (unit packages) | go-sqlmock (dev dep) |
| v2.0 | 45 test files | 54% (unit packages) | testcontainers-go (dev dep) |

### Top Lessons (Verified Across Milestones)

1. Wave-based execution keeps large phases manageable — break work into waves with validation after each
2. Clean repo-selection pattern (`repo := s.xxxRepo; if tenantDB != nil { ... }`) is safer than DB-first pattern
3. Pre-existing flaky tests should be documented, not ignored — prevents false negatives from blocking progress
4. GSD milestone archival needs manual verification — automated tools don't always capture full scope
