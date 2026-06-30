---
gsd_roadmap_version: 1.0
milestone: v2.0
status: active
created: 2026-06-30
---

# Roadmap: SchoolCare Database Transformation

## Milestones

- ✅ **v2.0-alpha — Foundation** — Phases 1-2 (shipped 2026-06-30)
- 🚧 **v2.0-beta — Full Conversion** — Phases 3-6 (in progress)

## Phases

<details>
<summary>✅ v2.0-alpha — Foundation (Phases 1-2) — SHIPPED 2026-06-30</summary>

- [x] **Phase 1: Foundation** (1 plan — BaseModel, UUID utilities, pgcrypto) — completed 2026-06-30
- [x] **Phase 2: Core Models** (2 plans — UUID Auth Flow + Core Repo UUID Methods) — completed 2026-06-30

</details>

### 🚧 v2.0-beta — Full Conversion (In Progress)

- [x] **Phase 3: All Models** (1 plan) — Convert 108 model structs to UUID — completed 2026-06-30
- [ ] **Phase 4: SQL→GORM + Fresh DB** (2 plans) — Convert ~81 SQL migrations to AutoMigrate + fresh DB
- [ ] **Phase 5: API Compatibility** (1 plan) — Accept both UUID and int IDs
- [ ] **Phase 6: Validation & Rollout** (1 plan) — Staged switch-over, old DB decommission

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Foundation | v2.0-alpha | 1/1 | ✅ Complete | 2026-06-30 |
| 2. Core Models | v2.0-alpha | 2/2 | ✅ Complete | 2026-06-30 |
| 3. All Models | v2.0-beta | 1/1 | ✅ Complete | 2026-06-30 |
| 4. SQL→GORM + Fresh DB | v2.0-beta | 0/2 | 🔵 Planned | - |
| 5. API Compatibility | v2.0-beta | 0/1 | ⏳ Pending | - |
| 6. Validation & Rollout | v2.0-beta | 0/1 | ⏳ Pending | - |

## Phase Details

### Phase 4: SQL→GORM + Fresh DB
- **Goal:** Convert all ~81 remaining SQL-based migrations to GORM AutoMigrate, eliminate raw SQL migration files, and provision a fresh database with the clean schema.
- **Status:** 🔵 Planned
- **Plans:** 2 plans

**Plan 01 — Convert Raw SQL to AutoMigrate (Wave 1):**
- `school/phase2.go`: Replace raw CREATE TABLE with AutoMigrate for attendance, CBA, books, hostels, transport, exam, reports, messages
- `school/phase4.go`: Replace raw SQL with AutoMigrate for LMS + CBA tables  
- `school/phase5.go`: Replace raw SQL with AutoMigrate for report cards
- `school/admissions.go`: Replace raw SQL with AutoMigrate for admissions tables
- `school/modules.go`: Replace raw SQL with AutoMigrate for modules tables
- Verify existing AutoMigrate coverage to avoid double-registration
- `go build ./...` and `go vet ./...` must pass

**Plan 02 — Consolidate + Fresh DB (Wave 2):**
- Consolidate migration file structure, merge domain-grouped files
- Remove deprecated raw SQL files (phase2, phase4, phase5, admissions, modules after conversion)
- Provision fresh database, run all migrations end-to-end
- Validate schema correctness (table count, column types, indexes)
- `go build ./...` and `go vet ./...` must pass

**Details:**
- Keep `school/core_models.go` (already AutoMigrate) — verify no overlap
- Keep `school/phase3.go` (already AutoMigrate — AuditLog)
- Keep `school/uuid_phase3.go` (Phase 3 ALTER TABLE for UUID columns)
- Keep ReusableMigrator pattern (migrator.go) as-is
- Keep raw SQL for `pgcrypto` extension and certain ALTER TABLE operations

### Phase 5: API Compatibility
- **Goal:** Accept both UUID and int IDs in route params, query params, and request bodies.
- **Status:** ⏳ Pending
- **Plans:** 1 plan

### Phase 6: Validation & Rollout
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
