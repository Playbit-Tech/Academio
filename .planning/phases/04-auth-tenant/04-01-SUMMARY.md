# 04-01: TenantResolutionService — Summary

## Objective
Single entry point that resolves JWT + school_id -> full TenantContext with Redis caching.

## What Was Built

### Files Created
- `internal/database/tenant/tenant_context.go` — `TenantContext` struct (School, SchoolConnection, Plan, DB), cache key helpers (`TenantCacheKey`, `TenantCacheLockKey`), `CtxKeyTenantContext` constant
- `internal/database/tenant/resolution_service.go` — `TenantResolutionService` with `ResolveTenant` (school lookup → status check → DB → Redis cache 5-min TTL), `InvalidateCache`, `WarmCache`. Graceful degradation when Redis unavailable.

### Files Modified
- `pkg/jwt/jwt.go` — Added `SchoolID uint` to `Claims` struct. Updated `GenerateAccessToken` / `GenerateTokenPair` to accept `schoolID` param.
- `internal/services/token_service.go` — Forwarded `schoolID` through to JWT generation.
- `internal/modules/auth/service.go` — `buildUserResponse` returns `primarySchoolID`; login embeds it; register passes `0`.
- `internal/modules/auth/service_test.go` — Updated mock/direct calls with `, 0` schoolID.
- `internal/database/tenant/factory.go` — Added `NewTenantRepositories()` constructor for backward compat.
- `internal/middleware/tenant.go` — Added `TenantResolution()` middleware (replaces old two-step pattern), `GetTenantContext()` helper, `configFromTenantContext()` builder, `setMinimalTenantDefaults()` fallback. Updated `GetTenantDB()` to check `TenantContext` first.
- `internal/router/router.go` — Replaced `TenantResolver` + `TenantDBResolver` with single `TenantResolution` middleware.
- `internal/router/setup.go` — Created `TenantResolutionService` with 5-min cache TTL; wired into Setup()

## Verification
- `go build ./...` passes
- `go vet ./...` passes
- Backward compatibility: existing middleware ctx keys (`CtxKeyTenantConfig`, `CtxKeyTenantPlan`, `CtxKeyTenantRepos`) still set by new middleware
