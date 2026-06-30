# Phase 2: Repository Layer Refactoring — Research

**Researched:** 2026-06-30
**Domain:** Multi-tenant repository/service wiring, tenant context middleware
**Confidence:** HIGH

## Summary

Phase 2 makes all 39 module repositories tenant-aware through the `RepositoryFactory` built in Phase 1. The key insight is that **repositories themselves need minimal changes** — they already accept `*gorm.DB` and use `WithContext(ctx)` correctly. The real work is in the **wiring layer**: `router/setup.go` (694 lines) currently creates every repository with a single core `*gorm.DB`. Phase 2 changes handlers to resolve tenant-specific connections per-request via the factory.

## Architecture Overview

```
Request → Auth Middleware → Tenant Context Middleware → Handler
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
              JWT Claims          ConnectionManager
              (school_id)         → GetTenantDB(schoolID)
                                     → tenant *gorm.DB
                              │
                              ▼
                     RepositoryFactory.ForSchool(schoolID)
                     → TenantRepositories { Auth, School, User, Academic, Score, ... }
```

### Key Decision: Per-request Repositories vs. Constructor Injection

| Approach | Pros | Cons |
|----------|------|------|
| **Per-request via factory** (recommended) | Zero service changes; handlers resolve repos from factory each request; clean separation | More object churn per request; handler signatures change |
| **Constructor injection** | Services get DB at construction time | Stateful services break; can't handle multi-school requests; complex lifecycle management |

**Recommendation:** Per-request factory resolution. Handlers call `factory.ForSchool(ctx, schoolID)` to get `TenantRepositories`, then pass the relevant repo to the service method. Services continue to accept repository interfaces as they do today.

### What Changes

1. **Handlers** (~39 handler files) — each handler currently stores service references. They need to either:
   - a) Accept a `*RepositoryFactory` and resolve per-request (change handler structs)
   - b) Accept resolved `TenantRepositories` (e.g., inject into Gin context via middleware)

2. **Services** (~38 service files) — NO structural changes needed. All services already accept repository interfaces. The same interface types work with tenant DB repos.

3. **Repositories** (~35 repository files) — NO structural changes. All accept `New*Repository(db *gorm.DB)` and use `r.db.WithContext(ctx)`. The same pattern works with tenant connections.

## Existing Codebase Patterns

### Repository Pattern (ALL 35 repositories)
```go
type AcademicRepository struct {
    db *gorm.DB  // ← just a *gorm.DB — no concept of "core" vs "tenant"
}

func NewAcademicRepository(db *gorm.DB) *AcademicRepository {
    return &AcademicRepository{db: db}
}

func (r *AcademicRepository) FindByID(ctx context.Context, id uint) (*Model, error) {
    return r.db.WithContext(ctx).First(...).Error  // ← uses WithContext
}
```

### Wiring Pattern (router/setup.go)
```go
// Currently all repos created with core DB:
academicRepo := academic.NewAcademicRepository(db)    // db = core DB
scoreRepo := score.NewScoreRepository(db)              // db = core DB
resultRepo := result.NewResultRepository(db)           // db = core DB

// Future: handlers get repos from factory per-request:
func (h *AcademicHandler) ListSessions(c *gin.Context) {
    repos := h.factory.ForSchool(c, getSchoolID(c))
    sessions, err := repos.Academic().ListSessions(c, ...)
}
```

### Module Inventory (39 modules, 35 with repositories)

| Category | Modules | Repos | Service | Tenant Data? |
|----------|---------|-------|---------|-------------|
| **Core** | auth, user, school, tenant, rbac | Yes | Yes | ✗ (cross-tenant) |
| **Academic** | academic, score, result, exam, cba, reportcard, reportbuilder, reports, lms | Yes | Yes | ✓ (per-school) |
| **Admin** | admission, bill, payment, finance, hr, inventory, audit, analytics | Yes | Yes | ✓ (per-school) |
| **Communication** | messages, notifications, communication, invitation, multimedia | Yes | Yes | ✓ (per-school) |
| **Facilities** | hostel, transport, library, timetable | Yes | Yes | ✓ (per-school) |
| **Student Services** | pastoral, health, career, alumni, parentdashboard | Yes | Yes | ✓ (per-school) |
| **Other** | proctoring, dashboard, ai | Yes | Yes | Mixed |

**Tenant data split**: ~30 modules are per-school (tenant DB), ~5 modules are cross-tenant (core DB).

## Approach: Tenant Context Middleware + Per-Request Factory

### Step 1: TenantContext struct
```go
// internal/middleware/tenant.go
type TenantContext struct {
    SchoolID uint
    TenantDB *gorm.DB
    Repos    *tenant.TenantRepositories
}

const TenantKey = "tenant" // gin.Context key
```

### Step 2: Tenant Context Middleware
```go
func TenantContextMiddleware(factory *tenant.RepositoryFactory) gin.HandlerFunc {
    return func(c *gin.Context) {
        claims := jwt.GetClaims(c) // from auth middleware
        if claims == nil || claims.SchoolID == 0 {
            c.Next()
            return
        }
        
        repos, err := factory.ForSchool(c.Request.Context(), claims.SchoolID)
        if err != nil {
            // If tenant DB unavailable, log warning but allow through with core DB
            // (graceful degradation for partially-migrated schools)
            c.Next()
            return
        }
        
        c.Set(TenantKey, &TenantContext{
            SchoolID: claims.SchoolID,
            TenantDB: repos.TenantDB(),
            Repos:    repos,
        })
        c.Next()
    }
}
```

### Step 3: Handler factory accessor helper
```go
// Helper for handlers to get repos
func GetTenantRepos(c *gin.Context) *tenant.TenantRepositories {
    if tc, ok := c.Get(TenantKey); ok {
        return tc.(*TenantContext).Repos
    }
    return nil  // caller falls back to core repos
}
```

### Step 4: Handler updates (example)
```go
// BEFORE
type AcademicHandler struct {
    service *academic.AcademicService
}
func (h *AcademicHandler) ListSessions(c *gin.Context) {
    sessions, err := h.service.ListSessions(c, schoolID)
}

// AFTER
type AcademicHandler struct {
    coreService *academic.AcademicService  // core (if needed)
    factory     *tenant.RepositoryFactory
}
func (h *AcademicHandler) ListSessions(c *gin.Context) {
    repos := GetTenantRepos(c)
    // Use repos.Academic() from tenant DB
}
```

## Execution Strategy

### Wave 1 (parallel): Infrastructure
- **02-01a**: Create TenantContext struct + middleware in `internal/middleware/tenant.go`
- **02-01b**: Add `GetTenantRepos()` helper + `TenantRepository` accessor functions in `internal/database/tenant/`
- **02-01c**: Wire `RepositoryFactory` into `router.NewRouter()` signature

### Wave 2 (parallel, 6 groups): Handler updates
Group by domain — each group is independent:
- **02-02a**: Core handlers (auth, user, school, tenant) — keep core DB
- **02-02b**: Academic handlers (academic, score, result, exam, cba, reportcard, reportbuilder, reports, lms)
- **02-02c**: Admin handlers (admission, bill, payment, finance, hr, inventory, audit, analytics)
- **02-02d**: Communication handlers (messages, notifications, communication, invitation, multimedia)
- **02-02e**: Facilities handlers (hostel, transport, library, timetable)
- **02-02f**: Other handlers (pastoral, health, career, alumni, parentdashboard, proctoring, dashboard, ai)

### Wave 3: Setup.go wiring
- **02-03**: Update `router/setup.go` — pass factory to handlers, register middleware

## Key Design Decisions

1. **Middleware-first**: Tenant DB resolution happens once per request in middleware, not per-repo call. Single point of configuration.
2. **Graceful degradation**: If tenant DB is unavailable, handlers fall back to core DB (supporting gradual rollout per the Phase 1 requirement).
3. **No service changes**: Services stay clean — they accept repository interfaces, not DB connections. Tested services don't need re-testing.
4. **Handler struct gets factory**: Instead of storing 15+ service references, handlers optionally get the factory for per-request tenant repo resolution.
5. **Core DB repos always available**: Auth, user, school, tenant repos stay on core DB. Factory always provides both.

## Anti-Patterns to Avoid

- **Don't put DB in request context directly** — wrap in TenantContext struct for type safety
- **Don't modify service interfaces** — they're tested and stable; keep the interface-contract boundary
- **Don't remove core DB fallback** — gradual migration means some schools won't have tenant DBs for months
- **Don't mix tenant and core DB in the same repository instance** — one repo, one DB
- **Don't cache tenant DB per request in handler** — middleware already handles this

## State of the Art

| Old Approach | New Approach | When |
|-------------|-------------|------|
| `NewRouter(cfg, db, rdb)` | `NewRouter(cfg, db, rdb, repoFactory)` | Phase 2 |
| Handler stores service refs | Handler stores factory + resolves per-request | Phase 2 |
| `service.Method(ctx, schoolID)` | `repos.Academic().Method(ctx, schoolID)` via middleware | Phase 2 |

## Verification Strategy
- `go build ./...` — must pass after each wave
- `go test ./internal/modules/...` — existing tests must pass (no service/repo interface changes)
- New middleware unit tests
- Router compiles with new factory parameter

## Open Questions

1. **How many handlers need per-request tenant resolution vs. can use middleware-injected repos directly?**
   - Via middleware: handlers that only touch tenant data (most handlers)
   - Via factory directly: handlers that need both core and tenant data (mixed handlers)
2. **Should handler constructors change to accept factory, or should we use a different DI approach?**
3. **What's the fallback behavior when a school has `database_status = 'shared'` (not yet migrated)?** — use core DB

## Confidence

- Repository patterns: HIGH — 35 repos verified, all identical `db *gorm.DB` pattern
- Service patterns: HIGH — 38 services verified, all accept interfaces
- Handler wiring: MEDIUM — 40+ handler structs need factory injection
- Middleware approach: HIGH — standard Go/Gin pattern
