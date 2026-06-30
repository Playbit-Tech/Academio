# 02-01: Tenant Context Middleware + Factory Accessors

**Status:** Complete
**Completed:** 2026-06-30

## What was built

- `backend/internal/middleware/tenant.go` — Added `TenantDBResolver()` middleware + helpers
- `backend/internal/database/tenant/factory.go` — Simplified to generic DB accessor pattern

## Key details

- `TenantDBResolver()` middleware sets tenant repos in Gin context via `SetTenantDBFactory()`
- `GetTenantRepos(c)` returns `*TenantRepositories` from context (nil = core DB fallback)
- `GetTenantDB(c)` / `GetCoreDB(c)` convenience accessors
- Factory uses package-level singleton (no per-handler injection needed)
- `TenantRepositories` exposes `TenantDB()`, `CoreDB()`, `SchoolID()`
- Avoids import cycle: factory stays generic, handlers create typed repos from DB connections

## Verification

- `go build ./...` — zero errors
- All existing middleware tests pass
- No handler/repo/service interface changes required
