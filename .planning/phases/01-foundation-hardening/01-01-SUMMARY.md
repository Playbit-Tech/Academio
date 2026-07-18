---
phase: 01-foundation-hardening
plan: 01
name: Migration Infrastructure Hardening
subsystem: migrations
tags: [infrastructure, migrations, observability, retry, ci]
requires: []
provides: [INFRA-01]
affects: [migrator.go, migration_service.go, school/handler.go, school/service.go, router.go, setup.go]
dependencies: {}
tech-stack:
  added: []
  patterns: [pg_advisory_xact_lock, LogMigrationError, retry-endpoint]
key-files:
  created:
    - backend/internal/database/models/migration_errors.go
    - backend/internal/database/migrations/core/migration_errors.go
    - backend/internal/database/migrations/migration_errors.go
    - scripts/ci-validate-migration-count.sh
  modified:
    - backend/internal/database/migrations/migrator.go
    - backend/internal/database/migrations/core/core.go
    - backend/internal/database/tenant/migration_service.go
    - backend/internal/modules/school/service.go
    - backend/internal/modules/school/handler.go
    - backend/internal/router/router.go
    - backend/internal/router/setup.go
decisions: []
metrics:
  duration: ""
  completed_date: 2026-07-18
---

# Phase 01 Plan 01: Migration Infrastructure Hardening Summary

Per-schema advisory-locked migrations with `pg_advisory_xact_lock(FNV-1a hash of tableName + ":" + schemaName)`, persistent `migration_errors` table for failure observability, HTTP retry endpoints (per-school and admin-wide), and CI integrity validation script.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] School model has no SchemaName field**
- **Found during:** Task 3b
- **Issue:** `service.go:795` referenced `school.SchemaName` which doesn't exist on `*models.School`. The `SchemaName` field lives on `models.SchoolConnection` (in `multitenant.go`), not on `models.School`.
- **Fix:** `RetrySchoolMigrations` now queries `schema_name` directly from the `schools` table via a raw `Scan` into a local `schemaRow` struct, instead of relying on a non-existent field on the School model.
- **Files modified:** `internal/modules/school/service.go`
- **Commit:** `5269c55` (backend submodule)

**2. [Rule 1 - Bug] CI script grep patterns didn't match actual file paths**
- **Found during:** Task 3d
- **Issue:** Plan's script referenced `internal/database/migrations/core.go` (doesn't exist — migrations are in `core/core.go` sub-package) and `internal/database/migrations/school.go` (doesn't exist — school migrations are in `school/school.go`). The `"Migration{"` grep pattern also found false positives.
- **Fix:** Rewrote script to use `"20[0-9][0-9]_"` (migration ID pattern) across the `core/` package directory and `school/school.go`. Also added duplicate ID detection and non-empty checks instead of a simple count comparison (core and school serve different schemas and have inherently different migration counts).
- **Files modified:** `scripts/ci-validate-migration-count.sh`
- **Commit:** `f458491`

## Auth Gates

None encountered.

## Known Stubs

None.

## Threat Flags

None — all modified files are internal migration/retry infrastructure with no new network surface beyond the existing authenticated middleware chain.

## Threat Model Compliance

No threat model was defined for this plan's `<threat_model>` — not applicable.

## Verification Results

- ✅ `go build ./...` passes
- ✅ `go vet ./...` passes
- ✅ `bash scripts/ci-validate-migration-count.sh` exits 0
- ✅ Routes wired: `POST /schools/:id/retry-migration`, `GET /admin/migrations/errors`, `POST /admin/migrations/retry-all`
- ⏳ Endpoint verification skipped (requires running server + auth)

## Decisions Made

1. **SchemaName fetched via raw query, not model field**: `School` model doesn't expose `SchemaName` (it's on `SchoolConnection`). Fetching it directly from the `schools` table avoids coupling to the `SchoolConnection` domain model and keeps migration infrastructure independent of the connection management layer.

2. **CI script validates integrity, not raw count parity**: Core and school migrations serve different schemas (public vs tenant) and have inherently different counts (23 vs 6). The script validates that both lists are non-empty and have unique IDs rather than asserting equal counts.

## Commit History

| Task | Hash (backend) | Hash (parent) | Description |
|------|--------|--------|-------------|
| 1-2  | `8c6dd66` | — | Advisory locking, migration_errors model + migration, LogMigrationError |
| 3a-c | `5269c55` | — | Retry methods, school handlers, route wiring, SchemaName fix |
| 3d   | — | `f458491` | CI validation script + submodule pointer update |

## Self-Check: PASSED

- [x] `backend/internal/database/models/migration_errors.go` exists
- [x] `backend/internal/database/migrations/core/migration_errors.go` exists
- [x] `backend/internal/database/migrations/migration_errors.go` exists
- [x] `scripts/ci-validate-migration-count.sh` exists
- [x] `backend` commit `5269c55` exists
- [x] `parent` commit `f458491` exists
- [x] `go build ./...` passes
- [x] `go vet ./...` passes
