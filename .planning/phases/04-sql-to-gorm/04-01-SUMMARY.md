---
phase: 04-sql-to-gorm
plan: 01
subsystem: database
tags: [gorm, automigrate, migrations, sql-to-gorm, postgres]
requires:
  - phase: 03-all-models-uuid
    provides: All ~108 model structs with UUID fields and TableName() methods
provides:
  - All ~81 raw SQL CREATE TABLE migrations replaced with GORM AutoMigrate calls
  - 5 migration files converted (phase2, phase4, phase5, admissions, modules)
  - Pivot table (cba_paper_questions) preserved as raw SQL
  - ALTER TABLE preserved as raw SQL
  - All migration IDs and entry order preserved
affects: [phase 04-02, phase 05, phase 06]
tech-stack:
  added: []
  patterns:
    - Migration files use db.AutoMigrate(&models.X{}) instead of raw CREATE TABLE
    - Rollback uses db.Migrator().DropTable(&models.X{}) instead of DROP TABLE CASCADE
    - Pivot tables without model structs kept as raw SQL with explicit ID
    - ALTER TABLE schema modifications kept as raw SQL where no GORM equivalent exists
key-files:
  created: []
  modified:
    - backend/internal/database/migrations/school/phase2.go
    - backend/internal/database/migrations/school/phase4.go
    - backend/internal/database/migrations/school/phase5.go
    - backend/internal/database/migrations/school/admissions.go
    - backend/internal/database/migrations/school/modules.go
key-decisions:
  - "Removed redundant index-creation migration entries that are now handled by GORM struct tags"
  - "Kept cba_paper_questions pivot table as raw SQL since it has no corresponding GORM model struct"
  - "Kept ALTER TABLE for cba_questions columns (category_id, difficulty) as raw SQL"
patterns-established:
  - "Conversion pattern: CREATE TABLE raw SQL → db.AutoMigrate(&models.X{}) with matching model"
  - "Pivot tables without model structs remain as raw SQL CREATE TABLE with preserved migration ID"
  - "ALTER TABLE / schema modifications remain as raw SQL entries"
requirements-completed: [INFRA-01]
duration: 15min
completed: 2026-06-30
---

# Phase 04 Plan 01: SQL-to-GORM AutoMigrate Conversion Summary

**All ~81 raw SQL CREATE TABLE migrations in school directory converted to GORM AutoMigrate calls, with pivot table and ALTER TABLE special cases preserved**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-30T20:45:00Z
- **Completed:** 2026-06-30T20:46:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- **phase2.go**: 18 entries converted — attendance, CBA questions/papers/assignments, books/issues, hostels/beds, transport routes/vehicles/assignments, exam schedules/results, reports, messages/recipients, notifications. Removed 2 redundant index entries handled by struct tags. Preserved cba_paper_questions pivot as raw SQL.
- **phase4.go**: 8 entries converted — courses, course_modules, lessons, course_enrollments, lesson_progress, question_categories, exam_sessions, exam_answers. ALTER TABLE for cba_questions preserved as raw SQL.
- **phase5.go**: 3 entries converted — report_cards, report_card_subjects, report_card_comments.
- **admissions.go**: 7 entries converted — admission_intakes, applications, application_documents, screening_results, entrance_exam_results, admission_offers, enrollments.
- **modules.go**: 43 entries converted — asset, inventory, wellness, counseling, alumni (careers/events/attendees/mentorships), fundraising (campaigns/donations), verification, job board, finance (chart_of_accounts/journal/budget/expense/vendor), HR (departments/staff/leaves/payroll/payslips/attendance/appraisals/recruitments/documents), career (profiles/assessments/recommendations), report_configs, alumni_insights, LMS (assignments/submissions/discussions), proctoring_events.

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert phase2.go** — `cec2ede` (feat)
2. **Task 2: Convert phase4.go + phase5.go + admissions.go** — `2260d24` (feat)
3. **Task 3: Convert modules.go** — `20f61a5` (feat)

## Files Created/Modified

- `backend/internal/database/migrations/school/phase2.go` — 18 entries, +33/-304 lines
- `backend/internal/database/migrations/school/phase4.go` — 8 AutoMigrate + 1 ALTER TABLE entry, +20/-208 lines
- `backend/internal/database/migrations/school/phase5.go` — 3 entries, +8/-80 lines
- `backend/internal/database/migrations/school/admissions.go` — 7 entries, +11/-200 lines
- `backend/internal/database/migrations/school/modules.go` — 43 entries, +87/-747 lines

## Decisions Made

- **Removed redundant index entries** — Separate migration entries for `idx_attendance_timetable_date` and `idx_attendance_student_id` were removed because these indexes are already defined via `gorm:"index:idx_name"` struct tags, which AutoMigrate handles automatically.
- **Kept cba_paper_questions raw SQL** — This is a pivot/join table with no corresponding GORM model struct. The `many2many` tag on `CBAPaper.Questions` uses this table, but there's no model to AutoMigrate.
- **Kept ALTER TABLE raw SQL** — The `category_id` and `difficulty` column additions to `cba_questions` are schema modifications, not table creation, and have no direct GORM equivalent.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All 5 school migration files converted from raw SQL to AutoMigrate
- Ready for Phase 04 Plan 02 (consolidation and fresh database validation)
- `go build ./...` and `go vet ./...` both pass cleanly

---

## Self-Check: PASSED

- [x] All 5 migration files exist and are modified
- [x] 3 task commits verified (cec2ede, 2260d24, 20f61a5)
- [x] SUMMARY.md exists in plan directory
- [x] `go build ./...` passes
- [x] `go vet ./...` passes
- [x] Only 1 raw `CREATE TABLE IF NOT EXISTS` remaining (cba_paper_questions pivot — intentional)
- [x] ALTER TABLE preserved (phase4.go — intentional)
- [x] No double-registration of tables already covered by core_models.go

---

*Phase: 04-sql-to-gorm*
*Completed: 2026-06-30*
