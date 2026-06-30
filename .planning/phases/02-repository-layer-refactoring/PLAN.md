# Phase 2: Repository Layer Refactoring — Execution Plan

> Three sub-plans making all 39 module repositories tenant-aware through middleware + per-request factory resolution.

## Dependency Graph

```
Wave 1 (parallel):       02-01a (TenantContext)  02-01b (Factory helpers)
                                   |                       |
Wave 2 (parallel, 6 groups):      02-02 (Handler updates — a, b, c, d, e, f)
                                   |
Wave 3:                           02-03 (Router wiring)
```

## Plan Overview

| Plan | Wave | Depends On | Autonomous | Est. Files |
|------|------|------------|------------|------------|
| 02-01a | 1 | Phase 1 | yes | 2 (middleware/tenant.go, new) |
| 02-01b | 1 | Phase 1 | yes | 1 (tenant/helpers.go, new) |
| 02-02a | 2 | 02-01 | yes | 4 handlers (core modules) |
| 02-02b | 2 | 02-01 | yes | 9 handlers (academic group) |
| 02-02c | 2 | 02-01 | yes | 8 handlers (admin group) |
| 02-02d | 2 | 02-01 | yes | 5 handlers (communication) |
| 02-02e | 2 | 02-01 | yes | 4 handlers (facilities) |
| 02-02f | 2 | 02-01 | yes | 8 handlers (other) |
| 02-03 | 3 | 02-02 | yes | 1 (setup.go) |

## Key Constraints

- Zero changes to existing repository interfaces or structs
- Zero changes to existing services
- Handlers optionally use factory; existing functionality unchanged for non-tenant-aware paths
- Backward compatible: schools with `database_status = 'shared'` continue to work via core DB

## Success Criteria

1. TenantContext middleware extracts school_id from JWT, resolves tenant DB, and stores in Gin context
2. RepositoryFactory.ForSchool(schoolID) returns TenantRepositories with all repo accessors wired
3. Handlers optionally resolve repos from context for tenant-scoped operations
4. Core DB repos (auth, user, school, tenant) always use core DB
5. All existing tests pass unchanged — no service or repository interface changes
6. `go build ./...` passes at every wave boundary

## Detailed Plans

### 02-01a: TenantContext middleware

**Files:** `backend/internal/middleware/tenant.go` (CREATE)

Create `TenantContext` struct and middleware:

```go
package middleware

import (
    "github.com/gin-gonic/gin"
    "gorm.io/gorm"
    "github.com/playbits/schoolcare-v2/internal/database/tenant"
)

// TenantContext holds per-request tenant database resources.
type TenantContext struct {
    SchoolID uint
    TenantDB *gorm.DB
    Repos    *tenant.TenantRepositories
}

const TenantKey = "tenant"

// TenantContextMiddleware resolves the tenant database from JWT claims
// and stores it in the Gin context. Supports gradual migration — schools
// without tenant DB continue using core DB.
func TenantContextMiddleware(factory *tenant.RepositoryFactory) gin.HandlerFunc {
    return func(c *gin.Context) {
        schoolID := GetSchoolID(c) // from auth middleware claims
        if schoolID == 0 {
            c.Next()
            return
        }

        repos, err := factory.ForSchool(c.Request.Context(), schoolID)
        if err != nil {
            // Graceful degradation: log warning, continue with core DB
            c.Next()
            return
        }

        c.Set(TenantKey, &TenantContext{
            SchoolID: schoolID,
            TenantDB: repos.TenantDB(),
            Repos:    repos,
        })
        c.Next()
    }
}

// GetTenantRepos retrieves TenantRepositories from the gin context.
// Returns nil if not set (school uses core DB or single-DB mode).
func GetTenantRepos(c *gin.Context) *tenant.TenantRepositories {
    if tc, ok := c.Get(TenantKey); ok {
        return tc.(*TenantContext).Repos
    }
    return nil
}
```

### 02-01b: Factory helper accessors

**Files:** `backend/internal/database/tenant/helpers.go` (CREATE)

Add typed accessor methods to `TenantRepositories` so each module gets a clean accessor:

```go
package tenant

func (tr *TenantRepositories) Academic() *academic.AcademicRepository {
    // return from tenant DB — populated later
    return nil // TODO: Phase 2 handler wiring
}
```

Each module gets a stub accessor returning `ErrRepositoryNotImplemented`. Handlers gradually switch to using these.

### 02-02: Handler Updates (6 groups, Wave 2)

Each handler group:
1. Adds `factory *tenant.RepositoryFactory` field to handler struct
2. Constructor updated to accept factory
3. Handler methods use `GetTenantRepos(c)` to access tenant repos when available
4. Falls back to core service when tenant repos unavailable

**Example — score handler:**
```go
// BEFORE
type ScoreHandler struct {
    service *score.ScoreService
}
func NewScoreHandler(service *score.ScoreService) *ScoreHandler

// AFTER
type ScoreHandler struct {
    coreService *score.ScoreService
    factory     *tenant.RepositoryFactory
}
func NewScoreHandler(service *score.ScoreService, factory *tenant.RepositoryFactory) *ScoreHandler

func (h *ScoreHandler) ListScores(c *gin.Context) {
    repos := middleware.GetTenantRepos(c)
    if repos != nil {
        // Use tenant-DB-based computation
    } else {
        // Fall back to core service
    }
}
```

### 02-03: Router wiring (Wave 3)

**Files:** `backend/internal/router/setup.go` (MODIFY)

1. Add `repoFactory` parameter to `NewRouter()`: `func NewRouter(cfg, db, rdb, repoFactory *tenant.RepositoryFactory)`
2. Register `TenantContextMiddleware(repoFactory)` in the authenticated route group
3. Pass factory to each handler constructor

## Verification

```bash
# After each wave:
cd backend && go build ./...

# Full test suite (no regressions expected):
go test ./internal/... -count=1 -timeout 120s

# Specific middleware tests:
go test ./internal/middleware/... -v -count=1
```
