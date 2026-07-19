---
phase: 05-gradebook-hardening
reviewed: 2026-07-19T16:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - frontend/src/routes/_dashboard/academics.tsx
  - frontend/src/components/academics/score-grid.tsx
  - frontend/src/components/academics/score-grid.test.tsx
  - backend/internal/modules/grading/service_test.go
  - backend/pkg/mathutil/rounding.go
  - backend/pkg/mathutil/rounding_test.go
findings:
  critical: 0
  warning: 3
  info: 8
  total: 11
status: issues_found
---

# Phase 5: Gradebook Hardening — Code Review Report

**Reviewed:** 2026-07-19T16:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed 6 source files across the gradebook hardening phase: grade freeze UI indicators (academics.tsx, score-grid.tsx), frontend integration tests (score-grid.test.tsx), Go boundary computation tests (grading/service_test.go), and the mathutil rounding utilities (rounding.go, rounding_test.go).

**Overall assessment:** The codebase is well-structured with solid test coverage for WAEC boundary calculations and ScoreGrid disabled state. Two bugs were found: an admin tab default mismatch that prevents content from displaying, and a hasSavedScore check that only inspects the first grade item. The plan specified `canModifyScore` tests should be in `grading/service_test.go` but they exist in `score/service_test.go` instead. Several minor accessibility and copy-deviation items were noted.

---

## Warnings

### WR-01: Admin default tab "sessions" does not exist in admin tabs

**File:** `frontend/src/routes/_dashboard/academics.tsx:932`

**Issue:** The `<Tabs>` component uses `defaultValue="sessions"`, but the admin tabs array (`adminTabs`, line 865) only contains keys `"classes"`, `"subjects"`, `"assessments"`, and `"results"` — no `"sessions"` key. When an admin user loads the page, `tabs = adminTabs`, and Radix Tabs cannot match `"sessions"` against any tab value. This causes **no tab content to be visible** on initial load for admin users.

The student tabs array (`studentTabs`, line 872) **does** include `"sessions"`, so only admin users are affected.

**Fix:** Either add a `"sessions"` tab to `adminTabs`, or change the `defaultValue` to match the first admin tab:

```tsx
// Option A: Use a computed default
const defaultTab = isAdmin ? "classes" : "sessions";
// ...
<Tabs defaultValue={defaultTab} className="space-y-4">

// Option B: Or derive from the tabs array
<Tabs defaultValue={tabs[0]?.key ?? "sessions"} className="space-y-4">
```

---

### WR-02: `hasSavedScore` only checks the first grade item

**File:** `frontend/src/components/academics/score-grid.tsx:514`

**Issue:** The `hasSavedScore` variable is computed as:
```tsx
const firstGiKey = `${student.id}:${gradeItems[0]?.id}`;
const hasSavedScore = existingMap.has(firstGiKey) && !dirtyRef.current.has(firstGiKey);
```
This only checks whether the **first** grade item (index 0) has a saved score. If a student has saved scores on grade items 2+ but not item 1, `hasSavedScore` is false and the green checkmark status indicator is suppressed.

**Fix:** Check across all grade items for the student:

```tsx
const hasSavedScore = gradeItems.some(
  (gi) => {
    const key = `${student.id}:${gi.id}`;
    return existingMap.has(key) && !dirtyRef.current.has(key);
  },
);
```

---

### WR-03: Missing `canModifyScore` frozen-grade test in grading/service_test.go

**File:** `backend/internal/modules/grading/service_test.go`

**Issue:** The plan (05-02-PLAN.md, Task 2) specifies adding `canModifyScore` frozen-grade tests to `grading/service_test.go`. These tests are absent from the file — only WAEC boundary and `CalculateGradeForAssessmentTotal` tests are present. The `canModifyScore` tests exist in `backend/internal/modules/score/service_test.go` (line 1083), which is in a different module.

The grading module's service has no `canModifyScore` method itself (it's in the score module), so adding those tests here would require cross-module dependencies. However, the plan's intent to verify integration between grading and session freeze status is not fulfilled by the current test suite.

**Fix:** Either:
- Add an integration test in `grading/service_test.go` that verifies `CalculateGrade` still works on completed sessions (grades should still be calculable even when scores are frozen), OR
- Update the plan to acknowledge these tests belong in `score/service_test.go` and ensure they cover the frozen-grade scenario there.

---

## Info

### IN-01: FrozenBadge missing `aria-label`

**File:** `frontend/src/routes/_dashboard/academics.tsx:76-83`

**Issue:** The UI spec (05-UI-SPEC.md, line 136) requires: `"Frozen" Badge on session cards must have aria-label="Session completed — grades frozen"`. The `FrozenBadge` component renders with a Lock icon and "Frozen" text but no `aria-label`.

**Fix:** Add `aria-label` to the badge container:

```tsx
function FrozenBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-600 border border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-700/50"
      aria-label="Session completed — grades frozen"
    >
      <Lock className="w-3 h-3" />
      Frozen
    </span>
  );
}
```

---

### IN-02: Unused import `X` in score-grid.tsx

**File:** `frontend/src/components/academics/score-grid.tsx:7`

**Issue:** The `X` icon from `lucide-react` is imported but never used in the `score-grid.tsx` component. (It is used in `academics.tsx` for the Withhold button, but that's a different module.)

**Fix:** Remove `X` from the import:

```tsx
import { Loader2, Save, CheckCircle2, AlertCircle, Download, Upload, MessageSquare, Lock } from "lucide-react";
```

---

### IN-03: Redundant grade_item_id resolution in handleFileSelect

**File:** `frontend/src/components/academics/score-grid.tsx:377-395`

**Issue:** The initial `parsed.push` on line 377 already resolves `grade_item_id` from the grade item name via a complex expression that redundantly finds the current column (`gradeItemColumns.find((c) => c.colKey === gc.colKey)` always matches `gc` itself). Lines 390-395 then re-resolve `grade_item_id` for items where it's 0.

**Fix:** Simplify to a direct lookup:

```tsx
const gi = gradeItems.find((g) => g.name === gc.name);
if (!gi) continue; // skip unknown grade items
parsed.push({
  student_name: studentName,
  student_id: studentId,
  grade_item_id: gi.id,
  grade_item_name: gc.name,
  score,
});
```

Then remove the post-loop re-resolution (lines 390-395).

---

### IN-04: FrozenBanner copy differs from UI spec

**File:** `frontend/src/routes/_dashboard/academics.tsx:835,837`

**Issue:** The UI spec (05-UI-SPEC.md, lines 79-80) specifies:
- Heading: `"Grades Frozen — Session Completed"`
- Body: `"This session's grades are locked. Scores are read-only."`

The implementation uses:
- Heading: `"Grades Frozen"` (missing `" — Session Completed"`)
- Body: `"This session's grades are frozen. Contact admin to make changes."`

**Fix:** Align copy with the UI spec:

```tsx
<p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
  Grades Frozen — Session Completed
</p>
<p className="text-xs text-amber-700 dark:text-amber-400">
  This session&apos;s grades are locked. Scores are read-only.
</p>
```

---

### IN-05: Disabled input title tooltip differs from UI spec

**File:** `frontend/src/components/academics/score-grid.tsx:557`

**Issue:** The UI spec (line 82) specifies the input title tooltip should be `"Session completed — scores are frozen"`. The implementation uses `"Grades are frozen for this session"` (applied at line 533 on the lock icon span and line 557 on the Input).

**Fix:** Align the title attribute with the spec:

```tsx
title={disabled ? "Session completed — scores are frozen" : isOver ? `Exceeds max score of ${gi.max_score}` : undefined}
```

---

### IN-06: Import Excel label has no accessible name when disabled

**File:** `frontend/src/components/academics/score-grid.tsx:462-466`

**Issue:** The file input is wrapped in a `<label>` with the text "Import Excel" but no explicit `aria-label`. When `disabled` is true, the hidden `<input>` is disabled, and screen readers may not properly announce the import functionality.

**Fix:** Add `aria-label` to the label:

```tsx
<label
  className={`...`}
  aria-label={disabled ? "Import Excel (grades frozen)" : "Import Excel"}
>
```

---

### IN-07: localStorage restores dirty cells even when grid is disabled

**File:** `frontend/src/components/academics/score-grid.tsx:47-67`

**Issue:** The `useEffect` that restores dirty cells from localStorage fires unconditionally on mount. If a session is completed (`disabled={true}`), any unsaved dirty cells from a previous editing session are restored and shown with amber row highlighting and "unsaved" badges — but the inputs are disabled so the user cannot save or clear them. This creates a confusing state where the UI appears to show pending changes that can't be acted upon.

**Fix:** Skip localStorage restoration when `disabled` is true:

```tsx
useEffect(() => {
  if (disabled) return; // don't restore dirty cells on frozen grids
  if (restoredRef.current) return;
  // ... existing restoration logic
}, [disabled]);
```

---

### IN-08: Rounding test comment clarity

**File:** `backend/pkg/mathutil/rounding_test.go:38`

**Issue:** The comment `"round half away from zero: 2.5 → 3"` on line 38 is correct for the mathematical rounding behavior at the percent level but could be misinterpreted as the expected basis-point output (which is 250, not 3).

The comment on line 84-87 does an excellent job explaining why `39.995` is excluded from tests due to IEEE 754 limitations.

**Fix** (optional): Clarify the comment:

```go
// round half away from zero at the percent level:
// RoundToBasisPoints(2.5) = 250 basis points (2.5% × 100 = 250 BP)
```

---

_Reviewed: 2026-07-19T16:00:00Z_
_Reviewer: gsd-code-reviewer (agent)_
_Depth: standard_
