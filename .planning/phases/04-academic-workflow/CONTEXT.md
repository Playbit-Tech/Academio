# Phase 4: Academic Workflow — Context & Decisions

## Phase Goal
Complete academic year lifecycle with automated rollover, WAEC/NECO external exam tracking, stable student identifiers, and student promotion/graduation.

## Requirements
YEAR-01, YEAR-02, YEAR-03, YEAR-04, YEAR-05, WAEC-01, WAEC-02, WAEC-03, WAEC-04, WAEC-05

## Plans
- [x] **04-01: End-of-Year workflow** — Grade finalization, session completion, score archival
- [x] **04-02: Stable student identifiers** — `admission_number` as cross-year stable key, re-enrollment without duplication
- [x] **04-03: WAEC external exam model** — ExternalExamResult with exam_type/sitting_number/grade/credit_flag, CSV import, credit count computation, multi-sitting tracking
- [x] **04-04: Student promotion/graduation** — Auto-promote to next class, graduate, PromotionRecord snapshot, Alumni auto-create, frontend UI

## Key Decisions

### Score Archival (04-01)
- **ArchivedScore model** stores a complete JSON snapshot of each student's Score blob at archive time — queryable, immutable, per-assessment/per-student
- No `school_id` column on `ArchivedScore` (model is denormalized, school context resolved through Assessment/Student relationships)
- Group 21 migration creates `archived_scores` table
- Archival runs during session completion, not as a separate endpoint

### Stable Student Identifiers (04-02)
- `admission_number` already existed on the `students` table as a unique+stable field — no new column needed
- Re-enrollment: `POST /api/v2/students/:id/reactivate` — sets `deleted_at = NULL`, updates `session_id`
- Identifier generation: auto-generated on student creation, also settable via CSV import / bulk create

### External Exam Integration (04-03)
- **ExternalExamResult model** tracks per-student subject results per-sitting — composite unique on `(admission_number, exam_type, sitting_number, subject)`
- **Credit count** computed as `SELECT COUNT(DISTINCT subject) WHERE credit_flag = true AND exam_type = 'WAEC'`
- **Best result per subject** across sittings: `SELECT DISTINCT ON (subject) ... ORDER BY subject, grade ASC` (A1=best)
- **CSV import** uses preview-then-confirm pattern matching existing batch error collection (per-row, not fail-fast)
- Grades follow WAEC A1-F9 (+ NECO equivalents) — mapped to boolean `credit_flag` (A1-C6 = true)

### Student Promotion/Graduation (04-04)
- **PromotionRecord model** stores per-student JSON snapshot (scores, level, session, status) for each promotion cycle
- **Alumni auto-create**: When a student graduates (promoted beyond highest level), an Alumni record is created inside the promotion transaction via log-and-continue (best-effort, non-blocking)
- **Frontend**: Standalone `/promotion` route with Promote tab (select third-term session → preview cards with keep-behind toggle → confirm dialog) and History tab (completed third-term sessions)
- `applyPromotions` accepts optional `sessionID` parameter to scope promotion to a specific session

### Bugs Fixed During Implementation
- **`database_status` default**: Changed column default from `'active'` to `'pending'` — synchronous provisioning checks status first and silently skipped when default was `'active'`
- **FK migration ordering**: Migration `2026_07_15_000004_add_remaining_cross_schema_fk_constraints` tried to add FKs for `archived_scores`/`external_exam_results`/`promotion_records` before Group 22 created them — moved FK creation into Group 22
- **ArchivedScore missing school_id**: Removed FK constraint for `archived_scores` since model lacks a `school_id` column

## Success Criteria
1. ✅ Admin can execute end-of-year workflow — grade finalization, session completion, grade archiving, student promotion or graduation
2. ✅ Admin can record WAEC/NECO external exam results (A1-F9) with sitting numbers
3. ✅ WAEC credit count computes automatically (A1-C6 including English and Mathematics) — multi-sitting tracking
4. ✅ Admin can import WAEC results from CSV with validation before committing
5. ✅ Student can be re-enrolled using stable admission_number — reactivation workflow restores previous records

## Verification
- 62/62 integration tests pass (health → CSRF → register → login → school create → provisioning → curriculum → assessments → sessions → grade items → sum-to-100 → teacher → staff → student+parents → XLSX import)
- `go build ./...` and `go vet ./...` pass clean
- Frontend: `npx tsc --noEmit` and `yarn build` pass clean
