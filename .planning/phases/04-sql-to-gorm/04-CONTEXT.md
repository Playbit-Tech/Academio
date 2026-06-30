# Phase 4: SQL→GORM + Fresh DB - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning
**Source:** Codebase analysis + ROADMAP.md

<domain>
## Phase Boundary

**Goal:** Replace all raw SQL migration files with GORM AutoMigrate calls, eliminate manual CREATE TABLE/INDEX statements, consolidate the migration architecture, and provision a fresh database with the clean schema.

**What this phase delivers:**
1. All ~81 raw SQL migrations converted to `db.AutoMigrate(&models.X{})` calls
2. Raw SQL files either deleted or reduced to minimal ALTER TABLE/index-only files
3. Migration file consolidation — cleaner organization by domain
4. `schoolcare_core` database provisioned (or verified existing connection)
5. All migrations execute successfully against fresh DB
6. Schema validated — `go build ./...` and `go vet ./...` both pass

**What this phase does NOT deliver:**
- API compatibility layer (Phase 5)
- Integration tests or staged rollout (Phase 6)
- Data migration from old database
</domain>

<decisions>
## Implementation Decisions

### D-01: Use GORM AutoMigrate for all entity tables
Every raw `CREATE TABLE IF NOT EXISTS` migration MUST be replaced with `db.AutoMigrate(&models.{X}{})`. GORM already has model structs for every table created by raw SQL (verified by Phase 3's UUID addition work). The `TableName()` methods on models ensure correct table names.

### D-02: Keep raw SQL for pgcrypto extension and certain ALTER TABLE
`CREATE EXTENSION IF NOT EXISTS "pgcrypto"` cannot be done via AutoMigrate — keep as raw SQL. ALTER TABLE migrations that add columns to existing tables (e.g., `alter_cba_questions_add_category`) must be kept as raw SQL but can be converted to `db.Migrator().AddColumn()` where possible.

### D-03: Explicit index creation for composite/non-standard indexes
GORM AutoMigrate creates indexes from struct tags (`gorm:"uniqueIndex:idx_name"`), but composite unique indexes spanning foreign keys ("school_id, code", "school_id, account_code") need explicit `db.Migrator().CreateIndex()` calls or must be handled by struct tag definitions. Verify each migration's index requirements against existing model struct tags.

### D-04: Consolidate migration file organization
After conversion, merge related migrations into domain-grouped files rather than the current "phaseN" naming. Use consistent `{YYYY}_{MM}_{DD}_000000_{description}` migration ID format. Keep the `school.go` registration pattern but clean up the file list.

### D-05: Keep the ReusableMigrator pattern
The existing `ReusableMigrator` (migrator.go) is well-designed and supports both core and tenant databases. Do NOT replace it. The conversion is about the migration CONTENT, not the runner.

### D-06: Fresh database vs existing
The target is a fresh database. Create/verify `schoolcare_core` database connection via `DATABASE_URL` in `.env`. Run both core migrations and school migrations against it to validate.

### D-07: Remove deprecated migration files
After migration content is fully converted, remove the old SQL-heavy migration files. Specifically:
- `phase2.go` — convert to AutoMigrate, then delete or reduce
- `phase4.go` — convert to AutoMigrate, then delete
- `phase5.go` — convert to AutoMigrate, then delete
- `admissions.go` — convert to AutoMigrate, then delete
- `modules.go` — convert to AutoMigrate, then delete
- `core_models.go` — already AutoMigrate, keep and consolidate
- `phase3.go` — already AutoMigrate (AuditLog), keep
- `uuid_phase3.go` — keep (Phase 3 UUID column additions)

### the agent's Discretion
- Whether to keep raw SQL index-creation migrations inside domain-grouped files vs separate index migration files
- Exact file naming for consolidated migration files
- Whether to add missing model structs if any raw SQL table lacks one (verified through Phase 3 — all tables have corresponding models)
- How to handle the migration tracking tables (`schema_migrations`, `tenant_schema_migrations`)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Migration Architecture
- `backend/internal/database/migration/types.go` — Migration struct definition
- `backend/internal/database/migrations/migrator.go` — ReusableMigrator pattern
- `backend/internal/database/migrations/migrations.go` — Migration registration
- `backend/internal/database/migrations/school/school.go` — School migration list
- `backend/internal/database/migrations/school/phase2.go` — Raw SQL to convert (largest file)
- `backend/internal/database/migrations/school/phase4.go` — Raw SQL to convert (LMS + CBA)
- `backend/internal/database/migrations/school/phase5.go` — Raw SQL to convert (report cards)
- `backend/internal/database/migrations/school/admissions.go` — Raw SQL to convert
- `backend/internal/database/migrations/school/modules.go` — Raw SQL to convert (largest)
- `backend/internal/database/migrations/school/core_models.go` — Reference: already uses AutoMigrate
- `backend/internal/database/migrations/school/phase3.go` — Reference: already uses AutoMigrate
- `backend/internal/database/migrations/core/phase1.go` — Reference: core AutoMigrate pattern

### GORM Model Definitions
- `backend/internal/database/models/school.go` — School, Subject, Level, Student, Teacher, Bill, Fee, Payment, Multimedia, Timetable, Invitation, StudentParent, CBA*, Book, BookIssue, Hostel, HostelBed, Transport*, ExamSchedule, ExamResult, Report, Message, MessageRecipient, Notification, Asset*, Wellness*, Survey*, Counseling*, Alumni*, Mentorship, Donation, FundraisingCampaign, VerificationRequest, JobBoardPost
- `backend/internal/database/models/lms.go` — Course, CourseModule, Lesson, CourseEnrollment, LessonProgress, Assignment, AssignmentSubmission, DiscussionThread, DiscussionPost, ProctoringEvent
- `backend/internal/database/models/cba.go` — QuestionCategory, ExamSession, ExamAnswer
- `backend/internal/database/models/hr.go` — Department, Staff, LeaveRequest, PayrollPeriod, Payslip, StaffAttendance, Appraisal, RecruitmentPost, StaffDocument
- `backend/internal/database/models/finance.go` — Invoice, Transaction, ChartOfAccount, JournalEntry, JournalLine, Budget, BudgetLine, Expense, Vendor
- `backend/internal/database/models/admission.go` — AdmissionIntake, Application, ApplicationDocument, ScreeningResult, EntranceExamResult, AdmissionOffer, Enrollment
- `backend/internal/database/models/reportcard.go` — ReportCard, ReportCardSubject, ReportCardComment
- `backend/internal/database/models/career.go` — CareerProfile, CareerAssessment, CareerRecommendation
- `backend/internal/database/models/attendance.go` — Attendance
- `backend/internal/database/models/session.go` — Session, SessionCurriculum
- `backend/internal/database/models/curriculum.go` — Curriculum, AssessmentCurriculum
- `backend/internal/database/models/assessment.go` — Assessment
- `backend/internal/database/models/score.go` — Score
- `backend/internal/database/models/result.go` — Result
- `backend/internal/database/models/audit_log.go` — AuditLog
- `backend/internal/database/models/communication.go` — CommunicationTemplate, CommunicationMessage, CommunicationCampaign, DeliveryLog
- `backend/internal/database/models/analytics.go` — AnalyticsSnapshot, AnalyticsMetric
- `backend/internal/database/models/alumni_insight.go` — AlumniInsight
- `backend/internal/database/models/report_config.go` — ReportConfig
- `backend/internal/database/models/base.go` — BaseModel

### Core Migrations (for reference)
- `backend/internal/database/migrations/core/core.go` — Core migration registration
- `backend/internal/database/migrations/core/phase1.go` — Core AutoMigrate pattern (School, User, Role, etc.)
</canonical_refs>

<specifics>
## Migration Inventory

### Raw SQL migrations to convert (with corresponding model check):

| File | Tables | Model Exists? | TableName() Override |
|------|--------|--------------|---------------------|
| `phase2.go` | attendance | ✅ Attendance | default |
| | cba_questions | ✅ CBAQuestion | `cba_questions` |
| | cba_papers | ✅ CBAPaper | `cba_papers` |
| | cba_assignments | ✅ CBAAssignment | `cba_assignments` |
| | cba_paper_questions | Pivot table — may need model or raw SQL | - |
| | books | ✅ Book | `books` |
| | book_issues | ✅ BookIssue | `book_issues` |
| | hostels | ✅ Hostel | `hostels` |
| | hostel_beds | ✅ HostelBed | `hostel_beds` |
| | transport_routes | ✅ TransportRoute | `transport_routes` |
| | transport_vehicles | ✅ TransportVehicle | `transport_vehicles` |
| | transport_assignments | ✅ TransportAssignment | `transport_assignments` |
| | exam_schedules | ✅ ExamSchedule | `exam_schedules` |
| | exam_results | ✅ ExamResult | `exam_results` |
| | reports | ✅ Report | `reports` |
| | messages | ✅ Message | `messages` |
| | message_recipients | ✅ MessageRecipient | `message_recipients` |
| | notifications | ✅ Notification | `notifications` |
| `phase4.go` | courses | ✅ Course | default |
| | course_modules | ✅ CourseModule | default |
| | lessons | ✅ Lesson | default |
| | course_enrollments | ✅ CourseEnrollment | default |
| | lesson_progress | ✅ LessonProgress | default |
| | question_categories | ✅ QuestionCategory | default |
| | exam_sessions | ✅ ExamSession | default |
| | exam_answers | ✅ ExamAnswer | default |
| | cba_questions (ALTER) | — | Keep as raw/migrator |
| `phase5.go` | report_cards | ✅ ReportCard | default |
| | report_card_subjects | ✅ ReportCardSubject | default |
| | report_card_comments | ✅ ReportCardComment | default |
| `admissions.go` | admission_intakes | ✅ AdmissionIntake | default |
| | applications | ✅ Application | default |
| | application_documents | ✅ ApplicationDocument | default |
| | screening_results | ✅ ScreeningResult | default |
| | entrance_exam_results | ✅ EntranceExamResult | default |
| | admission_offers | ✅ AdmissionOffer | default |
| | enrollments | ✅ Enrollment | default |
| `modules.go` | Asset categories + inventory | ✅ AssetCategory, InventoryAsset | TableName() defined |
| | All other modules | ✅ See model files | TableName() defined |

### Already using AutoMigrate (keep/consolidate):
- `core_models.go` — Subject, Level, Student, etc.
- `phase3.go` — AuditLog

### Special cases:
- `uuid_phase3.go` — Raw SQL ALTER TABLE to add UUID column — keep as-is (Phase 3 deliverable)
- `cba_paper_questions` — Pivot table (may need model or raw SQL)
</specifics>

<deferred>
## Deferred Ideas

- None — Phase 4 scope is fully captured above.
</deferred>

---

*Phase: 04-sql-to-gorm*
*Context gathered: 2026-06-30 via codebase analysis*
