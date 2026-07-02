# Phase 07: Validation & Rollout - Research

**Researched:** 2026-07-01
**Domain:** System Validation, Integration Testing, and Production Rollout
**Confidence:** HIGH

## Summary

Phase 7 marks the transition from a feature-complete "greenfield" implementation to a production-ready state. The primary technical challenge is verifying that the complex multi-tenant DB routing (implemented in Phase 6) is robust, secure, and performant across all modules before the legacy database can be decommissioned.

The current infrastructure provides basic E2E scripts and unit tests, but lacks a dedicated "Tenant Lifecycle" test suite that spans Provisioning $\rightarrow$ Migration $\rightarrow$ Routing $\rightarrow$ Isolation. 

**Primary recommendation:** Implement a "Tenant Validation Suite" using a real PostgreSQL Docker instance (via `testcontainers-go`) to verify the full database creation and routing lifecycle, combined with a "Shadow Traffic" period where the new API is compared against the legacy Laravel API.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `testcontainers-go` | Latest | Disposable DBs | Standard for Go integration tests requiring real Postgres |
| `go test` | 1.22+ | Test Runner | Native tooling with `integration` build tags already in use |
| `curl` / `bash` | System | E2E Smoking | Existing `test_e2e.sh` provides fast high-level verification |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlmock` | Latest | Unit Isolation | Already used in `isolation_test.go` for rapid logic checks |
| `httptrace` | Native | Latency Audit | To measure routing overhead added by `TenantDBResolver` |

## Architecture Patterns

### Tenant Lifecycle Verification Flow
To ensure a school is "production-ready," the following chain must be verified:
`ProvisioningService.ProvisionSchool()` $\rightarrow$ `CREATE DATABASE` $\rightarrow$ `MigrationService.ApplySchoolMigrations()` $\rightarrow$ `TenantDBResolver` (JWT $\rightarrow$ DB) $\rightarrow$ `TenantRepositories` $\rightarrow$ `ModuleService`.

### Pattern 1: Shadow Testing (Dual-Run)
**What:** Routing a percentage of production traffic to both the Legacy Laravel API and the New Go API, comparing responses and logging discrepancies.
**When to use:** During the "Staged Switch-over" before full DNS cut-over.
**Example:** Use a Reverse Proxy (Nginx/Caddy) with a mirror module to send requests to both backends.

### Anti-Patterns to Avoid
- **Mock-Only Isolation Tests:** Relying solely on `sqlmock` (as seen in some current tests) to prove isolation. Real PostgreSQL permissions and `CREATE DATABASE` constraints must be tested.
- **Big Bang Cut-over:** Switching all DNS to the new API at once without a fallback path to the legacy DB.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test DB Lifecycle | Custom shell scripts for Postgres | `testcontainers-go` | Handles port mapping and cleanup reliably across environments |
| Traffic Mirroring | Custom Go proxy | Nginx `mirror` module or GoReplay | Mature, high-performance traffic shadowing |

## Common Pitfalls

### Pitfall 1: Connection Pool Exhaustion
**What goes wrong:** Each tenant DB has its own pool. 100 schools $\times$ 10 connections = 1,000 connections on the Postgres server.
**Why it happens:** `ConnectionManager` might not aggressively close idle connections or limit max pool size per tenant.
**How to avoid:** Set `MaxOpenConns` and `MaxIdleConns` specifically for tenant pools; implement a TTL for inactive tenant connections.

### Pitfall 2: Migration Drift
**What goes wrong:** A core DB migration is applied, but some tenant DBs fail their specific migration.
**Why it happens:** Parallel migration in `MigrationService` might fail for a subset of schools without a proper retry/alert mechanism.
**How to avoid:** Implement a "Migration Audit" report that lists all schools and their current `schema_migrations` version.

## Verification Matrix

| Risk | Validation Method | Test Type | Target |
|------|-------------------|-----------|---------|
| **Cross-Tenant Leak** | Create School A and B; try to query School A's data using School B's JWT | Integration | `TenantDBResolver` |
| **Provisioning Failure** | Simulate DB permission error during `CREATE DATABASE` | Negative | `ProvisioningService` |
| **ID System Mismatch** | Verify UUIDs in Core DB map correctly to Ints in Tenant DBs | Integration | API Compatibility |
| **Routing Overhead** | Benchmark request latency with vs. without tenant resolution | Performance | `middleware.TenantDBResolver` |
| **Data Loss** | Compare record counts/sums between Legacy DB and New Tenant DBs | Data Audit | Migration Sync |

## Production Rollout Strategy

### Staged Switch-over Plan
1. **Internal Beta (Wave 1):** Deploy New API to a staging env; manually migrate 3-5 "pilot" schools.
2. **Shadow Phase (Wave 2):** Mirror production traffic to New API (read-only). Compare responses.
3. **Canary Rollout (Wave 3):** Switch DNS for 10% of schools. Keep legacy DB as read-only backup.
4. **Full Cut-over (Wave 4):** Transition all schools. Legacy API remains active but returns 410 Gone for migrated tenants.

### Decommissioning Criteria
The legacy database is deleted **ONLY** after:
- [ ] 100% of active schools are provisioned in New API.
- [ ] Zero "Shadow" discrepancies for 7 consecutive days.
- [ ] Full Backup of legacy DB stored in S3 (Cold Storage).
- [ ] All critical endpoints (Billing, User Management, Academic) verified.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Integration Tests | ✓ | System | Manual Postgres install (slow) |
| Nginx/Caddy| Shadow Traffic | ✗ | — | Application-level mirroring |
| S3/MinioS | Backups | ✓ | System | Local disk storage |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `testcontainers-go` is compatible with CI runner | Standard Stack | Tests cannot run in pipeline |
| A2 | DNS switch can be done per-tenant/subdomain | Rollout Strategy | Must do "Big Bang" switch |
| A3 | Legacy DB is PostgreSQL compatible | Decommissioning | Migration tools may need custom drivers |

## Open Questions

1. **Connection Limits:** What is the maximum number of concurrent tenant databases the current Postgres hardware can support?
   - *Recommendation:* Perform a load test with 50+ mock tenants.
2. **ID Mapping:** Are there any edge cases where the UUID $\rightarrow$ Int conversion in Phase 5 causes collisions across different tenants?
   - *Recommendation:* Run a uniqueness check script across all provisioned tenant DBs.

## Sources
- `backend/internal/database/tenant/provisioning.go` (Provisioning flow verified)
- `backend/internal/database/tenant/isolation_test.go` (Current isolation testing pattern)
- `backend/Makefile` (Existing test targets analyzed)
- `backend/scripts/test_e2e.sh` (Current E2E flow analyzed)
