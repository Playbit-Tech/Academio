# Requirements: Academio

**Defined:** 2026-07-18
**Core Value:** Students can be enrolled, tracked through their academic journey, and assessed — with every school's data isolated and secure in its own tenant schema.

## v1 Requirements

Requirements for next phase of development. Each maps to roadmap phases.

### Infrastructure & Foundation

- [x] **INFRA-01**: Migration infrastructure hardened with per-schema advisory locks, migration_errors table, retry CLI, and CI migration-count validation
- [ ] **INFRA-02**: SchemaTablePrefix plugin audited — verify `SET LOCAL` in transactions (not connection-level `SET search_path`) for PgBouncer compatibility
- [ ] **INFRA-03**: Provisioning pipeline hardened with transactional CREATE SCHEMA → migrations → seed and full rollback on failure
- [ ] **INFRA-04**: Gotenberg v8.x integrated for server-side HTML→PDF conversion of report cards, transcripts, certificates
- [ ] **INFRA-05**: Cron job scheduler (robfig/cron v3) integrated for nightly backups, weekly reports, monthly billing — delegates to Asynq for execution
- [ ] **INFRA-06**: PDF pipeline connecting existing HTML report card generator → Gotenberg → downloadable PDF served to users

### Student Health Records

- [ ] **HEALTH-01**: Student immunization tracking (polio, BCG, hepatitis, routine schedule) per Nigerian school requirements
- [ ] **HEALTH-02**: Student allergy records with alerting on medical profiles and attendance forms
- [ ] **HEALTH-03**: Medication log (prescriptions, dosages, administration times)
- [ ] **HEALTH-04**: Nurse visit records screening module
- [ ] **HEALTH-05**: Exportable health report (PDF via Gotenberg) for parent records

### Discipline / Behavior Management

- [ ] **DISC-01**: Incident logging with behavior categories, severity levels, descriptions
- [ ] **DISC-02**: Detention and suspension workflow (assignment, tracking, completion)
- [ ] **DISC-03**: Parent SMS/email notification on incidents (via existing Communication module)
- [ ] **DISC-04**: Conduct report rollup into report cards
- [ ] **DISC-05**: Behavior analytics dashboard (incident trends by class, student, type)

### CA/Exam Split Grading Configuration

- [ ] **GRADE-01**: CA/Exam split ratio configuration (30/70, 40/60, 50/50 per subject) tied to academic sessions
- [ ] **GRADE-02**: WAEC A1-F9 grading scale mapping alongside percentage scores
- [ ] **GRADE-03**: DB-level sum-to-100 enforcement trigger on grade_items (post-migration)

### Fee Structure Configuration (NGN)

- [ ] **FEE-01**: Nigerian fee itemization (tuition, PTA, development, exam, sports, uniform, bus fees)
- [ ] **FEE-02**: Per-class/term fee structure configuration
- [ ] **FEE-03**: Fee waivers and partial payment tracking
- [ ] **FEE-04**: Debtors list and automated fee reminders

### Enhanced Parent-Teacher Communication

- [ ] **COMM-01**: Conversation model with threading and read receipts in Messages module
- [ ] **COMM-02**: File attachments in parent-teacher messages
- [ ] **COMM-03**: Real-time delivery via existing WebSocket hub
- [ ] **COMM-04**: Parent inbox in parent dashboard (unread count, conversation list)
- [ ] **COMM-05**: WhatsApp notification channel via Twilio WhatsApp API
- [ ] **COMM-06**: iCal export endpoint for timetable calendar sync (RFC 5545)
- [ ] **COMM-07**: Parent-teacher conference management (slot booking, reminders)

### Academic Year Lifecycle

- [ ] **YEAR-01**: End-of-Year workflow — grade finalization validation, session completion
- [ ] **YEAR-02**: Student promotion workflow (auto-promote to next class/graduate)
- [ ] **YEAR-03**: Grade archiving on session completion (snapshot current scores)
- [ ] **YEAR-04**: Student admission_number as stable cross-year identifier
- [ ] **YEAR-05**: Student reactivation workflow (re-enrollment without duplication)

### WAEC External Exam Integration

- [ ] **WAEC-01**: ExternalExamResult model with exam_type (WAEC/NECO), sitting_number, grade (A1-F9), credit flag
- [ ] **WAEC-02**: Separate transcript sections for internal vs external exam results (NEVER mix)
- [ ] **WAEC-03**: WAEC credit count computation (A1-C6 including English + Mathematics)
- [ ] **WAEC-04**: Multi-sitting tracking (best result per subject across sittings)
- [ ] **WAEC-05**: WAEC result CSV import from board-provided exports

### Gradebook Hardening

- [ ] **PREC-01**: Integer basis-point score storage migration (7500 = 75.00%) — replace float32 in JSONB
- [ ] **PREC-02**: "Round half away from zero" defined as platform-wide rounding policy
- [ ] **PREC-03**: DB-level BEFORE INSERT/UPDATE trigger on grade_items enforcing sum-to-100
- [ ] **PREC-04**: Post-mutation recalculation queue (Asynq task) for cascading score updates
- [ ] **PREC-05**: Grade freeze on session.status → `completed` (all grades read-only)
- [ ] **PREC-06**: Report card snapshotting at generation time (store values, not live references)
- [ ] **PREC-07**: Versioned grade corrections with admin override and audit trail
- [ ] **PREC-08**: Boundary test suite verifying all WAEC grade thresholds at ±0.01 precision

### Communications Reliability

- [ ] **RELY-01**: Twilio/SendGrid delivery webhooks tracking status through delivered/failed/bounced
- [ ] **RELY-02**: Parent contact validation job (pre-term phone/email verification)
- [ ] **RELY-03**: Per-parent channel preference (SMS/Email/WhatsApp/In-App) with fallback chain
- [ ] **RELY-04**: Per-school rate limiting for communications (token bucket)

### Monitoring & Observability

- [ ] **OBSV-01**: pg_catalog monitoring — track total catalog rows, query planning time as p95 metric
- [ ] **OBSV-02**: Alert when tenant schema count exceeds 300 or catalog query time exceeds 50ms
- [ ] **OBSV-03**: Analytics schema with materialized views for cross-tenant reporting
- [ ] **OBSV-04**: Sentry integration for error aggregation and performance monitoring

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Multi-Campus Management

- **CAMP-01**: District/organization model aggregating multiple schools
- **CAMP-02**: Cross-schema queries for consolidated district dashboards
- **CAMP-03**: District admin role with visibility across campuses
- **CAMP-04**: Shared resources (teachers shared across campuses) with schema-per-campus isolation

### NERDC Curriculum Alignment

- **CURR-01**: Pre-loaded Nigerian curriculum database (JSS1-SSS3 subjects per term)
- **CURR-02**: Curriculum-aligned lesson plan templates
- **CURR-03**: Scheme of work generation from curriculum

### OAuth/SSO

- **AUTH-05**: Google Workspace OAuth login for staff
- **AUTH-06**: Microsoft 365 OAuth login for staff
- **AUTH-07**: Account linking between OAuth and existing email/password accounts

### Advanced Features

- **ADVN-01**: AI-powered report card comment generation from assessment data
- **ADVN-02**: WAEC/NECO CBT mock exam mode (extend existing CBA module)
- **ADVN-03**: Low-bandwidth / offline PWA mode (service workers, IndexedDB, sync queues)
- **ADVN-04**: i18n — backend communication templates + frontend translations
- **ADVN-05**: State compliance dashboards (Lagos, Rivers, FCT data submission requirements)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Native mobile apps | PWA strategy sufficient for v1; SchoolOS proves web-first works in Nigerian market |
| Video conferencing | Out of scope for school management; external tools (Zoom, Google Meet) integrate via links |
| Real-time collaboration | No Google Docs-style concurrent editing needed |
| Full HRIS/payroll engine | Integrate with Nigerian payroll providers (Paystack, Remita) instead of building payroll |
| Exam board content licensing | Focus on school-created mock exams; WAEC/NECO licensing is separate |
| E-commerce / marketplace | Out of scope for SIS |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| INFRA-05 | Phase 1 | Pending |
| INFRA-06 | Phase 1 | Pending |
| HEALTH-01 | Phase 2 | Pending |
| HEALTH-02 | Phase 2 | Pending |
| HEALTH-03 | Phase 2 | Pending |
| HEALTH-04 | Phase 2 | Pending |
| HEALTH-05 | Phase 2 | Pending |
| DISC-01 | Phase 2 | Pending |
| DISC-02 | Phase 2 | Pending |
| DISC-03 | Phase 2 | Pending |
| DISC-04 | Phase 2 | Pending |
| DISC-05 | Phase 2 | Pending |
| GRADE-01 | Phase 2 | Pending |
| GRADE-02 | Phase 2 | Pending |
| GRADE-03 | Phase 2 | Pending |
| FEE-01 | Phase 2 | Pending |
| FEE-02 | Phase 2 | Pending |
| FEE-03 | Phase 2 | Pending |
| FEE-04 | Phase 2 | Pending |
| COMM-01 | Phase 3 | Pending |
| COMM-02 | Phase 3 | Pending |
| COMM-03 | Phase 3 | Pending |
| COMM-04 | Phase 3 | Pending |
| COMM-05 | Phase 3 | Pending |
| COMM-06 | Phase 3 | Pending |
| COMM-07 | Phase 3 | Pending |
| YEAR-01 | Phase 4 | Pending |
| YEAR-02 | Phase 4 | Pending |
| YEAR-03 | Phase 4 | Pending |
| YEAR-04 | Phase 4 | Pending |
| YEAR-05 | Phase 4 | Pending |
| WAEC-01 | Phase 4 | Pending |
| WAEC-02 | Phase 4 | Pending |
| WAEC-03 | Phase 4 | Pending |
| WAEC-04 | Phase 4 | Pending |
| WAEC-05 | Phase 4 | Pending |
| PREC-01 | Phase 5 | Pending |
| PREC-02 | Phase 5 | Pending |
| PREC-03 | Phase 5 | Pending |
| PREC-04 | Phase 5 | Pending |
| PREC-05 | Phase 5 | Pending |
| PREC-06 | Phase 5 | Pending |
| PREC-07 | Phase 5 | Pending |
| PREC-08 | Phase 5 | Pending |
| RELY-01 | Phase 6 | Pending |
| RELY-02 | Phase 6 | Pending |
| RELY-03 | Phase 6 | Pending |
| RELY-04 | Phase 6 | Pending |
| OBSV-01 | Phase 6 | Pending |
| OBSV-02 | Phase 6 | Pending |
| OBSV-03 | Phase 6 | Pending |
| OBSV-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 56 total
- Mapped to phases: 56
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-18*
*Last updated: 2026-07-18 after roadmap creation*
