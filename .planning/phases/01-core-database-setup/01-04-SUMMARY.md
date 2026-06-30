# 01-04: RepositoryFactory

**Status:** Complete
**Completed:** 2026-06-29

## What was built

- `backend/internal/database/tenant/factory.go` — `RepositoryFactory` struct with:
  - `NewRepositoryFactory(connManager, coreDB)` constructor
  - `ForSchool(schoolID)` returning `TenantRepositories` with both tenant DB and core DB access
  - `TenantRepositories` struct grouping repository accessors per school
  - `ErrRepositoryNotImplemented` sentinel error for unimplemented types

## Design

- **Core DB repos** (Auth, School, User) always use the shared core database — these handle cross-tenant data
- **Tenant DB repos** are stubbed with `ErrRepositoryNotImplemented` — Phase 2 will populate them
- Matches existing `New*Repository(db *gorm.DB)` constructor pattern exactly
- `TenantRepositories` exposes `TenantDB()`, `CoreDB()`, and `SchoolID()` for direct access when needed
- Bridge pattern to Phase 2 where all 30+ module repositories will be accessible through the factory

## Dependencies

- 01-03: DatabaseConnectionManager (for tenant DB connections)
