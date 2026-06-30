# Phase 6: Testing & Validation — Overall Plan

**Status:** Draft
**Dependencies:** Phase 5 (complete)

## Objective

Validate the full multi-tenant database migration through comprehensive integration, security, and load testing. Deliver deployment guides, runbooks, and CI configuration that operations teams can use to manage the system in production. Phase 6 is split into 4 sequential plans executed in order, as each plan depends on the previous plan being stable.

## Execution Order

```
06-01 (Core Infrastructure Tests)
  └── 06-02 (Backup & Recovery Tests) — depends on stable 06-01 patterns
        └── 06-03 (Middleware + Integration Tests) — depends on stable 06-01 + 06-02
              └── 06-04 (Documentation + CI) — depends on passing 06-01..06-03
```

| # | Plan | Focus | Test Type | CI Job | Dependencies |
|---|------|-------|-----------|--------|-------------|
| 06-01 | Core Infrastructure Tests | EncryptionService, ConnectionManager, RepositoryFactory, Config, Errors | Unit (mocked) | `unit-tests` | None |
| 06-02 | Backup & Recovery Tests | BackupService, RestoreService, S3Backup, Local, Queue handlers | Unit (mocked, skip-if-binary) | `unit-tests` | 06-01 |
| 06-03 | Middleware + Integration Tests | Tenant/auth middleware, MigrationService, Cross-tenant isolation, Security | Integration (with services) | `integration-tests` (new) | 06-01, 06-02 |
| 06-04 | Documentation + CI | Deployment guides, runbooks, CI config updates, coverage | N/A (docs + infra) | N/A | 06-01..06-03 |

## Test Patterns (all plans)

- **assert/require**: Use `github.com/stretchr/testify` consistently (assert for non-fatal, require for fatal)
- **mock.Mock**: Hand-written mocks following existing patterns (see `internal/modules/auth/`)
- **t.Parallel**: Enable at function level for independent tests
- **t.Helper**: Mark helper functions
- **t.Skipf**: Skip pg_dump/pg_restore-dependent tests when binary not found: `t.Skipf("pg_dump not found, skipping: %v", err)`
- **gin.CreateTestContext**: Use for middleware tests with `httptest.NewRecorder`
- **go-sqlmock**: Optional for DB-layer tests (ConnectionManager, MigrationService) — not currently in go.mod, consider adding if real DB unavailable
- **miniredis**: Optional for Redis cache tests (TenantResolutionService, rate limiter) — consider for faster tests

## Coverage Target

- Overall project: >= 30% (statement coverage)
- New packages (crypto, tenant, backup, restore, storage): >= 50%
- Critical path (ConnectionManager, EncryptionService, middleware): >= 70%

## Success Criteria

- [ ] All 06-01 test suites pass (EncryptionService, ConnectionManager, RepositoryFactory, Config, Error types)
- [ ] All 06-02 test suites pass (BackupService, RestoreService, S3Backup, Local storage, Queue handlers)
- [ ] All 06-03 test suites pass (Middleware, MigrationService, Cross-tenant isolation, Security)
- [ ] CI pipeline has new `integration-tests` job with postgres/redis services
- [ ] Coverage threshold check (>= 30%) added to CI
- [ ] Deployment guides written for provisioning, migrating, and rolling back schools
- [ ] Runbooks written for DB connection failures, migration failures, backup failures, PITR
- [ ] Total test line count >= 7,500 (increased from ~5,860)

## Risks & Mitigations

- **Risk**: go-sqlmock not in go.mod — **Mitigation**: Write tests using real GORM with in-memory SQLite (via `gorm.io/driver/sqlite`) or add go-sqlmock as dev dependency
- **Risk**: pg_dump/pg_restore not available in CI — **Mitigation**: Use `t.Skipf` pattern for binary-dependent tests; mock the `exec.Command` calls
- **Risk**: miniredis not in go.mod — **Mitigation**: Use real Redis via docker-compose services (already available in CI); add miniredis for faster local iteration
- **Risk**: Integration tests need real DB — **Mitigation**: Use `testcontainers-go` or CI service containers; docker-compose provides postgres:16 and redis:7
