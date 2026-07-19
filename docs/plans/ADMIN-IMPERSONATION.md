# Admin User Impersonation

## ✅ COMPLETED

All backend and frontend implementation is in place:

### Backend
- `POST /api/v2/admin/impersonate` — generates impersonation token with `impersonator_id` claim
- `POST /api/v2/admin/impersonate/stop` — logs the end of impersonation
- `ImpersonatorID` field on JWT `Claims` in `pkg/jwt/jwt.go`
- Guardrails: super-admin and admin only, cannot impersonate super-admin, cannot impersonate self
- Audit logging on start/stop

### Frontend
- `auth-store.ts`: `impersonation` state with `startImpersonation`/`stopImpersonation` actions
- `api.ts`: `adminImpersonate(userId)` / `adminStopImpersonation()`
- `dashboard-layout.tsx`: impersonation banner at top
- `impersonation-banner.tsx`: visual warning bar with Stop button
- `users.tsx`: "Impersonate" action in user dropdown
- Super-admin school picker (`_super/super.$id.tsx`) with impersonate flow
