# Code Review Fixes — Phase Plan

> **Objective**: Resolve 13 findings from comprehensive code review of session changes
> **Source**: AGENTS.md anchored summary + `docs/plans/CR-CODE-REVIEW-FIXES.md` (this file)
> **Strategy**: Sequential phases grouped by severity, atomic commits per phase
> **Total Phases**: 4

---

## DEPENDENCY GRAPH

```
Phase 1 ──► Phase 2 ──► Phase 3
(Backend      (Backend      (Frontend
 Address       Hygiene)      UX Fixes)
 Validation)
                             │
                        Phase 4 can run parallel
                        (Low-severity polish)
```

---

## Phase 1: BatchCreateStudents Address Validation Fix

**Goal**: Fix broken `address == ""` comparison for `any` type in BatchCreateStudents

| ID | Task | File | Change |
|---|---|---|---|
| 1.1 | Create `isEmptyAddress(a any) bool` | `service.go` | Returns `true` for nil, empty string, empty map; `false` for populated string/map |
| 1.2 | Replace `req.Father.Address == ""` with `isEmptyAddress(req.Father.Address)` | `service.go:650` | Father address validation works for both string and map types |
| 1.3 | Same for mother | `service.go:664` | Mother address validation |
| 1.4 | Same for guardian | `service.go:678` | Guardian address validation |

**Exit criteria**: `go build ./...` and `go vet ./...` pass. XLSX rows with empty address correctly rejected. Form submissions with empty address `{}` correctly rejected.

---

## Phase 2: Backend Hygiene — Error Handling & Logging

**Goal**: Stop swallowing errors; collect all validation errors in one pass

| ID | Task | File | Change |
|---|---|---|---|
| 2.1 | Handle `json.Marshal(details)` error | `service.go:1512` | `fmt.Errorf("marshal parent details: %w", err)` |
| 2.2 | Log role assignment failures | `service.go:1411-1415` | `logger.Warnf(...)` when FindOrCreateRole or AssignRoleToUser fails |
| 2.3 | Collect all parent field errors before `continue` | `service.go:637-682` | Build slice of missing fields, join with commas, single `continue` |
| 2.4 | Log DB error during email lookup dedup | `service.go:1409` | `logger.Warnf("email lookup failed: %v", err)` before fallthrough |

**Exit criteria**: `go build ./...`, `go vet ./...`. No more discarded errors in changed functions. Validation shows all missing fields in one error message.

---

## Phase 3: Frontend Validation UX

**Goal**: Fix misleading errors and add navigation guardrails

| ID | Task | File | Change |
|---|---|---|---|
| 3.1 | Fix checkbox error path | `users.tsx:108-113` | Add the "at least one parent" issue to all three `has_*` paths |
| 3.2 | Validate step 1 fields before "Continue" | `users.tsx:376-380` | Trigger validation on Continue, block navigation if invalid |
| 3.3 | Return `undefined` from `buildAddress()` when empty | `users.tsx:57-65` | `return Object.keys(addr).length > 0 ? addr : undefined` |

**Exit criteria**: `tsc --noEmit` passes. Form validation shows correct error next to relevant checkbox. Step 1 validates before navigating. No empty `{}` address stored.

---

## Phase 4: Low-Severity Polish

**Goal**: Address remaining edge cases and inconsistencies

| ID | Task | File | Change |
|---|---|---|---|
| 4.1 | Add `Number()` coercion for `class_level` | `school.tsx` | Guard against string type from API |
| 4.2 | Remove `enabled: !!schoolId` from `useSubjects` | `useSchool.ts:89` | Align with `useClasses` behavior |
| 4.3 | Document `ActiveContinuousAssessmentID` FK edge case | `curriculum.go` | Comment about deletion behavior |
| 4.4 | Extract step indicator class logic to helper | `users.tsx` | Clean up repeated tri-state ternary |

**Exit criteria**: `tsc --noEmit` passes. `go build ./...` passes. Documentation comment added.

---

## EXECUTION STRATEGY

- **Phase 1 → Phase 2 → Phase 3** — strictly sequential (backend before frontend)
- **Phase 4** — can run after Phase 2 or parallel with Phase 3 (no backend/frontend dependency conflict)
- Each phase produces an atomic commit with message format: `fix(cr): phase N — description`
- All phases verified with `go build ./... && go vet ./... && npx tsc --noEmit`

## Plan Location

This plan lives at `docs/plans/CR-CODE-REVIEW-FIXES.md`. Future agents should read this file before implementing any code-review fix work to avoid duplicate or conflicting changes.
