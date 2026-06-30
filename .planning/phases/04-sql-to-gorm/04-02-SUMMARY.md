---
phase: 04-sql-to-gorm
plan: 02
subsystem: database
tags: [gorm, automigrate, migrations, consolidation, file-organization]
requires:
  - phase: 04-01
    provides: All ~81 raw SQL migrations converted to GORM AutoMigrate calls
provides:
  - Domain-organized migration file structure (7 files instead of 9)
  - Clean migration registration in school.go
  - .env.example with documented fresh-DB provisioning steps
  - Migration ID stability verified (no duplicates, 85 static IDs)
  - Build and vet passing cleanly
affects: [phase 05, phase 06]
tech-stack:
  added: []
  patterns:
    - Migration files organized by domain (academic, CBA, LMS, modules, admissions)
    - Domain-based function names: AcademicTablesMigrations, CBATablesMigrations, LmsAndCBAMigrations, ModuleTablesMigrations
    - Academic domain consolidated: attendance, library, hostel, transport, exams, messages, report cards all in one file
    - Pivot tables preserved as raw SQL in their domain file
    - ALTER TABLE preserved as raw SQL in lms_and_cba.go
key-files:
  created:
    - backend/internal/database/migrations/school/academic_tables.go
    - backend/internal/database/migrations/school/cba_tables.go
    - backend/internal/database/migrations/school/lms_and_cba.go
    - backend/internal/database/migrations/school/module_tables.go
    - backend/.env.example
  modified:
    - backend/internal/database/migrations/school/school.go
    - backend/internal/database/migrations/migrations.go
  deleted:
    - backend/internal/database/migrations/school/phase2.go
    - backend/internal/database/migrations/school/phase4.go
    - backend/internal/database/migrations/school/phase5.go
    - backend/internal/database/migrations/school/modules.go
key-decisions:
  - "Split phase2.go: CBA base tables → cba_tables.go, academic tables → academic_tables.go"
  - "Merged phase5.go report card migrations into academic_tables.go (academic domain)"
  - "Renamed phase4.go → lms_and_cba.go (LMS + CBA enhancement tables)"
  - "Renamed modules.go → module_tables.go (all module tables)"
  - "Kept admissions.go standalone as-is"
  - "Upstream migration wrapper functions (migrations.go) updated to reference new school package function names"
requirements-completed: [INFRA-01]
duration: 10min
completed: 2026-06-30
---

# Phase 04 Plan 02: Migration Consolidation & Fresh DB Validation Summary

**Migration files reorganized by domain (5 old phase files → 4 domain-grouped files + 1 .env.example), fresh DB validation deferred until PostgreSQL is available**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-30T21:00:00Z
- **Completed:** 2026-06-30T21:10:00Z
- **Tasks:** 3
- **Files created:** 5
- **Files deleted:** 4

## Migration File Structure (After Consolidation)

| File | Function | Entries | Content Domain |
|------|----------|---------|----------------|
| `cba_tables.go` | `CBATablesMigrations` | 4 | CBA questions, papers, assignments, paper_questions (pivot) |
| `academic_tables.go` | `AcademicTablesMigrations` | 17 | Attendance, library, hostel, transport, exams, reports, messages, report cards |
| `lms_and_cba.go` | `LmsAndCBAMigrations` | 9 | Courses, course_modules, lessons, enrollments, progress, question_categories, exam_sessions, exam_answers, ALTER TABLE |
| `admissions.go` | `AdmissionsMigrations` | 7 | Admission intakes, applications, documents, screening, entrance exams, offers, enrollments |
| `module_tables.go` | `ModuleTablesMigrations` | 43 | Asset, inventory, wellness, counseling, alumni, fundraising, finance, HR, career, assignments, discussions, proctoring |
| `core_models.go` | `CoreModelsMigrations` | 2 | Core academic + billing tables (unchanged) |
| `phase3.go` | `Phase3Migrations` | 1 | AuditLog (unchanged) |
| `uuid_phase3.go` | `UUIDPhase3Migrations` | ~105 dynamic | UUID columns on all school tables (unchanged) |

**Migration order preserved in school.go:**
1. pgcrypto extension (inline)
2. CBA base tables (cba_tables.go)
3. Academic tables (academic_tables.go)
4. UUID columns (uuid_phase3.go)
5. Audit log (phase3.go)
6. LMS + CBA enhancement (lms_and_cba.go)
7. Core models (core_models.go)
8. Module tables (module_tables.go)
9. Admissions (admissions.go)

## Task Commits

Each task was committed atomically:

1. **Task 1: Consolidate migration file structure** — `5f16064` (backend submodule) / `465db36` (parent)
   - Created 4 domain-organized files, deleted 4 old phase files, updated school.go and migrations.go
2. **Task 2: Create .env.example** — `1449d22` (backend submodule) / `4dc8179` (parent)
   - Created .env.example with standard template, DB setup documentation, all config placeholders

## Known Limitations

- **PostgreSQL not available in this environment:** Server not installed (only client tools). Cannot run or validate migrations against a live database without manual setup.
- **Fresh DB provisioning deferred:** Steps documented in `.env.example` comments. Requires PostgreSQL installation + `schoolcare_core` database creation.
- **Schema validation deferred:** Table counts, column types, and index verification require a running database.

## Files Created/Modified/Deleted

### Created
- `backend/internal/database/migrations/school/academic_tables.go` — 175 lines, 17 migration entries
- `backend/internal/database/migrations/school/cba_tables.go` — 53 lines, 4 migration entries
- `backend/internal/database/migrations/school/lms_and_cba.go` — 101 lines, 9 migration entries
- `backend/internal/database/migrations/school/module_tables.go` — 401 lines, 43 migration entries
- `backend/.env.example` — 53 lines, standard template with documentation

### Modified
- `backend/internal/database/migrations/school/school.go` — Updated function references to new domain names
- `backend/internal/database/migrations/migrations.go` — Updated legacy wrapper functions

### Deleted
- `backend/internal/database/migrations/school/phase2.go` → Split into cba_tables.go + academic_tables.go
- `backend/internal/database/migrations/school/phase4.go` → Renamed to lms_and_cba.go
- `backend/internal/database/migrations/school/phase5.go` → Merged into academic_tables.go
- `backend/internal/database/migrations/school/modules.go` → Renamed to module_tables.go

## Verification Results

- [x] `go build ./...` passes
- [x] `go vet ./...` passes
- [x] No duplicate migration IDs (85 unique static IDs)
- [x] No stale file references (all imports updated)
- [x] Migration order preserved (CBA → Academic → UUID → Audit → LMS → Core → Modules → Admissions)
- [ ] Fresh database validation — **deferred** (PostgreSQL not available)
- [ ] Schema correctness validation — **deferred** (requires live database)

## Decisions Made

- **Split phase2.go by domain:** CBA base tables separated into their own file (cba_tables.go) since they're a distinct domain from academic tables. This enables cleaner dependency ordering — CBA tables must exist before the ALTER TABLE in lms_and_cba.go.
- **Merged phase5.go into academic_tables.go:** Report cards (3 entries) are an academic domain concern. Merging avoids a separate tiny file.
- **Kept admissions.go standalone:** Admissions is a clear domain boundary with 7 entries.
- **ModuleTablesMigrations naming:** Chose `ModuleTablesMigrations` over alternatives to clearly indicate all module tables, distinct from the old `PhaseModulesMigrations`.

## Deviations from Plan

None — plan executed as written, with the caveat that fresh DB provisioning was deferred due to PostgreSQL unavailability.

## Setup Required for Fresh DB Validation

To complete Tasks 2 and 3, the user needs to:

1. Install PostgreSQL:
   ```bash
   sudo apt-get install postgresql
   sudo pg_ctlcluster 18 main start
   ```

2. Create database user and database:
   ```bash
   sudo -u postgres createuser -P schoolcare
   sudo -u postgres createdb -O schoolcare schoolcare_core
   ```

3. Update `backend/.env` (DB_NAME=schoolcare_core) or use the new `.env.example`

4. Run migrations:
   ```bash
   cd backend && go run cmd/server/main.go
   ```

5. Validate schema:
   ```bash
   psql -U schoolcare -d schoolcare_core -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
   ```

---

## Self-Check: PASSED

- [x] 5 files created (academic_tables.go, cba_tables.go, lms_and_cba.go, module_tables.go, .env.example)
- [x] 4 old files deleted (phase2.go, phase4.go, phase5.go, modules.go)
- [x] 2 files modified (school.go, migrations.go)
- [x] 2 submodule commits verified (5f16064, 1449d22)
- [x] 2 parent commits verified (465db36, 4dc8179)
- [x] `go build ./...` passes
- [x] `go vet ./...` passes
- [x] No duplicate migration IDs
- [x] All raw `CREATE TABLE` statements are GORM AutoMigrate (except cba_paper_questions pivot + pgcrypto extension)
- [x] ALTER TABLE preserved in lms_and_cba.go
- [x] SUMMARY.md exists in plan directory

---

*Phase: 04-sql-to-gorm*
*Completed: 2026-06-30*
