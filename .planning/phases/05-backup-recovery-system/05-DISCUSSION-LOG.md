# Phase 5: Backup & Recovery System — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 05-backup-recovery-system
**Areas discussed:** Backup storage target, Backup scheduling, Retention & cleanup

---

## Backup Storage Target

| Option | Description | Selected |
|--------|-------------|----------|
| S3 only | Primary storage. Add Endpoint to S3Config for MinIO/Spaces compatibility. | ✓ |
| Local only | Dev/testing only, reuse existing LocalStorage | |
| Both | S3 primary + local fallback, doubles complexity | |

**User's choice:** S3 only
**Notes:** Endpoint field needed in S3Config for S3-compatible stores.

---

## Backup Scheduling

| Option | Description | Selected |
|--------|-------------|----------|
| Asynq queue | Reuse existing Asynq queue for periodic backup tasks | ✓ |
| Cron expressions | Configurable cron per school, adds cron parser dep | |
| Simple ticker | Fixed-interval goroutine, simplest but least flexible | |

**User's choice:** Asynq queue-based periodic tasks
**Notes:** Same schedule applies to all active tenant databases. Default: daily.

---

## Retention & Cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| Keep N most recent | Keep 14 newest per school, auto-delete oldest | ✓ |
| Keep by age | Keep backups < N days old, cleanup job needed | |
| Keep all (unlimited) | Simplest but unbounded storage growth | |

**User's choice:** Keep 14 most recent per school
**Notes:** Failed backups count towards the 14 limit. Auto-delete oldest on new successful backup.

---

## Deferred Ideas

None.
