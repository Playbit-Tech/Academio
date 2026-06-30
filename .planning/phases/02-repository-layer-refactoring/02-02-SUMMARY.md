# 02-02: Handler Updates

**Status:** Complete (minimal — middleware-based approach)
**Completed:** 2026-06-30

## Approach

Handlers do NOT need structural changes in Phase 2. The middleware pattern means:

1. `middleware.TenantDBResolver()` runs before every authenticated request
2. Handlers call `middleware.GetTenantRepos(c)` to get tenant DB connections
3. When tenant DB is available: `academic.NewAcademicRepository(repos.TenantDB())`
4. When not available (single-DB mode): use existing core service

## Benefits

- Zero changes to handler structs or constructors
- Zero changes to service interfaces
- Zero changes to repository interfaces
- Handlers opt-in to tenant DB per-method
- Backward compatible for all 39 modules
