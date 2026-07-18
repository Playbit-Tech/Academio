# Production Audit Checklist

> **Purpose**: Checklist for performing a complete verification and audit of enterprise Go backend refactoring.  
> **Role**: Principal Software Architect / Staff Backend Engineer / Security Auditor / DevOps / QA / Code Reviewer.  
> **Constraint**: This is an audit-only task — no new features, no blind trust in existing code.  
> **Scope**: ~58K-line Go backend, 39 modules, multi-tenant (PostgreSQL per school), Gin + GORM + pgx v5.

---

## How to Use

1. Work through each section sequentially.
2. For every issue found, record: **Severity → Location → Explanation → Risk → Recommended Fix → Refactored Code → Why Better**.
3. Do not skip low-severity issues — production readiness requires all levels.
4. Assume the previous implementation contains mistakes, omissions, regressions, incomplete implementations, incorrect assumptions, or fake implementations.
5. Continue until every file has been inspected.

---

## 1. Architecture Review

Verify the application follows:

- [ ] **Clean Architecture**: Handler → Service → Repository layers are distinct. No layer skipping.
- [ ] **SOLID Principles**:
  - Single Responsibility: Each type/function has one reason to change.
  - Open/Closed: Extensions via interfaces, not modifications.
  - Liskov Substitution: Interface implementations are substitutable.
  - Interface Segregation: Small, focused interfaces — not monoliths.
  - Dependency Inversion: High-level modules don't depend on low-level modules; both depend on abstractions.
- [ ] **Repository Pattern**: Data access abstracted behind interfaces; callers never use GORM directly.
- [ ] **Dependency Injection**: Dependencies passed via constructor, not global singletons or `init()`.
- [ ] **Service Layer**: Business logic lives in services, not handlers or repositories.
- [ ] **Middleware Layer**: Cross-cutting concerns (auth, logging, CSRF) in middleware, not sprinkled in handlers.
- [ ] **Separation of Concerns**: DTOs, models, handlers, services, repositories each in their own files.
- [ ] **Proper Package Structure**: `internal/modules/{domain}/` with `handler.go`, `service.go`, `repository.go`, `dto.go`.

### Violations to Flag

| Pattern | Red Flag |
|---|---|
| Clean Architecture | Handler calling repository directly |
| DI | `var db *gorm.DB` package-level singleton |
| Interface Segregation | 10-method interface where caller only needs 2 |
| Separation | DTO/model/DB logic mixed in one file >500 lines |

---

## 2. Database Review

- [ ] **Transactions**: Mutations spanning multiple tables wrapped in GORM transactions. Rollback on any error.
- [ ] **Indexes**: Foreign key columns have indexes. Query WHERE columns have indexes. No sequential scans on hot paths.
- [ ] **No N+1 Queries**: `Preload` or `Joins` used instead of looping + per-row query. Verify with `db.Debug()`.
- [ ] **UUID Usage**: All public IDs are UUIDs (not auto-increment). Internal joins may use `uint` PKs.
- [ ] **Foreign Keys**: GORM `constraint` tags present. `ON DELETE` behavior explicitly set (CASCADE / SET NULL / RESTRICT).
- [ ] **Constraints**: DB-level uniqueness constraints (not just app-level checks).
- [ ] **Migrations**: Timestamped, idempotent, reversible (`Up`/`Down`). No destructive changes on production data.
- [ ] **Soft Delete**: `gorm.DeletedAt` used where data retention matters. Queries filter `WHERE deleted_at IS NULL`.
- [ ] **Multi-Tenant Readiness**: All tenant-scoped queries use schema-scoped `*gorm.DB` from `middleware.GetTenantDB(c)` (which returns the `SchemaTablePrefix`-prefixing session). Never use raw core DB for tenant queries.
- [ ] **Repository Correctness**: `First` vs `Find` used correctly (`First` expects 1 row; `Find` expects 0+). Errors checked after every query.
- [ ] **Connection Pooling**: `MaxOpenConns`, `MaxIdleConns`, `ConnMaxLifetime` set per tenant. No connection leaks.
- [ ] **pgx v5 Compatibility**: No multi-statement `db.Exec()`. Break into individual calls.

### Inefficient SQL Patterns

```sql
-- ❌ No index on status
SELECT * FROM users WHERE status = 'active';

-- ❌ N+1 in loop
for _, s := range students {
    db.Find(&grades, "student_id = ?", s.ID)  -- N queries!
}

-- ✅ Preload
db.Preload("Grades").Find(&students)
```

---

## 3. Security Review (OWASP Top 10)

- [ ] **Authentication**: JWT validated on every protected route. Token expiry enforced. Refresh token rotation.
- [ ] **Authorization (RBAC)**: Role checks on every state-mutating endpoint. `school_id` matches JWT claims.
- [ ] **Password Hashing**: bcrypt (or argon2) with cost ≥ 12. Never plaintext, never MD5/SHA1.
- [ ] **JWT Validation**: Signature verified. Claims validated (`exp`, `iat`, `school_id`). Algorithm enforced (HS256/RS256).
- [ ] **Refresh Tokens**: Stored securely (hashed in DB). Rotation on use. Revocation on password change.
- [ ] **MFA Readiness**: TOTP setup/verification flow exists. Backup codes generated.
- [ ] **Session Security**: Sessions invalidated on password change. Logout revokes tokens.
- [ ] **SQL Injection**: Parameterized queries only. No `fmt.Sprintf` for SQL. No raw SQL string concatenation.
- [ ] **XSS Protection**: Gin's `SecureJSON` or `HTML escape` on user-generated content in API responses.
- [x] **CSRF Protection**: HMAC-based token pattern via `middleware.CSRF(secret)`. APP_SECRET validated at startup (fail-fast in production, warning in dev). Tokens generated with `GenerateCSRFToken()` and validated with `ValidateCSRFToken()` — both read from a package-level secret set during middleware initialization, not via `os.Getenv`. All state-mutating endpoints protected.
- [ ] **SSRF Protection**: Outbound HTTP requests restricted to allowlisted domains. No user-controlled URLs.
- [ ] **Rate Limiting**: Per-IP and per-user rate limits. Login endpoints have stricter limits.
- [ ] **Request Validation**: Input validated at handler boundary (struct tags, custom validators). Invalid input rejected early.
- [ ] **Input Sanitization**: Path traversal prevented (`../` blocked). File uploads validated (type, size, content).
- [ ] **Output Encoding**: JSON responses use `json.Marshal` / Gin renderer (safe by default for JSON).
- [ ] **Secure File Uploads**: File type validated by content (not extension). Size limit enforced. Stored outside webroot.
- [ ] **Secret Management**: All secrets from env vars. No hardcoded defaults. `.env` never committed.
- [ ] **CORS**: Explicit origin allowlist. Credentials only with specific origin (not `*`).
- [x] **Security Headers**: `Content-Security-Policy` (path-based — strict for API routes, relaxed with `unsafe-inline`/`unsafe-eval` for `/swagger*`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy`, `Permissions-Policy` via `middleware/security.go`.

### Sensitive Data Exposure
- [ ] Passwords never returned in API responses.
- [ ] Tokens never logged.
- [ ] PII (email, phone, address) returned only when authorized.
- [ ] Internal error details never exposed in production responses.

---

## 4. Logging Review

- [ ] **Consistent Logger**: `pkg/logger` used everywhere. No `fmt.Printf`, `log.Printf`, `println`.
- [ ] **Traceability**: Every request has a unique `request_id` propagated through the chain.
- [ ] **Required Log Fields**:

| Field | Required | When |
|---|---|---|
| `timestamp` | Yes | Every log entry |
| `request_id` | Yes | Request-scoped |
| `user_id` | Yes | Authenticated requests |
| `tenant_id` / `school_id` | Yes | When school context exists |
| `method`, `path` | Yes | HTTP request logs |
| `status_code` | Yes | HTTP response logs |
| `latency_ms` | Yes | HTTP response logs |
| `ip_address` | Yes | HTTP request logs |
| `service_name` | Yes | Every log entry |
| `error` | Yes | Error logs (with stack trace) |
| `correlation_id` | Yes | Cross-service traces |

- [ ] **Log Levels**:
  - `Debugf`: Development-only details, not in production.
  - `Infof`: Normal operations (request start/end, successful mutations).
  - `Warnf`: Recoverable issues (fallback behavior, transient failures).
  - `Errorf`: Degraded functionality (partial success, downstream failure).
  - `Fatalf`: Unrecoverable startup failures only (not in request handlers).

- [ ] **Secrets in Logs**: Grep for patterns logging `password`, `token`, `secret`, `key`, `credit_card`. Zero tolerance — any found is Critical.

---

## 5. Error Handling

- [ ] **Centralized Error Handling**: Gin middleware catches panics (` Recovery`) and returns consistent JSON.
- [ ] **Consistent Error Responses**:

```json
{
    "error": "human-readable message",
    "code": "VALIDATION_ERROR",
    "details": { "field": "email", "reason": "already exists" }
}
```

- [ ] **Internal Errors Hidden**: `fmt.Errorf("some internal: %w", err)` — never expose internal details to client.
- [ ] **HTTP Status Codes**:

| Situation | Status |
|---|---|
| Validation failure | 400 |
| Unauthenticated | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Conflict | 409 |
| Rate limited | 429 |
| Internal error | 500 |

- [ ] **Error Wrapping**: Every `return err` in service layer wraps with `fmt.Errorf("context: %w", err)`.
- [ ] **Context Preserved**: Error chain retains root cause via `%w`. Callers can `errors.Is()` / `errors.As()`.

### Check Every Handler
- [ ] No bare `c.Error(err)` without response.
- [ ] No `c.JSON(200, ...)` on error.
- [ ] No missing `return` after `c.JSON(err)`.

---

## 6. Performance Review

- [ ] **Slow Queries**: Check for missing indexes on `WHERE`, `JOIN`, `ORDER BY` columns. Sequential scans in EXPLAIN ANALYZE.
- [ ] **Memory Leaks**: Long-lived goroutines with no exit condition. Channels that never get drained. Maps that grow unbounded.
- [ ] **Goroutine Leaks**: Goroutines launched without `WaitGroup` or context cancellation. Background loops with no shutdown signal.
- [ ] **Blocking Operations**: Channel sends with no receiver. `sync.Mutex` held across network calls. `time.Sleep` in loops.
- [ ] **Unnecessary Allocations**: Large structs passed by value. `fmt.Sprintf` in hot loops. Repeated slice growth.
- [ ] **Duplicate DB Calls**: Same query executed multiple times in the same request. Missing `Preload` causing N+1.
- [ ] **Missing Caching**: Frequently accessed, rarely changed data (config, school settings) not cached. Redis available but unused.
- [x] **Missing Pagination**: Resolved. Three academic endpoints (`ListSessions`, `ListCurriculums`, `ListAssessments`) now use service-layer pagination: `helpers.ParsePagination(c)` → `(page=1, limit=20)` with a max limit of 100. Handlers return `response.SuccessWithPagination(data, total, page, limit)`. Unbounded queries on remaining list endpoints flagged as future work.
- [ ] **Missing Indexes**: Composite indexes for multi-column WHERE clauses.
- [ ] **Inefficient Loops**: Nested loops over DB result sets. O(n²) algorithms on large slices.

### Optimizations
| Pattern | Fix |
|---|---|
| Repeated `Find` in loop | Batch fetch + in-memory map |
| Large JSON marshaling | Stream or paginate |
| Hot-path string concat | `strings.Builder` |
| Reflection-heavy code | Generics (Go 1.26) |

---

## 7. Configuration Review

- [ ] **Environment Variables**: All config loaded from env vars. No config files committed with secrets.
- [ ] **Startup Validation**: `config.Load()` validates all required fields. Missing required config = fatal error, not warning.
- [x] **Fail-Fast**: `config.Load()` validates all required fields and calls `validateProduction()`, which checks: email enabled → SendGrid key present, SMS enabled → Twilio credentials present, S3 driver → access/secret key present, AI enabled → provider API key present. Server doesn't start if any enabled service is missing its required credentials.
- [ ] **No Hardcoded Secrets**: Zero tokens, passwords, API keys in source. Grep the entire repo.
- [ ] **Secure Defaults**:
  - Production: rejects default passwords, requires strong JWT secret.
  - Development: safe defaults that don't expose real data.

---

## 8. Middleware Review

- [ ] **Middleware Order** (top → bottom as applied to router):

```go
r.Use(
    Recovery(),
    RequestID(),      // 1. Generate request ID
    Logger(),         // 2. Log request
    SecurityHeaders(),// 3. Security headers
    CORS(),           // 4. CORS
    RateLimiter(),    // 5. Rate limit
    Timeout(),        // 6. Timeout (after rate limit, before auth)
    Auth(),           // 7. Authenticate
    Tenant(),         // 8. Resolve school/tenant
    Audit(),          // 9. Audit trail
)
```

- [ ] **Recovery**: Panic recovery middleware is first in chain. Returns 500 JSON, not HTML.
- [ ] **Logging**: Logs every request with all required fields. No PII in logs.
- [ ] **Authentication**: JWT middleware validates token on every protected route. Returns 401 with no body on failure.
- [ ] **Authorization**: RBAC middleware checks role before handler executes. Returns 403 with clear message.
- [ ] **Request ID**: UUID generated per request. Set on context and response header (`X-Request-ID`).
- [ ] **Correlation ID**: Propagated from client if present; generated if absent.
- [ ] **Timeout**: Per-request timeout (e.g., 30s). Prevents hung connections from consuming resources.
- [ ] **Rate Limiting**: Per-IP + per-user. Sliding window. Login endpoints stricter (e.g., 5/min).
- [ ] **Security Headers**: `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security`, `X-Content-Type-Options`.
- [ ] **Compression**: Gzip/brotli for responses > 1KB.
- [ ] **CORS**: Allowlist of origins. Credentials only with explicit origin, never `*`.

---

## 9. API Review

- [ ] **RESTful Design**: Resources mapped to endpoints. Nouns, not verbs (`/users`, not `/getUsers`).
- [ ] **Correct HTTP Methods**:
  - `GET` — read
  - `POST` — create
  - `PUT` — full update
  - `PATCH` — partial update
  - `DELETE` — delete
- [ ] **Status Codes**:
  - `200` — success
  - `201` — created
  - `204` — no content (delete)
  - `400` — bad request
  - `401` — unauthorized
  - `403` — forbidden
  - `404` — not found
  - `409` — conflict
  - `422` — unprocessable entity
  - `429` — too many requests
  - `500` — internal error
- [ ] **Validation**: Every input validated at handler. Rejected with 400 and field-level error messages.
- [ ] **Pagination**: List endpoints support `?page=&limit=` with default and max bounds.
- [ ] **Filtering**: `?status=active&school_id=X` with documented params.
- [ ] **Sorting**: `?sort=name&order=asc` with documented fields.
- [ ] **Versioning**: All routes under `/api/v2/`.
- [ ] **Consistent JSON Responses**:

```json
// Success (single)
{ "data": { ... } }

// Success (list)
{ "data": [...], "total": 100, "page": 1, "limit": 20 }

// Error
{ "error": "message", "code": "ERROR_CODE", "details": {} }
```

---

## 10. Code Quality Review

- [ ] **Dead Code**: Unused functions, types, variables, constants, imports. Run `go vet ./...` + `unused` check.
- [ ] **Duplicate Logic**: Same validation/transformation repeated across files. Extract to shared helper.
- [ ] **Large Functions**: Any function > 120 lines. Extract named sub-functions.
- [ ] **Magic Numbers**: Bare literals like `86400`, `3`, `100` without named constants.
- [ ] **Global Mutable State**: Package-level `var` that can be modified from multiple goroutines.
- [ ] **Poor Naming**: Single-letter vars (except loop indexes), abbreviations, inconsistent casing.
- [ ] **Tight Coupling**: Concrete type dependencies instead of interfaces. `import` cycles.
- [ ] **Missing Interfaces**: Repositories, services, not abstracted behind interfaces (untestable).
- [ ] **Missing Comments**: Exported types/functions without doc comments. Complex logic without explanation.
- [ ] **Missing Tests**: Public API functions without tests. Error paths without tests.

### Scoring

| Dimension | Target |
|---|---|
| Cyclomatic complexity | ≤ 25 per function |
| Function length | ≤ 120 lines |
| Test coverage | ≥ 80% on service layer |
| Duplication | ≤ 5% |
| Comment density | ≥ 15% (doc comments) |

---

## 11. Testing Review

- [ ] **Unit Tests**: Service layer tested with mocked repositories. All error paths covered.
- [ ] **Integration Tests**: Repository tests with real (or container) database. Full round-trip CRUD.
- [ ] **Repository Tests**: Each repository method tested. Edge cases: zero results, duplicate keys, FK violations.
- [ ] **Middleware Tests**: Auth middleware tested with valid/invalid/expired tokens. Rate limiter tested.
- [ ] **Service Tests**: Business logic tested in isolation. Validation rules tested.

### Critical Paths to Cover

| Path | Scenario |
|---|---|
| Registration | Success, duplicate email, weak password |
| Login | Success, wrong password, locked account |
| Tenant provisioning | Pending → Active → Failed transitions |
| Score entry | Valid score, exceeds max, duplicate |
| Batch import | All valid, mixed errors, all errors |
| Parent dedup | Same email, same phone, same username |
| Password change | Success, wrong current, revoked sessions |

### Coverage Requirements

- Service layer: ≥ 80%
- Repository layer: ≥ 70%
- Handler layer: ≥ 60%
- Overall: ≥ 75%

---

## 12. Observability Review

- [ ] **Health Endpoint**: `GET /health` returns 200 with `{"status": "ok"}`.
- [ ] **Readiness Endpoint**: `GET /ready` returns 200 when DB + Redis + queue are connected; 503 otherwise.
- [ ] **Liveness Endpoint**: `GET /live` returns 200 when process is alive (simple ping).
- [ ] **Metrics Endpoint**: `GET /metrics` exposes Prometheus metrics (Go runtime, HTTP request count/duration, DB query count/duration).
- [ ] **Prometheus**: Counter for requests, Histogram for latency, Gauge for concurrent requests, DB pool stats.
- [ ] **Grafana**: Dashboard exists for key metrics (error rate, p99 latency, DB pool utilization).
- [ ] **OpenTelemetry**: Traces propagated across service boundaries. Span attributes include tenant_id, user_id.
- [ ] **Alerting**: Rules for error rate spike > 5%, p99 latency > 2s, DB connections > 80% of pool.

---

## 13. Tenant Isolation Review (Schema-Per-Tenant)

- [ ] **School Isolation**: All schools share one PostgreSQL database; each school's data lives in `school_{id}` schema. `User` + `School` tables in shared `public` schema. `SchemaTablePrefix` GORM plugin auto-prefixes table names at query time.
- [ ] **Schema Resolution**: `TenantDBResolver` middleware calls `TenantResolutionService.Resolve(ctx, schoolID)` → checks Redis cache → falls back to `schools` table → returns `schema_name`. `RepositoryFactory.ForSchoolSchema(ctx, schoolID, schemaName)` creates a `SchemaDB` wrapper around the core DB connection.
- [ ] **Tenant-Safe Repositories**: Repositories receive a `*gorm.DB` from `GetTenantDB(c)`, which returns the `SchemaDB` session. Queries on this session automatically have schema-prefixed table names via the GORM plugin.
- [ ] **Tenant-Safe Logging**: Every log entry includes `tenant_id`/`school_id`.
- [ ] **Tenant-Safe Caching**: Cache keys include `school_id` prefix. No cross-tenant cache poisoning.
- [ ] **Migration Isolation**: `SET LOCAL search_path TO school_{id}` scopes DDL to the tenant schema within a transaction. Tracking table: `tenant_schema_migrations` created inside each schema.
- [ ] **Search path isolation**: No connection-level `SET search_path` exists.
      All raw SQL uses either explicit schema qualifiers or `SET LOCAL` inside
      transactions. The `SchemaTablePrefix` GORM plugin is the default isolation
      mechanism for API queries — it prefixes table names at the SQL statement
      level, making it PgBouncer-compatible and immune to connection pool reuse
      issues. See `docs/architecture/search-path-strategy.md`.
- [ ] **Leak Prevention**:
  - [ ] No query without schema prefix in tenant operations (enforced by `SchemaTablePrefix` plugin).
  - [ ] No hardcoded schema names (resolved from `schools` table at runtime).
  - [ ] No `context.Background()` in tenant-scoped operations.
  - [ ] Single shared connection pool — no per-tenant connections (schema isolation removes the need).
  - [ ] Cross-schema FK constraints verified (e.g., `students.user_id` → `public.users.id`).

---

## 14. Consistency Review

- [ ] **Naming Conventions**: All files follow the same pattern (camelCase vars, PascalCase exports, snake_case JSON).
- [ ] **Folder Structure**: Every module has the same layout (`dto.go`, `handler.go`, `service.go`, `repository.go`).
- [ ] **Coding Style**: Go style guide (gofmt, goimports) followed uniformly.
- [ ] **Logging Style**: All log messages use the same format (`pkg/logger.Infof`/`Warnf`/`Errorf`).
- [ ] **Error Handling Style**: All errors use `fmt.Errorf("context: %w", err)`. No bare `return err`.
- [ ] **Dependency Injection**: All constructors follow `NewX(deps ...) *X` pattern. No `init()`.
- [ ] **Repository Implementations**: Every repository implements an interface. Methods return domain types, not GORM models.

---

## 15. Severity Classification

| Severity | Definition | Action |
|---|---|---|
| **Critical** | Data loss, security breach, complete functionality broken | Fix immediately, block release |
| **High** | Major functionality broken, significant performance issue, security weakness | Fix before next release |
| **Medium** | Minor functionality issue, code quality concern, missing test coverage | Fix this sprint |
| **Low** | Style violation, missing comment, minor refactor opportunity | Add to backlog |

---

## 16. Report Format

For every issue found, record:

```markdown
### [SEVERITY] Title

**Location**: `file.go:123`

**Explanation**: What's wrong and why it matters.

**Risk**: What could go wrong in production.

**Recommended Fix**: Briefly describe the fix.

**Refactored Code**:
```go
// Before (broken)
func bad() { ... }

// After (fixed)
func good() { ... }
```

**Why Better**: Why the fix improves correctness/performance/security/maintainability.
```

---

## References

- `backend/STYLE.md` — Go coding conventions
- `backend/AGENTS.md` — project operational context
- `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` — context propagation, graceful shutdown, telemetry
- `docs/plans/CR-CODE-REVIEW-FIXES.md` — current code-review phase plan
- `backend/TESTING.md` — testing conventions
- `.golangci.yml` — linter config (used in CI)
