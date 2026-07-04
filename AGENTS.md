## Goal
Implement Phase 3 of the Curriculum & Assessment Model (per-grade-item score recording + rollup), fix the onboarding cache invalidation bug, and add a Curriculum step to the onboarding flow.

## Constraints & Preferences
- Enforce under/over 100 validation on both backend and frontend for grade item scores and rollups.
- Seeded classes/subjects must appear immediately after school creation without manual reload.
- Curriculum step must appear on the onboarding page between Subjects and Session, with defaults pre-filled (like classes and subjects).

## Progress
### Done
- Phase 1 (GradeItem CRUD Backend) and Phase 2 (Nested Curriculum Frontend+Backend) marked completed in `plans/curriculum-assessment-roadmap.md` and `plans/STATE.md`.
- `Score` model: added nullable `GradeItemID` (FK) and `ScoreValue` fields.
- `POST /academic/grade-item-score` endpoint: upsert per-grade-item score.
- `POST /academic/scores/rollup` endpoint: roll up grade item scores into assessment total.
- Added `grade_item_id` filter to `ListScores` handler.
- Backend validation: score clamped to `[0, grade_item.max_score]`, FK mismatch rejected, rollup requires all grade items scored, result bounded to `[0, assessment.total]`.
- Added `useGradeItemScores`, `useSaveGradeItemScore`, `useRollupScores` hooks and exported from `hooks/index.ts`.
- Built `GradeItemScoreEntry` component with per-item inputs, live total calculation, per-item save, Save All, and Rollup button.
- Integrated `GradeItemScoreEntry` into Teacher Academics page with subject/assessment/class selectors.
- Ran `make db-init DROP_TENANT=true`, `make migrate`, `make seed` to recreate and seed the database.
- **Fixed backend onboarding bug**: Added `DatabaseStatus` to `SchoolResponse`, updated `Get` handler, added `GetDB()` to `SchoolService`, fixed `ListSubjects`/`ListLevels` to return empty arrays when `tenantDB` is nil.
- **Added Curriculum step to onboarding**: Between Subjects (step 2) and Session (step 4). Uses reusable `CurriculumForm` component. Defaults are now fetched from the backend (seeded assessment + grade items via provisioning) rather than hardcoded—same polling + pre-fill pattern as classes/subjects.
- **Added `seedDefaultGradeItems` in provisioning.go**: Creates a default `Assessment` ("Terminal Examination", total=100) with three `GradeItem` rows (CA1=20, CA2=20, Exam=60) when a new tenant DB is provisioned.
- **Created reusable `CurriculumForm` component** at `src/components/academics/curriculum-form.tsx` — same plain `useState` pattern as `CurriculumDrawer` in `school.tsx`; handles curriculum name, description, multiple assessments with grade items, add/remove, total validation. Used by onboarding step 3.
- **Created `useAssessmentGradeItems` hook** in `useAcademics.ts` — fetches grade items for a given assessment ID via `GET /academic/grade-item?assessment_id=X`.
- **Added `gradeItems` query key** in `query-keys.ts`.
- Both `go build ./...` and `yarn tsc --noEmit` pass clean after all changes.
- **Fixed API URL mismatch**: Frontend hooks in `useSchool.ts` were calling `/schools/levels?school_id=X` (query param) but backend routes are `/:id/levels` (path param). Updated all 6 hooks to use path params.
- **Fixed class pre-fill field name**: Changed `level: String(...)` to `class_level: (l.class)?.level as number ?? 1` — the reusable `ClassFormFields` component reads `class_level`, not `level`.
- **Added missing `<form>` wrappers**: Steps 2 (Subjects) and 4 (Session) had `type="submit"` buttons without a containing `<form>`.
- **CurriculumForm UI polish**: Grade items in 2-column grid with card styling (`p-4 rounded-xl border`); delete/add buttons fixed from overflowing (added `min-w-0`, reduced gap, `w-16` score input).
- **Assessment total guards**: "Add Assessment" disabled when `assessmentsTotal >= 100`; "Create Curriculum" disabled when `Math.round(assessmentsTotal) !== 100`; remaining marks hint shown.
- **Fixed `footer` prop**: Was defined in interface but never destructured/rendered in `CurriculumForm`.
- **Removed duplicate back button** below `CurriculumForm` in onboarding step 3.
- **Fixed JSX in Next button**: Was raw string `"Next <ChevronRight/>"`, now proper `<><span>Next</span> <ChevronRight/></>` fragment.
- **Fixed `AssessmentCurriculum` model**: Removed `ID uint gorm:"primaryKey"` — the `assessment_curriculum` table was created by GORM's many2many as a join table with composite PK `(assessment_id, curriculum_id)` and no `id` column. The explicit model with a separate `ID` field caused GORM to generate `RETURNING "uuid","id"` on INSERT, which failed with `column "id" does not exist`. Changed to composite `gorm:"primaryKey"` on both FK fields, matching `SessionCurriculum`'s pattern.

### In Progress
- *(none)*

### Blocked
- *(none)*

## Key Decisions
- Added `GradeItemID` as nullable FK on existing `scores` table (Option A from plan) to keep assessment-level rollup scores alongside per-grade-item scores.
- Placed score entry UI in Teacher Academics page with per-student expandable cards rather than a flat table.
- Fixed the onboarding polling issue at the backend level (returning `database_status` + empty data when tenant not provisioned).
- Used existing `useCreateCurriculum` + `POST /academic/curriculum` for the onboarding curriculum step instead of creating individual assessment/grade-item endpoints.

## Next Steps
1. Re-test the full onboarding flow end-to-end — verify that after school creation, polling picks up `database_status`, and the Curriculum step creates the curriculum/assessments/grade items correctly.
2. Verify the full score entry → rollup flow works in Teacher Academics.

## Critical Context
- `.env` connects to `shared-postgres` container at `localhost:5432`, user `postgres`, database `academio`.
- Super admin credentials after seed: `playbit / Password123!`.
- The provisioning task (background) seeds default levels and subjects AFTER `POST /schools` returns, which is why the frontend must poll until `database_status` changes from `"pending"` to `"active"`.
- `models.School` in Go does NOT have a `DatabaseStatus` field — the column is added dynamically via raw SQL and must be queried separately.
- Use `make db-init DROP_TENANT=true && make migrate && make seed` to reset the database.

## Relevant Files
- `backend/internal/modules/school/dto.go`: Added `DatabaseStatus` field to `SchoolResponse`.
- `backend/internal/modules/school/handler.go`: Updated `Get` to include `database_status`; fixed `ListSubjects`/`ListLevels` to return empty when tenantDB nil.
- `backend/internal/modules/school/service.go`: Added `GetDB()` method to `SchoolService`.
- `backend/internal/database/tenant/provisioning.go`: Seeds default levels and subjects asynchronously.
- `backend/internal/modules/academic/dto.go`: `CreateCurriculumRequest`, `CreateAssessmentInput`, `CreateGradeItemInput` DTOs.
- `frontend/src/routes/_onboarding/onboarding.tsx`: Added Curriculum step (step 3) with curriculum name, assessment name, and grade items. Uses `useCreateCurriculum`.
- `frontend/src/lib/hooks/useAcademics.ts`: `useCreateCurriculum` hook.
- `frontend/src/routes/_dashboard/school.tsx`: `CurriculumDrawer` component for full curriculum management.
- `frontend/src/components/academics/curriculum-form.tsx`: Reusable `CurriculumForm` component (used by onboarding step 3). Same state-management pattern as `CurriculumDrawer`.
- `frontend/src/components/academics/grade-item-score-entry.tsx`: Reusable `GradeItemScoreEntry` component.
- `plans/curriculum-assessment-roadmap.md`: Roadmap with all 3 phases.
- `plans/STATE.md`: Project state tracking.
