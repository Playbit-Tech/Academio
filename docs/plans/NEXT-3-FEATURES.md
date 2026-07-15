# Next 3 Features — Plan

## 1. Assessment Active Toggle UI

### Current State
- `IsActive` field exists on `Assessment` model
- Backend gates score entry/update against it
- But no UI to toggle it — assessments are always `active` (default)

### Implementation

**Backend** — `UpdateAssessmentRequest` already has `IsActive` from our earlier work. The `PUT /api/v2/academic/assessment/:id` endpoint already accepts it.

**Frontend — Admin Academics page** (`admin.academics.tsx`):
- Replace the "Assessments & Scores" placeholder tab with a real assessment list
- Show all assessments for the school with: name, total weight, grade items count, active status badge (green/gray)
- Toggle switch to activate/deactivate each assessment
- Refresh list after toggle via `queryClient.invalidateQueries`
- Minor: an "Add Assessment" button with name + total (grade items created separately via curriculum)

**Files:** `admin.academics.tsx`, `useAcademics.ts`

---

## 2. Admin/Principal Dashboard

### Current State
- `admin.dashboard.tsx` is a placeholder with "coming soon" card

### Implementation

Replace with real data:
- **Stat cards**: Total Students, Teachers, Staff, Active Sessions
- **Results pending approval**: list of results with `status: "teacher-approved"` waiting for final approval — each with Approve/Withhold buttons
- **Quick links**: Academics, Users, School Settings, Reports
- **Recent activity**: placeholder (can come from audit log API later)

**Files:** `admin.dashboard.tsx`, `useAcademics.ts` (add `usePendingResults` hook)

---

## 3. Student/Parent Result Approval UX

### Current State
- `GetResult` hides unapproved results from students/parents (returns 404)
- No friendly messaging when results aren't ready

### Implementation
- In `academics.tsx` (student view), when the result query returns 404/empty, detect whether it's "not yet approved" vs "no data exists" by hitting a lightweight status endpoint
- Show a friendly card: "Your results for [Assessment Name] are being reviewed by your class teacher. Check back later."
- When approved, show the result as before

**Simpler alternative**: Add a `GET /academic/result/:id/status` endpoint that returns `{ status: "not-approved" | "teacher-approved" | "approved" | "withheld" }` without requiring approval gating. The student UI calls this first, then conditionally shows the full result.

**Files:** `result/handler.go`, `result/service.go`, `academics.tsx`
