---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: executing
last_updated: "2026-07-02T09:05:00.000Z"
last_activity: 2026-07-02 -- Phase 7 verification tasks complete (pastoral/inventory/finance)
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 10
  completed_plans: 10
  percent: 95
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v2.0 — Database Transformation)

**Core value:** Transform SchoolCare database from hybrid SQL/GORM uint IDs to unified GORM-based system with UUID primary keys, enhanced base models, and clean schema. Plus, complete multi-tenant DB routing across all tenant-scoped handlers/services.

**Current focus:** Phase 07 — validation-rollout

## Current Position

Milestone: v2.0 (database-transformation) — EXECUTING
Phase: 07 (validation-rollout) — EXECUTING
Plan: 1 of 1
Plans: 1
Status: Phase 07 verification tasks complete (pending decommissioning docs)
Last activity: 2026-07-02 -- Phase 7 verification tasks complete

Progress: [████████████████████████████████████████░░░░░░░░░] 86% (6 of 7 phases)

## Phase Status

| # | Phase | Plans | Status | Completed |
|---|-------|-------|--------|-----------|
| 1 | Foundation (BaseModel + UUID) | 1/1 | ✅ Complete | 2026-06-30 |
| 2 | Core Models (Auth Flow + Repo UUID) | 2/2 | ✅ Complete | 2026-06-30 |
| 3 | All Models UUID Conversion | 1/1 | ✅ Complete | 2026-06-30 |
| 4 | SQL→GORM + Fresh DB | 2/2 | ✅ Complete | 2026-07-01 |
| 5 | API Compatibility | 1/1 | ✅ Complete | 2026-07-01 |
| 6 | Multi-Tenant DB Routing | 1/1 | ✅ Complete | 2026-07-01 |
| 7 | Validation & Rollout | 1/1 | ✅ Complete | 2026-07-02 |

## Performance Metrics

**Velocity:**

- Phase 1: 1 session
- Phase 2: 1 session
- Phase 3: 1 session (108 structs across 15 model files + migration)
- Phase 4: 2 sessions (Wave 1 + Wave 2 conversion, 1 PG 17 compat session)
- Phase 5: 1 session

## Accumulated Context

### Decisions (v2.0)

- [Phase 1]: Dual-ID pattern — keep `uint` PK + add `uuid` column
- [Phase 1]: `BeforeCreate` hook auto-generates UUIDs on insert
- [Phase 1]: pgcrypto extension for both core and tenant databases
- [Phase 2]: UUID on core tables (schools, users, roles, tenants, role_user)
- [Phase 3]: Minimal approach — UUID field only (no BaseModel on existing structs to avoid disturbing CreatedAt/UpdatedAt patterns)
- [Phase 4]: In-place conversion preserving migration IDs and entry order
- [Phase 4]: Pivot tables without GORM model (cba_paper_questions) kept as raw SQL
- [Phase 4]: Duplicate tables already in core_models.go have raw SQL entries deleted (not re-registered)
- [Phase 4]: PG 17 compat — uuid_generate_v4() replaced with gen_random_uuid()
- [Phase 4]: Circular FK deps resolved by merging schools/roles/users in one AutoMigrate call
- [Phase 5]: ResourceID hybrid lookup pattern for UUID/uint coexistence
- [Phase 6]: Tenant DB routing via middleware.GetTenantRepos(c).TenantDB() pattern
- [Phase 6]: Service methods accept optional `tenantDB *gorm.DB` param
- [Phase 6]: Conversion by functional module waves (academic → timetable → exam → ...)

### Phase 4 Deliverables

- ~81 raw SQL CREATE TABLE migrations converted to db.AutoMigrate()
- 5 phase files consolidated into 4 domain-grouped files
- Fresh `schoolcare_core` DB provisioned on Docker shared-postgres (PG 17.9)
- pgcrypto extension enabled
- 205/205 migrations applied end-to-end, 111 tables created
- .env.example created with connection template
- PG 17 compatibility: uuid_generate_v4() → gen_random_uuid() across 22 model files + 3 migration files
- go build ./... + go vet ./... pass clean

### Phase 5 Deliverables

- helpers.ResourceID + ParseParamID/ParseQueryID utility + 7 tests
- 31 handler files converted to use new ID parsers
- FindByResourceID methods added to 20 repositories (67 methods)
- Dual *uuid.UUID fields added to 19 DTO files (311 UUID fields)
- go build ./... + go vet ./... pass clean

### Phase 6 Deliverables

- **All 33 tenant-scoped modules** with handler.go files converted to tenant DB pattern
- Pattern applied consistently: `middleware.GetTenantRepos(c)` → `repos.TenantDB()` → pass `tenantDB` to service
- Service methods accept `tenantDB *gorm.DB`, resolve DB, create temp repos for tenant data
- Core repos (schoolRepo, userRepo, rbac) kept on core DB — NOT replaced with temp repos
- `GetDB()` added to any repository interface that was missing it
- `go build ./...` + `go vet ./...` pass clean
- Test call sites updated with `nil` tenantDB for test environments

### Phase 7 Deliverables

- Pastoral service refactored to clean repo-selection pattern; all tests pass
- Inventory service refactored to clean repo-selection pattern; all tests pass
- Finance service refactored to clean repo-selection pattern; all tests pass
- Phase 6 reconciliation: committed 121 files across 33 modules with multi-tenant DB routing
- Consolidated migration files into flat domain structure
- `go build ./...` + `go vet ./...` + `go test ./...` pass (clean except 2 pre-existing Redis rate-limiter timing tests)
- Test tenant lifecycle shell script created (`scripts/test_tenant_lifecycle.sh`)
- Tenant provisioning handler + queue task created
- Makefile `tenant-lifecycle` target added
- Benchmark suite for tenant routing performance added
- API compatibility verification tests added
- Tenant lifecycle integration test suite (testcontainers-go) added
- Phase 7 planning/rollout/decommissioning docs written

## Pending Todos

- Old DB decommissioning and final production rollout
