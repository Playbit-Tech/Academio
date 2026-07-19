---
phase: 01-foundation-hardening
verified: 2026-07-19T07:30:00Z
status: gaps_found
score: 3/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "User can generate and download a PDF report card, transcript, or certificate — existing HTML templates render via Gotenberg v8.x headless Chromium with proper page breaks"
    status: partial
    reason: "Report card PDF generation works end-to-end with Gotenberg, but transcript and certificate templates do not exist, SchoolName/SchoolAddress are placeholder strings, no proper page breaks in the HTML template, and the PDF render endpoint is dev-only"
    artifacts:
      - path: "backend/pkg/pdf/generator.go"
        issue: "Only report card template exists — no transcript or certificate templates. SchoolName and SchoolAddress fields are empty/hardcoded. No page-break CSS."
      - path: "backend/internal/modules/reportcard/handler.go"
        issue: "PDF download endpoint exists only for report cards, not for transcripts or certificates"
    missing:
      - "Transcript HTML template (generator.go) — e.g., generateTranscriptHTML()"
      - "Certificate HTML template (generator.go) — e.g., generateCertificateHTML()"
      - "Page-break CSS in report card template (generator.go)"
      - "School-branded PDF template resolution from school records"
  - truth: "Scheduled jobs (nightly backups, weekly reports, monthly billing) execute automatically on configured cron intervals, delegating to Asynq for fault-tolerant execution"
    status: partial
    reason: "NightlyBackup job works fully — enumerates active schools and enqueues backup:create Asynq tasks. But WeeklyReport and MonthlyBilling are placeholders (log and return). All three are registered via cron so schedules fire, but only backup does real work."
    artifacts:
      - path: "backend/internal/scheduler/jobs.go"
        issue: "weeklyReportJob() and monthlyBillingJob() are stubs — only log and return"
    missing:
      - "Real implementation for weeklyReportJob — batch report card generation"
      - "Real implementation for monthlyBillingJob — invoice/billing generation"
deferred: []
human_verification:
  - test: "Run integration test suite end-to-end"
    expected: "All 40 tests pass (register → login → school create → provisioning poll → curriculum → assessments → sessions → grade items → sum-to-100)"
    why_human: "Verification requires running server with PostgreSQL and Redis — cannot run programmatically in isolated check"
  - test: "Serve a PDF report card via the download endpoint"
    expected: "Downloading a report card returns valid application/pdf content with proper page breaks and school branding"
    why_human: "Requires running server with PostgreSQL, Redis, and Gotenberg Docker containers"
---

# Phase 1: Foundation Hardening Verification Report

**Phase Goal:** Production-safe multi-tenant infrastructure with reliable migrations, schema isolation, provisioning, PDF generation, and scheduled jobs
**Verified:** 2026-07-19T07:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Admin can run schema migrations across all tenant schemas with per-schema advisory locks — partial failures recorded in migration_errors table and retryable via CLI, with CI validating migration count parity | ✓ VERIFIED | `pg_advisory_xact_lock` in migrator.go (line 97), migration_errors table + model, HTTP retry endpoints (`POST /schools/:id/retry-migration`, `POST /admin/migrations/retry-all`), CI script validates migration integrity (23 core + 6 school, all unique) |
| 2 | Schema isolation is guaranteed through PgBouncer — SchemaTablePrefix plugin uses SET LOCAL inside GORM transactions, never connection-level SET search_path | ✓ VERIFIED | `SET LOCAL search_path` in migration_service.go (line 135), SchemaTablePrefix GORM plugin in schema_db.go using context/SQL prefix — zero connection-level SET search_path found; documented in search-path-strategy.md |
| 3 | Tenant provisioning is fully transactional — CREATE SCHEMA → migrations → seed completes entirely or rolls back with no orphaned schemas | ✓ VERIFIED | Compensating-actions rollback in provisioning.go (DROP SCHEMA ... CASCADE on failure), RecoveryService for reprovision, 6 integration tests covering rollback paths |
| 4 | User can generate and download a PDF report card, transcript, or certificate — existing HTML templates render via Gotenberg v8.x headless Chromium with proper page breaks | ✗ FAILED | Report card pipeline works (GotenbergClient + HTMLGenerator + DownloadReportCard handler), but no transcript/certificate templates exist, SchoolName is placeholder, no page-break CSS |
| 5 | Scheduled jobs (nightly backups, weekly reports, monthly billing) execute automatically on configured cron intervals, delegating to Asynq for fault-tolerant execution | ✗ FAILED | CronRunner framework works, NightlyBackup enqueues real Asynq tasks, but WeeklyReport and MonthlyBilling are stubs (log-only) |

**Score:** 3/5 truths verified

### Deferred Items

No deferred items — all gaps are within Phase 1 scope.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/internal/database/migrations/migrator.go` | Advisory locking with `pg_advisory_xact_lock` | ✓ VERIFIED | FNV-1a hash lock key, per-schema locking |
| `backend/internal/database/models/migration_errors.go` | MigrationError model | ✓ VERIFIED | SchemaName, MigrationID, ErrorText, resolved_at fields |
| `backend/internal/database/migrations/core/migration_errors.go` | migration_errors table migration | ✓ VERIFIED | AutoMigrate + DropTable rollback |
| `scripts/ci-validate-migration-count.sh` | CI migration validation script | ✓ VERIFIED | Validates non-empty + unique IDs — passes (23 core, 6 school) |
| `docs/architecture/search-path-strategy.md` | Search path isolation strategy | ✓ VERIFIED | Documents 4 code paths, anti-patterns, verification |
| `backend/pkg/pdf/gotenberg.go` | Gotenberg client for HTML→PDF | ✓ VERIFIED | POST /forms/chromium/convert/html, A4, margin config |
| `backend/pkg/pdf/generator.go` | HTML report card generator | ✓ VERIFIED | Go template, CalculateGPA, ScoreToGrade |
| `backend/docker-compose.yml` | Gotenberg service in compose | ✓ VERIFIED | `gotenberg/gotenberg:8`, health check, API dependency |
| `backend/internal/scheduler/cron_runner.go` | CronRunner with Start/Stop | ✓ VERIFIED | robfig/cron/v3, SkipIfStillRunning, Recover chains |
| `backend/internal/scheduler/jobs.go` | Job definitions | ⚠️ PARTIAL | NightlyBackup real, WeeklyReport/MonthlyBilling stubs |
| `backend/internal/scheduler/config.go` | Scheduler configuration | ✓ VERIFIED | Default cron expressions + env var overrides |
| `backend/internal/database/tenant/provisioning_recovery.go` | Recovery service | ✓ VERIFIED | ReprovisionSchool with panic guard + DROP SCHEMA |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| migrator.go | PostgreSQL | `pg_advisory_xact_lock()` raw SQL | ✓ WIRED | Line 97, inside migrationDB.Transaction() |
| migrator.go | migration_errors table | LogMigrationError() | ✓ WIRED | Uses separate logDB to survive tx rollback |
| school/handler.go | migration_service.go | RetryMigration / ListMigrationErrors | ✓ WIRED | Router wired at lines 872, 198-199 |
| schema_db.go | GORM callback chain | SchemaTablePrefix plugin | ✓ WIRED | Registered for Create/Query/Update/Delete/Row/Raw |
| migration_service.go | PostgreSQL | SET LOCAL search_path | ✓ WIRED | Line 135, inside transaction |
| provisioning.go | PostgreSQL | CREATE SCHEMA + compensating rollback | ✓ WIRED | DROP SCHEMA ... CASCADE on failure |
| provisioning_recovery.go | ProvisioningService | ReprovisionSchool() | ✓ WIRED | Drops schema then calls ProvisionSchool |
| gotenberg.go | Gotenberg API | HTTP POST /forms/chromium/convert/html | ✓ WIRED | Multipart form with HTML, A4, margins |
| reportcard/service.go | GotenbergClient | GeneratePDF() via type assertion | ✓ WIRED | Fallback to HTML if Gotenberg unavailable |
| cron_runner.go | jobs.go | cron.AddFunc() | ✓ WIRED | 3 jobs registered (backup real, report/billing stubs) |
| jobs.go | Asynq queue | queueClient.Enqueue() | ✓ WIRED | backup:create task with MaxRetry(3) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| provisioning.go | schemaName | `fmt.Sprintf("school_%d", schoolID)` | ✓ Yes | Validated with safeSchemaNameRegex |
| jobs.go (nightlyBackupJob) | schools | `coreDB.Table("schools")` query | ✓ Yes | Queries active schools with non-empty schema_name |
| reportcard/service.go (buildSubjectData) | subjects (scores) | `scores` table joined with `subjects`, `assessments` | ✓ Yes | JSON extraction from score blob, real DB query |
| reportcard/service.go (GeneratePDF) | SchoolName | Hardcoded "School Name" | ✗ HOLLOW | Placeholder — not resolved from school record |
| generator.go (reportCardTemplate) | SchoolAddress | Empty string from ReportCardData | ✗ HOLLOW | Not wired to any data source |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Go build | `go build ./...` | clean (exit 0) | ✓ PASS |
| Go vet | `go vet ./...` | clean (exit 0) | ✓ PASS |
| CI validation script | `bash scripts/ci-validate-migration-count.sh` | PASS: 23 core + 6 school | ✓ PASS |
| No connection-level SET search_path | `grep -rn "SET search_path" backend/internal/ --include="*.go" \| grep -v "SET LOCAL" \| grep -v "^\s*//"` | Only comment match (line 101 comment, not code) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| INFRA-01 | 01-01 | Migration hardening with advisory locks, migration_errors, retry, CI validation | ✓ SATISFIED | migrator.go, migration_errors.go, retry endpoints, CI script |
| INFRA-02 | 01-02 | SchemaTablePrefix PgBouncer-compatible, SET LOCAL in transactions | ✓ SATISFIED | schema_db.go, migration_service.go line 135, search-path-strategy.md |
| INFRA-03 | 01-03 | Provisioning pipeline with transactional rollback | ✓ SATISFIED | provisioning.go (compensating rollback), provisioning_recovery.go |
| INFRA-04 | 01-04 | Gotenberg v8.x integrated for PDF conversion | ✓ SATISFIED | gotenberg.go, docker-compose.yml gotenberg service, config.go |
| INFRA-05 | 01-05 | Cron scheduler (robfig/cron v3) with Asynq delegation | ⚠️ PARTIAL | CronRunner + NightlyBackup real, WeeklyReport/MonthlyBilling stubs |
| INFRA-06 | 01-04 | PDF pipeline connecting HTML generator → Gotenberg → download | ✓ SATISFIED | reportcard/service.go GeneratePDF, handler.go DownloadReportCard, HTML + PDF flow |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/internal/scheduler/jobs.go` | 65-67 | Placeholder stub (TODO + log only) | ⚠️ Warning | WeeklyReport and MonthlyBilling are stubs — no real work done |
| `backend/internal/scheduler/jobs.go` | 73-75 | Placeholder stub (TODO + log only) | ⚠️ Warning | Same as above |
| `backend/internal/modules/reportcard/service.go` | 452 | Fallback to HTML on Gotenberg error | ℹ️ Info | Graceful degradation — not a blocker |
| `backend/pkg/pdf/generator.go` | 56-58 | GeneratePDF returns error for HTML-only mode | ℹ️ Info | Expected — HTMLGenerator doesn't support PDF natively |
| `backend/pkg/pdf/generator.go` | SchoolName placeholder | Hardcoded "School Name" | ℹ️ Info | Noted as known stub in plan; will be resolved in future phase |

### Human Verification Required

#### 1. End-to-end integration test suite

**Test:** Run `backend/scripts/test_endpoint.sh` with a freshly seeded database
**Expected:** All 40 tests pass (health → CSRF → register → login → school create → provisioning poll → curriculum → assessments → sessions → grade items → sum-to-100)
**Why human:** Requires running PostgreSQL, Redis, and the API server — cannot verify in isolated checks

#### 2. PDF report card download

**Test:** After integration test suite creates a school, navigate to a report card and trigger PDF download
**Expected:** Valid PDF content is returned with school name, student scores, GPA, teacher/principal remarks
**Why human:** Requires running server + PostgreSQL + Redis + Gotenberg Docker containers

#### 3. Cron job execution

**Test:** Verify that cron jobs fire on their configured schedules (nightly 2AM, Monday 3AM, 1st 4AM)
**Expected:** Nightly backup enqueues backup:create Asynq tasks; report/billing jobs log activation
**Why human:** Requires running server with active time passage or manual clock manipulation

### Gaps Summary

**Gap 1: PDF generation limited to report cards only** (SC #4)
- No transcript or certificate templates exist — only the report card template in `generator.go`
- SchoolName and SchoolAddress are hardcoded/empty — not resolved from school database records
- No page-break CSS in the report card HTML template
- The PDF render endpoint (`/api/v2/pdf/render`) is gated by `APP_ENV != production` — dev-only
- **Impact:** Users cannot generate transcripts or certificates as PDF. Report card PDF lacks school branding.

**Gap 2: Weekly/billing jobs are stubs** (SC #5)
- WeeklyReport and MonthlyBilling job functions only log a message and return
- The cron schedules fire correctly and the CronRunner infrastructure is solid
- NightlyBackup is fully implemented — it enumerates active schools and enqueues Asynq backup:create tasks
- **Impact:** Backup automation works. Report and billing automation requires Phase 2+ modules to be implemented first, then these jobs need real logic.

**Non-gap deviations (acceptable):**
- "Retry CLI" in INFRA-01 requirement is implemented as HTTP admin endpoints (`POST /schools/:id/retry-migration`, `POST /admin/migrations/retry-all`) rather than a CLI binary. The admin API provides the same functionality with proper auth gating. This is acceptable given the project is an API-first system.
- "CI migration count parity" is implemented as migration integrity validation (non-empty + unique IDs) instead of exact count parity. The decision is documented: core and school migrations have inherently different counts (23 vs 6). This is acceptable.

---

_Verified: 2026-07-19T07:30:00Z_
_Verifier: the agent (gsd-verifier)_
