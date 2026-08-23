# RBAC Enforcement Rollout Runbook (v1.1)

## Semantics
- Enforcement is **default-ON** for every school (absence of flag = enforced).
- Opt-out per school writes `school_feature_flags` row (`rbac_enforcement=false`).
- Flag cache TTL 30s — changes propagate within ~30s, no redeploy.
- Super-admins bypass ONLY under `/api/v2/admin/*`; elsewhere use impersonation.

## Enable / disable for a school
```bash
TOKEN=<super-admin-token>
# Disable (legacy behavior):
curl -X PUT http://localhost:8080/api/v2/admin/schools/<ID>/flags/rbac_enforcement \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": false}'
# Enable:
curl ... -d '{"enabled": true}'
```

## Verify
1. As school admin: `GET /api/v2/schools/<ID>/roles` → 200 with permissions.
2. As restricted role (teacher): any finance route → 403 PERMISSION_DENIED.
3. Cross-tenant probes green: `go test -tags=integration ./internal/security/probes/ -run TestRBAC_`.

## Rollback
Disable the flag for affected schools (above). Legacy behavior returns within
30s. Do NOT roll back the migration — role_permissions data must persist.
