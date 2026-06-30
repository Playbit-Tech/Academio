# Phase 4 Plan: Enhanced Auth & Tenant Resolution

## Overview

Phase 4 unifies tenant resolution into a single `TenantResolutionService`, embeds `school_id` in JWT claims, caches the full tenant context in Redis, and adds tenant-aware error codes and structured logging.

### Success Criteria
1. TenantResolutionService.ResolveTenant(schoolID, userID) validates school status, resolves DB connection, caches in Redis
2. Tenant context cached in Redis with TTL; subsequent requests skip core DB
3. All API errors include tenant-aware codes (TENANT_DISABLED, TENANT_DB_UNAVAILABLE, SUBSCRIPTION_EXPIRED)
4. Structured logs include school_id, request_id, tenant_db_host, plan for every request

---

## Wave 04-01: TenantResolutionService

**Goal**: Single entry point that resolves JWT + school_id -> full TenantContext with Redis caching.

### Files to Modify/Create

| # | File | Action | Description |
|---|------|--------|-------------|
| 1 | `pkg/jwt/jwt.go` | Edit | Add `SchoolID uint` to Claims; add schoolID param to `GenerateAccessToken` and `GenerateTokenPair` |
| 2 | `internal/database/tenant/tenant_context.go` | **Create** | `TenantContext` struct + Redis cache keys |
| 3 | `internal/database/tenant/resolution_service.go` | **Create** | `TenantResolutionService` with ResolveTenant, caching, invalidation |
| 4 | `internal/services/token_service.go` | Edit | Pass schoolID through to JWT generation |
| 5 | `internal/modules/auth/service.go` | Edit | Resolve user's school at login, pass to token generation |
| 6 | `internal/middleware/tenant.go` | Edit | Replace TenantResolver + TenantDBResolver with unified `TenantResolution` middleware |
| 7 | `internal/router/router.go` | Edit | Remove old middleware refs, use new `TenantResolution()` |
| 8 | `internal/router/setup.go` | Edit | Wire TenantResolutionService, pass to middleware |

### Step-by-Step

#### Step 1: Add SchoolID to JWT Claims
**File**: `pkg/jwt/jwt.go`

- Add `SchoolID uint \`json:"school_id"\`` to `Claims` struct
- Update `GenerateTokenPair(userID, email, role, familyID, schoolID)`
- Update `GenerateAccessToken(userID, email, role, familyID, schoolID)`
- Backward compatible: callers passing 0 get JWT with SchoolID=0

```go
type Claims struct {
    UserID    uint      `json:"user_id"`
    Email     string    `json:"email"`
    Role      string    `json:"role"`
    SchoolID  uint      `json:"school_id"`
    TokenType TokenType `json:"token_type"`
    FamilyID  string    `json:"family_id"`
    golangJwt.RegisteredClaims
}
```

#### Step 2: Create TenantContext
**File**: `internal/database/tenant/tenant_context.go`

```go
// TenantContext holds the resolved tenant information for a single request.
type TenantContext struct {
    SchoolID           uint      `json:"school_id"`
    SchoolName         string    `json:"school_name"`
    Plan               string    `json:"plan"`
    DatabaseName       string    `json:"-"`  // never expose in logs/response
    DatabaseHost       string    `json:"-"`
    Status             string    `json:"status"`
    SubscriptionStatus string    `json:"subscription_status"`
    SubscriptionExpiry *time.Time `json:"subscription_expiry,omitempty"`
    Features           []string  `json:"features,omitempty"`
    TenantDB           *gorm.DB  `json:"-"`  // never serialize
    ResolvedAt         time.Time `json:"resolved_at"`
}

// TenantContextKey is the context key for the resolved tenant context.
const CtxKeyTenantContext = "tenant_context"

// Redis cache key helpers
func tenantContextCacheKey(schoolID uint) string {
    return fmt.Sprintf("tenant:ctx:%d", schoolID)
}
```

#### Step 3: Create TenantResolutionService
**File**: `internal/database/tenant/resolution_service.go`

```go
// TenantResolutionService resolves school_id + user_id -> TenantContext.
type TenantResolutionService struct {
    coreDB      *gorm.DB
    connManager *ConnectionManager
    rdb         *redis.Client       // optional, nil = no cache
    cacheTTL    time.Duration       // default 5 min
}

func NewTenantResolutionService(coreDB *gorm.DB, connManager *ConnectionManager, rdb *redis.Client, cacheTTL time.Duration) *TenantResolutionService

// ResolveTenant returns the full TenantContext for a school.
// It checks: school exists -> database_status -> tenant DB connection -> cache result.
// Returns error with AppError for domain failures (school not found, disabled, etc.)
func (s *TenantResolutionService) ResolveTenant(ctx context.Context, schoolID uint) (*TenantContext, error)

// InvalidateCache removes the cached TenantContext for a school.
func (s *TenantResolutionService) InvalidateCache(ctx context.Context, schoolID uint) error

// WarmCache pre-populates the cache for a school.
func (s *TenantResolutionService) WarmCache(ctx context.Context, schoolID uint) error
```

**ResolveTenant internal flow**:
1. Check Redis cache (if rdb != nil) -> return cached if fresh
2. Look up school from core DB (`models.School`)
3. Validate status: `school.Status` == "active", `school.DatabaseStatus` in ["active","shared"]
4. If `DatabaseStatus == "active" && DatabaseName != ""`:
   - Get tenant DB from `connManager.GetConnection(schoolID)`
   - Validate DB is reachable with a ping
5. If shared DB mode, TenantDB = nil (handlers use core DB)
6. Build `TenantContext`, write to Redis cache, return
7. On any failure: return descriptive `AppError` with tenant error code

#### Step 4: Update TokenService
**File**: `internal/services/token_service.go`

- `GenerateTokenPair(ctx, user, role, rememberMe, deviceInfo, userAgent, ipAddress, schoolID)` -- add schoolID param
- Pass schoolID to `jwtSvc.GenerateAccessToken(user.ID, email, role, familyID, schoolID)`
- Update `TokenServiceInterface` to match new signature
- Update mock (or remove mock and rely on interface)

#### Step 5: Update Auth Service
**File**: `internal/modules/auth/service.go`

- In `Login()`: after `buildUserResponse()` resolves the user's schools, pick the school_id
  - If user has exactly 1 school, use that school_id
  - If user has 0 schools (super-admin), use 0
  - If user has multiple, use 0 (client must send x-school-id)
- Pass `schoolID` to `tokenSvc.GenerateTokenPair()`
- Pass the selected school ID in the login response for client awareness

#### Step 6: Create Unified Middleware
**File**: `internal/middleware/tenant.go`

Replace the existing `TenantResolver()` and `TenantDBResolver()` middlewares with a single `TenantResolution()` middleware:

```go
// TenantResolution returns middleware that resolves tenant context
// using TenantResolutionService. It combines the old TenantResolver
// + TenantDBResolver into a single middleware.
func TenantResolution(resolver *tenant.TenantResolutionService) gin.HandlerFunc {
    return func(c *gin.Context) {
        schoolID := GetSchoolID(c)
        if schoolID == 0 {
            c.Next()
            return
        }

        ctx, err := resolver.ResolveTenant(c.Request.Context(), schoolID)
        if err != nil {
            // For active degradation: set minimal context and continue
            // For hard failures (disabled school): abort with error
            var appErr *domerr.AppError
            if errors.As(err, &appErr) {
                _ = c.Error(appErr)
                c.Abort()
                return
            }
            // Unknown error: log and continue with defaults
            c.Set(string(CtxKeyTenantContext), minimalContext(schoolID))
            c.Next()
            return
        }

        c.Set(string(CtxKeyTenantContext), ctx)
        c.Set(string(CtxKeyTenantPlan), ctx.Plan)
        
        // Also store in Go context
        reqCtx := c.Request.Context()
        reqCtx = context.WithValue(reqCtx, CtxKeyTenantContext, ctx)
        c.Request = c.Request.WithContext(reqCtx)

        c.Next()
    }
}
```

Old helpers to keep: `GetTenantConfig()`, `RequireFeature()`, `GetTenantPlan()`
New helpers to add: `GetTenantContext(c)`, `GetTenantDB(c)` (moved from TenantRepos)
Remove: `TenantDBResolver()`, `SetTenantDBFactory()`, `GetTenantRepos()`, `GetCoreDB()`

#### Step 7: Update Router
**File**: `internal/router/router.go`

Replace:
```go
tenantAware.Use(middleware.TenantResolver(tenantService))
tenantAware.Use(middleware.TenantDBResolver())
```
With:
```go
tenantAware.Use(middleware.TenantResolution(tenantResolutionService))
```

**File**: `internal/router/setup.go`

- Initialize `TenantResolutionService` after `ConnectionManager`
- Remove `SetTenantDBFactory()` call (no longer needed)
- Pass `tenantResolutionService` to `Setup()`

### Verification
- `go build ./...` passes with zero errors
- All existing tests still pass (mock updates may be needed)
- `TenantResolution()` handles the same cases as old two-middleware chain

---

## Wave 04-02: Enhanced Error Handling + Tenant-Aware Logging

**Goal**: Add tenant-specific error codes, enrich error responses with school context, add tenant fields to structured logs.

### Files to Modify/Create

| # | File | Action | Description |
|---|------|--------|-------------|
| 1 | `internal/errors/errors.go` | Edit | Add tenant error codes, sentinels, constructors |
| 2 | `internal/middleware/error.go` | Edit | Enrich error responses with tenant context |
| 3 | `internal/middleware/logger.go` | Edit | Add tenant_db_host, plan fields |

### Step-by-Step

#### Step 1: Add Tenant Error Codes
**File**: `internal/errors/errors.go`

New error codes:
```go
const (
    CodeTenantDisabled       = "TENANT_DISABLED"
    CodeTenantDBUnavailable  = "TENANT_DB_UNAVAILABLE"
    CodeSubscriptionExpired  = "SUBSCRIPTION_EXPIRED"
    CodeTenantMismatch       = "TENANT_MISMATCH"
    CodeTenantNotProvisioned = "TENANT_NOT_PROVISIONED"
)
```

New sentinel errors:
```go
var (
    ErrTenantDisabled       = errors.New("school is disabled")
    ErrTenantDBUnavailable  = errors.New("tenant database unavailable")
    ErrSubscriptionExpired  = errors.New("subscription has expired")
    ErrTenantNotProvisioned = errors.New("tenant database not provisioned")
)
```

New constructors:
```go
func NewTenantDisabledError(schoolName string) *AppError { ... }
func NewTenantDBUnavailableError(schoolID uint) *AppError { ... }
func NewSubscriptionExpiredError(schoolName string) *AppError { ... }
```

Update `categoryFromCode()` to include new codes.

#### Step 2: Enrich Error Responses
**File**: `internal/middleware/error.go`

- In `writeErrorResponse()` and `writeAppError()`: extract `school_id` and `request_id` from context and add to response meta
- Add `SchoolID` field to error response when available

#### Step 3: Enhance Structured Logging
**File**: `internal/middleware/logger.go`

- After resolving tenant context, log: `school_id`, `tenant_db_host`, `plan`
- Use `GetTenantContext(c)` to extract fields

### Verification
- `go build ./...` passes
- Error responses include tenant context when available
- Logs include new tenant fields
- Existing tests still pass (new fields are additive)

---

## Backward Compatibility

| Change | Breaking? | Mitigation |
|--------|-----------|------------|
| `Claims.SchoolID` added | No | Defaults to 0, old tokens without it still parse (not a required field) |
| `GenerateAccessToken` new param | Yes | Update all callers in one commit |
| `GenerateTokenPair` new param | Yes | Update all callers in one commit |
| Remove `TenantDBResolver` middleware | Yes | Replaced by `TenantResolution` which covers same cases |
| Remove `SetTenantDBFactory` | Yes | No longer needed |
| New error codes | No | Additive, no existing code references them |
| New log fields | No | Additive |

## Dependencies
- 04-02 depends on 04-01 (needs TenantContext in middleware context)
- Both waves must pass `go build ./...` and existing tests
