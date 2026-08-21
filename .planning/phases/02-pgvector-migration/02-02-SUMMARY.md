---
phase: 02-pgvector-migration
plan: 02
subsystem: infra, database
tags: [postgres, pgvector, docker, migrations, gorm]

# Dependency graph
requires:
  - phase: 02-pgvector-migration
    provides: 02-CONTEXT.md locked decisions D-01..D-14, 02-RESEARCH.md image pin + extension mechanics
provides:
  - Running pgvector-backed Postgres 18.4 (shared-postgres) with `vector` in pg_extension owned by `public`
  - Pinned compose source of truth (backend/docker-compose.yml) + live infra compose (shared-infrastructure) on pgvector/pgvector:0.8.6-pg18-trixie
  - Versioned idempotent core migration 2026_08_01_000000_enable_vector_extension installing the extension before any school DDL
affects: [02-03 (tenant ai_vectors DDL), 02-04 (PGVectorStore), 02-05 (copy tool), 02-06 (config swap)]

# Tech tracking
tech-stack:
  added: [pgvector/pgvector:0.8.6-pg18-trixie docker image (PG 18.4 + pgvector 0.8.6)]
  patterns:
    - "Core migration installs CREATE EXTENSION IF NOT EXISTS vector into public schema (runs before school migrations via ApplyCoreMigrations at startup)"
    - "Idempotent versioned migrations with single-statement Exec per Rule B4/B13"

key-files:
  created: [backend/internal/database/migrations/core/vector.go]
  modified: [backend/docker-compose.yml, backend/internal/database/migrations/core/core.go, /home/playbit/Playbit/shared-infrastructure/docker-compose.yml (external, not in git)]

key-decisions:
  - "Pinned pgvector/pgvector:0.8.6-pg18-trixie (>=0.8.2, CVE-2026-3172 fixed); verified empirically that PGDATA is /var/lib/postgresql/18/docker identical to running postgres:alpine 18.4, so the shared-postgres-data volume survives the swap"
  - "Extension installed via core migration (not tenant) so it lands in public (default search_path at core-migration time); tenant DDL will schema-qualify public.vector"
  - "Single-statement Exec in migration (CREATE EXTENSION IF NOT EXISTS vector) per Rule B4/B13 - pgx v5 prepared-statement constraint"

patterns-established:
  - "Extension install = core migration owns install; tenant migrations repeat IF NOT EXISTS as harmless no-op (spec compliance only)"
  - "Migration IDs follow YYYY_MM_DD_HHMMSS_slug; tracked in schema_migrations with advisory-lock serialization"

requirements-completed: [PGV-01, PGV-02]
# Note: PGV-02 shared half ships here (core/public install); the tenant half (repeat IF NOT EXISTS in school migrations)
# ships with 02-03 tenant DDL, which depends on this plan's public install.

# Metrics
duration: 5min
completed: 2026-08-01
---

# Phase 02 Plan 02: pgvector Image Swap + Core Extension Migration Summary

**Pinned dev Postgres to pgvector/pgvector:0.8.6-pg18-trixie (PG 18.4, CVE-2026-3172 fix) and installed the vector extension in the shared public schema via a versioned idempotent core migration, with verified zero data loss across the container recreate**

## Performance

- **Duration:** 5 min
- **Started:** 2026-08-01T05:51:06Z
- **Completed:** 2026-08-01T05:56:12Z
- **Tasks:** 2
- **Files modified:** 3 in repo (backend submodule) + 1 external (shared-infrastructure, not in git)

## Accomplishments
- Postgres image swapped to `pgvector/pgvector:0.8.6-pg18-trixie` in BOTH `backend/docker-compose.yml` (repo source of truth) and `/home/playbit/Playbit/shared-infrastructure/docker-compose.yml` (live `shared-postgres` container). Container recreated healthy in 4 checks.
- **Critical A1 verification passed:** pgvector image reports `PGDATA=/var/lib/postgresql/18/docker` and PostgreSQL 18.4 — byte-identical to the running `postgres:alpine` container, so the `shared-postgres-data` volume (mounted at `/var/lib/postgresql`) was reused transparently. Zero data loss confirmed pre/post (8 DBs, 16 public tables, 1908 tenant tables across 12 school schemas, 103 users all intact).
- `vector` now in `pg_available_extensions` AND `pg_extension` (owned by schema `public`). Functional smoke test: `'[1,2,3]'::public.vector(3) <-> '[4,5,6]'::public.vector(3)` → 5.196 (√27, correct).
- New core migration `2026_08_01_000000_enable_vector_extension` (VectorExtensionMigration) registered in `CoreMigrations()`, applied at server startup via `ApplyCoreMigrations` before any school DDL, recorded in `schema_migrations`.

## Task Commits

Each task was committed atomically in the backend submodule (branch `dev`):

1. **Task 1: Swap Postgres image to pgvector (PGV-01)** - `8e3086c` (chore)
2. **Task 2: Versioned core extension migration (PGV-02 shared)** - `f987f47` (feat)

**Plan metadata:** `docs(02-pgvector-02): complete pgvector image swap + extension migration plan` (final commit, root repo)

## Files Created/Modified
- `backend/docker-compose.yml` - postgres service image pinned to `pgvector/pgvector:0.8.6-pg18-trixie` (academio-pg source of truth; volume `postgres_data:/var/lib/postgresql/data` unchanged)
- `backend/internal/database/migrations/core/vector.go` (new) - `VectorExtensionMigration()` returning `migration.Migration{ID: "2026_08_01_000000_enable_vector_extension", Migrate: CREATE EXTENSION IF NOT EXISTS vector, Rollback: DROP EXTENSION IF EXISTS vector}`; single-statement Exec per Rule B4/B13; idempotent
- `backend/internal/database/migrations/core/core.go` - appended `VectorExtensionMigration()` to `CoreMigrations()` slice
- `/home/playbit/Playbit/shared-infrastructure/docker-compose.yml` - shared-postgres image pinned to the same pgvector tag (external file, NOT in a git repo — edited locally per plan, not committed)

## Decisions Made
- Followed plan exactly — image pin `0.8.6-pg18-trixie` chosen over `0.8.5` (latest, contains CVE fix; matches running PG 18.4). No deviations.
- Migration field names `Migrate`/`Rollback` (not Up/Down) per `migration/types.go` — matched ai.go pattern.

## Deviations from Plan

None - plan executed exactly as written. (No Rule 1/2/3/4 deviations; no deferred items; nothing logged to deferred-items.md.)

## Issues Encountered
- None. The one environment quirk (zsh `status` is a read-only variable in the health-wait loop) was a shell scripting detail, resolved by renaming the variable — no code impact.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- **02-03 (tenant `school_{id}.ai_vectors` DDL):** extension is installed in `public` so tenant DDL can reference `public.vector(1536)` / `public.vector_cosine_ops`. Tenant migrations repeat `CREATE EXTENSION IF NOT EXISTS vector` per spec (PGV-02 tenant half) — will no-op because the core install precedes it. Research pitfall: tenant DDL MUST schema-qualify `public.vector` and `public.vector_cosine_ops` (schema-only search_path in ApplySchoolMigrationsForSchema).
- **02-04 (PGVectorStore):** no backend Go dependency on pgvector-go added in this plan (deferred to 02-04 per plan); extension availability verified at DB level.
- **Blocker check:** zero data loss on swap means no `make db-init DROP_TENANT=true` reset needed. Assumption A1 (data-dir compatibility) is now empirically resolved — not just assumed.

---
*Phase: 02-pgvector-migration*
*Completed: 2026-08-01*

## Self-Check: PASSED
- Files verified on disk: vector.go, core.go, docker-compose.yml, 02-02-SUMMARY.md
- Commits verified: 8e3086c (task 1), f987f47 (task 2)
- must_haves artifact greps: image pin (1), migration ID (1), VectorExtensionMigration in core.go (1)
