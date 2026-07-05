---
gsd_roadmap_version: 1.0
milestone: v2.1
status: active
created: 2026-07-05
---

# Roadmap: SchoolCare v2.1 — Backend Hardening

## Milestones

- ✅ **v2.0 — Multi-Tenant Database Migration** — Completed 2026-07-02
- 🏗 **v2.1 — Backend Hardening** — Error propagation, security, context, code quality

## Phases

<details>
<summary>✅ v2.0 — Multi-Tenant Database Migration (Phases 1-7) — SHIPPED 2026-07-02</summary>

- [x] **Phase 1: Foundation** (1 plan — BaseModel, UUID utilities, pgcrypto) — completed 2026-06-30
- [x] **Phase 2: Core Models** (2 plans — UUID Auth Flow + Core Repo UUID Methods) — completed 2026-06-30
- [x] **Phase 3: All Models** (1 plan — 108 model structs to UUID) — completed 2026-06-30
- [x] **Phase 4: SQL→GORM + Fresh DB** (2 plans — ~81 SQL to AutoMigrate + fresh DB) — completed 2026-07-01
- [x] **Phase 5: API Compatibility** (1 plan — UUID/int ID coexistence) — completed 2026-07-01
- [x] **Phase 6: Multi-Tenant DB Routing** (1 plan — per-school DB routing across 33 modules) — completed 2026-07-01
- [x] **Phase 7: Validation & Rollout** (1 plan — integration tests, benchmarks, verification) — completed 2026-07-02

</details>

<details open>
<summary>🏗 v2.1 — Backend Hardening (Phases 8-11) — IN PROGRESS</summary>

- [ ] **Phase 8: Error Propagation** (1 plan — replace 21 `_ =` GORM discard patterns with logging/error returns) — planned
- [ ] **Phase 9: Security Hardening** (1 plan — CSRF warning, safe DSN via net/url, DB name validation) — planned
- [ ] **Phase 10: Context Propagation** (1 plan — propagate ctx through provisioning, S3, alumni, connection manager) — planned
- [ ] **Phase 11: Code Quality** (1 plan — replace panic, add stop channel, backoff, guard assertions, goroutine lifecycle) — planned

</details>

## What's Next

After v2.1:
- Old DB decommissioning and final production rollout
- Monitoring and stabilization
- Future milestones TBD (AI integration, microservices, etc.)

## Dependencies

| Dependency | Used By |
|------------|---------|
| google/uuid v1.6.0 | UUID generation |
| pgcrypto extension | Database-level UUID generation |
| BaseModel change | All subsequent phases |
| Core model UUIDs | Academic/module UUID migration |
| GORM AutoMigrate patterns | SQL migration cleanup |
| GetTenantRepos(c) middleware | All tenant-scoped handlers |
| repos.TenantDB() | All tenant-scoped services |

---

*Archived: Full phase details in `.planning/milestones/v2.0-ROADMAP.md`*
