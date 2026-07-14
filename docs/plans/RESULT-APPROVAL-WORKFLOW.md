# Result Approval Workflow & Score Comments

## Overview

Add a two-tier result approval pipeline and optional per-score comments.

---

## Current State

| Feature | Status |
|---------|--------|
| Result statuses | `not-approved`, `approved`, `withheld` |
| Class teacher check | Enforced on `SaveResult` — only homeroom teacher can save |
| Score entry | No comment field per grade-item score |
| Approval endpoint | `PUT /result/:id/approve` — anyone with admin/principal role can set any status |

---

## Two-Tier Approval Flow

```
Teachers enter scores        → grade-item scores with optional comments
         ↓
Class teacher submits result → POST /result/:id/submit
  - Adds comment (required)
  - Sets status → "teacher-approved"
         ↓
Principal/Admin reviews      → PUT /result/:id/approve
  - Can approve (→ "approved") or withhold (→ "withheld")
  - Only allowed when status is "teacher-approved"
         ↓
Student/Parent sees result   → only if status is "approved"
```

### Status Transitions

```
not-approved ──[teacher submit]──→ teacher-approved ──[admin approve]──→ approved
                                                     ──[admin withhold]──→ withheld
```

---

## Backend Changes

### 1. New enum: `ResultTeacherApproved`

Add to `enums.go`:
```go
const (
    ResultApproved        = "approved"
    ResultNotApproved     = "not-approved"
    ResultTeacherApproved = "teacher-approved"
    ResultWithheld        = "withheld"
)
```

### 2. Optional comment on score input

**`CreateGradeItemScoreRequest`** — add optional `Comment` field:
```go
type CreateGradeItemScoreRequest struct {
    // ... existing fields
    Comment string `json:"comment,omitempty"`
}
```

**`BulkScoreItem`** — add optional `Comment` field:
```go
type BulkScoreItem struct {
    // ... existing fields
    Comment string `json:"comment,omitempty"`
}
```

**Storage**: Store comments alongside scores in the JSON blob:
```json
{
    "scores": {"5": 15, "6": 12},
    "comments": {"5": "Late submission", "6": ""},
    "total": null
}
```

Update `buildGradeItemScoreJSON` and `mergeGradeItemScore` to accept and persist the optional comment.

### 3. Teacher submit endpoint: `POST /academic/result/:id/submit`

**Request:**
```json
{
    "comment": "Student has shown consistent improvement"
}
```

**Handler checks:**
- User must be the class teacher of the student (existing `SaveResult` check)
- Result must exist and have status `not-approved` or `teacher-approved`
- Sets status to `teacher-approved`
- Stores the teacher's comment in the result's `Comments` JSON

### 4. Update `ApproveResult` — enforce status gating

Before allowing approval, check:
- Status must be `teacher-approved` (can't approve a result that hasn't been teacher-submitted)
- Only allow transitions to `approved` or `withheld` (already enforced by DTO validation)

### 5. Update `GetResult` gating

- Students/parents: only see status `approved` (already implemented)
- Teachers: see all results (unchanged)
- Admins/principals: see all results (unchanged)

---

## Files Changed

| File | Change |
|------|--------|
| `models/enums.go` | Add `ResultTeacherApproved` |
| `modules/score/dto.go` | Add `Comment` to `CreateGradeItemScoreRequest` + `BulkScoreItem` |
| `modules/score/service.go` | Persist comment in JSON blob; update `buildGradeItemScoreJSON` + `mergeGradeItemScore` |
| `modules/result/dto.go` | Add `SubmitResultRequest` |
| `modules/result/handler.go` | Add `SubmitResult` handler |
| `modules/result/service.go` | Add `SubmitResult` method; update `ApproveResult` to gate on `teacher-approved` |
| `modules/result/repository.go` | (No changes needed) |
| `router/router.go` | Add route for `POST /result/:id/submit` |

---

## Frontend Considerations

- ScoreGrid cells could show a small comment icon/indicator when a comment exists
- Hover or click to view/add comment on a per-grade-item basis
- Admin result view shows teacher comment + approval status badge
- Principal result view shows approve/withhold buttons when status is `teacher-approved`
