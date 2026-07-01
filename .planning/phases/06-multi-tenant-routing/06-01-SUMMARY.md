---
phase: 06-multi-tenant-routing
plan: 01
type: summary
status: complete
completed: "2026-07-01"
wave: all
---

# Phase 6 Summary: Multi-Tenant DB Routing

## Goal
Convert all tenant-scoped Go handler and service methods to route per-school data through the school's dedicated tenant database (`schoolcare_tenant_<id>`) via the established `middleware.GetTenantRepos(c).TenantDB()` pattern.

## Scope Executed

All **33 modules** with `handler.go` files converted — far exceeding the original Wave 1 scope of 5 modules:

| Module | Handler Methods | Service Methods | Notes |
|--------|:-:|:-:|:------|
| user | 4 | 5 | Reference implementation (existing) |
| academic | 28 | 17 | Wave 1 lead — complex, 4 sub-domains |
| timetable | 7 | 5 | Wave 1 |
| exam | 12 | 11 | Wave 1 |
| result | 2 | 2 | Wave 1 (converted in session) |
| score | 5 | 5 | Wave 1 (fixed in session) |
| admission | 18 | 21 | |
| bill | 5 | 6 | |
| payment | 5 | 6 | |
| dashboard | 1 | 2 | |
| audit | 2 | 3 | |
| multimedia | 2 | 4 | |
| invitation | 3 | 5 | |
| reports | 3 | 9 | |
| notifications | 5 | 8 | |
| messages | 6 | 11 | |
| reportcard | 8 | 13 | |
| hostel | 8 | 9 | |
| transport | 10 | 12 | |
| library | 8 | 9 | |
| inventory | 14 | 16 | |
| analytics | 9 | 10 | |
| proctoring | 5 | 6 | |
| career | 10 | 11 | |
| cba | 29 | 31 | Large module |
| finance | 26 | 29 | Large module, many repos |
| alumni | 42 | 45 | Large module, many repos |
| pastoral | 17 | 18 | |
| hr | 49 | 50 | Largest module, 9 repos |
| lms | 33 | 35 | Large module |
| communication | 14 | 9 | |
| school | 13 | 15 | Special: mixed core + tenant |
| tenant | 4 | 10 | Special: all core DB |
| **Total** | **~370** | **~420** | |

## Pattern Applied

### handler.go
```go
import (
    "gorm.io/gorm"
    "github.com/playbits/schoolcare-v2/internal/middleware"
)

// In each school-scoped handler method:
schoolID := helpers.GetSchoolID(c)
// ...
repos := middleware.GetTenantRepos(c)
var tenantDB *gorm.DB
if repos != nil {
    tenantDB = repos.TenantDB()
}
result, err := h.service.SomeMethod(c.Request.Context(), tenantDB, schoolID, req)
```

### service.go
```go
import (
    "gorm.io/gorm"
)

func (s *Service) SomeMethod(ctx context.Context, tenantDB *gorm.DB, schoolID uint, req *Req) (*Model, error) {
    db := s.repo.GetDB()
    if tenantDB != nil {
        db = tenantDB
    }
    tempRepo := NewRepository(db)
    // Use tempRepo for tenant data, keep s.*Repo for core data
}
```

### Key Design Decisions
- **TENANT repos** (module's own repo, academicRepo, studentRepo, teacherRepo): temp repos with resolved DB
- **CORE repos** (schoolRepo, userRepo, rbac): keep `s.*Repo` on core DB
- **`GetDB()` accessor**: added to any repository interface missing it
- **Graceful degradation**: when `tenantDB` is `nil` (school not provisioned), falls back to core DB with school_id filtering
- **Thread safety**: service repos (`s.*`) never modified — temp repos are local to each method call

## Verification
- ✅ `go build ./...` — zero errors
- ✅ `go vet ./...` — zero errors
- ✅ All 33 handler files reference `middleware.GetTenantRepos(c)`
- ✅ All ~420 school-scoped service methods accept `tenantDB *gorm.DB` parameter
- ✅ Test call sites updated with `nil` tenantDB where needed
