# Teacher Assessment Scoring — Manual & Excel Input

## Overview

Replace the current per-student expand-to-enter pattern with a **spreadsheet-style grid** where teachers see all students as rows and grade items as columns, entering scores in a table. Add Excel import/export for bulk operations.

---

## Phase 1: Manual Input Improvements

### Current Problems

- Class dropdown uses hardcoded `JSS1-SS3` instead of real school levels
- All students load regardless of class filter — `useUsers("student")` with no level_id
- Per-student expand pattern is slow for classes of 30+ students
- No visual indication of which scores are saved vs pending
- No bulk save — each student's scores save individually

### Proposed Solution: Score Grid Table

A `<ScoreGrid>` component that replaces `GradeItemScoreEntry`:

```
┌──────────┬────────────┬──────────┬──────────┬──────────┬────────┐
│ Student  │ Classwork  │ Assignmt│ W.Test   │ Practcls │ Total  │
│          │ (10 marks) │ (20)    │ (50)     │ (20)     │ (100%) │
├──────────┼────────────┼──────────┼──────────┼──────────┼────────┤
│ John D.  │     8      │   15     │   42     │   18     │  83/100│ ✓
│ Jane S.  │     7      │   18     │   45     │   19     │  89/100│ ✓
│ Bob K.   │     6      │         │         │          │        │ ✗
│ ...      │            │          │          │          │        │
├──────────┼────────────┼──────────┼──────────┼──────────┼────────┤
│          │  [Save All]│          │          │          │        │
└──────────┴────────────┴──────────┴──────────┴──────────┴────────┘
```

### Implementation

**ScoreGrid component** (`components/academics/score-grid.tsx`):
- Props: `assessmentId, assessmentTotal, gradeItems, subjectId, sessionId, schoolId`
- Fetches students filtered by selected level + school ID
- Fetches existing scores for the assessment/subject combo
- Renders an HTML `<table>` with:
  - Rows: students (checkable for bulk operations)
  - Columns: grade item name + max score in header
  - Cells: `<input type="number" min="0" max="{maxScore}">` 
  - Last column: computed total (sum of entered scores) / assessment total
  - Status column: saved (✓), pending/unsaved (✗), or error
- Local state: `{ [studentId]: { [gradeItemId]: number | null } }` — only tracks changes
- On input change: mark as dirty, auto-save after 3s debounce or explicit Save
- "Save All" button saves all dirty rows at once
- Color coding: green cell if score is within range, red if over max

**TeacherAcademics page changes** (`teacher.academics.tsx`):
- Replace class dropdown hardcoded values with `useLevels()` hook
- Pass level_id to student query when a class is selected
- Use `useGradeItemScores` to preload existing scores
- Replace per-student expand with `<ScoreGrid>`

### Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/academics/score-grid.tsx` | **New** — grid component |
| `frontend/src/routes/_dashboard/teacher.academics.tsx` | Replace per-student expand with ScoreGrid |
| `frontend/src/lib/hooks/useAcademics.ts` | Add score queries for grid batch |

---

## Phase 2: Excel Input

### Overview

Allow teachers to download a pre-populated XLSX template with student names and grade item columns, fill scores offline, and upload.

### Flow

1. Teacher clicks **"Download Excel"** → generates XLSX with student rows × grade item columns
2. Teacher fills scores in Excel offline
3. Teacher clicks **"Upload Excel"** → selects file
4. Frontend parses XLSX, validates scores (non-negative, within max), shows preview
5. Teacher confirms → sends to backend endpoint
6. Backend bulk-inserts/updates scores via existing `SaveGradeItemScore` logic

### Backend Endpoint: `POST /api/v2/academic/scores/bulk`

```
Request: {
  assessment_id: uint,
  subject_id: uint,
  session_id: uint,
  scores: [
    { student_id: uint, grade_item_id: uint, score: float }
  ]
}
Response: { success: true, saved: 30, errors: [...] }
```

Reuses existing `SaveGradeItemScore` logic — iterates and calls the same merge function.

### Backend Endpoint: `GET /api/v2/academic/scores/export`

```
Query: assessment_id, subject_id, session_id, level_id
Response: XLSX binary with student rows × grade item columns
```

### Files Changed

| File | Change |
|------|--------|
| `backend/internal/modules/score/handler.go` | Add `BulkSaveScores`, `ExportScoresXLSX` handlers |
| `backend/internal/modules/score/service.go` | Add `BulkSaveScores` logic |
| `backend/internal/modules/score/dto.go` | Add `BulkSaveScoresRequest` DTO |
| `backend/internal/router/router.go` | Add routes |
| `frontend/src/components/academics/score-grid.tsx` | Add Download/Upload Excel buttons |
| `frontend/src/lib/api.ts` | Add bulk save + export functions |

---

## Implementation Order

1. **Phase 1**: Score Grid component + improved TeacherAcademics page
2. **Phase 2**: Backend bulk save endpoint + frontend Excel import
