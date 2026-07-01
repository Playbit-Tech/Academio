# Staged Rollout Runbook

**Phase:** 07 — Validation & Rollout
**Plan:** 07-01
**Created:** 2026-07-01

---

## Overview

This runbook defines the production switch-over from the legacy SchoolCare API to the new multi-tenant Go API. The rollout proceeds in four escalating stages, each with explicit success criteria, gate checks, and documented rollback procedures.

## Pre-Flight Checklist

Before beginning Wave 1, verify the following:

- [ ] All Phase 7 validation tests pass (`go test -tags=integration ./internal/database/tenant/`)
- [ ] Staging environment is provisioned with production-equivalent PostgreSQL (v16+), Redis, and minIO/S3
- [ ] Multi-tenant routing is verified across all 39 module services
- [ ] Backup pipeline is tested end-to-end (`BackupService` → S3)
- [ ] Monitoring dashboards are active (connection pool metrics, DB size, error rates)
- [ ] War room communication channel is established (Slack/Discord incident bridge)

## Wave 1: Internal Beta (Staging)

### Objective
Validate tenant provisioning, migration, and routing on a non-production footprint using pilot schools.

### Prerequisites
- Staging environment mirrors production infrastructure
- Pilot schools identified (3–5 schools with low student counts)

### Procedures

1. **Environment Preparation**
   - Deploy the new Go API to staging
   - Point API to staging core PostgreSQL
   - Ensure `APP_ENV=staging` and TLS is configured

2. **Pilot School Provisioning**
   - For each pilot school:
     a. Run `ProvisioningService.ProvisionSchool(ctx, schoolID)` via API or admin CLI
     b. Confirm dedicated tenant database is created
     c. Run `MigrationService.ApplySchoolMigrations(tenantDB, schoolID)`
     d. Verify tenant connection is cached in `ConnectionManager`
     e. Confirm `TenantResolutionService.ResolveTenant` returns valid `TenantContext`

3. **Smoke Testing**
   - Perform CRUD operations for each pilot school via API
   - Verify cross-tenant data isolation (School A cannot query School B resources)
   - Confirm JWT token school-scoping works end-to-end

4. **Performance Baseline**
   - Run `BenchmarkSchoolMigration_Apply` and record p50/p95 latency
   - Run `BenchmarkConcurrentTenantAccess` and record throughput
   - Compare against legacy API latency metrics

### Success Criteria
- All pilot schools provisioned and migrated without error
- Zero cross-tenant leaks detected
- API latency within 10% of legacy baseline

### Rollback
- Stop provisioning cron job
- Truncate tenant databases created during Wave 1
- Revert staging deploy to previous API version
- Legacy DB remains untouched (no risk)

---

## Wave 2: Shadow Phase (Traffic Mirroring)

### Objective
Compare new API responses against the legacy Laravel API in production-readiness mode without affecting users.

### Prerequisites
- Wave 1 success
- Production canary (DNS-style or proxy-style) infrastructure ready

### Procedures

1. **Traffic Mirroring Configuration**
   - Option A: **Nginx Mirror Module** (preferred if Nginx is used)
     ```nginx
     mirror /mirror;
     mirror_request_body on;
     location /mirror {
         internal;
         proxy_pass http://new-go-api:8080;
     }
     ```
   - Option B: **GoReplay**
     ```bash
     gor --input-raw :8080 \
         --output-http http://new-go-api:8080 \
         --output-http-status-header X-GoReplay-Target
     ```

2. **Comparison Methodology**
   - Mirror 100% of production traffic to the new API (read-only)
   - Log response status codes, latencies, and payload diffs
   - Alert on:
     - HTTP status code mismatch (expected: identical)
     - Payload schema mismatch (UUID vs Int ID columns)
     - Error rate delta > 0.5%

3. **Duration**
   - Minimum 48 hours of mirrored traffic
   - Minimum 7 consecutive days of zero discrepancies before advancing

4. **Metrics Collection**
   - Record `BenchmarkRepositoryFactory_ForSchool` p95 per request
   - Track `MigrationService` queue depth
   - Monitor S3 backup upload success rate

### Success Criteria
- Zero shadow discrepancies for 7 consecutive days
- New API p95 latency <= legacy p95 latency
- Zero unauthorized cross-tenant access events in logs

### Rollback
- Disable traffic mirroring (remove Nginx `mirror` or stop GoReplay)
- Legacy API continues serving production traffic unaffected
- No data migration performed in this wave, so no cleanup needed

---

## Wave 3: Canary Rollout (10%)

### Objective
Gradually route 10% of production traffic to the new API, maintaining the legacy API as warm standby.

### Prerequisites
- Wave 2 success (7 days clean shadow)
- Legacy API remains fully operational on the old database
- DNS or load balancer supports weighted routing

### Procedures

1. **DNS / Load Balancer Configuration**
   - Configure weighted DNS or `Router` upstream to split traffic:
     ```
     10% -> new-go-api (tenant-routed)
     90% -> legacy-laravel-api (legacy DB)
     ```

2. **Monitoring Window**
   - Monitor for 24 hours at 10% traffic
   - Key metrics:
     - `GET /api/v2/health` response time
     - Tenant DB connection pool utilization (`MaxOpenConns` / `MaxIdleConns`)
     - Cross-tenant error replay count (expected: 0)
     - Legacy API latency (expected: unchanged)

3. **Ramp Criteria**
   - If error rate < 0.1% for 24 hours -> proceed to 25% traffic
   - If error rate spikes -> pause at current traffic level, investigate, then decide
   - If error rate > 1% -> emergency rollback to 100% legacy

### Success Criteria
- 10% traffic serves successfully with zero data loss
- Tenant-scoped school data matches legacy fetch results
- Monitoring dashboards remain stable for 24 hours

### Rollback
- Change DNS/LB weight to 0% -> new API, 100% -> legacy
- Legacy API remains the source of truth
- Tenant DBs created during canary are retained for re-use (do not delete)

---

## Wave 4: Full Cut-Over

### Objective
Migrate all schools to the new multi-tenant API and deprecate the legacy Laravel API.

### Prerequisites
- Wave 3 success (25%, 50%, 75% stages all successful)
- All schools either already provisioned or scheduled for same-day migration
- Legacy API team is on standby for emergency revert
- S3 cold storage contains verified full backup of legacy DB

### Procedures

1. **Final Legacy DB Backup**
   - Run `pg_dump` of the entire legacy database
   - Upload to S3 with lifecycle policy: **Glacier after 30 days, delete after 365 days**
   - Verify backup checksum and row counts

2. **Bulk School Migration**
   - Trigger `MigrationService.MigrateAllTenants()` for all active schools
   - Verify `schema_migrations` version across all tenant databases
   - Run reconciliation script: compare row counts between legacy and tenant tables for critical modules (Academic, Finance, HR)

3. **DNS Cut-Over**
   - Update DNS to 100% -> new-go-api
   - Verify load balancer health checks pass
   - Monitor API gateway for 200-level response rate

4. **Legacy API Deprecation**
   - Return `410 Gone` for all endpoints on the legacy domain
   - Include `Retry-After` header pointing to migration guide
   - Keep legacy API read-only for 30 days, then decom

### Success Criteria
- 100% of active schools traffic routed to new API
- Zero replayed cross-tenant errors for 24 hours post-cut-over
- Legacy DB backup confirmed in S3
- All critical endpoints (Billing, User Management, Academic) verified working

### Rollback
- **Emergency DNS revert:** Change DNS back to legacy-laravel-api (requires DNS TTL < 60s)
- Legacy DB is still online and read-write, so no data divergence risk
- If tenant DB divergence detected, pause at legacy, restore last known-good tenant DB from S3, and re-run migration for affected schools only

---

## Post-Cutover Monitoring

| Metric | Threshold | Action |
|--------|-----------|--------|
| New API 5xx rate | > 0.5% | Page on-call engineer |
| Legacy DB diff | any row count discrepancy > 0.1% | Freeze traffic; compare tenant DB to last backup |
| Tenant DB connection pool exhaustion | > 80% utilization | Scale connection manager `MaxOpenConns` per tenant |
| Cross-tenant leak alert | any occurrence | Immediate traffic isolation and incident review |

## Decommissioning Gate

The legacy database **cannot** be deleted until all of the following are satisfied:

1. [ ] 100% of active schools provisioned and verified on tenant DBs
2. [ ] Zero shadow discrepancies for 7 consecutive days after full cut-over
3. [ ] Full backup of legacy DB stored in S3 (Cold Storage)
4. [ ] All critical endpoints (Billing, User Management, Academic) verified operational on new API
5. [ ] Runbook 07-DECOMMISSION.md completed

Once the gate is passed, proceed to the `07-DECOMMISSION.md` procedure.
