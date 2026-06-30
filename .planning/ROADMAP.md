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

- [ ] **Phase 3: All Models** (1 plan) — Convert ~95 remaining model structs to UUID
- [ ] **Phase 4: SQL→GORM + Fresh DB** (1 plan) — Convert ~81 SQL migrations to AutoMigrate
- [ ] **Phase 5: API Compatibility** (1 plan) — Accept both UUID and int IDs
- [ ] **Phase 6: Validation & Rollout** (1 plan) — Staged switch-over, old DB decommission

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. Foundation | v2.0-alpha | 1/1 | ✅ Complete | 2026-06-30 |
| 2. Core Models | v2.0-alpha | 2/2 | ✅ Complete | 2026-06-30 |
| 3. All Models | v2.0-beta | 0/1 | ⏳ Pending | - |
| 4. SQL→GORM + Fresh DB | v2.0-beta | 0/1 | ⏳ Pending | - |
| 5. API Compatibility | v2.0-beta | 0/1 | ⏳ Pending | - |
| 6. Validation & Rollout | v2.0-beta | 0/1 | ⏳ Pending | - |

## Dependencies

| Dependency | Used By |
|------------|---------|
| google/uuid v1.6.0 | Already in go.mod |
| pgcrypto extension | Database-level UUID generation |
| BaseModel change | All subsequent phases |
| Core model UUIDs | Academic/module UUID migration |
| GORM AutoMigrate patterns | SQL migration cleanup |
