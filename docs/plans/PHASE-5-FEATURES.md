# Phase: 5 High-Value Feature Implementations

> **Objective**: Complete 5 backlog features — Assessment Active Toggle UI, Admin/Principal Dashboard, Teacher Dashboard, Result Approval Workflow, and Scheduler Jobs
> **Source**: `docs/plans/PHASE-5-FEATURES.md` (this file)
> **Strategy**: 5 sequential waves, backend-first within each wave, atomic commits
> **Total Waves**: 5 (17 sub-waves)
> **Estimated Effort**: 2–3 sessions

---

## DEPENDENCY GRAPH

```
Wave 1 ──► Wave 2 ──► Wave 3 ──► Wave 4 ──► Wave 5
(Assess-    (Admin      (Teacher    (Result     (Scheduler
 ment       Dashboard)  Dashboard)  Approval)   Jobs)
 Toggle)

Wave 5 has no code dependencies on Waves 1–4
(independent backend-only work — can be done anytime)
```

---

## Wave 1: Assessment Active Toggle UI

**Goal**: Replace the placeholder assessments tab with a real list showing active/inactive status with a toggle switch.

**Backend status**: Already complete — `PUT /api/v2/academic/assessment/:id` accepts `is_active` field in `UpdateAssessmentRequest` DTO. No backend changes needed.

### Tasks

| ID | Task | Area | File | Change |
|----|------|------|------|--------|
| 1.1 | Build assessment list component | Frontend | `admin.academics.tsx` | Fetch assessments for the school; render card/table with name, total weight, grade items count |
| 1.2 | Add active status badge | Frontend | `admin.academics.tsx` | Green badge for active, gray for inactive using `Badge` component |
| 1.3 | Wire toggle switch | Frontend | `admin.academics.tsx` | Toggle calls `PUT /academic/assessment/:id` with `{ is_active: !current }`; invalidate query on success |
| 1.4 | Add "Create Assessment" button | Frontend | `admin.academics.tsx` | Dialog with name + total fields (grade items created separately via curriculum) |
| 1.5 | Verify `useUpdateAssessment` hook | Frontend | `useAcademics.ts` | Confirm hook exists or create if missing; check it sends `is_active` |

**Exit criteria**: Admin can see all assessments, toggle active/inactive, see badge update immediately. `npx tsc --noEmit` passes. `yarn build` passes.

---

## Wave 2: Admin/Principal Dashboard

**Goal**: Replace the placeholder admin dashboard with real data — stat cards, pending approvals, quick links.

### Tasks

| ID | Task | Area | File | Change |
|----|------|------|------|--------|
| 2.1 | Add admin stats endpoint | Backend | `dashboard/handler.go`, `dashboard/service.go`, `dashboard/dto.go` | New aggregate query returning total students, teachers, staff, active sessions count |
| 2.2 | Add pending results endpoint | Backend | `result/handler.go`, `result/service.go` | `GET /result/pending` — list results with `status = "teacher-approved"` waiting for final approval |
| 2.3 | Register new routes | Backend | `router/router.go` | Wire `GET /dashboard/admin` and `GET /result/pending` |
| 2.4 | Build admin dashboard page | Frontend | `admin.dashboard.tsx` | Stat cards (Students, Teachers, Staff, Active Sessions) using `StatsCard` component |
| 2.5 | Add pending approvals section | Frontend | `admin.dashboard.tsx` | List of teacher-submitted results with Approve/Withhold buttons |
| 2.6 | Add quick links section | Frontend | `admin.dashboard.tsx` | Academics, Users, School Settings, Reports using existing `QuickActions` component |
| 2.7 | Create `usePendingResults` hook | Frontend | `useAcademics.ts` | Fetches pending results from `GET /result/pending` |

**Exit criteria**: Admin dashboard shows real stats, pending approvals list with approve/withhold functionality. `go build ./...`, `go vet ./...`, `npx tsc --noEmit` all pass.

---

## Wave 3: Teacher Dashboard

**Goal**: Replace the teacher redirect from admin dashboard with a dedicated teacher dashboard showing relevant data.

### Tasks

| ID | Task | Area | File | Change |
|----|------|------|------|--------|
| 3.1 | Create teacher dashboard route | Frontend | `teacher/dashboard.tsx` | New route file under `_dashboard/teacher/` with TanStack Router file conventions |
| 3.2 | Add welcome + session card | Frontend | `teacher/dashboard.tsx` | "Welcome, [Name]" greeting; active session stat card using `useSessions()` |
| 3.3 | Add classes + subjects cards | Frontend | `teacher/dashboard.tsx` | Teacher's assigned classes (from teacher profile `levels`) and subjects count |
| 3.4 | Add current assessment card | Frontend | `teacher/dashboard.tsx` | Shows active assessment name; "Enter Scores →" link to assessment scoring page |
| 3.5 | Add quick actions section | Frontend | `teacher/dashboard.tsx` | Links: Enter Scores, View Results, My Timetable, My Subjects |
| 3.6 | Add recent activity section | Frontend | `teacher/dashboard.tsx` | Placeholder for now — wire to audit log API in future |
| 3.7 | Update dashboard redirect | Frontend | `_dashboard/dashboard.tsx` | Already exists (line 32) — verify teacher redirect points to new route |

**Exit criteria**: Teachers redirected to `/teacher/dashboard` showing real data. Stat cards populated. Quick actions navigate correctly. `npx tsc --noEmit` passes.

---

## Wave 4: Result Approval Workflow

**Goal**: Implement two-tier approval (teacher submit → admin approve) with status gating and per-score comments.

### Tasks

| ID | Task | Area | File | Change |
|----|------|------|------|--------|
| 4.1 | Add `ResultTeacherApproved` enum | Backend | `models/enums.go` | `const ResultTeacherApproved = "teacher-approved"` |
| 4.2 | Add `SubmitResultRequest` DTO | Backend | `result/dto.go` | `{ comment string }` — teacher's submission rationale |
| 4.3 | Add `SubmitResult` method | Backend | `result/service.go` | Validates class teacher ownership, sets status to `teacher-approved`, stores comment |
| 4.4 | Add `POST /result/:id/submit` handler | Backend | `result/handler.go` | Call service method, return updated result |
| 4.5 | Gate `ApproveResult` on status | Backend | `result/service.go` | Only allow approve/withhold when status is `teacher-approved` |
| 4.6 | Register submit route | Backend | `router/router.go` | `POST /api/v2/result/:id/submit` |
| 4.7 | Add teacher submit button | Frontend | `teacher/results.tsx` | "Submit for Approval" button when status is `not-approved` |
| 4.8 | Wire pending approvals | Frontend | `admin.dashboard.tsx` | Approve/Withhold calls `PUT /result/:id/approve`, refreshes list |

**Exit criteria**: Teacher can submit results for approval. Admin can approve/withhold submitted results. Status transitions enforced. `go build ./...`, `go vet ./...` pass.

---

## Wave 5: Scheduler Jobs

**Goal**: Wire up the stub `weeklyReportJob` and `monthlyBillingJob` in the scheduler.

### Tasks

| ID | Task | Area | File | Change |
|----|------|------|------|--------|
| 5.1 | Add `TypeWeeklyReport` task type | Backend | `queue/tasks.go` | New constant + `NewReportGenerateTask` constructor with school/session context |
| 5.2 | Add `TypeMonthlyBilling` task type | Backend | `queue/tasks.go` | New constant + `NewBillingTask` constructor with school/period context |
| 5.3 | Wire `weeklyReportJob` | Backend | `scheduler/jobs.go` | Query active sessions/enrolled students, enqueue `report:generate` tasks per class |
| 5.4 | Wire `monthlyBillingJob` | Backend | `scheduler/jobs.go` | Query active accounts with billing config, enqueue billing tasks |
| 5.5 | Register task handlers | Backend | `queue/worker.go` | Wire new task types to `ReportGenerateHandler` and `BillingHandler` stubs |
| 5.6 | Verify cron registration | Backend | `scheduler/cron.go` | Confirm `WeeklyReport` and `MonthlyBilling` are registered in cron schedule |

**Exit criteria**: Scheduler triggers weekly/monthly jobs. Tasks enqueued to Asynq (observed in logs). No compile errors. `go build ./...`, `go vet ./...` pass.

---

## SUCCESS CRITERIA

- [ ] Assessment list shows all assessments with active/inactive toggle
- [ ] Admin dashboard displays real stats and pending approvals
- [ ] Teacher dashboard shows active session, classes, subjects, assessment card
- [ ] Teacher can submit results, admin can approve/withhold
- [ ] Scheduler enqueues weekly report and monthly billing tasks
- [ ] `go build ./...` and `go vet ./...` pass after every backend change
- [ ] `npx tsc --noEmit` and `yarn build` pass after every frontend change
- [ ] Integration tests pass: `bash scripts/test_endpoint.sh`

---

## RISK ASSESSMENT

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Teacher dashboard redirect breaks existing flow | High | Low | Verify redirect works before/after; test manually |
| Result status gating blocks legitimate approvals | High | Low | Add migration for existing results; test transition matrix |
| Scheduler cron timing overlaps with backup | Low | Medium | Stagger cron schedules; add jitter |
| CSRF token missing on toggle/approve mutations | Medium | Low | Follow existing pattern from `useUploadMedia` — call `getCSRFToken()` |
| Base UI Select shows raw IDs on assessment form | Medium | Low | Follow `frontend/AGENTS.md` hard rule pattern (names as values) |

---

## ROLLBACK PLAN

Each wave is independently revertible via git:
1. Complete a wave → commit
2. If issues found, revert the wave's commit(s) without affecting others
3. Waves 1–3 (frontend-heavy) can be rolled back by reverting route file changes
4. Waves 4–5 (backend + DB enums) need schema-aware rollback if migrations are involved
