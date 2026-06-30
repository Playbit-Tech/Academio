# Phase 4 Research: Enhanced Auth & Tenant Resolution

## Current State Analysis

### Auth Flow
1. User authenticates via `/auth/login` -> receives JWT + refresh token
2. JWT claims: `user_id`, `email`, `role`, `token_type`, `family_id`, `jti`, `exp`, `iat`, `iss`
3. **No `school_id` in JWT** -- school context is per-request via `x-school-id` header
4. `SchoolID()` middleware (global) extracts `x-school-id` -> stores in context
5. `JWTAuth()` middleware validates JWT -> stores `user_id`, `role`, `claims`
6. `EnforceSchoolID()` middleware ensures school_id present for non-super-admin
7. `TenantResolver()` loads tenant config (plan, features, limits) from Redis->DB
8. `TenantDBResolver()` gets tenant DB connection from `RepositoryFactory.ForSchool()`

### Token Service
- `TokenService.GenerateTokenPair()` -> calls `jwtSvc.GenerateAccessToken(user.ID, email, role, familyID)`
- No school_id is passed to token generation
- Role is a simple string like "admin", "teacher", "student", "parent"

### Multi-School User Model
- A single user can belong to multiple schools via `role_user` pivot table
- Login response includes `Schools []School` and `Role` -- client picks school and sends `x-school-id`
- `buildUserResponse()` resolves user's school associations from the DB

### Tenant Resolution (Current)
- `TenantResolver` middleware -> loads `TenantConfig` (plan/features/limits) via `TenantConfigResolver`
- `TenantDBResolver` middleware -> calls `RepositoryFactory.ForSchool(schoolID)` for GORM connection
- Both have graceful degradation: if tenant DB unavailable, fall back to core DB

### Error Handling
- `AppError` with categories: AUTH, AUTHZ, VALID, BUS, SYS, EXT
- Error codes cover: NOT_FOUND, CONFLICT, AUTH_FAILED, TOKEN_EXPIRED, etc.
- **No tenant-specific error codes exist** (no TENANT_DISABLED, TENANT_DB_UNAVAILABLE, etc.)

### Logging
- `log/slog` JSON output to stdout
- Current fields: method, path, status, latency_ms, remote_ip, request_id, user_id, tenant_id
- **Missing**: `tenant_db_host`, `school_id` (uses tenant_id alias), `plan`

### Redis Usage
- JWT blacklist (`blacklist:<jti>`)
- Rate limiting (sorted sets)
- Tenant config cache (5 min TTL)
- Refresh token cache (opaque tokens)

## Design Decisions

### Decision 1: Embed SchoolID in JWT Claims
**Approach**: Add `SchoolID uint` to `Claims` struct. Populated:
- At login: if user has exactly 1 school, embed it; if multiple, set to 0
- At token refresh: carry over from existing claims
- No dedicated school-switch endpoint needed -- `x-school-id` header continues to work for multi-school users

**Rationale**:
- Satisfies "JWT tokens carry tenant routing information" (GSD-R10)
- Backward compatible: `x-school-id` header still takes precedence when present
- Users with single school have seamless auth -- no header needed
- Users with multiple schools continue current behavior

### Decision 2: TenantResolutionService -- Unify Resolution in One Place
**Approach**: New `TenantResolutionService` that combines school lookup, status check, DB resolution, and caching into a single method `ResolveTenant(ctx, schoolID, userID)`. Used by a new `TenantResolutionMiddleware` that replaces the current `TenantResolver` + `TenantDBResolver` pair.

**Rationale**:
- Single entry point for all tenant resolution logic
- Redis cache covers the full context (not just config)
- Easier to test and instrument
- Eliminates the two-step middleware dance

### Decision 3: Keep Middleware Chain Order
**Approach**: The new `TenantResolutionMiddleware` runs in the same position as current `TenantResolver` (after JWTAuth + EnforceSchoolID, before route handlers). The old `TenantDBResolver` becomes redundant and is removed.

### Decision 4: Graceful Degradation Preserved
- If tenant DB unavailable -> still fall back to core DB
- If school not found or disabled -> return specific error with new codes (TENANT_DISABLED, TENANT_DB_UNAVAILABLE)
- If subscription expired -> return SUBSCRIPTION_EXPIRED error

## Components to Build

### 04-01: TenantResolutionService (~7 files)
1. `pkg/jwt/jwt.go` -- Add SchoolID to Claims + update GenerateAccessToken/GenerateTokenPair
2. `internal/database/tenant/types.go` -- TenantContext struct
3. `internal/database/tenant/resolution_service.go` -- Resolution service + Redis cache
4. `internal/middleware/tenant.go` -- Replace TenantResolver+TenantDBResolver with TenantResolutionMiddleware
5. `internal/services/token_service.go` -- Pass school_id through token generation
6. `internal/modules/auth/service.go` -- Update Login to resolve school_id for JWT
7. `internal/router/router.go` + `setup.go` -- Update middleware chain and wiring

### 04-02: Enhanced Error Handling + Logging (~4 files)
1. `internal/errors/errors.go` -- Add tenant error codes + sentinels + constructors
2. `internal/middleware/error.go` -- Enrich error response with tenant context
3. `internal/middleware/logger.go` -- Add tenant_db_host, plan fields
4. Router wiring -- Ensure tenant context available when errors/logging fire

## Key Interfaces

```go
// TenantResolutionService resolves JWT + school -> complete tenant context
type TenantResolutionService struct {
    coreDB      *gorm.DB
    connManager *ConnectionManager
    rdb         *redis.Client
    cacheTTL    time.Duration
}

func (s *TenantResolutionService) ResolveTenant(ctx, schoolID, userID) (*TenantContext, error)
func (s *TenantResolutionService) InvalidateCache(ctx, schoolID) error

type TenantContext struct {
    SchoolID           uint
    SchoolName         string
    Plan               string
    DatabaseName       string
    DatabaseHost       string
    Status             string     // "active", "disabled", "suspended"
    SubscriptionStatus string     // "active", "expired", "trial"
    UserID             uint
    Permissions        []string
    TenantDB           *gorm.DB   // nil if shared DB mode
}
```

## Dependencies
- `04-02` depends on `04-01` (needs TenantContext in context for enriched logging/errors)
- Both sub-plans can be validated independently with `go build ./...` + existing tests
