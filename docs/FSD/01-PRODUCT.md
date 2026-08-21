# Academio — Functional Specification Document

## Part 1: Product Specification (01-PRODUCT)

| | |
|---|---|
| **Document** | FSD Part 1 — Product Specification |
| **Status** | Draft v1.0 for review |
| **Version** | 1.0 |
| **Date** | 31 July 2026 |
| **Product** | Academio — Multi-Tenant School Management & Education ERP |
| **Audience** | Product management, engineering, design, QA, executive stakeholders |
| **Applies to** | Web application (React 19 + Vite), API platform (Go/Gin/GORM), mobile application (Flutter, in progress) |

> **How to read this document.** This is Part 1 of the Academio Functional Specification Document (FSD). It defines *what* Academio is, *who* it serves, *what* is in scope today, *where* the product is going, and *what* could threaten delivery. It is intentionally product-first: detailed functional requirements, UX design, data/API contracts, platform architecture, and engineering standards are specified in the sibling parts and are cross-referenced throughout.

### FSD Document Suite

| Part | File | Content |
|---|---|---|
| 0 | `00-FSD-INDEX.md` | Table of contents, document map, revision history |
| **1** | **`01-PRODUCT.md`** | **Executive summary, vision, goals, personas, MVP scope, roadmap, risks (this document)** |
| 2 | `02-REQUIREMENTS.md` | Detailed functional and non-functional requirements per module |
| 3 | `03-UX-DESIGN.md` | UX principles, information architecture, persona journeys, interface design |
| 4 | `04-DATA-API.md` | Data model, multi-tenant schema design, REST API catalog, events |
| 5 | `05-PLATFORM.md` | Audit logging, notifications, search, global settings, tenant architecture, event-driven architecture, background jobs, caching strategy, file storage |
| 6 | `06-ENGINEERING.md` | Engineering standards, conventions, quality gates, testing strategy |

---

## 1. Executive Summary

### 1.1 Product Overview

Academio is an enterprise-grade, cloud-native, multi-tenant School Management and Education ERP platform developed by Playbit Technologies. It is designed as a single operating system for educational institutions — covering nursery schools, primary schools, secondary schools, colleges, universities, and training institutes — and it manages the complete student lifecycle from prospect to applicant, student, graduate, and alumni.

Academio is architected as a **modular monolith** with a clean layered structure:

- **Backend**: Go (Gin) API on port `:8080`, GORM + pgx v5 against PostgreSQL, Redis 7 for caching, rate limiting, and the Asynq background-job queue. JWT authentication with refresh-token rotation, CSRF protection, and optional TOTP 2FA.
- **Frontend**: React 19 single-page application built with Vite, TanStack Router (type-safe, file-based routing), TanStack Query, Zustand, shadcn/ui and Base UI, Tailwind CSS v4, React Hook Form + Zod validation, and i18next localization.
- **Data**: Single PostgreSQL instance with **schema-per-tenant** isolation — each school gets its own `school_{id}` schema applied automatically via the GORM `SchemaTablePrefix` plugin. Shared (platform) data such as `User`, `School`, and `Role` lives in the `public` schema.
- **Mobile**: A Flutter application is under active development per the 23-phase `ACADEMIO_IMPLEMENTATION_PLAN.md`; the mobile client consumes the same `/api/v2` REST surface as the web application.

The platform currently ships **49 backend modules** (verified directory inventory — see Appendix A) and a frontend route tree of **100+ route files** covering public marketing/admissions pages, a school-onboarding wizard, a super-admin console, and 60+ authenticated dashboard destinations across role-specific surfaces (admin, teacher, student, parent).

### 1.2 Current State (Verified)

| Dimension | Verified State |
|---|---|
| Backend modules | 49 module directories under `backend/internal/modules/`, from `academic` to `user` |
| Frontend routes | 100+ route files; 60+ dashboard destinations plus public, onboarding, and super-admin areas |
| Core academics | Sessions, curriculum, subjects, levels, assessments, score entry, result processing, report cards, timetables, attendance — shipped |
| Assessment & learning | CBA engine (question bank, papers, exam player, results) and LMS (courses, assignments, discussions) — shipped |
| Admissions | Intakes, application forms (configurable), screening, offers, public apply and status tracking — shipped |
| Finance | Billing, payments, fee structures, financial reports — shipped |
| People & operations | Library, hostel, transport, inventory, HR, discipline, student health, alumni, career, forum, conferences, pastoral — shipped |
| Communication | Broadcast/campaigns/templates/delivery, messages, notifications — shipped |
| Analytics | Dashboard, analytics (academic/enrollment/revenue), reports, report builder, report cards — shipped |
| AI | Partially shipped — `ai` module exposes chat, search, and agent-list endpoints; agent framework exists; the full AI layer (RAG, proctoring AI, essay grading, risk prediction) is roadmap |
| Compliance & accreditation | Not shipped — specified in `docs/COMPLIANCE-ACCREDITATION.md` as a future module |
| Education Blueprint Engine | Not shipped — specified in `docs/FUTURE-DIRECTION.md` as the global-configurability evolution |
| Mobile apps | Flutter app in progress per the 23-phase implementation plan |

> **Source-doc inconsistency resolved.** `docs/PROJECT.md` states "39 modules total"; the verified directory inventory of `backend/internal/modules/` contains **49 module directories**. This FSD uses the verified count of 49.

### 1.3 Target State

Academio's target state is an **AI-native, configurable, globally deployable Education Operating System**:

1. **AI-native, not AI-added**: every module has an AI layer (assistant, summarization, prediction, generation) embedded in workflows rather than bolted on. The architecture for this is defined in `docs/architecture/5-AI-ARCHITECTURE.md`.
2. **Configuration-driven education domain**: an Education Blueprint Engine replaces hardcoded assumptions (Session→Term, Class, Subject) with per-institution templates supporting term-based, semester-based, quarter-based, university, polytechnic, vocational, and international (Cambridge, IB, American K-12) calendars without application-code changes. See `docs/FUTURE-DIRECTION.md`.
3. **Complete lifecycle coverage**: prospect → applicant → admission → student → academic progress → graduate → alumni → lifelong engagement.
4. **Scalable to 1M+ students**: schema-per-tenant isolation, Redis caching layers, horizontal scaling, and a documented evolution path from single PostgreSQL to read replicas, sharding, and multi-region deployment.
5. **Africa-first, global-ready**: compliance tooling for Nigerian regulatory bodies (Lagos State Ministry of Education, TRCN, WAEC, NECO, JAMB) as a strategic differentiator, with an expansion roadmap to the rest of Africa and then global markets.

### 1.4 Scope of This Document

This part defines the **product layer** of the FSD:

- The vision, strategic pillars, and market positioning (Section 2).
- Product goals and measurable success metrics (Section 3).
- Primary and secondary personas grounded in the Nigerian education domain and the verified module inventory (Section 4).
- MVP scope with a strict **Implemented vs Planned** distinction, verified against the codebase (Section 5).
- The future roadmap across product, platform, AI, and market expansion (Section 6).
- A risk register and mitigation strategy (Section 7).

Functional detail, UX, data contracts, platform, and engineering standards are deferred to the sibling FSD parts:

- **`02-REQUIREMENTS.md`** — detailed functional requirements per module and non-functional requirements.
- **`03-UX-DESIGN.md`** — UX principles, navigation architecture, persona journeys, accessibility.
- **`04-DATA-API.md`** — entity model, tenancy, API catalog, pagination, events.
- **`05-PLATFORM.md`** — infrastructure, security, observability, deployment.
- **`06-ENGINEERING.md`** — conventions, quality gates, testing, and contribution workflow.

---

## 2. Vision

### 2.1 Vision Statement

> **Academio is the operating system for education** — a single platform that powers the complete lifecycle of every learner and every institution, from the first enquiry to lifelong alumni engagement, with AI embedded natively in every workflow.

The product vision is to evolve Academio from a traditional School ERP into a comprehensive **AI-Powered Student Lifecycle & School Operating System** that is the single source of truth for educational institutions in Nigeria first, across Africa next, and worldwide thereafter. This mirrors the strategic direction documented in `docs/architecture/1-VISION-AND-STRATEGY.md`, re-branded and extended for the Academio product line.

### 2.2 The Complete Student Lifecycle

```
PROSPECT ──► APPLICANT ──► ADMISSION ──► STUDENT ──► ACADEMIC PROGRESS ──► GRADUATE ──► ALUMNI
                                                                                          │
                                                                                          ▼
                                                                                   LIFELONG ENGAGEMENT
                                                                                (Mentorship, Fundraising,
                                                                                 Career Services, Events)
```

Academio unifies data across the lifecycle so that a single student record follows the learner from prospect to alumni. Today the platform implements the middle of this lifecycle deeply (admission → student → academic progress → graduate/reporting); the alumni and lifelong-engagement stages are partially implemented (alumni and career modules exist) and the prospect/apply stages are implemented via the public admissions portal.

### 2.3 Target Markets

| Segment | Description | Scale (students) | MVP Priority |
|---|---|---|---|
| K-12 Schools (Nursery, Primary, Secondary) | The Nigerian private-school market; Lagos State first | 100 – 5,000 | **Primary** — deepest existing coverage |
| Colleges | Tertiary and diploma institutions | 500 – 20,000 | Secondary |
| Universities | Higher education; faculty/department/course structures | 5,000 – 100,000+ | Secondary (Blueprint Engine enabler) |
| Training Institutes | Vocational and professional training | 100 – 10,000 | Secondary |
| Online Academies | Digital-first education | 1,000 – 1M+ | Tertiary |
| Multi-Campus Groups | Chains and franchises | 5 – 500+ campuses | Tertiary (Enterprise tier) |

### 2.4 Brand Positioning

- **Tagline**: "The Operating System for Education."
- **Positioning**: premium SaaS — the Salesforce of Education, with a distinct Africa-first advantage.
- **Competitive differentiators**:
  1. AI-native architecture (AI is embedded in modules, not bolted on).
  2. Complete lifecycle coverage from prospect to alumni.
  3. Multi-tenant SaaS with schema-per-tenant isolation and single-instance scalability.
  4. API-first and event-driven, enabling third-party integrations and mobile clients.
  5. Compliance and accreditation tooling for African regulatory environments that global competitors do not serve (see `docs/COMPLIANCE-ACCREDITATION.md`).
  6. Education Blueprint Engine for configuration-driven support of any institutional model worldwide.

### 2.5 Strategic Pillars

The vision rests on five strategic pillars, inherited from the architecture strategy and adapted to Academio:

1. **AI-First, Not AI-Added.** Every module has an AI layer. AI is not a separate feature; it is embedded into every workflow. The current AI module and agent framework are the first increment of this pillar.
2. **Student Lifecycle Unification.** Break down silos between admissions, academics, finance, and alumni. A single student record follows the learner from prospect to alumni.
3. **API-First Ecosystem.** Every feature is an API. This enables third-party integrations, custom frontends, and the mobile application. All endpoints live under `/api/v2` with additive-only evolution.
4. **Real-Time by Default.** Notifications, dashboards, analytics, and communication operate in real time via WebSockets, SSE, and event streaming.
5. **Cloud-Native Multi-Tenancy.** True SaaS architecture with per-tenant schema isolation, shared-infrastructure efficiency, and data-sovereignty controls.

### 2.6 Competitive Landscape

| Capability | Academio | PowerSchool | Infinite Campus | Fedena | Alma SIS |
|---|---|---|---|---|---|
| AI Assistant | Native (partial, roadmap complete) | Add-on | Add-on | No | No |
| Student Lifecycle | Complete (implemented/planned) | Partial | Partial | Partial | Partial |
| CBA (Computer-Based Assessment) | Built-in (implemented) | No | No | No | No |
| LMS | Built-in (implemented) | Acquired | No | No | No |
| Alumni Management | Built-in (implemented, extensible) | No | No | No | No |
| Multi-Tenant SaaS | Native (schema-per-tenant) | Yes | Yes | No | No |
| Open API | First-class (`/api/v2`) | Yes | Yes | Yes | Yes |
| Mobile Apps | In progress (Flutter) | Partial | Yes | Yes | Yes |
| WhatsApp / SMS | Native (communication module) | No | No | No | No |
| African Market Readiness | Native (Lagos-first compliance) | No | No | Partial | No |

### 2.7 Ten-Year Aspiration

Within ten years, Academio aims to:

- Power institutions across the full education spectrum — nursery to university — on every inhabited continent.
- Operate at 1M+ active student records with multi-region deployment and data-residency controls.
- Offer an AI layer that includes adaptive learning paths, multimodal tutoring, and institutional predictive analytics.
- Provide a marketplace where schools exchange curriculum, assessments, and verified credentials.
- Serve as a trusted credential-verification network for employers and universities (blockchain-verifiable credentials are on the Phase 10+ roadmap).

---

## 3. Product Goals

### 3.1 Strategic Goals

| # | Goal | Description | Primary Owner | Reference |
|---|---|---|---|---|
| G1 | **Complete the transactional core** | Keep the implemented academic, financial, and people-management modules production-grade: attendance, grading, results, report cards, billing, payments, HR, operations | Engineering | `06-ENGINEERING.md` |
| G2 | **Deliver AI assistance end to end** | Ship the AI Assistant Suite (student, teacher, parent) built on the existing agent framework, with RAG and natural-language search; make AI a paid differentiator, not a free cost center | Product, AI Eng | `02-REQUIREMENTS.md` (AI section), `docs/architecture/5-AI-ARCHITECTURE.md` |
| G3 | **Achieve configuration-driven education** | Implement the Education Blueprint Engine so institutions of any type or country can be onboarded without code changes | Architecture | `05-PLATFORM.md`, `docs/FUTURE-DIRECTION.md` |
| G4 | **Establish compliance leadership in Nigeria** | Deliver the Compliance & Accreditation module (Lagos State registration, TRCN tracking, inspection readiness) as a core differentiator | Product | `02-REQUIREMENTS.md`, `docs/COMPLIANCE-ACCREDITATION.md` |
| G5 | **Ship mobile experiences** | Complete the Flutter mobile app for parents, students, teachers, and admins against the 23-phase implementation plan | Engineering | `06-ENGINEERING.md`, `ACADEMIO_IMPLEMENTATION_PLAN.md` |
| G6 | **Grow from schools to institutions** | Expand persona support beyond K-12 (registrar, bursar, counselor, nurse, transport/hostel managers) and eventually to higher-education roles | Product | Section 4 (Personas) |
| G7 | **Scale to 1M+ students** | Keep the platform horizontally scalable: modular monolith → service evolution, Redis caching, read replicas, sharding path | Platform | `05-PLATFORM.md` |
| G8 | **Monetize responsibly** | Execute the tiered pricing ("Free forever, but verified"), verified-school program, and premium add-ons without enabling abuse | Product, Ops | `docs/ABUSE-PREVENTION.md` |

### 3.2 Operational Goals

1. **Onboarding time to value under 7 days.** A verified school should be provisioning a configured tenant and entering real data within one week of sign-up (current synchronous provisioning flow already creates a schema, runs migrations, and seeds curriculum in seconds).
2. **Implementation time under 30 days for enterprise customers**, including data migration, configuration, and training.
3. **Zero-downtime additive evolution.** No removal of existing endpoints; all changes to `/api/v2` are additive.
4. **Tenant isolation integrity.** No cross-tenant data leakage; enforced by schema-per-tenant resolution and verified by the audit and security checklists (`docs/architecture/10-AUDIT-CHECKLIST.md`).
5. **Institutional trust.** NPS 50+; < 3% monthly churn; < 5 critical bugs per month; 99.9%+ uptime.

### 3.3 Measurable Success Metrics (KPIs)

#### 3.3.1 Product KPIs

| KPI | Target |
|---|---|
| Student weekly active usage | 80%+ login at least once per week |
| Teacher weekly usage | 95%+ use the system for attendance/grades weekly |
| Parent weekly engagement | 60%+ check child progress weekly |
| Admin daily usage | 100% daily active |
| Attendance marked via system | 95%+ of sessions |
| Grades entered via system | 90%+ of assessments |
| Fees collected via system | 70%+ of collections |
| AI Assistant monthly usage | 50%+ of students (post-AI-launch) |
| System uptime | 99.9%+ |
| API p95 latency | < 500 ms |
| AI response time | < 3 s |
| Critical bug rate | < 5 per month |

#### 3.3.2 Business KPIs

| KPI | Target |
|---|---|
| MRR growth | 15%+ month-over-month (Year 1) |
| Customer acquisition cost | < $200 |
| Lifetime value | > $5,000 |
| LTV/CAC | > 25x |
| Monthly churn | < 3% |
| Net revenue retention | > 110% |
| Time to value | < 7 days (sign-up to active use) |
| Enterprise implementation | < 30 days |
| Support resolution | < 4 hrs critical, < 24 hrs normal |

### 3.4 Non-Functional Goals

| Goal | Target | FSD Reference |
|---|---|---|
| Security | Defense-in-depth; JWT rotation; CSRF; Redis rate limiting; tenant isolation | `05-PLATFORM.md` |
| Performance | p95 API < 500 ms; dashboard queries cached | `05-PLATFORM.md`, `06-ENGINEERING.md` |
| Availability | 99.9%+ with graceful degradation of non-critical analytics | `05-PLATFORM.md` |
| Accessibility | WCAG 2.2 AA for all user-facing surfaces | `03-UX-DESIGN.md` |
| Internationalization | i18next-based locales; currency/locale-aware displays (NGN default) | `03-UX-DESIGN.md`, `04-DATA-API.md` |
| Maintainability | Layered module structure (dto/handler/service/repository); `go vet` and `tsc --noEmit` clean | `06-ENGINEERING.md` |

### 3.5 Goal Traceability

The goals above map to detailed requirements as follows:

- G1, G6 → `02-REQUIREMENTS.md` (module-level functional requirements)
- G2 → `02-REQUIREMENTS.md` (AI requirements) and `04-DATA-API.md` (AI endpoints)
- G3 → `04-DATA-API.md` (configuration model) and `05-PLATFORM.md` (provisioning)
- G4 → `02-REQUIREMENTS.md` (compliance module) and `04-DATA-API.md`
- G5 → `03-UX-DESIGN.md` (mobile UX) and `06-ENGINEERING.md`
- G7 → `05-PLATFORM.md` (scaling strategy)
- G8 → `05-PLATFORM.md` (feature flags, rate limits)

---

## 4. Personas

### 4.1 Persona Methodology

Personas are derived from two sources:

1. **The education domain** as defined in `docs/NG-EDUCATION-STANDARDS.md` — the Nigerian 1-6-3-3-4 structure (nursery, primary, junior secondary, senior secondary, tertiary) and its actors: proprietors, head teachers, teachers, registrars, bursars, parents, and students.
2. **The verified module and route inventory** — a persona is only claimed as *supported* if the module and dashboard routes exist. Personas marked "planned" map to roadmap modules.

Each persona lists: description, key goals, primary tasks, system touchpoints (verified modules), and current support status.

### 4.2 Primary Personas

#### 4.2.1 Super Admin (Platform Operations)

- **Description**: Academio operations staff responsible for the multi-tenant platform: tenant lifecycle, provisioning, billing, monitoring, abuse prevention, and support.
- **Key goals**: monitor system health; provision and deprovision schools; manage plans and feature flags; enforce the abuse-prevention safeguards from `docs/ABUSE-PREVENTION.md`.
- **System touchpoints (verified)**: `tenant`, `school`, `user`, `audit`, `auth`, `invitation`, `notifications`, `analytics`, `dashboard`; super-admin routes `/super` (school picker and tenant detail).
- **Support status**: Implemented (super-admin console exists); tenant-level billing and plan management partially covered by `tenant`/`school` modules; full billing console is roadmap.

#### 4.2.2 School Admin / Proprietor

- **Description**: School principal, head teacher, or proprietor who owns the institution's configuration and day-to-day operations. In Nigeria this persona also carries regulatory duties (Lagos State Ministry of Education registration, TRCN compliance, WAEC/NECO candidate registration) documented in `docs/NG-EDUCATION-STANDARDS.md` and `docs/COMPLIANCE-ACCREDITATION.md`.
- **Key goals**: configure sessions, curriculum, subjects, levels, and grade items; manage staff and students; publish results and report cards; monitor fee collection; keep the school inspection-ready.
- **System touchpoints (verified)**: `school`, `academic`, `academic-calendar`, `score`, `result`, `reportcard`, `exam`, `grading`, `attendance`, `timetable`, `user`, `rbac`, `bill`, `payment`, `finance`, `hr`, `communication`, `audit`, `settings`, `dashboard`, `analytics`, `reports`.
- **Support status**: Implemented — the richest persona in the product.

#### 4.2.3 Registrar / Admissions Officer

- **Description**: Staff member who manages the admissions pipeline: intakes, application forms, screening, offers, and enrollment. Handles document verification and candidate communication.
- **Key goals**: open intakes; process applications through screening → exam → offer → acceptance; enroll admitted applicants as students; maintain the admission register required by regulators.
- **System touchpoints (verified)**: `admission` (intakes, applications, forms, screening, offers), `user`, `communication`, `media`, `notifications`, `dashboard`.
- **Support status**: Implemented (admin admissions screens and public apply/status flows).

#### 4.2.4 Teacher

- **Description**: Classroom teacher responsible for lesson delivery and assessment. In Nigerian secondary schools, teachers also prepare lesson notes and schemes of work (see `docs/NG-LESSON-NOTE-PLAN-STANDARDS.md`) and enter continuous-assessment and exam scores.
- **Key goals**: mark attendance; enter scores against grade items; prepare lesson notes and lesson plans; set and mark CBA exams and LMS assignments; view and print class results and report cards.
- **System touchpoints (verified)**: `attendance`, `score`, `result`, `lessonplan`, `cba`, `lms`, `exam`, `timetable`, `grading`, `reportcard`, `academic`, `communication`, `notifications`; teacher dashboard routes (`teacher.*`).
- **Support status**: Implemented — dedicated teacher surface with role-based route gating in the dashboard layout.

#### 4.2.5 Student

- **Description**: Enrolled learner (primary through tertiary). Students in the Nigerian system follow the 1-6-3-3-4 progression and sit internal assessments plus external exams (BECE, WASSCE, NECO, UTME) depending on level.
- **Key goals**: view timetable and attendance; view results and report cards; take CBA exams; complete LMS assignments; monitor fee status; interact with the AI academic assistant.
- **System touchpoints (verified)**: `studentportal`, `student` dashboard routes (index, attendance, fees, results, report-cards, timetable), `cba`, `lms`, `result`, `reportcard`, `exam`, `academic-calendar`, `messages`, `notifications`, `ai` (partial), `career`, `alumni`.
- **Support status**: Implemented — dedicated student surface with role-based route gating.

#### 4.2.6 Parent / Guardian

- **Description**: Parent or guardian of one or more enrolled students. Pays school fees, monitors academic progress, attendance, behavior, and communicates with the school. In Nigeria, parents may also act as the applicant for admission on behalf of the child.
- **Key goals**: view all children in one dashboard; check progress, attendance, and fee balances; pay fees; book parent–teacher conferences; receive broadcast messages and AI-generated performance summaries.
- **System touchpoints (verified)**: `parentdashboard` (dashboard, child detail routes), `bill`/`payment` (fee visibility), `attendance`, `result`, `reportcard`, `conference`, `communication`, `messages`, `notifications`, `ai` (partial), public admissions `apply`/`status`.
- **Support status**: Implemented — parent dashboard and child detail routes exist; AI parent summaries are roadmap.

#### 4.2.7 Accountant / Bursar

- **Description**: School finance staff responsible for fee structures, invoicing, payment recording, receivables (debtors), and financial reports. Must keep fee collection at 70%+ through the system per product KPIs.
- **Key goals**: configure fee items and structures; generate bills; record and allocate payments; track outstanding balances; produce financial reports; reconcile with school bank accounts.
- **System touchpoints (verified)**: `bill`, `payment`, `finance`, `reports`, `analytics` (revenue), `user`, `audit`.
- **Support status**: Implemented — bills/payment/finance modules and dashboard routes exist; double-entry accounting depth (journal, chart of accounts, budgets) is roadmap (Phase 17 of the implementation plan).

### 4.3 Secondary Personas

| Persona | Description | Touchpoints | Support Status |
|---|---|---|---|
| **Librarian** | Manages the book catalog, issue/return, overdue tracking | `library` | Implemented |
| **Counselor / Guidance Officer** | Career guidance, pastoral support, wellness, interventions | `career`, `pastoral`, `discipline` | Implemented (AI risk prediction roadmap) |
| **Nurse / School Health Officer** | Student health records, immunizations, sick-bay visits | `health`, `studenthealth` | Implemented |
| **HR Manager** | Staff records, leave, payroll, appraisals | `hr`, `audit` | Implemented (payroll depth roadmap) |
| **Transport Manager** | Routes, vehicles, student assignments, trip tracking | `transport` | Implemented |
| **Hostel Manager** | Hostel and bed assignment, occupancy, billing | `hostel` | Implemented |
| **Alumni** | Former student: profile, events, mentorship, donations, job board | `alumni`, `career`, `forum` | Implemented (fundraising depth roadmap) |
| **Applicant** | Prospective student or parent applying for admission | Public admissions portal | Implemented |
| **System (Automated)** | Scheduled jobs, queue workers (Asynq), AI agents, notification dispatch | `tenant`, `audit`, `notifications`, `ai` | Implemented (agent automation roadmap) |

### 4.4 Persona × Module Access Matrix

The detailed permissions matrix is specified in `03-UX-DESIGN.md` and enforced by RBAC (`06-ENGINEERING.md`). The summary below is grounded in the verified module inventory:

| Capability | Super Admin | School Admin | Registrar | Teacher | Student | Parent | Accountant |
|---|---|---|---|---|---|---|---|
| Tenant & school provisioning | CRUD | R | — | — | — | — | — |
| Student management | R | CRUD | CRUD | R | R | R | R |
| Teacher/staff management | R | CRUD | R | R | — | — | R |
| Academic structure (levels, subjects, curriculum) | R | CRUD | R | R | — | — | — |
| Attendance | R | R | — | CRUD | R | R | — |
| Assessments & CBA | R | CRUD | — | CRUD | Take | R | — |
| Results & report cards | R | CRUD | R | CRUD | R | R | R |
| Fees, billing & payments | R | CRUD | — | — | R | CRUD | CRUD |
| Admissions | R | CRUD | CRUD | Screen | — | Create | — |
| LMS | R | R | — | CRUD | Take | R | — |
| Library / hostel / transport / inventory | R | CRUD | — | R | R | R | — |
| HR & payroll | R | CRUD | — | R | — | — | R |
| Finance & accounting | R | R | — | — | — | — | CRUD |
| Alumni & career | R | R | — | — | CRUD | — | — |
| Communication hub | R | CRUD | Send | Send | Read | Read | Send |
| AI assistant | R | R | R | R | CRUD | CRUD | — |
| Reports & analytics | CRUD | CRUD | R | R | R | R | R |
| Settings & configuration | CRUD | CRUD | R | R | R | R | R |

Legend: C = Create, R = Read, U = Update, D = Delete, — = No access. Exact permissions are subject to RBAC refinement (`docs/architecture/7-USE-CASES.md`).

### 4.5 Persona-Driven Design Principles

1. **Teachers and admins work fast, students and parents read simply.** Entry surfaces (attendance, score entry, CBA) are optimized for keyboard/mouse speed and bulk actions; portal surfaces are optimized for comprehension.
2. **Every persona sees only what their role allows.** Role-based route gating is implemented in the dashboard layout (`_dashboard.tsx`) and must be extended to data-level RBAC (`06-ENGINEERING.md`).
3. **Terminology follows the institution.** A parent in a university should see "semester"; a parent in a Lagos secondary school should see "term". This is the Education Blueprint Engine requirement and drives dynamic navigation and labels (`03-UX-DESIGN.md`).
4. **Regulatory literacy is a feature.** Nigerian users expect WAEC/NECO-grade lettering (A1–F9), BECE grading, and JAMB subject combinations — the grading engine must support these natively (`02-REQUIREMENTS.md`).

---

## 5. MVP Scope

### 5.1 Scope Definition and Verification Method

The MVP scope distinguishes **Implemented** (verified present in the codebase at the time of writing), **Partially Implemented** (exists but with known gaps), and **Planned** (specified in source documents but not yet shipped).

Verification was performed against:

1. **Backend module inventory**: directory listing of `backend/internal/modules/` — 49 modules; a module counts as implemented when it contains the layered files (`dto.go`, `handler.go`, `service.go`, `repository.go`) per the project structure convention.
2. **Frontend route inventory**: directory listing of `frontend/src/routes/` — 100+ route files across `_public`, `_onboarding`, `_super`, and `_dashboard` areas.
3. **Implementation plan gaps**: `ACADEMIO_IMPLEMENTATION_PLAN.md` explicitly identifies open backend gaps (RBAC middleware, AI DI wiring, CSRF token handling in the mobile client, API client hardening) and the 23-phase mobile roadmap.

> Scope statements in this section are **current-state claims only**. They do not guarantee feature completeness inside a module; module-level acceptance criteria are defined in `02-REQUIREMENTS.md`.

### 5.2 Implemented — Core Platform

| Domain | Module(s) | Verified Evidence | Notes |
|---|---|---|---|
| Identity & access | `auth`, `user`, `invitation`, `rbac` | Login/register/forgot-password/reset-password/confirm-email routes; JWT + refresh rotation; TOTP option | `rbac` roles/permissions CRUD present; route-level enforcement gap noted in 5.3 |
| Tenant management | `tenant`, `school` | Synchronous provisioning; `school_{id}` schema; frontend polling until `schema_name` non-empty | Super-admin school picker routes |
| Audit | `audit` | Audit log routes (`audit-logs.tsx`); mutation audit logging middleware | |

### 5.3 Implemented — Academic Domain

| Domain | Module(s) | Verified Evidence |
|---|---|---|
| Academic structure | `academic`, `academic-calendar` | Academics route; academic calendar with calendar/events/periods/blueprint editing routes |
| Curriculum & subjects | `academic`, `grading` | Curriculum, subjects, levels, grade items configuration (school setup) |
| Attendance | `attendance` | Attendance routes (admin + teacher surfaces) |
| Examinations | `exam`, `external_exam` | Exam schedule and external exam (WAEC/NECO) management routes |
| Scoring & results | `score`, `result` | Results routes incl. master-sheet; promotion route |
| Report cards | `reportcard` | Report card routes incl. batch generation and per-card detail |
| Timetables | `timetable` | Timetable routes (admin + teacher + student views) |
| Lesson planning | `lessonplan` | Lesson plans, lesson notes, schemes of work routes |
| CBA engine | `cba` | Question bank, paper composer, exam player (`cba.exams.$examId.take`), results |
| LMS | `lms` | Courses, assignments, discussions routes |

### 5.4 Implemented — People, Operations, and Finance

| Domain | Module(s) | Verified Evidence |
|---|---|---|
| Admissions | `admission` | Intakes, applications, configurable forms, screening, offers; public apply/status routes |
| Alumni | `alumni` | Alumni directory and insights routes |
| Career | `career` | Career route |
| HR | `hr` | HR route (staff, leave, payroll screens) |
| Student health | `health`, `studenthealth` | Student health route (records, blood group, immunizations) |
| Discipline | `discipline` | Discipline route (incidents, detentions, suspensions) |
| Pastoral care | `pastoral` | Pastoral route (wellness surveys, counseling) |
| Library | `library` | Library route |
| Hostel | `hostel` | Hostel route |
| Transport | `transport` | Transport route |
| Inventory | `inventory` | Inventory route |
| Billing & payments | `bill`, `payment` | Bills and payment routes; NGN (₦) default currency |
| Finance | `finance` | Finance route (fee structures, debtors) |
| Communication | `communication`, `messages`, `notifications`, `conference`, `forum`, `media`, `multimedia` | Broadcast, campaigns, templates, delivery, compose; messages; notifications; conferences; forum; media |
| Analytics & reporting | `analytics`, `reports`, `reportbuilder`, `dashboard` | Analytics (academic/enrollment/revenue), reports + report builder, dashboard |

### 5.5 Partially Implemented

| Feature | What Exists | Known Gap | Evidence |
|---|---|---|---|
| **AI Assistant Suite** | `ai` module with chat, search, and agent-list endpoints; agent framework, conversation store, and natural-language search engine under `internal/ai`; `ai-assistant.tsx` dashboard route | AI handler DI wiring flagged as incomplete; full AI layer (RAG on pgvector, AI proctoring, essay grading, risk prediction, parent summaries) is roadmap | `ACADEMIO_IMPLEMENTATION_PLAN.md` Phase 22.2 |
| **RBAC enforcement** | `rbac` module and role-based frontend route gating | Route/action-level permission middleware on sensitive backend endpoints flagged as incomplete | `ACADEMIO_IMPLEMENTATION_PLAN.md` Phase 22.1 |
| **Proctoring** | `proctoring` module and dashboard route | AI-driven proctoring (face detection, event analysis) is roadmap; basic event review is the current scope | Module inventory; `docs/architecture/5-AI-ARCHITECTURE.md` |
| **Finance depth** | `bill`, `payment`, `finance` modules | Double-entry accounting (chart of accounts, journal, budgets, expenses, vendors) is roadmap | `ACADEMIO_IMPLEMENTATION_PLAN.md` Phase 17 |
| **Payroll depth** | `hr` module | Batch payslip generation, payroll periods, appraisals, recruitment workflows are roadmap | `ACADEMIO_IMPLEMENTATION_PLAN.md` Phase 18 |
| **Mobile app** | Flutter `mobile/` codebase exists; parent portal, notifications, messages, library, hostel, transport, inventory, discipline, health, exam, CBA, LMS, admissions, finance, HR, alumni screens planned | 23-phase plan in progress; hardcoded IDs and provider fixes are open (Phase 1) | `ACADEMIO_IMPLEMENTATION_PLAN.md` |

### 5.6 Planned (Not Yet Shipped)

| Feature | Description | Source |
|---|---|---|
| **Compliance & Accreditation module** | Document repository with expiry tracking, compliance checklists, staff credential management (TRCN, NYSC), facility/asset audits, inspection readiness reports | `docs/COMPLIANCE-ACCREDITATION.md` |
| **Education Blueprint Engine** | Institution-type and country templates (Nigeria Basic/Secondary/Polytechnic/University, Cambridge, British, American K-12, IB, Montessori, Custom); configurable period types, curricula, grading templates, report templates, workflows | `docs/FUTURE-DIRECTION.md` |
| **Full AI layer** | RAG on pgvector (Qdrant retired PGV-06), AI Teacher/Parent/Student assistants, NL search, AI-assisted marking, risk prediction, enrollment forecasting, executive summaries | `docs/architecture/5-AI-ARCHITECTURE.md` |
| **Advanced analytics / BI** | Executive dashboards, forecasting models, custom report builder enhancements, AI executive summaries | `docs/architecture/1-VISION-AND-STRATEGY.md` (Phase 8) |
| **White-label and mobile apps** | Branded school mobile apps, push notifications at scale | `docs/architecture/8-FUTURE-EXPANSION.md` |
| **Payments & communications partners** | Paystack/Flutterwave/Stripe, Twilio/AfricasTalking/Termii, WhatsApp Business | `docs/architecture/8-FUTURE-EXPANSION.md` |
| **Enterprise workflow engine** | Configurable approval workflows (score entry → review → approval → publish) | `docs/WORKFLOW-IMPLEMENTATION.md` |

### 5.7 Explicitly Out of Scope for MVP

The following are **not** part of the MVP and are deferred to the roadmap (Section 6):

1. Blockchain-verifiable credentials and crypto/stablecoin fee payments.
2. Global school marketplace (curriculum/assessment commerce).
3. Virtual classrooms and metaverse learning spaces.
4. Biometric authentication (WebAuthn/FIDO2 attendance, facial proctoring) — basic credential-based proctoring review only.
5. IoT/smart-campus integrations (RFID attendance, environmental monitoring).
6. International student management (SEVIS/CAS-style compliance).
7. Gamification (points, badges, leaderboards).
8. Multi-region deployment and data-residency controls (post-scale architecture).
9. GraphQL federation for mobile clients (REST `/api/v2` remains the single contract).

### 5.8 MVP Scope by Persona

| Persona | In MVP Scope (verified) | Not in MVP |
|---|---|---|
| Super Admin | Tenant provisioning, school lifecycle, audit, invitations, usage monitoring | Full billing console, revenue analytics, abuse auto-enforcement |
| School Admin | All academic, people, finance, operations, communication configuration | Compliance dashboards, blueprint engine, AI executive summaries |
| Registrar | Intakes, applications, forms, screening, offers, enrollment | AI applicant scoring, enrollment forecasting |
| Teacher | Attendance, scores, lesson plans/notes, CBA, LMS, results, report cards | AI lesson-plan generation, AI-assisted marking |
| Student | Timetable, attendance, results, report cards, CBA, LMS, fees, AI chat (partial) | Adaptive learning paths, AI tutoring with RAG |
| Parent | Child dashboard, progress, attendance, fees, conferences, messages | AI performance summaries |
| Accountant | Bills, payments, fee structures, debtors, financial reports | Double-entry accounting, budgets, payroll |
| Alumni | Profile, directory, career, forum | Fundraising, mentorship platforms, verification services |

### 5.9 Scope Governance

- Scope changes require an Architecture Decision Record (ADR) and must be traceable to a goal in Section 3.
- Any new backend module must follow the layered structure (`dto.go`, `handler.go`, `service.go`, `repository.go`) and be registered in the router with Swagger annotations (`06-ENGINEERING.md`).
- Any new frontend route must be added under `frontend/src/routes/` using TanStack Router file-based routing and be covered by role-based route gating (`03-UX-DESIGN.md`).
- MVP acceptance is defined per module in `02-REQUIREMENTS.md`; platform acceptance is defined in `05-PLATFORM.md`; quality gates are defined in `06-ENGINEERING.md`.

---

## 6. Future Roadmap

### 6.1 Roadmap Overview

The roadmap is phased to deliver value incrementally while preserving backward compatibility. It consolidates the phase plans from `docs/architecture/1-VISION-AND-STRATEGY.md`, `ACADEMIO_IMPLEMENTATION_PLAN.md`, `docs/FUTURE-DIRECTION.md`, and `docs/COMPLIANCE-ACCREDITATION.md`.

| Horizon | Timeline | Focus |
|---|---|---|
| Foundation (largely complete) | Month 1–4 | Modular monolith, auth, RBAC foundations, core SIS, fee/billing, React SPA |
| Phase 1A (in progress) | Month 1–2 | Architecture hardening: audit logging depth, distributed rate limiting, OpenAPI 3.1, OpenTelemetry, HPA, load testing |
| Phase 2 | Month 3–5 | Admissions & enrollment depth: online portal polish, document verification, AI applicant scoring, enrollment forecasting |
| Phase 3 | Month 4–7 | AI Services Layer: gateway, RAG, student/teacher/parent assistants, NL search, marking assistance, risk prediction |
| Phase 4 | Month 5–8 | CBA + LMS depth: question-bank breadth, WAEC/JAMB-style support, auto-grading, course management, progress tracking |
| Phase 5 | Month 6–9 | Communication & engagement: communication hub breadth, parent engagement, digital report-card engine, AI summaries |
| Phase 6 | Month 8–11 | Extended modules depth: library, hostel, transport, inventory, HR/payroll, finance & accounting |
| Phase 7 | Month 10–13 | Alumni & career: verification services, fundraising, mentorship, AI career guidance |
| Phase 8 | Month 12–15 | BI & analytics: executive dashboards, forecasting, custom report builder, AI executive summaries |
| Phase 9 | Month 14–18 | Mobile & scale: 4 mobile apps, offline-first, 1M+ validation, multi-region, data residency |
| Phase 10+ | Month 18+ | Innovation: credentials, marketplace, virtual classrooms, biometrics, IoT, white-label, international students, advanced analytics, gamification |

### 6.2 Near-Term (Next Two Quarters)

1. **Complete the AI wiring**: fix AI handler dependency injection so `/api/v2/ai/chat`, `/agents`, and `/search` are reliably served; enable feature-flagged rollout. This is the highest-value unblocked work (Phase 22.2).
2. **Ship RBAC enforcement**: roles/permissions CRUD plus route- and action-level middleware on sensitive endpoints (finance, HR, admissions) (Phase 22.1).
3. **Deliver the Education Blueprint Engine foundation**: institution-type templates, country templates (Nigeria first), configurable academic period types, and backward-compatible migration of existing tenants to a "Legacy Secondary Blueprint" (`docs/FUTURE-DIRECTION.md`).
4. **Launch the Compliance & Accreditation module Phase 1–3**: document repository, expiry tracking, staff credential management (TRCN, NYSC), pre-inspection checklists (`docs/COMPLIANCE-ACCREDITATION.md`).
5. **Advance the mobile app** per the implementation plan: parent portal, notifications, messages first, then library/hostel/transport/inventory, then academic modules.

### 6.3 Mid-Term (Quarters 3–6)

1. Finance & accounting depth: chart of accounts, journal entries, budgets, expenses, vendor management (Phase 17).
2. HR & payroll depth: payroll periods, batch payslip generation, appraisals, recruitment (Phase 18).
3. CBA/LMS depth: WAEC/JAMB-style exam support, anti-cheating controls, webcam proctoring, course learning paths, video lessons.
4. Communication hub breadth: SMS, email, push, WhatsApp channels with partner integrations (Twilio, AfricasTalking, Termii, SendGrid, FCM).
5. AI services layer: RAG on pgvector, AI teacher/student/parent assistants, natural-language search, AI-assisted marking.
6. BI & analytics: executive dashboards, enrollment/revenue/academic trends, custom report builder.

### 6.4 Long-Term (Year 2 and Beyond)

1. Alumni & career suite: certificate verification services, fundraising and donation management, mentorship programs, AI career guidance.
2. Mobile scale: four white-label apps (student, parent, teacher, admin), offline-first capabilities, push at scale.
3. Platform scale: read replicas, PgBouncer, application-level sharding, Redis cluster, multi-region deployment with data-residency controls.
4. Enterprise workflow engine: configurable multi-stage approval workflows across modules (`docs/WORKFLOW-IMPLEMENTATION.md`).

### 6.5 Innovation & Expansion (Phase 10+)

| Innovation | Description | Revenue Potential |
|---|---|---|
| Blockchain credentials | Tamper-proof digital diplomas; instant employer verification | $5–15 per verification |
| Crypto & stablecoin payments | USDC/USDT fee payments for diaspora parents | 0.5% conversion fee |
| Global school marketplace | Schools and teachers sell curriculum, lesson plans, exam banks | 15–30% commission |
| Virtual classrooms & metaverse | WebXR classrooms, 3D campus tours, virtual labs | Enterprise add-on |
| Biometric authentication | WebAuthn/FIDO2 login, attendance check-in, exam identity | Platform feature |
| IoT smart campus | RFID attendance, smart ID cards, asset tracking | Enterprise add-on |
| White-label mobile apps | Branded school apps on App Store / Play | $499/mo setup + hosting |
| International student management | Visa tracking, multi-currency fees, SEVIS/CAS integration | Enterprise |
| Advanced analytics & data science | Cohort analysis, predictive models, what-if simulation | $499/mo add-on |
| Gamification | Points, badges, leaderboards, rewards store | Engagement driver |

### 6.6 AI Innovation Roadmap

| Stage | Capability |
|---|---|
| Near-term | AI chat assistant (student/teacher/parent), natural-language search, AI-assisted essay grading suggestions |
| Mid-term | Academic risk prediction and intervention, enrollment forecasting, AI lesson-plan and question generation |
| Long-term | Dropout prediction, career-success prediction, optimal scheduling, teacher-effectiveness prediction, curriculum optimization, adaptive learning paths, multimodal AI (photo/audio/video homework help), automated curriculum alignment to WAEC/NECO/JAMB/IGCSE/IB |

### 6.7 Monetization and Pricing (Summary)

The full pricing strategy is specified in `docs/ABUSE-PREVENTION.md`. The model is **"Free forever, but verified"** — abuse is made expensive rather than adoption blocked.

| Tier | Target | Price (NGN) | Max Students | Key Boundaries |
|---|---|---|---|---|
| Starter (Free) | Small schools | ₦0 | 300 | 2 GB storage; 20 AI requests/mo; watermark on reports; community support |
| Growth | Mid-size schools | ₦69,999/mo | 2,000 | 50 GB; 500 AI requests/mo; custom domain; premium modules (HR, payroll, transport, inventory, LMS, advanced analytics) |
| Enterprise | Large / multi-campus | Custom | Unlimited | Unlimited storage/AI; 365-day backup + PITR; white-label; API; dedicated CSM |

Global (USD) equivalents and à-la-carte add-ons (AI suite, CBA, alumni, HR/payroll, advanced BI, white-label mobile, API tiers) are defined in the monetization strategy. Annual plans carry a 15% discount.

### 6.8 Roadmap Dependencies

1. **AI layer depends on** the AI gateway configuration and provider keys being operational; multi-provider abstraction (OpenAI + Anthropic + open-source) is required before AI features leave pilot.
2. **Blueprint Engine depends on** schema/config refactoring with backward-compatible migration; existing tenants receive a "Legacy Secondary Blueprint" automatically.
3. **Compliance module depends on** document/media storage and HR credential data; integration points are documented in `docs/COMPLIANCE-ACCREDITATION.md`.
4. **Mobile app depends on** API stability and the parent/notification/message endpoints already shipped in the backend.
5. **Global scale depends on** load-test baselines (k6), OpenTelemetry tracing, and the production-readiness audit gates in `docs/architecture/10-AUDIT-CHECKLIST.md`.

---

## 7. Risks

### 7.1 Risk Register

| # | Risk | Likelihood | Impact | Mitigation | FSD Reference |
|---|---|---|---|---|---|
| R1 | **AI vendor lock-in** | High | High | Multi-provider abstraction (OpenAI + Anthropic + open-source); prompt/task routing; no provider-specific contracts in domain code | `02-REQUIREMENTS.md`, `05-PLATFORM.md` |
| R2 | **Data privacy and regulatory change** | High | High | GDPR/NDPRA-aware design; data-residency controls; compliance module tracks evolving requirements (e.g., NECO 2026 NIN mandate) | `05-PLATFORM.md` |
| R3 | **Security breach or tenant isolation failure** | Medium | Critical | Defense-in-depth (CSP, CSRF, JWT rotation, Redis rate limits); schema-per-tenant enforcement; audit logging of all mutations; penetration-testing cadence | `05-PLATFORM.md` |
| R4 | **Competition from global SIS vendors** | Medium | Medium | AI-native, Africa-first compliance positioning, complete lifecycle, aggressive pricing, verified-school trust program | Section 2.6 |
| R5 | **Internet reliability in target markets** | Medium | Medium | Offline-first mobile app, progressive web app, SMS fallback for critical notifications | `05-PLATFORM.md` |
| R6 | **Payment failure rates** | Medium | Medium | Multiple payment providers (Paystack, Flutterwave, Stripe), retry logic, offline payment recording | `04-DATA-API.md` |
| R7 | **Scaling bottlenecks at 1M+ students** | Medium | Medium | Modular monolith → service evolution; Redis caching layers; read replicas; sharding path documented | `05-PLATFORM.md` |
| R8 | **Customer churn** | Medium | Medium | Onboarding success program (< 7 days to value); enterprise CSM; free-forever verified tier reduces early churn | Section 3.3 |
| R9 | **Abuse of the free tier** | Medium | High | The 15 abuse-prevention safeguards: school verification, free-plan limits, invite-based growth, activity monitoring, rate limits, feature flags | `docs/ABUSE-PREVENTION.md`, `05-PLATFORM.md` |
| R10 | **Uneven module depth (technical debt)** | High | Medium | 49 modules exist with varying completeness; module-level acceptance criteria in `02-REQUIREMENTS.md`; implementation-plan phases 1–2 target bug fixes and quality gates | `06-ENGINEERING.md` |
| R11 | **RBAC gaps exposing data** | Medium | High | Phase 22.1 RBAC middleware; route gating already in frontend; data-level permission matrix in `03-UX-DESIGN.md` | `06-ENGINEERING.md` |
| R12 | **AI cost exposure** | Medium | High | Per-plan AI request caps (20/500/unlimited); feature-flag gating; model-routing for cost/quality | `docs/ABUSE-PREVENTION.md` |
| R13 | **pgx v5 prepared-statement constraints** | Low | Medium | Multi-statement `db.Exec()` is forbidden; break into individual calls (Rule B4/B13 in `AGENTS.md`) | `06-ENGINEERING.md` |
| R14 | **Schema-per-tenant join complexity** | Medium | Medium | `SchemaTablePrefix` plugin centralizes schema scoping; GORM join audit; tenant-DB resolver middleware; see `docs/reports/gorm-issues.md` | `05-PLATFORM.md` |
| R15 | **Blueprint Engine migration breakage** | Medium | High | Backward-compatible migration; automatic "Legacy Secondary Blueprint"; no-downtime rollout; migration tests required | `06-ENGINEERING.md` |
| R16 | **Key-person / documentation drift** | Medium | Medium | FSD suite + architecture docs as source of truth; ADR process; CI docs checks | `06-ENGINEERING.md` |

### 7.2 Technical Risks

- **Uneven module maturity (R10).** Several modules are thin screens over minimal service logic. Mitigation: every module must meet the acceptance criteria in `02-REQUIREMENTS.md` before it is marketed as complete; the implementation plan's bug-fix phase (Phase 1) must complete first.
- **AI feature latency and reliability (R1, R12).** AI responses must be < 3 s and degrade gracefully when providers are unavailable. Mitigation: timeouts, retries, cached responses for common queries, and log-and-continue for analytics use cases.
- **Multi-tenant query correctness (R14).** Cross-schema joins are the most common source of tenant leakage or failure. Mitigation: tenant-scoped DB resolution via `middleware.GetTenantDB(c)`; never use the raw core DB for tenant queries (Rule B8); regression tests.
- **Background-job resilience.** Provisioning, email, SMS, backup, and AI-scoring tasks run on Asynq; a Redis outage must not corrupt provisioning state. Mitigation: idempotent task handlers, retries with backoff, and health monitoring.

### 7.3 Product and Market Risks

- **Market timing for AI features.** African schools may prioritize reliability and cost over AI novelty. Mitigation: AI is a paid add-on, never a prerequisite; core SIS value is delivered without AI.
- **Compliance scope creep.** Regulatory tooling varies by state and country. Mitigation: configurable templates (multi-state support is Phase 6 of the compliance roadmap), not hardcoded Lagos-specific rules.
- **Brand transition.** Legacy documents and code identifiers still reference the former codename. Mitigation: this FSD suite standardizes on "Academio"; internal identifiers are being normalized in parallel engineering work.

### 7.4 Security and Compliance Risks

- **Regulatory record-keeping (R2).** Nigerian schools must retain records for 7 years and produce registers on demand. Mitigation: audit logs, media/document repository, and exportable registers in the compliance module.
- **Examination malpractice surfaces.** CBA and proctoring introduce integrity risk. Mitigation: randomized questions/options, timed exams, auto-save, proctoring event logs, and review workflows.
- **Phishing and account takeover.** Mitigation: TOTP 2FA, refresh-token rotation, Redis token blacklist, rate-limited login, and CSRF protection.

### 7.5 Operational Risks

- **Infrastructure dependency on Docker-local services.** Development requires `shared-postgres` and `shared-redis` containers; production deploys must codify the same topology. Mitigation: documented ops runbooks in `docs/ops/` and CI/CD gates in `05-PLATFORM.md`.
- **Data loss.** Mitigation: tiered backup retention (7/90/365 days), S3-based tenant backups, restore drills.

### 7.6 Risk Response Strategy

- **Avoid**: refuse features that compromise tenant isolation or security (e.g., raw SQL in handlers, hardcoded secrets — Rules B6/B7).
- **Mitigate**: apply the mitigations in Section 7.1 and track them in the production-readiness checklist (`docs/architecture/10-AUDIT-CHECKLIST.md`).
- **Transfer**: payment processing and SMS delivery are handled by regulated partners (Paystack, Twilio, AfricasTalking); the platform abstracts provider details.
- **Accept**: certain market risks (e.g., internet reliability) are accepted with compensating design (offline-first, SMS fallback).

---

## Appendix A — Verified Implementation Inventory

### A.1 Backend Modules (49, verified 31 July 2026)

```
backend/internal/modules/
  academic        academic-calendar  admission      ai             alumni
  analytics       audit              auth           bill           career
  cba             communication      conference     dashboard      discipline
  exam            external_exam      finance        forum          grading
  health          hostel             hr             inventory      invitation
  lessonplan      library            lms            media          messages
  multimedia      notifications      parentdashboard pastoral      payment
  proctoring      rbac               reportbuilder  reportcard     reports
  result          school             score          studenthealth  studentportal
  tenant          timetable          transport      user
```

Layered convention per module: `dto.go`, `handler.go`, `service.go`, `repository.go` (plus optional `events.go`, `*_test.go`). Modules `ai` and `rbac` are thinner than the convention and are tracked in Section 5.5.

### A.2 Frontend Route Tree (verified 31 July 2026)

| Area | Routes |
|---|---|
| Auth (root) | `login`, `register`, `forgot-password`, `reset-password`, `confirm-email` |
| Public (`_public`) | Landing, `about`, `features`, `how-to-use`, `editions`, `cookies`, `privacy`, `terms`, admissions `apply` / `route` / `status` |
| Onboarding (`_onboarding`) | School setup wizard (`onboarding`) |
| Super admin (`_super`) | `super.index` (school picker), `super.$id` (tenant detail) |
| Dashboard (`_dashboard`, 60+ destinations) | Dashboard, school, settings, profile, change-password, users (+ student), invitations, audit-logs, notifications; academics, academic-calendar (calendar/events/periods/blueprints), attendance, exams, timetable, grading, promotion, results (+ master-sheet), report-cards (+ batch/detail), lesson-plans (notes/plans/schemes), external-exam; cba (+ exams, take, results), proctoring, lms (+ course detail, assignments, discussions); admissions (applications, forms, intakes, screening, offers); alumni (+ insights), career, hr, student-health, discipline, pastoral, conferences; finance, bills, payment; hostel, transport, inventory, library, media; communication (broadcast/campaigns/compose/templates/delivery), messages, forum; analytics (academic/enrollment/revenue), reports (+ builder); ai-assistant; teacher (dashboard/class/attendance/academics/results/timetable/report-cards), student (index/attendance/fees/results/report-cards/timetable), parent (index/children/$id) |

### A.3 Implementation Plan Status (reference)

`ACADEMIO_IMPLEMENTATION_PLAN.md` defines 23 phases (~362 hours, ~85 sub-phases) covering the Flutter mobile app plus backend gaps and quality work. Phase 1 (bug fixes) and Phase 2 (quality/polish) are prerequisites for all feature phases.

---

## Appendix B — Terminology

| Term | Definition |
|---|---|
| Tenant | An isolated school/organization instance. In Academio, each tenant maps to a PostgreSQL schema `school_{id}`. |
| Schema-per-tenant | Isolation model where each school's data lives in its own database schema within a single PostgreSQL database. |
| Provisioning | The synchronous process that creates the tenant schema, runs migrations, seeds curriculum data, and sets `schema_name` on the school record. |
| Module | A backend domain folder under `internal/modules/` following the dto/handler/service/repository convention. |
| CBA | Computer-Based Assessment — the exam engine (question bank, papers, timed exam player, results). |
| LMS | Learning Management System — courses, modules, lessons, assignments, submissions, discussions. |
| SIS | Student Information System — the core academic records surface. |
| Blueprint (Education Blueprint Engine) | A template that installs academic structure, calendar, curriculum, grading, roles, and defaults for an institution type/country. |
| NGN / ₦ | Nigerian Naira — the default display currency (Rule F5). |
| 1-6-3-3-4 | Nigerian education structure: 1 year crèche, 6 years primary, 3 years junior secondary, 3 years senior secondary, 4+ years tertiary. |
| BECE / WASSCE / SSCE / UTME | Basic Education Certificate Examination; West African Senior School Certificate Examination; Senior School Certificate Examination; Unified Tertiary Matriculation Examination. |
| TRCN | Teachers Registration Council of Nigeria — teacher certification and registration body. |

---

## Appendix C — Source Documents

| Document | Role in this FSD |
|---|---|
| `docs/architecture/INDEX.md` | Document map and architecture decisions |
| `docs/architecture/1-VISION-AND-STRATEGY.md` | Vision, pillars, roadmap phases, monetization, competitive landscape |
| `docs/architecture/5-AI-ARCHITECTURE.md` | AI layer target state (roadmap for Section 5.5/6) |
| `docs/architecture/7-USE-CASES.md` | Actor definitions and use cases (persona grounding) |
| `docs/architecture/8-FUTURE-EXPANSION.md` | Phase 10+ roadmap, risks, KPIs |
| `docs/PROJECT.md` | Project overview, architecture, stack, conventions |
| `AGENTS.md` | Engineering rules and constraints (Rules F1–F5, B1–B13) |
| `ACADEMIO_IMPLEMENTATION_PLAN.md` | 23-phase implementation plan; gap identification |
| `docs/NG-EDUCATION-STANDARDS.md` | Nigerian education domain model, grading systems, compliance |
| `docs/COMPLIANCE-ACCREDITATION.md` | Compliance module roadmap (planned scope) |
| `docs/FUTURE-DIRECTION.md` | Education Blueprint Engine evolution |
| `docs/ABUSE-PREVENTION.md` | Free-tier safeguards and pricing model |

---

*End of Part 1 — Product Specification. Continue to `02-REQUIREMENTS.md` for module-level functional requirements.*
