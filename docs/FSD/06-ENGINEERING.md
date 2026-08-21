# Academio — Functional Specification Document

## Part 6: Engineering — Security, Monitoring, Performance, Disaster Recovery, Testing, Deployment, CI/CD, Scalability, and Technical Decisions

| Attribute | Value |
|---|---|
| Product | Academio — Enterprise School Management and Education ERP Platform |
| Author | Playbit Technologies — Platform Engineering |
| Document | FSD Part 6 of 8 |
| Status | Ratified |
| Applies to | `backend/` (Go 1.26 / Gin / GORM / pgx v5), `frontend/` (React 19 / Vite / TanStack Router), `mobile/` (Flutter) |
| Last verified | 2026-07-31 |

---

## Table of Contents

1. [Introduction and Scope](#1-introduction-and-scope)
2. [Security](#2-security)
3. [Monitoring](#3-monitoring)
4. [Performance](#4-performance)
5. [Disaster Recovery](#5-disaster-recovery)
6. [Testing Strategy](#6-testing-strategy)
7. [Deployment Strategy](#7-deployment-strategy)
8. [CI/CD](#8-cicd)
9. [Scalability Plan](#9-scalability-plan)
10. [Technical Decisions](#10-technical-decisions)
11. [Cross-References to Other FSD Parts](#11-cross-references-to-other-fsd-parts)
12. [Appendix A: Implementation Status Summary](#12-appendix-a-implementation-status-summary)
13. [Appendix B: Reference Documents](#13-appendix-b-reference-documents)

---

## 1. Introduction and Scope

This part of the Academio Functional Specification defines the engineering backbone of the platform: how the system is secured, observed, performance-tuned, backed up, tested, deployed, released, and scaled. It is the authoritative engineering companion to the product and functional descriptions in FSD Parts 1 through 5.

### 1.1 Document Conventions

- **Status markers.** Each capability in this document is marked as one of:
  - **Implemented** — present in the current codebase and verified against source.
  - **Partial** — present but with known gaps or limited coverage.
  - **Planned** — specified as a target architecture but not yet implemented.
- **Numbers.** Performance figures, limits, and thresholds are quoted from measured baselines, documented budgets, or configuration files. Where a figure is a target rather than a measurement, it is labelled as a budget.
- **Hard rules.** Rules prefixed `B1`-`B13` (backend) and `F1`-`F5` (frontend) refer to the operational constitution in `AGENTS.md` and are mandatory.

### 1.2 Technology Stack Summary

| Layer | Technology | Version (verified) |
|---|---|---|
| Backend language | Go | 1.26 |
| HTTP framework | Gin | v1.10 |
| ORM / driver | GORM + pgx v5 | GORM v1.31.2 |
| Database | PostgreSQL | 16 |
| Cache / queue | Redis + asynq | 7 |
| Auth tokens | golang-jwt | v5 |
| Telemetry | OpenTelemetry (OTLP) + Prometheus | — |
| Object storage | S3 (AWS SDK v2) or local filesystem | — |
| Crypto | AES-256-GCM | — |
| Frontend | React / Vite / TypeScript / TanStack Router / Tailwind CSS | React 19.2.4 / Vite 8 / TS 5 / Router 1.170 / Tailwind 4 |
| Frontend tests | Vitest / Playwright | Vitest 4.1.9 / Playwright 1.61 |
| Package manager | Yarn | 4.17.0 (corepack) |
| Mobile | Flutter | Dart SDK ^3.12 |
| Linting | golangci-lint | v1.64.8 (CI) |

### 1.3 Engineering Principles

The engineering organization operates under the following priority order (from `AGENTS.md`): correctness, security, performance, scalability, reliability, simplicity, maintainability, extensibility, developer experience, user experience. Security and maintainability are never sacrificed for convenience.

---

## 2. Security

### 2.1 Security Posture

Academio implements a defense-in-depth model across seven layers, from physical infrastructure to application logic (see `docs/architecture/6-SECURITY-INFRASTRUCTURE.md`). The platform achieved a production audit score of **84/100** on 2026-07-17 (`docs/reports/production-audit.md`), with all four critical/high findings from the initial audit resolved. The remaining high finding — `context.Background()` in request-scoped Redis operations — is scheduled for the next sprint.

### 2.2 Authentication

**Status: Implemented**

| Capability | Detail |
|---|---|
| Access token | JWT (HS256), default TTL **15 minutes** |
| Refresh token | Rotating refresh token, default TTL **168 hours (7 days)** |
| Revocation | Redis-backed token blacklist checked on every authenticated request |
| Session management | Refresh tokens stored server-side in Redis; rotation invalidates the old token |
| Password hashing | bcrypt (`pkg/password/bcrypt.go`) |
| Multi-factor | TOTP support (`pkg/totp/totp.go`, `totp_settings` migration) exposed through the profile module |

The authentication flow is documented in FSD Part 4 (API Specification) and `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` section 1.2: credentials are verified against the `public.users` table, an access token and rotating refresh token are issued, the refresh token is stored in Redis, and subsequent requests validate the JWT statelessly while checking the blacklist.

### 2.3 Authorization (RBAC)

**Status: Implemented**

| Role | Scope |
|---|---|
| super-admin | Full platform access (Playbit staff) |
| admin / principal | School-level administration |
| teacher | Own classes, subjects, students |
| student / parent / alumni | Own data only |
| accountant / librarian / hr / admissions_officer / counselor / transport_mgr / hostel_mgr | Module-scoped |

Data filtering is enforced through:
- `EnforceSchoolID()` middleware that prevents cross-tenant access.
- RBAC middleware that gates mutating endpoints by role.
- Automatic tenant scoping of all queries via the schema-per-tenant resolver (`middleware.GetTenantDB`), so teachers see only assigned students and parents see only their children.

### 2.4 CSRF Protection

**Status: Implemented** (resolved from Critical in `docs/reports/production-audit.md`)

- Stateless HMAC-SHA256 CSRF tokens with nonces (`middleware/csrf.go`).
- The signing secret is injected from configuration as `CSRF(secret)`; there is **no hardcoded fallback**.
- `validateProduction()` rejects an empty or placeholder `APP_SECRET`.
- An allowlist covers auth endpoints (`/auth/*`) that legitimately exchange credentials.
- The `GET /api/v2/csrf` endpoint issues the token; state-mutating requests must include the `X-CSRF-Token` header.

### 2.5 Rate Limiting

**Status: Implemented**

- Redis-backed sliding window with per-IP, per-user, and per-tenant tiers (`middleware/ratelimit.go`).
- Plan-based limits (free / basic / premium / enterprise) are configurable via environment variables (e.g., premium `RATE_LIMIT_PREMIUM_LIMIT` default 300 requests/minute with burst 50; enterprise default 1000 requests/minute with burst 100).
- Response headers expose remaining quota.
- Product-level abuse-prevention limits are specified in `docs/ABUSE-PREVENTION.md`:

| Resource | Free-tier limit |
|---|---|
| Login attempts | 5 per minute per IP |
| API requests | 60 per minute per school |
| File uploads | 10 per minute per school |
| Email sending | 50 per day per school |
| Password resets | 3 per hour per user |

### 2.6 Security Headers

**Status: Implemented** (`middleware/security.go`)

| Header | Value |
|---|---|
| `Content-Security-Policy` | Path-based: strict policy (no `unsafe-inline`/`unsafe-eval`) for all API routes; relaxed policy applied **only** to `/swagger*` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` / `Permissions-Policy` | Set |
| `Cache-Control` | Set on responses |

CORS uses an explicit origin allowlist; credentials are only sent for specific origins, never `*`.

### 2.7 Request Hygiene and Middleware Order

**Status: Implemented**

The verified middleware chain (`router.go`) is:

```
Recovery → RequestID → Tracing → ErrorHandler → Logger → SecurityHeaders → CORS → BodyLimit → SchoolID → RateLimit → CSRF
```

A `BodyLimit` middleware caps request body size. A centralized error handler returns structured JSON errors with codes and categories, and `Recovery()` captures panics with stack traces.

### 2.8 Data Security

| Capability | Status | Detail |
|---|---|---|
| Encryption in transit | Implemented | TLS 1.3 minimum in production; `DB_SSLMODE` configurable (`disable` for local dev) |
| Encryption at rest | Implemented | AES-256-GCM field encryption (`internal/crypto/encryption.go`) keyed by `ENCRYPTION_KEY` (32-byte hex, validated at startup); database-level encryption via provider (PostgreSQL TDE/disk encryption) is a deployment concern |
| PII handling | Partial | Data classification (public/internal/sensitive/PII/restricted) is specified; column-level PII encryption and masking are Planned |
| Secure deletion | Planned | GDPR right-to-erasure workflow (anonymize or remove) |

### 2.9 Secrets Management and Configuration Validation

**Status: Implemented**

Hard rule B6 (no hardcoded secrets) and B12 (fail-fast configuration) are enforced:

- All secrets are read from environment variables: `JWT_SECRET`, `ENCRYPTION_KEY`, `APP_SECRET`, `DB_PASSWORD`, `SENDGRID_API_KEY`, `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`, `S3_ACCESS_KEY`/`S3_SECRET_KEY`, `AI_API_KEY`.
- `config.Load()` runs `validate()` plus `validateProduction()`; invalid or missing required configuration prevents server start.
- `validateProduction()` rejects placeholder values (`change-me-in-production`), weak database passwords, and returns errors when a service is enabled but its credentials are missing.
- `.env` is never committed; `.env.example` is the template. Generation guidance: `openssl rand -hex 32` for `JWT_SECRET`, `ENCRYPTION_KEY`, and `APP_SECRET`.
- A secret scan (gitleaks/trufflehog) is specified as a pre-commit and CI gate (Planned; see section 8.6).

### 2.10 Audit Logging

**Status: Implemented**

Hard rule B11 requires every mutation to create an audit log entry with `SchoolID`, `UserID`, `Action`, `ResourceType`, and `RequestID`. The audit model additionally records `ResourceID`, `OldValues`/`NewValues` JSON diffs, `IPAddress`, `UserAgent`, and `Timestamp`. The `audit` module exposes listing endpoints, and `middleware/audit.go` provides the logging middleware. The audit table is indexed for tenant/resource, user, and timestamp lookups.

### 2.11 Abuse Prevention (Product Layer)

**Status: Partial — policy implemented, several technical controls Planned**

`docs/ABUSE-PREVENTION.md` defines the "Free Forever, But Verified" strategy with fifteen safeguards. Implemented controls include plan-based rate limiting and feature-flag gating. Planned controls include: school verification (official email domain, government registration number), email/phone OTP verification, storage quotas, AI request caps, invite-based growth, suspicious-activity monitoring, watermarking of free-plan PDFs, and one-free-school-per-identity enforcement.

### 2.12 Security Compliance Mapping

| AGENTS.md rule | Enforcement |
|---|---|
| B1 — no silent error discards | `errcheck` (check-blank), code review |
| B2 — no `context.Background()` in request scope | `contextcheck` linter, code review; residual Redis occurrences scheduled |
| B3 — no `fmt.Printf`/`log.Print` | Code review, grep gates; `pkg/logger` mandatory |
| B4/B13 — no multi-statement `db.Exec()` | Code review (pgx v5 prepared-statement incompatibility) |
| B6 — no hardcoded secrets | Config validation, secret scan (Planned in CI) |
| B7 — no `fmt.Sprintf` for SQL | Code review, `gosec` |
| B8 — tenant queries via `middleware.GetTenantDB` | Architecture standards, code review |
| B12 — fail-fast config | `config.Load()` + `validateProduction()` unit-tested |

---

## 3. Monitoring

### 3.1 Logging

**Status: Implemented**

All application logs use `pkg/logger`, a structured JSON wrapper around Go's standard `log/slog`. Levels are `debug`, `info`, `warn`, `error`, `fatal`.

Required structured fields per `docs/architecture/9-ARCHITECTURAL-STANDARDS.md`:

| Field | Source | Required |
|---|---|---|
| `request_id` | `middleware/requestid.go` | Yes |
| `tenant_id` | school context middleware | When school context exists |
| `user_id` | JWT claims | When authenticated |
| `method`, `path`, `status`, `latency_ms` | request logging middleware | Yes |
| `error` | error object | On errors |

Logs are JSON to stdout (captured by Docker/systemd in deployment). No PII is written to logs (verified in the production audit).

### 3.2 Request ID Propagation

**Status: Implemented**

A `requestid` middleware assigns or forwards a request ID (typically via the `X-Request-ID` header). The ID is propagated through structured log fields and audit records (`RequestID`), enabling end-to-end correlation across logs, audit trails, and tracing spans.

### 3.3 Health and Readiness

**Status: Implemented** (`internal/modules/health`)

| Endpoint | Purpose | Healthy response |
|---|---|---|
| `/health` | Base health check with component status | `{"status":"ok"}` |
| `/livez` | Liveness probe | `{"status":"alive"}` |
| `/readyz` | Readiness probe (DB + Redis connectivity) | `{"status":"ready"}` |
| `/startupz` | Startup probe | `{"status":"started"}` |
| `/metrics` | Prometheus metrics (`go_*`, `http_*`) | Prometheus text format |

### 3.4 Metrics

**Status: Implemented**

- Prometheus-compatible `/metrics` endpoint aggregated from Go runtime and HTTP metrics.
- The Docker Compose stack provisions Prometheus (scrape interval 15s, 30-day TSDB retention) and Grafana with pre-provisioned data sources and dashboards (`backend/monitoring/`).
- The Grafana dashboard "Academio v2.0 Overview" covers request rate, latency distribution, goroutines, memory, database pool, queue depth, and error rate.
- Queue metrics are emitted by the asynq worker (`internal/queue/metrics.go`).

### 3.5 Distributed Tracing

**Status: Partial — instrumented, external export configuration-dependent**

- OpenTelemetry provider and instrumentation exist (`internal/telemetry/provider.go`, `gorm_tracing.go`, `redis_tracing.go`; `middleware/tracing.go` creates a span per request with standard HTTP attributes).
- W3C trace context propagation across service boundaries is specified.
- Export to an OTLP backend (Jaeger / Grafana Tempo) is configuration-dependent; when `OTEL_ENABLED=true`, `OTEL_ENDPOINT` must be set (validated at startup).

### 3.6 Alerting

**Status: Planned**

The target alerting model from `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` section 3.4:

| Priority | Condition |
|---|---|
| P0 | API down, database down, error rate > 5% |
| P1 | Latency p99 > 2s, queue depth > 1000 |
| P2 | AI cost over budget, disk > 80% |
| P3 | Slow queries, cache hit rate < 80% |

Alert rules and notification channels are not yet provisioned in the compose stack.

### 3.7 Swagger / API Documentation in Development

**Status: Implemented (dev only)**

- Swagger UI: `http://localhost:8080/swagger/index.html`
- Swagger JSON: `http://localhost:8080/swagger/doc.json`
- Generated via `make swagger` (`swag init`); regenerated from annotations in `cmd/server/main.go`.
- Swagger routes receive the relaxed CSP policy (see section 2.6).

---

## 4. Performance

### 4.1 Performance Budgets (Ratified Targets)

The performance baselines (`docs/performance-baseline.md`, `docs/ops/load-test-baseline.md`) define the service-level budgets that must be met and continuously verified:

| Metric | Budget | Violation action |
|---|---|---|
| Error rate | < 1% | Investigate backend errors and DB connection pool |
| Latency p95 | < 500 ms | Profile slow endpoints, check DB query plans |
| Latency p99 | < 1000 ms | Check GC pauses, connection bottlenecks |
| Parallel throughput drop (sequential vs parallel) | < 30% | Investigate contention and connection pool limits |

Reference k6 configuration: 10 virtual users, 30 seconds per endpoint, 1 second think time, five canonical scripts (login, attendance, scores, users, bills) covering the API surface from authentication through academic flows and finance.

**Status note.** `docs/ops/load-test-baseline.md` is currently a template with no measured values. The budget numbers above are ratified targets; measured baselines must be captured with `make loadtest ARGS="--env smoke"` (or the full suite) and archived per the baseline procedure before they can be compared. This is the single largest performance-related gap and is tracked in section 9.4.

### 4.2 Build and Startup Performance (Measured)

| Figure | Value | Source |
|---|---|---|
| Cold build time | ~2 minutes | `AGENTS.md` |
| Warm build time | ~15-30 seconds | `AGENTS.md` |
| Backend binary | ~25 MB | `docs/ops/deploy.md` |
| Frontend bundle | ~500 KB gzipped | `docs/ops/deploy.md` |
| Hot reload | Air (`backend/tmp/server`) | `AGENTS.md` |

### 4.3 Query Discipline and Database Performance

**Status: Implemented, with documented known issues**

- **Pagination (B5, B10).** All list queries are bounded. Service-layer pagination is mandatory: handlers use `helpers.ParsePagination(c)` (default `page=1, limit=20`, maximum `limit=100`), services accept `(page, limit int)`, and responses use `response.SuccessWithPagination()`. Backend-wide query caps default to 100 with a maximum of 1000. Implemented on academic list endpoints and the communication module; remaining unbounded endpoints (`ListStudents`, `ListTeachers`, `ListByRole`, `GetAttendance`) are flagged for extension in `docs/reports/production-audit.md`.
- **Connection pooling.** A single PostgreSQL connection pool serves all tenants (schema-per-tenant requires no per-school connections). GORM/pgx pool defaults are used with tuning per tenant load recommended by `backend/STYLE.md`.
- **Index strategy.** Migrations add targeted indexes (audit logs by tenant/resource/user/timestamp; `pg_trgm` extension for search; `read_source` and `schema_name` on schools for the resolver). Index additions accompany new query patterns during code review.
- **Prepared statements.** `PrepareStmt` is disabled on the shared plugin-registered DB because of a GORM panic (see 4.4); per-tenant direct connections may use `PrepareStmt: true`.

### 4.4 Known GORM Performance and Correctness Issues

`docs/reports/gorm-issues.md` documents two critical interactions between the `SchemaTablePrefix` plugin and GORM v1.31.2:

| Issue | Severity | Impact | Workaround (in production) |
|---|---|---|---|
| `PrepareStmt: true` + schema prefix plugin panics on `Create` | Critical | Server crash on inserts through the shared DB | `PrepareStmt: false` on the shared DB; safe on per-tenant DSN connections |
| Many-to-many `Preload` returns empty results with schema prefix | High | Silent data loss — join table is not schema-prefixed | Manual raw SQL with explicit schema prefix (e.g., `loadSessionCurriculums`) |
| `WithContext()` on schema session loses the schema context key | Medium | Incorrect schema resolution | Use `Set()` to carry the schema value or `InjectSchemaToContext` |

These workarounds are implemented in the academic module. GORM upstream fixes are tracked.

### 4.5 Frontend Performance

**Status: Implemented baseline**

- Client-rendered SPA on Vite 8 with route-based code splitting (TanStack Router file-based routes).
- React Query caching of server state (`src/lib/hooks/`), TanStack Virtual for large tables, and `lucide-react` icon tree-shaking.
- Frontend loads via the Vite dev server on port `:4000`, proxying `/api` to `:8080`; production serves the static `dist/` behind nginx.
- No measured Lighthouse/Core Web Vitals baseline is yet published; web performance measurement is a Planned addition to the load-test routine.

---

## 5. Disaster Recovery

### 5.1 Backup

**Status: Implemented**

| Capability | Detail |
|---|---|
| Backup engine | Schema-aware `pg_dump` via `internal/backup/service.go` and `pkg/storage/s3_backup.go` |
| Scheduling | Asynq queue task (`internal/queue/handlers/backup_handler.go`) |
| Storage | S3-compatible object storage (or local driver) |
| Retention | 14-backup retention cycle (verified in production audit); plan-based retention of 7 / 90 / 365 days is specified in `docs/ABUSE-PREVENTION.md` |
| Tests | `backup_handler_test.go`, `service_test.go`, `s3_backup_test.go` exist and pass |

### 5.2 Restore

**Status: Implemented**

- Restore service (`internal/restore/service.go`, `handler.go`) with asynq handler (`restore_handler.go`) and tests.
- Restore is schema-aware and operates on the S3 backup store.

### 5.3 Disaster Recovery Plan

| Capability | Status | Notes |
|---|---|---|
| Backup encryption | Planned | Backups should be AES-256 encrypted at rest (specified in security architecture) |
| Point-in-time recovery | Planned | Enterprise plan (365-day retention + PITR) |
| Read replicas | Planned | See section 9 |
| Multi-region / multi-AZ | Planned | Target: active-passive region with replicated PostgreSQL and Redis; not implemented in the current single-VPS deployment |
| Restore drill / RTO / RPO | Planned | No measured RTO/RPO or scheduled restore drill exists; should be defined (target RPO ≤ 24h with daily backups, RTO ≤ 4h) |
| Tenant-level restore | Partial | Schema-aware restore exists; per-school granular restore workflow is not exposed as a product feature |

### 5.4 Recovery Runbook Summary

The deployment runbook (`docs/ops/deploy.md`) defines rollback procedures: assess impact via `/metrics` and logs, roll back migrations with `make migrate-rollback ARGS="--steps N"` (with `--dry-run` preview), roll back the application image, and verify via health checks and smoke tests. Post-incident actions include tagging the broken release and filing a blocking issue with root-cause analysis.

---

## 6. Testing Strategy

### 6.1 Test Pyramid Overview

| Layer | Tooling | Status |
|---|---|---|
| Backend unit tests | Go `testing` + testify + go-sqlmock | Implemented (race detector, shuffle) |
| Backend integration tests | Go build tag `//go:build integration`, testcontainers | Implemented |
| Endpoint (API) tests | `backend/scripts/test_endpoint.sh` and sibling scripts | Implemented (documented as 40 tests, verified 40/40 pass) |
| Frontend unit/component tests | Vitest + Testing Library | Implemented (17+ suites) |
| Frontend E2E tests | Playwright | Implemented (smoke specs) |
| Mobile widget/unit tests | Flutter `flutter_test` | Implemented (provider + screen suites) |
| Load tests | k6 | Implemented (smoke + stress scripts), baselines unpopulated |

### 6.2 Backend Unit Tests

**Status: Implemented**

- Conventions in `backend/TESTING.md`: table-driven tests, Arrange-Act-Assert, `t.Parallel()` where safe (never with `t.Setenv()`), testify assert/require, go-sqlmock at the driver level (never mocking `gorm.DB` directly), `mock.ExpectationsWereMet()` per test.
- Repository interfaces exist at the top of each module repository file to support testify mocks (`mock_repository_test.go` across modules).
- Test naming: `Test{Unit}_{Scenario}`.
- Coverage targets (`backend/TESTING.md`): overall ≥ 30%, new packages ≥ 50%, critical path (migration, tenant, auth) ≥ 70%. The CI pipeline enforces a **40%** total coverage threshold (see section 8).
- Make targets: `make test` (unit + race + coverage), `make test-short`, `make test-coverage`, `make check`.

### 6.3 Backend Integration Tests

**Status: Implemented**

- Integration tests are isolated behind the `//go:build integration` build tag and live in `internal/database/tenant/` (`isolation_test.go`, `integration_test.go`, `provisioning_rollback_test.go`) plus `internal/service/`.
- They require real PostgreSQL; CI provisions a Postgres service container; locally they skip gracefully when `DATABASE_URL` is unset.
- `testcontainers_setup.go` provides container-based setup.
- Make targets: `make test-integration`, `make test-all`.

### 6.4 Endpoint Test Suite

**Status: Implemented**

`backend/scripts/test_endpoint.sh` is the primary black-box API suite. It drives the full lifecycle — health, CSRF, admin registration, login, school creation, tenant provisioning (polling until `schema_name` is populated), curriculum/assessment/grade-item/session flows, teacher and staff registration, impersonation audit checks, student creation with parents, scoring, bulk score save, rollup, and XLSX import preview. The documented expectation is **40 tests passing, 0 failing** (`docs/ops/deploy.md`), verified as 40/40 in the production audit. Companion suites cover schools (`test_school.sh`), users (`test_users.sh`), forum E2E (`test_forum_e2e.sh`), and tenant lifecycle (`test_tenant_lifecycle.sh`).

Prerequisites: `make db-init DROP_TENANT=true && make migrate && make seed && ./bin/server`, then `bash scripts/test_endpoint.sh` (or `make test-endpoints RESET=true`).

### 6.5 Frontend Tests

**Status: Implemented**

- Vitest 4 + Testing Library with jsdom; suites cover hooks (`use-*`), components (button, data-table, export-csv, stats-card, score-grid), terminology provider, and academic calendar (`frontend/src/__tests__/`).
- Playwright 1.61 with `playwright.config.ts`; E2E smoke specs for auth and navigation (`frontend/e2e/`).
- Type checking: `tsc --noEmit` clean (verified 0 errors in the production audit).
- Make target: `make test-frontend` (runs `yarn vitest run`).

### 6.6 Mobile Tests

**Status: Implemented**

- Flutter widget tests for screens (login, admin dashboard/people/detail, teacher screens, student dashboard, notifications) and provider unit tests (auth, dashboard, library, message, notification, people, api-client) under `mobile/test/`.
- Hard rule M15 requires every screen to have a widget test covering render, loading, error, and empty states; M12/M18 forbid empty catches.

### 6.7 Load and Performance Testing

**Status: Partial — tooling implemented, baselines not populated**

- k6 scripts at `backend/scripts/k6/` (smoke-test.js, stress-test.js, auth.js).
- Local: `make loadtest ARGS="--env smoke"`.
- CI: `load-test.yml` runs k6 smoke on PRs and k6 stress on manual dispatch (see section 8).
- Baselines (`docs/ops/load-test-baseline.md`, `docs/performance-baseline.md`) are templates; measured values are outstanding (see section 4.1).

### 6.8 Coverage and Quality Gates Summary

| Gate | Threshold |
|---|---|
| CI unit-test coverage (backend) | ≥ 40% total |
| Local `make test-coverage-check` | ≥ 10% total |
| TESTING.md target — overall | ≥ 30% |
| TESTING.md target — new packages | ≥ 50% |
| TESTING.md target — critical path | ≥ 70% |
| golangci-lint | Full config (errcheck, contextcheck, gosec, cyclop ≤ 25, funlen ≤ 120 lines, etc.) |
| Endpoint suite | 40/40 passing |

---

## 7. Deployment Strategy

### 7.1 Local Development Topology

| Component | Configuration |
|---|---|
| PostgreSQL | Docker container `shared-postgres` on port 5432, user `postgres`, database `academio` |
| Redis | Docker container `shared-redis` on port 6379 |
| Backend | `cd backend && ./bin/server` binds `:8080`; queue worker runs as a goroutine in the same process |
| Frontend | Vite dev server on `:4000`, proxies `/api` → `:8080` |
| Hot reload | Air (binary at `backend/tmp/server`, config `.air.toml`) |
| Env | `backend/.env` (`JWT_SECRET`, `ENCRYPTION_KEY`, `DB_*`, `REDIS_*`) |

Database reset sequence: `make db-init DROP_TENANT=true && make migrate && make seed`.

### 7.2 Docker Compose Production Stack

**Status: Implemented** (`backend/docker-compose.yml`)

| Container | Image | Port | Purpose |
|---|---|---|---|
| `academio-pg` | postgres:alpine | 5432 | PostgreSQL |
| `academio-redis` | redis:alpine | 6379 | Cache + asynq queue |
| `academio-pg` | pgvector/pgvector | 5432 | PostgreSQL + vector store (AI/RAG) |
| `academio-gotenberg` | gotenberg/gotenberg:8 | 3000 | PDF generation |
| `academio-api` | built image | 8080 | Go API server |
| `academio-prometheus` | prom/prometheus | 9090 | Metrics (30-day retention) |
| `academio-grafana` | grafana/grafana | 3001 (→3000) | Dashboards (pre-provisioned) |

The API service depends on healthy Postgres, Redis, and Gotenberg. Compose uses explicit `academio-*` names; the local dev `shared-*` containers are the canonical names for development per `AGENTS.md`.

### 7.3 Container Image

**Status: Implemented** (`backend/Dockerfile`)

- Multi-stage build: `golang:1.26-alpine` builder with `CGO_ENABLED=0`, runtime `alpine:3.19` with ca-certificates and tzdata.
- Static binary at `/app/server`, `EXPOSE 8080`, `ENTRYPOINT ["./server"]`.
- `.dockerignore` excludes local artifacts.
- Image build: `make docker-build`; stack lifecycle: `make docker-up` / `make docker-down`.

### 7.4 Build and Release Commands

| Action | Command |
|---|---|
| Backend build | `make build` → `backend/bin/server` |
| Backend lint | `make lint` (golangci-lint) or `make vet` |
| Frontend build | `cd frontend && yarn build` → `dist/` |
| Frontend typecheck | `yarn typecheck` |
| Migrations | `make migrate` |
| Migration rollback | `make migrate-rollback ARGS="--steps N"` |
| Seed (production-safe) | `make seed` (super admin only) |
| Seed (demo data) | `make seed-demo` |
| Swagger regeneration | `make swagger` |
| Pre-commit checks | `make check` (vet + lint-vet + build + test-unit) |
| Full verification | `make check-all` |

### 7.5 Production Deployment Paths

**Status: Implemented**

1. **Docker Compose** (single host): `make docker-build && make docker-up`, then `docker exec academio-api ./server migrate`; verify with section 7.6.
2. **Kubernetes** (target production): manifests under `backend/deploy/k8s/base` (deployment, service, ingress, HPA, PDB, configmap) with staging and production overlays; `make kustomize ENV=production`.
3. **VPS systemd** (current production path): the `deploy.yml` workflow ships a release package (binary + `.env` + `academio.service` + `nginx.conf` + `deploy.sh`) to a VPS over SCP/SSH and runs the deployment script. Secrets are injected from GitHub Secrets.

### 7.6 Health Verification (Post-Deploy)

| Check | Command | Expected |
|---|---|---|
| Health | `curl http://localhost:8080/health` | `{"status":"ok"}` |
| Liveness | `/livez` | `{"status":"alive"}` |
| Readiness | `/readyz` | `{"status":"ready"}` |
| Startup | `/startupz` | `{"status":"started"}` |
| Metrics | `/metrics` | Prometheus output |
| CSRF + login smoke | `curl /api/v2/csrf` then `POST /auth/login` | tokens returned |
| Full suite | `bash scripts/test_endpoint.sh` | 40/40 pass |

### 7.7 Rollback Criteria (Immediate Rollback)

From `docs/ops/deploy.md` section 10.4: `/readyz` non-200 after 60 seconds, 5xx error rate above 5%, tenant provisioning failure, migration error, unbounded memory growth over 5 minutes, or any authenticated user-facing endpoint returning 500.

---

## 8. CI/CD

### 8.1 Current State

**Status: Implemented.** CI workflows exist at three levels. This determination is based on verified files:

| Workflow | Location | Triggers | Purpose |
|---|---|---|---|
| Backend CI | `backend/.github/workflows/ci.yml` | push/PR to `main`, `dev`, `v2/**` | lint, vet, build, unit tests + 40% coverage, integration tests, endpoint tests |
| Backend deploy | `backend/.github/workflows/deploy.yml` | push to `main` | build release package, SCP to VPS, systemd deploy |
| Backend load test | `backend/.github/workflows/load-test.yml` | PR paths + manual dispatch | k6 smoke (PR), k6 stress (manual) |
| Frontend CI | `frontend/.github/workflows/ci.yml` | push/PR to `main`, `dev` | lint, typecheck, vitest, build (Yarn 4 via corepack) |
| Docs publish | `.github/workflows/docs.yml` | push to `main` on `docs/**` | GitHub Pages deployment of docs |

### 8.2 Backend CI Pipeline (Implemented)

```
pull_request / push → main|dev|v2/**
├── lint           golangci-lint v1.64.8 run ./...
├── vet            go vet ./...
├── build          go build -o /tmp/academio-server ./cmd/server
├── unit-tests     go test -race -shuffle=on -coverprofile ... ./internal/... ./pkg/... ./cmd/...
│                  → coverage threshold 40% (COVERAGE_THRESHOLD env)
│                  → uploads test output + coverage artifacts
├── integration-tests   (main/PR-to-main only) go test -tags=integration -race
│                       with Postgres service container
├── endpoint-tests      (main/PR-to-main only) migrate + seed + start server
│                       with Postgres + Redis service containers
│                       → bash ./scripts/test_endpoint.sh session
└── coverage-summary    go tool cover → $GITHUB_STEP_SUMMARY
```

The endpoint-tests job injects CI-only secrets via environment (`APP_SECRET`, `JWT_SECRET`, `ENCRYPTION_KEY`) and cleans up tenant databases via `RESET=true`.

### 8.3 Backend Deploy Pipeline (Implemented)

`deploy.yml` builds `GOOS=linux GOARCH=amd64`, assembles `.env` from GitHub Secrets/Vars (DB, Redis, JWT, encryption, storage, SES), packages the binary with `academio.service`, `nginx.conf`, and `deploy.sh`, ships via SCP (`appleboy/scp-action`), then runs `deploy.sh` over SSH (`appleboy/ssh-action`) with systemd stop/start.

### 8.4 Frontend CI Pipeline (Implemented)

```
push/PR → main|dev
├── lint        corepack yarn lint
├── typecheck   npx tsc --noEmit
├── test        corepack yarn test  (vitest run)
└── build       corepack yarn build (needs typecheck + test)
```

Node 22 via `actions/setup-node@v4`; Yarn 4 enabled via `corepack enable`.

### 8.5 Load-Test Pipeline (Implemented)

- k6 smoke on every PR touching `backend/**` (Postgres + Redis service containers, server readiness wait, `k6 run smoke-test.js`, check failure gate, artifact upload).
- k6 stress on manual `workflow_dispatch` (`test_type: stress|all`).

### 8.6 Proposed Additions (Planned)

| Addition | Rationale |
|---|---|
| Secret scanning job (gitleaks/trufflehog) | Required by `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` section 8; currently absent from workflows |
| Performance regression gate | `docs/performance-baseline.md` section 7: fail builds that degrade p95 latency by more than 20% against archived baseline |
| Container image build + push to registry | Current pipelines build binaries; containerized release with provenance is planned |
| Staging deployment environment | Deployment currently targets production directly; a staging overlay exists in K8s manifests but is not wired to CI |
| Mobile (Flutter) pipeline | `flutter analyze` + `flutter test` job; the mobile repo has no workflow yet |
| Frontend Playwright E2E job | Vitest is gated; Playwright specs are not yet executed in CI |

---

## 9. Scalability Plan

### 9.1 Target Scale

Academio is designed for thousands of schools and millions of records. The decision framework in `AGENTS.md` requires every design to be validated at 10, 100, and 10,000 schools. The multi-tenant architecture (schema-per-tenant, FSD Part 2) is the foundation of the scale plan.

### 9.2 Current Scaling Characteristics

| Characteristic | Detail |
|---|---|
| Tenant isolation | Schema-per-tenant (`school_{id}`) on a single PostgreSQL instance — no per-school connection pools |
| Tenant resolution | Schema name cached in Redis (`TenantResolutionService`), eliminating per-request catalog lookups |
| Queue | asynq on Redis; worker currently runs inside the API process (goroutine) |
| Application | Stateless API (JWT auth, Redis-backed sessions) — horizontally scalable by design |
| Frontend | Static SPA — served by nginx/Vite, cacheable |
| Vector search | pgvector in the compose stack and K8s manifests (AI/RAG) |

### 9.3 Horizontal Scaling Path

| Phase | Action | Status |
|---|---|---|
| 1 | Scale API replicas behind a load balancer (Docker Compose `--scale api=3`; K8s HPA min 3 / max 20 at CPU 70%, memory 80%) | Implemented (manifests + runbook) |
| 2 | Extract asynq workers into a separate deployment/process so queue jobs scale independently of HTTP traffic | Planned (worker already a component; split the goroutine into a standalone binary) |
| 3 | Add PostgreSQL read replicas for reports, analytics, and read-heavy endpoints; route analytics queries to replicas (log-and-continue, hard rule B9) | Planned |
| 4 | Redis Cluster / managed Redis for session, rate-limit, and queue scaling; add Redis Sentinel/HA | Planned |
| 5 | Object storage (S3) for uploads/media with CDN edge caching; `STORAGE_DRIVER=s3` already supported | Partial (driver implemented) |
| 6 | Analytics scale layer: ClickHouse for long-range analytics/reports (compose template exists in the architecture doc) | Planned |
| 7 | Vector scale layer: pgvector clustering for AI features | Partial |
| 8 | Search scale layer: dedicated search engine (e.g., MeiliSearch) for global/tenant search | Planned |
| 9 | Event-driven decoupling: Kafka or equivalent for cross-module events at high volume | Planned |
| 10 | Multi-region deployment with active-passive database replication | Planned |

### 9.4 Performance and Capacity Risks

| Risk | Mitigation |
|---|---|
| No measured load baseline | Run and archive baselines via `make loadtest`; enforce in CI (section 8.6) |
| Single PostgreSQL instance | Read replicas + connection pool tuning; monitor `gorm_*` pool metrics |
| Many-to-many Preload limitation | Raw-SQL workaround already implemented; track GORM upstream fix |
| `PrepareStmt` disabled on shared DB | Acceptable for cross-schema admin queries; tenant DSN connections retain prepared statements |
| Queue in-process with API | Phase 2 worker extraction prevents head-of-line blocking under load |
| Unbounded endpoints | Extend service-layer pagination to all remaining list endpoints |

---

## 10. Technical Decisions

### 10.1 Ratified Decisions (from `AGENTS.md` "Key Decisions & Rationale")

| Decision | Rationale |
|---|---|
| Log-and-continue for reports/analytics queries | Failing reports on transient database blips is worse than serving stale data |
| Return errors for state mutations | Silent failures corrupt status — always propagate |
| Collect-and-report for batch operations | Better UX — the user fixes everything in one pass |
| Break multi-statement `db.Exec()` into individual calls | pgx v5 prepared-statement mode rejects multi-statement Exec |
| Parent dedup priority: email → phone → username | Email is the strongest identifier |
| Select entity names (not IDs) as `<SelectItem>` values | Base UI renders raw value text when no match exists |
| Service-layer pagination (not repository) | Keeps repository interfaces mock-friendly without signature changes |
| Sonner `<Toaster />` in root layout | Toasts survive navigation and drawer close |

### 10.2 Additional Decisions Confirmed by Source Documents

| Decision | Source | Rationale |
|---|---|---|
| Schema-per-tenant over database-per-tenant | `docs/architecture/6` section 2.1 | Single connection pool, no per-school connections; database-per-tenant retired for runtime use |
| Redis-cached tenant resolution | `docs/architecture/6` section 2.2 | Avoids per-request catalog queries; cache-miss falls back to the `schools` table |
| `PrepareStmt: false` on the shared plugin DB | `docs/reports/gorm-issues.md` | Eliminates the GORM create panic; tenant DSN connections keep prepared statements |
| Raw-SQL workaround for many-to-many Preload | `docs/reports/gorm-issues.md` | Join tables are not schema-prefixed by the plugin; manual prefix is the verified workaround |
| Path-based CSP (strict for API, relaxed for Swagger) | `docs/architecture/9` section 7, `docs/reports/production-audit.md` | Backend serves no HTML except Swagger; strictest policy by default |
| CSRF secret injected via `CSRF(secret)` | `docs/reports/production-audit.md` | Removes the silent-fallback critical; `APP_SECRET` validated at startup |
| Fail-fast production config for enabled services | `docs/architecture/9` section 5, `docs/reports/production-audit.md` | Misconfigured features fail at startup, not at runtime |
| 40% CI coverage gate | `backend/.github/workflows/ci.yml` | Raises the bar above the local 10% / documented 30% minimum |
| 14-backup retention with S3 | `docs/reports/production-audit.md` | Bounded storage cost with adequate recovery window; plan-based retention tiers to follow |
| JWT access 15 min / refresh 7 days with rotation | `docs/architecture/6` section 1.2, `docs/ops/deploy.md` | Short-lived access tokens limit exposure; rotating refresh tokens revoke on reuse |
| Redis blacklist for revoked tokens | `docs/architecture/6` section 1.2, `docs/reports/production-audit.md` | Immediate revocation without re-signing infrastructure |
| Free forever, verified schools (abuse prevention) | `docs/ABUSE-PREVENTION.md` | Makes abuse expensive, not adoption; schools operate on term cycles |
| Feature flags gate premium features | `docs/ABUSE-PREVENTION.md` | Instant plan upgrades without redeployment; enables A/B testing |
| `go:build integration` tag isolation | `backend/TESTING.md` | Unit tests run everywhere; database-backed tests run in CI and on demand |
| Air hot reload with `backend/tmp/server` | `AGENTS.md` | Fast inner dev loop; build time ~2 min cold |
| Yarn 4 exclusively for the frontend | `AGENTS.md` rule F2 | npm bypasses the Yarn lockfile and breaks the dependency tree |
| Default currency Nigerian Naira (NGN) | `AGENTS.md` rule F5 | All monetary displays use the naira symbol; stored as NGN |
| K8s HPA min 3 / max 20 at CPU 70% | `docs/architecture/6` section 3.2 | Bounded horizontal scaling with headroom |

### 10.3 Decisions Challenged or Flagged for Revisit

| Topic | Recommendation |
|---|---|
| CI coverage threshold mismatch (10% local vs 40% CI vs 30% documented) | Unify thresholds; align `Makefile` `COVERAGE_THRESHOLD` with `TESTING.md` and CI |
| `context.Background()` in Redis audit/blacklist paths | Replace with request context in the next sprint (tracked in production audit) |
| Endpoint suite composition | The 40-test suite is curated, not exhaustive; extend coverage to finance, HR, and AI modules and migrate to a Go test harness for CI reliability |
| Unpopulated load-test baseline | Highest-value performance action: capture and archive measured baselines before scaling |
| In-process queue worker | Extract standalone worker binary in phase 2 to decouple HTTP and job scaling |

---

## 11. Cross-References to Other FSD Parts

| FSD Part | Relationship to this document |
|---|---|
| Part 1 — Introduction and Vision | Platform goals, scope, and stakeholders that drive the engineering requirements here |
| Part 2 — System Architecture | Multi-tenant architecture (schema-per-tenant) that this part's scalability and security sections build upon |
| Part 3 — Data Model | Schema design, indexing, and migration strategy referenced by sections 4.3 and 5 |
| Part 4 — API Specification | Endpoints, pagination contracts, and auth flows exercised by the test suites in section 6 |
| Part 5 — Functional Modules | Module behavior that the audit-logging, rate-limiting, and feature-flag controls protect |
| Part 7 — AI and Intelligence | AI agents, pgvector store, and cost controls referenced by the observability and scalability plans |
| Part 8 — Roadmap | Planned scale layers (ClickHouse, search, Kafka) and CI additions detailed here |

Companion engineering documents: `AGENTS.md`, `docs/architecture/6-SECURITY-INFRASTRUCTURE.md`, `docs/architecture/9-ARCHITECTURAL-STANDARDS.md`, `docs/performance-baseline.md`, `docs/ops/deploy.md`, `docs/ops/load-test-baseline.md`, `backend/STYLE.md`, `backend/TESTING.md`, `docs/reports/production-audit.md`, `docs/reports/gorm-issues.md`, `docs/ABUSE-PREVENTION.md`.

---

## 12. Appendix A: Implementation Status Summary

| Capability | Status |
|---|---|
| Authentication (JWT + refresh + blacklist + TOTP) | Implemented |
| Authorization (RBAC + cross-tenant guard) | Implemented |
| CSRF (stateless HMAC, injected secret) | Implemented |
| Rate limiting (Redis sliding window, plan tiers) | Implemented |
| Security headers (CSP path-based, HSTS, CORS allowlist) | Implemented |
| Audit logging (all mutations) | Implemented |
| Fail-fast config validation | Implemented |
| Structured logging (`pkg/logger`, request IDs) | Implemented |
| Health/liveness/readiness/metrics endpoints | Implemented |
| OpenTelemetry instrumentation | Partial (in-process; external export config-dependent) |
| Prometheus + Grafana stack | Implemented (compose, pre-provisioned) |
| Alerting | Planned |
| Performance budgets ratified | Implemented (targets defined) |
| Measured load baselines | Planned (tooling implemented) |
| Backup (S3, 14-backup retention) | Implemented |
| Restore | Implemented |
| Point-in-time recovery / multi-region DR | Planned |
| Backend unit tests + race detector | Implemented |
| Backend integration tests (`integration` tag) | Implemented |
| Endpoint suite (40 tests) | Implemented (40/40 verified) |
| Frontend Vitest + Playwright | Implemented |
| Mobile Flutter tests | Implemented |
| k6 load tests | Implemented (smoke/stress scripts + CI) |
| Docker Compose stack | Implemented |
| Kubernetes manifests (base + overlays) | Implemented |
| VPS systemd deployment | Implemented |
| Backend CI (lint/vet/build/test/coverage) | Implemented |
| Frontend CI | Implemented |
| Load-test CI | Implemented |
| Docs CI (GitHub Pages) | Implemented |
| Secret scanning in CI | Planned |
| Performance regression gate in CI | Planned |
| Staging environment in CI | Planned |
| Mobile CI | Planned |
| Playwright E2E in CI | Planned |
| API replica scaling (compose scale / K8s HPA) | Implemented (manifests) |
| Standalone queue workers | Planned |
| Read replicas | Planned |
| ClickHouse analytics layer | Planned |
| pgvector clustering | Partial |
| Dedicated search engine | Planned |
| Event-driven decoupling (Kafka) | Planned |

---

## 13. Appendix B: Reference Documents

| Document | Path | Relevance |
|---|---|---|
| Operational constitution | `AGENTS.md` | Hard rules B1-B13, F1-F5; environment; tenant architecture; key decisions |
| Security and infrastructure architecture | `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` | Defense in depth, auth flow, monitoring stack, K8s/HPA, CI/CD target |
| Architectural standards | `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` | Context propagation, graceful shutdown, logging, OTel, fail-fast config, pagination, CSP, secrets, audit |
| Performance baseline | `docs/performance-baseline.md` | Budgets (p95 < 500 ms, p99 < 1000 ms, error < 1%, parallel drop < 30%) |
| Deployment runbook | `docs/ops/deploy.md` | Env checklist, build, migrations, rollback, health verification, release workflow |
| Load-test baseline | `docs/ops/load-test-baseline.md` | k6 template; measured values outstanding |
| Backend style | `backend/STYLE.md` | Formatting, error handling, logging, security, GORM patterns, performance |
| Testing conventions | `backend/TESTING.md` | Test layout, build tags, mocking, coverage targets |
| Production audit | `docs/reports/production-audit.md` | 84/100 score; resolved and remaining findings; strengths evidence |
| GORM issues | `docs/reports/gorm-issues.md` | SchemaTablePrefix + PrepareStmt panic; many-to-many Preload workaround |
| Abuse prevention and pricing | `docs/ABUSE-PREVENTION.md` | Fifteen safeguards, tier limits, feature flags, decision log |
| Project overview | `docs/PROJECT.md` | Repository layout, technology stack |

---

*End of FSD Part 6 — Engineering.*
