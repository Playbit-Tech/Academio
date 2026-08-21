# Academio Functional Specification — Part 3: UX Design

| | |
|---|---|
| **Document** | FSD Part 3 — UX Design (Wireframes, Information Architecture, Navigation, UI Component Standards) |
| **Product** | Academio — Multi-tenant School Management / Education ERP |
| **Stack (frontend)** | React 19, Vite, TanStack Router, TanStack Query, Tailwind CSS v4, shadcn/ui + Base UI, Zustand, react-i18next (en/fr) |
| **Stack (mobile)** | Flutter (Material 3), three role flavors: admin, teacher, student |
| **Status** | Current as of 2026-07-31 — grounded in the implemented route tree |
| **Audience** | Frontend engineers, UI/UX designers, QA, product owners |

---

## Document Map — the FSD Series

This document is **Part 3** of the Academio Functional Specification series. Cross-references:

| Part | Document | Content |
|------|----------|---------|
| 0 | `00-FSD-INDEX.md` | Table of contents, document map, revision history (planned) |
| 1 | `01-PRODUCT.md` | Executive summary, vision, goals, personas, MVP scope, roadmap, risks |
| 2 | `02-REQUIREMENTS.md` | Detailed functional and non-functional requirements per module |
| **3** | **`03-UX-DESIGN.md` (this document)** | Wireframe descriptions, information architecture, navigation design, UI component standards |
| 4 | `04-DATA-API.md` | Data model, multi-tenant schema design, REST API catalog, events |
| 5 | `05-PLATFORM.md` | Audit logging, notifications, search, global settings, tenant architecture, event-driven architecture, background jobs, caching strategy, file storage |
| 6 | `06-ENGINEERING.md` | Engineering standards, conventions, quality gates, testing strategy |

Supporting project documentation referenced throughout:

- `AGENTS.md` — engineering hard rules (frontend rules F1–F5, backend rules B1–B13)
- `frontend/DESIGN_SYSTEM.md` — the "Empathetic Growth" design system
- `frontend/DESIGN_PATTERNS.md` — frontend architectural and coding conventions
- `docs/audits/FRONTEND-ENTERPRISE-AUDIT.md` — audit findings that shape UI standards
- `docs/architecture/INDEX.md`, `docs/architecture/2-ARCHITECTURE-OVERVIEW.md` — module catalogue and portal strategy
- `docs/WORKFLOW-IMPLEMENTATION.md` — workflow engine consumed by results/admission/leave screens
- `mobile/AGENTS.md` — Flutter flavor architecture (admin / teacher / student apps)

---

## 1. Wireframe Descriptions

### 1.1 Conventions

Wireframes below are **text-based**. Legend:

```
[ Button ]        primary/secondary button        ( input )       text input
[▾ Select ]       dropdown (Base UI Select)       o checkbox      ( ) radio
[ Tab ]           tab bar                         # Sidebar      ┃ header/footer edge
| col | col |     table columns                  ...             loading / more
```

Screen status:

- **Implemented** — route exists in `frontend/src/routes/` and is reachable.
- **Partial** — functionality exists but is embedded in another screen; a dedicated route does not exist.
- **Planned** — no route exists; described as target UX for future work.

Status is determined strictly from the actual route tree (Section 2.5). Where a screen is marked Planned, the wireframe is a design target, not a description of shipped UI.

### 1.2 Authentication

#### 1.2.1 Login — Implemented (`/login`)

Purpose: single sign-in surface for all roles (super admin, admin, teacher, student, parent). The backend authenticates by identifier (email, username, or phone) and returns a role; the frontend routes to the correct portal afterward. There is no per-role login screen.

```
┌────────────────────────────────────────────────────────────────┐
│  [Academio logo]                                   [Theme] [FR|EN] │   <- standalone auth layout
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                    Welcome back                                │
│                    Sign in to Academio                         │
│                                                                │
│                    ( Email or username            )            │
│                    ( Password                    ) [Show]      │
│                                                                │
│                    [ Forgot password? ]                        │
│                                                                │
│                    [           Sign In           ]             │
│                                                                │
│                    Don't have an account? [Sign up]            │
│                                                                │
│                    ─────────  or continue with  ─────────      │
│                    [ (identifier) sign-in ]                    │
│                                                                │
│                    Language: [▾ English | Français]            │
├────────────────────────────────────────────────────────────────┤
│  © Academio · [Terms] [Privacy] [Cookies]                      │
└────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Identifier field accepts email or username (backend resolves; see FSD Part 1 for credential policy).
- Password field has a show/hide toggle; minimum 8 characters (see `zPassword` in `src/i18n/zod.ts`).
- On success the app stores tokens via Zustand (`auth-store` persisted with `academio-auth`), derives `isAuthenticated` from `!!user && !!accessToken` (audit C-1 fix), and navigates to the role default: `/dashboard` (admin/teacher), `/student` (student), `/parent` (parent).
- Error states: invalid credentials, unverified email, disabled account — shown inline and via Sonner toast (Toaster lives in `__root.tsx`, Rule F4).
- Localization: `auth.*` keys; `LanguageToggle` writes `academio-locale` to localStorage (detection order: localStorage → navigator → htmlTag).

#### 1.2.2 Register, Forgot Password, Reset Password, Confirm Email — Implemented

| Screen | Route | Key elements |
|--------|-------|--------------|
| Register | `/register` | Full-name, email, username, password + confirmation; links back to Sign in |
| Forgot password | `/forgot-password` | Email/identifier input; submits reset request |
| Reset password | `/reset-password` | Token + new password fields (8+ chars) |
| Confirm email | `/confirm-email` | Email confirmation status page; link to login |

All four share the standalone auth layout (logo top, language/theme toggles, footer). Validation messages come from `validation.*` i18n keys via the shared Zod helpers.

### 1.3 Public Marketing Site — Implemented (`_public` routes)

Routes: `/` (landing), `/about`, `/features`, `/editions`, `/how-to-use`, `/privacy`, `/terms`, `/cookies`, plus public admissions flow (`/admissions/apply`, `/admissions/route`, `/admissions/status` — see 1.18).

```
┌────────────────────────────────────────────────────────────────┐
│ [logo]  Features  Editions  How to Use  About  [Theme][FR] [Sign in] │
├────────────────────────────────────────────────────────────────┤
│  Hero: "The school platform built for growth"                   │
│  [Book a demo]  [Get started]                                   │
│  ───── value props / feature cards ─────                        │
│  ───── editions comparison (Nursery..University) ─────          │
│  ───── testimonials / stats ─────                               │
├────────────────────────────────────────────────────────────────┤
│  Footer: product links · legal links · © Academio               │
└────────────────────────────────────────────────────────────────┘
```

Public layout is a navbar + footer shell (`_public.tsx`). The navbar hosts the theme toggle and an auth-aware Sign in / Dashboard button.

### 1.4 Onboarding Wizard — Implemented (`/onboarding`, `_onboarding` layout)

Purpose: first-run school setup for a new tenant. The wizard provisions the school schema synchronously and drives the admin through core configuration steps.

```
┌────────────────────────────────────────────────────────────────┐
│ [logo]  Onboarding                    [Theme][FR] [Sign out]     │
├────────────────────────────────────────────────────────────────┤
│  Step indicator:  1 School  2 Profile  3 Session  4 Classes  5 Subjects  6 Curriculum │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Step title / description                                │  │
│  │                                                          │  │
│  │  ( School name        )   ( School type  [▾ ] )          │  │
│  │  ( Address            )   ( Phone         )              │  │
│  │  [ Upload logo ]                                        │  │
│  │                                                          │  │
│  │                    [ Back ]  [ Continue ]                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Steps (from `components/onboarding/`): `school-step`, `admin-profile-step`, `session-step`, `classes-step`, `subjects-step`, `curriculum-step`; the final step triggers provisioning.
- After completion the app redirects to `/dashboard`; the backend `school.schema_name` field becomes non-empty when provisioned (frontend polls `GET /api/v2/schools/:id`).
- Class and subject steps reuse the same form field components as the Academics screens (`class-form-fields.tsx`, `subject-form-fields.tsx`, `session-form-fields.tsx`, `school-form-fields.tsx` in `components/forms/`), guaranteeing consistency.

### 1.5 Admin Dashboard — Implemented (`/dashboard`)

Purpose: the operational home for school administrators — day-at-a-glance statistics, quick actions, recent activity, and alerts.

```
┌──────────────┬─────────────────────────────────────────────────────┐
│ # Overview   │  Header: [School badge] Tue, Jul 31 · 10:42 AM   [⌘K] [FR][Theme][Bell][User] │
│ #  Dashboard │─────────────────────────────────────────────────────│
│ #  My School │  Breadcrumb: Home                                    │
│ #  AI Assis. │                                                     │
│ #────────────#  Welcome back, Ada — here's what's happening today   │
│ # Academics  #  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ #  Acads     #  │ 1,248    │ │ 64       │ │ 92%      │ │ 18       │ │
│ #  Promotion #  │ Students │ │ Teachers │ │ Attend.  │ │ Pending  │ │
│ #  Timetables#  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│ #  Attendance#  ┌─ Quick Actions ──────────┐ ┌─ Recent Activity ──┐ │
│ #  Exams     #  │ [Add student] [Add teacher]│ │ • Fee paid: A. Bello│ │
│ #  Lesson Pl.#  │ [Record attendance] [New bill]│ │ • Result approved │ │
│ #  LMS       #  │ [Message parents] [Report] │ │ • New application  │ │
│ #  Career    #  └───────────────────────────┘ └────────────────────┘ │
│ #  Confs     #  ┌─ Analytics snapshot (enrollment trend line) ─────┐ │
│ #  Ext. exams#  │  ▁▂▃▅▇ chart · 12-month enrolment                │ │
│ #────────────#  └───────────────────────────────────────────────────┘ │
│ # Assessment #  Pending result approvals: [View workflow]            │
│ #  CBA …     #                                                        │
│ # Results …  #                                                        │
│ # Admissions #                                                        │
│ # Resources  #                                                        │
│ # Pastoral   #                                                        │
│ # Finance    #                                                        │
│ # People     #                                                        │
│ # Analytics  #                                                        │
│ # Discussion #                                                        │
│ # Communic.  #                                                        │
│ # Settings   #                                                        │
└──────────────┴─────────────────────────────────────────────────────┘
```

Interaction notes:

- Components: `StatsCard` grid, `QuickActions`, `RecentActivity`, `AnalyticsChart` (recharts). All monetary stats render in NGN with the Naira symbol (Rule F5).
- The left rail is the collapsible role-scoped sidebar (Section 3.1); the header hosts the school badge, live clock, command palette trigger (⌘K), language/theme toggles, notification bell, and user dropdown.
- Links to `/analytics` (executive overview), `/results` (pending approvals), and workflow-driven items per `docs/WORKFLOW-IMPLEMENTATION.md`.

### 1.6 Teacher Dashboard — Implemented (`/teacher/dashboard`)

Purpose: a focused view for teachers — their classes, today's timetable, pending score entry, and announcements.

```
┌──────────────┬─────────────────────────────────────────────────────┐
│ # Overview   │  Header: [School badge] … [⌘K][FR][Theme][Bell][User]      │
│ #  Dashboard │─────────────────────────────────────────────────────│
│ #────────────#  Welcome back, Mr. Okafor                             │
│ # Academics  #  ┌─ Today's timetable ──────┐ ┌─ My classes ───────┐ │
│ #  Score Entry#  │ Period 1 · JSS 2A · Math │ │ JSS 2A · Class Tchr│ │
│ #  Timetable #  │ Period 2 · JSS 3B · Math  │ │ JSS 3B             │ │
│ #  Attendance#  │ …                         │ │ SS 1A              │ │
│ #  Lesson Pl.#  └───────────────────────────┘ └────────────────────┘ │
│ #────────────#  ┌─ Pending tasks ──────────────┐ ┌─ Announcements ─┐ │
│ # My Class   #  │ 3 assessments need score     │ │ • Staff meeting  │ │
│ #────────────#  │ 1 attendance mark pending    │ │ • Term 3 begins  │ │
│ # Results    #  └──────────────────────────────┘ └──────────────────┘ │
│ #  Results   #                                                       │
│ #  Master Sh.#                                                       │
│ #  Report C. #                                                       │
│ #────────────#                                                       │
│ # Analytics  #                                                       │
│ # Discussion #                                                       │
│ # Communic.  #                                                       │
└──────────────┴─────────────────────────────────────────────────────┘
```

Interaction notes:

- The teacher rail is a reduced group set (Section 3.1.2): Overview, Academics (Score Entry, Timetable, Attendance, Lesson Plans), My Class, Results, Analytics & Reports, Discussion, Communication.
- The "Report Cards" item appears only when the teacher is a class teacher (filtered at render time via `useTeacherDetail`).
- Score Entry links to `/teacher/academics`; results workflow (submit → class teacher → department → vice principal) is driven by the workflow engine.

### 1.7 Student Portal Dashboard — Implemented (`/student`)

Purpose: the student-facing home — results summary, attendance, fees balance, timetable, and report cards. The sidebar group is titled "Student Portal".

```
┌──────────────┬─────────────────────────────────────────────────────┐
│ # Student    │  Header: [School badge] … [⌘K][FR][Theme][Bell][User]      │
│ #  Dashboard │─────────────────────────────────────────────────────│
│ #  My Results#  Hi, Chidi — Term 3, 2025/2026                        │
│ #  Attendance#  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│ #  Fees      #  │ 87.5%    │ │ 12       │ │ ₦45,000  │             │
│ #  Timetable #  │ Attendance│ │ Subjects │ │ Fees due │             │
│ #  Report C. #  └──────────┘ └──────────┘ └──────────┘             │
│ #────────────#  ┌─ Latest results ────────────┐ ┌─ Timetable today ┐│
│ # Learning   #  │ Mathematics  A1  92%        │ │ 08:00 Math JSS2A ││
│ #  LMS       #  │ English     B2  78%         │ │ 09:00 English    ││
│ #  My Exams  #  │ [View all results]          │ │ 10:00 Physics    ││
│ #  Forums    #  └─────────────────────────────┘ └──────────────────┘│
│ #────────────#  ┌─ Announcements ──────────────────────────────────┐│
│ # Communic.  #  │ • Mid-term break: Oct 12–16 · • Exam timetable   ││
│ #  Notif.    #  └──────────────────────────────────────────────────┘│
│ #  Messages  #                                                       │
│ #  AI Assist.#                                                       │
│ #────────────#                                                       │
│ # Settings   #                                                       │
│ #  Profile   #                                                       │
└──────────────┴─────────────────────────────────────────────────────┘
```

Interaction notes:

- All monetary values (fees) render with the Naira symbol (Rule F5).
- Sub-routes: `/student/results`, `/student/attendance`, `/student/fees`, `/student/timetable`, `/student/report-cards`.
- Learning group reuses shared routes (`/lms`, `/cba/exams`, `/forum`) that are also used by admin/teacher — access is role-gated at the API layer.

### 1.8 Parent Portal Dashboard — Implemented (`/parent`)

Purpose: parent-facing home — children summary, fees, notices, and quick links into shared modules.

```
┌──────────────┬─────────────────────────────────────────────────────┐
│ # Overview   │  Header: [School badge] … [⌘K][FR][Theme][Bell][User]      │
│ #  Dashboard │─────────────────────────────────────────────────────│
│ #────────────#  Welcome, Mrs. Bello                                   │
│ # Academics  #  ┌─ My children ────────────────────────────────────┐ │
│ #  My Child. #  │ [Avatar] Adaeze Bello · JSS 2A · Attendance 96% │ │
│ #  Timetable #  │ [Avatar] Tobi Bello · SS 1B  · Attendance 91%   │ │
│ #  LMS       #  │ [View all children]                              │ │
│ #  Forums    #  └──────────────────────────────────────────────────┘ │
│ #  Career    #  ┌─ Notices ──────────────┐ ┌─ Fees ───────────────┐ │
│ #────────────#  │ • PTA meeting Thu      │ │ ₦38,500 due for      │ │
│ # Alumni     #  │ • School closes Dec 18 │ │ Adaeze [Pay now]     │ │
│ #────────────#  └────────────────────────┘ └──────────────────────┘ │
│ # Payments   #                                                       │
│ #  Fees      #                                                       │
│ #────────────#                                                       │
│ # Communic.  #                                                       │
│ #  Notif.    #                                                       │
│ #  Messages  #                                                       │
└──────────────┴─────────────────────────────────────────────────────┘
```

Interaction notes:

- `/parent/children/$id` renders a per-child detail view (progress, results, attendance).
- The sidebar "Fees" item currently links to `/parent/children` (no dedicated parent fees route exists — **Planned**, see Section 2.7).
- Parents can also reach shared routes (`/timetable`, `/lms`, `/forum`, `/alumni`, `/career`) from the rail; these render the shared implementations.

### 1.9 Students Management — Implemented (`/users`, Students tab) / Standalone route Planned (`/students`)

Purpose: the People hub manages all three person types (Students, Teachers, Staff) from one route with tabs. Student and teacher rows support create, edit, detail (right-hand sheet), search, pagination, CSV export, and bulk import.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Users                                            │
│  Users                                                    [Add user]│
│  [ Students ] [ Teachers ] [ Staff ]                                │
│  ( Search students...        )  [Export CSV] [Import]               │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ | Student | Class | Admission No. | Status   | Actions      | │  │
│  │ | Adaeze  | JSS2A | ACM-2025-0412 | Active   | [...]          | │  │
│  │ | Chidi   | SS1B  | ACM-2025-0418 | Active   | [...]          │  │
│  │ | …       |       |               |          |              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  [< Prev]  Page 1 of 84  [Next >]                                   │
│                                                                     │
│  [...] menu → View profile · Edit · Deactivate                       │
│  ┌─ View profile (right sheet) ──────────────────────────────────┐  │
│  │ Avatar, name, class, admission no, guardian, fees, contact    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Create flow is a 3-step wizard (personal → guardian/parent → preview) with avatar upload in step 1 (audit H-5/H-6: JPEG/PNG/WebP, 5 MB max).
- Entity selects (class, level, guardian) follow the **Base UI entity-name pattern** (Rule F1): `SelectItem` values are entity names, not raw IDs (see Section 4.8).
- The `/users/student` route (`users.student.tsx`) exists as a dedicated student view; the standalone `/students` route is **Planned** for a future split of the consolidated People hub (audit Q-1 recommends splitting the 1,900-line `users.tsx`).

### 1.10 Teachers Management — Implemented (`/users`, Teachers tab)

Identical shell to 1.9 with teacher-specific fields: staff ID, subjects (multi-select), assigned class (class teacher), employment date, department. Detail sheet shows assigned subjects, class, and contact. Uses the same table/sheet/form components as Students; `view-teacher-sheet.tsx`, `add-user-form.tsx` shared components.

### 1.11 Academics — Classes, Levels, Subjects, Assessments — Partial (`/academics`)

There is **no standalone Classes, Levels, or Subjects route** today; these are managed inside the Academics screen, which is also where assessments, grade items, and score grids live. Standalone screens are **Planned** (see 2.7).

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Academics                                        │
│  Academics                                                          │
│  [ Sessions ] [ Classes ] [ Subjects ] [ Assessments ] [ Curriculum ]│
│                                                                     │
│  ┌─ Sessions ────────────────────────────────────────────────────┐  │
│  │ Current session: 2025/2026 · Term 3     [Add session]        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Classes / Levels ────────────────────────────────────────────┐  │
│  │ | Level | Arms | Class Teacher   | Subjects | Actions        | │  │
│  │ | JSS 2 | A, B | Mr. Okafor      | 8        | [...]            │  │
│  │ [ Add level ] [ Add arm ]                                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Subjects (curriculum) ───────────────────────────────────────┐  │
│  │ | Subject | Code | Assessments (CA/Midterm/Exam) | Actions   │  │
│  │ | Math    | MTH  | 30 / 20 / 50                 | [...]        │  │
│  │ [ Add subject ] [ Excel upload ]                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Assessments / Grade items ───────────────────────────────────┐  │
│  │ Assessment totals must equal 100  (live validation)           │  │
│  │ | Assessment | Weight | Grade items | CBA link | Actions     │  │
│  │ | CA         | 30     | [sub-items] | optional | [...]         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Assessment weight validation ("totals must be 100") is enforced live (`academics.*` i18n keys, e.g. `assessments_total_error`).
- Curriculum can be seeded via Excel upload step (`excel-upload-step.tsx`).
- Score entry grids (`score-grid.tsx`) support inline editing with grade-item columns.
- Entity selects for class/level/subject/teacher across the platform must follow Rule F1.

### 1.12 Results & Master Sheet — Implemented (`/results`, `/results/master-sheet`, `/teacher/results`, `/teacher/results/master-sheet`, `/grading`)

Purpose: approve and publish results, review the school-wide master sheet, and maintain grading scales.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Results                                          │
│  Results                                                  [Export]  │
│  Filters:  Session [▾]  Term [▾]  Class [▾]  Assessment [▾]        │
│  ┌─ Approval workflow status ────────────────────────────────────┐  │
│  │  Teacher submits  →  Class Teacher  →  Department  →  VP      │  │
│  │  [Pending review]  [Approved]  [Returned]  [Rejected]         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Results table ───────────────────────────────────────────────┐  │
│  │ | Student | Math | Eng | Phy | Total | Avg | Grade | Position | │
│  │ | Adaeze  | 92   | 78  | 85  | 255   | 85  | A1    | 1       │  │
│  │ …                                                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  [ View master sheet ]  [ Generate report cards ]                  │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Workflow stages come from the enterprise workflow engine (`docs/WORKFLOW-IMPLEMENTATION.md`); result approval is one of its first consumers.
- Master sheet mirrors this table with all assessments side by side and supports CSV/XLSX export (`export-csv.tsx`).
- Grading (`/grading`) configures grade boundaries (A1, B2, C4, …) used by the table.
- Teachers reach a scoped copy at `/teacher/results` and `/teacher/results/master-sheet`; their submissions feed the same workflow.

### 1.13 Report Cards — Implemented (`/report-cards`, `/report-cards/$id`, `/report-cards/batch`)

List view shows generated report cards per student/class with status (draft, published). The detail route renders the card layout; batch generates cards for a whole class. A template builder (`components/template-builder/`) provides a drag-and-drop editor for card layouts (canvas, toolbox, properties panel, live result-slip preview). Teachers access a scoped copy at `/teacher/report-cards`.

### 1.14 CBA — Computer-Based Assessment — Implemented (`/cba`, `/cba/exams`, `/cba/exams/$examId/take`, `/cba/exams/$examId/results`)

Purpose: create CBT exams, take them in a secure player, and review auto-graded results.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > CBA > Exam 41                                    │
│  ┌─ Exam player ────────────────────────────────────────────────┐  │
│  │  Mathematics — Mid-Term CBT          Timer: 18:42  [Submit]  │  │
│  │  Question 12 of 40                                            │  │
│  │  Solve for x: 3x + 5 = 20                                     │  │
│  │  ( ) 3   ( ) 4   ( ) 5   ( ) 6                                │  │
│  │  ┌─ Question palette ─┐                                       │  │
│  │  │ [1][2][3][4][5]     │   Answered: 11                       │  │
│  │  │ [6][7][8][9][10]    │   Unanswered: 29                     │  │
│  │  │ [11][12][13][14][15]│                                      │  │
│  │  └─────────────────────┘                                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  [ Previous ]  [ Next ]                                            │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Exam builder lives at `/cba/exams`; results at `/cba/exams/$examId/results`; proctoring at `/proctoring`.
- Timer, auto-save, and question palette are core player behaviors; auto-graded scores feed assessments via the optional "CBA Assignment" link in Academics.
- Students reach their exams via `/cba/exams` (sidebar "My Exams").

### 1.15 Attendance — Implemented (`/attendance`, `/teacher/attendance`, `/student/attendance`)

Purpose: mark and review attendance per class/date; students see their own record.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Attendance                                       │
│  Attendance                                                         │
│  Date: ( 2026-07-31 )  Class: [▾ JSS 2A]  Session: [▾ 2025/2026]   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ | # | Student        | Status          | Remark              │  │
│  │ | 1 | Adaeze Bello   | (o) P [ ] A [ ] L | ( note )          │  │
│  │ | 2 | Chidi Okafor   | (o) P [ ] A [ ] L | ( note )          │  │
│  │ | 3 | …              |                 |                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  [ Mark all present ]  [ Save attendance ]   Rate: 92%             │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Admin marks for any class; teacher marks for their own classes (`/teacher/attendance`); students view their record with a calendar/heatmap summary (`/student/attendance`).
- Bulk toolbar behavior mirrors the timetable bulk editor patterns.

### 1.16 Timetable — Implemented (`/timetable`, `/teacher/timetable`, `/student/timetable`)

Purpose: build and view the weekly timetable grid with drag-and-drop period editing.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Timetables                                       │
│  Timetable — JSS 2A                      [Week: [▾] ] [Bulk edit]  │
│  ┌─────────┬──────────┬──────────┬──────────┬──────────┬─────────┐ │
│  │ Period  │ Mon      │ Tue      │ Wed      │ Thu      │ Fri     │ │
│  │ 08:00-  │ Math     │ English  │ Physics  │ Math     │ English │ │
│  │ 08:40   │ A. Musa  │ B. Adamu │ C. Eze   │ A. Musa  │ B. Adamu│ │
│  │ 09:00-  │ English  │ Math     │ Chemistry│ …        │ …       │ │
│  │ 09:40   │ …        │ …        │ …        │          │         │ │
│  └─────────┴──────────┴──────────┴──────────┴──────────┴─────────┘ │
│  [ Add period ]  [ Publish ]   Conflicts: 0                        │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Components: `calendar-editor-view`, `calendar-grid`, `bulk-toolbar` in `components/timetable/`.
- Teacher view (`/teacher/timetable`) shows only the teacher's periods; student view (`/student/timetable`) shows the class timetable. Parents reach `/timetable` from the shared route.

### 1.17 Finance / Bills — Implemented (`/finance`, `/bills`, `/payment`, `/student/fees`, `/analytics/revenue`)

Purpose: fee structures, bill generation, payment tracking, and revenue analytics.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Bills                                            │
│  Bills                                                    [New bill]│
│  ( Search student/class )   Status: [▾ All]   Term: [▾ Term 3]     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ | Student  | Class | Items        | Amount  | Paid   | Status |  │
│  │ | Adaeze   | JSS2A | Tuition+Books| ₦85,000 | ₦46,500| Partial|  │
│  │ | Chidi    | SS1B  | Tuition      | ₦95,000 | ₦95,000| Paid   |  │
│  │ …                                                                │
│  └───────────────────────────────────────────────────────────────┘  │
│  Totals: ₦1,240,000 billed · ₦980,000 collected                    │
│  [ Generate class bills ]  [ Export CSV ]                           │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- **All monetary values render with the Naira symbol (Rule F5)**; `formatCurrency` lives in `src/lib/utils.ts` (line 63) and uses safe rounding (audit M-1).
- `/finance` is the general ledger/home, `/bills` the fee-bill workspace, `/payment` records receipts, `/student/fees` is the student's own ledger, and `/analytics/revenue` trends collections.
- Payment confirmations raise Sonner toasts and feed the notification center.

### 1.18 Admissions — Implemented (`/admissions/*` admin suite + `/admissions/apply`, `/admissions/status` public)

Purpose: full prospect-to-enrollee pipeline — intakes, application forms (drag-and-drop form builder), applications inbox, screening, offers.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Admissions > Applications                        │
│  Admissions                                              [New form] │
│  [ Dashboard ] [ Applications ] [ Intakes ] [ Forms ] [ Screening ] [ Offers ] │
│  ┌─ Stats ───────────────────────────────────────────────────────┐  │
│  │ 124 Applications · 38 Screening · 21 Offers · 12 Enrolled    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Applications table ──────────────────────────────────────────┐  │
│  │ | Applicant | Intake  | Status    | Screening | Actions     │  │
│  │ | A. Yusuf  | Sep 2026| In review | 82/100    | [...]         │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  Application detail (application.$id):                             │
│  ┌─ Status timeline ─┐ ┌─ Form steps ──────────────────────────┐  │
│  │ Submitted →       │ │ Personal → Contact → Academic →      │  │
│  │ Screening → Offer │ │ Documents → Review                    │  │
│  └───────────────────┘ └───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Admin suite: `/admissions` (dashboard), `/admissions/applications`, `/admissions/application/$id`, `/admissions/intakes`, `/admissions/forms` (+ `/admissions/forms/$id` form editor), `/admissions/screening`, `/admissions/offers`.
- Public flow: `/admissions/apply` (multi-step `ApplicationForm` with Personal/Contact/Academic/Review steps + document upload), `/admissions/route` (programme selection), `/admissions/status` (application lookup).
- Status changes ride the workflow engine (admission approval is a configured workflow).

### 1.19 Communication / Messages — Implemented (`/messages`, `/communication/*`, `/notifications`, `/forum`)

Purpose: in-app messaging, broadcast campaigns (email/SMS/push), templates, delivery log, and school forums.

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Communication > Compose                          │
│  Compose message                                                    │
│  Audience: [▾ Whole school | Class | Parents | Custom]              │
│  Channel: [x] Email  [x] SMS  [ ] Push  [ ] In-app                  │
│  ( Subject                      )                                   │
│  ( Message body…                                  )                 │
│  [ Insert template ▾ ]  [ Attach file ]                             │
│  ┌─ Preview / recipients ───────────────────────────────────────┐  │
│  │ 1,240 recipients · Parents of JSS 2 · 0 excluded             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  [ Schedule ▾ ]  [ Send now ]                                      │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- Routes: `/communication/compose`, `/communication/templates`, `/communication/campaigns` (+ `/communication/campaigns/$id`), `/communication/broadcast`, `/communication/delivery`.
- Inbox: `/messages` (threads, conversation detail), compose from shared component `components/` messaging flows.
- `/notifications` is the notification center (bell in header); `/forum` (+ `/forum/$id`, `/forum/posts/$postId`) hosts school discussions with moderation.
- SMS/email gateway configuration is backend-side; the UI only selects channels and audiences.

### 1.20 Settings & Profile — Implemented (`/settings`, `/profile`, `/change-password`, `/school`, `/audit-logs`)

```
┌────────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Home > Settings                                         │
│  Settings                                                           │
│  [ General ] [ Academic ] [ Notifications ] [ Security ]            │
│  ┌─ General ────────────────────────────────────────────────────┐  │
│  │ ( School name )   ( Session default )   ( Term )             │  │
│  │ [ Logo upload ]  [ Theme: light/dark ]  [ Language: en/fr ]  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌─ Security ───────────────────────────────────────────────────┐  │
│  │ Two-factor authentication  [Enable]  · Active sessions [View]│  │
│  │ Change password → /change-password                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- `/settings` groups institution and app preferences; `/profile` edits the user's own profile (avatar upload, edit profile modal, active sessions modal, 2FA modal, change-password modal — `components/profile/`).
- `/school` ("My School") edits institution details, incl. Google Places address lookup; `/audit-logs` reviews platform audit entries (Rule B11 audit trail).

### 1.21 Super Admin Console — Implemented (`/super`, `/super/$id`, `_super` layout)

Purpose: platform operator view — school registry, provisioning status, and per-school drill-down; entry point for admin impersonation.

```
┌────────────────────────────────────────────────────────────────────┐
│ [logo]  Super Admin Console                  [FR][Theme] [Sign out] │
├────────────────────────────────────────────────────────────────────┤
│  Schools                                                  [Search] │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ | School   | Type     | Schema        | Status      | Actions |  │
│  │ | Greenhill| Secondary| school_12     | Provisioned | [Open]  │  │
│  │ | Kids Nest| Nursery  | (empty)       | Pending     | [Open]  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  School detail (/super/$id):                                        │
│  Overview · Users · Provisioning · [Impersonate admin]              │
└────────────────────────────────────────────────────────────────────┘
```

Interaction notes:

- The `_super` layout is a separate minimal shell (navbar only, no dashboard sidebar).
- "Impersonate admin" starts an impersonation session; the dashboard layout then shows the violet **Impersonation Banner** with a live elapsed timer and a Stop button (`dashboard-layout.tsx`). While impersonating, the user dropdown gains "Switch School" (`/super`).

### 1.22 Screen Status Summary

| Screen | Primary route(s) | Status |
|--------|------------------|--------|
| Login / Auth flows | `/login`, `/register`, `/forgot-password`, `/reset-password`, `/confirm-email` | Implemented |
| Public marketing site | `/_public/*` | Implemented |
| Onboarding wizard | `/onboarding` | Implemented |
| Admin dashboard | `/dashboard` | Implemented |
| Teacher dashboard | `/teacher/dashboard` | Implemented |
| Student portal | `/student`, `/student/results`, `/student/attendance`, `/student/fees`, `/student/timetable`, `/student/report-cards` | Implemented |
| Parent portal | `/parent`, `/parent/children/$id` | Implemented |
| Students management | `/users` (Students tab), `/users/student` | Implemented; standalone `/students` route Planned |
| Teachers management | `/users` (Teachers tab) | Implemented |
| Classes / Levels | inside `/academics` | Partial — standalone route Planned |
| Subjects / Curriculum | inside `/academics` | Partial — standalone route Planned |
| Assessments / Grading | `/academics`, `/grading` | Implemented |
| Results & Master Sheet | `/results`, `/results/master-sheet`, `/teacher/results/*` | Implemented |
| Report cards | `/report-cards`, `/report-cards/$id`, `/report-cards/batch` | Implemented |
| CBA exams | `/cba`, `/cba/exams`, `/cba/exams/$examId/take`, `…/results` | Implemented |
| Attendance | `/attendance`, `/teacher/attendance`, `/student/attendance` | Implemented |
| Timetable | `/timetable`, `/teacher/timetable`, `/student/timetable` | Implemented |
| Finance / Bills | `/finance`, `/bills`, `/payment`, `/student/fees`, `/analytics/revenue` | Implemented |
| Admissions | `/admissions/*`, `/admissions/apply`, `/admissions/route`, `/admissions/status` | Implemented |
| Communication | `/communication/*`, `/messages`, `/notifications`, `/forum*` | Implemented |
| Settings & Profile | `/settings`, `/profile`, `/change-password`, `/school`, `/audit-logs` | Implemented |
| Super admin console | `/super`, `/super/$id` | Implemented |
| Parent fees dashboard | (sidebar "Fees" → `/parent/children`) | Planned — no dedicated route |
| Parent children list | `/parent/children/$id` exists; list route | Partial — list route Planned |

---

## 2. Information Architecture

### 2.1 Principles

1. **Role-first portals.** The same SPA renders five experience areas — public, auth, onboarding, dashboard, and super admin — selected by authentication and role. Within the dashboard, the sidebar data model selects the navigation set for the user's role (`sidebar-data.ts`: admin / teacher / student / parent).
2. **Shared module routes with role scoping.** Modules such as LMS, CBA exams, forums, and reports are single routes reused across portals; the backend enforces data scope per role (Rule B8, tenant-scoped queries).
3. **Progressive disclosure.** Top-level routes are destinations, not menus. Detail views are right-hand sheets (students, teachers, staff) or dedicated `/$id` routes (applications, campaigns, forum threads, lesson plans, report cards).
4. **Module-deep organization in the admin rail.** The admin sidebar groups 13 headings (Overview, Academics, Assessment, Results, Admissions, Resources, Pastoral, Finance, People, Analytics & Reports, Discussion, Communication, Settings) — the authoritative information hierarchy for administrators.
5. **Route files encode the tree.** TanStack Router file-based routing means every directory/file under `src/routes/` is the source of truth for the IA (naming conventions in 2.3).

### 2.2 Top-Level Sitemap

```
academio.app
├── (public)  _public layout ───────────── navbar + footer
│   ├── /                         landing
│   ├── /about                    about
│   ├── /features                 features
│   ├── /editions                 editions (Nursery … University)
│   ├── /how-to-use               how-to-use
│   ├── /privacy · /terms · /cookies
│   └── /admissions/apply · /admissions/route · /admissions/status
│
├── (auth)    standalone ───────── no shared chrome
│   ├── /login · /register
│   ├── /forgot-password · /reset-password · /confirm-email
│
├── (onboarding)  _onboarding layout ── minimal navbar
│   └── /onboarding               school setup wizard
│
├── (super)    _super layout ───── minimal navbar
│   ├── /super                    school registry (super index)
│   └── /super/$id                school detail + impersonation
│
└── (dashboard)  _dashboard layout ── sidebar + header + breadcrumbs
    ├── /dashboard                admin dashboard
    ├── /school                   My School
    ├── /ai-assistant             AI assistant chat
    ├── /academics                sessions, classes, subjects, assessments
    ├── /promotion                promotion manager
    ├── /timetable                timetable builder
    ├── /attendance               attendance register
    ├── /exams · /external-exam   exams, external exams
    ├── /lesson-plans             (+ /notes/$id, /plans/$id, /schemes/$id)
    ├── /lms                      (+ /lms/$courseId, assignments, discussions)
    ├── /career · /conferences
    ├── /cba · /cba/exams         (+ /cba/exams/$examId/take, …/results)
    ├── /grading · /proctoring
    ├── /results                  (+ /results/master-sheet)
    ├── /report-cards             (+ /report-cards/$id, /report-cards/batch)
    ├── /analytics                (+ /analytics/academic, /enrollment, /revenue)
    ├── /admissions               (+ applications, application/$id, intakes,
    │                               forms, forms/$id, screening, offers)
    ├── /media · /library · /hostel · /transport · /inventory
    ├── /pastoral · /discipline · /student-health
    ├── /finance · /bills · /payment
    ├── /hr · /users · /users/student · /invitations · /profile
    ├── /alumni                   (+ /alumni/insights)
    ├── /reports                  (+ /reports/builder)
    ├── /forum                    (+ /forum/$id, /forum/posts/$postId)
    ├── /communication            (+ compose, templates, campaigns,
    │                               campaigns/$id, broadcast, delivery)
    ├── /messages · /notifications
    ├── /settings · /audit-logs · /change-password
    ├── /academic-calendar        (+ /calendar, /events, /periods,
    │                               /blueprints/$id/edit)
    ├── /parent                   parent portal
    ├── /student                  student portal
    └── /teacher/*                teacher portal (dashboard, academics,
                                    timetable, attendance, class,
                                    results, results/master-sheet,
                                    report-cards)
```

### 2.3 Route Conventions (TanStack Router)

| Pattern | Example | Resulting path |
|---------|---------|----------------|
| `_layout.tsx` | `_dashboard.tsx`, `_public.tsx`, `_onboarding.tsx`, `_super.tsx` | layout group, invisible in URL |
| `file.tsx` | `attendance.tsx` | `/attendance` |
| `dir/index.tsx` | `results/index.tsx` | `/results` |
| `a.b.c.tsx` | `teacher.results.master-sheet.tsx` | `/teacher/results/master-sheet` |
| `$param.tsx` | `lms.$courseId.tsx` | `/lms/:courseId` |
| `parent.children.$id.tsx` | — | `/parent/children/:id` |
| `__root.tsx` | — | root layout: ThemeProvider + ErrorBoundary + AuthProvider + Toaster |

The root also defines `notFoundComponent` (404) and the dashboard layout applies `beforeLoad` auth + onboarding redirect guards (audit H-12).

### 2.4 Portal Separation Model

| Portal | Route root(s) | Rail (sidebar-data group key) | Default landing |
|--------|---------------|-------------------------------|-----------------|
| Public | `/` (marketing) | none | `/` |
| Auth | `/login` etc. | none | `/dashboard` after login |
| Onboarding | `/onboarding` | none | `/onboarding` until school provisioned |
| Super admin | `/super` | none (own shell) | `/super` |
| Admin | `/dashboard` … (shared area) | `admin` | `/dashboard` |
| Teacher | `/teacher/*` + shared area | `teacher` | `/teacher/dashboard` |
| Student | `/student/*` + shared area | `student` | `/student` |
| Parent | `/parent/*` + shared area | `parent` | `/parent` |

Role mapping to rail keys (`sidebar-data.ts` + command palette): `super-admin`, `super_admin`, `admin`, `principal`, `staff` → `admin`; `teacher` → `teacher`; `student` → `student`; `parent` → `parent`.

### 2.5 Route Inventory (dashboard area, per feature)

Counts are route files in `src/routes/_dashboard/` (100+ files as of this writing).

| Area | Routes | Notes |
|------|--------|-------|
| Academic calendar | 5 | `/academic-calendar`, `/calendar`, `/events`, `/periods`, `/blueprints/$id/edit` |
| Academics core | 6+ | `/academics`, `/promotion`, `/grading`, `/exams`, `/external-exam`, `/school` |
| Timetable | 3 | `/timetable`, `/teacher/timetable`, `/student/timetable` |
| Attendance | 3 | `/attendance`, `/teacher/attendance`, `/student/attendance` |
| Lesson plans | 4 | `/lesson-plans`, `/notes/$id`, `/plans/$id`, `/schemes/$id` |
| LMS | 6 | `/lms`, `/lms/$courseId`, assignments (list + detail), discussions (list + detail) |
| CBA | 4 | `/cba`, `/cba/exams`, `/cba/exams/$examId/take`, `/cba/exams/$examId/results` |
| Proctoring | 1 | `/proctoring` |
| Results | 5 | `/results`, `/results/master-sheet`, `/teacher/results`, `/teacher/results/master-sheet`, `/report-cards` family |
| Report cards | 3 | `/report-cards`, `/report-cards/$id`, `/report-cards/batch` |
| Analytics | 4 | `/analytics`, `/analytics/academic`, `/analytics/enrollment`, `/analytics/revenue` |
| Admissions | 10 | admin: `/admissions`, `/applications`, `/application/$id`, `/intakes`, `/forms`, `/forms/$id`, `/screening`, `/offers`; public: `/admissions/apply`, `/admissions/status`, `/admissions/route` |
| Resources | 5 | `/media`, `/library`, `/hostel`, `/transport`, `/inventory` |
| Pastoral | 3 | `/pastoral`, `/discipline`, `/student-health` |
| Finance | 5 | `/finance`, `/bills`, `/payment`, `/student/fees`, `/analytics/revenue` |
| People | 6 | `/hr`, `/users`, `/users/student`, `/invitations`, `/profile`, `/alumni`, `/alumni/insights` |
| Reports | 3 | `/reports`, `/reports/builder`, `/reports/index` |
| Discussion | 3 | `/forum`, `/forum/$id`, `/forum/posts/$postId` |
| Communication | 8 | `/communication/compose`, `/templates`, `/campaigns`, `/campaigns/$id`, `/broadcast`, `/delivery`, `/messages`, `/notifications` |
| Settings | 5 | `/settings`, `/audit-logs`, `/change-password`, `/school`, `/profile` |
| AI | 1 | `/ai-assistant` |
| Student portal | 6 | `/student`, `/student/results`, `/student/attendance`, `/student/fees`, `/student/timetable`, `/student/report-cards` |
| Teacher portal | 8 | `/teacher/dashboard`, `/teacher/academics`, `/teacher/timetable`, `/teacher/attendance`, `/teacher/class`, `/teacher/results`, `/teacher/results/master-sheet`, `/teacher/report-cards` |
| Parent portal | 2 | `/parent`, `/parent/children/$id` |

### 2.6 Content Depth

- **Level 0 — Landing/posts**: routes that are full destinations (dashboard, lists, forms).
- **Level 1 — Detail routes**: `/$id` routes for objects that need deep links (application, course, campaign, forum thread, lesson plan, report card, school in super console).
- **Level 2 — Sheets**: transient detail views (student/teacher/staff profiles) that do not need their own URL — right-hand `Sheet` components with `aria-labelledby` (audit M-5).
- **Level 3 — Modals**: small forms and confirmations (`Dialog`, `AlertDialog`) scoped to the current page.

### 2.7 Known Gaps and Route Inconsistencies (found during this audit)

1. **Parent "Fees" link** (`sidebar-data.ts`) points to `/parent/children` — there is no dedicated parent fees route (`/parent/fees` is **Planned**); the parent Payments group and the Fees item are effectively duplicates.
2. **No `/parent/children` list route** — only `parent/children.$id.tsx` exists; the sidebar's "My Children" target (`/parent/children`) has no matching index route and will resolve to the 404 handler.
3. **No standalone Classes/Levels or Subjects routes** — these are managed inside `/academics` (Partial); a dedicated route would improve deep-linking and teacher navigation.
4. **No standalone `/students` and `/teachers` routes** — consolidated in `/users` tabs; `/users/student` exists but is not surfaced in the sidebar.
5. **Parent portal reuses admin paths** (`/timetable`, `/lms`, `/forum`, `/alumni`, `/career`) rather than parent-scoped paths — works today because routes are shared, but muddies role-based analytics and permission visibility.
6. **`breadcrumbs.tsx` label maps** are not exhaustive — segments without a `ROUTE_LABELS`/`nav.*` entry fall back to capitalized segment text, which can produce non-translated crumbs (e.g., deep analytics or communication sub-routes).
7. **`/teacher` itself has no route** — breadcrumbs special-case it to `/teacher/dashboard`; direct navigation to `/teacher` would 404.

---

## 3. Navigation Design

### 3.1 Sidebar Navigation

#### 3.1.1 Structure and behavior

- The sidebar is a fixed left rail (`AppSidebar`), width `w-64` expanded / `w-16` collapsed, collapsible via the sidebar store (Zustand, persisted). Collapsed mode shows icons only with tooltips; the logo switches to the icon-only mark.
- Navigation is organized into **groups** with headers; groups are collapsible (chevron, `aria-expanded`, keyboard togglable with Enter/Space). Group collapse state is per-user persisted (`collapsedGroups`).
- Active state is derived from `pathname === item.href`; icons are Lucide React at `w-4 h-4`, `strokeWidth 2.5`.
- A search shortcut chip at the top of the expanded rail opens the command palette (⌘K).
- Keyboard users get a skip-to-content link (`#main-content`) before the sidebar (audit A-2).

#### 3.1.2 Admin group model (13 groups)

| Group | Items |
|-------|-------|
| Overview | Dashboard, My School, AI Assistant |
| Academics | Academics, Promotion, Timetables, Attendance, Exams, Lesson Plans, LMS, Career Guidance, Conferences, External Exams |
| Assessment | CBA, CBA Exams, Grading, Proctoring |
| Results | Results, Master Sheet, Report Cards, Performance Analytics |
| Admissions | Dashboard, Applications, Intakes, Forms, Screening, Offers |
| Resources | Media Library, Library, Hostel, Transport, Inventory |
| Pastoral | Pastoral, Discipline, Health |
| Finance | Finance, Bills |
| People | HR, Users, Invitations, Profile, Alumni, Insights |
| Analytics & Reports | Executive Overview, Enrollment Trends, Revenue, Reports |
| Discussion | Forums |
| Communication | Notifications, Messages, Compose, Templates, Campaigns, Broadcast, Delivery Log |
| Settings | Settings, Audit Logs |

#### 3.1.3 Teacher group model (7 groups)

| Group | Items |
|-------|-------|
| Overview | Dashboard |
| Academics | Score Entry, Timetable, Attendance, Lesson Plans |
| My Class | My Class |
| Results | Results, Master Sheet, Report Cards (class teachers only) |
| Analytics & Reports | Reports |
| Discussion | Forums |
| Communication | Notifications, Messages |

#### 3.1.4 Student group model (4 groups)

| Group | Items |
|-------|-------|
| Student Portal | Dashboard, My Results, Attendance, Fees, Timetable, Report Cards |
| Learning & Assessment | LMS, My Exams, Forums |
| Communication | Notifications, Messages, AI Assistant |
| Settings | Profile |

#### 3.1.5 Parent group model (5 groups)

| Group | Items |
|-------|-------|
| Overview | Dashboard |
| Academics | My Children, Timetable, LMS, Forums, Career Guidance |
| Alumni | Alumni |
| Payments | Fees |
| Communication | Notifications, Messages |

All group/item titles are passed through `t("nav.<slug>", { defaultValue })` so rails translate to French when the locale is `fr`.

### 3.2 Portal Switching

- **No explicit portal switcher in the UI.** Portal selection is a function of the authenticated user's role: the rail data key (`admin`/`teacher`/`student`/`parent`) is derived from `user.role` and login redirects to the role default landing.
- **Super admin → school admin impersonation** is the one sanctioned "switch": a super admin opens `/super/$id`, starts impersonation, and the app enters the target school's context with a persistent violet **Impersonation Banner** (target name, role badge, elapsed timer, Stop). While impersonating, the user dropdown shows "Switch School" (`/super`). Stopping impersonation restores the original session and navigates back to `/super`.
- The mobile apps take a different approach (Section 3.8): three separate Flutter flavors with no role switching inside the app; login validates that the role matches the flavor.

### 3.3 Command Palette (⌘K)

- Triggered by Ctrl/⌘+K anywhere in the dashboard layout, or by the header search field.
- Scoped to the current user's role rail (`roleToNavKey` map shared with the sidebar).
- Supports fuzzy title search, arrow-key navigation, Enter to navigate, Escape to dismiss; shows the target path beside each result.
- `Dialog`-based with a visually hidden `DialogTitle` for accessibility.

### 3.4 Header

Fixed/sticky top bar (`h-16`, `backdrop-blur-xl`, shadow on scroll). Contents, left to right:

1. Mobile menu button (hamburger, `md:hidden`) — opens the mobile sheet sidebar.
2. **School badge** — school name with Building2 icon (from `user.schools[0].name`).
3. Live date/time (day, date, clock — hidden on small screens).
4. Search trigger (⌘K affordance, hidden on small screens).
5. Language toggle, theme toggle, notification bell (`NotificationsCenter`), user dropdown (`UserDropdown`: profile, notifications, settings, change password, switch school when impersonating, sign out).

### 3.5 Breadcrumbs

- Rendered by `Breadcrumbs` inside `<main>`; hidden on `/dashboard`.
- Algorithm: split `pathname`, map each segment to a label via `nav.*` i18n keys with an English fallback map (`ROUTE_LABELS`), then a capitalized fallback; parent segments link to their real routes; the last segment is plain text; `/teacher` is rewritten to `/teacher/dashboard`.
- Semantic nav with `aria-label="Breadcrumb"`; first crumb is a Home icon linking to `/dashboard`.

### 3.6 Mobile Responsive Navigation

- **Below `md`**: the desktop sidebar is hidden; a hamburger opens `MobileSidebar`, a right-hand/left `Sheet` reusing the same group/item model and active states.
- Tables collapse to scrollable cards or reduced columns; grids use mobile-first Tailwind breakpoints (`grid-cols-1 sm:grid-cols-2` pattern, audit R-2).
- Header condenses to menu + school badge + bell + user; search and clock are hidden.
- Detail sheets go full-width (`w-full`, `sm:max-w-*`).

### 3.7 Deep Linking and Route Guards

- Every route is deep-linkable; `/$id` routes support refresh-safe navigation.
- `_dashboard` and `_onboarding` apply `beforeLoad` guards: unauthenticated → redirect `/login`; un-onboarded admin → redirect `/onboarding` (audit H-12). `ProtectedRoute` handles initialization only, eliminating the auth flash.
- Unknown paths render the root `notFoundComponent` (404 with "Go home"), per audit H-3.
- Scroll restoration is enabled (`scrollRestoration: true`) so deep links and back/forward land at the top of the target page (audit H-4).

### 3.8 Mobile Navigation (Flutter flavors) — brief IA

Three flavors, one codebase, Material 3 (`AppTheme.light`, seed `#4F46E5`):

| Flavor | Entry | Shell / navigation | Screens |
|--------|-------|--------------------|---------|
| Student & Parent (`com.academio.student`) | `main_student.dart` | `StudentShell` bottom-tab bar; parents route to `ParentDashboard` | Student: dashboard, results, attendance, fees, timetable, report cards. Parent: dashboard, child progress. Shared: login, onboarding, messages, compose, conversation, notifications |
| Teacher (`com.academio.teacher`) | `main_teacher.dart` | drawer (`AcademioDrawer`) + teacher screens | Dashboard, academics (score entry), attendance, class, results, timetable, student health |
| Admin (`com.academio.admin`) | `main_admin.dart` | drawer + admin screens | Dashboard, academics, people (list + detail), hostel, library, transport, more |

Rules: all network via `ApiClient`, state in providers, shimmer loading, secure-storage tokens, no `print()` (M13). The web and mobile share the same REST API (`/api/v2`) but have independent navigation models (persistent rail on web; bottom tabs/drawer on mobile).

---

## 4. UI Component Standards

### 4.1 Design Tokens — "Empathetic Growth" (per `frontend/DESIGN_SYSTEM.md`)

| Token | Light | Dark |
|-------|-------|------|
| Primary (Sage Green) | `#A5A78F` | `#BFC1AB` |
| Secondary (Digital Peach) | `#FF7E5F` | `#FF9B85` |
| Background (Cloud Dancer White) | `#F9F8F3` | `#1C1F1A` |
| Surface | `#FFFFFF` | `#252922` |
| Text primary (Anthracite Gray) | `#2D3436` | `#F9F8F3` |
| Text secondary (Muted Slate) | `#636E72` | `#A5A78F` |
| Success | `#6B8E5A` | — |
| Warning | `#D4A574` | — |
| Error | `#C87F7F` | — |
| Info | `#7B9AA1` | — |

Rules:

- Colors are consumed via Tailwind v4 `@theme inline` utilities (`text-primary`, `bg-background`, `text-text-secondary`, `border-border`, etc.). Do not hardcode hex values in components.
- Accessibility first: text/background pairs must meet WCAG 2.2 AA (audit A-4: do not use raw primary for small text on background; use semantic tokens).
- Dark mode is driven by the `.dark` class + `ThemeProvider`; `ThemeToggle` ships in public, auth, onboarding, super, and dashboard headers.
- Avoid global theme transitions that flash on first paint (audit M-4).

### 4.2 Typography, Spacing, Radius, Shadow

| Concern | Standard |
|---------|----------|
| Type scale | `h1` 4xl bold, `h2` 3xl semibold, body base, meta `text-sm`/`text-xs`; Inter via `@fontsource/inter` |
| Spacing | page padding `p-4 md:p-6 lg:p-8`; card padding `p-6`; form spacing `space-y-4`; consistent gap-4 grids |
| Radius | cards `rounded-2xl`, controls `rounded-xl`, pills/avatars `rounded-full` |
| Elevation | `shadow-sm`/`shadow-md`/`shadow-lg`; card elevation `card-elevated` with subtle blur; primary-shadow for emphasis buttons |
| Touch targets | `min-h-[44px] min-w-[44px]` for interactive controls on touch |

### 4.3 Component Inventory (shadcn/ui + Base UI)

Present in `src/components/ui/`: `alert`, `alert-dialog`, `avatar`, `badge`, `button`, `calendar`, `card`, `data-table`, `date-picker`, `detail-sheet-skeleton`, `dialog`, `dropdown-menu`, `empty-state`, `error-boundary`, `export-csv`, `field`, `form`, `input`, `label`, `loading`, `math-renderer`, `multi-select`, `popover`, `progress`, `school-type-tabs`, `searchable-select`, `select` (Base UI), `separator`, `sheet`, `sonner`, `stat-card`, `switch`, `table`, `tabs`, `textarea`, `time-picker`, `toggle`.

Standards:

- Prefer the shared primitives; do not hand-roll new interactive components without a documented reason.
- `data-table` supports sorting, pagination, and CSV export; large datasets must eventually be virtualized (audit P-2) — new tables over ~500 rows should virtualize from day one.
- Loading: use skeletons for primary content (`detail-sheet-skeleton`, card skeletons) and inline spinners only for secondary states (audit M-13, mobile M4/M16 equivalents).
- Empty states: use `empty-state` with title + description + action instead of blank panels.

### 4.4 Form Standards

- **Stack**: `react-hook-form` + `zodResolver`; shared Zod builders in `src/i18n/zod.ts` (`zStr`, `zEmail`, `zPassword`, `zPhone`, `zNum`, …) so validation messages are localized via `validation.*` keys.
- **Multi-step wizards**: step state held in the form value object under a reserved `__step` key; strip `__step` before submission (audit Q-4).
- **Selects (Rule F1)**: Base UI Select — entity options use **entity names as `SelectItem` values**; resolve the current entity ID back to its name for the `value` prop; resolve the selected name back to an ID in `onValueChange`; show a loading placeholder until options arrive (see 4.8 for the canonical snippet).
- **Searchable selects**: `searchable-select` wrapper (currently `react-select`-based) for long option lists; a Base UI/`cmdk` replacement is recommended for bundle and deprecation reasons (audit M-17, B-3).
- **File upload**: client-side MIME + size validation (`validateAvatarFile`: JPEG/PNG/WebP, 5 MB), `disabled` while uploading (audit H-6/H-7).
- **Mutation feedback**: submit buttons bind `disabled` to `isPending`/`isSaving` (audit H-11); success/failure surfaced via Sonner toast.

### 4.5 Data Display Standards

- Tables: zebra-free, sticky headers on scroll, right-aligned numeric columns, status via `badge` (semantic colors), row actions via `dropdown-menu` (...).
- Monetary amounts: `formatCurrency` (`src/lib/utils.ts:63`) — NGN with Naira symbol by default (**Rule F5**), safe rounding to 2 decimals (audit M-1).
- Dates: consistent `dayjs`-based formatting; localization note (audit L-7) — prefer locale-aware output (`en-GB`/`fr`) over hardcoded `en-US` where the locale is `fr`.
- Detail views: right-hand `Sheet` (`w-full`, `sm:max-w-*`) with `aria-labelledby` tied to the sheet title (audit M-5/R-1).

### 4.6 Feedback, Loading, Error, Empty States

| State | Standard |
|-------|----------|
| Success/failure | Sonner toast; `<Toaster richColors closeButton />` lives once in `__root.tsx` (Rule F4) — never duplicate in child routes |
| In-flight mutation | button `disabled` + spinner, inline field errors |
| Route-level errors | `ErrorBoundary` at root renders friendly fallback with retry (audit C-5) |
| Empty lists | `empty-state` with actionable CTA |
| 404 | root `notFoundComponent` |
| Network timeouts | API client aborts after 30 s; transient failures retried 2x with backoff (audit C-6/H-13) |

### 4.7 Accessibility Standards (WCAG 2.2 AA)

- Skip-to-content link at the top of the dashboard layout.
- Visible `:focus-visible` rings on all interactive elements (`focus-visible:ring-2 ring-primary`); no outline removal without replacement.
- Keyboard: sidebar groups toggle with Enter/Space; dropdown menus navigable; command palette fully keyboard-operable.
- Forms: every `FormControl` wires `id`/`htmlFor`; selects associated with labels (audit A-1).
- Dialog/Sheet semantics: `DialogTitle` (visible or sr-only) + `aria-describedby`; focus trapped by shadcn primitives.
- Images: meaningful `alt` (e.g., `"{name}'s avatar"`), lazy-load non-critical images.
- Motion: honor `prefers-reduced-motion` (global reset per audit A-7).
- Color contrast: AA minimums; do not use raw primary for body text (audit A-4).

### 4.8 Codified Frontend Hard Rules (AGENTS.md F1–F5)

**F1 — Entity-name Select pattern (Base UI).**

```tsx
// Correct — entity names as SelectItem values
const currentName = options.find((o) => o.id === watch("field_id"))?.name ?? "";
<Select value={currentName} onValueChange={(name) => {
    const opt = options.find((o) => o.name === name);
    if (opt) setValue("field_id", opt.id, { shouldValidate: true });
}}>
  <SelectContent>
    {options.map((o) => (
      <SelectItem key={o.id} value={o.name}>{o.name}</SelectItem>
    ))}
  </SelectContent>
</Select>

// WRONG — raw IDs render in the trigger
<Select value={String(watch("field_id"))}>
  <SelectItem value={String(o.id)}>{o.name}</SelectItem>
</Select>
```

Applies to every entity select: subjects, levels/classes, teachers, sessions, assessments, guardians.

**F2 — Yarn 4 only.** Never `npm install`/`npm run build`; dependency changes go through the Yarn lockfile.

**F3 — Vite + TanStack Router, not Next.js.** No App Router/page.tsx/server components; routes live in `src/routes/`; env vars via `import.meta.env.VITE_*`.

**F4 — Sonner `<Toaster />` in the root layout** (`__root.tsx`), so toasts survive navigation and drawer close.

**F5 — Default currency NGN (₦).** All monetary displays use the Naira symbol on the frontend; NGN is the backend reference currency unless a field is explicitly documented otherwise.

### 4.9 Internationalization (i18n)

- **Stack**: `react-i18next` + `i18next-browser-languagedetector`; languages `en` (fallback) and `fr`.
- **Files**: `src/i18n/i18n.ts` (init + detector), `src/i18n/zod.ts` (localized validation builders), `src/locales/{en,fr}/translation.json`.
- **Key organization**: module-scoped namespaces — `academic_calendar.*`, `academics.*`, `admissions.*`, `nav.*`, `common.*`, `auth.*`, `roles.*`, `layout.*`, `validation.*`.
- **Usage rule**: every user-facing string uses `t("key", { defaultValue })`; English defaults are provided inline for missing keys; new screens must add keys to both locale files.
- **Detection order**: `localStorage` (`academio-locale`) → `navigator` → `htmlTag`; the `LanguageToggle` in every shell writes the localStorage key.
- **RTL**: not currently supported; treat as out of scope unless a future locale requires it.

### 4.10 Performance Standards

| Metric/rule | Standard |
|-------------|----------|
| Total JS budget | warn at ~800 kB gzip, block at ~1 MB gzip (audit B-4) |
| Route bundles | rely on TanStack Router auto code-splitting; lazy-load heavy components (`React.lazy` + `Suspense` — audit H-8) |
| Charts | keep recharts behind the analytics routes (largest chunk today, ~350 kB) — do not import into dashboard bundles (audit B-2) |
| Tables | virtualize above ~500 rows (audit P-2) |
| Search | debounce inputs (`useDebounce`); consider `useDeferredValue` for keystroke-heavy lists (audit M-7/P-1) |
| API | 30 s timeout, 2 retries with backoff for transient network errors; TanStack Query for cached data with sensible staleTime |
| Assets | lazy-load images, convert to WebP where practical, avoid duplicate font families (audit P-3/P-4) |

### 4.11 Naming and File Conventions

| Type | Convention | Example |
|------|------------|---------|
| Route files | `kebab-case`, dot for path nesting | `teacher.results.master-sheet.tsx` |
| Layout files | `_prefix.tsx` | `_dashboard.tsx` |
| Components | `PascalCase` | `StudentProfileCard`, `UserDropdown` |
| Utilities/stores/hooks | `camelCase`, `use-` for hooks | `auth-store.ts`, `useDebounce.ts` |
| i18n keys | `snake_case`, module prefix | `academics.assessments_total_error` |
| Feature components | colocate under `components/<feature>/` | `components/admissions/`, `components/timetable/` |

### 4.12 Mobile (Flutter) Standards Summary

- Material 3, `AppTheme.light` defined once in `config/theme.dart`; Inter font; seed `#4F46E5`; 20 px horizontal padding, 12–16 px card gap, 24 px section gap.
- Loading: `ShimmerStatCards`/`ShimmerList` for primary content (M4/M16); inline spinners only for pagination.
- Networking: all requests through `services/api_client.dart` (M1); tokens in `flutter_secure_storage` (M10).
- State: Provider; screens minimal-state (M2); every provider disposes its `ApiClient` (M14).
- Errors: no empty `catch`; every failure either recovers, shows a user-visible message, logs, or rethrows (M12/M18).
- Testing: every screen has a widget test covering render/loading/error/empty (M15).

---

## 5. Cross-References

| Topic | Where specified |
|-------|-----------------|
| Personas & functional requirements per module | FSD Part 1 (`01-PRODUCT.md`) |
| Functional + non-functional requirements, user stories, journeys, acceptance criteria | FSD Part 2 (`02-REQUIREMENTS.md`) |
| Data model, schema-per-tenant design, REST API catalog | FSD Part 4 (`04-DATA-API.md`), `docs/architecture/4-API-SPECIFICATIONS.md` |
| Backend hard rules (B1–B13), tenant schema rule, audit logging | `AGENTS.md` |
| Design system tokens, component recipes | `frontend/DESIGN_SYSTEM.md` |
| Frontend stack, project structure, route conventions | `frontend/DESIGN_PATTERNS.md` |
| Security, auth flow, RBAC, impersonation | `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` |
| Workflow engine (result approval, admission approval) | `docs/WORKFLOW-IMPLEMENTATION.md` |
| Audit findings driving UI standards | `docs/audits/FRONTEND-ENTERPRISE-AUDIT.md` |
| Mobile flavor architecture and rules | `mobile/AGENTS.md`, `docs/plans/FLUTTER-MOBILE.md` |
| Testing & QA strategy | FSD Part 6 (`06-ENGINEERING.md`, section 6), `frontend/DESIGN_PATTERNS.md` |

> **Naming note.** Sibling FSD parts refer to parts 2–5 under slightly different working titles
> (System Architecture, Data Model, API Specification, Functional Modules). The file names in
> the Document Map (Section 0) and this table are authoritative: `01-PRODUCT.md`,
> `02-REQUIREMENTS.md`, `03-UX-DESIGN.md`, `04-DATA-API.md`, `05-PLATFORM.md`,
> `06-ENGINEERING.md`.

---

*End of FSD Part 3 — UX Design. Wireframes, IA, navigation, and component standards are grounded in the implemented `frontend/src/routes/` tree and `frontend/src/components/layout/` as of 2026-07-31. Screens marked Planned are design targets, not shipped UI.*
