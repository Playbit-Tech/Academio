# Project Research Summary

**Project:** Academio
**Domain:** Multi-tenant K-12 school management system (Nigerian-focused)
**Researched:** 2026-07-18
**Confidence:** HIGH (codebase-verified findings + multiple authoritative sources)

## Executive Summary

Academio is an unusually mature multi-tenant school management system. At ~58K lines of Go backend across 39 modules, it already delivers most features that international SIS platforms (PowerSchool, FACTS SIS, Gradelink) offer — assessment, attendance, timetabling, finance, HR, LMS, alumni, communication, AI integration, CBA/proctoring, and custom reporting. The architecture is a well-structured modular monolith with schema-per-tenant PostgreSQL isolation, Redis-backed task queuing (Asynq), WebSocket real-time notifications, and a comprehensive React 19 frontend. **The core question is no longer "what to build" but "what's missing for Nigerian market fit and production hardening."**

The research reveals three critical realities. First, **table-stakes features for Nigerian schools are the biggest gap**: Student Health Records (immunizations, allergies), Discipline/Behavior Management, End-of-Year Rollover automation, WAEC external exam integration, and CA/Exam split grading configuration are all absent. These are non-negotiable for competing with sERP Nigeria, EduSync, and SchoolOS. Second, **the schema-per-tenant model has well-documented scaling ceilings** (~500 tenants before pg_catalog bloat degrades performance) — the migration infrastructure needs hardening (per-schema locking, retry, rollback) before tenant count grows. Third, **grade calculation uses float32 throughout**, which is a known precision-loss pattern that causes boundary-value disputes (74.98% displayed as B2 when it should be A1). This must be migrated to integer basis-point storage before the first school completes a full academic year.

The recommended approach is six disciplined phases: **(1) Foundation** — harden provisioning, migration fan-out, search_path isolation, and add PDF generation + cron scheduling; **(2) Critical Features** — Student Health Records, Discipline Management, CA/Exam Split Grading, Fee Structure (NGN); **(3) Communication & Calendar** — Enhanced parent-teacher messaging with conversations, iCal export, WhatsApp notifications; **(4) Academic Workflow** — End-of-Year Rollover, WAEC external exam model, stable student identifiers, timetable mutation safety; **(5) Gradebook Hardening** — Integer precision migration, DB-level sum-to-100 enforcement, grade freeze with report card snapshotting; **(6) Scaling & Reliability** — Communication delivery tracking, pg_catalog monitoring, analytics materialized views, error tracking. Growth features (multi-campus, NERDC alignment, OAuth/SSO, i18n) follow in later phases. Key risk: skipping Phase 1 foundation work means every subsequent phase operates on fragile infrastructure.

## Key Findings

### Recommended Stack (Additions)

The existing stack (Go 1.26 / Gin / GORM / PostgreSQL / React 19 / Vite / TanStack Router / shadcn/ui / Asynq / Redis) is well-established and not re-evaluated. Focus is on **what's missing** for advanced features:

**Immediate (Phase 1):**
- **Gotenberg v8.34.0** (`nativebpm/gotenberg-client`) — Server-side HTML→PDF conversion via headless Chromium. Replaces current HTML-only report card output. Clean Docker deployment, no browser embedding.
- **robfig/cron v3** — Scheduled job runner. Needed for nightly backups, weekly reports, monthly billing. Delegates to Asynq for execution.

**Near-term (Phase 2-3):**
- **Firebase Cloud Messaging** (`appleboy/go-fcm`) — Push notifications for mobile browser and (future) mobile app. Cross-platform, free tier.
- **markbates/goth v1.80+** — OAuth/SSO (Google Workspace, Microsoft 365). Staff login via school Google accounts.
- **disintegration/imaging v1.6.2** — Pure Go image resizing/thumbnail generation. Zero CGO deps.
- **golang-ical** (`arran4/golang-ical`) — iCal export for timetable calendar sync.

**Later (Phase 5-6):**
- **getsentry/sentry-go** — Error aggregation and alerting (beyond current logging).
- **nicksnyder/go-i18n v2** + **react-i18next** — Internationalization for parent-facing communications.

**Deferred:** API gateway (existing rate limiting sufficient), search infrastructure (PostgreSQL FTS first), native mobile apps (PWA strategy).

### Expected Features

**Existing (39 modules — do not rebuild):**
Auth with 2FA/CSRF, multi-tenant schema isolation, school provisioning, academic sessions/terms/curriculum, admissions with dynamic forms, user/student/staff/parent management, assessment & scoring, attendance (student + staff), timetable with calendar editor, report cards, communication (email/SMS), AI (Gemini + OpenAI + RAG), finance (CoA, billing, budgets), HR (payroll, leave, appraisals, recruitment), LMS, library, hostel, transport, inventory, alumni, CBA + proctoring, exam, career guidance, pastoral care, notifications, multimedia, backup/restore, observability.

**Must have (table stakes — currently missing):**
1. **Student Health Records** — Immunizations, allergies, medications, nurse visits. Nigerian schools track polio/BCG/hepatitis records, sickle cell status. *Highest priority gap.*
2. **Discipline / Behavior Management** — Incident logging, detention, suspension tracking, parent notifications.
3. **End-of-Year Rollover / Student Promotion** — Automated promotion, grade archiving, session lifecycle. Critical annual operation, currently manual.
4. **CA/Exam Split Grading Configuration** — Nigerian 30/70 or 40/60 continuous assessment + exam split. WAEC A1-F9 scale mapping.
5. **WAEC External Exam Integration** — Separate model for board-certified grades (A1-F9), credit pass counting, multi-sitting tracking. Must NOT mix with internal grades.
6. **Parent-Teacher Conference Management** — Slot booking, reminders, confirmation.

**Should have (competitive differentiators):**
1. **WhatsApp Notification Integration** — EduSync differentiator. Parents more responsive on WhatsApp than email. Build on existing Twilio integration.
2. **Fee Structure Configuration (NGN)** — Nigerian fee complexity (tuition, PTA levies, development fees, per-class structures, waivers). Verify existing finance module depth.
3. **Multi-Campus Management** — School chains need consolidated dashboards. Schema-per-campus + cross-schema queries.
4. **NERDC Curriculum Alignment** — Pre-loaded curriculum per subject/class (JSS1-SSS3). High effort, high Nigerian market value.
5. **AI-Powered Report Card Comments** — Quick win. Feed assessment data → prompt AI → generate personalized comments.
6. **WAEC/NECO CBT-Ready Certification** — Build on CBA module. Government CBT mandate by 2026.

**Differentiators worth emphasizing (already built):**
- Multi-tenant schema isolation (stronger than most competitors)
- AI integration (few SIS platforms have this)
- CBA + proctoring (positioned for WAEC/NECO CBT transition)
- Custom report builder (ad-hoc reporting gap is #1 PowerSchool complaint)
- Career guidance + pastoral care (rare in SIS)
- Schema-aware backup/restore (enterprise-grade)

**Anti-features (explicitly not building):**
- Native mobile apps (PWA strategy — SchoolOS proves it works)
- Video conferencing, real-time collaboration, e-commerce
- Full HRIS/payroll engine (integrate with Nigerian payroll providers instead)
- Exam board content licensing (focus on school-created mock exams)

### Architecture Approach

The system is a well-structured **modular monolith** (Go/Gin, 39 modules) with a clear **Handler → Service → Repository** layered pattern per module. Schema-per-tenant PostgreSQL isolation via the `SchemaTablePrefix` GORM plugin routes queries to `school_{id}` schemas. Real-time features use an in-process WebSocket hub with room-based messaging. Background jobs run via Asynq (Redis-backed). The architecture is production-ready for single-process deployment; horizontal scaling (Redis Pub/Sub for WebSocket, read replicas) is a known future need.

**Major components relevant to upcoming work:**

1. **WebSocket Hub** (`backend/internal/ws/`) — Already built with JWT auth, room management, rate limiting, Prometheus metrics, and 8 event types. Powers real-time notifications. **Needs Redis Pub/Sub for horizontal scaling** (future).
2. **Communication Module** (`backend/internal/modules/communication/`) — Already built with `NotificationProvider` interface supporting SendGrid (email) and Twilio (SMS). **Needs delivery tracking webhooks and WhatsApp channel**.
3. **Report Builder** (`backend/internal/modules/reportbuilder/`) — Built but **returns CSV with metadata only** (known TODO at `service.go:148`). Actual data querying not yet implemented. Needs analytics schema with materialized views for cross-tenant reporting.
4. **Messages Module** (`backend/internal/modules/messages/`) — Basic CRUD exists. **Needs conversation model, threading, read receipts, file attachments** for parent-teacher communication.
5. **Timetable Module** (`backend/internal/modules/timetable/`) — Full CRUD with calendar editor, bulk create, conflict highlighting. **Needs recurrence model and iCal export** for calendar sync.

**Cross-cutting integration patterns:**
- **Real-time events:** Service → NotificationService.Create() → WebSocket Hub.Broadcast()
- **Async workflows:** Service → Enqueue Asynq task → Worker processes → NotificationService.Create() on completion
- **Cross-tenant queries:** Query each schema in goroutines → merge server-side (for multi-campus)

### Critical Pitfalls

1. **Schema-per-tenant Migration Fan-Out Failure** (Phase 1) — Migrations must apply to every tenant schema. A 2-second migration × 500 tenants = 16 minutes. Partial failures create unrecoverable drift. **Mitigation:** Concurrent runner exists but needs per-schema advisory locks, `migration_errors` table, retry CLI, and CI migration-count validation.
2. **search_path Leakage in Pooled Connections** (Phase 1) — PgBouncer transaction-pooling resets session-level `SET search_path`, causing data to land in wrong schemas. **Mitigation:** Use `SET LOCAL` inside GORM transactions, not connection-level `SET`. Audit SchemaTablePrefix plugin. Use PgBouncer session-pooling mode for tenant DB.
3. **Academic Year Rollover Without Data Cleanup** (Phase 4) — No automated rollover means manual data carry-forward creates duplication and inconsistencies. **Mitigation:** Build End-of-Year workflow with grade finalization, student promotion, data archiving, and session lifecycle management.
4. **Grade Calculation Precision Loss** (Phase 5) — Float32 scores stored in JSONB accumulate micro-drift (±0.01 per multiplication). Over a term, boundary-value scores (74.98% displayed as B2 instead of A1) cause disputes. **Mitigation:** Store all scores as integer basis points (7500 = 75.00%). Define "round half away from zero" as platform policy. Add boundary test suite.
5. **WAEC External Exam Records Mixed with Internal Grades** (Phase 4) — Board-certified WAEC results (A1-F9) and internal school grades serve different purposes. Mixing them causes transcript inaccuracy and university admission disputes. **Mitigation:** Separate `ExternalExamResult` model with exam type, sitting number, grade (A1-F9), credit flag. Never feed into internal GPA.
6. **Cross-Tenant Analytics Without Schema Awareness** (Phase 3) — ReportBuilder has a TODO at `service.go:148` and doesn't actually query data. Building cross-schema queries as UNION ALL loops will fail at scale. **Mitigation:** Build analytics schema with materialized views refreshed on schedule from the start.
7. **Parent Communication Degradation** (Phase 6) — "Sent to provider" ≠ "delivered." No delivery webhooks wired for Twilio/SendGrid. Rate limits discovered during bulk events. **Mitigation:** Implement delivery receipt webhooks, contact validation jobs, per-parent channel preference, per-school rate limiting.

## Implications for Roadmap

Based on research, the suggested phase structure is:

### Phase 1: Foundation Hardening (Immediate)
**Rationale:** Every subsequent phase depends on reliable infrastructure. Migration fan-out failures, provisioning race conditions, and search_path leaks are existential risks that compound as tenant count grows. PDF generation and cron scheduling are blocking dependencies for later phases.

**Delivers:** Production-safe multi-tenant infrastructure, PDF capability, scheduled jobs.

**Stack additions:** Gotenberg v8.34.0, robfig/cron v3

**Addresses from FEATURES.md:** (infrastructure — no feature gaps addressed directly)

**Avoids from PITFALLS.md:**
- Pitfall 1: Migration fan-out → per-schema locking + retry + CI validation
- Pitfall 3: search_path leakage → transaction-based isolation audit + PgBouncer config
- Pitfall 11: Provisioning race conditions → transactional flow + timeout + cancellation

**Implementation items:**
1. Migration infrastructure: per-schema advisory locks, `migration_errors` table, retry CLI
2. Search_path audit: verify SchemaTablePrefix uses `SET LOCAL` in transactions
3. Provisioning hardening: transactional CREATE SCHEMA → migrations → seed with full rollback
4. Gotenberg integration: Docker container + Go client wrapper + HTML→PDF pipeline
5. robfig/cron integration: CronRunner + Asynq task delegation pattern
6. PDF pipeline: Connect existing HTML report cards → Gotenberg → downloadable PDF

### Phase 2: Critical Table-Stakes Features (Near-term)
**Rationale:** Student Health Records and Discipline Management are the #1 gap vs. Nigerian competitors (sERP, EduSync, SchoolOS). CA/Exam Split Grading and Fee Structure verification are blocking for Nigerian market fit. These features should ship before active sales expansion.

**Delivers:** Nigerian market parity on key features.

**Stack additions:** disintegration/imaging (for student photos, thumbnail generation)

**Addresses from FEATURES.md:**
- Student Health Records (immunizations, allergies, medications, screenings)
- Discipline / Behavior Management (incidents, detention, suspension, parent alerts)
- CA/Exam Split Grading Configuration (verify depth, add if missing)
- Fee Structure Configuration (NGN) — verify existing finance module covers Nigerian complexity

**Avoids from PITFALLS.md:**
- Pitfall 9: Sum-to-100 enforcement gaps — add DB-level constraint from the start

**Implementation items:**
1. Health module: immunization tracking, allergy alerts, medication log, nurse visit records
2. Discipline module: incident types, behavior categories, detention/suspension workflow, parent SMS alerts
3. Gradebook audit: verify CA/Exam split support in score module
4. Finance audit: verify Nigerian fee complexity (per-class fee structures, waivers, term installments)

### Phase 3: Communication & Calendar (Near-term)
**Rationale:** Parent-teacher communication is partially built — the missing conversation model is a relatively contained enhancement. WhatsApp and iCal export are low-complexity, high-value features that leverage existing Twilio and timetable infrastructure. This phase can run in parallel with Phase 2.

**Delivers:** Enhanced parent-teacher messaging, calendar sync, WhatsApp channel.

**Stack additions:** golang-ical, FCM (appleboy/go-fcm)

**Addresses from FEATURES.md:**
- Parent-teacher conversation system (FEATURES: student timetable portal)
- WhatsApp Notification Integration
- Parent-Teacher Conference Management (can use conversation + calendar infrastructure)

**Implements from ARCHITECTURE.md:**
- Parent-teacher communication (conversation model, file attachments, real-time delivery)
- iCal export (Tier 1: download endpoint)

**Avoids from PITFALLS.md:**
- (Communication delivery failures addressed in Phase 6)

**Implementation items:**
1. Conversation model + enhanced messages module (threaded, file attachments, read receipts)
2. Real-time message delivery via existing WebSocket hub
3. Parent inbox in parent dashboard (unread count, conversation list)
4. iCal export endpoint (RFC 5545, recurrence support)
5. WhatsApp notification channel (Twilio WhatsApp API)
6. Conference management: slot booking, reminders

### Phase 4: Academic Workflow (Medium-term)
**Rationale:** End-of-Year Rollover, WAEC integration, and stable student identifiers are complex but critical for schools completing a full academic year. These features have deep dependencies across modules and must be built before any school's first year-end. Timetable mutation safety is needed before year-end schedule changes.

**Delivers:** Complete academic year lifecycle, WAEC exam tracking, safe timetable changes.

**Addresses from FEATURES.md:**
- End-of-Year Rollover / Student Promotion
- WAEC/NECO integration & credit tracking
- Graduation / Degree Audit Tracking

**Avoids from PITFALLS.md:**
- Pitfall 4: Academic year rollover → automated promotion + grade archiving + session lifecycle
- Pitfall 8: WAEC integration → separate external exam model + credit tracking
- Pitfall 10: Student ID instability → stable admission_number + reactivation workflow
- Pitfall 13: Timetable-attendance disconnect → soft-change policy + re-parenting + integrity checks

**Implementation items:**
1. End-of-Year workflow: grade finalization validation, student promotion, data archiving, session lifecycle
2. ExternalExamResult model: exam_type (WAEC/NECO), sitting_number, grade (A1-F9), credit flag
3. Student admission_number as stable cross-year identifier
4. Student reactivation workflow (re-enrollment without duplication)
5. Timetable mutation safety: status-based changes, attendance re-parenting, integrity reports
6. WAEC credit count computation (A1-C6 including English + Math)
7. Separate transcript sections for internal vs. external exam results

### Phase 5: Gradebook Hardening (Medium-term)
**Rationale:** Grade precision and data integrity are non-negotiable in education. Float32 accumulation errors, missing DB-level sum-to-100 enforcement, and the absence of grade freeze will cause real disputes at the first year-end. This phase must complete before any school finishes a full academic year on the platform.

**Delivers:** Financially/scholastically reliable gradebook.

**Addresses from FEATURES.md:**
- (Internal quality — no new features, but enables confidence in existing features)

**Avoids from PITFALLS.md:**
- Pitfall 5: Grade calculation precision → integer basis point storage + boundary test suite
- Pitfall 9: Sum-to-100 enforcement → DB trigger + proportional normalization + recalculation queue
- Pitfall 12: Report card timing → grade freeze + snapshotting + reissue workflow

**Implementation items:**
1. Integer basis-point migration for all score storage (7500 = 75.00%)
2. Rounding policy: define "round half away from zero" platform-wide
3. DB-level BEFORE INSERT/UPDATE trigger on grade_items for sum-to-100 enforcement
4. Post-mutation recalculation queue (asynq task)
5. Grade freeze: session.status → `completed` locks all grades read-only
6. Report card snapshotting: store grade values at generation time, not live references
7. Reissue workflow: versioned corrections with admin override and audit trail
8. Boundary test suite: verify all WAEC grade thresholds at ±0.01

### Phase 6: Scaling & Reliability (Growth)
**Rationale:** Communication reliability (delivery tracking), pg_catalog monitoring, and analytics infrastructure become urgent as tenant count grows and feature usage increases. These are not blocking for initial sales but become critical at ~100+ tenants and 10K+ daily active users.

**Delivers:** Enterprise-grade reliability, monitoring, cross-tenant analytics.

**Stack additions:** Sentry (sentry-go)

**Addresses from FEATURES.md:**
- (Operational excellence — enables confidence at scale)

**Avoids from PITFALLS.md:**
- Pitfall 2: pg_catalog bloat → instrument metrics, design hybrid tenant tiers at 300 schemas
- Pitfall 6: Cross-tenant analytics → analytics schema with materialized views
- Pitfall 7: Communication reliability → delivery webhooks + contact validation + rate limiting

**Implementation items:**
1. Twilio/SendGrid delivery webhooks: track `delivery_status` through delivered/failed/bounced
2. Parent contact validation job: pre-term phone/email verification
3. Per-parent channel preference (SMS/Email/WhatsApp/In-App) with fallback
4. Per-school rate limiting for communications (token bucket)
5. pg_catalog monitoring: track total catalog rows, query planning time as p95 metric
6. Alert when schema count >300 or catalog query time >50ms
7. Analytics schema with materialized views for cross-tenant reporting
8. Sentry integration: error aggregation, performance monitoring, release tracking

### Phase 7+: Growth & Expansion (Long-term)

**Rationale:** These are valuable but not blocking for market entry. Multi-campus management addresses school chains (growing segment in Nigeria). NERDC curriculum alignment is high-effort but high-value. OAuth/SSO is a quality-of-life improvement. i18n is deferred until backend communication templates are internationalized first.

**Delivers:** Enterprise expansion features.

**Stack additions:** Goth, go-i18n, react-i18next

**Addresses from FEATURES.md:**
- Multi-Campus Management
- NERDC Curriculum Alignment
- WAEC/NECO CBT-Ready Certification
- OAuth/SSO (Google Workspace, Microsoft 365)
- Low-Bandwidth / Offline PWA
- LEA/State Compliance Dashboards
- AI-Powered Report Card Comments
- i18n (backend → frontend)

**Implementation items:**
1. Multi-campus: district model, cross-schema queries, district admin dashboard
2. NERDC curriculum database: pre-loaded subjects/classes JSS1-SSS3
3. WAEC CBT mock exam mode (extend CBA module)
4. OAuth/SSO via Goth: Google Workspace, Microsoft 365 login alongside email/password
5. Offline PWA: service workers, IndexedDB, sync queues
6. AI report card comments: assessment data → AI prompt → personalized remarks
7. State compliance dashboards: research Lagos/Rivers requirements
8. Backend i18n: communication templates first, then API error messages
9. Frontend i18n: react-i18next, consume locale from backend accept-language

### Phase Ordering Rationale

- **Foundation before features** — Migration fan-out, search_path isolation, and provisioning reliability underpin everything. A data leak or partial migration corrupts all subsequent work.
- **Table-stakes before differentiators** — Health records and discipline are minimum expectations. Building WhatsApp or AI comments is pointless if basic SIS features are missing.
- **Academic workflow before gradebook hardening** — End-of-year rollover and WAEC integration define the data lifecycle. Grade precision fixes touch the same data model — better to migrate once after the model is stable.
- **Gradebook hardening before scaling** — Float32 precision affects all score computation from day one. Fixing it after schools have a year of data is a painful backfill migration.
- **Scaling/reliability last** — Delivery tracking and pg_catalog monitoring become urgent only at scale. The system can safely operate without them for the first 50-100 tenants.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Health Records):** Nigerian school health record practices (immunization schedules, common allergies, screening protocols). Verify with school administrators.
- **Phase 3 (iCal):** `golang-ical` library — needs verification with Context7. Recurrence model design for timetables needs careful modeling.
- **Phase 4 (WAEC):** WAEC result CSV import format, grade boundary configuration, multi-sitting tracking requirements. Nigerian education regulations.
- **Phase 6 (pg_catalog):** Exact trigger thresholds for hybrid tenant tier migration. PostgreSQL 17+ catalog improvements.
- **Phase 7 (Multi-Campus):** Nigerian school chain operational models — do they share teachers, curricula, or just administration?
- **Phase 7 (State Compliance):** Research Lagos, Rivers, FCT data submission requirements — varies by state.

**Phases with standard patterns (skip deeper research):**
- **Phase 1 (Foundation):** Gotenberg, robfig/cron, provisioning patterns — well-documented infrastructure patterns.
- **Phase 3 (WhatsApp):** Twilio WhatsApp API — existing Twilio integration pattern extends directly.
- **Phase 5 (Grade Precision):** Integer basis-point storage, rounding policies — well-documented in education domain.
- **Phase 7 (OAuth/SSO):** Goth library — 30+ providers, well-documented patterns. Context7 verified.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Gotenberg (12.5K stars, 68M+ pulls), robfig/cron (5K+ stars), Goth (Context7 86), imaging (Context7 97.5) all verified. Lower confidence on `golang-ical` (300 stars, web search only) and `nativebpm/gotenberg-client` (newer library). |
| Features | **HIGH** | Feature gaps identified via competitive analysis of 9+ SIS platforms (PowerSchool, FACTS, OpenSIS, Gradelink, sERP Nigeria, SchoolOS, EduSync, EduKit, RosarioSIS). Nigerian-specific features validated against sERP Nigeria, SchoolOS, EduSync product pages. Existing feature set confirmed via codebase audit. |
| Architecture | **HIGH** | All architecture findings verified against actual codebase files (`backend/internal/ws/`, `backend/internal/modules/notifications/`, `backend/internal/modules/messages/`, `backend/internal/modules/reportbuilder/`, etc.). Where features are "not built," this is confirmed by absence. Existing WebSocket hub, notification service, and communication providers verified as functional. |
| Pitfalls | **HIGH** | 13 pitfalls identified from: codebase audit (migration_service.go, schema_db.go, score/service.go), SIS post-mortems (PowerSchool, Classter, EdPayU), grade calculation analysis (Blackbaud, Moodle, CodePex), multi-tenant Postgres scaling guides (Cadence, Planetscale, AWS SaaS Lens), and academic year rollover guides (Clever, PowerSchool, Aequitas). All sources are current (2024-2026). |

**Overall confidence:** HIGH

### Gaps to Address

1. **Nigerian school administrator validation** — Feature importance and priority should be validated with actual Nigerian school administrators before committing to Phase 2 sequencing. Competitive analysis is a proxy, not direct feedback.
2. **Existing finance module depth (NGN complexity)** — The `finance` module's ability to handle Nigerian fee structures (waivers, per-class fees, term installments, late fees, debtors lists) needs direct codebase examination. If it's already sufficient, this de-risks Phase 2.
3. **WAEC CSV import format** — The exact format of WAEC result exports is not well-documented publicly. May need to obtain sample data from a partner school during Phase 4 planning.
4. **pg_catalog bloat thresholds** — The ~500 schema ceiling is based on community reports (Cadence, Planetscale). Exact thresholds depend on PostgreSQL version (17+ may have improvements), hardware, and query patterns. Monitor proactively rather than pre-optimize.
5. **Offline PWA feasibility** — Service worker architecture for a data-heavy SIS with 39 backend modules is complex. Feasibility study needed before committing to Phase 7 scope.

## Sources

### Primary (HIGH confidence — codebase-verified)
- `backend/internal/ws/` — WebSocket hub with JWT auth, rooms, metrics. Fully built.
- `backend/internal/modules/notifications/` — Notification CRUD + WebSocket broadcast. Fully built.
- `backend/internal/modules/communication/` — SendGrid + Twilio providers. Fully built.
- `backend/internal/modules/messages/` — Message CRUD, needs conversation enhancement.
- `backend/internal/modules/reportbuilder/` — `service.go:148` has TODO for data querying.
- `backend/internal/modules/reportcard/` — Report card generation with templates. Fully built.
- `backend/pkg/pdf/generator.go` — HTML-only PDF generation, no actual PDF output.
- `backend/internal/database/tenant/migration_service.go` — Concurrent migration runner.
- `backend/internal/database/tenant/schema_db.go` — SchemaTablePrefix plugin.
- `backend/internal/database/tenant/provisioning.go` — Synchronous provisioning pipeline.
- `backend/internal/modules/score/service.go` — Float32 score arithmetic.

### Primary (HIGH confidence — official documentation)
- Context7: `/gotenberg/gotenberg/v8` — PDF generation (MEDIUM confidence on version)
- Context7: `/markbates/goth` — OAuth/SSO (score 86)
- Context7: `/disintegration/imaging` — Image processing (score 97.5)
- Context7: `/robfig/cron` — Job scheduling (score 87+)
- Context7: `/nicksnyder/go-i18n` — i18n (score 87+)
- npm registry: `@react-pdf/renderer@4.5.1` — Client-side PDF preview
- PowerSchool SIS product page — Feature reference
- OpenSIS documentation + GitHub — Feature reference
- Gradelink features page — Feature reference
- sERP Nigeria, SchoolOS Nigeria, EduSync Nigeria product pages — Nigerian competitor features
- Clever school year rollover guide — Academic workflow best practices
- PowerSchool SIS EOY guide — Year-end procedures

### Secondary (MEDIUM confidence — community/aggregated sources)
- TrustRadius, Capterra, Software Advice — SIS feature reviews and complaints
- Nigerian government CBT transition announcement (technext24.com) — WAEC policy direction
- Cadence blog (2026-05-22) — Multi-tenant PostgreSQL scaling patterns
- Planetscale approaches to tenancy (2026-04-21) — Tenant architecture comparison
- Aequitas K-12 SIS rollover guide — Academic year lifecycle
- Blackbaud LMS grading troubleshooting — Grade precision analysis
- Moodle SCORM grade rounding bug analysis — Float precision in education
- Easy!Appointments blog — CalDAV integration patterns
- Edunation, HelloParent — Parent-teacher communication patterns

### Tertiary (LOW confidence — single source, needs validation)
- Nigerian fee structure complexity (sERP Nigeria product page) — Needs codebase audit of existing finance module
- State compliance requirements (Lagos, Rivers, FCT) — Needs direct research
- WAEC CSV export format — Needs sample data from partner school
- Exact pg_catalog bloat thresholds at various PostgreSQL versions — Needs benchmarking

---

*Research completed: 2026-07-18*
*Ready for roadmap: yes*
