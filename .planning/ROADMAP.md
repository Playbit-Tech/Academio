# Roadmap: Academio

## Overview

Academio is a mature multi-tenant school management system (~58K Go backend, 39 modules) serving K-12 and higher education institutions in Nigeria. This roadmap delivers the remaining production-hardening and Nigerian-market-fit features across six disciplined phases — starting with infrastructure foundations (migration locking, search_path audit, provisioning, PDF generation, cron scheduling), then building critical table-stakes features (health records, discipline, CA/Exam grading, fee structure), enhancing parent-teacher communication (conversations, iCal, WhatsApp, conferences), completing the academic year lifecycle (rollover, WAEC integration, student promotion), hardening the gradebook (integer precision, sum-to-100 enforcement, grade freeze), and finishing with scaling and reliability (delivery webhooks, monitoring, analytics).

## Phases

- [ ] **Phase 1: Foundation Hardening** - Production-safe multi-tenant infrastructure, PDF generation, and scheduled job runner
- [ ] **Phase 2: Critical Table-Stakes Features** - Student health records, discipline management, CA/Exam grading config, Nigerian fee structure
- [ ] **Phase 3: Communication & Calendar** - Threaded messaging with attachments, real-time delivery, iCal export, WhatsApp channel, conference management
- [ ] **Phase 4: Academic Workflow** - End-of-year rollover, WAEC/NECO external exam integration, stable student identifiers, promotion
- [ ] **Phase 5: Gradebook Hardening** - Integer basis-point score storage, sum-to-100 triggers, grade freeze, report card snapshotting
- [ ] **Phase 6: Scaling & Reliability** - Delivery webhooks, contact validation, communication rate limiting, pg_catalog monitoring, cross-tenant analytics, Sentry

## Phase Details

### Phase 1: Foundation Hardening
**Goal**: Production-safe multi-tenant infrastructure with reliable migrations, schema isolation, provisioning, PDF generation, and scheduled jobs
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. Admin can run schema migrations across all tenant schemas with per-schema advisory locks — partial failures are recorded in migration_errors table and retryable via CLI, with CI validating migration count parity
  2. Schema isolation is guaranteed through PgBouncer — SchemaTablePrefix plugin uses `SET LOCAL` inside GORM transactions, never connection-level `SET search_path`
  3. Tenant provisioning is fully transactional — `CREATE SCHEMA → migrations → seed` either completes entirely or rolls back with no orphaned schemas
  4. User can generate and download a PDF report card, transcript, or certificate — existing HTML templates render via Gotenberg v8.x headless Chromium with proper page breaks
  5. Scheduled jobs (nightly backups, weekly reports, monthly billing) execute automatically on configured cron intervals, delegating to Asynq for fault-tolerant execution
**Plans**: 5 plans (all created)

Plans:
- [x] 01-01: Migration infrastructure hardening — per-schema advisory locks, migration_errors table, retry CLI, CI migration-count validation
- [ ] 01-02: SchemaTablePrefix search_path audit — verify SET LOCAL in transactions, PgBouncer compatibility
- [ ] 01-03: Provisioning pipeline hardening — transactional CREATE SCHEMA → migrations → seed with full rollback
- [ ] 01-04: Gotenberg PDF integration — Docker config, Go client wrapper, report card/transcript/certificate PDF pipeline
- [ ] 01-05: Cron job scheduler — robfig/cron v3 integration, Asynq task delegation, backup/report/billing job templates

**Plans Directory**: `.planning/plans/phase-1/`

### Phase 2: Critical Table-Stakes Features
**Goal**: Nigerian market parity with student health records, discipline management, CA/Exam split grading, and itemized fee structures
**Depends on**: Phase 1 (needs PDF infrastructure for health report export, stable provisioning)
**Requirements**: HEALTH-01, HEALTH-02, HEALTH-03, HEALTH-04, HEALTH-05, DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, GRADE-01, GRADE-02, GRADE-03, FEE-01, FEE-02, FEE-03, FEE-04
**Success Criteria** (what must be TRUE):
  1. School nurse can log and view immunization records (polio, BCG, hepatitis, routine schedule), allergy alerts, medication logs, and visit visit records for any student — with PDF export for parent records
  2. Teacher/administrator can log behavior incidents with categories and severity levels, initiate detention/suspension workflows with completion tracking, and notify parents automatically via SMS/email
  3. Admin can configure CA/Exam split ratios (30/70, 40/60, 50/50) per subject tied to academic sessions, with WAEC A1-F9 grading scale mapped alongside percentage scores
  4. Admin can define Nigerian fee items (tuition, PTA, development, exam, sports, uniform, bus fees) per class/term, configure waivers and partial payments, and view a debtors list with automated fee reminders
  5. Behavioral analytics dashboard shows incident trends filtered by class, student, and incident type — conduct reports roll up into report cards
**Plans**: 4 plans

Plans:
- [ ] 02-01: Student Health Records module — models, CRUD, immunization/alerts/medication/visits, PDF export via Gotenberg
- [ ] 02-02: Discipline/Behavior Management module — incident logging, categories/severity, detention/suspension workflow, parent notifications via existing Communication module, conduct rollup to report cards, analytics dashboard
- [ ] 02-03: CA/Exam split grading configuration — ratio config per subject/term, WAEC A1-F9 scale mapping, DB-level sum-to-100 enforcement
- [ ] 02-04: Fee structure configuration — NGN itemization per class/term, waivers, partial payments, debtors list, automated fee reminders
**UI hint**: yes

### Phase 3: Communication & Calendar
**Goal**: Enhanced parent-teacher messaging with real-time delivery, calendar sync via iCal, WhatsApp notifications, and conference management
**Depends on**: Phase 1 (can run partially parallel with Phase 2)
**Requirements**: COMM-01, COMM-02, COMM-03, COMM-04, COMM-05, COMM-06, COMM-07
**Success Criteria** (what must be TRUE):
  1. Parent and teacher can exchange threaded messages with file attachments in the Messages module — messages deliver in real-time via WebSocket with read receipts
  2. Parent sees unread message count and conversation list in their dashboard — clicking opens the threaded conversation
  3. User can export timetable as iCal file (RFC 5545) for calendar sync with Google Calendar, Apple Calendar, Outlook
  4. Admin can send notifications via WhatsApp channel (Twilio WhatsApp API) alongside existing email/SMS — per-parent channel preference respected
  5. Admin can configure parent-teacher conference slots — parents can book available slots and receive automated reminders
**Plans**: 5 plans

Plans:
- [ ] 03-01: Conversation model & enhanced messaging — threading, file attachments, read receipts, frontend conversation view
- [ ] 03-02: Real-time delivery via WebSocket hub — parent inbox with unread count, conversation list in parent dashboard
- [ ] 03-03: iCal export endpoint (RFC 5545) — timetable calendar sync for Google Calendar, Apple Calendar, Outlook
- [ ] 03-04: WhatsApp notification channel — Twilio WhatsApp API integration, per-parent channel preference management
- [ ] 03-05: Parent-teacher conference management — slot booking, reminders, confirmation workflow
**UI hint**: yes

### Phase 4: Academic Workflow
**Goal**: Complete academic year lifecycle with automated rollover, WAEC/NECO external exam tracking, and stable student identifiers
**Depends on**: Phase 2 (needs CA/Exam split grading), Phase 3 (needs communication for parent notifications during rollover)
**Requirements**: YEAR-01, YEAR-02, YEAR-03, YEAR-04, YEAR-05, WAEC-01, WAEC-02, WAEC-03, WAEC-04, WAEC-05
**Success Criteria** (what must be TRUE):
  1. Admin can execute end-of-year workflow — grade finalization validation, session completion, grade archiving (snapshot current scores), and student promotion to next class or graduation
  2. Admin can record WAEC/NECO external exam results (A1-F9 grades) with sitting numbers — transcript clearly separates internal grades from board-certified results in two distinct sections
  3. WAEC credit count computes automatically (A1-C6 including English and Mathematics) — multi-sitting tracking shows best result per subject across sittings
  4. Admin can import WAEC results from CSV (board-provided export format) with validation before committing
  5. Student can be re-enrolled using stable admission_number — reactivation workflow restores previous records without data duplication
**Plans**: 4 plans

Plans:
- [ ] 04-01: End-of-Year workflow — grade finalization validation, session completion, grade archiving, session lifecycle management
- [ ] 04-02: Student promotion/graduation workflow — auto-promote to next class, graduate, student reactivation via admission_number
- [ ] 04-03: WAEC external exam model — ExternalExamResult with exam_type/sitting_number/grade/credit_flag, CSV import, credit count computation, multi-sitting tracking
- [ ] 04-04: Stable student identifiers — admission_number as cross-year stable key, re-enrollment without duplication
**UI hint**: yes

### Phase 5: Gradebook Hardening
**Goal**: Financially and scholastically reliable gradebook with integer-precision scores, DB-level constraints, grade freeze, and report card snapshotting
**Depends on**: Phase 4 (needs year-end lifecycle for grade freeze, WAEC thresholds for boundary tests)
**Requirements**: PREC-01, PREC-02, PREC-03, PREC-04, PREC-05, PREC-06, PREC-07, PREC-08
**Success Criteria** (what must be TRUE):
  1. All scores are stored as integer basis points (7500 = 75.00%) — float32 drift eliminated from all computation with "round half away from zero" as platform-wide rounding policy
  2. Grade items automatically enforce sum-to-100 at database level via BEFORE INSERT/UPDATE trigger — post-mutation recalculation queue cascades score updates asynchronously
  3. When a session status changes to `completed`, all grades are frozen (read-only) — no further edits allowed without admin override
  4. Report card generation snapshots grade values at creation time — reissued report cards show the values from that academic period, not current live references
  5. Admin can make versioned grade corrections with full audit trail — each correction recorded with admin ID, timestamp, before/after values, and reason
**Plans**: 5 plans

Plans:
- [ ] 05-01: Integer basis-point score migration — replace float32 in JSONB, "round half away from zero" policy, platform-wide rounding utility
- [ ] 05-02: DB-level sum-to-100 trigger + post-mutation recalculation queue — Asynq task for cascading score updates
- [ ] 05-03: Grade freeze on session completion — read-only enforcement, UI indicators for frozen grades
- [ ] 05-04: Versioned grade corrections — admin override workflow, audit trail, reissue history
- [ ] 05-05: Boundary test suite — verify all WAEC grade thresholds at ±0.01 precision
**UI hint**: yes

### Phase 6: Scaling & Reliability
**Goal**: Enterprise-grade communication reliability, pg_catalog monitoring, cross-tenant analytics, and error aggregation
**Depends on**: Phase 5 (communication reliability after hardened gradebook)
**Requirements**: RELY-01, RELY-02, RELY-03, RELY-04, OBSV-01, OBSV-02, OBSV-03, OBSV-04
**Success Criteria** (what must be TRUE):
  1. Admin can see delivery status (delivered/failed/bounced) for each communication — Twilio/SendGrid delivery webhooks update delivery_status field in real-time
  2. System automatically validates parent contact info (phone/email) before term starts — contacts with invalid entries flagged for admin review
  3. Per-parent channel preference (SMS/Email/WhatsApp/In-App) with automatic fallback chain — per-school token bucket rate limiting prevents provider throttling
  4. Ops team receives alerts when tenant schema count exceeds 300 or catalog query planning time exceeds 50ms — pg_catalog monitoring tracks total rows and p95 planning time
  5. Cross-tenant analytics reports load from materialized views in the analytics schema — Sentry aggregates errors with performance monitoring and release tracking
**Plans**: 6 plans

Plans:
- [ ] 06-01: Twilio/SendGrid delivery webhooks — delivery_status tracking through delivered/failed/bounced
- [ ] 06-02: Parent contact validation job — pre-term phone/email verification, invalid contact flagging
- [ ] 06-03: Per-parent channel preference (SMS/Email/WhatsApp/In-App) with fallback chain; per-school token bucket rate limiting
- [ ] 06-04: pg_catalog monitoring — track total catalog rows, p95 query planning time, alerts at 300 schema / 50ms thresholds
- [ ] 06-05: Analytics schema with materialized views — cross-tenant reporting infrastructure
- [ ] 06-06: Sentry integration — error aggregation, performance monitoring, release tracking
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Hardening | 1/5 | In progress | 2026-07-18 |
| 2. Critical Table-Stakes Features | 0/4 | Not started | - |
| 3. Communication & Calendar | 0/5 | Not started | - |
| 4. Academic Workflow | 0/4 | Not started | - |
| 5. Gradebook Hardening | 0/5 | Not started | - |
| 6. Scaling & Reliability | 0/6 | Not started | - |
