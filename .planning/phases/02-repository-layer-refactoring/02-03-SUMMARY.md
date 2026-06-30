# 02-03: Router Wiring

**Status:** Complete
**Completed:** 2026-06-30

## What was built

- `backend/internal/router/setup.go` — Multi-tenant infrastructure initialization
- `backend/internal/router/router.go` — TenantDBResolver middleware registration

## Key details

- `NewRouter` initializes: `crypto.Service` → `ConnectionManager` → `RepositoryFactory`
- `middleware.SetTenantDBFactory()` called during startup
- `TenantDBResolver()` registered in `tenantAware` route group (after `TenantResolver`)
- Conditional on `ENCRYPTION_KEY` being set — no key = single-DB mode (no tenant resolution)
- Import aliasing: `tenant` (database/tenant) vs `tenantModule` (modules/tenant)

## Middleware chain (authenticated routes)

```
JWTAuth → EnforceSchoolID → TenantResolver (plan/features)
→ TenantDBResolver (DB connection) → AuditLogging → Handler
```

## Verification

- `go build ./...` — zero errors
- `go test ./internal/middleware/...` — all pass
- Backend submodule pushed: `916caae`
