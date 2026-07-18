---
phase: 01-foundation-hardening
plan: 02
subsystem: database
tags:
  - postgres
  - schema-per-tenant
  - search_path
  - pgbouncer
  - gorm
  - audit

# Dependency graph
requires:
  - phase: 01-foundation-hardening
    plan: 01
    provides: Provisioning & migration infrastructure that this plan audits

provides:
  - Verified search_path isolation audit confirming zero connection-level SET search_path calls
  - Architecture decision record for search path isolation strategy (4 code paths documented)
  - Updated production audit checklist with search path gate item

affects:
  - All subsequent phases that touch tenant-scoped queries or raw SQL

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SchemaTablePrefix GORM plugin as default isolation mechanism"
    - "SET LOCAL search_path inside GORM transactions for migrations only"
    - "--schema= flag for pg_dump/pg_restore"
    - "Explicit schema qualifiers (schema.table) for raw SQL"

key-files:
  created:
    - docs/architecture/search-path-strategy.md
  modified:
    - docs/architecture/10-AUDIT-CHECKLIST.md

key-decisions:
  - "GORM SchemaTablePrefix plugin is the correct primary isolation strategy — it's PgBouncer-compatible, survives connection pool reuse, and requires zero PostgreSQL session state changes"
  - "SET LOCAL search_path inside transactions is acceptable only for migrations (where DDL conflicts with pgx prepared-statement cache prevent using the plugin)"
  - "Raw SQL with explicit schema qualifiers (%s.tablename) is a correct pattern — it does not depend on search_path"
  - "pg_dump --schema= and pg_restore --schema= flags are the correct approach for backup/restore (CLI tools, not GORM)"

patterns-established:
  - "Rule: If a query touches a tenant table, either use SchemaDB.DB() (plugin prefix), %s.tablename with schema name (raw SQL), --schema= flag (CLI tools), or SET LOCAL in transaction (migrations only)"
  - "Anti-pattern: Connection-level SET search_path is forbidden — it leaks across pooled connections"

requirements-completed:
  - INFRA-02

# Metrics
duration: 12min
completed: 2026-07-18
---

# Phase 01 Foundation Hardening — Plan 02: SchemaTablePrefix search_path Audit

**SchemaTablePrefix search_path audit: zero connection-level SET search_path violations found, isolation strategy documented across 4 code paths**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-18T23:00:00Z
- **Completed:** 2026-07-18T23:12:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- **Complete codebase audit** of all `SET search_path`, `SET LOCAL`, `pg_dump`, `pg_restore`, and `CREATE SCHEMA` usage — confirmed **zero connection-level `SET search_path` calls** exist
- **Verified `SchemaTablePrefix` plugin** in `schema_db.go` — correct PgBouncer-compatible approach using context-based prefixing with Set/Get for cross-session survival; no `.Unwrap()` misuse for tenant queries
- **Documented all 4 schema isolation code paths** with mechanism, correctness proof, and file references
- **Updated production audit checklist** with a search path isolation gate item to prevent regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit all raw SQL** — No changes needed (zero violations found)
2. **Task 2: Document search_path isolation strategy** — `adefcb5` (feat: document strategy + update checklist)

**Plan metadata:** (included in Task 2 commit)

## Files Created/Modified

- `docs/architecture/search-path-strategy.md` — Complete search path isolation strategy covering problem statement, decision table, 4 code paths, anti-patterns, and verification commands
- `docs/architecture/10-AUDIT-CHECKLIST.md` — Added search path isolation audit item under Tenant Isolation section

## Decisions Made

- **GORM SchemaTablePrefix plugin as primary isolation**: The plugin prefixes table names at the SQL statement level, making it PgBouncer-compatible and immune to connection pool reuse. This is the correct default for all API queries.
- **SET LOCAL for migrations only**: DDL operations invalidate pgx prepared-statement caches, so migrations use a separate GORM connection without `PrepareStmt`. `SET LOCAL search_path` inside a transaction is safe because the setting is automatically reverted on transaction end.
- **Explicit schema qualifiers for raw SQL**: The `%s.tablename` pattern in `academic/repository.go` and `academic/service.go` is correct — the schema is baked into the SQL, not dependent on search_path.
- **Backup/restore via `--schema=` flag**: `pg_dump` and `pg_restore` target schemas explicitly via CLI flags, which is the most precise mechanism.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Pre-existing build error in `backend/pkg/pdf/generator.go:5` (`"errors" imported and not used`) is unrelated to this plan. Logged to `deferred-items.md`.

## Verification Results

| Check | Result |
|-------|--------|
| Zero connection-level `SET search_path` | ✅ Only `SET LOCAL` in transaction (correct) |
| `pg_dump` uses `--schema=` flag | ✅ `backup/service.go` line 119 |
| `pg_restore` uses `--schema=` flag | ✅ `restore/service.go` line 160 |
| `CREATE SCHEMA` uses explicit name | ✅ `provisioning.go` line 102, `migration_service.go` line 168 |
| Strategy doc exists | ✅ `docs/architecture/search-path-strategy.md` |
| Audit checklist updated | ✅ New item at line 362 |
| Build passes | ⚠️ Pre-existing `pkg/pdf/generator.go` error (unrelated) |

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Codebase is verified clean for search_path isolation — no connection-level leaks exist
- Future phases can reference `docs/architecture/search-path-strategy.md` for the canonical isolation strategy
- Audit checklist gate item will catch any regression adding `SET search_path` without LOCAL

## Self-Check: PASSED

All assertions verified:
- `docs/architecture/search-path-strategy.md` — FOUND
- Commit `adefcb5` — FOUND
- Zero connection-level `SET search_path` — PASS (only a comment references it)
- Audit checklist updated — FOUND

---

*Phase: 01-foundation-hardening*
*Completed: 2026-07-18*
