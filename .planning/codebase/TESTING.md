# Testing

**Analysis Date:** 2026-07-18

---

## Backend Testing

### Framework & Tools

| Tool | Purpose | Version |
|---|---|---|
| `go test` | Test runner | Go 1.26.1 |
| `testify` | Assertions + mocking | v1.11.1 |
| `go-sqlmock` (DATA-DOG) | Mock SQL driver for DB tests | v1.5.2 |
| `testcontainers-go` | Integration test containers | v0.43.0 |

### Test Commands

All from `backend/` directory:

```bash
make test                    # Run all unit tests with race detection + coverage
make test-unit               # Unit tests only
make test-integration        # Integration tests (requires DB, uses build tag `integration`)
make test-all                # Unit + integration tests
make test-coverage           # Unit tests + HTML coverage report
```

Or directly:
```bash
go test -race -count=1 ./internal/... ./pkg/... ./cmd/...
go test -tags=integration -race -count=1 ./internal/database/...
```

### Integration Test Suite: `test_endpoint.sh`

Location: `backend/scripts/test_endpoint.sh` (675 lines)

A comprehensive Bash-based integration test that exercises the full API flow end-to-end:

- **40 tests** — health → CSRF → register → login → school create → provisioning poll → curriculum → assessments → sessions → grade items → sum-to-100 validation
- Uses `curl` against `http://localhost:8080/api/v2`
- Custom `req()` function wraps `curl` with auth, CSRF, and JSON headers
- Helper functions: `check_ok()`, `check_status()`, `extract_value()`, `extract_nested()`
- CSRF token extraction uses `extract_nested` (Python-based JSON path navigation)
- Requires: `make db-init DROP_TENANT=true && make migrate && make seed && ./bin/server`

### Unit Test Pattern

**Interface-based mocking** with `testify/mock`:

Each module has a `mock_repository_test.go` file (e.g., `backend/internal/modules/user/mock_repository_test.go`) that implements the repository interface with `testify/mock.Mock`:

```go
type MockUserRepository struct {
    mock.Mock
}

func (m *MockUserRepository) FindByID(ctx context.Context, id uint) (*models.User, error) {
    args := m.Called(ctx, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*models.User), args.Error(1)
}
```

**Test structure** — Arrange → Act → Assert:

```go
func TestRegisterAttendee_Duplicate(t *testing.T) {
    t.Parallel()

    // Arrange
    mockEventRepo := new(MockEventRepository)
    mockAttendeeRepo := new(MockAttendeeRepository)
    mockEventRepo.On("FindByIDAndSchool", mock.Anything, uint(1), uint(1)).Return(event, nil)
    svc := &AlumniService{eventRepo: mockEventRepo, attendeeRepo: mockAttendeeRepo}

    // Act
    _, err := svc.RegisterAttendee(context.Background(), nil, 1, 1, 1)

    // Assert
    require.Error(t, err)
    mockEventRepo.AssertExpectations(t)
}
```

**Test naming convention:** `Test{Unit}_{Scenario}` or `Test{Unit}_{Scenario}_{Expected}`

Examples:
- `TestRegisterAttendee_Duplicate`
- `TestRegisterAttendee_Success`
- `TestSaveGradeItemScore_Success`
- `TestBatchCreateStudents_DuplicateEmail_SkipsDuplicate`
- `TestNewNotFoundError`

### Test File Locations

**67 test files found** across the backend:

| Path | Count | Purpose |
|---|---|---|
| `internal/modules/*/service_test.go` | 14 | Service layer unit tests (one per module) |
| `internal/modules/*/mock_repository_test.go` | 10 | Mock implementations for testing |
| `internal/middleware/*_test.go` | 6 | Middleware tests (auth, tenant, CSRF, request ID, etc.) |
| `internal/database/tenant/*_test.go` | 4 | Tenant isolation, connection manager, factory, migration |
| `internal/database/uuid/*_test.go` | 1 | UUID column helpers |
| `internal/errors/*_test.go` | 1 | Error constructors |
| `internal/config/*_test.go` | 1 | Config validation |
| `internal/crypto/*_test.go` | 2 | Encryption, security helpers |
| `internal/services/*_test.go` | 3 | Blacklist, user cache, refresh store |
| `internal/backup/*_test.go` | 1 | Backup service |
| `internal/restore/*_test.go` | 1 | Restore service |
| `internal/queue/*_test.go` | 3 | Queue tasks, backup/restore handlers |
| `internal/helpers/*_test.go` | 1 | Helper functions |
| `internal/ai/rag/*_test.go` | 1 | RAG chunker |
| `pkg/storage/*_test.go` | 2 | S3 backup, local storage |
| `pkg/totp/*_test.go` | 1 | TOTP implementation |
| `benchmarks/*_test.go` | 1 | Tenant routing benchmark |

### Test Helpers

**`newMockDB()` pattern** for DB-layer tests using `go-sqlmock`:
```go
func newMockDB(t *testing.T) (*gorm.DB, sqlmock.Sqlmock) {
    t.Helper()
    db, mock, err := sqlmock.New()
    require.NoError(t, err)
    t.Cleanup(func() { _ = db.Close() })
    gormDB, err := gorm.Open(postgres.New(postgres.Config{Conn: db}), &gorm.Config{SkipDefaultTransaction: true})
    require.NoError(t, err)
    return gormDB, mock
}
```

### Coverage

- Coverage output: `backend/coverage.out` and `backend/coverage.html`
- Coverage target: 80%+ on service logic

### What's Tested vs Not Tested

**Well-tested:**
- Service-layer business logic (mock-based, ~14 service test files)
- Auth flows (register, login, refresh, logout)
- Domain error constructors
- Middleware behaviors (auth, CSRF, tenant resolution, request ID)
- Tenant isolation (build-tag gated `//go:build integration`)
- Score/CBA/Banking operations
- S3 backup/restore operations
- HR/staff attendance
- Encryption/crypto operations

**Not explicitly tested (no unit tests found):**
- Handler layer HTTP routing (no `httptest` tests found)
- Most frontend logic (only 2 frontend test files)

---

## Frontend Testing

### Test Framework

| Tool | Purpose | Config |
|---|---|---|
| **Vitest** | Unit/component test runner | `frontend/vitest.config.ts` |
| **Playwright** | E2E smoke tests | `frontend/playwright.config.ts` |
| **@testing-library/react** | Component rendering | via `setupFiles` |
| **@testing-library/jest-dom/vitest** | DOM matchers | in `src/setupTests.ts` |

### Test Commands

```bash
cd frontend
yarn test                    # vitest run
yarn test:watch              # vitest (watch mode)
yarn test:e2e                # playwright test
yarn test:e2e:ui             # playwright test --ui
```

### Vitest Configuration (`frontend/vitest.config.ts`)

```ts
export default defineConfig({
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    test: {
        globals: true,
        environment: "jsdom",
        setupFiles: ["./src/setupTests.ts"],
        css: true,
        exclude: ["e2e/**", "node_modules/**"],
    },
});
```

### Frontend Test Files

| File | Type | Lines |
|---|---|---|
| `frontend/src/__tests__/use-debounce.test.ts` | Unit (hook) | 104 |
| `frontend/src/__tests__/template-store.test.ts` | Unit (store) | — |
| `frontend/e2e/auth-smoke.spec.ts` | E2E (Playwright) | 43 |
| `frontend/e2e/navigation-smoke.spec.ts` | E2E (Playwright) | 26 |

### Frontend Unit Test Patterns (Vitest)

```ts
/// <reference types="vitest/globals" />
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/lib/hooks/useDebounce";

describe("useDebounce", () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); });

    it("returns the initial value immediately", () => {
        const { result } = renderHook(() => useDebounce("hello", 300));
        expect(result.current).toBe("hello");
    });
});
```

- Uses `vi.fn()` / `vi.useFakeTimers()` (Vitest globals)
- `renderHook()` from `@testing-library/react`
- Standard `describe` / `it` / `expect` pattern

### Playwright E2E Tests

Configuration (`frontend/playwright.config.ts`):
- testDir: `./e2e`
- Single worker (smoke tests run sequentially)
- Retries: 1
- baseURL: `http://localhost:4000`
- Trace/screenshot on failure only
- Chromium only

**`auth-smoke.spec.ts`** — tests login flow:
1. Renders login page
2. Shows validation errors on empty submit
3. Logs in with valid credentials (playbit/Password123!)

**`navigation-smoke.spec.ts`** — tests basic navigation.

### Frontend Setup

```ts
// src/setupTests.ts
import "@testing-library/jest-dom/vitest";
```

---

## Known Test Gaps

| Gap | Impact | Location |
|---|---|---|
| **No handler/HTTP tests** | Routes and request/response formats untested at unit level | All `handler.go` files |
| **Minimal frontend tests** | Only 2 unit tests and 2 E2E smoke tests for entire frontend | `frontend/src/__tests__/` |
| **No component tests** | UI component behavior not tested | All `src/components/` |
| **No integration test for frontend+backend** | No test validates the full stack together (backend E2E is curl-based) | — |
| **No mutation/query error coverage** | Frontend error states (network failure, empty responses) not tested | All `src/lib/hooks/` |
| **Coverage not enforced** | `go test` generates coverage report but there is no minimum threshold | `backend/Makefile` |
| **Flaky Redis tests** | `TestRedisRateLimiter_Allow` and `TestRedisRateLimiter_SlidingWindowPrecision` fail due to sub-second duration truncation | `backend/internal/middleware/ratelimit_test.go` |

---

*Testing analysis: 2026-07-18*
