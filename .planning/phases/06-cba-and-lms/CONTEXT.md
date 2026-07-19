# Phase 6: CBA Integration & Course Management

## Phase Goal
Connect the CBA exam engine to the academic gradebook, integrate CBA entities with real school data (Level/Subject FKs), and deliver a complete course management experience in the LMS — admin CRUD UI, student progress dashboard, and quiz content type powered by CBA.

## Background
Both CBA and LMS are ~5.5K lines each. The gap isn't feature volume — it's **integration and UI polish**:

- **CBA** (3,390 backend + 1,250 frontend): Full exam engine — questions, categories, papers, assignments, exam sessions (start/pause/resume/submit), auto-grading (MCQ/true-false), manual grading (essays), proctoring events. 28 endpoints. 1,250 lines of tests. **But**: scores never reach the gradebook, `Class`/`Subject` are free-text strings not FKs, no admin CBA dashboard.
- **LMS** (2,834 backend + 2,414 frontend): Full CRUD for courses/modules/lessons/enrollments/progress, assignments with submission/grading, discussions with threaded replies. 29 endpoints. 6 frontend pages. **But**: no admin CRUD UI (create/edit/delete dialogs), no student progress dashboard, file upload disabled, quiz content type has no engine.

## Plans

| # | Plan | Wave | Effort | Key Deliverable |
|---|------|------|--------|-----------------|
| 06-01 | CBA → Gradebook push | 1 | Medium | `CBAAssignment.grade_item_id` FK, `SubmitExam`/`GradeAnswer` writes to `Score` table |
| 06-02 | CBA entity integration | 1 | Small | `Class`→`Level` FK, `Subject`→`Subject` FK, exam config (schedule, max_attempts, passing_threshold, randomize) |
| 06-03 | LMS admin CRUD UI | 1 | Large | Create/edit/delete dialogs for courses, modules, lessons with rich text |
| 06-04 | Student progress dashboard | 2 | Medium | Enrolled courses with completion %, linked scores, CBA results |
| 06-05 | LMS quiz engine | 2 | Small | Wire `content_type: "quiz"` to CBA engine — reuse questions/papers |
| 06-06 | CBA → Assessment integration | 2 | Medium | Assessment.cba_assignment_id FK, auto-populate assessment scores from CBA |
| 06-07 | CBA → Intake enrollment exam | 2 | Medium | AdmissionIntake.cba_paper_id FK, applicant CBA exam flow → EntranceExamResult |

## Key Decisions

### 1. CBA → Gradebook Integration Pattern
- `CBAAssignment` gets optional `grade_item_id` FK (nullable — legacy assignments remain valid)
- On `SubmitExam` (auto-graded) and `GradeAnswer` (manual grade complete → all answered graded), push final `session.Score` as a percentage to `Score` table
- Uses existing `Score` model with `student_id`, `grade_item_id`, `score` (float), `graded_by`, `graded_at`
- No new tables, no background jobs — synchronous push in the existing transaction

### 2. CBA Entity Integration
- `CBAAssignment.Class` (string) gets a new `level_id` FK → `Level` model (nullable, backward-compatible)
- `CBAAssignment.Subject` (string) gets a new `subject_id` FK → `Subject` model (nullable)
- Existing string fields remain for display; new FK fields enable cross-referencing with gradebook
- Add `exam_config` JSONB column: `{ schedule_start, schedule_end, max_attempts, passing_threshold, randomize_questions, show_results_immediately }`

### 3. LMS Admin CRUD UI
- New route: `/_dashboard/lms/admin` (teacher/admin only, `requireRole(["admin", "teacher"])`)
- Course create/edit dialog: name, code, description, subject, level, teacher, cover image, status
- Module management: inline reorderable list within course detail, create/edit/delete
- Lesson editor: title, content type selector (video/text/pdf/quiz), rich text content, sort order
- Uses existing TanStack Query hooks from `useLMS.ts` — no new backend endpoints needed

### 4. Student Progress Dashboard
- New tab/section on existing `lms.tsx` or `_dashboard` home: "My Learning"
- Shows enrolled courses with progress bars, completion %, next lesson
- Linked assignment scores (from `AssignmentSubmission`)
- Linked CBA exam results (from `ExamSession`, after 06-01)

### 5. Quiz Engine = Reuse CBA
- When `content_type: "quiz"`, the lesson renders an inline CBA exam taking experience
- Teacher selects an existing CBA paper when creating a quiz lesson
- Reuses `StartExam`/`SubmitExam`/`GetExamResults` — no new auto-grading

### 6. CBA → Assessment Integration
- `Assessment` gets optional `cba_assignment_id` FK → `CBAAssignment` (nullable)
- When `pushScoreToGradebook` writes to `Score` table via GradeItem, it also checks if the GradeItem's Assessment has a linked CBA assignment and populates assessment scores
- Teacher links an assessment to a CBA exam from the assessment configuration UI

### 7. CBA → Intake Enrollment Exam
- `AdmissionIntake` gets optional `cba_paper_id` FK → `CBAPaper` (nullable)
- When an intake has a linked CBA paper, submitted applicants see a "Take Entrance Exam" section
- On exam submission, score is recorded in `EntranceExamResult` and application status moves to "screening"
- Admin configures the exam link on the intake setup page

## Out of Scope
- ~~No course analytics (engagement stats, completion rates)~~
- ~~No gamification / badges~~
- ~~No announcements feature~~
- ~~No content search~~
- ~~No AI-powered grading or recommendations~~
- ~~No file upload (deferred)~~
- ~~No late submission enforcement UI (backend exists)~~

## Dependencies
- Phase 5 (Gradebook Hardening) must be complete first — provides `session.status` freeze and WAEC boundary foundations that 06-01/06-02 may reference
- 06-04 depends on 06-01 (CBA scores in gradebook)
- 06-05 depends on 06-02 (entity FKs for quiz lesson context)
- 06-06 depends on 06-02 (entity FKs for exam config)
- 06-07 depends on 06-02 (entity FKs for exam config)
- Old Phase 6 (Scaling & Reliability) moves to Phase 7

## Canonical Refs
- `backend/internal/modules/cba/service.go` — CBA business logic (1,229 lines)
- `backend/internal/modules/cba/handler.go` — CBA endpoints (1,227 lines)
- `backend/internal/modules/cba/dto.go` — CBA DTOs (281 lines)
- `backend/internal/modules/lms/` — LMS module (4 files, 2,834 lines)
- `frontend/src/routes/_dashboard/lms.tsx` — LMS course catalog (93 lines)
- `frontend/src/routes/_dashboard/lms.$courseId.tsx` — LMS course detail (315 lines)
- `frontend/src/lib/hooks/useLMS.ts` — LMS hooks (370 lines)
- `frontend/src/routes/_dashboard/cba.tsx` — CBA main page (449 lines)
- `frontend/src/routes/_dashboard/cba.exams.tsx` — CBA exams list (111 lines)
- `frontend/src/routes/_dashboard/cba.exams.$examId.take.tsx` — CBA exam taking (519 lines)
- `frontend/src/routes/_dashboard/cba.exams.$examId.results.tsx` — CBA exam results (173 lines)
- `backend/internal/modules/score/` — Score module (gradebook writes)
- `backend/internal/database/models/cba.go` — CBA models
- `backend/internal/database/models/lms.go` — LMS models (8 models)
- `backend/internal/router/router.go` — Route registration (CBA: lines 414-451, LMS: lines 470-513)
- `backend/internal/modules/cba/service_test.go` — CBA test suite (1,250 lines)
