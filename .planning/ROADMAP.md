---
gsd_roadmap_version: 1.0
milestone: v2.0
status: active
created: 2026-06-30
---

# Roadmap: SchoolCare Database Transformation

## Milestones

- ✅ **v2.0-alpha — Foundation** — Phases 1-2 (shipped 2026-06-30)
- 🚧 **v2.0-beta — Full Conversion** — Phases 3-7 (Phases 3-5 complete, 6 executing, 7 pending)

## Phases

<details>
<summary>✅ v2.0-alpha — Foundation (Phases 1-2) — SHIPPED 2026-06-30</summary>

- [x] **Phase 1: Foundation** (1 plan — BaseModel, UUID utilities, pgcrypto) — completed 2026-06-30
- [x] **Phase 2: Core Models** (2 plans — UUID Auth Flow + Core Repo UUID Methods) — completed 2026-06-30

</details>

### 🚧 v2.0-beta — Full Conversion (In Progress)

- [x] **Phase 3: All Models** (1 plan) — Convert 108 model structs to UUID — completed 2026-06-30
- [x] **Phase 4: SQL→GORM + Fresh DB** (2 plans) — Convert ~81 SQL migrations to AutoMigrate + fresh DB — completed 2026-07-01
- [x] **Phase 5: API Compatibility** (1 plan) — Accept both UUID and int IDs — completed 2026-07-01
- [ ] **Phase 6: Multi-Tenant DB Routing** (1 plan) — Convert tenant-scoped handlers/services to use per-school DB connections — 🚧 Executing
- [ ] **Phase 7: Validation & Rollout** (1 plan) — Integration tests, staged switch-over, old DB decommission — ⏳ Pending

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Foundation | v2.0-alpha | 1/1 | ✅ Complete | 2026-06-30 |
| 2. Core Models | v2.0-alpha | 2/2 | ✅ Complete | 2026-06-30 |
| 3. All Models | v2.0-beta | 1/1 | ✅ Complete | 2026-06-30 |
| 4. SQL→GORM + Fresh DB | v2.0-beta | 2/2 | ✅ Complete | 2026-07-01 |
| 5. API Compatibility | v2.0-beta | 1/1 | ✅ Complete | 2026-07-01 |
| 6. Multi-Tenant DB Routing | v2.0-beta | 0/1 | 🚧 Executing | - |
| 7. Validation & Rollout | v2.0-beta | 0/1 | ⏳ Pending | - |

## Phase Details

### Phase 4: SQL→GORM + Fresh DB ✅
- **Goal:** Convert all ~81 remaining SQL-based migrations to GORM AutoMigrate, eliminate raw SQL migration files, and provision a fresh database with the clean schema.
- **Status:** ✅ Complete (2026-07-01)
- **Plans:** 2/2

**Plan 01 — Convert Raw SQL to AutoMigrate (Wave 1):**
- All ~81 raw CREATE TABLE migrations replaced with `db.AutoMigrate()`
- Core models (Subject, Level, Student, Teacher, Bill, Fee, Payment) deduplicated
- Pivot table `cba_paper_questions` kept as raw SQL (no GORM model)
- `go build ./...` and `go vet ./...` pass

**Plan 02 — Consolidate + Fresh DB (Wave 2):**
- 5 phase files consolidated into 4 domain-grouped files
- Fresh `schoolcare_core` DB on Docker shared-postgres (PG 17.9)
- pgcrypto extension enabled
- 205/205 migrations applied, 111 tables created
- PG 17 compat: uuid_generate_v4() → gen_random_uuid() across 25 files

### Phase 5: API Compatibility ✅
- **Goal:** Accept both UUID and int IDs in route params, query params, and request bodies.
- **Status:** ✅ Complete (2026-07-01)
- **Plans:** 1/1

Plans:
- [x] 05-01-PLAN.md — Core ID utility + handler conversion + DTO dual fields + repository methods

**Key Deliverables:**
- `helpers.ResourceID` + `ParseParamID`/`ParseQueryID` utility + 7 tests
- 31 handler files converted to use new ID parsers
- `FindByResourceID` methods added to 20 repositories (67 methods)
- Dual `*uuid.UUID` fields added to 19 DTO files (311 UUID fields)
- `go build ./...` and `go vet ./...` pass clean

### Phase 6: Multi-Tenant DB Routing 🚧
- **Goal:** Convert all tenant-scoped handler/service methods to use per-school dedicated databases via `middleware.GetTenantRepos(c).TenantDB()` pattern.
- **Status:** 🚧 Executing (2026-07-01)
- **Plans:** 1 plan (multiple waves)

**Scope:** ~28 modules with tenant-scoped data need conversion. Wave 1 covers academic + timetable.

**Pattern (established in user module):**
```go
// Handler:
repos := middleware.GetTenantRepos(c)
tenantDB := repos.TenantDB()
result, err := h.service.Method(ctx, tenantDB, schoolID, req)

// Service:
func (s *Service) Method(ctx context.Context, tenantDB *gorm.DB, schoolID uint, req *Req) (*Model, error) {
    db := s.repo.GetDB()
    if tenantDB != nil { db = tenantDB }
    // Use db for operations
}
```

### Phase 7: Validation & Rollout
- **Goal:** Integration tests, staged switch-over, old DB decommission.
- **Status:** ⏳ Pending
- **Plans:** 1 plan

## Dependencies

| Dependency | Used By |
|------------|---------|
| google/uuid v1.6.0 | Already in go.mod |
| pgcrypto extension | Database-level UUID generation |
| BaseModel change | All subsequent phases |
| Core model UUIDs | Academic/module UUID migration |
| GORM AutoMigrate patterns | SQL migration cleanup |
| GetTenantRepos(c) middleware | All tenant-scoped handlers |
| repos.TenantDB() | All tenant-scoped services |
