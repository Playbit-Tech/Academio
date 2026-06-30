---
gsd_roadmap_version: 1.0
milestone: v2.0
status: planning
created: 2026-06-30
---

# Roadmap: SchoolCare Database Transformation

## Milestone Summary

| # | Phase | Focus | Est. Effort |
|---|-------|-------|-------------|
| 1 | Foundation | Enhanced BaseModel, UUID utilities, pgcrypto | Medium |
| 2 | Core Models | School, User, Role, Tenant UUID conversion | Medium |
| 3 | All Models | Academic, LMS, CBA, Financial, HR, Admin (~95 structs) | Large |
| 4 | SQL→GORM Cleanup | Convert ~81 SQL migrations to AutoMigrate, fresh DB | Large |
| 5 | API Compatibility | Accept both UUID and int IDs, update handlers | Medium |
| 6 | Validation & Rollout | Integration tests, staged switch-over, old DB decommission | Medium |

## Execution Order

```
Phase 1 (Foundation)
  └── Phase 2 (Core Models) — depends on Phase 1
        └── Phase 3 (All Models) — depends on Phase 2 pattern
              └── Phase 4 (SQL→GORM + Fresh DB) — depends on Phase 3
                    └── Phase 5 (API Compatibility) — depends on Phase 3
                          └── Phase 6 (Validation & Rollout) — depends on all
```

## Phase Details

### Phase 1: Foundation
- Add UUID field to BaseModel alongside existing uint ID
- Create `Model` and `TenantAwareModel` interfaces
- UUID utility functions (GenerateUUID, ParseUUID)
- Pgcrypto extension setup
- Dual-ID pattern: uint (existing) + uuid (new) during transition

### Phase 2: Core Models
- School model: add UUID, update references
- User, Role models: add UUID, update auth middleware
- Tenant model: add UUID, align with ConnectionManager
- Repository updates for core models

### Phase 3: All Models
- Academic: Student, Teacher, Class, Subject, Level, Session, Attendance
- LMS: Course, Lesson, Assignment, Submission, Grade
- CBA: Question, Paper, Answer, Score
- Financial: Fee, Bill, Payment, Invoice, Transaction
- HR: Staff, Leave, Payroll, Appraisal
- Administrative: Inventory, Library, Hostel, Transport
- Everything else (~95 structs total)

### Phase 4: SQL→GORM + Fresh DB
- Convert all ~81 remaining SQL migrations to GORM AutoMigrate
- Remove SQL migration files
- Update ReusableMigrator to use AutoMigrate where possible
- Create `schoolcare_core` database
- Run all GORM migrations against fresh DB
- Validate schema matches expected structure

### Phase 5: API Compatibility
- Route params accept both UUID and int IDs
- Query params compatible with both formats
- Request body parsing handles both
- Response format consistency
- Middleware updates for UUID-based auth

### Phase 6: Validation & Rollout
- Integration tests for UUID-backed API endpoints
- Cross-tenant isolation verification with UUIDs
- Performance benchmarking (UUID vs int)
- Staged switch-over (pilot → limited → full)
- Old database backup and decommissioning

## Dependencies

| Dependency | Used By |
|------------|---------|
| google/uuid v1.6.0 | Already in go.mod |
| pgcrypto extension | Database-level UUID generation |
| BaseModel change | All subsequent phases |
| Core model UUIDs | Academic/module UUID migration |
| GORM AutoMigrate patterns | SQL migration cleanup |
