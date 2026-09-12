# Per-Role Guide

> **Audience:** School admins onboarding new staff; engineers verifying dashboard behavior.
> **Cross-checked:** T4a (API) + T4b (UI) E2E results.

---

## 1. Super Admin (`super_admin`)

- **Landing:** `/super`
- **Dashboard branch:** N/A (super-admin uses dedicated `/super` landing, not `/dashboard`)
- **School context:** Platform-wide; bypass all RBAC checks
- **Visible modules:** Everything — all 40+ nav items visible
- **Core actions:** School management, user impersonation, platform settings, database operations
- **Key permissions:** `platform:manage` (exclusive to super_admin)
- **E2E proof:** Session valid, platform ops accessible

---

## 2. Admin (`admin`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `generic` (has `users:write` → all specialist branches excluded)
- **School context:** School-scoped; first-school-wins
- **Visible modules:** All admin nav items except platform-only surfaces
- **Core actions:** Full user management, curriculum setup, session management, finance administration, school settings
- **Key grants:** Full catalog minus `platform:manage`
- **E2E proof:** `users:read` confirmed, `/users/list` accessible, `platform:manage` absent (fail-closed)
- **Cannot:** Platform operations (`/super`)

---

## 3. Teacher (`teacher`)

- **Landing:** `/teacher/dashboard`
- **Dashboard branch:** N/A (dedicated `/teacher/dashboard` landing, not `/dashboard`)
- **School context:** School-scoped; class-level row scoping in services
- **Visible modules:** Academics, grading, attendance, timetable, students, results, LMS, media, AI, forum
- **Core actions:** Grade students, take attendance, manage timetables, view results, communicate with parents
- **Key grants:** `grading:read/write`, `attendance:read/write`, `results:read`, `students:read/write`
- **E2E proof:** `grading:read` confirmed, timetables accessible, forged approve → 403
- **Cannot:** Finance, HR, health, admissions, settings, user management

---

## 4. Student (`student`)

- **Landing:** `/academics`
- **Dashboard branch:** N/A (dedicated `/academics` portal landing)
- **School context:** School-scoped; own records only
- **Visible modules:** Academics, timetable, calendar, forum, LMS, notifications, results, media, AI, payments
- **Core actions:** View grades, check timetable, access learning materials, submit forum posts
- **Key grants:** `timetable:read`, `results:read`, `lms:read`, `forum:read/write`, `payments:pay`
- **E2E proof:** `timetable:read` confirmed, student dashboard portal accessible
- **Cannot:** Any write operations on other students, finance, HR, admin

---

## 5. Parent (`parent`)

- **Landing:** `/parent`
- **Dashboard branch:** N/A (dedicated `/parent` portal landing)
- **School context:** School-scoped; linked children only
- **Visible modules:** Parent portal, children's results, timetable, calendar, finance (read), health (read), forum, notifications, payments
- **Core actions:** View children's results, check attendance, pay fees, view health records (own child)
- **Key grants:** `students:read`, `results:read`, `health:read`, `finance:read`, `timetable:read`
- **E2E proof:** `health:read` confirmed, parent dashboard accessible, school-summary → 403 (PHI gate)
- **Cannot:** Health school-summary (403 — PHI), grading, any write operations

---

## 6. Principal (`principal`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `principal` (`sessions:write` ∧ ¬`users:write` ∧ ¬`schools:write`)
- **School context:** School-scoped; academically-scoped admin
- **Visible modules:** Academics, sessions, grading, results, attendance, timetable, reports, analytics, discipline, pastoral, career, health (read + manage), communication, audit, branding, email studio, users (read-only)
- **Core actions:** Approve results (D-C approve chain), manage sessions, view analytics, oversee discipline, approve pastoral cases, communicate with parents
- **Key grants:** `sessions:write`, `grading:read/write`, `results:read`, `health:manage`, `communication:write`, `career:read/write`
- **E2E proof:** `sessions:write` confirmed, `users:write` absent (fail-closed), D-C approve → 200, expense approve → 403
- **Cannot:** `users:write`, `finance:write`, `hr:write`, `schools:write` (academically-scoped by design)

---

## 7. Staff (`staff`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `generic` (permission-less by design; specialist discriminators require module-write perms)
- **School context:** School-scoped; grant-by-grant via RBAC admin
- **Visible modules:** Depends on granted permissions (empty state when zero grants)
- **Core actions:** Depends on grants — e.g. attendance scan, leave requests, payslip viewing
- **Default grants:** ZERO (permission-less by design)
- **Sections (when granted):**
  - `attendance:read/write` → Attendance / Scan
  - `hr:read` → Leave Requests, Payslips
  - `hostel:read` → Hostel Roster
- **E2E proof (zero-grant):** Empty permissions, empty state, no 403 noise on mount
- **E2E proof (granted):** `attendance:read` confirmed, held section accessible, unheld section → 403
- **Cannot:** Anything without explicit grant. Custom roles per school.

---

## 8. Accountant (`accountant`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `accountant` (`finance:write` ∧ ¬`users:write`)
- **School context:** School-scoped; finance module only
- **Visible modules:** Finance, invoices, expenses, reports, audit (read), students (read), users (read)
- **Core actions:** Create/manage invoices, approve expenses, view financial reports, reconcile overdue invoices
- **Key grants:** `finance:read/write/delete/manage/export`, `audit:read`, `reports:read/export`
- **E2E proof:** `finance:write` confirmed, invoices accessible, expense approve → 200, audit-logs readable
- **Cannot:** `users:write`, any non-finance modules

---

## 9. Librarian (`librarian`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `librarian` (`library:write` ∧ ¬`finance:write` ∧ ¬`sessions:write` ∧ ¬`users:write`)
- **School context:** School-scoped; library module only
- **Visible modules:** Library, media (read), students (read)
- **Core actions:** Issue books, process returns, manage library inventory, view circulation summary
- **Key grants:** `library:read/write/delete/manage`, `media:read`, `students:read`
- **E2E proof:** `library:write` confirmed, summary accessible, issue→return chain completes, forged expense approve → 403
- **Cannot:** `finance:write`, `sessions:write`, `users:write`

---

## 10. Nurse (`nurse`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `nurse` (`health:write` ∧ ¬`users:write`)
- **School context:** School-scoped; health module only
- **Visible modules:** Student health, health records, students (read)
- **Core actions:** Record clinic visits, manage allergies, track immunizations, view health summary
- **Key grants:** `health:read/write/delete/manage`, `students:read`
- **E2E proof:** `health:manage` confirmed, school-summary → 200 (nurse PHI holder), visit audit row present
- **Cannot:** `users:write`, any non-health modules

---

## 11. Guidance Counselor (`counselor`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `counselor` (`pastoral:write` ∧ ¬`sessions:write` ∧ ¬`users:write`)
- **School context:** School-scoped; pastoral + career modules
- **Visible modules:** Pastoral, discipline (read), career, reports (read), students (read)
- **Core actions:** Manage pastoral cases (self-only), create discipline reports, guide career counseling
- **Key grants:** `pastoral:read/write/delete/manage`, `career:read/write`, `discipline:read`, `reports:read`
- **E2E proof:** `pastoral:write` confirmed, self-only caseload (counselor-A ≠ counselor-B), forged discipline POST → 403
- **Self-only filter:** Counselors see only their own caseload rows (enforced at API level)
- **Cannot:** `sessions:write`, `users:write`, discipline write/delete (read-only)

---

## 12. Admissions Officer (`admissions`)

- **Landing:** `/dashboard`
- **Dashboard branch:** `admissions` (`admissions:write` ∧ ¬`users:write`)
- **School context:** School-scoped; admissions pipeline
- **Visible modules:** Admissions (applications, intakes, forms, screening, offers), communication (read), students (read/write)
- **Core actions:** Screen applications, create offers, manage enrollment pipeline, track intake performance
- **Key grants:** `admissions:read/write/delete/manage/export`, `communication:read`, `students:read/write`
- **E2E proof:** `admissions:write` confirmed, screen→offer→accept→enroll SC3b chain completes
- **Cannot:** `users:write`, any non-admissions modules

---

## Cross-Role Patterns

### PHI (Protected Health Information) Gate

- **Parent** holds `health:read` → can view own child's health records
- **Parent** is denied `GET /student-health/school-summary` → 403 (PHI policy)
- **Nurse** holds `health:manage` → school-summary accessible (200)
- **Principal** holds `health:manage` → school-summary accessible (200)
- **All others** → 403 on school-summary

### D-C (Display-Certification) Approve Chain

1. Teacher saves scores → `POST /academic/scores/bulk` (200)
2. Result status: `teacher-approved` (needs `SessionID` + `AssessmentID` — seed fix)
3. Principal approves → `PUT /academic/result/:id/approve` → 200
4. Result published → parent sees approved result
5. Idempotent: re-publish → 200 (no duplicate)

### Forged-Call Defense

All specialist dashboards include forged-call spot-checks in T4a:
- Teacher forged approve → 403
- Librarian forged expense approve → 403
- Counselor forged discipline POST → 403
- Principal forged expense approve → 403
