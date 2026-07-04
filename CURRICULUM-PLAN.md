# Curriculum & Assessment Model (Nigerian CA/Exam System)

## Hierarchy

```
School → Session → Curriculum → Assessment → Grade Item → Score (per student)
```

### Layers

1. **Session** — e.g. "2025/2026", "2026/2027"
   - Has one active curriculum (e.g. "General CA")
   - Contains classes, subjects, etc.

2. **Curriculum** — a named grading scheme tied to a session
   - e.g. "General CA", "Term Exams", "Continuous Assessment"
   - Lives under a school → session
   - Contains multiple Assessments

3. **Assessment** — a component of the curriculum with a max score
   - e.g. "First CA" (max 15), "Second CA" (max 25), "Exam" (max 60)
   - All assessments within a curriculum sum to the curriculum total (usually 100)
   - Each Assessment contains Grade Items

4. **Grade Item** — a breakdown of marks within an assessment, sums to 100
   - e.g. for "First CA" (max 15):
     - Classwork (10 marks)
     - Assignments (20 marks)
     - Written Test (50 marks)
     - Practicals (20 marks)
   - e.g. for "Second CA" (max 25):
     - Written Test (60 marks)
     - Project (40 marks)
   - e.g. for "Exam" (max 60):
     - Written Test (100 marks)
   - All grade items within an assessment sum to 100
   - Student's actual score is: (grade item score / 100) × assessment max

5. **Score** — per-student, per-grade-item entry
   - student_id, assessment_id, grade_item_id, score_value

---

## Example Calculation

For "First CA" (max 15):
- If a student scores: Classwork 8/10, Assignments 15/20, Written Test 40/50, Practicals 17/20
- Total out of 100: 8+15+40+17 = 80
- Scaled to assessment max: 80/100 × 15 = **12/15**

---

## Key Rules

- Assessments under a curriculum sum to 100
- Grade items under an assessment sum to 100
- Grade item scores are always out of 100, then scaled to assessment max
- Only admins create/manage curriculums, assessments, and grade items
- Curriculum lives on the School page (not the admin academics page)

---

## Backend State (Current)

- `curriculums` table exists with many-to-many to `assessments` (pivot: `assessment_curriculum`) and `sessions` (pivot: `session_curriculum`)
- `assessments` table exists with `grades` (JSON column — currently used for grade boundaries like A/B/C/D/F, NOT grade items)
- `scores` table exists — stores per-student scores as JSON per assessment
- `results` table exists — aggregates scores
- **No `grade_items` table exists yet** — needs to be created
- Current `assessments.grades` JSON stores letter-grade boundaries (A:80, B:60, etc.) — this is separate from grade items

## What Needs to Change

### Backend
1. Create `grade_items` table: id, uuid, assessment_id (FK), name, max_score (default 100), sort_order
2. Add `curriculum_id` FK to `assessments` (or keep current many-to-many pivot)
3. Update assessment creation flow to include grade items inline
4. Add/update endpoints for grade_item CRUD
5. Update score recording to work per-grade-item

### Frontend
1. Move curriculum from admin academics page to School page
2. Build curriculum creation form with inline "add assessment" with inline "add grade item"
3. Build score entry UI per grade item
4. Build result rollup display

---

## API Endpoints

### Phase 1 (Done)
```
POST   /academic/grade-item              → CreateGradeItem
GET    /academic/grade-item              → ListGradeItems (filter by ?assessment_id=X)
GET    /academic/grade-item/:id          → GetGradeItem
PUT    /academic/grade-item/:id          → UpdateGradeItem
DELETE /academic/grade-item/:id          → DeleteGradeItem
```

### Phase 2 (Planned)
```
POST   /academic/curriculum              → Create (with nested assessments + grade items)
GET    /academic/curriculum              → List (with nested)
GET    /academic/curriculum/:id          → Get (with nested)
PUT    /academic/curriculum/:id          → Update (with nested)

POST   /academic/assessment              → Create (with grade items)
GET    /academic/assessment              → List
GET    /academic/assessment/:id          → Get (with grade items)
PUT    /academic/assessment/:id          → Update

Session creation auto-generates default curriculum

### Phase 3 (Planned)
```
POST   /academic/scores                  → Save per-grade-item scores
GET    /academic/scores                  → List with grade items breakdown
POST   /academic/scores/rollup           → Trigger score rollup
```
