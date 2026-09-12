# Multi-School Semantics

> **Audience:** Engineers, ops.
> **Source:** `backend/internal/modules/auth/service.go:1551-1555`.

## JWT School Selection

The JWT carries a single `school_id`. On login, the system uses **first-school-wins** semantics:

1. User has one school → that school is the JWT school.
2. User has multiple schools → the **first** school (by creation order) wins.
3. There is no school-switcher in the current UI — the JWT school is fixed for the session.

This means:
- All API calls use the JWT's `school_id` for tenant resolution.
- The `x-school-id` header is validated against the JWT's school — cross-school requests are rejected.
- Permission resolution is per-school (different schools can grant different permissions to the same user).

## Schema-Per-Tenant Isolation

Each school gets its own PostgreSQL schema (`school_{id}`). All school-specific data (students, teachers, scores, etc.) lives in the tenant schema. The `User` model lives in the shared `public` schema.

- **Shared tables:** `users`, `user_info`, `schools`, `school_connections`, `roles`, `permissions`
- **Tenant tables:** Everything else (students, teachers, scores, assessments, etc.)

## Permission Resolution

Permissions are resolved per-school via `GET /auth/me/permissions?school_id={id}`:

1. Super admins: bypass all RBAC (platform-wide)
2. School users: union of (role defaults) + (custom grants) − (revoked grants)
3. Custom roles: only explicitly granted permissions (no defaults)

The frontend uses the permission set from the JWT's school for all UI gating.

## First-School-Wins Implications

- If a user belongs to School A and School B, the JWT always targets School A.
- The sidebar shows only modules relevant to School A's permissions.
- To switch schools, the user must log out and log in with a different school context (future: school switcher).

## Staff and Custom Roles

Staff is permission-less by design (zero defaults). Permissions are granted per-school via the RBAC admin. This means:

- Staff user with `attendance:read` in School A has NO permissions in School B.
- The same user can be a teacher in School A and a staff member in School B.
- The JWT school determines which permission set applies.
