# Remaining Work — Phased Plan

## Phase 1: Admin Dashboard (1-2 sessions)

Replace the placeholder `admin.dashboard.tsx` with live data:

- **Stat cards**: Total Students, Teachers, Staff, Active Sessions
- **Results pending approval**: List of results with `status: "teacher-approved"` — each with Approve/Withhold buttons
- **Quick links**: Academics, Users, School Settings, Reports, Teacher Academics
- **Time-bounded greeting** like the teacher dashboard

**Files:** `admin.dashboard.tsx`, `useAcademics.ts` (add `usePendingResults` hook)

---

## Phase 2: Student/Parent Result UX (1 session)

- Add `GET /academic/result/:id/status` endpoint returning `{ status: "not-approved" | "teacher-approved" | "approved" | "withheld" }` without approval gating
- Frontend calls status endpoint first; shows friendly card when not approved
- Shows full result when approved

**Files:** `result/handler.go`, `result/service.go`, `academics.tsx`, `parent/children.$id.tsx`

---

## Phase 3: Admin Assessments Tab (1 session)

Replace the "Coming soon" placeholder in `admin.academics.tsx` with:
- Full assessment list (reuse the curriculum tab pattern from school page)
- Active/inactive toggle per assessment
- "Create Assessment" button

**Files:** `admin.academics.tsx`

---

## Phase 4: Teacher Sidebar Guard (1 session)

- Teacher sidebar `/users/student` should show students only in their assigned levels
- Backend `GET /users/teacher/students` already exists
- Frontend `users.student.tsx` already uses it
- Verify the redirect guard on `/users` prevents teacher access

**Files:** `users.tsx` (add `beforeLoad` guard), `users.student.tsx` (verify)

---

## Phase 5: Excel Score Import (1-2 sessions)

Frontend connect to the existing backend bulk endpoint:
- Upload XLSX button in ScoreGrid toolbar
- Parse workbook with `xlsx` library
- Preview dialog with row count and error list
- Confirm → `POST /academic/scores/bulk`
- Download template from `GET /academic/scores/export`

**Files:** `score-grid.tsx` (already partially wired — needs polish)

---

## Phase 6: Report Cards (2-3 sessions)

Audit and complete the report card generation pipeline:
- Backend: report card PDF generation, template rendering
- Frontend: template editor, batch generation UI, individual report card view
- Wiring: link from results to report cards

**Files:** Multiple — audit needed first

---

## Phase 7: Communication Module (2-3 sessions)

- Compose view (send email/SMS)
- Template management
- Campaign progress tracking
- Delivery logs

**Files:** `communication/*` routes
