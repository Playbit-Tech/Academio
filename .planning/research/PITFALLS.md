# Domain Pitfalls: School Management System

**Domain:** Multi-tenant K-12 school management (schema-per-tenant, Nigerian curriculum)
**Researched:** 2026-07-18
**Confidence:** HIGH (verified across multiple industry sources and codebase analysis)

## Critical Pitfalls

### Pitfall 1: Schema-per-tenant Migration Fan-Out Failure

**What goes wrong:**
When a new migration is added (new column, new table, index change), it must be applied to every tenant schema. A migration that takes 2 seconds per schema takes 16 minutes for 500 tenants. If one schema out of 500 fails, and the migration tool lacks resume-from-failure capability, half the tenants get migrated and half don't — creating an unrecoverable drift between tenant schemas. Subsequent queries against the unmigrated schemas either crash (column not found) or silently return wrong results (missing data).

This project's `MigrateAllSchemaTenants` at `backend/internal/database/tenant/migration_service.go:188` already runs parallel migrations with a semaphore (concurrency 5), records per-schema success/failure, and handles context cancellation. This is better than many implementations. However, there is no per-schema migration locking or ordering guarantee — if the same migration runs twice on the same schema concurrently (e.g., operator error), it can corrupt the migration tracking table.

**Why it happens:**
- Newcomers to schema-per-tenant don't realize that a single `ALTER TABLE` doesn't apply everywhere
- Migration tools default to single-DB mode; operator must build tenant iteration
- The mental model is "one migration = one DB change," but schema-per-tenant means N changes
- When a migration fails mid-transaction in one schema but not others, recovery is manual

**How to avoid:**
- **Already mitigated:** Concurrent migration runner exists. Extend with:
  - Per-schema advisory lock before migration (prevents double-migration)
  - A `migration_errors` table that records per-schema failure reason and timestamp
  - A "retry failed schemas" CLI command that skips already-migrated schemas and retries only failures
  - Migration ordering documentation: always test a new migration against the largest tenant schema first (worst-case timing), not the smallest
- Add a pre-deploy CI check: ensure the migration count for every active schema matches expected count before deploying new code

**Warning signs:**
- CI/deploy pipeline doesn't include a schema-per-tenant migration test
- Any migration script that starts with a loop over schemas without error isolation
- Developer adds a migration and tests only against the local dev DB (1-2 schemas)
- `SELECT COUNT(*) FROM tenant_schema_migrations WHERE applied = false` returns > 0 in production

**Phase to address:**
Phase 1 (Foundation): Migration infrastructure hardening with locking, retry, and CI validation. The concurrent runner exists but lacks guardrails for production safety.

---

### Pitfall 2: pg_catalog Bloat at Scale (Schema-per-Tenant Ceiling)

**What goes wrong:**
Every table, index, sequence, and view in every tenant schema adds rows to PostgreSQL's system catalogs (`pg_class`, `pg_attribute`, `pg_index`). At ~200 tables per schema and 1,200 schemas (~240,000 catalog entries), `information_schema.tables` queries slow to 383+ ms (sequential scan over 1.3M+ rows). Query planning time degrades for every query because the planner consults the catalog. Migration tools that iterate `information_schema` (like Flyway, Liquibase, some ORM schema diff tools) become unusably slow. The GORM SchemaTablePrefix plugin already adds per-query overhead; degraded planner performance compounds this.

**Why it happens:**
- Schema-per-tenant feels like "clean isolation" and teams don't plan for the ceiling
- The degradation is gradual — no single event triggers an alarm
- Teams assume Postgres handles schemas at any scale (it doesn't past ~500-1,000)
- Connection pooler configuration (PgBouncer session mode) masks the problem by keeping connections alive

**How to avoid:**
- Instrument `pg_stat_user_tables` grouped by schema. Track total catalog row count and query planning time as a p95 metric across schemas. Alert when planning time exceeds 50ms or catalog rows exceed 100K.
- Avoid `information_schema` lookups in application code — query `pg_class` and `pg_namespace` directly for schema discovery
- Plan for the hybrid model before hitting 500 tenants: shared-schema RLS for small/free tenants, schema-per-tenant for paying ones, database-per-tenant for enterprise whales
- Document the schema-per-tenant ceiling in the architecture doc so future engineers don't assume unlimited scale

**Warning signs:**
- Deploy times increase (migrations fan-out starts taking noticeable wall time)
- Application startup slows (GORM auto-migrate iterates schemas)
- Any query that joins `information_schema` starts timing out
- Developers report "GORM is slow" but specific query latency is normal

**Phase to address:**
Phase 2 (Scaling): Instrument catalog metrics, set up per-schema monitoring, and design the hybrid tenant tier architecture before crossing 300 schemas. Phase 6 (Enterprise) if tenant count is still < 200.

---

### Pitfall 3: search_path Leakage in Transaction-Pooled Connections

**What goes wrong:**
The SchemaTablePrefix plugin in `backend/internal/database/tenant/schema_db.go` uses `SET search_path TO school_{id}` to route GORM queries to the correct tenant schema. If the core DB connection pool uses PgBouncer in transaction-pooling mode, the `search_path` is reset between transactions because it's a session-level setting. The next request on the same connection gets the `public` schema (or no schema), silently:
- Creating tables in the wrong schema
- Returning "relation does not exist" errors
- Worse: querying one tenant's data from another tenant's schema if a previous `search_path` leaked

**Why it happens:**
- Transaction pooling is the recommended default for PgBouncer performance
- Schema-per-tenant relies on session-level state that gets discarded in transaction mode
- The app code sets `search_path` correctly, but the pooler undoes it between requests
- Developers test with direct connections (no PgBouncer), so the issue only surfaces in production

**How to avoid:**
- **Already mitigated:** The project sets `search_path` per-transaction using `SET LOCAL` in the migration runner (`migration_service.go:132`). However, the SchemaTablePrefix plugin in `schema_db.go` should also use `SET LOCAL search_path TO ...` inside a GORM session, not a connection-level `SET search_path`.
- Audit the SchemaTablePrefix plugin to ensure every query path wraps in a transaction with `SET LOCAL`. Verify GORM's session creation path uses transactions for all tenant-scoped queries.
- Configure PgBouncer in session-pooling mode for the tenant core DB pool (accepts lower connection reuse in exchange for correctness).
- Add a runtime check on startup that verifies `search_path` isolation — connect, set path to a test schema, run a query, verify it resolves to the correct schema.

**Warning signs:**
- Intermittent "relation does not exist" errors that disappear on retry
- One tenant's data appearing in another tenant's dashboard (tenant isolation breach)
- Errors that reproduce on production but not in development
- PgBouncer configured without awareness of tenant routing

**Phase to address:**
Phase 1 (Foundation): Audit SchemaTablePrefix for transaction-based isolation. Phase 3 (Production Hardening): Add runtime search_path verification tests and PgBouncer configuration review.

---

### Pitfall 4: Academic Year Rollover Without Data Cleanup

**What goes wrong:**
When the system transitions from one academic year to the next, data from the previous year (students, enrollments, grades, attendance) must be promoted, archived, or closed. The common failure pattern: promoting dirty data. Duplicate student records, incomplete demographic fields, orphan enrollments, and unresolved grade discrepancies all get copied into the new year — turning a clean start into a propagated mess. Once the data is in the new year, fixing it requires cross-year reconciliation, which is harder and rarely happens.

For this project, the Session model (`backend/internal/database/models/session.go`) has a `Status` field (`not-active`, `active`, `completed`), but there is no explicit rollover mechanism — no "promote students," "archive old sessions," or "finalize grades" workflow. Sessions are manually created and activated. Without a structured rollover process, schools will manually carry data forward, creating the exact duplication and inconsistency patterns that plague SIS migrations.

**Why it happens:**
- New academic year pressure (staff returning, classes starting) forces speed over quality
- No automated rollover means manual data entry or copy-paste between years
- "Clean it up later" is the default, but later never comes during the year
- The system doesn't enforce that prior-year grades must be finalized before new-year sessions activate

**How to avoid:**
- Build an "End of Year" workflow that: (1) validates all grades are finalized, (2) runs exception reports for missing enrollments, (3) archives attendance and grade data, (4) promotes students to next grade/graduated, (5) creates new-year sessions with status "setup" (not "active"), (6) locks prior-year data read-only.
- Implement a `year_end_checklist` config per school that must be completed before new-year sessions can become "active"
- Add a `finalized` boolean to the Session model — report cards can only be generated for finalized sessions, preventing mid-year grade changes after reports are issued

**Warning signs:**
- Support tickets about "grades from last year showing in this year's reports"
- Students appearing in multiple grade levels simultaneously
- Teachers asking "can I still edit last term's grades?"
- No documented end-of-year process in the codebase or docs

**Phase to address:**
Phase 4 (Academic Workflow): Full academic year lifecycle — rollover workflow, grade finalization, student promotion, session lifecycle management.

---

### Pitfall 5: Grade Calculation Precision Loss (Numeric → Alpha Conversion)

**What goes wrong:**
Nigerian schools use the WAEC A1-F9 scale with specific grade boundaries (A1: 75-100, B2: 70-74, B3: 65-69, etc.). When a student's numeric average (e.g., 67.3%) is converted to an alpha grade (B3), the original precision is lost. If the system then uses the alpha grade for GPA calculation, all students with B3 are treated identically — losing the distinction between 65.1% and 69.9%. This is documented as a known issue in major SIS platforms (it's called out explicitly in the Genesis Grading module documentation and the Blackbaud grade troubleshooting guide).

For this project, the `GradeItem` model stores `MaxScore` as `float32`, scores are stored in a JSONB blob per assessment, and `computeGradeItemsTotal` at `score/service.go:829` calculates proportional totals. The precision chain is: scores are float32 → stored as JSON floats → parsed back to float32 → proportional calculation → assessment total. Each step can introduce ±0.01 drift. Over a term with multiple assessments, these micro-drifts accumulate. If grade boundaries are applied strictly ("≥ 75 is A1") and a student's true score is 74.98 but the system rounds it to 74.9 (displaying as B2 instead of A1), the student loses a credit pass.

This exact class of bug caused the Moodle SCORM rounding issue documented at scale — a grade displays as 80 but the stored value is 79.55, causing a false "Failed" status.

**Why it happens:**
- Developers treat floating point as "good enough" for grades (it isn't for pass/fail boundaries)
- JSONB stores numbers as float64, but Go reads them as float32 (precision loss)
- No fixed-point or integer representation (store as integer basis points: 7500 = 75.00%)
- Rounding policy is undefined: round-half-up? banker's rounding? truncate?
- Display rounding and calculation rounding use different precision (display shows 2 decimals, calculation uses full float)

**How to avoid:**
- Store all scores as integers representing basis points (75.00% = 7500). This eliminates floating-point drift entirely. Convert to decimal only for display.
- Define a single rounding policy for the platform: "round half away from zero" is the education domain standard (K-12 expects 89.5 → 90, not banker's rounding 89.5 → 89).
- The `computeGradeItemsTotal` function should use integer arithmetic: `total += score * 10000 / maxScore` (scaled integer math).
- Add a grade boundary test suite: for every boundary (A1/B2 at 75, B2/B3 at 70, etc.), verify that scores at the boundary ± 0.01 produce the correct grade.
- Document the rounding policy in the API docs so schools know what to expect.

**Warning signs:**
- A student's report card shows a different grade than manual calculation
- Grade distribution shows suspicious clustering at boundary values (too many 74.9, too many 69.9 — suggesting boundary rounding issues)
- Support tickets about "my grade should be higher"
- Comparing the same score across exports gives different totals

**Phase to address:**
Phase 5 (Gradebook & Assessment): Score precision audit, integer storage migration, and boundary test suite. This is a data-model change, so it cannot be done late.

---

### Pitfall 6: Cross-Tenant Analytics Without Schema Awareness

**What goes wrong:**
When reports need to aggregate data across all schools (district-wide analytics, platform-wide enrollment counts, aggregate revenue reports), the natural instinct is to write a query that joins across tenant schemas using `UNION ALL of SELECT ... FROM school_1.table UNION ALL SELECT ... FROM school_2.table ...`. This works in development with 3 test schemas. In production with 300 schemas:
- The query string is megabytes long
- Query planning takes seconds
- If schemas have drifted (different migration states), some UNION branches fail
- The entire report fails if a single schema is down or migrated differently

This project's `reportbuilder` module at `backend/internal/modules/reportbuilder/service.go:148` contains a TODO: "Full data querying will be implemented in the next iteration." It currently returns CSV with metadata only — meaning cross-tenant reporting hasn't been built yet, so this pitfall is imminent when it gets implemented.

**Why it happens:**
- Schema-per-tenant makes cross-tenant queries hard by design (intentional isolation)
- Developers don't realize until they try to write the first cross-schema report
- Using `dblink` or `postgres_fdw` creates a new set of operational headaches
- The easy path is to query each schema in a loop from application code (N+1 query pattern against schemas, which is slow)

**How to avoid:**
- Build a dedicated analytics schema (`analytics`) with materialized views that are refreshed on a schedule. Each view consolidates data from all tenant schemas for reporting. The refresh happens as a background job (asynq is already available in the project).
- For real-time aggregations, use `postgres_fdw` to create a unified view across schemas, but only for a small, fixed set of reporting tables (not the full schema).
- Enforce schema uniformity: the CI migration check (from Pitfall 1) ensures all schemas are at the same migration version. If they drift, the reporting layer must skip or flag mismatched schemas.
- Never write ad-hoc UNION ALL queries across schemas from application code.

**Warning signs:**
- Report generation takes >30 seconds
- "Reports" module returns stale or empty data without explanation
- Developer asks "how do I query data from all schools?"
- The ReportBuilder module is still a placeholder with the TODO comment

**Phase to address:**
Phase 3 (Reporting & Analytics): When the ReportBuilder module is implemented, build the analytics schema approach from the start. Trying to retrofit cross-schema queries onto an existing report builder will be much harder than designing for it upfront.

---

### Pitfall 7: Parent Communication Degradation (Delivery Failures + Rate Limits)

**What goes wrong:**
Schools send attendance alerts, grade notifications, fee reminders, and broadcast announcements via SMS (Twilio), email (SendGrid), and potentially WhatsApp or in-app notifications. Each channel has failure modes:
- **SMS:** Carriers block bulk school SMS as spam (dollar signs, URL shorteners, "act now" language trigger filters). Rate limits per sender ID. DLT/scrub list compliance failures (TRAI regulations in India, similar rules in Nigeria). Sender name vs phone number — some phones block non-number senders.
- **Email:** SendGrid marks bulk school mail as promotional. SPF/DKIM misconfiguration causes delivery to spam. Recipient mailboxes full. Blocklist accumulation from repeated bounces.
- **WhatsApp:** Template approval by Meta takes 24-48 hours. Editing a template after submission invalidates approval. Opted-out users return BLOCKED_BY_USER errors.
- **In-App:** Disabled notifications, outdated app versions, silent OS-level throttling.

The critical failure mode: **silent delivery failure.** The system records "sent" (dispatched to provider) but the provider never delivers (carrier blocked, inbox full, number invalid). The school thinks parents were notified. Parents say they weren't. Trust erodes, and the school blames the software.

The project currently uses SendGrid (email) and Twilio (SMS) via the communications module. There's an asynq queue for email dispatch (`auth/service.go:909,1072`) but no delivery tracking or retry logic beyond dispatch. Twilio has delivery receipts; SendGrid has event webhooks — neither is wired.

**Why it happens:**
- "Sent to provider" is treated as "delivered" (they are not the same)
- No webhook handler for delivery receipts from Twilio/SendGrid
- Rate limits are discovered when report card season triggers 10K SMS in an hour
- Contact info goes stale (parents change numbers, update emails) but the system doesn't validate before sending
- No per-parent channel preference (some want SMS, some want email, some want WhatsApp)

**How to avoid:**
- Implement delivery receipt webhooks for both Twilio (Message Status callback) and SendGrid (Event Webhook). Record `delivery_status` as: `queued`, `sent`, `delivered`, `failed`, `bounced`. Add a delivery dashboard showing success rate by channel.
- Add a "parent contact validation" job: before the first message of a term, validate all parent phone numbers (send a test message, require confirmation reply). Flag invalid numbers for admin review before bulk sends.
- Implement per-parent channel preference (SMS, Email, WhatsApp, In-App) with fallback: try primary channel, if delivery failure persists for 24h, fall back to secondary channel.
- Set rate limits per school per hour based on Twilio/SendGrid account limits. Queue sends with asynq (already available) and add a token-bucket rate limiter per school.
- Add sender name/ID configuration per school — schools should be able to set their SMS sender name and email from-address so parents recognize the sender.

**Warning signs:**
- No delivery receipt webhooks configured in Twilio or SendGrid
- Communication module sends messages but doesn't track delivery status
- No per-school rate limiting for communications
- Support tickets from schools saying "parents didn't receive the alert"
- Communications dashboard shows "sent" count matching "total" (indicating no delivery tracking)

**Phase to address:**
Phase 6 (Communication Reliability): Delivery webhooks, contact validation, channel preferences, rate limiting, and delivery dashboard.

---

### Pitfall 8: WAEC External Exam Records Mixed with Internal Grades

**What goes wrong:**
WAEC WASSCE results (A1-F9 scale) and internal school assessments (continuous assessment + term exams) serve different purposes: WAEC grades are board-certified, used for university admissions, and follow a fixed 9-point scale. Internal grades are school-issued, used for promotion, and may follow a different scale. When the system doesn't clearly separate these two record types:
- University admissions disputes: "This A1 on the transcript — is it from WAEC or from the school?"
- GPA calculations incorrectly include WAEC grades (WAEC grades should not affect internal GPA)
- Credit pass counting (A1-C6) conflates WAEC results with internal exam results
- WAEC sitting numbers (first vs. second attempt) are lost, causing transcript inaccuracies

The project currently has no WAEC-specific model or external exam tracking. The `Assessment` and `GradeItem` models handle continuous assessment and term exams, but there's no mechanism to tag a grade as "external examination (WAEC/NECO)" separate from internal scores. The existing `curriculum.go` has `ActiveContinuousAssessmentID` but no WAEC integration.

**Why it happens:**
- WAEC integration is seen as "just another grade entry" — but it has fundamentally different semantics
- Nigerian schools often enter WAEC results manually into the same gradebook that holds internal results
- The system doesn't differentiate between "school-certified" and "board-certified" grades
- Multi-sitting WAEC results require tracking which attempt each result belongs to

**How to avoid:**
- Add an `ExternalExamResult` model: `student_id`, `exam_type` (WAEC/NECO/other), `sitting_number` (1, 2), `subject`, `grade` (A1-F9), `year`, `credit` (boolean), `verified` (boolean for admin verification). Store separately from internal `Assessment`/`Score` models.
- WAEC external exam results must never feed into internal GPA or class ranking calculations
- Add a computed `waec_credit_count` (number of A1-C6 grades including English + Math) per student for university eligibility reporting
- Add WAEC grade boundary validation: if someone enters 74 as A1, reject it (A1 requires ≥75). The WAEC boundaries are strict and fixed.
- Transcript/report card views should clearly label "External Examination (WAEC)" vs. "School Assessment"

**Warning signs:**
- WAEC grades entered as regular assessments with no differentiation
- No WAEC-specific model or table in the database
- Report cards don't distinguish between school grades and WAEC grades
- No "credit pass count" reporting for SSS3 students
- Multi-sitting WAEC results not tracked (students who retake WAEC)

**Phase to address:**
Phase 4 (Academic Workflow): WAEC integration — external exam models, credit tracking, separate transcript sections. This is uniquely critical for the Nigerian curriculum focus.

---

### Pitfall 9: Grade Item Weight Validation (Sum-to-100) Enforcement Gaps

**What goes wrong:**
This project already has sum-to-100 validation for grade items within an assessment (checked at `academic/service.go:858` and `academic/service.go:1315`). The pitfall is what happens after validation passes: subsequent edits can break the constraint silently. If a teacher adds a new grade item or changes a max score, the existing validation only runs on explicit "validate" operations, not on every save. Between validation passes, grade items can drift out of balance (e.g., max scores summing to 110 instead of 100), causing proportional calculations in `computeGradeItemsTotal` to produce inflated totals. A student might get 85/110 instead of 85/100 — a 77% displayed as something else entirely.

**Why it happens:**
- Validation on create/update but not on every read operation
- MaxScore can be edited independently of the sum-to-100 check
- The validation is in the academic service layer but may not be called from all mutation paths
- No runtime guard in the scoring engine — `computeGradeItemsTotal` doesn't verify the sum of max scores

**How to avoid:**
- Enforce sum-to-100 in the database layer: add a BEFORE INSERT/UPDATE trigger on `grade_items` that rejects changes causing the assessment's grade items to exceed 100% total max score. This catches every code path, not just the ones that call `validateGradeItems()`.
- Add a `total_max_score` check in `computeGradeItemsTotal` at `score/service.go:829`: if the sum of grade item max scores != assessment total, log a warning and normalize proportionally instead of silently using the raw max scores.
- After any grade item mutation, asynchronously recalculate all affected scores (enqueue a background recalculation job via asynq) so discrepancies don't persist until the next explicit revalidation.

**Warning signs:**
- Student scores > assessment total (e.g., a student with 95/100 on an assessment where grade items sum to 120)
- `computeGradeItemsTotal` logs warnings about scores exceeding max (already implemented at line 852 — this code is already detecting the symptom but not the root cause)
- Grade items within an assessment have different max scores that don't sum to 100
- No database constraint enforcing the sum-to-100 rule

**Phase to address:**
Phase 5 (Gradebook & Assessment): Database-level sum-to-100 enforcement, proportional normalization, and post-mutation recalculation queue.

---

### Pitfall 10: Student ID Instability Between Academic Years

**What goes wrong:**
Students have internal IDs (the database primary key or UUID) and may also have external IDs (admission number, registration number, national ID). When students transition between academic years, their class/section assignments change, and sometimes their "student number" changes too. If the system uses the wrong ID for cross-year lookups:
- A student's historical grade records become disconnected from their current profile
- Transcripts show incomplete academic history
- Attendance records from previous terms are orphaned
- Parent-Student relationships break when student ID changes but parent records still reference the old ID

This is explicitly documented as a critical risk by Clever (the major SIS platform): "Clever highly advises against changing these values in the middle of a school year. Doing so presents a significant risk of loss of historical data."

The project uses both a numeric `ID` and a `UUID` on most models. The `User` model (public schema) connects to `Student`/`Teacher`/`Parent` (tenant schema) via `UserID`. Student records in the tenant schema have their own primary key. If a student is re-enrolled (removed and re-added) during a year transition, the tenant-schema student record gets a new ID, breaking the connection to historical scores, attendance, and assessments — all of which reference the old student record ID.

**Why it happens:**
- No clear "stable student identifier" policy — which ID should cross-year lookups use?
- Re-enrollment (e.g., a student leaves mid-year and returns next year) creates a new record rather than reactivating the old one
- Bulk import from XLSX creates new records instead of matching by admission number / national ID
- The system doesn't have a merge or reactivation workflow for returning students

**How to avoid:**
- Designate `admission_number` (or `registration_number`) as the stable student identifier that persists across years. It should be unique, immutable per student, and set on first enrollment. All cross-year queries should use this identifier, not the database primary key.
- Add a "reactivate student" workflow: when importing or enrolling a student whose admission_number already exists (possibly in an archived schema or inactive status), reactivate the existing record rather than creating a new one.
- Add a `merged_into_student_id` field for merge operations (deduplication). When records are merged, the old record is soft-deleted and the field points to the surviving record. Historical scores/attendance are re-parented.
- Validate during academic year rollover: generate a report of students whose records changed IDs between years.

**Warning signs:**
- Student's academic history shows gaps when viewed across years
- "Student not found" errors when looking up a returning student by admission number
- Multiple student records with the same name but different IDs
- Parents can see one child's grades but not another's on the same account
- Bulk import creates duplicates instead of matching existing students

**Phase to address:**
Phase 4 (Academic Workflow): Stable student identifier policy, reactivation workflow, and merge capability. This directly enables clean academic year transitions.

---

### Pitfall 11: Provisioning Race Conditions and Incomplete Schema Setup

**What goes wrong:**
The project's `ProvisionSchool` at `provisioning.go:37` is synchronous: it creates the schema, runs migrations, seeds data (levels, subjects, assessments), and sets the school's status to "active." The frontend polls until `database_status = 'active'`. This works for sequential provisioning. Under concurrent provisioning (two schools created simultaneously), the seed operations can collide:
- Seed functions that query for existing data by name may find a partial dataset from the other provisioning
- Schema names are unique per school, so no direct schema collision — but the `public` schema `schools` table has concurrent updates
- If provisioning fails mid-way (e.g., migration succeeds but seed fails), the school is left in an inconsistent state: schema exists with some tables, `database_status` is `pending`, and no rollback occurs

**Why it happens:**
- No explicit transaction wrapping the entire provisioning flow (CREATE SCHEMA + migrations + seed)
- No provisioning timeout — if a migration hangs, the deployment is stuck
- Seed idempotency is assumed but not enforced (some seed functions use "find or create," others use "create without check")
- The provisioning endpoint doesn't support cancellation (if a school admin refreshes the page, provisioning continues regardless)

**How to avoid:**
- Wrap the full provisioning pipeline in a transaction block: `CREATE SCHEMA → migrations → seed`. If any step fails, roll back by dropping the schema — this is safe because provisioning is the first step and no real data has been entered yet.
- Add a provisioning timeout (5 minutes for the full flow). If exceeded, mark the school as `provisioning_failed` and trigger an asynq task to clean up the partial schema.
- Add a provisioning cancellation endpoint: `DELETE /api/v2/schools/{id}/provisioning`. If the school is still `pending`, cancel and drop the schema.
- Enforce seed idempotency: all seed operations should use `FirstOrCreate` or a similar pattern that doesn't error on duplicate data.

**Warning signs:**
- Schools stuck in `pending` status with no visible error
- Support tickets about "my school was created but nothing works"
- Two provisioning requests for the same school succeeding partially
- Manual cleanup of orphaned schemas required on PostgreSQL

**Phase to address:**
Phase 1 (Foundation): Provisioning hardening — transactional flow, timeout, cancellation, and idempotent seeds.

---

### Pitfall 12: Report Card Generation During Active Grade Entry

**What goes wrong:**
Report cards are typically generated at the end of a term, when grades should be final. In practice, teachers may still be entering or adjusting grades during the report generation period. If a report card is generated while grades are changing:
- Two report cards for the same student can show different grades if generated hours apart
- Parents receive a PDF report, then a corrected version, then a third — eroding trust
- GPA calculations for class rankings become inconsistent (some students included at one point, others at a different point)
- The audit trail becomes ambiguous: which version of the grade was "official"?

The project's `reportcard` model has a `GradeSummary` JSONB field. The ReportCard module can generate batch reports. But there's no grade-locking mechanism — once a grade is entered, it can be changed at any time unless the session is completed.

**Why it happens:**
- No concept of "grade freeze" — grades are always mutable
- Teachers enter grades asynchronously (some finish early, some late)
- Report generation is seen as a "print" operation, not a "snapshot" operation
- The system doesn't track which version of a grade was used in which report card

**How to avoid:**
- Implement a "grade freeze" on the Session: when `session.status` transitions to `completed`, all grades within that session become read-only. This prevents after-the-fact grade changes that would invalidate issued report cards.
- Report cards should snapshot the grade values at generation time (store a `grades_snapshot` JSONB field on the ReportCard record, not just reference the live `Score` records). This makes the report card an immutable historical document.
- Add a "reissue" workflow: if grades are corrected after the session is frozen (rare, requires admin override), the system creates a corrected report card entry with a version number and reason. The original report card remains accessible.
- Class ranking calculations should always use the snapshot at a specific moment (rank_generated_at), never live data, to ensure consistency within a batch.

**Warning signs:**
- Teachers editing grades after report cards have been issued
- No "session completed" workflow in the UI
- Report cards don't have a `generated_at` or `version` field
- Support tickets about "my child's report card changed"
- Class ranks differ between printed report cards and the online gradebook

**Phase to address:**
Phase 5 (Gradebook & Assessment): Grade freeze on session completion, report card snapshotting, reissue workflow with versioning.

---

### Pitfall 13: Timetable-Student-Attendance Disconnect

**What goes wrong:**
Timetables define the schedule (which subject, teacher, level, and session). Attendance records reference timetable entries. If timetables are modified mid-term (teacher reassignment, schedule change) without updating the attendance references, attendance records become orphaned:
- Attendance marked under Teacher A now shows as "no teacher" after Teacher A is replaced
- Students who switched sections have attendance records under the wrong timetable entry
- Attendance statistics for a subject become unreliable when timetable IDs change

The project has a sophisticated timetable system (calendar editor with conflict highlighting, bulk create, CRUD). The attendance module references timetable entries via foreign key. But there's no cascade or re-parenting when timetable entries change.

**Why it happens:**
- Timetable CRUD doesn't check for existing attendance references before allowing changes
- No "orphaned record" report after timetable modifications
- Teachers are replaced, but their timetable entries are edited rather than replaced with new IDs
- Attendance-to-timetable link is assumed immutable once created

**How to avoid:**
- Add a "soft change" policy for timetables: instead of deleting and recreating timetable entries (which changes the ID), allow status changes (active/archived/inactive). Attendance records always reference the timetable entry ID, which persists even when the entry is inactive.
- If a timetable entry must be replaced (not just edited), automatically re-parent affected attendance records to the new entry. This is a batch update triggered before the old entry is removed.
- Add an integrity check that runs after timetable changes: `SELECT COUNT(*) FROM attendance WHERE timetable_id NOT IN (SELECT id FROM timetables)`. Report any orphaned records.
- For attendance statistics, always join through the timetable to the current subject/teacher at the time of the attendance record, not the current subject/teacher assignment (which may have changed).

**Warning signs:**
- Attendance records with no matching timetable entry after schedule changes
- Teacher attendance summary shows hours for classes they no longer teach
- Subject attendance statistics have gaps after mid-term timetable changes
- No "timetable change log" or versioning

**Phase to address:**
Phase 4 (Academic Workflow): Timetable mutation safety — soft changes, re-parenting, integrity checks.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| JSONB for grade scores blob (current pattern) | Single-column storage, flexible schema | Can't query individual scores at DB level; float precision loss; no constraints on score ranges | Acceptable for MVP but must migrate to normalized table for production reporting |
| `PrepareStmt: false` on core DB (current pattern) | Avoids SchemaTablePrefix corruption | Every query re-planned by PostgreSQL (2-5x query planning overhead) | Acceptable until tenant count >100; then invest in fixing SchemaTablePrefix |
| `context.Background()` in S3/audit operations (current pattern) | Goroutines survive request lifecycle | Lost trace context; no request correlation for audit writes | Acceptable for best-effort operations but not for tenant-critical writes |
| Cross-tenant analytics via application loop | Quick implementation | N+1 queries against schemas; slow; no consistency guarantee | Never acceptable in production — always use materialized views or FDW |
| Manual session/term creation without rollover automation | Simple initial setup | Data duplication and inconsistency at every year boundary | Acceptable only during alpha; must be automated before first school completes a full academic year |
| No WAEC external exam model | Less code | WAEC grades mixed with internal grades; transcript inaccuracy; university rejection risk | Never acceptable for a system targeting Nigerian schools |
| Grade item sum-to-100 validation only in service layer | Faster to implement | Code-path gaps; edit drift can silently break constraint | Acceptable for alpha but must add DB constraint before GA |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Twilio SMS | Treating "sent to provider" as "delivered" | Implement status callback webhook; track `delivery_status` through delivered/failed states |
| SendGrid Email | No SPF/DKIM setup for school domain | Configure DKIM signing per sending domain or subdomain; verify SPF records |
| S3-Compatible Storage | Hardcoding `*.amazonaws.com` URL format (exists at `s3_backup.go:92`) | Use `S3Config.Endpoint` for URL generation; support MinIO/DO Spaces |
| Asynq Queue | Using only for email dispatch (current) | Queue all async work: report generation, backup, restore, grade recalculation, parent notification |
| WAEC Results CSV Import | No grade boundary validation | Validate each grade falls within WAEC A1-F9 scale; reject invalid values before import |
| OAuth/SSO (future) | Not handling user merge between SSO and existing accounts | Always match by verified email; never create duplicate accounts for SSO users |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Cross-schema UNION ALL reports | Report generation takes >30s; query string >1MB | Use materialized views in analytics schema refreshed on schedule | >50 schemas |
| `PrepareStmt: false` query re-planning | Higher-than-expected CPU on DB; query planning dominating pg_stat_statements | Fix SchemaTablePrefix for prepared statement compatibility | >100 concurrent requests |
| Floating point score accumulation | Grade drift over multiple assessments (±0.1-0.5 cumulative) | Store scores as integer basis points | Affects every calculation from day one |
| Unbounded list endpoints | Memory OOM on large-school queries; DB CPU spike | Add pagination to remaining endpoints (known gap from CONCERNS.md) | School with >1000 students |
| No grade item mutation queue | Heavy recalculation on every grade item change | Defer proportional recalculation to background asynq job | >1000 scores per assessment |
| Session pooling with PgBouncer | Connection exhaustion at high concurrency | Session pooling (fewer connections per tenant) or connection limits per tenant | >50 concurrent teachers |
| `pg_dump` for per-tenant backup | DB-wide lock; long backup window | Use `pg_dump --schema=school_N` (already implemented) but stagger backups | >100 tenants backing up simultaneously |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `search_path` not scoped per transaction | Tenant data leak (Student A sees Student B's grades) | Always use `SET LOCAL search_path` within a GORM transaction; never `SET search_path` |
| No CSRF on school-facing admission forms (public endpoint) | Third-party can submit fake admission applications | Rate-limit by IP + reference number; add CAPTCHA for public forms |
| Student ID as URL parameter without authorization check | User can enumerate student records by ID | Always verify `tenant_id` + `school_id` + `role` before returning student data |
| HS256 JWT with shared secret (current pattern) | Any service with the secret can forge tokens for any school | Plan RS256 migration for multi-service deployments; no immediate threat in modular monolith |
| S3 URL accessible without auth if bucket is misconfigured | Student/PII data exposed via backup URL | Generate pre-signed URLs with expiration; never return raw S3 URLs (known gap at `s3_backup.go:92`) |
| Grade data in JSONB with no encryption at rest | Grade/PII data in plaintext in DB | Enable PostgreSQL TDE or use `pgcrypto` for sensitive JSONB fields |
| Public schema `User` table accessible to all tenant connections | Shared DB connection can read all users if search_path not isolated | Verify the core DB connection pool never exposes public schema without tenant context |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Grade freeze prevents post-report correction | Teacher can't fix an error after session is completed | Allow corrections with approval workflow and version tracking (original preserved) |
| No "what changed" on grade edits | Parents dispute grades without visibility | Audit log on every score change with before/after values and user attribution |
| Bulk import errors are opaque | User doesn't know which row failed or why | Per-row validation report with clear error messages and row reference numbers |
| Timetable conflict highlighting only on save | Teacher creates a conflict and discovers it too late | Real-time conflict check during calendar grid editing (show conflicts as teacher drags) |
| Report card download without notification | Parents don't know new reports are available | Push notification (SMS/email) when report card is generated and ready for download |
| Academic year rollover is invisible | Staff confused when data "disappears" or changes | Clear "End of Year" wizard with progress indicators and undo period |

## "Looks Done But Isn't" Checklist

- [ ] **Report Builder:** Returns CSV with metadata only, not actual query data (known TODO at `reportbuilder/service.go:148`). Verify actual data queries are implemented before marketing as "done."
- [ ] **WAEC Integration:** No model, no credit tracking, no separate transcript section. Verify WAEC external results are stored separately from internal grades.
- [ ] **Grade Calculation:** Float32 arithmetic throughout. Verify integer basis-point storage for calculable precision.
- [ ] **Delivery Tracking:** SendGrid/Twilio messages tracked as "sent" at dispatch time only. Verify webhook handlers for delivered/failed/bounced status updates.
- [ ] **Academic Year Rollover:** No automated student promotion or grade archiving. Verify a complete end-of-year workflow exists.
- [ ] **Cross-Tenant Reporting:** No analytics schema or materialized views. Verify reports can aggregate across schools without N+1 query loops.
- [ ] **Parent Communication Preferences:** No per-parent channel preference or fallback. Verify parents can choose SMS/Email/WhatsApp and fallback behavior is defined.
- [ ] **Provisioning Rollback:** Failed provisioning leaves orphaned schemas. Verify transactional provisioning with full rollback on failure.
- [ ] **S3 URL Generation:** Hardcoded AWS domain (`s3_backup.go:92`). Verify custom endpoints work for MinIO/DO Spaces compatibility.
- [ ] **Grade Freeze:** No mechanism to lock grades after session completion. Verify finalization workflow exists before report card generation.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Schema migration failure on one tenant | MEDIUM | `MigrateAllSchemaTenants` retry with resume-from-failure. If schema drifted, roll back migration on all tenants, fix, re-apply. |
| search_path data leak (wrong tenant data written) | HIGH | Identify affected queries and records. For reads: discard wrong results. For writes: reverse via audit log or point-in-time recovery. Implement tenant isolation tests. |
| Grade calculation error affects existing report cards | MEDIUM | Recalculate all affected scores. Reissue affected report cards with version number. Notify parents via communication module. |
| Provisioning failure with orphaned schema | LOW | Drop schema; set school status to provisioning_failed; allow retry from UI. |
| Delivery notification failure (parent didn't receive) | LOW | Query delivery status from Twilio/SendGrid webhook data. Manual resend via communication dashboard. Update parent contact info. |
| Student data lost during year rollover | HIGH | Restore from pre-rollover backup (`pg_dump --schema` for the school). Re-run rollover with corrected data. Audit loss extent. |
| WAEC grade import with wrong boundaries | MEDIUM | Delete imported WAEC results; fix grade boundary configuration; re-import. Regenerate affected transcripts. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Migration fan-out failure | Phase 1: Foundation | CI check: migration count matches across all schemas |
| pg_catalog bloat | Phase 2: Scaling | Alert when schema count >300 or catalog query time >50ms |
| search_path leakage | Phase 1: Foundation | Runtime isolation test passes; PgBouncer config confirmed session mode |
| Academic year rollover | Phase 4: Academic Workflow | Automated rollover produces verified student promotion report |
| Grade calculation precision | Phase 5: Gradebook | Boundary test suite passes for all WAEC grade thresholds |
| Cross-tenant analytics | Phase 3: Reporting | Report generation uses materialized views, not UNION ALL loops |
| Parent delivery failures | Phase 6: Communication | Delivery webhooks confirmed; rate limiting tested at 10x expected volume |
| WAEC integration | Phase 4: Academic Workflow | External exam model exists; credit tracking works; transcript separates WAEC from internal |
| Sum-to-100 enforcement gaps | Phase 5: Gradebook | DB trigger rejects invalid grade item combinations; recalculation queue tested |
| Student ID instability | Phase 4: Academic Workflow | Reactivation workflow tested; duplication eliminated in import |
| Provisioning race conditions | Phase 1: Foundation | Concurrent provisioning test passes; rollback verified |
| Report card generation timing | Phase 5: Gradebook | Grade freeze tested; report card snapshotting verified |
| Timetable-attendance disconnect | Phase 4: Academic Workflow | Integrity check passes after timetable changes; re-parenting tested |

## Sources

- **Multi-tenant PostgreSQL schemas:** Cadence blog (2026-05-22, medium confidence), toolchew multi-tenant Postgres patterns (2026-05-24, medium confidence), Planetscale approaches to tenancy (2026-04-21, high confidence), Sachith Dassanayake scaling strategies (2026-03-23, medium confidence)
- **SIS migration post-mortems:** EdPayU migration playbook (2026-06-14, medium confidence), Classter SIS migration guide (2026-03-30, high confidence), EIN360 UAE migration guide (2026-06-18, medium confidence), SI Elements SIS failures analysis (2026-02-12, high confidence)
- **Grade calculation errors:** Blackbaud LMS grading troubleshooting (2025-12-08, high confidence), Moodle SCORM grade rounding bug analysis (2026-06-16, high confidence), CodePex automated grading guide for Indian schools (2026-05-30, medium confidence)
- **Academic year rollover:** Aequitas K-12 SIS rollover guide (2026-06-15, high confidence), PowerSchool SIS EOY guide (2024-10-14, high confidence), Clever school year rollover (2026-07, high confidence)
- **Parent communication delivery:** Inkwelly parent message diagnosis (2026-05-18, high confidence), Finalsite Connect SMS best practices (2026, high confidence), SchoolMessenger troubleshooting (2026, medium confidence)
- **WAEC/Nigerian curriculum:** OpenEduCat WAEC integration (2026, medium confidence), ByteVista Nigerian result processing (2026-05-20, medium confidence), WAEC Management Module (2026, medium confidence)
- **Codebase-specific:** CONCERNS.md (2026-07-18, high confidence), migration_service.go, schema_db.go, score/service.go analysis

---

*Pitfalls research for: Academio school management system*
*Researched: 2026-07-18*
