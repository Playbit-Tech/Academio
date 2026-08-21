# Academio Functional Specification — Part 2: Requirements

| Attribute | Value |
|---|---|
| **Document** | FSD Part 2 — Requirements |
| **Product** | Academio — Enterprise School Management & Education ERP |
| **Version** | 1.0 |
| **Status** | Draft for review |
| **Date** | 31 July 2026 |
| **Source documents** | `docs/architecture/INDEX.md`, `docs/architecture/1-VISION-AND-STRATEGY.md`, `docs/architecture/7-USE-CASES.md`, `docs/PROJECT.md`, `AGENTS.md`, `ACADEMIO_IMPLEMENTATION_PLAN.md`, `docs/NG-EDUCATION-STANDARDS.md`, `docs/NG-LESSON-NOTE-PLAN-STANDARDS.md`, `docs/WORKFLOW-IMPLEMENTATION.md`, `docs/COMPLIANCE-ACCREDITATION.md`, `docs/ABUSE-PREVENTION.md`, `docs/performance-baseline.md`, `docs/ops/load-test-baseline.md` |
| **Implementation basis** | Verified against 49 backend modules under `backend/internal/modules/`, frontend route tree under `frontend/src/routes/`, and API client surface in `frontend/src/lib/api.ts` |

---

## 0. Document Purpose and Scope

This document is Part 2 of the Academio Functional Specification set. It defines the functional and non-functional requirements, user stories, use cases, user journeys, and acceptance criteria for the Academio platform as currently implemented.

The requirements in this document are grounded in the **verified implementation state** of the codebase (49 backend modules, the frontend route tree, and the API client surface). Features that are documented as design targets but not yet implemented are explicitly marked **Planned** and are never described as implemented behaviour.

### 0.1 Relationship to the FSD Set

| Part | Document | Relationship to this document |
|---|---|---|
| 01 | `01-PRODUCT.md` | Product overview, personas, product vision. This document elaborates the requirements derived from Part 1 scope. |
| 02 | `02-REQUIREMENTS.md` (this document) | Functional + non-functional requirements, user stories, use cases, journeys, acceptance criteria. |
| 03 | `03-UX-DESIGN.md` | UX design: wireframes, information architecture, navigation, UI component standards. Requirements in Sections 3.21 and 4.6 constrain UI behaviour (entity-name selects, root-layout toaster, portal surfaces). |
| 04 | `04-DATA-API.md` | API contract for every FR listed here. Each FR maps to one or more endpoints defined in Part 4 (response envelope, pagination, error format). |
| 05 | `05-PLATFORM.md` | Test strategy, acceptance criteria execution, quality gates (k6 baselines, `backend/scripts/test_endpoint.sh`). Acceptance criteria in Section 8 are the input to Part 5 test cases. |
| 06 | `06-ENGINEERING.md` | Engineering standards and process. Non-functional requirements in Section 4.7 (maintainability) cross-reference Part 6. |

### 0.2 Referenced Architecture and Standards Documents

- `docs/architecture/1-VISION-AND-STRATEGY.md` — product vision, student lifecycle, roadmap phases.
- `docs/architecture/7-USE-CASES.md` — 15 actor personas and 15 use cases; Section 6 derives from and extends this document.
- `docs/NG-EDUCATION-STANDARDS.md` — Nigerian 1-6-3-3-4 structure, WAEC/NECO/JAMB examination systems, grading scales.
- `docs/NG-LESSON-NOTE-PLAN-STANDARDS.md` — lesson plan and lesson note standards for the Nigerian curriculum.
- `docs/WORKFLOW-IMPLEMENTATION.md` — approval workflow requirements (results, admissions, leave, expenses, etc.).
- `docs/COMPLIANCE-ACCREDITATION.md` — Lagos State compliance and accreditation requirements.
- `docs/ABUSE-PREVENTION.md` — free-tier limits, rate limits, verification safeguards.
- `docs/performance-baseline.md` and `docs/ops/load-test-baseline.md` — performance budgets cited in Section 4.

### 0.3 Conventions

- **Requirement identifiers**: `FR-<AREA>-<NN>` (functional), `NFR-<AREA>-<NN>` (non-functional), `US-<NN>` (user story), `UC-<NN>` (use case), `UJ-<NN>` (user journey), `AC-<NN>` (acceptance criterion).
- **Priority levels**: `MUST` (P0 — release blocking), `SHOULD` (P1 — important, can ship behind flag), `COULD` (P2 — desirable), `WON'T` (P3 — explicitly out of scope for current phase).
- **Implementation status**: `Implemented` (verified in code), `Partially implemented` (core flow verified, extension marked Planned), `Planned` (documented design target, not yet in code).
- **Currency**: All monetary values are Nigerian Naira (NGN, symbol ₦) unless a field explicitly states otherwise. All monetary amounts are stored and displayed as NGN.

### 0.4 Verification Basis

The requirements below were verified against:

1. `backend/internal/modules/` — **49 modules** listed in Section 3.1.
2. `frontend/src/routes/` — route tree under `_dashboard`, `_public`, `_super`, `_onboarding` (verified 30 July 2026).
3. `frontend/src/lib/api.ts` — native `fetch`-based client with Bearer token injection, 401-refresh-retry, CSRF header injection on mutations, 30 s timeout, 2-retry exponential backoff, `x-school-id` header injection, and `{ success, data, error, meta }` envelope unwrapping.

---

## 1. Product Summary

Academio is a multi-tenant School Management / Education ERP platform serving nursery, primary, secondary, tertiary, and training institutions. It covers the complete student lifecycle — Prospect, Applicant, Admission, Student, Academic Progress, Graduate, Alumni — and provides operational modules for finance, HR, library, hostel, transport, inventory, discipline, health, CBA, and LMS.

**Core product principles (from `docs/architecture/1-VISION-AND-STRATEGY.md`):**

| Principle | Requirement impact |
|---|---|
| AI-first, not AI-added | AI module (chat, search, agents) exists; deeper AI assistance per module is Planned |
| Student lifecycle unification | Single student record from prospect to alumni; admissions flow ends in enrollment |
| API-first ecosystem | Every FR is exposed via `/api/v2` endpoints |
| Real-time by default | WebSocket hub exists; notifications and messaging operate on top of it |
| Cloud-native multi-tenancy | Schema-per-tenant isolation (`school_{id}` schemas), shared `public` schema for users |

**Implementation status at a glance (verified):**

- **Implemented**: 49 backend modules; frontend dashboard, public, super-admin, and onboarding route groups; full academic scoring, result approval, admissions, CBA, finance, HR, alumni, LMS, communication, and portal surfaces.
- **Planned (documented, not in code)**: generic Workflow Engine (`docs/WORKFLOW-IMPLEMENTATION.md`), compliance/accreditation module (`docs/COMPLIANCE-ACCREDITATION.md`), AI-assisted essay grading, risk prediction agents, multi-campus management, mobile Flutter apps (`ACADEMIO_IMPLEMENTATION_PLAN.md`), BI forecasting.

---

## 2. Module Inventory (Implementation Basis)

### 2.1 Verified Backend Modules (49)

| # | Module | Area (this document) | # | Module | Area (this document) |
|---|---|---|---|---|---|
| 1 | `academic` | Academic | 26 | `lessonplan` | LSM/LMS |
| 2 | `academic-calendar` | Academic | 27 | `library` | Library |
| 3 | `admission` | Admissions | 28 | `lms` | LSM/LMS |
| 4 | `ai` | AI Assistant | 29 | `media` | LSM/LMS |
| 5 | `alumni` | Alumni | 30 | `messages` | Communication/Messaging |
| 6 | `analytics` | Reports/Analytics | 31 | `multimedia` | LSM/LMS |
| 7 | `audit` | Core Platform | 32 | `notifications` | Communication/Messaging |
| 8 | `auth` | Core Platform | 33 | `parentdashboard` | Portals |
| 9 | `bill` | Finance/Billing | 34 | `pastoral` | Health/Pastoral |
| 10 | `career` | Alumni/Career | 35 | `payment` | Finance/Billing |
| 11 | `cba` | CBA | 36 | `proctoring` | CBA |
| 12 | `communication` | Communication/Messaging | 37 | `rbac` | Core Platform |
| 13 | `conference` | LSM/LMS (PTC) | 38 | `reportbuilder` | Reports/Analytics |
| 14 | `dashboard` | Reports/Analytics | 39 | `reportcard` | Reports/Analytics |
| 15 | `discipline` | Discipline | 40 | `reports` | Reports/Analytics |
| 16 | `exam` | Assessment/Results | 41 | `result` | Assessment/Results |
| 17 | `external_exam` | Assessment/Results | 42 | `school` | Core Platform |
| 18 | `finance` | Finance/Billing | 43 | `score` | Assessment/Results |
| 19 | `forum` | LSM/LMS | 44 | `studenthealth` | Health/Pastoral |
| 20 | `grading` | Assessment/Results | 45 | `studentportal` | Portals |
| 21 | `health` | Health/Pastoral | 46 | `tenant` | Core Platform |
| 22 | `hostel` | Hostel | 47 | `timetable` | Timetable |
| 23 | `hr` | HR/Payroll | 48 | `transport` | Transport |
| 24 | `inventory` | Inventory | 49 | `user` | Core Platform |
| 25 | `invitation` | Core Platform | — | — | — |

### 2.2 Verified Frontend Route Groups

| Route group | Verified surfaces (abridged) |
|---|---|
| `_dashboard/` | dashboard, school, users (students/teachers/staff), academics, attendance, exams, grading, results (incl. master-sheet), timetable, cba (exams, take, results), lms (courses, assignments, discussions), lesson-plans (plans, notes, schemes), report-cards (single, batch), bills, payment, finance, hr, library, hostel, transport, inventory, discipline, pastoral, student-health, communication (compose, campaigns, broadcast, templates, delivery), messages, notifications, invitations, media, conferences, forum, alumni (incl. insights), career, analytics (academic, enrollment, revenue), reports (incl. builder), ai-assistant, audit-logs, promotion, external-exam, proctoring, parent (children, child detail), student (results, report-cards, fees, timetable, attendance), teacher (dashboard, class, attendance, academics, results, report-cards, timetable) |
| `_public/` | landing, features, how-to-use, about, editions, admissions (apply, status), legal pages |
| `_super/` | super-admin tenant console (list, detail) |
| `_onboarding/` | school setup wizard |

### 2.3 Verified API Client Capabilities (`frontend/src/lib/api.ts`)

- `fetch`-based; automatic Bearer token injection; `x-school-id` injection from the user's first school or session.
- Deduplicated 401 → refresh → retry; proactive refresh before requests when access token is missing.
- CSRF token acquisition (lazy, cached) attached to all mutating requests.
- 30-second request timeout; network retry (2 attempts, exponential backoff 500 ms → 1000 ms).
- Cross-tab auth sync via `BroadcastChannel` (`academio-auth`).
- Admin impersonation helpers (`/admin/impersonate`, `/admin/impersonate/stop`), user deactivation, permanent deletion.

---

## 3. Functional Requirements

Functional requirements are organized by business area. Each requirement maps to verified modules from Section 2.1. **No unimplemented feature is listed as a functional requirement**; planned capabilities appear only in the "Planned" note of each section and in the use-case matrix (Section 6).

### 3.1 Core Platform — Authentication, Users, Tenancy, RBAC, Audit

Modules: `auth`, `user`, `school`, `tenant`, `rbac`, `audit`, `invitation`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-AUTH-01 | The system MUST authenticate users by username/identifier and bcrypt-hashed password and issue a short-lived JWT access token with a rotating refresh token. | P0 | `auth` |
| FR-AUTH-02 | The system MUST support optional TOTP two-factor authentication for user accounts. | P1 | `auth`, `pkg/totp` |
| FR-AUTH-03 | The system MUST revoke tokens on logout and blacklist revoked JWTs in Redis until natural expiry. | P0 | `auth`, `internal/services/blacklist_service.go` |
| FR-AUTH-04 | The system MUST issue nonce-based CSRF tokens and require the `X-CSRF-Token` header on all mutating requests. | P0 | `auth`, `middleware/csrf.go` |
| FR-AUTH-05 | The system MUST enforce per-IP rate limiting on login attempts (free tier: 5 per minute per IP) and per-tenant API rate limits (free tier: 60 per minute per school). | P0 | `middleware/ratelimit.go` |
| FR-AUTH-06 | The system MUST support password reset via email and email confirmation flows (forgot-password, reset-password, confirm-email routes). | P0 | `auth` |
| FR-AUTH-07 | The system MUST support admin impersonation of a user with a full audit trail, and a stop-impersonation endpoint. | P1 | `auth`, `audit` |
| FR-USR-01 | The system MUST provide user CRUD with role assignment, soft-deactivate (`/user/deactivate/:id`) and permanent deletion (`/user/:id`). | P0 | `user` |
| FR-USR-02 | When creating parent/guardian accounts, the system MUST deduplicate identities by priority: **email → phone → username**. | P0 | `user` |
| FR-USR-03 | The system MUST support invitation-based provisioning of staff, students, and parents via secure invitation codes rather than open self-registration inside a school. | P1 | `invitation`, `user` |
| FR-SCH-01 | The system MUST create a school with a synchronous provisioning flow: create `school_{id}` tenant schema, run tenant migrations, seed initial data, then set `schema_name`; the frontend MUST poll `GET /api/v2/schools/:id` until `schema_name` is non-empty. | P0 | `school`, `tenant`, `internal/queue/handlers/provisioning_handler.go` |
| FR-TEN-01 | The system MUST resolve tenant database connections per request via the `x-school-id` header, using `middleware.GetTenantDB(c)` for all tenant-scoped queries; no raw core DB access and no hardcoded schema names. | P0 | `tenant`, `middleware/tenant.go` |
| FR-TEN-02 | The system MUST store per-tenant database credentials encrypted at rest (AES-256-GCM) and maintain a pooled connection manager with periodic health checks. | P0 | `tenant`, `internal/crypto` |
| FR-RBAC-01 | The system MUST provide role and permission CRUD and enforce permission checks on sensitive routes (finance, HR, admissions, super-admin). | P0 | `rbac` |
| FR-AUD-01 | The system MUST record an audit log entry for every mutation with `SchoolID`, `UserID`, `Action`, `ResourceType`, and `RequestID`. | P0 | `audit`, `middleware/audit.go` |
| FR-MID-01 | The system MUST apply the documented middleware chain in order: recovery, request ID, tracing, error handler, structured logging, security headers, CORS, body limit, school ID extraction, Redis rate limiting, CSRF, JWT, tenant resolution, audit, tenant DB resolver. | P0 | `middleware/*`, `cmd/server/main.go` |
| FR-SUP-01 | The system MUST provide a super-admin console to list and inspect tenants (verified route group `_super/`). | P1 | `school`, `tenant` |

**Planned (not implemented — excluded from FR list)**: generic configurable Workflow Engine (`docs/WORKFLOW-IMPLEMENTATION.md`); distributed tracing rollout; OpenAPI 3.1 beyond Swagger; horizontal pod autoscaling.

### 3.2 Academic — Sessions, Curriculum, Assessment, Grade Items, Calendar, Grading, Promotion

Modules: `academic`, `academic-calendar`, `grading`, `exam`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-ACA-01 | The system MUST support academic session CRUD (term/session structure), active-session selection, session completion, and curriculum-to-session linking. | P0 | `academic` |
| FR-ACA-02 | The system MUST support curriculum CRUD per session, aligned with Nigerian education structure (1-6-3-3-4) and NERDC subject sets. | P0 | `academic` |
| FR-ACA-03 | The system MUST support assessment CRUD per session (e.g. first term, mid-term, exam) and per assessment grade-item configuration. | P0 | `academic` |
| FR-ACA-04 | The system MUST support grade item CRUD, grade override enable/disable, and score aggregation across grade items. | P0 | `academic`, `score` |
| FR-ACA-05 | The system MUST provide promotion preview and execution when a session is completed. | P1 | `academic` |
| FR-ACA-06 | The system MUST support academic calendar management: calendar view, events, periods, and reusable blueprints. | P1 | `academic-calendar` |
| FR-GRA-01 | The system MUST support configurable grading scales for internal assessments (subject to the Nigerian WAEC-style A1–F9 scale where configured). | P1 | `grading` |
| FR-EXM-01 | The system MUST support exam schedule management (list, create, update, delete, view results, publish toggle). | P1 | `exam` |

**Planned**: AI-generated lesson plans and question generation (see Section 3.19 and UC-9).

### 3.3 Admissions

Module: `admission` (verified handler surface: intakes, public forms, applications, screening, entrance exam, offers, enrollment, form builder, dashboard stats).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-ADM-01 | The system MUST support intake management: create, update, activate, close, delete, and list intakes; public listing of open intakes. | P0 | `admission` |
| FR-ADM-02 | The system MUST support a dynamic application form builder: forms with typed fields (text, email, number, date, select, radio, textarea, file, phone, checkbox), required flags, validation, and field reordering. | P0 | `admission` |
| FR-ADM-03 | The system MUST allow public application submission against an open intake, issue a reference number, and allow status tracking via that reference. | P0 | `admission` |
| FR-ADM-04 | The system MUST support document upload for applications (public and admin) and a document verification workflow. | P0 | `admission` |
| FR-ADM-05 | The system MUST support application screening with decisions that move an application to the exam phase or to rejected status. | P0 | `admission` |
| FR-ADM-06 | The system MUST support entrance examination integration: start exam, complete exam, and record exam results against the application. | P0 | `admission`, `cba` |
| FR-ADM-07 | The system MUST support offer creation (conditional/unconditional), applicant response (accept/decline), and offer tracking. | P0 | `admission` |
| FR-ADM-08 | The system MUST support enrollment of an accepted applicant into the student record. | P0 | `admission` |
| FR-ADM-09 | The system MUST expose admissions dashboard statistics (application counts by intake and status). | P1 | `admission` |

**Planned**: AI applicant scoring, eligibility checks, enrollment forecasting (documented in `docs/architecture/7-USE-CASES.md` UC-1 extension and roadmap Phase 2).

### 3.4 Assessment / Results — Scores, Results, Approval, External Exams, Report Cards

Modules: `score`, `result`, `external_exam`, `reportcard`, `grading`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-SCO-01 | The system MUST support saving scores per grade item per student, bulk score entry, score update, and score listing. | P0 | `score` |
| FR-SCO-02 | The system MUST support score rollup across grade items to produce aggregated scores. | P0 | `score` |
| FR-SCO-03 | The system MUST support XLSX export of scores. | P1 | `score` |
| FR-RES-01 | The system MUST support saving a result and retrieving a result, with a result status workflow (e.g. draft → submitted → approved). | P0 | `result` |
| FR-RES-02 | The system MUST support result submission for approval, including submission by key, and listing of pending results. | P0 | `result` |
| FR-RES-03 | The system MUST support result approval by authorized roles (approve endpoint); publication follows approval. | P0 | `result` |
| FR-EXT-01 | The system MUST support external examination (WAEC/NECO) result tracking: create, list, update, delete; best-results computation (best six credit subjects) and credit counts. | P1 | `external_exam` |
| FR-EXT-02 | The system MUST support CSV import of external exam results with a preview-then-confirm flow. | P1 | `external_exam` |
| FR-RPC-01 | The system MUST support report card generation for a single student and batch generation for a class/session/term, with publish/unpublish control. | P0 | `reportcard` |
| FR-RPC-02 | The system MUST support report card templates, teacher/principal comments, and PDF download. | P0 | `reportcard` |
| FR-GRA-02 | The system MUST compute grades from scores using the configured grading scale and expose grade results to authorized roles. | P1 | `grading`, `result` |

**Planned**: AI-assisted essay grading and rubric-based feedback (UC-6 extension; AI module currently exposes chat/search/agents only).

### 3.5 Attendance

Modules: `academic` (student attendance handlers), `hr` (staff attendance).

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-ATT-01 | The system MUST support marking student attendance for a single student and bulk attendance creation for a class. | P0 | `academic` |
| FR-ATT-02 | The system MUST support attendance queries filtered by student, subject, and date range, and exposure of attendance records to teachers, students, and parents through their portals. | P0 | `academic`, `studentportal`, `parentdashboard` |
| FR-ATT-03 | The system MUST support staff attendance: check-in/check-out self-service, daily staff attendance, attendance summary, and attendance CRUD. | P1 | `hr` |

### 3.6 Timetable

Module: `timetable` (verified: list, get, create, update, delete, calendar, iCal export, bulk create).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-TT-01 | The system MUST support timetable CRUD for a school, including bulk creation. | P0 | `timetable` |
| FR-TT-02 | The system MUST support calendar view and iCal export of timetables. | P1 | `timetable` |
| FR-TT-03 | The system MUST surface timetable views to teachers and students through their dashboards. | P0 | `timetable`, `teacher.*`, `student` routes |

### 3.7 Finance / Billing

Modules: `bill`, `payment`, `finance` (verified: accounts, journal entries, budgets, expenses, fee items/structures/waivers, debtors, payment allocation, vendors).

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-BIL-01 | The system MUST support bill CRUD and bill listing filtered by student and date range. | P0 | `bill` |
| FR-PAY-01 | The system MUST support payment recording, payment status query, and payment allocation against fee structures. | P0 | `payment`, `finance` |
| FR-FIN-01 | The system MUST support a chart of accounts (account CRUD). | P1 | `finance` |
| FR-FIN-02 | The system MUST support double-entry journal entries with validation that debits equal credits, and a post-entry workflow. | P1 | `finance` |
| FR-FIN-03 | The system MUST support budget CRUD with spending tracking. | P1 | `finance` |
| FR-FIN-04 | The system MUST support expense CRUD with an approval workflow (approve, pay) and status tracking. | P1 | `finance` |
| FR-FIN-05 | The system MUST support fee items, fee structures (combinations per level/class), and fee waivers (discounts/exemptions). | P0 | `finance` |
| FR-FIN-06 | The system MUST support debtor summaries (total due, total paid, balance) and sending fee reminders. | P0 | `finance` |
| FR-FIN-07 | The system MUST support vendor CRUD. | P1 | `finance` |
| FR-FIN-08 | The system MUST store and display all monetary values in Nigerian Naira (NGN, ₦) unless a field explicitly specifies another currency. | P0 | `bill`, `payment`, `finance`, `hr` |

**Planned**: procurement/purchase-request workflow, GL budgeting reports, compliance reporting (see `docs/COMPLIANCE-ACCREDITATION.md`).

### 3.8 HR / Payroll

Module: `hr` (verified: departments, staff, documents, leaves, payroll periods, payslips, batch generation, staff attendance, appraisals, recruitment).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-HR-01 | The system MUST support department CRUD. | P1 | `hr` |
| FR-HR-02 | The system MUST support staff CRUD with attached documents (credentials, contracts). | P0 | `hr` |
| FR-HR-03 | The system MUST support leave management with an approve/reject workflow. | P1 | `hr` |
| FR-HR-04 | The system MUST support payroll periods (create, open/close), payslip CRUD, batch payslip generation, and mark-paid status. | P1 | `hr` |
| FR-HR-05 | The system MUST support staff attendance: daily attendance, summary, check-in/check-out. | P1 | `hr` |
| FR-HR-06 | The system MUST support staff appraisal CRUD (period, rating, comments, goals). | P1 | `hr` |
| FR-HR-07 | The system MUST support recruitment postings CRUD with publish and close workflow. | P1 | `hr` |

**Planned**: TRCN/NYSC credential tracking and expiry alerts, staff-to-student ratio monitoring (see `docs/COMPLIANCE-ACCREDITATION.md` Phase 3).

### 3.9 Library

Module: `library` (verified: books CRUD, issues, returns).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-LIB-01 | The system MUST support book catalog CRUD with availability tracking. | P1 | `library` |
| FR-LIB-02 | The system MUST support book issue and return lifecycle (create issue, list issues, return). | P1 | `library` |

### 3.10 Hostel

Module: `hostel` (verified: hostels CRUD, beds, assign/unassign).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-HST-01 | The system MUST support hostel CRUD and bed listing. | P1 | `hostel` |
| FR-HST-02 | The system MUST support bed assignment and unassignment with occupancy tracking. | P1 | `hostel` |

### 3.11 Transport

Module: `transport` (verified: routes, vehicles, assignments).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-TRN-01 | The system MUST support transport route CRUD (name, area, distance, fare, vehicles). | P1 | `transport` |
| FR-TRN-02 | The system MUST support vehicle CRUD (plate, model, capacity, driver). | P1 | `transport` |
| FR-TRN-03 | The system MUST support student-to-route/vehicle assignment CRUD. | P1 | `transport` |

### 3.12 Communication / Messaging

Modules: `communication` (verified: templates, single send, bulk send, campaigns, delivery logs, broadcasts), `messages`, `notifications`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-COM-01 | The system MUST support message template CRUD. | P1 | `communication` |
| FR-COM-02 | The system MUST support sending a single message and bulk messaging over configured channels (email, SMS, WhatsApp). | P1 | `communication` |
| FR-COM-03 | The system MUST support campaign management: create, list, pause, resume, cancel, and delivery log inspection. | P1 | `communication` |
| FR-COM-04 | The system MUST support broadcasts (create, list). | P1 | `communication` |
| FR-MSG-01 | The system MUST support internal messaging: conversation list, message list, send, read receipt, star, unread count. | P1 | `messages` |
| FR-NOT-01 | The system MUST support notifications: paginated list, unread count, mark single read, mark all read, delete. | P0 | `notifications` |
| FR-NOT-02 | The system MUST deliver notifications in real time via the WebSocket hub and surface unread counts on dashboards. | P1 | `notifications`, `internal/ws` |

**Planned**: free-tier send caps (50 emails/day/school) and abuse-threshold suspension (see `docs/ABUSE-PREVENTION.md` safeguards 8 and 14).

### 3.13 Alumni and Career

Modules: `alumni` (verified: profiles, careers, events, attendees, mentorships, campaigns, donations, verifications, jobs, insights), `career`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-ALM-01 | The system MUST support alumni profile CRUD and search. | P1 | `alumni` |
| FR-ALM-02 | The system MUST support career history management per alumni profile. | P1 | `alumni` |
| FR-ALM-03 | The system MUST support alumni events CRUD, attendee registration, and attendance marking. | P1 | `alumni` |
| FR-ALM-04 | The system MUST support mentorship pairing CRUD (mentor, mentee, status). | P1 | `alumni` |
| FR-ALM-05 | The system MUST support fundraising campaigns CRUD and donation records. | P1 | `alumni` |
| FR-ALM-06 | The system MUST support certificate/credential verification requests (create, list, update, get). | P1 | `alumni` |
| FR-ALM-07 | The system MUST support an alumni job board: job CRUD and search. | P1 | `alumni` |
| FR-ALM-08 | The system MUST expose alumni insights (engagement and dashboard analytics). | P2 | `alumni` |
| FR-CAR-01 | The system MUST expose career guidance records via the career module (career paths and related records). | P2 | `career` |

**Planned**: AI career guidance engine, skills gap analysis, university/job matching (UC-14; roadmap Phase 7).

### 3.14 Computer-Based Assessment (CBA) and Proctoring

Modules: `cba` (verified: question bank with categories/tags, papers, assignments, exam sessions, grading, proctoring events), `proctoring`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-CBA-01 | The system MUST support a question bank: question CRUD, categories, and tags. | P0 | `cba` |
| FR-CBA-02 | The system MUST support paper composition: paper CRUD, paper-question association, and exam assignments (student/class-level). | P0 | `cba` |
| FR-CBA-03 | The system MUST support the exam session lifecycle: start, pause, resume, submit, and get session; timed exams with auto-submit on time expiry and progress persistence. | P0 | `cba` |
| FR-CBA-04 | The system MUST auto-grade objective questions and queue subjective answers for manual grading (list pending grading, grade answer). | P0 | `cba` |
| FR-CBA-05 | The system MUST list a student's assigned exams (`my exams`) and expose results subject to configuration. | P0 | `cba` |
| FR-CBA-06 | The system MUST capture proctoring events for exam sessions, list events by session, and support a review workflow (review, dismiss, escalate). | P1 | `cba`, `proctoring` |

**Planned**: webcam/biometric identity verification and AI cheating-behaviour detection (UC-5 extension; roadmap Phase 4).

### 3.15 Discipline

Module: `discipline` (verified: incidents, detentions, suspensions, conduct grades, records, stats).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-DIS-01 | The system MUST support incident CRUD (student, category, severity, location, description). | P1 | `discipline` |
| FR-DIS-02 | The system MUST support detention CRUD with status transitions. | P1 | `discipline` |
| FR-DIS-03 | The system MUST support suspension CRUD with status transitions (in/out-of-school). | P1 | `discipline` |
| FR-DIS-04 | The system MUST support conduct grade calculation, conduct records, per-student summaries, and discipline statistics. | P1 | `discipline` |

### 3.16 Health and Pastoral Care

Modules: `health`, `studenthealth` (verified surface per `ACADEMIO_IMPLEMENTATION_PLAN.md` Phase 11: health records, immunizations, allergies, medications, nurse visits), `pastoral`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-HLT-01 | The system MUST support student health records (blood group, genotype, BMI, vision/hearing, edit history). | P1 | `health`, `studenthealth` |
| FR-HLT-02 | The system MUST support immunizations, allergy alerts, medication logs, and nurse visit check-in records per student. | P1 | `studenthealth` |
| FR-PAS-01 | The system MUST support pastoral care records: wellness surveys, wellness alerts, and counseling session logs. | P2 | `pastoral` |

### 3.17 Inventory

Module: `inventory` (verified per plan: categories, assets, assignments, returns, maintenance).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-INV-01 | The system MUST support inventory category CRUD. | P1 | `inventory` |
| FR-INV-02 | The system MUST support asset CRUD (serial number, category, status, current value). | P1 | `inventory` |
| FR-INV-03 | The system MUST support asset assignment, return, and maintenance records per asset. | P1 | `inventory` |

### 3.18 LSM/LMS — Courses, Lessons, Assignments, Forums, Conferences, Media

Modules: `lms` (verified: courses, enrollment, modules, lessons, quiz assignment, progress, assignments, submissions, grading, discussions), `lessonplan`, `forum`, `conference`, `media`, `multimedia`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-LMS-01 | The system MUST support LMS course CRUD, student enrollment, course modules, and lessons. | P1 | `lms` |
| FR-LMS-02 | The system MUST support lesson progress tracking and quiz-to-lesson assignment. | P1 | `lms` |
| FR-LMS-03 | The system MUST support assignments: create, list, submit, grade submissions, and student grade view. | P1 | `lms` |
| FR-LMS-04 | The system MUST support course discussions: threads and posts (create, list, get, update, delete). | P2 | `lms` |
| FR-LSN-01 | The system MUST support lesson plans, lesson notes, and schemes of work aligned to Nigerian lesson-note standards. | P1 | `lessonplan` |
| FR-FOR-01 | The system MUST support a school forum: posts, threads, and moderation actions. | P2 | `forum` |
| FR-CON-01 | The system MUST support parent-teacher conference scheduling: slots and bookings. | P2 | `conference` |
| FR-MED-01 | The system MUST support media/multimedia upload and storage for documents, images, and lesson content. | P1 | `media`, `multimedia` |

### 3.19 Reports and Analytics

Modules: `reports`, `reportbuilder`, `reportcard`, `analytics`, `dashboard`, `audit` (frontend route groups `analytics/`, `reports/`, `report-cards/`, `audit-logs`).

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-RPT-01 | The system MUST provide standard reports and report listing/generation. | P1 | `reports` |
| FR-RPT-02 | The system MUST provide a custom report builder. | P2 | `reportbuilder` |
| FR-ANL-01 | The system MUST provide analytics dashboards for academic performance, enrollment, and revenue. | P1 | `analytics`, `dashboard` |
| FR-ANL-02 | The system MUST expose audit-log views to authorized roles. | P1 | `audit` |
| FR-ANL-03 | Analytics and report queries MUST follow the log-and-continue pattern (best-effort; transient query failures must not fail the whole request). | P0 | `analytics`, `reports`, `reportbuilder` |

**Planned**: executive BI summaries, forecasting models, AI-generated summaries (roadmap Phase 8).

### 3.20 AI Assistant

Module: `ai` (verified: chat, search, agent list).

| ID | Requirement | Priority | Module |
|---|---|---|---|
| FR-AI-01 | The system MUST expose an AI chat endpoint usable by authenticated users (student/teacher/admin roles). | P1 | `ai` |
| FR-AI-02 | The system MUST expose an AI search endpoint that accepts natural-language queries and returns permission-filtered, tenant-isolated results. | P1 | `ai`, `internal/ai/search` |
| FR-AI-03 | The system MUST expose the list of available AI agents. | P1 | `ai` |
| FR-AI-04 | The AI module MUST be gated by configuration (`cfg.AI.Enabled`) and MUST fail safe (non-nil handler, clear error) when disabled. | P1 | `ai`, `cmd/server/main.go` |

**Planned**: RAG-based tutoring, AI lesson-plan generation, AI essay grading, risk prediction and intervention agents (UC-6/7/9/11; roadmap Phase 3).

### 3.21 Portals — Parent and Student

Modules: `parentdashboard` (verified endpoints per plan: dashboard, child progress, child attendance, child fees), `studentportal`.

| ID | Requirement | Priority | Module(s) |
|---|---|---|---|
| FR-PAR-01 | The system MUST provide a parent dashboard listing the parent's children with progress, attendance, and fee summaries. | P0 | `parentdashboard` |
| FR-PAR-02 | The system MUST expose per-child progress, attendance, and fee detail to the parent. | P0 | `parentdashboard` |
| FR-STU-01 | The system MUST provide a student portal exposing results, report cards, fees, timetable, and attendance. | P0 | `studentportal` |

**Planned**: AI parent summary generation, parent-teacher meeting scheduling from the dashboard (UC-8 extension).

---

## 4. Non-Functional Requirements

### 4.1 Multi-Tenancy and Isolation

| ID | Requirement | Priority | Source |
|---|---|---|---|
| NFR-TEN-01 | The system MUST isolate tenant data by PostgreSQL schema (`school_{id}`) via the GORM `SchemaTablePrefix` plugin; shared identity data (users) resides in the `public` schema. | P0 | `AGENTS.md`, `docs/PROJECT.md` |
| NFR-TEN-02 | The system MUST resolve the tenant DB from the request context (`middleware.GetTenantDB(c)`) for every tenant-scoped query; raw core DB access for tenant queries is prohibited. | P0 | `AGENTS.md` Rule B8 |
| NFR-TEN-03 | Provisioning MUST be synchronous and observable: a non-empty `schema_name` on `GET /api/v2/schools/:id` is the completion signal the frontend polls for. | P0 | `AGENTS.md` |
| NFR-TEN-04 | Tenant connection credentials MUST be encrypted at rest (AES-256-GCM) and pooled; connection health must be checked periodically. | P0 | `docs/PROJECT.md` |

### 4.2 Performance and Capacity

Cited from `docs/performance-baseline.md` (k6, 10 VUs, 30 s/endpoint; endpoints: login, attendance, scores, users, bills) and `docs/ops/load-test-baseline.md` (smoke: 2 min, 1–2 VUs).

| ID | Requirement | Priority | Target |
|---|---|---|---|
| NFR-PERF-01 | API error rate under load MUST be below 1%. | P0 | failure rate < 0.01 |
| NFR-PERF-02 | 95th-percentile request latency MUST stay below 500 ms. | P0 | p95 < 500 ms |
| NFR-PERF-03 | 99th-percentile latency MUST stay below 1000 ms. | P1 | p99 < 1000 ms |
| NFR-PERF-04 | Median latency below 200 ms is the reference good-experience target. | P1 | p50 < 200 ms |
| NFR-PERF-05 | Parallel-run throughput MUST not drop more than 30% versus sequential baseline. | P1 | drop < 30% |
| NFR-PERF-06 | Every list endpoint MUST be paginated with a default page size of 100 and a hard maximum of 1000; service-layer pagination with `helpers.ParsePagination(c)` is mandatory. | P0 | `AGENTS.md` Rule B5/B10 |
| NFR-PERF-07 | The frontend API client MUST enforce a 30-second request timeout and retry transient network failures (2 attempts, exponential backoff 500 ms → 1000 ms). | P0 | `frontend/src/lib/api.ts` |
| NFR-PERF-08 | The frontend MUST use server-state caching (TanStack Query, 60 s stale time, 1 retry) to reduce redundant requests. | P1 | `docs/PROJECT.md` |

### 4.3 Security

Full detail in `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` and FSD Part 6 (`06-ENGINEERING.md`, Security section); verification of these requirements is specified in Part 5 (`05-PLATFORM.md`). Requirement-level statements:

| ID | Requirement | Priority |
|---|---|---|
| NFR-SEC-01 | Passwords MUST be hashed with bcrypt; secrets MUST come from environment variables with fail-fast startup validation — no hardcoded fallbacks. | P0 |
| NFR-SEC-02 | Access tokens MUST be short-lived JWTs with rotating refresh tokens; revoked tokens MUST be blacklisted in Redis. | P0 |
| NFR-SEC-03 | All mutating requests MUST carry a valid nonce-based CSRF token. | P0 |
| NFR-SEC-04 | Security headers (HSTS, CSP, `X-Content-Type-Options`), CORS origin whitelist, and body-size limits MUST be applied globally. | P0 |
| NFR-SEC-05 | All mutations MUST be audit-logged (SchoolID, UserID, Action, ResourceType, RequestID). | P0 |
| NFR-SEC-06 | SQL construction MUST use parameterized queries (GORM/pgx); `fmt.Sprintf` for SQL and multi-statement `db.Exec()` are forbidden. | P0 |
| NFR-SEC-07 | Rate limiting MUST be applied per IP (login: 5/min free) and per school tenant (API: 60/min free; uploads 10/min; email 50/day; password reset 3/hr/user) per `docs/ABUSE-PREVENTION.md`. | P0 |
| NFR-SEC-08 | No `context.Background()` in request-scoped chains; context MUST propagate handler → service → repository → external calls. | P0 |
| NFR-SEC-09 | No silent error discards (`_`); state mutations MUST return errors, batch operations MUST collect-and-report. | P0 |

### 4.4 Reliability and Operations

| ID | Requirement | Priority |
|---|---|---|
| NFR-REL-01 | The system MUST run with Docker containers `shared-postgres` (5432) and `shared-redis` (6379); Redis is required for the asynq queue used by provisioning. | P0 |
| NFR-REL-02 | Background jobs (email, SMS, WhatsApp, backup, restore, provisioning) MUST be processed by the asynq worker; the worker runs in-process with the HTTP server. | P0 |
| NFR-REL-03 | The server MUST start with graceful shutdown and MUST validate all required configuration at startup (fail-fast). | P0 |
| NFR-REL-04 | Request-scoped logging MUST use `pkg/logger` (slog wrapper); `fmt.Printf`/`log.Print` are prohibited in application code. | P0 |
| NFR-REL-05 | Scheduled jobs (backups, reminders) MUST be driven by the internal scheduler (`internal/scheduler/`). | P1 |
| NFR-REL-06 | Backup retention MUST be tiered per plan: 7 days (free), 90 days (growth), 365 days + PITR (enterprise). | P1 |

### 4.5 Compliance and Localization (Nigerian Market)

| ID | Requirement | Priority | Source |
|---|---|---|---|
| NFR-NG-01 | The system MUST model the Nigerian education structure (1-6-3-3-4: nursery, primary 1–6, JSS 1–3, SSS 1–3, tertiary) in levels/sessions/curricula. | P0 | `docs/NG-EDUCATION-STANDARDS.md` |
| NFR-NG-02 | The system MUST support the WAEC/NECO A1–F9 grading scale (A1 75–100 … F9 0–39) and the five-credit rule (C6 or better, including English and Mathematics) for university eligibility reporting. | P1 | `docs/NG-EDUCATION-STANDARDS.md` |
| NFR-NG-03 | The system MUST support continuous-assessment composition (CA 30–40%, end-of-term 30–40%) via configurable grade items and assessments. | P1 | `docs/NG-EDUCATION-STANDARDS.md` |
| NFR-NG-04 | The system MUST support external examination (WAEC/NECO/JAMB-aligned) result tracking, including best-six credit computation. | P1 | `docs/NG-EDUCATION-STANDARDS.md`, `external_exam` module |
| NFR-NG-05 | All monetary values MUST default to NGN (₦) in storage and display. | P0 | `AGENTS.md` Rule F5 |
| NFR-NG-06 | The system MUST support lesson plans and lesson notes conforming to the Nigerian lesson-note plan standard (objectives, materials, procedure, evaluation). | P1 | `docs/NG-LESSON-NOTE-PLAN-STANDARDS.md` |
| NFR-NG-07 | The system SHOULD support compliance evidence capture (documents, registers, credential expiry) to satisfy Lagos State inspection requirements (document repository, expiry alerts, TRCN/NYSC tracking are Planned; student/staff registers and attendance export are covered by existing modules). | P1 | `docs/COMPLIANCE-ACCREDITATION.md` |

### 4.6 Usability and Accessibility

| ID | Requirement | Priority |
|---|---|---|
| NFR-UX-01 | The frontend MUST use entity names (never raw IDs) as `Select` item values, resolving IDs ↔ names on selection, per `AGENTS.md` Rule F1. | P0 |
| NFR-UX-02 | Sonner `<Toaster />` MUST live in the root layout so toasts survive navigation and drawer close (Rule F4). | P0 |
| NFR-UX-03 | Forms MUST validate with Zod schemas + React Hook Form before submission. | P1 |
| NFR-UX-04 | Loading, empty, and error states MUST be rendered for every data list (verified pattern in mobile plan; same standard applies to web). | P1 |
| NFR-UX-05 | Dashboards and lists MUST surface human-readable, actionable messages from the API error envelope (`{ success, data, error, meta }`). | P1 |

### 4.7 Maintainability and Developer Experience

| ID | Requirement | Priority |
|---|---|---|
| NFR-MNT-01 | Every backend module MUST follow the `dto.go / handler.go / service.go / repository.go` layout; repositories expose interfaces at the top. | P0 |
| NFR-MNT-02 | `go build ./...` and `go vet ./...` MUST pass clean; `npx tsc --noEmit` MUST pass with zero errors. | P0 |
| NFR-MNT-03 | Frontend dependency management MUST use Yarn 4+ (lockfile); npm usage is prohibited (Rule F2). | P0 |
| NFR-MNT-04 | Integration verification MUST use `backend/scripts/test_endpoint.sh` (40-test flow) after `make db-init && make migrate && make seed && ./bin/server`. | P1 |
| NFR-MNT-05 | OpenAPI/Swagger documentation MUST be available at `/swagger/index.html` in development. | P1 |

---

## 5. User Stories

| ID | Role | Story | Priority | Mapped FR |
|---|---|---|---|---|
| US-01 | Super Admin | As a super admin, I want to create a school and watch provisioning complete (schema created, migrations run, seed data loaded) so the school can start configuration immediately. | P0 | FR-SCH-01, FR-TEN-01 |
| US-02 | School Admin | As a school admin, I want to configure sessions, curricula, assessments, and grade items so teachers have a ready grading structure each term. | P0 | FR-ACA-01..04 |
| US-03 | Teacher | As a teacher, I want to mark attendance for my class in one bulk action so the register is up to date. | P0 | FR-ATT-01 |
| US-04 | Teacher | As a teacher, I want to enter scores per grade item and roll them up so results reflect continuous assessment. | P0 | FR-SCO-01, FR-SCO-02 |
| US-05 | Principal | As a principal, I want to review and approve submitted results so only verified results are published. | P0 | FR-RES-01..03 |
| US-06 | Accountant | As an accountant, I want to create fee structures per class, record payments, and allocate them so debtor balances stay accurate. | P0 | FR-FIN-05, FR-FIN-06, FR-PAY-01 |
| US-07 | HR Manager | As an HR manager, I want to generate payroll in batches and close the period so payslips are consistent. | P1 | FR-HR-04 |
| US-08 | Admissions Officer | As an admissions officer, I want to screen applications, run entrance exams, and issue offers so the admission cycle closes with enrollment. | P0 | FR-ADM-05..08 |
| US-09 | Applicant | As a parent applying for my child, I want to submit the application online and track its status with a reference number. | P0 | FR-ADM-03 |
| US-10 | Parent | As a parent, I want a dashboard showing my children's progress, attendance, and fees so I can monitor school life. | P0 | FR-PAR-01, FR-PAR-02 |
| US-11 | Student | As a student, I want to see my results, report cards, timetable, and fees so I can track my own progress. | P0 | FR-STU-01 |
| US-12 | Student | As a student, I want to take a timed CBA, navigate questions, and submit so my score is graded instantly. | P0 | FR-CBA-03, FR-CBA-04 |
| US-13 | Teacher | As a teacher, I want to grade subjective CBA answers from a pending queue so grading is complete before publication. | P0 | FR-CBA-04 |
| US-14 | Librarian | As a librarian, I want to issue and return books so the catalog reflects real availability. | P1 | FR-LIB-02 |
| US-15 | Hostel Manager | As a hostel manager, I want to assign and unassign beds so occupancy is accurate. | P1 | FR-HST-02 |
| US-16 | Transport Manager | As a transport manager, I want to manage routes, vehicles, and student assignments so trips are planned. | P1 | FR-TRN-01..03 |
| US-17 | Communications Officer | As a communications officer, I want to send campaigns and inspect delivery logs so parents receive school updates. | P1 | FR-COM-02, FR-COM-03 |
| US-18 | Alumni Officer | As an alumni officer, I want to maintain alumni profiles, events, and verifications so the alumni network stays engaged. | P1 | FR-ALM-01, FR-ALM-03, FR-ALM-06 |
| US-19 | Counselor | As a counselor, I want to see discipline incidents, detentions, and conduct grades so I can support student welfare. | P1 | FR-DIS-01..04 |
| US-20 | School Admin | As a school admin, I want audit logs of every mutation so I can trace who changed what. | P0 | FR-AUD-01, FR-ANL-02 |
| US-21 | Any User | As any authenticated user, I want natural-language AI search so I can find records without knowing filter syntax. | P1 | FR-AI-02 |
| US-22 | Super Admin | As a super admin, I want to impersonate a user to diagnose support issues, with the action audited. | P1 | FR-AUTH-07 |

---

## 6. Use Cases

Derived from `docs/architecture/7-USE-CASES.md`. Each use case is marked **Implemented**, **Partially implemented**, or **Planned**, based on the verified module surfaces in Section 3. Actor definitions (Super Admin, School Admin, Teacher, Student, Parent, Accountant, Librarian, Admissions Officer, Counselor, HR Manager, Transport Manager, Hostel Manager, Alumni, Applicant, System) are inherited from the source document.

| ID | Use case | Primary actor | Status | Implementation evidence / notes |
|---|---|---|---|---|
| UC-1 | Online Admission | Applicant | **Implemented** | Intakes, public form config, application submission with reference, status tracking. AI scoring/eligibility is Planned. |
| UC-2 | Application Screening | Admissions Officer | **Implemented** | `ScreenApplication`, document verification, decision → exam/rejected. AI pre-screening is Planned. |
| UC-3 | Entrance Examination | Applicant | **Implemented** | `StartEntranceExam`/`CompleteEntranceExam`/`RecordExamResult` plus CBA engine (UC-5). Webcam proctoring is Planned; event-capture proctoring is Implemented. |
| UC-4 | Admission Offer & Acceptance | Admissions Officer / Applicant | **Implemented** | `CreateOffer`, `RespondToOffer`, `EnrollStudent`. AI offer recommendations are Planned. |
| UC-5 | Take Computer-Based Assessment | Student | **Implemented** | Question bank, papers, assignments, timed sessions (start/pause/resume/submit), auto-grading, result visibility config. AI behaviour detection is Planned. |
| UC-6 | Teacher Grades Essays with AI Assistance | Teacher | **Partially implemented** | Manual grading queue (`ListPendingGrading`, `GradeAnswer`) is Implemented. AI-assisted rubric scoring is Planned (AI module exposes chat/search/agents only). |
| UC-7 | Student Uses AI Academic Assistant | Student | **Partially implemented** | AI chat endpoint is Implemented. RAG-based tutoring, study plans, and session persistence are Planned. |
| UC-8 | Parent Views Child Performance Summary | Parent | **Implemented** | Parent dashboard, child progress/attendance/fees endpoints and web routes. AI natural-language summary is Planned. |
| UC-9 | Teacher Generates Lesson Plan with AI | Teacher | **Partially implemented** | Lesson plans/notes/schemes management is Implemented (`lessonplan`). AI generation is Planned. |
| UC-10 | Natural Language Search | Any authenticated user | **Partially implemented** | `POST /api/v2/ai/search` exists with permission filtering and tenant isolation. Full NL→structured-filter query engine across all modules is Planned. |
| UC-11 | Risk Detection & Intervention | System / Counselor | **Planned** | Analytics dashboards exist; automated academic-risk scoring, alerts, and intervention plans are not yet implemented. |
| UC-12 | Alumni Registration & Career Tracking | Graduate / Alumni | **Implemented** | Alumni profiles, careers, events, mentorships, donations, jobs, insights. Automatic profile creation on graduation is Planned. |
| UC-13 | Certificate Verification | Third Party | **Implemented** | Verification request lifecycle in `alumni` module. Public self-service verification portal is Planned. |
| UC-14 | AI Career Guidance | Student / Alumni | **Planned** | Career module stores records; AI skills assessment, career-path recommendations, and university matching are not implemented. |
| UC-15 | Multi-Campus Management | School Admin (Central Office) | **Planned** | Schema-per-tenant supports one campus per tenant today; cross-campus reporting and campus-level admin scoping are future work. |

### 6.1 Use Case Extensions (derived for this FSD)

| Extension | Base use case | Requirement |
|---|---|---|
| EX-1: Entrance exam results feed the admission record | UC-3, UC-4 | `RecordExamResult` must store the score against the application and make it available to offer computation. |
| EX-2: Result approval gates publication | UC-5 extension (internal exam lifecycle) | Published report cards/results must only be generated from approved results (`result` approval workflow). |
| EX-3: Document verification precedes screening pass | UC-2 | An application cannot be moved to the exam phase until required documents are uploaded and verified (`VerifyDocument`). |
| EX-4: Payment allocation updates debtor balance | UC-8 (fees) | `RecordPaymentAllocation` must reduce the debtor's outstanding balance atomically with the payment record. |
| EX-5: CBA auto-grading feeds score rollup | UC-5, FR-SCO-02 | CBA objective scores must be exportable/importable into the score rollup for internal assessment composition. |

### 6.2 Actor × Module Permission Matrix

Inherited from `docs/architecture/7-USE-CASES.md` (CRUD matrix). This FSD records the following authorization invariants for acceptance testing:

| Invariant | Actors |
|---|---|
| Student records: create/update/delete restricted to School Admin; read for Teacher/Student/Parent | School Admin, Teacher, Student, Parent |
| Results: submit/approve restricted to Teacher (submit) and authorized approver roles (approve); read for Student/Parent | Teacher, Principal/Approver, Student, Parent |
| Fees & billing: create/manage by Accountant and School Admin; view/pay by Parent and Student | Accountant, School Admin, Parent, Student |
| Finance journal/budget/expense: create/approve restricted to finance roles | Accountant, School Admin |
| Payroll: restricted to HR Manager and School Admin | HR Manager, School Admin |
| CBA: paper/question management by Teacher; taking by assigned Student; results view per configuration | Teacher, Student |
| Admissions decisions: restricted to Admissions Officer and School Admin | Admissions Officer, School Admin |
| Super-admin console: Super Admin only | Super Admin |

---

## 7. User Journeys

End-to-end narrative flows. Each journey references the FRs and use cases it exercises.

### 7.1 UJ-1 — New School Onboarding and Provisioning

1. A new user registers on the Academio web app (`register.tsx`) and confirms their email.
2. The user creates a school from the onboarding wizard (`_onboarding/`). The backend creates the `School` row with an empty `schema_name` and triggers synchronous provisioning (create `school_{id}` schema, run tenant migrations, seed curriculum/subjects/levels, seed super-admin access).
3. The frontend polls `GET /api/v2/schools/:id` until `schema_name` is non-empty — this is the provisioning completion signal.
4. On completion, the user is guided to configure the first academic session, curriculum, subjects, levels, and grade items.
5. The school admin invites staff and enrolls students via invitation codes (FR-USR-03); parent accounts are linked with dedup priority email → phone → username (FR-USR-02).
6. The school is ready to run attendance, scoring, billing, and report-card cycles.

**Exercises**: FR-SCH-01, FR-TEN-01, FR-ACA-01..04, FR-USR-02, FR-USR-03. **Acceptance**: AC-01, AC-02.

### 7.2 UJ-2 — Term Result Cycle from Score Entry to Published Report Cards

1. Teacher opens the term's assessment and grade items (`academics.tsx`, `teacher.academics.tsx`).
2. Teacher enters scores per grade item, individually or in bulk, and rolls up scores (FR-SCO-01/02).
3. Teacher submits the result; the result enters the pending-approval queue (FR-RES-02).
4. The designated approver (principal) reviews pending results and approves them (FR-RES-03).
5. Report cards are generated individually or in batch from approved results (FR-RPC-01), customized with templates and comments (FR-RPC-02), published, and downloaded as PDF.
6. Students and parents see published results/report cards through their portals (FR-STU-01, FR-PAR-01).

**Exercises**: UC-5 (extension EX-2). **Acceptance**: AC-06, AC-07, AC-08, AC-10.

### 7.3 UJ-3 — Parent Enrollment and Ongoing Monitoring

1. A parent receives an invitation code from the school and joins the platform (FR-USR-03).
2. The parent logs in and lands on the parent dashboard listing their children (FR-PAR-01).
3. The parent opens a child's detail view to see progress, attendance, and fees (FR-PAR-02).
4. The parent receives notifications of results publication and fee reminders (FR-NOT-01/02) and can view outstanding bills and pay/allocate payments (FR-BIL-01, FR-PAY-01, FR-FIN-06).
5. The parent can message staff and view campaign broadcasts from the school (FR-MSG-01, FR-COM-03/04).

**Exercises**: UC-8. **Acceptance**: AC-12, AC-13.

### 7.4 UJ-4 — Admission Lifecycle: Application to Enrollment

1. School admin creates an intake and activates it; configures the application form via the form builder (FR-ADM-01/02).
2. A parent submits an application publicly and receives a reference number (FR-ADM-03), uploading documents (FR-ADM-04).
3. Admissions officer screens the application and verifies documents (FR-ADM-05, EX-3).
4. If passed, the applicant takes the entrance exam through the CBA engine; the score is recorded against the application (FR-ADM-06, UC-3).
5. Admissions officer creates an offer; the applicant accepts; the officer enrolls the applicant as a student (FR-ADM-07/08).

**Exercises**: UC-1, UC-2, UC-3, UC-4. **Acceptance**: AC-03, AC-04, AC-05.

### 7.5 UJ-5 — CBA Examination Cycle

1. Teacher builds a question bank with categories and tags, then composes a paper and assigns it to a class or students (FR-CBA-01/02).
2. Student sees the exam in "My Exams", starts the timed session, navigates questions, and submits (FR-CBA-03).
3. Objective answers are auto-graded; subjective answers enter the pending grading queue (FR-CBA-04).
4. Teacher grades subjective answers; results become visible per configuration (FR-CBA-05).
5. Proctoring events (if configured) are captured and reviewed by an administrator (FR-CBA-06).

**Exercises**: UC-5, UC-6 (manual portion). **Acceptance**: AC-14, AC-15.

### 7.6 UJ-6 — Fee Billing, Payment, and Allocation

1. Accountant configures fee items and fee structures per level/class (FR-FIN-05).
2. Bills are generated and displayed to students/parents (FR-BIL-01).
3. Parent pays; the accountant records the payment and allocates it across the fee structure (FR-PAY-01, EX-4).
4. Debtor balances update; the accountant can send fee reminders (FR-FIN-06).
5. Revenue analytics reflect collections (FR-ANL-01).

**Exercises**: UC-8 (fees). **Acceptance**: AC-16, AC-17.

---

## 8. Acceptance Criteria

All criteria are binary: the test either passes or fails. Each criterion is given in the form *Given / When / Then*.

### 8.1 Tenancy and Provisioning

| ID | Given | When | Then |
|---|---|---|---|
| AC-01 | A new user registers and creates a school | provisioning completes synchronously | `GET /api/v2/schools/:id` returns a non-empty `schema_name`; the test passes, otherwise it fails. |
| AC-02 | A provisioned school exists with `schema_name = school_{id}` | a tenant-scoped query executes with `x-school-id` | the query resolves against the tenant schema; any query to the wrong schema fails the test. |

### 8.2 Admissions

| ID | Given | When | Then |
|---|---|---|---|
| AC-03 | An active intake and published form exist | a public applicant submits with documents | the API returns a reference number and status `submitted`; any missing required field returns a 400 and the test fails. |
| AC-04 | An application is in `submitted` status | the admissions officer screens it as pass | the application status transitions to the exam phase; document verification is a precondition (EX-3). |
| AC-05 | A screened applicant completes the entrance exam | the officer creates an offer and the applicant accepts | the enrollment endpoint creates a student record; otherwise the test fails. |

### 8.3 Scoring, Results, Report Cards

| ID | Given | When | Then |
|---|---|---|---|
| AC-06 | Grade items and assessments exist for the term | a teacher saves and rolls up scores | aggregated scores equal the configured composition of grade items; any arithmetic mismatch fails the test. |
| AC-07 | Scores are rolled up | the teacher submits the result | the result appears in the pending approval list with status `submitted`. |
| AC-08 | A result is pending | an authorized approver approves it | the result status becomes `approved`; an unauthorized role attempting approval receives 403 and the test fails. |
| AC-09 | A result is `approved` | batch report cards are generated for the class/term | every student in scope has a report card with template applied and PDF downloadable. |
| AC-10 | External exam results CSV is provided | the officer previews and confirms the import | results persist and best-six credit computation returns the expected credit set; malformed rows are rejected in preview. |

### 8.4 Attendance and Timetable

| ID | Given | When | Then |
|---|---|---|---|
| AC-11 | A class roster exists | the teacher bulk-marks attendance for a date | each student in scope receives a present/absent record; counts in the attendance query match the marks. |
| AC-12 | A timetable exists | the teacher or student opens the timetable view | the view reflects the stored entries and iCal export succeeds without error. |

### 8.5 Portals and Finance

| ID | Given | When | Then |
|---|---|---|---|
| AC-13 | A parent is linked to a student | the parent opens the child detail | progress, attendance, and fee summaries render from the API; empty/error states are shown if data is missing. |
| AC-14 | A debtor has outstanding balance | the accountant records a payment and allocates it | the debtor's balance decreases by the allocated amount atomically; any mismatch fails the test. |
| AC-15 | A fee structure exists in NGN | any monetary field is rendered | the value displays with ₦ (NGN); any other default currency fails the test. |

### 8.6 CBA and Proctoring

| ID | Given | When | Then |
|---|---|---|---|
| AC-16 | A student has an assigned CBA paper | the student starts and submits the timed exam | objective questions auto-grade and the session records completion; late submission after expiry is blocked. |
| AC-17 | Subjective answers are submitted | the teacher grades from the pending queue | the answers leave the pending queue with scores recorded and results visibility updates per configuration. |
| AC-18 | Proctoring events are captured | the administrator reviews an event | the event transitions to reviewed/dismissed/escalated and the change persists. |

### 8.7 HR, Library, Hostel, Transport, Discipline

| ID | Given | When | Then |
|---|---|---|---|
| AC-19 | Staff records and a payroll period exist | batch payslips are generated and the period closed | every active staff member has a payslip with net pay equal to gross minus deductions; closing a period with unpaid payslips is rejected. |
| AC-20 | A book is in stock | the librarian issues it to a student and later processes a return | availability decrements and then increments; over-issuance beyond stock fails. |
| AC-21 | A hostel has beds | the manager assigns and unassigns a bed | occupancy updates and double-assignment of an occupied bed fails. |
| AC-22 | Routes, vehicles, and assignments exist | the transport manager updates an assignment | the change persists and the assignment list reflects it. |
| AC-23 | An incident is recorded | the counselor views the student summary | conduct grade and stats reflect the incident; severity/status transitions persist. |

### 8.8 Platform and Cross-Cutting

| ID | Given | When | Then |
|---|---|---|---|
| AC-24 | A user is authenticated | any mutating request is sent without a CSRF token | the request is rejected (403) and the test fails if accepted. |
| AC-25 | A mutation succeeds | the audit middleware runs | an audit row is created with SchoolID, UserID, Action, ResourceType, and RequestID; absence of the row fails the test. |
| AC-26 | A list endpoint is called without explicit pagination | the response returns | default page size is 100 and the metadata reports counts; exceeding the 1000 cap is rejected. |
| AC-27 | The free-tier school exceeds 60 API requests in a minute | further requests are sent | the API returns 429 and the test passes only if the limit is enforced. |
| AC-28 | A request chain calls an external dependency | any code path uses `context.Background()` in a request-scoped handler | static analysis flags it; the test passes only with zero occurrences. |
| AC-29 | A JWT is blacklisted | the same token is presented again | the request is rejected; silent acceptance fails the test. |
| AC-30 | A school is provisioned and live | the integration suite `backend/scripts/test_endpoint.sh` runs against a fresh DB | all 40 tests pass; any failure fails the suite. |
| AC-31 | Load test runs with 10 VUs for 30 s per endpoint | k6 thresholds evaluate | error rate < 1%, p95 < 500 ms, p99 < 1000 ms; threshold breach fails the run. |
| AC-32 | A tenant is created with credentials encrypted | stored credentials are inspected | they are AES-256-GCM encrypted; plaintext storage fails the test. |
| AC-33 | The parent dedup routine runs on parent creation | an existing email is submitted | the existing user is linked (email → phone → username priority); creating a duplicate fails the test. |
| AC-34 | A Select referencing entities renders | options and current value are loaded | the trigger displays an entity name, never a raw numeric ID; raw ID display fails the test. |
| AC-35 | An AI request is sent while AI is disabled | the chat/search endpoints are called | a clear, non-nil error response is returned; a nil-handler panic fails the test. |

---

## 9. Traceability

### 9.1 Module → FR Coverage

| Area | Modules | FR count (this document) |
|---|---|---|
| Core Platform | auth, user, school, tenant, rbac, audit, invitation | 17 |
| Academic | academic, academic-calendar, grading, exam | 8 |
| Admissions | admission | 9 |
| Assessment/Results | score, result, external_exam, reportcard, grading | 11 |
| Attendance | academic (attendance), hr (staff) | 3 |
| Timetable | timetable | 3 |
| Finance/Billing | bill, payment, finance | 10 |
| HR/Payroll | hr | 7 |
| Library | library | 2 |
| Hostel | hostel | 2 |
| Transport | transport | 3 |
| Communication/Messaging | communication, messages, notifications | 7 |
| Alumni/Career | alumni, career | 9 |
| CBA | cba, proctoring | 6 |
| Discipline | discipline | 4 |
| Health/Pastoral | health, studenthealth, pastoral | 3 |
| Inventory | inventory | 3 |
| LSM/LMS | lms, lessonplan, forum, conference, media, multimedia | 8 |
| Reports/Analytics | reports, reportbuilder, reportcard, analytics, dashboard, audit | 5 |
| AI Assistant | ai | 4 |
| Portals | parentdashboard, studentportal | 3 |
| **Total** | **49 modules** | **127** |

### 9.2 Acceptance Criteria → FR Coverage

AC-01–AC-02 → FR-SCH-01/FR-TEN-01/02; AC-03–AC-05 → FR-ADM-01..08; AC-06–AC-10 → FR-SCO-01/02, FR-RES-01..03, FR-RPC-01/02, FR-EXT-01/02; AC-11–AC-12 → FR-ATT-01/02, FR-TT-01..03; AC-13–AC-15 → FR-PAR-01/02, FR-PAY-01, FR-FIN-05/06, FR-FIN-08; AC-16–AC-18 → FR-CBA-01..06; AC-19–AC-23 → FR-HR-04, FR-LIB-02, FR-HST-02, FR-TRN-03, FR-DIS-01..04; AC-24–AC-35 → FR-AUTH-04/05, FR-AUD-01, FR-TEN-01, FR-USR-02, FR-AI-04, NFR-* series.

---

## 10. Open Items and Assumptions

| # | Item | Status |
|---|---|---|
| O-1 | Generic Workflow Engine (`docs/WORKFLOW-IMPLEMENTATION.md`) — module-embedded approval flows exist today (results, admissions, leave, expenses); a configurable engine is Planned. Requirement-level statements in this document describe only the embedded flows. | Planned |
| O-2 | Compliance/accreditation module (`docs/COMPLIANCE-ACCREDITATION.md`) — document repository, TRCN/NYSC expiry tracking, inspection checklists are Planned; register exports are partially covered by existing modules. | Planned |
| O-3 | AI capability ceiling — current AI module is chat/search/agents; RAG tutoring, AI grading, risk prediction are Planned and excluded from FR tables. | Planned |
| O-4 | Multi-campus management (UC-15) and automatic alumni creation on graduation (UC-12 extension) are Planned. | Planned |
| O-5 | Performance baseline values are thresholds defined in `docs/performance-baseline.md`; measured numbers are populated by the k6 runs in `scripts/loadtest/` and reported in Part 5 (`05-PLATFORM.md`) and Part 6 (`06-ENGINEERING.md`). | In progress |
| O-6 | Currency: all monetary values default to NGN (₦). Any future multi-currency field must be explicitly modelled per FR-FIN-08. | Assumed |

---

## 11. Document Revisions

| Date | Author | Changes |
|---|---|---|
| 31 July 2026 | Systems Architecture | Initial draft — functional and non-functional requirements, user stories, use cases (Implemented/Planned), user journeys, binary acceptance criteria. Verified against 49 backend modules, frontend route tree, and API client surface. |
