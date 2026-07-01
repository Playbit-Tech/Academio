# Legacy Database Decommissioning Procedure

**Phase:** 07 — Validation & Rollout
**Plan:** 07-01
**Created:** 2026-07-01

---

## Overview

This procedure documents the safe decommissioning of the legacy SchoolCare database after all schools have been migrated to the new multi-tenant architecture. It is the final step before the legacy database can be permanently deleted.

**Do NOT begin this procedure until all pre-requisites are satisfied.**

## Pre-Requisites Checklist

Before starting decommissioning, confirm ALL of the following:

1. [ ] `07-ROLLOUT.md` Wave 4 Full Cut-Over is complete
2. [ ] 100% of active schools are provisioned on tenant databases
3. [ ] Zero cross-tenant discrepancies for 7 consecutive days post-cut-over
4. [ ] Legacy DB full backup verified in S3 Cold Storage (Glacier tier)
5. [ ] Row count reconciliation: legacy DB table totals match tenant DB aggregates
   - `Academic` module: session count, curriculum count, assessment count
   - `Finance` module: bill count, payment count
   - `HR` module: staff count, leave count
   - `User` module: total user count
6. [ ] Application monitoring dashboards show no legacy DB references
7. [ ] Runbook owner has confirmed with stakeholders

## Step 1: Legacy DB → Read-Only Mode (Day 1)

### Objective
Prevent any further writes to the legacy database while keeping it available for reads during the observation window.

### Procedure

1. **Application-Level Lock**
   - Update the legacy Laravel API to return `503 Service Unavailable` for all mutating requests:
     ```php
     // In Laravel middleware
     if ($request->isMethod('POST') || $request->isMethod('PUT') || $request->isMethod('DELETE') || $request->isMethod('PATCH')) {
         return response()->json([
             'success' => false,
             'error' => [
                 'code' => 'LEGACY_DB_READONLY',
                 'message' => 'This endpoint is deprecated. Please use the new API.'
             ]
         ], 503);
     }
     ```

2. **Database-Level Lock**
   - Connect to legacy PostgreSQL as a superuser:
     ```sql
     REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM legacy_app_user;
     REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM legacy_app_user;
     ```
   - If the legacy app uses multiple roles, lock all app roles.
   - **Do NOT run `DROP TABLE` or `TRUNCATE` at this stage.**

3. **Verification**
   - Attempt a write via the legacy API and confirm `503` response
   - Attempt a read via the legacy API and confirm data returns correctly
   - Attempt a write directly via `psql` as the app user and confirm permission denied

### Observation Window
- Maintain this state for **7 days**
- Monitor for any legacy write attempts (indicates hidden integration, bot, or migration gap)
- If any write is attempted:
  1. Investigate the source
  2. Add the source to the migration wait-list
  3. Do NOT proceed to Step 2 until the write source is resolved

## Step 2: Final Backup & Archival (Day 8)

### Objective
Create a definitive, verifiable snapshot of the legacy database before any destructive action.

### Procedure

1. **Logical Dump**
   ```bash
   pg_dump -Fc -v \
       --host=legacy-db-host \
       --port=5432 \
       --username=postgres \
       --dbname=schoolcare_legacy \
       --file=/tmp/schoolcare_legacy_final.dump
   ```

2. **Checksum Verification**
   ```bash
   sha256sum /tmp/schoolcare_legacy_final.dump
   # Record checksum in incident notes
   ```

3. **S3 Upload**
   ```bash
   aws s3 cp /tmp/schoolcare_legacy_final.dump \
       s3://schoolcare-backups/legacy/schoolcare_legacy_final_$(date +%Y%m%d).dump \
       --storage-class GLACIER
   ```
   - Set lifecycle policy: delete after 365 days unless thawed

4. **Table Count Reconciliation**
   Run the following and attach the output to the decommission ticket:
   ```sql
   SELECT schemaname, relname, n_tup_ins, n_tup_upd, n_tup_del
   FROM pg_stat_user_tables
   ORDER BY schemaname, relname;
   ```

5. **Verification**
   - Compare checksum against previous backup (from Wave 4)
   - Confirm S3 upload succeeded (`aws s3 ls`)
   - Confirm no new writes occurred during the Step 1 observation window

## Step 3: DNS & API Deprecation (Day 9)

### Objective
Remove all user-facing access to the legacy API so that the database becomes invisible to end users.

### Procedure

1. **DNS TTL Reduction**
   - Reduce TTL on legacy subdomain to 60 seconds (pre-cut-over already done in Wave 4)

2. **API Return-to-Sender**
   - Update legacy API to return `410 Gone` for ALL endpoints (including GET)
   - Add `Retry-After: 86400` header (24 hours)
   - Response body should include migration documentation link

3. **Load Balancer Removal**
   - Remove legacy API upstream from load balancer entirely
   - Confirm health checks fail for legacy API instances

4. **Verification**
   - `curl -I https://legacy-api.schoolcare.ng` returns `HTTP/1.1 410 Gone`
   - New API continues serving all traffic without errors
   - No references to legacy hostname in application logs

## Step 4: Database Deletion (Day 10+)

### Objective
Permanently remove the legacy database from production infrastructure.

### Prerequisites Before This Step
- [ ] Step 1 observation window passed with zero incidents
- [ ] Step 2 backup verified in S3 Glacier
- [ ] Step 3 DNS and LB removal confirmed

### Procedure

1. **Final Connection Audit**
   ```sql
   SELECT pid, usename, application_name, client_addr, state
   FROM pg_stat_activity
   WHERE datname = 'schoolcare_legacy';
   ```
   - Terminate any remaining connections
   - Confirm zero active connections

2. **Database Drop**
   ```sql
   DROP DATABASE IF EXISTS schoolcare_legacy;
   ```

3. **Role Cleanup** (optional)
   ```sql
   DROP ROLE IF EXISTS legacy_app_user;
   ```

4. **Infrastructure Cleanup**
   - Remove legacy database credentials from secrets manager
   - Remove legacy database host from connection whitelist
   - Archive or terminate legacy database server/pod
   - Update architecture diagrams to remove legacy DB references

5. **Verification**
   - Confirm database no longer exists: `\l` in `psql`
   - Confirm no application logs reference the legacy host
   - Confirm no monitoring alerts for the legacy host

## Step 5: Post-Decommission Audit (Day 17)

### Objective
Verify that the legacy system is fully retired and no recovery is needed.

### Procedures

1. **Spot-check queries**
   - Compare tenant DB counts against the Step 2 backup counts for 5 random schools
   - Verify no tenant DB has missing tables compared to the expected schema

2. **Documentation Update**
   - Update `PROJECT.md` to reflect legacy DB removal
   - Update `README.md` architecture section
   - Update runbooks to remove legacy references

3. **Team Notification**
   - Announce completion in the engineering channel
   - Tag stakeholders for sign-off

## Emergency Recovery

If a critical data issue is discovered post-decommission:

1. **Stop** all tenant DB writes immediately (read-only mode if possible)
2. **Restore** legacy dump from S3 Glacier to a temporary database:
   ```bash
   pg_restore -d schoolcare_legacy_recovery /tmp/schoolcare_legacy_final.dump
   ```
3. **Diff** the affected tenant tables against the restored legacy tables
4. **Repair** the tenant DB with the missing/correct data
5. **Resume** normal operations once verification passes
6. **Retro**: Run a blameless postmortem on why the issue was not detected in Wave 4

## References

- `07-ROLLOUT.md` — Staged rollout procedures
- `backend/internal/database/tenant/testcontainers_setup.go` — Integration test environment
- `backend/internal/database/migrations/migrations.go` — Migration engine
- `pkg/response/response.go` — API response envelope standards
