---
phase: 01-foundation-hardening
plan: 05
subsystem: infra
tags: [cron, scheduler, asynq, queue, robfig, backup, periodic-jobs]
requires:
  - phase: 01-01
    provides: Schema-per-tenant infrastructure, provisioning pipeline
  - phase: 01-04
    provides: Gotenberg PDF generation, backup/restore services, Asynq queue infrastructure
provides:
  - CronRunner — wraps robfig/cron/v3 with Start/Stop lifecycle
  - NightlyBackup job (daily 2AM) — enqueues backup:create tasks per active school
  - WeeklyReport job (Mon 3AM) — placeholder for batch report generation
  - MonthlyBilling job (1st 4AM) — placeholder for billing/invoice generation
  - Configurable cron schedules via CRON_BACKUP, CRON_REPORT, CRON_BILLING env vars
  - Server lifecycle integration (start after queue worker, graceful shutdown)
affects:
  - deploy
  - operations
tech-stack:
  added:
    - github.com/robfig/cron/v3 v3.0.1 (promoted from indirect to direct)
  patterns:
    - Periodic jobs delegate to Asynq for fault-tolerant execution
    - cron.SkipIfStillRunning prevents overlapping job runs
    - cron.Recover catches panics and logs them
    - cronLogger adapter bridges robfig/cron Logger interface to pkg/logger
key-files:
  created:
    - backend/internal/scheduler/config.go
    - backend/internal/scheduler/cron_runner.go
    - backend/internal/scheduler/jobs.go
  modified:
    - backend/internal/config/config.go
    - backend/internal/router/setup.go
    - backend/cmd/server/main.go
key-decisions:
  - "Jobs delegate to Asynq for retryable, persisted execution rather than handling failures inline"
  - "cron.SkipIfStillRunning prevents overlapping runs (critical for backup job that may exceed 24h)"
  - "cron.Recover captures job panics to keep scheduler running"
  - "Scheduler starts after queue worker in NewRouter; main.go calls Start/Stop"
  - "cronLogger adapter uses pkg/logger Infof/Errorf instead of cron's default PrintfLogger"
patterns-established:
  - "Scheduled Job: define in jobs.go, register in cron_runner.go, enqueue Asynq task"
  - "Graceful shutdown: cronRunner.Stop() in shutdown function waits for running jobs"
  - "Configurable period: env vars with defaults in DefaultSchedulerConfig()"
requirements-completed:
  - INFRA-05
duration: 12min
completed: 2026-07-19
---

# Phase 01 Foundation Hardening: Plan 05 — Cron Job Scheduler Summary

**Production-ready cron scheduler with nightly backup, weekly report, and monthly billing jobs — each delegating to Asynq for fault-tolerant execution, with server lifecycle integration**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-19
- **Completed:** 2026-07-19
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created `CronRunner` wrapping robfig/cron/v3 with Start/Stop lifecycle, `SkipIfStillRunning` chain, and `Recover` chain
- Implemented `cronLogger` adapter bridging robfig/cron's Logger interface to `pkg/logger`
- Defined 3 job functions: nightly backup (enumerates active schools, enqueues `backup:create` tasks), weekly report (placeholder), monthly billing (placeholder)
- Added `SchedulerConfig` to app config with environment variable overrides (`CRON_BACKUP`, `CRON_REPORT`, `CRON_BILLING`)
- Integrated cron runner into server startup (created after queue worker, started in main.go)
- Ensured graceful shutdown via shutdown function and defer in main.go

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CronRunner service and job definitions** — `5e4b58a` (feat) / parent `13aa453`
2. **Task 2: Integrate CronRunner lifecycle into server startup** — `7aaa541` (feat) / parent `e739299`

## Files Created/Modified

- `backend/internal/scheduler/config.go` — SchedulerConfig with BackupCron, ReportCron, BillingCron, Location; DefaultSchedulerConfig()
- `backend/internal/scheduler/cron_runner.go` — CronRunner with NewCronRunner, Start, Stop; cronLogger adapter
- `backend/internal/scheduler/jobs.go` — Jobs with NightlyBackup, WeeklyReport, MonthlyBilling; NewJobs, nightlyBackupJob, weeklyReportJob, monthlyBillingJob
- `backend/internal/config/config.go` — Added Scheduler field to Config struct, env var loading for CRON_BACKUP/CRON_REPORT/CRON_BILLING
- `backend/internal/router/setup.go` — Updated NewRouter return signature to include *scheduler.CronRunner; added cron runner creation after queue worker; added cron stop to shutdown function
- `backend/cmd/server/main.go` — Start cron runner after router creation, defer Stop on shutdown

## Decisions Made
- Jobs delegate to Asynq for retryable, persisted execution rather than handling failures inline — keeps job functions simple and leverages existing queue infrastructure
- `SkipIfStillRunning` chain prevents overlapping job runs (critical for backup jobs on large tenants that may exceed 24h)
- `Recover` chain catches panics in job functions, logs them, and keeps scheduler running
- Scheduler is started in main.go after `NewRouter` returns (queue worker is already running by then)
- `cronLogger` adapter uses `pkg/logger.Infof`/`Errorf` for consistent structured logging

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Unused `context.Background()` in `jobs.go` — removed during build verification (cleanup fix)

## User Setup Required

None — cron schedules use sensible defaults (daily 2AM backup, Monday 3AM report, 1st 4AM billing). Schedules can be overridden via `CRON_BACKUP`, `CRON_REPORT`, `CRON_BILLING` environment variables if desired.

## Next Phase Readiness
- Cron scheduler infrastructure is in place and ready for additional periodic jobs
- Weekly report and monthly billing are placeholders — they will need real implementations as the report card batch and billing modules mature
- Additional jobs can be added by creating a new function in `jobs.go` and registering it in `cron_runner.go`

## Self-Check: PASSED

All files created, all commits verified.

---

*Phase: 01-foundation-hardening*
*Completed: 2026-07-19*
