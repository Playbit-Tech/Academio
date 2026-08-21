# Academio Functional Specification Document

| Attribute | Value |
|---|---|
| **Document** | 00-FSD-INDEX.md — Master Index and Reading Guide |
| **Product** | Academio — Enterprise Multi-tenant School Management / Education ERP |
| **Version** | 1.0 |
| **Status** | Initial release — draft for review (part files carry individual implementation statuses) |
| **Date** | 2026-07-31 |
| **Owner** | Playbit Technologies |
| **Document set** | Six part files (`01-PRODUCT.md` … `06-ENGINEERING.md`) plus this index |

---

## 1. Purpose of This Document

This file is the master index for the Academio Functional Specification Document (FSD) set. It provides a complete table of contents across all six part files, a document map showing how the parts relate, guidance on how to read the set by audience, the revision history, and the underlying source documents.

The FSD set is grounded in the **verified implementation state** of the codebase (49 backend modules under `backend/internal/modules/`, the frontend route tree under `frontend/src/routes/`, and the API client surface in `frontend/src/lib/api.ts`). Features documented as design targets but not yet implemented are explicitly marked **Planned** and are never described as implemented behaviour.

---

## 2. Table of Contents

Section references below match the actual header hierarchy of each part file. Part-level links jump to the file; section links jump to the in-file anchor.

### Part 01 — Product Specification (`01-PRODUCT.md`, 706 lines)

- [§1 Executive Summary](01-PRODUCT.md#1-executive-summary) — product overview, current state (verified), target state, scope
- [§2 Vision](01-PRODUCT.md#2-vision) — vision statement, complete student lifecycle, target markets, brand positioning, strategic pillars, competitive landscape, ten-year aspiration
- [§3 Product Goals](01-PRODUCT.md#3-product-goals) — strategic goals, operational goals, measurable KPIs, non-functional goals, goal traceability
- [§4 Personas](01-PRODUCT.md#4-personas) — persona methodology, primary and secondary personas, persona × module access matrix, persona-driven design principles
- [§5 MVP Scope](01-PRODUCT.md#5-mvp-scope) — scope definition and verification method; implemented, partially implemented, and planned capabilities
- [§6 Future Roadmap](01-PRODUCT.md#6-future-roadmap)
- [§7 Risks](01-PRODUCT.md#7-risks)
- [Appendix A — Verified Implementation Inventory](01-PRODUCT.md#appendix-a--verified-implementation-inventory)
- [Appendix B — Terminology](01-PRODUCT.md#appendix-b--terminology)
- [Appendix C — Source Documents](01-PRODUCT.md#appendix-c--source-documents)

### Part 02 — Requirements (`02-REQUIREMENTS.md`, 803 lines)

- [§0 Document Purpose and Scope](02-REQUIREMENTS.md#0-document-purpose-and-scope) — relationship to the FSD set, referenced documents, conventions, verification basis
- [§1 Product Summary](02-REQUIREMENTS.md#1-product-summary)
- [§2 Module Inventory (Implementation Basis)](02-REQUIREMENTS.md#2-module-inventory-implementation-basis) — 49 verified backend modules, frontend route groups, API client capabilities
- [§3 Functional Requirements](02-REQUIREMENTS.md#3-functional-requirements) — 21 business areas:
  §3.1 Core Platform (auth, users, tenancy, RBAC, audit) · §3.2 Academic (sessions, curriculum, assessment, grade items, calendar, grading, promotion) · §3.3 Admissions · §3.4 Assessment / Results (scores, results, approval, external exams, report cards) · §3.5 Attendance · §3.6 Timetable · §3.7 Finance / Billing · §3.8 HR / Payroll · §3.9 Library · §3.10 Hostel · §3.11 Transport · §3.12 Communication / Messaging · §3.13 Alumni and Career · §3.14 CBA and Proctoring · §3.15 Discipline · §3.16 Health and Pastoral Care · §3.17 Inventory · §3.18 LSM/LMS (courses, lessons, assignments, forums, conferences, media) · §3.19 Reports and Analytics · §3.20 AI Assistant · §3.21 Portals (parent and student)
- [§4 Non-Functional Requirements](02-REQUIREMENTS.md#4-non-functional-requirements) — §4.1 multi-tenancy and isolation · §4.2 performance and capacity · §4.3 security · §4.4 reliability and operations · §4.5 compliance and localization (Nigerian market) · §4.6 usability and accessibility · §4.7 maintainability and developer experience
- [§5 User Stories](02-REQUIREMENTS.md#5-user-stories) — US-01 … US-22, each mapped to functional requirements
- [§6 Use Cases](02-REQUIREMENTS.md#6-use-cases) — UC-1 … UC-15 with implementation status and evidence, actor × module permission matrix, use case extensions
- [§7 User Journeys](02-REQUIREMENTS.md#7-user-journeys) — UJ-1 new school onboarding and provisioning · UJ-2 term result cycle · UJ-3 parent enrollment and monitoring · UJ-4 admission lifecycle · UJ-5 CBA examination cycle · UJ-6 fee billing, payment, and allocation
- [§8 Acceptance Criteria](02-REQUIREMENTS.md#8-acceptance-criteria) — §8.1 tenancy and provisioning · §8.2 admissions · §8.3 scoring, results, report cards · §8.4 attendance and timetable · §8.5 portals and finance · §8.6 CBA and proctoring · §8.7 HR, library, hostel, transport, discipline · §8.8 platform and cross-cutting
- [§9 Traceability](02-REQUIREMENTS.md#9-traceability) — module → FR coverage, acceptance criteria → FR coverage
- [§10 Open Items and Assumptions](02-REQUIREMENTS.md#10-open-items-and-assumptions)
- [§11 Document Revisions](02-REQUIREMENTS.md#11-document-revisions)

### Part 03 — UX Design (`03-UX-DESIGN.md`, 1105 lines)

- [Document Map — the FSD Series](03-UX-DESIGN.md#document-map--the-fsd-series)
- [§1 Wireframe Descriptions](03-UX-DESIGN.md#1-wireframe-descriptions) — 22 screens: conventions · authentication · public marketing site · onboarding wizard · admin dashboard · teacher dashboard · student portal · parent portal · students management · teachers management · academics · results and master sheet · report cards · CBA · attendance · timetable · finance/bills · admissions · communication/messages · settings and profile · super admin console · screen status summary
- [§2 Information Architecture](03-UX-DESIGN.md#2-information-architecture) — principles, top-level sitemap, route conventions (TanStack Router), portal separation model, route inventory, content depth, known gaps and inconsistencies
- [§3 Navigation Design](03-UX-DESIGN.md#3-navigation-design)
- [§4 UI Component Standards](03-UX-DESIGN.md#4-ui-component-standards)
- [§5 Cross-References](03-UX-DESIGN.md#5-cross-references)

### Part 04 — Data & API Design (`04-DATA-API.md`, 646 lines)

- [§1 Database Design](04-DATA-API.md#1-database-design) — topology, shared schema (`public`), tenant schema (`school_{id}`), base model conventions, assessment domain, audit and retention
- [§2 ER Diagrams](04-DATA-API.md#2-er-diagrams) — shared schema, tenant schema (academic core)
- [§3 API Design](04-DATA-API.md#3-api-design) — conventions, response envelope and error categories, pagination, v2 endpoint catalog, worked example
- [§4 Authentication](04-DATA-API.md#4-authentication) — token model, cookie vs Bearer transport modes, auth endpoints, authentication flow, tenant resolution after auth
- [§5 RBAC](04-DATA-API.md#5-rbac) — roles, permission levels, enforcement points, audit of privileged actions
- [Appendix A — Implementation References](04-DATA-API.md#appendix-a--implementation-references)
- [Appendix B — Known Constraints](04-DATA-API.md#appendix-b--known-constraints)

### Part 05 — Platform Services (`05-PLATFORM.md`, ≈800 lines)

- [§0 Implementation Status Legend](05-PLATFORM.md#0-implementation-status-legend)
- [§1 Audit Logging](05-PLATFORM.md#1-audit-logging) — event model, storage topology, asynchronous write path, capture points, query API, retention and archival
- [§2 Notifications](05-PLATFORM.md#2-notifications) — in-app persistence, WebSocket and FCM delivery, broadcast integration, gaps and roadmap
- [§3 Search](05-PLATFORM.md#3-search) — record search (ILIKE), trigram indexing, AI natural-language search, planned semantic/vector search
- [§4 Global Settings](05-PLATFORM.md#4-global-settings) — plan defaults, tenant configuration API, school-level profile, planned global console
- [§5 Tenant Architecture](05-PLATFORM.md#5-tenant-architecture) — schema-per-tenant model, schema DB and table prefixing, provisioning, tenant resolution and caching, isolation and testing, scaling
- [§6 Event-driven Architecture](05-PLATFORM.md#6-event-driven-architecture) — task-driven asynchrony (Asynq), inter-module integration, planned domain event bus
- [§7 Background Jobs](05-PLATFORM.md#7-background-jobs) — queue infrastructure, task types, cron scheduler, health and observability
- [§8 Caching Strategy](05-PLATFORM.md#8-caching-strategy) — implemented Redis caches, cache warm, planned query cache
- [§9 File Storage](05-PLATFORM.md#9-file-storage) — storage abstraction, startup selection, per-tenant prefixes, media library, backup storage, roadmap
- [Appendix A. Platform Configuration Reference](05-PLATFORM.md#appendix-a-platform-configuration-reference)
- [Appendix B. Implementation Status Summary](05-PLATFORM.md#appendix-b-implementation-status-summary)

### Part 06 — Engineering (`06-ENGINEERING.md`, 799 lines)

- [§1 Introduction and Scope](06-ENGINEERING.md#1-introduction-and-scope)
- [§2 Security](06-ENGINEERING.md#2-security)
- [§3 Monitoring](06-ENGINEERING.md#3-monitoring)
- [§4 Performance](06-ENGINEERING.md#4-performance)
- [§5 Disaster Recovery](06-ENGINEERING.md#5-disaster-recovery)
- [§6 Testing Strategy](06-ENGINEERING.md#6-testing-strategy)
- [§7 Deployment Strategy](06-ENGINEERING.md#7-deployment-strategy)
- [§8 CI/CD](06-ENGINEERING.md#8-cicd)
- [§9 Scalability Plan](06-ENGINEERING.md#9-scalability-plan)
- [§10 Technical Decisions](06-ENGINEERING.md#10-technical-decisions)
- [§11 Cross-References to Other FSD Parts](06-ENGINEERING.md#11-cross-references-to-other-fsd-parts)
- [§12 Appendix A: Implementation Status Summary](06-ENGINEERING.md#12-appendix-a-implementation-status-summary)
- [§13 Appendix B: Reference Documents](06-ENGINEERING.md#13-appendix-b-reference-documents)

---

## 3. Document Map

| Part | File | Scope | Primary audience | Dependencies |
|---|---|---|---|---|
| 0 | `00-FSD-INDEX.md` | Master index, document map, reading guide, revision history, references | All stakeholders | All parts |
| 1 | `01-PRODUCT.md` | Executive summary, vision, product goals, personas, MVP scope, future roadmap, risks | Executives, product owners, investors | Architecture vision documents |
| 2 | `02-REQUIREMENTS.md` | Module inventory, functional and non-functional requirements, user stories, use cases, user journeys, acceptance criteria, traceability | Product managers, engineers, QA | Part 01 |
| 3 | `03-UX-DESIGN.md` | Wireframe descriptions, information architecture, navigation design, UI component standards | UX/UI designers, frontend engineers | Parts 01, 02 |
| 4 | `04-DATA-API.md` | Database design, ER diagrams, API design, authentication, RBAC | Backend, frontend, platform engineers | Parts 02, 06 |
| 5 | `05-PLATFORM.md` | Audit logging, notifications, search, global settings, tenant architecture, event-driven architecture, background jobs, caching strategy, file storage | Backend and platform engineers, DevOps, QA | Parts 02, 04, 06 |
| 6 | `06-ENGINEERING.md` | Security, monitoring, performance, disaster recovery, testing strategy, deployment, CI/CD, scalability plan, technical decisions | All engineering, DevOps, QA, SRE | Parts 02, 04, 05 |

The FSD set follows a linear read order (01 → 06) but is designed for targeted reading: every part declares its cross-references, and Part 06 §11 and Part 03 §5 are dedicated cross-reference indexes.

---

## 4. How to Read This Document

The FSD set is intentionally modular. Choose the parts that match your role; the table below is the recommended reading path.

| Audience | Recommended path | Why |
|---|---|---|
| Executives / leadership / investors | **01** (§1 Executive Summary, §3 Goals, §6 Roadmap, §7 Risks), skim §2 Vision | Product-level decisions, scope, and risk posture; no implementation detail needed |
| Product managers / business analysts | **01**, **02** (§2–§7), **03** §2 (Information Architecture) | Requirements, priorities, user stories, journeys, and the module surface |
| UX / UI designers | **03** (all), **02** §4.6 (Usability) | Wireframes, information architecture, navigation, UI component standards |
| Frontend engineers | **03** §4 (UI standards), **04** §3 (API design) and §4 (Authentication), **02** §4.6–§4.7 | UI component rules (incl. Rules F1–F5), API contracts, auth flow |
| Backend / platform engineers | **04** (all), **05** (all), **06** §2–§5 and §10 | Data model, API contract, platform services, engineering standards and technical decisions |
| QA / test engineers | **02** §8 (Acceptance Criteria), **06** §6 (Testing Strategy), **04** §3 (API contracts) | Acceptance criteria are the input to test cases; testing strategy defines quality gates |
| DevOps / SRE | **06** §3 (Monitoring), §5 (DR), §7 (Deployment), §8 (CI/CD), §9 (Scalability); **05** §7 (Background Jobs) | Operations, deployment, reliability, and capacity planning |
| Security reviewers | **06** §2 (Security), **04** §4–§5 (Auth, RBAC), **05** §1 (Audit) | Security architecture, authentication, authorization, audit trail |

**Series conventions** (defined in `02-REQUIREMENTS.md` §0.3 and reused across parts):

- **Requirement identifiers**: `FR-<AREA>-<NN>` (functional), `NFR-<AREA>-<NN>` (non-functional), `US-<NN>` (user story), `UC-<NN>` (use case), `UJ-<NN>` (user journey), `AC-<NN>` (acceptance criterion).
- **Priority levels**: `MUST` (P0 — release blocking), `SHOULD` (P1 — important, can ship behind flag), `COULD` (P2 — desirable), `WON'T` (P3 — out of scope for current phase).
- **Implementation status**: `Implemented` (verified in code), `Partially implemented` (core flow verified, extension marked Planned), `Planned` (documented design target, not yet in code). Part 05 §0 defines its own legend.
- **Currency**: all monetary values default to Nigerian Naira (NGN, symbol ₦) unless a field explicitly states otherwise.

---

## 5. Revision History

| Version | Date | Author / Owner | Summary of changes |
|---|---|---|---|
| v1.0 | 2026-07-31 | Playbit Technologies | Initial FSD release (all 40 sections across 6 parts) |

---

## 6. References

The FSD set is derived from and cross-references the following source documents. The "Cited by" column indicates which part file(s) cite each document.

| Document | Role in the FSD set | Cited by |
|---|---|---|
| `AGENTS.md` | Engineering constitution — hard rules F1–F5 (frontend), B1–B13 (backend); environment; tenant architecture; key decisions | 01, 02, 03, 06 |
| `docs/architecture/INDEX.md` | Document map and architecture decisions | 01, 03 |
| `docs/architecture/1-VISION-AND-STRATEGY.md` | Vision, pillars, roadmap phases, monetization, competitive landscape | 01, 02 |
| `docs/architecture/2-ARCHITECTURE-OVERVIEW.md` | Module catalogue and portal strategy | 03 |
| `docs/architecture/5-AI-ARCHITECTURE.md` | AI layer target state, mobile/AI integration roadmap, RAG architecture | 01, 05 |
| `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` | Defense in depth, auth flow, monitoring stack, K8s/HPA, CI/CD target | 06 |
| `docs/architecture/7-USE-CASES.md` | 15 actor personas and 15 use cases; basis for FSD Part 02 §6 | 01, 02 |
| `docs/architecture/8-FUTURE-EXPANSION.md` | Phase 10+ roadmap, risks, KPIs | 01 |
| `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` | Context propagation, graceful shutdown, logging, OTel, fail-fast config, pagination, CSP, secrets, audit | 06 |
| `ACADEMIO_IMPLEMENTATION_PLAN.md` | 23-phase implementation plan; gap identification | 01, 02 |
| `docs/PROJECT.md` | Project overview, architecture, stack, conventions, repository layout | 01, 02, 06 |
| `docs/NG-EDUCATION-STANDARDS.md` | Nigerian education domain model (1-6-3-3-4), WAEC/NECO/JAMB systems, grading scales | 01, 02 |
| `docs/NG-LESSON-NOTE-PLAN-STANDARDS.md` | Lesson plan and lesson note standards for the Nigerian curriculum | 02 |
| `docs/WORKFLOW-IMPLEMENTATION.md` | Approval workflow requirements (results, admissions, leave, expenses) | 02, 03 |
| `docs/COMPLIANCE-ACCREDITATION.md` | Lagos State compliance and accreditation requirements | 01, 02 |
| `docs/ABUSE-PREVENTION.md` | Free-tier limits, rate limits, verification safeguards, pricing model | 01, 02, 06 |
| `docs/FUTURE-DIRECTION.md` | Education Blueprint Engine evolution | 01 |
| `docs/performance-baseline.md` | Performance budgets (p95 < 500 ms, p99 < 1000 ms, error < 1%, parallel drop < 30%) | 02, 06 |
| `docs/ops/deploy.md` | Deployment runbook — env checklist, build, migrations, rollback, health verification | 06 |
| `docs/ops/load-test-baseline.md` | k6 load-test baseline and template | 02, 06 |
| `backend/STYLE.md` | Backend style — formatting, error handling, logging, security, GORM patterns, performance | 06 |
| `backend/TESTING.md` | Testing conventions — test layout, build tags, mocking, coverage targets | 06 |
| `frontend/DESIGN_SYSTEM.md` | The "Empathetic Growth" design system | 03 |
| `frontend/DESIGN_PATTERNS.md` | Frontend architectural and coding conventions | 03 |
| `mobile/AGENTS.md` | Flutter flavor architecture (admin / teacher / student apps) | 03 |
| `docs/audits/FRONTEND-ENTERPRISE-AUDIT.md` | Frontend audit findings that shape UI standards | 03 |
| `docs/reports/production-audit.md` | Production audit — 84/100 score; resolved and remaining findings | 06 |
| `docs/reports/gorm-issues.md` | SchemaTablePrefix + PrepareStmt panic; many-to-many Preload workaround | 06 |

---

*End of the FSD master index. Continue to `01-PRODUCT.md` for the Product Specification.*
