# Backend Authoritative, UI is UX

> **Audience:** Engineers, security reviewers.
> **Source:** `frontend/src/lib/auth/route-guard.ts:27-47`.

## Principle

The backend is the single source of truth for authorization. The frontend provides UX convenience (hiding nav items, redirecting on direct URL access) but never enforces security.

## Defense Layers

### Layer 1: Sidebar Filtering (UX)

The sidebar filters visible items based on the permission snapshot (`usePermissions` hook). This is purely cosmetic — a user never sees a module they can't access, but the filtering happens client-side.

**Implementation:** `NAV_PERMISSIONS` map in `role-config.ts` → `useFilteredNav` hook.

### Layer 2: Route Guard (UX + mild security)

`requirePermission()` in `route-guard.ts` checks the cached permission snapshot before rendering a route. If the snapshot is stale (still resolving), it **allows through** and lets `<Can>` fail-close.

**Key behavior:** Stale snapshot → allow through → `<Can>` in UI hides buttons. Backend still rejects forged API calls.

### Layer 3: Backend RBAC (Security)

Every API endpoint with a permission gate checks the JWT's school-scoped permissions server-side. This is the real security boundary.

**Examples:**
- `POST /finance/expenses/:id/approve` requires `finance:write` → librarian gets 403
- `PUT /academic/result/:id/approve` requires `sessions:write` → teacher gets 403
- `GET /student-health/school-summary` requires `health:manage` → parent gets 403

### Layer 4: `<Can>` Component (UX)

The `<Can>` component in React conditionally renders write/delete CTAs based on permissions. This hides buttons that would fail on the backend anyway.

**Pattern:** `<Can permission="finance:write"><Button onClick={approve}>Approve</Button></Can>`

## Failure Modes

| Layer | Failure | Consequence |
|-------|---------|-------------|
| Sidebar | Stale permissions | User sees nav item they can't access → clicks → 403 |
| Route Guard | Stale snapshot | User reaches page → `<Can>` hides buttons → no action possible |
| Backend | Forged API call | 403 returned → UI shows error |
| `<Can>` | Missing gate | User sees button → clicks → 403 from backend |

**Bottom line:** The backend is always authoritative. The frontend layers are UX optimizations that degrade gracefully — they never grant access that the backend would deny.

## Verification

T4a E2E proves this with forged-call spot-checks:
- Teacher forged approve → 403 (backend denies)
- Librarian forged expense approve → 403 (backend denies)
- Counselor forged discipline POST → 403 (backend denies)

The frontend `<Can>` gates prevent these buttons from rendering, but the backend 403 is the real security boundary.
