# Curriculum & Assessment — Implementation Roadmap

> **Goal:** Replace the current flat assessment/score model with a nested
> Curriculum → Assessment → Grade Item hierarchy with per-grade-item scoring
> and inline creation flows.

---

## Overview

```
School → Session → Curriculum → Assessment → Grade Item → Score (per student)
```

**Current state:** Curriculums + Assessments exist but use many-to-many pivots.
Scores are recorded per-assessment as JSON. No Grade Items exist.

**Target state:** Curriculum owns assessments (FK). Assessment owns grade items (FK).
Scores are per-grade-item. Admin creates curriculum with nested assessments + grade
items inline from the School page.

---

## Phases

### Phase 1: GradeItem Model + CRUD API (Backend)

**Goal:** `grade_items` table exists with full CRUD and sum-to-100 validation.

**Depends on:** Nothing

#### Backend Tasks

1. **Create `GradeItem` model** (`backend/internal/database/models/grade_item.go`)
   ```go
   type GradeItem struct {
       ID           uint       `gorm:"primaryKey" json:"id"`
       UUID         guuid.UUID `gorm:"type:uuid;uniqueIndex;default:gen_random_uuid()" json:"uuid"`
       AssessmentID uint       `gorm:"index;not null" json:"assessment_id"`
       Name         string     `gorm:"not null;size:255" json:"name"`
       MaxScore     float32    `gorm:"type:real;not null;default:100" json:"max_score"`
       SortOrder    int        `gorm:"not null;default:0" json:"sort_order"`
       CreatedAt    time.Time  `json:"created_at"`
       UpdatedAt    time.Time  `json:"updated_at"`
   }
   ```

2. **Register in `AllModels()`** for auto-migration

3. **Add to `Assessment` model** — `GradeItems []GradeItem gorm:"foreignKey:AssessmentID"`

4. **Create `GradeItemRepositoryInterface` + `GradeItemRepository`**
   - CRUD methods (Create, FindByID, FindByAssessmentID, Update, Delete)
   - Follow existing pattern in `academic/repository.go`

5. **Create DTOs** (following `academic/dto.go` pattern)
   - `CreateGradeItemRequest` — name, max_score, sort_order, assessment_id
   - `UpdateGradeItemRequest` — name, max_score, sort_order
   - `GradeItemResponse`

6. **Create `GradeItemService`**
   - CRUD delegation to repository
   - **Validation:** Sum of all grade items' max_score for an assessment must equal 100
   - Recalculate sum on create, update, delete

7. **Create `GradeItemHandler`** (can add to academic package or new gradeitem package)
   - `POST /academic/grade-item` — create
   - `GET /academic/grade-item` — list (filterable by `assessment_id`)
   - `GET /academic/grade-item/:id` — get
   - `PUT /academic/grade-item/:id` — update
   - `DELETE /academic/grade-item/:id` — delete

8. **Register routes** in `router.go`
   ```go
   academic.POST("/grade-item", academicHandler.CreateGradeItem)
   academic.GET("/grade-item", academicHandler.ListGradeItems)
   academic.GET("/grade-item/:id", academicHandler.GetGradeItem)
   academic.PUT("/grade-item/:id", academicHandler.UpdateGradeItem)
   academic.DELETE("/grade-item/:id", academicHandler.DeleteGradeItem)
   ```

9. **Wire dependencies** in server setup

#### Verification Criteria

1. `grade_items` table exists after migration with FK to `assessments`
2. Can `POST /academic/grade-item` to create a grade item for an assessment
3. Can `GET /academic/grade-item?assessment_id=X` returns filtered list
4. Creating grade items where `max_score` sum ≠ 100 returns validation error
5. Deleting a grade item updates the sum calculation for remaining items
6. `GET /academic/assessment/:id` returns nested `grade_items` array

---

### Phase 2: Nested Curriculum Management (Backend + Frontend)

**Goal:** Admin can create curriculum with inline assessment + grade item definitions
from the School page. Curriculum lives on School page, not generic academics.

**Depends on:** Phase 1

#### Backend Tasks

1. **Restructure `Assessment` → `Curriculum` relationship**
   - Add `CurriculumID` FK to `Assessment` model (removing many-to-many pivot, or keep
     pivot for backward compat and add FK as primary path)
   - Keep `assessment_curriculum` pivot for existing data; new code uses FK

2. **Update `CreateCurriculumRequest`** to accept nested payload:
   ```json
   {
     "name": "General CA",
     "description": "...",
     "assessments": [
       {
         "name": "First CA",
         "total": 15,
         "description": "...",
         "grade_items": [
           { "name": "Classwork", "max_score": 10, "sort_order": 1 },
           { "name": "Written Test", "max_score": 50, "sort_order": 3 }
         ]
       },
       {
         "name": "Exam",
         "total": 60,
         "description": "...",
         "grade_items": [
           { "name": "Written Test", "max_score": 100, "sort_order": 1 }
         ]
       }
     ]
   }
   ```

3. **Update `CreateCurriculum` service logic**
   - Create curriculum
   - Loop assessments: create each with curriculum_id, then create grade items
   - Validate: assessments.total sum to 100
   - Validate: per-assessment grade_items.max_score sum to 100

4. **Update `GetCurriculum` / `ListCurriculums`** to return full nested tree:
   `curriculum → assessments → grade_items`

5. **Update `UpdateCurriculum`** to support full replacement of nested structure

6. **Add `GET /schools/curriculums`** endpoint (or reuse existing `/academic/curriculum`
   with school_id scope) — so School page can fetch curriculums for the school

#### Frontend Tasks

1. **Add `GradeItem` TypeScript type** in `useAcademics.ts`
   ```typescript
   export interface GradeItem {
     id: number;
     name: string;
     max_score: number;
     sort_order: number;
   }
   ```

2. **Update `Assessment` type** — add `grade_items?: GradeItem[]`

3. **Add `Curriculum` tab** to School page (`school.tsx`)
   - New tabs list entry `<TabsTrigger value="curriculums">Curriculum</TabsTrigger>`
   - New `<TabsContent value="curriculums">` with curriculum list + create button

4. **Build `CurriculumDrawer` component** (or inline as a Sheet)
   - Curriculum name + description fields
   - Dynamic "Add Assessment" section inside
     - Assessment name + total (max_score) fields
     - Dynamic "Add Grade Item" section inside each assessment
       - Grade item name + max_score fields
       - Live sum display showing grade items sum / 100
   - Live sum display showing assessments total / 100
   - Submit sends nested JSON to `POST /academic/curriculum`

5. **Build curriculum list display**
   - Card per curriculum showing name, description
   - Expandable assessments list showing name + total
   - Expandable grade items list showing name + weight

6. **Update query keys** — add `gradeItems` key

7. **Add hooks**: `useCreateNestedCurriculum`, `useCurriculum`, `useCurriculums`
   (update existing to include grade_items)

#### Verification Criteria

1. Admin can see a "Curriculum" tab on the School page
2. Admin can create a curriculum with 2+ assessments and grade items in a single form
3. Assessments total sum to 100 enforced at form level + API level
4. Grade items per-assessment sum to 100 enforced at form level + API level
5. Created curriculum appears in the list with nested assessments + grade items visible
6. GET endpoint returns full nested tree: curriculum → assessments → grade_items
7. Existing data migration path works (old many-to-many assessments still readable)

---

### Phase 3: Per-Grade-Item Score Recording + Rollup (Backend + Frontend)

**Goal:** Scores recorded per-grade-item, rolled up to assessment total, then to
curriculum total. Teachers enter scores per grade item, not per assessment.

**Depends on:** Phase 2

#### Backend Tasks

1. **Update `scores` table / create `grade_item_scores` table**
   Option A: Add `grade_item_id` column to existing `scores` table
   Option B: New `grade_item_scores` table (cleaner separation)

   Recommended: Option A — add `grade_item_id` FK, keep `AssessmentID` for rollup
   queries. The existing `Score` model gets a `GradeItemID` field.

   ```go
   type Score struct {
       // ... existing fields ...
       GradeItemID *uint `gorm:"index" json:"grade_item_id"`
   }
   ```

2. **Update `CreateScoreRequest`** — add `grade_item_id`, make it key
   - Remove/warn on the old `grades` JSON array approach
   - New payload: `{ "student_id": X, "assessment_id": Y, "grade_item_id": Z, "subject_id": W, "score_value": 85 }`

3. **Update `SaveScore` service logic**
   - Validate grade_item_id belongs to assessment_id
   - Validate score_value ≤ grade_item.max_score
   - Upsert per (student_id, assessment_id, grade_item_id, subject_id, session_id)

4. **Build grade-item rollup service** (`ScoreRollupService` or methods on `ScoreService`)
   - `RollupAssessmentScore(studentID, assessmentID, subjectID)`:
     - Fetch all grade item scores for this assessment
     - Sum: (each_score / each_max) × assessment_total
     - Write/update the aggregate assessment score (in scores table with grade_item_id = null)
   - `RollupCurriculumScore(studentID, curriculumID, subjectID)`:
     - Sum of all assessment rollups
     - Write to result or scores table

5. **Update `ListScores`** — support filter by `grade_item_id`
   - Return grade-item-level scores when `grade_item_id` provided
   - Return assessment-level rollup when only `assessment_id` provided

6. **Add endpoint** `POST /academic/scores/rollup` to trigger rollup for a
   student × assessment or student × curriculum

#### Frontend Tasks

1. **Create `useGradeItemScores` hook** (or extend `useAcademics.ts`)
   - `useGradeItemScores(filters)` — fetch per-grade-item scores
   - `useSaveGradeItemScore()` — save score for a grade item

2. **Build score entry Sheet** on the assessment page
   - Select subject → shows students in that subject
   - For each student, show grade items as rows
   - Each row: grade item name + max + input field
   - Live calculation of assessment total as teacher types

3. **Build rollup display** on the curriculum page
   - Per-student: curriculum total, breakdown per assessment
   - Per-assessment: grade item scores listed
   - Visual progress bars / percentage display

4. **Add trigger button** "Calculate Assessment Totals" which calls rollup endpoint

5. **Update query keys** — add `gradeItemScores`

#### Verification Criteria

1. Teacher can load a class/subject and see per-grade-item score entry form
2. Teacher enters score for a grade item, value validated against max_score
3. After saving all grade items, assessment rollup shows correct calculated total
4. Rollup formula: `(grade_item_score / max_score) × assessment_total = weighted_score`
5. Curriculum total = sum of all assessment totals for that student/subject
6. Score entry form shows live calculation while typing
7. Old per-assessment JSON scores remain readable (backward compatibility)

---

## Requirement Coverage Map

| Requirement | Phase | Verification |
|---|---|---|
| `grade_items` table exists | 1 | Migration runs, table visible |
| Assessments sum to 100 per curriculum | 2 | API rejects invalid totals |
| Grade items sum to 100 per assessment | 1, 2 | API + form validation |
| Curriculum management on School page | 2 | Curriculum tab visible |
| Nested creation (curriculum → assessments → grade items) | 2 | Single form creates all |
| Per-grade-item score recording | 3 | Scores saved per grade item |
| Score rollup (grade item → assessment → curriculum) | 3 | Rollup endpoint returns correct totals |
| Assessment creation includes grade items inline | 2 | Grade items inside assessment form |

---

## Data Flow Diagram

```
Phase 1:                     Phase 2:                         Phase 3:
┌──────────────┐            ┌──────────────────┐             ┌─────────────────────┐
│  GradeItem   │            │  CurriculumForm  │             │  ScoreEntryForm     │
│  Model       │            │  (nested Sheet)  │             │  (per grade item)   │
│  CRUD API    │──────────▶│  CreateCurriculum │────────────▶│  SaveGradeItemScore  │
│  Validation  │            │  w/assessments + │             │  ─────────────      │
│  (sum=100)   │            │  grade items     │             │  RollupAssessment   │
└──────────────┘            └──────────────────┘             │  RollupCurriculum   │
                                                             └─────────────────────┘
```

---

## Dependencies Between Phases

```
Phase 1 ─────────────────────────────────────────────────────────────────
  │
  └──▶ Phase 2 ──▶ Phase 3
       (needs       (needs
        GradeItem    nested curriculum
        CRUD API)    + GradeItem FK on scores)
```

---

## Progress

| Phase | Backend | Frontend | Status |
|---|---|---|---|---|
| 1 — GradeItem CRUD | 9/9 tasks | — | ✅ Completed |
| 2 — Nested Curriculum | 6/6 tasks | 6/6 tasks | ✅ Completed |
| 3 — Per-Grade-Item Scoring | 6/6 tasks | 5/5 tasks | ✅ Completed |
