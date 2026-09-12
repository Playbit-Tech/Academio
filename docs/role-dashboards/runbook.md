# Ops Runbook: Permission Backfill

> **Audience:** DevOps, platform engineers.
> **Status:** PARTIAL — awaiting T5 staging execution. Prod execution gated on explicit owner authorization (Rule I1).

## Overview

The permission backfill ensures pre-v1.1 schools hold the new grants introduced in Phases 2–4:

| Grant | Target Roles | Purpose |
|-------|-------------|---------|
| `communication:write` | Principal | Academic-leadership broadcasts |
| `career:read` | Principal, Counselor | Counselor-profile oversight |
| `career:write` | Counselor | Career counseling CRUD |

The mechanism is **additive only** (`ON CONFLICT DO NOTHING`) and **rerun-safe**.

## Mechanism

`BackfillAllSchools` (`backend/internal/rbac/defaults.go:157-186`):

1. Iterates all schools
2. For each school, upserts default permissions for each role
3. Uses `ON CONFLICT DO NOTHING` — never overwrites custom grants
4. Skips custom roles (not in the 10 defaults)
5. Already wired into migrations and `make seed-demo`

## Pre-Flight Checklist

- [ ] Confirm target environment (staging/clone, never production without authorization)
- [ ] Verify `make migrate` is current
- [ ] Take a database snapshot (`pg_dump`)
- [ ] Record timestamp for before/after comparison

## Execution

### Option A: Via seed-demo (recommended)

```bash
# Dev/staging
make db-init DROP_TENANT=true && make migrate && make seed-demo

# Production (requires authorization)
make seed-demo
```

### Option B: Direct invocation

```bash
# One-off Go invocation
go run -v -tags=seed ./scripts/seed-demo/main.go
```

## Verification Queries

### Before

```sql
-- Per-school role grant diff
SELECT
  r.name AS role,
  p.name AS permission
FROM school_{id}.role_permissions rp
JOIN school_{id}.roles r ON r.id = rp.role_id
JOIN public.permissions p ON p.id = rp.permission_id
WHERE r.name IN ('principal', 'guidance-counselor', 'nurse')
  AND p.name IN ('communication:write', 'career:read', 'career:write', 'health:manage')
ORDER BY r.name, p.name;
```

### After

```sql
-- Verify grants present
SELECT
  r.name AS role,
  COUNT(*) AS grant_count
FROM school_{id}.role_permissions rp
JOIN school_{id}.roles r ON r.id = rp.role_id
JOIN public.permissions p ON p.id = rp.permission_id
WHERE r.name IN ('principal', 'guidance-counselor', 'nurse')
  AND p.name IN ('communication:write', 'career:read', 'career:write', 'health:manage')
GROUP BY r.name;

-- Verify custom roles untouched
SELECT
  r.name AS role,
  rp.*
FROM school_{id}.role_permissions rp
JOIN school_{id}.roles r ON r.id = rp.role_id
WHERE r.is_system = false;
-- Should return identical rows before/after
```

### Rerun-Safe Proof

```bash
# Run backfill twice, compare counts
make seed-demo  # first run
make seed-demo  # second run — should be no-op
# Counts should be identical
```

## Rollback

The backfill is additive only. To remove grants:

1. Delete specific `role_permissions` rows (if T8 is enabled)
2. Or: restore from `pg_dump` snapshot

**Never** run a "reverse backfill" — use T8's explicit removal for dead permissions.

## Custom Roles

Custom roles are skipped by the backfill. If a custom role needs new grants, use the RBAC admin UI or direct SQL. The backfill never touches custom role rows.

## Notes

- The `health:manage` grant for principal is new in Phase 4 (T1). It gates exactly one route: `GET /student-health/school-summary`. Parent holds only `health:read` → 403 on that summary (PHI gate).
- `career:read/write` for counselor is new in Phase 2 (T2). It was re-gated from `hr:read/hr:write` to the narrower career resource. The `career` DELETE stays on `hr:delete` by design.
- `communication:write` for principal is new in Phase 2 (T2). It enables the "Compose" nav item for academic-leadership broadcasts.
