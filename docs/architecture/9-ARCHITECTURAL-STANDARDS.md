# Architectural Standards

> **Status**: Ratified  
> **Applies to**: `backend/` Go services  
> **Enforcement**: `go build ./...`, `go vet ./...`, `golangci-lint`, CI gates

---

## 1. Context Propagation (`context.Context`)

**Rule**: Every handler → service → repository → external call chain must accept and propagate a `context.Context`.

### Requirements
- All handler methods must pass `c.Request.Context()` to services.
- All service methods must accept `ctx context.Context` as the first parameter.
- All repository methods must accept `ctx context.Context` and call `db.WithContext(ctx)`.
- Background goroutines must use the parent `ctx`, not `context.Background()`.
- Batch operations must use a context that carries request metadata.

### Canonical Pattern
```go
// Handler
func (h *XHandler) HandleX(c *gin.Context) {
    result, err := h.service.DoX(c.Request.Context(), ...)
}

// Service
func (s *XService) DoX(ctx context.Context, ...) (*X, error) {
    return s.repo.FindX(ctx, ...)
}

// Repository
func (r *XRepository) FindX(ctx context.Context, ...) (*X, error) {
    var x X
    if err := r.db.WithContext(ctx).Where(...).First(&x).Error; err != nil {
        return nil, err
    }
    return &x, nil
}
```

### Anti-patterns (forbidden)
```go
// ❌ Using context.Background() in request-scoped code
tenantDB, err := f.dbManager.GetTenantDB(context.Background(), schoolID)

// ❌ Not passing ctx to repository
err := r.DB.Where(...).First(&x).Error

// ❌ Dropping ctx in goroutines
go func() {
    doWork(context.Background())
}()
```

### Enforcement
- `golangci-lint` rule: `contextcheck`
- Code review checklist: verify `ctx` propagation at every boundary

---

## 2. Graceful Shutdown

**Rule**: All servers and background workers must support graceful shutdown with bounded timeout.

### Requirements
- HTTP server must use `srv.Shutdown(ctx)` with a 30-second timeout.
- Queue workers must call `server.Shutdown()` during shutdown.
- WebSocket hubs must stop accepting new connections and drain existing ones.
- Audit logger must flush pending events before returning.
- Database connections must be closed after in-flight requests complete.

### Canonical Pattern
```go
// main.go
quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
<-quit

ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()

if err := srv.Shutdown(ctx); err != nil {
    logger.Fatal("Server forced to shutdown", "error", err)
}
```

### Shutdown Sequence
1. Stop accepting new connections
2. Drain in-flight HTTP requests
3. Shutdown queue worker (drain in-flight tasks)
4. Close Redis client
5. Close AI provider
6. Flush audit logger
7. Close database connections

### Anti-patterns (forbidden)
```go
// ❌ No shutdown handler
go func() {
    srv.ListenAndServe()
}()

// ❌ Immediate kill without drain
os.Exit(0)
```

---

## 3. Structured Logging

**Rule**: All logs must use the structured logger (`pkg/logger`) with JSON output.

### Requirements
- All application code must use `pkg/logger` (`Debug`, `Info`, `Warn`, `Error`, `Fatal`).
- All logs must include structured fields, not formatted strings.
- Request logs must include `request_id`, `method`, `path`, `status`, `latency_ms`, `tenant_id`.
- Background tasks must include `school_id`, `task_id`, and relevant domain fields.
- Never use `log.Printf`, `fmt.Println`, or `println` in application code.

### Canonical Pattern
```go
// ✅ Structured logging
logger.Infof("Processing score entry",
    "student_id", studentID,
    "grade_item_id", gradeItemID,
    "score", score,
    "tenant_id", schoolID,
)

// ❌ Unstructured logging (forbidden)
fmt.Printf("Processing score entry for student %d\n", studentID)
log.Printf("Processing score entry for student %d", studentID)
```

### Log Fields Standard
| Field | Source | Required |
|-------|--------|----------|
| `request_id` | `middleware.RequestID` | Yes |
| `tenant_id` | `middleware.SchoolID` | Yes (when school context exists) |
| `user_id` | `middleware.JWTAuth` | Yes (when authenticated) |
| `method` | HTTP method | Yes |
| `path` | Request path | Yes |
| `status` | HTTP status | Yes |
| `latency_ms` | Duration | Yes |
| `error` | Error object | Yes (on errors) |

### Enforcement
- `golangci-lint` rule: custom `logcheck` linter
- Code review: reject `log.Printf`, `fmt.Println`, `println`

---

## 4. OpenTelemetry Instrumentation

**Rule**: All services must emit traces and metrics via OpenTelemetry for export to Grafana, Jaeger, or other observability platforms.

### Requirements
- HTTP middleware must create a span per request with standard attributes.
- All database operations must be traced via GORM plugin.
- All Redis operations must be traced via Redis hook.
- All external API calls must be traced.
- Metrics must be emitted for business-critical operations.
- Trace context must be propagated across service boundaries via W3C TraceContext.

### Canonical Pattern
```go
// HTTP middleware (already implemented)
func Tracing(serviceName string) gin.HandlerFunc

// Service-level spans
func (s *XService) DoX(ctx context.Context) error {
    ctx, span := telemetry.Tracer("XService").Start(ctx, "DoX")
    defer span.End()
    // ... work ...
}

// External calls
func (s *XService) callExternal(ctx context.Context) error {
    ctx, span := telemetry.Tracer("external").Start(ctx, "CallAPI")
    defer span.End()
    // ... HTTP call ...
}
```

### Required Span Attributes
| Attribute | Value |
|-----------|-------|
| `http.method` | HTTP method |
| `http.path` | Request path |
| `http.status_code` | Response status |
| `http.route` | Matched route pattern |
| `db.system` | `postgresql` |
| `db.name` | Database name |
| `db.operation` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `redis.command` | Redis command name |

### Enforcement
- CI must verify OTel provider initializes without error.
- Code review: verify new external calls are traced.

---

## 5. Configuration Validation with Fail-Fast

**Rule**: All configuration must be validated at startup. Invalid or missing required config must prevent the server from starting.

### Requirements
- All required environment variables must be validated.
- Production environment must enforce stronger validation than development.
- Default values must be safe and explicit.
- Validation errors must be logged with `logger.Fatal` and stop startup.

### Canonical Pattern
```go
func (c *Config) validate() error {
    if c.App.Env == "production" {
        if c.JWT.Secret == "" || c.JWT.Secret == "change-me-in-production" {
            return fmt.Errorf("JWT_SECRET must be set to a secure value in production")
        }
        if c.DB.Password == "" || c.DB.Password == "academio" {
            return fmt.Errorf("DB_PASSWORD must be set in production")
        }
    }
    if len(c.Encryption.Key) == 0 {
        return fmt.Errorf("ENCRYPTION_KEY must be set")
    }
    return nil
}
```

### Validation Rules
| Config | Rule |
|--------|------|
| `JWT_SECRET` | Required in production; reject placeholder values |
| `ENCRYPTION_KEY` | Always required; must be 32-byte hex |
| `DB_PASSWORD` | Required in production; reject default `academio` |
| `APP_PORT` | Must be valid port (1-65535) |
| `OTEL_ENABLED` | If `true`, `OTEL_ENDPOINT` must be set |

### Anti-patterns (forbidden)
```go
// ❌ Silent fallback to insecure defaults in production
secret := getEnv("JWT_SECRET", "change-me-in-production")

// ❌ Warning instead of error for required config
if c.JWT.Secret == "" {
    logger.Warnf("JWT_SECRET not set, using default")
}
```

### Enforcement
- `config.Load()` must return error on invalid config.
- `main.go` must call `logger.Fatal` on config load failure.

---

## 6. Zero Hardcoded Secrets

**Rule**: No secrets, passwords, API keys, or tokens may be hardcoded in source code.

### Requirements
- All credentials must be loaded from environment variables or a secret manager.
- No fallback to hardcoded values for security-critical secrets.
- Seed scripts must read passwords from environment variables.
- Default values for non-secret config are allowed.

### Canonical Pattern
```go
// ✅ Environment variable with no fallback for secrets
secret := os.Getenv("JWT_SECRET")
if secret == "" {
    return fmt.Errorf("JWT_SECRET is required")
}

// ✅ Non-secret config can have defaults
port := getEnv("APP_PORT", "8080")
```

### Forbidden Patterns
```go
// ❌ Hardcoded secret fallback
secret := "academio-default-csrf-secret"

// ❌ Hardcoded password in seed script
password := "Password123!"

// ❌ Placeholder secret in source code
getEnv("JWT_SECRET", "change-me-in-production")
```

### Specific Fixes Required
| File | Issue | Fix |
|------|-------|-----|
| `internal/middleware/csrf.go` | Hardcoded CSRF fallback | Make `APP_SECRET` required at startup |
| `internal/config/config.go` | JWT default in source | Remove default, validate empty |
| `scripts/seed/main.go` | Hardcoded password | Read from `SEED_ADMIN_PASSWORD` env var |

### Enforcement
- Pre-commit hook: `gitleaks` or `trufflehog` scan.
- CI: secret scanning job.
- Code review: reject any hardcoded credentials.

---

## 7. Tenant-Aware Logging and Auditing

**Rule**: Every request must be traceable to a specific school via structured logs and audit records.

### Requirements
- All HTTP request logs must include `tenant_id` when school context exists.
- All mutation operations must create audit log entries with `SchoolID`, `UserID`, `Action`, `ResourceType`, `RequestID`.
- Audit batch inserts must use request context, not `context.Background()`.
- Background tasks must include `school_id` in structured log fields.
- All service methods that perform mutations must log with tenant context.

### Canonical Pattern
```go
// Request logging middleware
args := []any{
    "method", method,
    "path", path,
    "status", status,
    "latency_ms", latency.Milliseconds(),
    "tenant_id", schoolID,  // ✅ Always include when available
}

// Audit logging
auditLogger.Log(AuditEvent{
    SchoolID:     schoolID,
    UserID:       userID,
    Action:       "update",
    ResourceType: "users",
    RequestID:    requestID,
})

// Background task logging
logger.Infof("Processing provisioning",
    "school_id", payload.SchoolID,
    "task_id", task.ID(),
)
```

### Audit Event Fields
| Field | Type | Required |
|-------|------|----------|
| `SchoolID` | `uint` | Yes |
| `UserID` | `uint` | Yes |
| `Action` | `string` | Yes |
| `ResourceType` | `string` | Yes |
| `ResourceID` | `string` | No |
| `OldValues` | `*models.JSONMap` | No |
| `NewValues` | `*models.JSONMap` | No |
| `IPAddress` | `string` | Yes |
| `UserAgent` | `string` | Yes |
| `RequestID` | `string` | Yes |

### Anti-patterns (forbidden)
```go
// ❌ Audit batch without request context
al.db.WithContext(context.Background()).Create(&rows)

// ❌ Unstructured background logging
h.logger.Printf("Starting backup for school %d", payload.SchoolID)

// ❌ Missing tenant_id in logs
logger.Infof("Processing request")
```

### Enforcement
- Code review: verify `tenant_id` in all request logs.
- Code review: verify audit events for all mutations.
- CI: grep for `context.Background()` in middleware/audit code.

---

## Enforcement Summary

| Principle | Enforcement Mechanism |
|-----------|----------------------|
| Context Propagation | `golangci-lint contextcheck`, code review |
| Graceful Shutdown | Integration tests, code review |
| Structured Logging | Custom linter, grep for `log.Printf`/`fmt.Println` |
| OpenTelemetry | CI verification, code review |
| Config Validation | Unit tests, `config.Load()` error handling |
| Zero Hardcoded Secrets | `gitleaks` pre-commit, CI secret scan |
| Tenant-Aware Logging | Code review, grep for missing `tenant_id` |

---

## References

- `AGENTS.md` — project operational constitution
- `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` — monitoring stack, tenant isolation
- `backend/MIGRATION_PLAN.md` — error wrapping, DTO discipline
- `backend/TESTING.md` — testing conventions
- `pkg/logger/logger.go` — structured logger implementation
- `internal/telemetry/provider.go` — OpenTelemetry setup
- `internal/middleware/tracing.go` — HTTP tracing middleware
- `internal/middleware/logger.go` — request logging middleware
- `internal/middleware/audit.go` — audit logging middleware
