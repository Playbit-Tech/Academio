# Codebase Concerns

**Analysis Date:** 2026-07-18

---

## Security

### MEDIUM: Unchecked error discards in security-critical paths

`backend/internal/modules/auth/service.go` contains ~18 intentional error discards (`_ =`) in security-sensitive operations including cache operations, blacklist revocations, session revocations, and queue dispatches. While most are documented as "best-effort" (e.g., cache invalidation, blacklist JTI, user cache Set/Delete), the pattern makes it hard to distinguish intentional best-effort from accidental error swallowing.

Key locations:
- `backend/internal/modules/auth/service.go:301` — `_ = s.blacklist.BlacklistJTI(ctx, claims.ID, remaining)` - blacklisting errors are silently dropped during logout
- `backend/internal/modules/auth/service.go:555` — `_ = s.blacklist.BlacklistJTI(ctx, claims.ID, remaining)` - same pattern in ChangePassword
- `backend/internal/modules/auth/service.go:720` — `_ = s.tokenSvc.RevokeAllSessions(ctx, userID)` - session revocation failure silently dropped in DeleteAccount
- `backend/internal/modules/auth/service.go:981` — `_ = s.tokenSvc.RevokeAllSessions(ctx, vt.UserID)` - during password reset via token
- `backend/internal/modules/auth/service.go:909,1072` — `_ = s.queueClient.Enqueue(task)` - email dispatch failures silently dropped

**Impact:** Security events (token revocation, session invalidation, audit-relevant actions) may fail silently without observability.

### LOW: JWT secret default validation

`backend/internal/config/config.go:216` — Default JWT secret is `"change-me-in-production"`. The config validation at line 362 catches this and returns a fatal error, but only if the env var is explicitly set to this value. If the env var is unset, the default is used and the validation error triggers. **Mitigated** by startup validation.

### MEDIUM: `context.Background()` in audit batch insert

`backend/internal/middleware/audit.go:160` — `context.Background()` is used with a 5-second timeout for the audit batch insert. This means audit events are written without request context propagation (no tenant_id, user_id, request_id in the query context). Under high load when a request is cancelled but the audit goroutine continues, this is acceptable, but it prevents DB statement-level tracing from correlating audit writes to specific requests.

Same pattern in:
- `backend/internal/backup/service.go:172` — `context.Background()` for retention enforcement in goroutine
- `backend/pkg/storage/s3.go:95,112` — `context.Background()` for S3 Put/Delete operations (not backup-specific)

### LOW: CORS allows all when origins empty

`backend/internal/middleware/cors.go:19` — When `allowedOrigins` is empty/nil, all origins are allowed (`allowAll = true`). This is documented as "useful for development." In production, the CORS config is populated from `CORS_ALLOWED_ORIGINS` env var which defaults to `"http://localhost:4000,http://localhost:5173"`, so this is safe in practice. But a misconfiguration could expose the API.

### LOW: S3 URL hardcodes AWS domain

`backend/pkg/storage/s3_backup.go:92` — `URL()` method hardcodes `s3.%s.amazonaws.com` as the URL template. This breaks when using S3-compatible storage (MinIO, DigitalOcean Spaces) via a custom endpoint. The `S3Config.Endpoint` field exists but is not used for URL generation.

### INFO: CSRF protection can be silently disabled

`backend/internal/middleware/csrf.go:125-129` — When `APP_SECRET` is not configured, CSRF validation is silently skipped for all routes. The config validation logs a warning in dev but is not fatal. `backend/internal/config/config.go:369-371` — warns but continues.

---

## Performance

### MEDIUM: No Prometheus metrics endpoint

The router imports `prometheus` (`backend/internal/router/setup.go:11`) but no `/metrics` endpoint or promhttp handler is visible in the middleware stack. There is no standard Prometheus HTTP handler registered, meaning runtime metrics (request count, latency, error rates, DB pool stats) cannot be scraped. The telemetry system has OpenTelemetry tracing configured but the MeterProvider is explicitly set to a no-op (`backend/internal/telemetry/provider.go:64` comment confirms).

### MEDIUM: `PrepareStmt: false` on core DB

`backend/internal/database/postgres.go:29` — `PrepareStmt` is set to `false` for the core DB because the `SchemaTablePrefix` plugin corrupts cached field-index mappings when prepared statements are enabled. This means every GORM query on the core DB is re-planned by PostgreSQL, adding query planning overhead to every request. The `ConnectionManager.createConnection` at `connection_manager.go:258` sets `PrepareStmt: true` for per-tenant dedicated DB connections (legacy mode), but the primary schema-per-tenant path uses the core DB with prepare disabled.

### LOW: Missing pagination on remaining list endpoints

Per the audit checklist at `docs/architecture/10-AUDIT-CHECKLIST.md:187`, unbounded queries on remaining list endpoints were "flagged as future work." Three academic endpoints (ListSessions, ListCurriculums, ListAssessments) were fixed with pagination. Other list endpoints across the 39 modules may still return unbounded result sets.

### INFO: N+1 query patterns partially mitigated

`Preload` is used in 237 locations across the modules (timetable, inventory, messages, communication, etc.), indicating awareness of the N+1 problem. However, `backend/internal/modules/academic/repository.go:156-171` shows nested raw SQL queries in a loop: curriculum → assessments → grade items, which could be N+1 if not batched in SQL.

`backend/internal/modules/score/service.go` contains `for _, cur := range session.Curriculums { for _, a := range cur.Assessments { ... } }` loops (lines 271-272) that could trigger N+1 if lazy-loaded.

---

## Maintainability

### HIGH: Three files exceed 2000 lines

| File | Lines | Concern |
|------|-------|---------|
| `backend/internal/modules/user/handler.go` | 2,494 | Multiple concerns mixed in one file |
| `backend/internal/modules/hr/handler.go` | 2,281 | Very large handler file |
| `backend/internal/modules/user/service.go` | 2,240 | Large service file |

These exceed the 120-line function target and 500-line file heuristic from the audit checklist. Refactoring these into multiple files or splitting concerns would improve maintainability.

### MEDIUM: 40+ intentional error discards across production code

The `_ = ` pattern is used extensively across the backend:
- `backend/internal/modules/auth/service.go` — 18 discards (cache, blacklist, queue, session revocations)
- `backend/internal/modules/user/service.go` — `exists, _ = s.userRepo.ExistsByEmail(...)` patterns (lines 1476, 1903)
- `backend/internal/modules/school/service.go:238,257` — `_ = json.Unmarshal(...)` discards
- `backend/internal/modules/tenant/repository.go:68,120` — `_ = r.CacheTenantConfig(...)` and `_ = r.deleteFromCache(...)`
- `backend/internal/modules/library/service.go:45,74,92,105,148` — `_ = tempIssueRepo` (unused dependency)
- `backend/internal/pkg/validator/validator.go` — 8 `_ = v.RegisterValidation(...)` discards (acceptable — registration failure would be a programming error)

While many are documented as "best-effort," the aggregate makes it hard to audit whether a discard is intentional or accidental.

### MEDIUM: Dead code / unused variables

- `backend/internal/modules/library/service.go:45,74,92,105,148` — `_ = tempIssueRepo` is repeatedly assigned to the blank identifier, indicating an unused dependency that was never wired up
- `backend/internal/modules/hr/handler.go:2281` — `var _ = time.Parse` — import guard for unused `time` package import? This is a dead code smell
- `backend/internal/modules/admission/service.go:1008` — `_ = app` is an unused variable
- `backend/internal/modules/timetable/service.go:57` — `_ = school` is an unused parameter

### MEDIUM: `context.Background()` in production goroutines

- `backend/internal/backup/service.go:172` — backup retention enforcement launches a goroutine with `context.Background()`
- `backend/internal/middleware/audit.go:160` — audit batch insert uses `context.Background()` (acceptable as the goroutine outlives the request, but loses context propagation)
- `backend/internal/restore/handler.go:63` — restore handler launches a goroutine

### LOW: Module path mismatch

`go.mod` uses module path `github.com/playbits/schoolcare-v2` but the repository is named `academio`. This causes confusion for developers and IDE tooling.

### LOW: Only 2 TODO/FIXME comments found across 61K+ lines of Go

Only 2 TODOs found, both in `backend/internal/modules/auth/handler.go` (lines 447, 557) about email dispatch. Either:
1. All issues have been diligently addressed, OR
2. Issues are not being tracked in code comments

The audit checklist from `docs/architecture/10-AUDIT-CHECKLIST.md` has many unchecked items suggesting the latter.

### LOW: Some modules have inconsistent file structure

While most modules follow the `dto.go`, `handler.go`, `service.go`, `repository.go` pattern, some do not:
- `transport` module: 4 files (some may be missing standard files)
- `tenant` module: 4 files
- `communication` module: 7 files (may include sub-modules)

### LOW: ReportBuilder stub with placeholder

`backend/internal/modules/reportbuilder/service.go:148` — Contains a TODO comment indicating report generation is a placeholder: `"Full data querying will be implemented in the next iteration."` The report builder returns a CSV with only configuration metadata, not actual data.

---

## Scalability

### MEDIUM: Single-DB bottleneck for schema-per-tenant

All tenant schemas live in the same PostgreSQL database (`shared-postgres`). While schema-per-tenant provides logical isolation, the single database instance is a scalability bottleneck. As the number of schools grows:
- Connection pool contention increases (25 max open connections default)
- A single noisy tenant can impact all others
- `pg_dump` for backup locks the entire instance
- SchemaTablePrefix plugin adds per-query overhead

The `ConnectionManager` (`connection_manager.go`) supports per-school dedicated databases (legacy model) but this path is deprecated in favor of schema-per-tenant.

### MEDIUM: Connection pool limited to 25 connections

`backend/internal/config/config.go:206` — `MaxOpenConns: 25`. With 39 modules serving concurrent requests, 25 connections can become a bottleneck during peak load. Each module may hold connections for the duration of request processing.

### LOW: Synchronous provisioning for schema-per-tenant

`backend/internal/database/tenant/provisioning.go` — `ProvisionSchool` is synchronous. While schema creation is near-instant, the frontend polls `GET /schools/:id` until `database_status` is `"active"`. This is acceptable but means the HTTP request thread is blocked during provisioning (CREATE SCHEMA, migrations, seeding).

### LOW: Asynq queue underutilized

The asynq queue (`backend/internal/queue/`) is only used for email dispatch (`backend/internal/modules/auth/service.go:909,1072`). Other async-capable workloads (report generation, backup, restore, bulk operations) don't use the queue.

---

## Operational Concerns

### MEDIUM: Observability gaps

- **No metrics endpoint** — `/metrics` (Prometheus) not registered despite `prometheus` import in router setup
- **No liveness/readiness endpoints visible** — need to verify `GET /health`, `/ready`, `/live` exist
- **OTEL MeterProvider is a no-op** — `backend/internal/telemetry/provider.go:64` — "the default MeterProvider (no-op) is used for now"
- **Logging does not consistently include structured fields** — `backend/internal/middleware/logger.go` uses `slog.Info("request", args...)` which is good, but `pkg/logger` functions (`Infof`, `Warnf`, `Errorf`) use `fmt.Sprintf` internally (lines 140-153), losing structured field benefits

### LOW: Static analysis tooling broken

`AGENTS.md:44` — `staticcheck` is incompatible with Go 1.25/1.26 (built with 1.23.4). CI cannot run static analysis. The `.golangci.yml` exists but may also be incompatible.

### LOW: Two Redis rate limiter tests fail

`AGENTS.md:45` — `TestRedisRateLimiter_Allow` and `TestRedisRateLimiter_SlidingWindowPrecision` fail because installed Redis truncates sub-second durations to 1s. These are pre-existing failures unrelated to recent changes.

### LOW: Seed scripts use `fmt.Printf` instead of structured logging

`backend/scripts/seed/main.go` and `backend/scripts/migrate/main.go` use `fmt.Printf` for output instead of `pkg/logger`. While acceptable for CLI tools, this means seed/migration output doesn't include timestamps or structured fields.

### LOW: S3 backup URL method not compatible with custom endpoints

`backend/pkg/storage/s3_backup.go:92` — The `URL()` method constructs `https://{bucket}.s3.{region}.amazonaws.com/{path}` which only works for standard AWS S3. Projects using MinIO, DigitalOcean Spaces, or other S3-compatible storage will get incorrect URLs. The `S3Config.BaseURL` field exists but is not used here.

---

## Test Coverage Gaps

### HIGH: No tests found for many modules

Of the 39 modules, test files exist in only a few. Quick scan found test files in:
- `backend/internal/middleware/` — `auth_test.go`, `error_test.go`, `ratelimit_test.go`, `requestid_test.go`, `schoolid_test.go`, `security_test.go`, `tenant_test.go`
- `backend/internal/modules/auth/` — `service_test.go`, `mock_repository_test.go`
- `backend/internal/database/tenant/` — `connection_manager_test.go`, `factory_test.go`, `integration_test.go`, `isolation_test.go`, `migration_service_test.go`
- `backend/pkg/storage/` — `local_test.go`, `s3_backup_test.go`
- `backend/internal/services/` — `blacklist_service_test.go`, `refresh_store_test.go`, `user_cache_test.go`
- `backend/internal/backup/` — `service_test.go`
- `backend/internal/config/` — `config_test.go`

**Many modules have zero tests.** The audit checklist targets 80% service layer coverage, 70% repository, 60% handler. This is far from achieved.

### MEDIUM: Integration test only covers happy path

`backend/scripts/test_endpoint.sh` covers the full end-to-end flow (40 tests) but is predominantly a happy-path test. It does not test:
- Error cases (invalid credentials, expired tokens, duplicate entries)
- Concurrent access / race conditions
- Tenant isolation breaches
- Rate limiting behavior
- Backup/restore round-trip
- Large payloads or boundary conditions

---

## Technical Debt

### MEDIUM: ReportBuilder is a placeholder

`backend/internal/modules/reportbuilder/service.go:148` — `"Full data querying will be implemented in the next iteration."` This module exists in production but returns CSV files with only metadata, not actual query results. This could confuse users.

### MEDIUM: Library module has unwired dependency

`backend/internal/modules/library/service.go` — Contains `var _ = tempIssueRepo` on 5 separate lines (45, 74, 92, 105, 148). This is an unused repository that was presumably intended for a library issue tracking feature that was never completed.

### LOW: Admission module has unused variable

`backend/internal/modules/admission/service.go:1008` — `_ = app` — an unused variable assignment suggesting incomplete refactoring.

---

## Dependencies at Risk

### LOW: Prometheus client imported but unused metrics endpoint

`backend/internal/router/setup.go:11` — `"github.com/prometheus/client_golang/prometheus"` is imported but there is no `promhttp.Handler()` registered. The import may only be used for Go runtime metric registration without an endpoint to expose them.

### LOW: `golang-jwt/jwt/v5` used with HS256

`backend/pkg/jwt/jwt.go` — Uses HMAC-SHA256 (HS256) for JWT signing. HS256 is symmetric — the same secret signs and verifies. For multi-service deployments, RS256 (asymmetric) would allow verification without sharing the signing key. Not a vulnerability but a limitation for future service decomposition.

### INFO: OpenTelemetry configured but not fully wired

`backend/internal/telemetry/provider.go` exists and has a full OTLP exporter setup with batch span processing, but:
- `otel.SetMeterProvider` is never called (no-op meter provider)
- The `Tracing()` middleware only creates spans — it doesn't export metrics
- No trace sampling configuration beyond `AlwaysSample()`, which could be expensive in production
