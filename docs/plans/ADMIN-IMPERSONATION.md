# Admin User Impersonation

## Goal

Allow a super-admin or school admin to "log in as" any other user from the user management page. The admin should be able to see the app exactly as that user sees it, perform actions on their behalf, and return to their own identity at any time.

---

## Design

### Impersonation session model

Impersonation creates a **temporary session** for the target user, while preserving the admin's original session. The JWT for the impersonated session carries an extra claim identifying the impersonator, so downstream systems (audit, logging, rate limiting) can distinguish genuine user actions from admin-on-behalf-of actions.

| Concept | Implementation |
|---------|---------------|
| Target user | Gets a fresh JWT pair generated for them |
| Impersonator ID | Stored as an optional `impersonator_id` claim in the access token |
| Audit trail | Every mutation during impersonation logs both `actor_id` (impersonator) and `user_id` (target) |
| Session restoration | Admin's original refresh token is saved in memory before impersonation starts |

### Guardrails

- Only `super-admin` and `admin` roles can impersonate
- `super-admin` cannot be impersonated (by anyone)
- Impersonated sessions inherit the target user's full permissions — they are not read-only
- All impersonation events are logged: start, stop, and every mutation action

---

## Backend Changes

### 1. New endpoint: `POST /api/v2/admin/impersonate`

```
Request:  { "user_id": uint }
Response: { "user": UserResponse, "authorization": TokenResponse }
```

The handler:

1. Checks the caller is `admin` or `super-admin` (via `helpers.GetRole(c)`)
2. Fetches the target user by ID
3. Rejects if target is `super-admin` (guardrail)
4. Generates a fresh token pair via `TokenService`, with an extra claim:
   ```go
   claims.ImpersonatorID = callerUserID  // new field on jwt.Claims
   ```
5. Logs an audit event with type `"impersonation:start"`, storing both actor and target IDs
6. Returns the same `AuthResponse` shape the frontend already expects (`user` + `authorization`)

### 2. New endpoint: `POST /api/v2/admin/impersonate/stop`

```
Request:  {}
Response: { "message": "impersonation ended" }
```

The handler:

1. Verifies the current token has an `impersonator_id` claim (i.e., the request is already impersonated)
2. Logs an audit event `"impersonation:stop"`
3. Returns a confirmation — the frontend restores the original session on its side

### 3. JWT claims change

Add an optional field to `Claims` in `pkg/jwt/jwt.go`:

```go
type Claims struct {
    // ... existing fields
    ImpersonatorID uint   `json:"impersonator_id,omitempty"`
}
```

This is `omitempty` — regular tokens are unaffected. When present, the token belongs to an impersonated session.

### 4. Audit logging integration

Write to `audit_logs` on impersonation start/stop. The existing `AuditLogging` middleware already captures all mutations, so every action taken during impersonation is automatically logged. The audit log has an `actor_id` field — if we set the context's actor ID to the impersonator's ID (not the target's), existing audit middleware writes the right thing without changes.

Alternatively, downstream consumers of audit logs can check the JWT claim directly via the `X-Impersonator-ID` header (see middleware section below).

### 5. Optional middleware: `ImpersonationContext`

A tiny middleware (can be added later) that reads the `impersonator_id` claim and injects an `X-Impersonator-ID` header or context key:

```go
func ImpersonationContext() gin.HandlerFunc {
    return func(c *gin.Context) {
        claims, _ := c.Get("claims")
        if c, ok := claims.(*jwt.Claims); ok && c.ImpersonatorID > 0 {
            c.Header("X-Impersonator-ID", strconv.FormatUint(uint64(c.ImpersonatorID), 10))
            c.Set("impersonator_id", c.ImpersonatorID)
        }
        c.Next()
    }
}
```

This is optional — the claim is already on the token. The header exists for middleware/service layers that don't parse JWTs directly.

---

## Frontend Changes

### 1. Users page — add "Impersonate" action to dropdown

In each user's action dropdown (student, teacher, staff tables), add a new item:

```
┌─────────────────────┐
│ View Details         │
│ Edit                 │
│ Impersonate     ←new │
│ ─────────────────── │
│ Deactivate           │
│ Delete               │
└─────────────────────┘
```

Clicking "Impersonate":
1. Shows a confirmation dialog: *"You are about to impersonate [User Name]. You will see the app as they see it. Continue?"*
2. Calls `POST /api/v2/admin/impersonate` with the user's ID
3. On success, saves the **current auth state** (admin's tokens + user) to a separate slot (e.g., `impersonation.originalSession` in Zustand)
4. Calls `setAuth()` with the new user + tokens from the response
5. Navigates to `/` (or `/dashboard`) — the app re-renders as the target user

### 2. Impersonation banner

A persistent bar at the top of the screen, above the sidebar, visible only during impersonation:

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠ Impersonating  │  John Doe (student)  │  [Stop Impersonating] │
└──────────────────────────────────────────────────────────────────┘
```

The banner:

- Shows the target user's name and role
- Has a red/orange accent color (visual warning)
- Is fixed at the top, outside the dashboard layout
- The "Stop Impersonating" button:
  1. Calls `POST /api/v2/admin/impersonate/stop`
  2. Restores the admin's original session from `impersonation.originalSession`
  3. Calls `setAuth()` with the original tokens + user
  4. Navigates to `/users` (back to where they started)

### 3. Zustand store changes

Add to the auth store:

```typescript
interface AuthState {
  // ... existing fields
  impersonation: {
    isActive: boolean;
    targetUser: User | null;
    originalSession: {
      user: User;
      accessToken: string;
      refreshToken: string;
    } | null;
  };
}
```

Add actions:

```typescript
startImpersonation: (targetUser: User, accessToken: string, refreshToken: string) => void;
stopImpersonation: () => void;
```

`startImpersonation` saves the current session to `originalSession` and loads the target's session. `stopImpersonation` reverses the swap. `clearAuth` also clears impersonation state.

---

## Audit Trail

| Event Type | Logged By | Data |
|-----------|-----------|------|
| `impersonation:start` | Backend handler | `actor_id` (admin), `target_id`, timestamp |
| `impersonation:stop` | Backend handler | `actor_id` (admin), `target_id`, duration |
| Mutations during impersonation | Existing AuditLogging middleware | Automatically captured — actor is the admin (via `impersonator_id` claim), target is the impersonated user |

---

## Files to Change

### Backend

| File | Change |
|------|--------|
| `pkg/jwt/jwt.go` | Add `ImpersonatorID uint \`json:"impersonator_id,omitempty"\`` to Claims |
| `internal/modules/auth/handler.go` | Add `Impersonate()` and `StopImpersonation()` handler methods |
| `internal/modules/auth/service.go` | Add `Impersonate(ctx, callerID, targetID)` with guardrails |
| `internal/modules/auth/dto.go` | No changes needed — reuse `AuthResponse` |
| `internal/router/router.go` | Register new routes in the admin-protected group |
| `internal/middleware/auth.go` | (Optional) Inject `impersonator_id` into context |

### Frontend

| File | Change |
|------|--------|
| `src/lib/stores/auth-store.ts` | Add `impersonation` state + `startImpersonation`/`stopImpersonation` actions |
| `src/routes/_dashboard/users.tsx` | Add "Impersonate" to student/teacher/staff action dropdowns |
| `src/lib/api.ts` | Add `adminImpersonate(userId)` / `adminStopImpersonation()` functions |
| `src/components/layout/dashboard-layout.tsx` | Add impersonation banner above sidebar |
| `src/components/layout/impersonation-banner.tsx` | New component: the banner |

---

## Open Questions

1. **Read-only vs full access?** Should impersonation be read-only (can view but not act), or full access (can mutate as the target)? The design above goes with full access + audit trail, which matches what most admin panels do (GitHub, Stripe, etc.).

2. **API scope during impersonation?** When impersonating, should the admin be restricted to endpoints available to the target's role? The JWT already carries the target user's role, so the existing role-checking middleware naturally enforces this — an admin impersonating a student cannot access `/admin/dashboard`.

3. **Should we store the original admin token server-side?** Currently the plan stores it in frontend Zustand memory. If we want to survive page refresh during impersonation, we'd need to store it server-side (Redis) with a key like `impersonation:{targetTokenJTI}:original_refresh`. Not needed for v1.

4. **Rate limiting during impersonation?** Apply the admin's rate limit tier (not the target's), since the actor is still the admin. The middleware could check `impersonator_id` claim to decide which tier to apply.
