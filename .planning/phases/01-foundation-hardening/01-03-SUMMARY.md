---
phase: 01-foundation-hardening
plan: 03
subsystem: api
tags: [gorm, postgres, asynq, provisioning, tenant-isolation]
requires:
  - phase: 01-foundation-hardening
    plan: 01
    provides: provisioning code structure, migration service
provides:
  - transactional rollback in ProvisionSchool with compensating actions
  - RecoveryService for re-provisioning failed schools
  - POST /schools/:id/re-provision super-admin endpoint
  - async provisioning:school task type and handler
affects: school onboarding, tenant lifecycle, infra reliability
tech-stack:
  added: []
  patterns:
    - compensating-actions rollback for DDL-heavy operations
    - deferred cleanup with boolean step tracking
    - recovery service pattern for re-triggering failed provisioning
key-files:
  created:
    - backend/internal/database/tenant/provisioning_rollback_test.go
    - backend/internal/database/tenant/provisioning_recovery.go
    - backend/internal/queue/handlers/provisioning_handler.go
  modified:
    - backend/internal/database/tenant/provisioning.go
    - backend/internal/modules/school/service.go
    - backend/internal/modules/school/handler.go
    - backend/internal/router/setup.go
    - backend/internal/router/router.go
    - backend/internal/queue/tasks.go
key-decisions:
  - "Use compensating-actions pattern instead of PG transaction (DDL cannot run inside DML transactions)"
  - "DROP SCHEMA ... CASCADE as nuclear rollback — cleanly removes all intermediate state"
  - "Idempotent provisioning: active schools skipped, provisioning_failed triggers drop + recreate"
  - "RecoveryService exposes ReprovisionSchool with same panic-recovery guard as ProvisionSchool"
  - "Async provisioning task uses same provisioning:school type but run via separate handler"
patterns-established:
  - "Compensating actions: boolean flags track completed steps, deferred function rolls back in reverse order"
  - "Panic recovery: recover() in defer converts panic to error, triggers same cleanup path"
  - "Recovery service: wraps ProvisioningService with DROP SCHEMA before re-provision"
requirements-completed:
  - INFRA-03
duration: 35min
completed: 2026-07-19
---

# Phase 01 Foundation Hardening — Plan 03 Summary

**ProvisionSchool with transactional rollback (compensating actions), RecoveryService for re-provisioning failed schools, super-admin re-provision endpoint, and async provisioning task via asynq**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-19
- **Completed:** 2026-07-19
- **Tasks:** 2 (1 TDD with integration tests)
- **Files modified:** 9

## Accomplishments
- ProvisionSchool() uses deferred compensating-actions rollback on failure — schema dropped, status reset, admin UserInfo cleaned up
- Panics caught via recover() and converted to errors, same rollback path executes
- Idempotent provisioning: active schools skipped; provisioning_failed status triggers full drop + recreate
- 6 integration tests (testcontainers + PostgreSQL) covering success, idempotent, migration/seed failure rollback, provisioning_failed re-provision, and panic recovery
- RecoveryService.ReprovisionSchool() with super-admin guard (POST /schools/:id/re-provision under admin group)
- New provisioning:school task type, ProvisionSchoolPayload, ProvisioningTaskHandler with HandleProvisionSchool registered in asynq mux

## Task Commits

Each task was committed atomically:

1. **Task 1: Add transactional rollback to ProvisionSchool()** - `b4fdd6f` (feat, TDD with tests)
2. **Task 2: Create recovery service and re-provisioning endpoint** - `450dd30` (feat, 7 files)

## Files Created/Modified
- `backend/internal/database/tenant/provisioning.go` - Compensating-actions rollback, step tracking, panic recovery, idempotent/re-provision logic
- `backend/internal/database/tenant/provisioning_rollback_test.go` - 6 integration tests for rollback scenarios
- `backend/internal/database/tenant/provisioning_recovery.go` - RecoveryService with ReprovisionSchool (drop schema + re-provision)
- `backend/internal/modules/school/service.go` - WithRecoveryService(), ReprovisionSchool() delegation
- `backend/internal/modules/school/handler.go` - Reprovision handler for POST /schools/:id/re-provision
- `backend/internal/router/setup.go` - RecoveryService wiring, ProvisioningTaskHandler, handler registration
- `backend/internal/router/router.go` - Route: admin POST /schools/:id/re-provision
- `backend/internal/queue/tasks.go` - TypeProvisionSchool, ProvisionSchoolPayload, NewProvisionSchoolTask, TaskHandlers.ProvisionSchool
- `backend/internal/queue/handlers/provisioning_handler.go` - ProvisioningTaskHandler with HandleProvisionSchool and HandleReprovisionSchool

## Decisions Made
- **Compensating actions instead of PG transaction**: DDL (CREATE SCHEMA) cannot run inside a traditional PG transaction alongside DML without special `tx_ddl` handling. Boolean flags track each completed step; deferred function rolls back in reverse order.
- **DROP SCHEMA ... CASCADE as nuclear option**: On failure, the entire tenant schema is dropped — cleanly removes migrations, seed data, and UserInfo in one step. The schema_name field and database_status are reset to allow a fresh retry.
- **Idempotent re-provision**: If school status is already "active", ProvisionSchool returns early (no-op). If "provisioning_failed", it drops any existing schema and re-runs the full pipeline.
- **RecoveryService as separate concern**: Keeps the re-provisioning orchestration (DROP SCHEMA + ProvisionSchool call) out of ProvisioningService, which remains focused on the creation pipeline.
- **Handler function for async task**: The ProvisioningTaskHandler uses a struct with constructor (matching backup_handler.go pattern) rather than a closure, keeping the codebase consistent.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `migrationsRun` boolean flag tracked migrations in the plan's sample code but was unused in the actual rollback (DROP SCHEMA covers migration cleanup). Removed to fix compilation.
- Integration tests required inserting school records in the schools table before tests that query database_status. The plan's test pseudocode assumed records already exist.
- Submodule build is pre-deployed; build verified inside the backend submodule with `go build ./...` for affected packages.

## Next Phase Readiness
- ProvisionSchool is fully hardened with rollback — safe for synchronous provisioning during school creation
- Recovery endpoint gives admins a self-service repair path for stuck provisioning_failed schools
- Async provisioning task available for fault-tolerant provisioning (currently unused; can be integrated into CreateSchool flow)

## Self-Check: PASSED

All 9 files present. Both commits verified (b4fdd6f, 450dd30). All 4 packages build (`tenant`, `queue`, `school`, `router`). No vet warnings from changed code.

---

*Phase: 01-foundation-hardening*
*Plan: 03*
*Completed: 2026-07-19*
