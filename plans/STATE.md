# Project State: Curriculum & Assessment Model

## Project Reference
- **Repository:** academio (schoolcare-v2)
- **Stack:** Go (Gin/GORM) backend, React (Vite/TanStack Router/shadcn/ui) frontend
- **Core Value:** Replace flat assessment scoring with nested Curriculum → Assessment → Grade Item hierarchy

## Current Position

| Phase | Status | Started | Completed |
|---|---|---|---|
| 1 — GradeItem CRUD | ✅ Completed | — | 2026-07-04 |
| 2 — Nested Curriculum | ✅ Completed | — | 2026-07-04 |
| 3 — Per-Grade-Item Scoring | ✅ Completed | 2026-07-04 | 2026-07-04 |
| 3b — Schema Restructure | ✅ Completed | 2026-07-05 | 2026-07-05 |
| 3c — SortOrder & Provisioning | ✅ Completed | 2026-07-05 | 2026-07-05 |

## Current Focus
All 3 curriculum phases are complete. Backend schema has been restructured and endpoints verified via `make test-endpoints`. Frontend testing pending user feedback.

## Current State

### Backend — Schema
- `curriculums` — standalone table (no many2many)
- `assessments` — belongs to curriculum via `curriculum_id` FK (NOT NULL); no `grades` JSON column; has `sort_order` (default 0)
- `grade_items` — belongs to assessment via `assessment_id` FK; no `parent_grade_item_id` (flat hierarchy); has `sort_order`
- `scores` — stores per-student grade-item scores with nullable `GradeItemID` FK and `ScoreValue`; supports rollup to assessment total
- `assessment_curriculum` join table — **removed**
- `assessments.grades` JSON column — **removed**
- `grade_items.parent_grade_item_id` — **removed**

### Backend — API Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v2/academic/curriculum` | GET | List curriculums (includes assessments → grade items) |
| `/api/v2/academic/curriculum` | POST | Create curriculum with inline assessments & grade items |
| `/api/v2/academic/curriculum/:id` | GET | Get curriculum detail |
| `/api/v2/academic/curriculum/:id` | PUT | Update curriculum name/description |
| `/api/v2/academic/assessment` | POST | Create standalone assessment (with `curriculum_id` & `sort_order`) |
| `/api/v2/academic/assessment/:id` | PUT | Update assessment (incl. `sort_order`) |
| `/api/v2/academic/grade-item` | GET | List grade items (filter by `assessment_id`) |
| `/api/v2/academic/grade-item` | POST | Create grade item |
| `/api/v2/academic/grade-item/:id` | PUT | Update grade item |
| `/api/v2/academic/grade-item-score` | POST | Upsert per-grade-item score |
| `/api/v2/academic/scores/rollup` | POST | Roll up grade item scores into assessment total |

### Backend — Provisioning & Seeding
- `seedDefaultGradeItems` creates a default curriculum with **3 assessments** (First CA / total=15 / sort_order=1, Second CA / total=25 / sort_order=2, Exam / total=60 / sort_order=3) each with their own sub-grade items
- `seedDefaultLevels` seeds Grades 1-3 with arms A & B (removed Grades 4-6 that lacked `level_data`)
- Default curriculum is created via async Asynq task during school provisioning

### Backend — DTO Changes
- All assessment DTOs include `sort_order` (int)
- No `Grades` on any assessment DTO
- No `ParentGradeItemID` / `Children` on any grade item DTO
- No `AssessmentIDs` / `AssessmentUUIDs` on curriculum DTOs
- `AssessmentResponse` includes `curriculum_id` and `sort_order`

### Backend — Score Service
- `computeHierarchyTotal` renamed to `computeGradeItemsTotal` — flat iteration, no `Children` references
- No `validateGrades` / `assessment.Grades` references

### Frontend
- `useAcademics.ts` hooks for Sessions, Curriculums, Assessments, Grade Items, Scores
- `CurriculumDrawer` in `school.tsx` for full curriculum management
- `CurriculumForm` reusable component (used by onboarding step 3)
- `GradeItemScoreEntry` component for per-grade-item score entry
- Curriculum step on onboarding page (step 3 between Subjects and Session)
- Onboarding bug fixed: `database_status` returned from backend, polling logic handles pending → active transition

## Architecture Decisions

1. **Assessment → Curriculum via `curriculum_id` FK (NOT NULL)** — Direct belongs_to replaces the many2many join table. Simpler queries, no orphan assessments.
2. **Flat grade items** — No `parent_grade_item_id` / tree hierarchy. All grade items are top-level under an assessment.
3. **`sort_order` on assessments** — Assessments are ordered per curriculum; used in provisioning and create-default flows.
4. **Inline assessment creation** — `POST /academic/curriculum` accepts nested `{ name, assessments: [{ name, total, sort_order, grade_items: [...] }] }`. Validates totals == 100.
5. **Score rollup via separate endpoint** — Grade-item scores saved individually via `POST /academic/grade-item-score`; rollup computed via `POST /academic/scores/rollup`.
6. **`datatabase_status` on school response** — Enables frontend to distinguish "pending provisioning" vs "active" for polling and cache invalidation.

## Test Script
- `backend/scripts/test_endpoint.sh` — auth-first E2E test suite covering health, login, CSRF, school creation, provisioning, curriculum/assessment/grade-item CRUD, and sort_order verification
- `make test-endpoints` — builds binary and runs the suite
- Auto-resets DB (drop tenants, migrate, seed) on clean run

## Relevant Files

### Backend
- `backend/internal/database/models/assessment.go` — `Assessment` model (CurriculumID FK, SortOrder, no Grades)
- `backend/internal/database/models/curriculum.go` — `Curriculum.Assessments` as `has_many`
- `backend/internal/database/models/grade_item.go` — `GradeItem` (flat, no parent/children)
- `backend/internal/modules/academic/dto.go` — All DTOs (no Grades/ParentGradeItemID/AssessmentIDs; SortOrder everywhere)
- `backend/internal/modules/academic/repository.go` — No `ReplaceCurriculumAssessments`; simplified `FindGradeItemsByAssessment`
- `backend/internal/modules/academic/service.go` — All service methods updated for new schema; `createDefaultCurriculum` creates 3 assessments
- `backend/internal/modules/academic/handler.go` — Converters include SortOrder; removed parentID param from ListGradeItems
- `backend/internal/modules/score/service.go` — `computeGradeItemsTotal` (flat); no validateGrades
- `backend/internal/database/tenant/provisioning.go` — `seedDefaultGradeItems` with 3 assessments + grade items; `seedDefaultLevels` for Grades 1-3 A/B
- `backend/internal/database/migrations/school/core_academic.go` — No `AssessmentCurriculum` in AutoMigrate
- `backend/internal/database/migrations/school/uuid_columns.go` — No `"assessment_curriculum"` in table list
- `backend/scripts/test_endpoint.sh` — E2E test suite
- `backend/Makefile` — `test-endpoints` target

### Frontend
- `frontend/src/components/academics/curriculum-form.tsx` — Reusable CurriculumForm
- `frontend/src/components/academics/grade-item-score-entry.tsx` — GradeItemScoreEntry
- `frontend/src/lib/hooks/useAcademics.ts` — useCreateCurriculum, useAssessmentGradeItems hooks
- `frontend/src/lib/hooks/useSchool.ts` — Hooks with polling + path parameter fix
- `frontend/src/routes/_onboarding/onboarding.tsx` — Curriculum step (step 3)
- `frontend/src/routes/_dashboard/school.tsx` — CurriculumDrawer on school management page
