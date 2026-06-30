# Phase 6: Research — Testing & Validation

## Current State

### Existing Test Coverage (24 test files, ~5,860 lines)

| Package | Files | Patterns Used |
|---------|-------|---------------|
| `internal/errors/` | 1 | testify/assert, table-driven, t.Parallel |
| `internal/middleware/` | 4 | gin.CreateTestContext, httptest, router.ServeHTTP, t.Run subtests, t.Skip for Redis |
| `internal/crypto/` | 1 | Raw testing.T (no testify) — basic roundtrip only |
| `internal/ai/rag/` | 1 | testify/assert |
| `internal/modules/auth/` | 2 | testify/mock + mock.Mock, mock.MatchedBy, testify/assert+require, t.Helper |
| `internal/modules/academic/` | 2 | testify/mock |
| `internal/modules/alumni/` | 2 | testify/mock |
| `internal/modules/finance/` | 2 | testify/mock |
| `internal/modules/hr/` | 2 | testify/mock |
| `internal/modules/inventory/` | 2 | testify/mock |
| `internal/modules/pastoral/` | 2 | testify/mock |
| `internal/services/` | 3 | testify/assert, t.Run subtests |

### Existing Non-Go Tests
- **E2E shell script** (`scripts/test_e2e.sh`, 559 lines, 57+ API calls)
- **k6 load tests** (`scripts/k6/`, 9 scripts with smoke + stress profiles)
- **Simple hey-based load test** (`scripts/loadtest.sh`)

### CI Infrastructure
- **ci.yml**: Lint (golangci-lint), Build (go build + vet), Unit Tests (`go test -v -count=1 -race -shuffle=on ./internal/...`), E2E Tests
- **load-test.yml**: k6 smoke (auto on PR), k6 stress (manual dispatch)
- **deploy.yml**: Docker build + K8s deploy

## Interfaces Needing Tests (Phase 1-5 gaps)

### Phase 1 — Core Database Setup
- `internal/crypto/encryption_test.go` — minimal, no testify, no AAD mismatch, no key rotation
- `internal/database/tenant/connection_manager.go` — **ZERO tests** (ConnectionManager, health loop, eviction, caching)
- `internal/database/tenant/factory.go` — **ZERO tests** (RepositoryFactory, ForSchool, TenantRepositories)
- `internal/database/models/` — **ZERO tests**
- `internal/config/config.go` — **ZERO tests**

### Phase 2 — Repository Refactoring
- `internal/middleware/tenant.go` — **ZERO tests** (tenant resolution middleware)
- `internal/middleware/auth.go` — **ZERO tests** (enhanced auth middleware with tenant cross-check)

### Phase 3 — Migration System
- `internal/database/migration/` — **ZERO tests** (MigrationService)
- Migration SQL files exist but unreachable from Go tests

### Phase 4 — Enhanced Auth & Tenant Resolution
- **No integration test** for TenantResolutionService (JWT → tenant DB resolution)
- **No test** for tenant error codes propagation

### Phase 5 — Backup & Recovery
- `internal/backup/service.go` — **ZERO tests** (BackupService, EnforceRetention)
- `internal/restore/service.go` — **ZERO tests** (RestoreService, validation queries)
- `internal/queue/handlers/backup_handler.go` — **ZERO tests**
- `internal/queue/handlers/restore_handler.go` — **ZERO tests**
- `pkg/storage/s3_backup.go` — **ZERO tests**
- `pkg/storage/local.go` — **ZERO tests**

### Cross-Cutting
- `internal/router/setup.go` — **ZERO tests** (DI wiring)
- `internal/router/router.go` — **ZERO tests** (routes, middleware ordering)
- **No cross-tenant isolation integration tests**
- **No security tests** (encryption edge cases, JWT forgery)

## Test Infrastructure Available

### Dependencies in go.mod
- `github.com/stretchr/testify` v1.9.0 — assert, require, mock, suite

### What's NOT in go.mod (candidates)
- `github.com/DATA-DOG/go-sqlmock` — mock SQL driver
- `github.com/testcontainers/testcontainers-go` — real PostgreSQL in tests
- `github.com/alicebob/miniredis/v2` — in-memory Redis
- `github.com/golang/mock` or `github.com/vektra/mockery/v2` — mock generation

### Docker Services Available
- `docker-compose.yml`: postgres:16-alpine, redis:7-alpine, qdrant

## Recommended Plan

### 4 Plans

| Plan | Focus | Components | Priority |
|------|-------|------------|----------|
| 06-01 | Core Infrastructure Tests | EncryptionService, ConnectionManager, RepositoryFactory, Config, Errors | P0 |
| 06-02 | Backup & Recovery Tests | BackupService, RestoreService, S3Backup, Queue handlers, Local storage | P0 |
| 06-03 | Middleware + Integration Tests | Tenant/auth middleware, MigrationService, TenantResolution, Cross-tenant isolation, Security | P1 |
| 06-04 | Documentation + CI | Deployment guides, runbooks, CI config updates, coverage thresholds | P1 |

### Test Patterns to Follow
- **Existing**: testify/assert+require, mock.Mock, t.Parallel, t.Helper, gin.CreateTestContext, httptest
- **New (optional)**: go-sqlmock for DB-layer tests, miniredis for Redis cache tests
- **Skip condition**: Use `t.Skipf` pattern for pg_dump/S3-dependent tests
