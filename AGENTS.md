## Goal
Apply code quality fixes (error discards, security, context propagation, code quality) and validate end‑to‑end onboarding + scoring flows for a ~58K-line backend across 39 Go modules.

## Constraints & Preferences
- Go 1.26+, GORM v1.30.0, Gin framework, pgx/v5 PostgreSQL driver.
- Multi-tenant: each school gets its own PostgreSQL database via tenant `ConnectionManager`.
- Backend on :8080; frontend Vite dev server on :4000 proxies `/api` → :8080.
- Air handles hot reload (binary at `backend/tmp/server`).
- All fixes must pass `go build ./...`, `go vet ./...`, and auth tests.
- **Use `pkg/logger`** (slog wrapper) for logging; `logger.Warnf`/`logger.Errorf`.
- **Redis required** for asynq queue (tenant provisioning). Docker container `shared-redis` at localhost:6379.
- **Use `backend/scripts/test_endpoint.sh`** for integration testing — covers full flow (40 tests). Don't write ad-hoc test scripts.
- **pgx v5 prepared-statement mode** does NOT support multiple SQL statements in one `db.Exec()`. Break into individual calls.

## Progress
### Done
- **Initial CRITICAL/HIGH code review fixes** (13 items): TOCTOU in Register, BatchDelete N+1, ChangePassword revoke, Logout error logging, ListScores cap, mergeGradeItemScore data loss, build\*JSON marshal errors, computeGradeItemsTotal warning, CSRF nonce token, fresh repos helper, dead RedisClient removed, CORS credentials fix, unbounded query caps.
- **Phase 08: Error discard patterns** — 21 patterns fixed across reports (13 log-and-continue), communication (3 log), admission (2 error-return), cba (3: 2 log + 1 sig change `gradeExamAnswers`).
- **Phase 09: Security hardening** — CSRF fallback `logger.Warnf`; `net/url` DSN in `tenant/config.go` + `config/config.go`; `safeDBNameRegex` in `provisioning.go`.
- **Phase 10: Context propagation** — `GetTenantDB`/`GetTenantDBByUUID` accept `ctx` (8 callers + tests updated); `provisioning.go` seed methods receive `ctx`; `s3_backup.go` all 4 methods accept `ctx` (callers updated); `alumni/service.go` `GetDashboardInsights` accepts `ctx`.
- **Phase 11: Code quality** — `tool.go` `Register()` returns `error` (caller `runner.go` updated); `ratelimit.go` `Stop()` method; `postgres.go` `Close(ctx)` with exponential backoff; `uuid_columns.go` `checkSafeTableName` guard; `connection_manager.go` health goroutine uses `WaitGroup`.
- **Provisioning fix** — `user_infos.go` multi‑statement `db.Exec()` broken into 7 individual calls (pgx prepared‑statement compatibility).
- **Test script fix** — `test_endpoint.sh` CSRF token extraction changed from `extract_value` (breaks on colon) to `extract_nested`; school creation payload updated to match `CreateSchoolRequest` DTO.
- **End-to-end validation** — `test_endpoint.sh` passes **40/40 tests, 0 failed** (health → CSRF → register → login → school create → provisioning poll → curriculum → assessments → sessions → grade items → sum-to-100 validation).
- `go build ./...` and `go vet ./...` clean.

### In Progress
- *(none)*

### Blocked
- `staticcheck` incompatible with Go 1.25/1.26 (built with 1.23.4).
- Redis rate limiter tests (`TestRedisRateLimiter_Allow`, `TestRedisRateLimiter_SlidingWindowPrecision`) fail because installed Redis truncates sub-second durations to 1s — pre-existing, unrelated.

## Key Decisions
- **Reports: log-and-continue** for GORM errors — analytics queries are best-effort; failing reports on transient DB blips is worse.
- **Communication/Admission/CBA: return errors** — state mutations where silent failures would corrupt status.
- **`gradeExamAnswers` signature changed** from `(float64, float64)` to `(float64, float64, error)`.
- **Break multi‑statement `db.Exec()` into individual calls** for pgx v5 prepared‑statement compatibility.
- `ChangePassword` logs RevokeAllSessions error instead of returning it — password change itself succeeded, session revocation is best-effort defense in depth.
- `computeGradeItemsTotal` logs a warning instead of returning an error when a score exceeds max — prevents rollup from blocking on data quality issues.

## Next Steps
1. Verify the full score entry → rollup flow works in Teacher Academics (grade items, scoring, sum-to-100 validation — covered by `test_endpoint.sh`).
2. Update README.md and AGENTS.md to reference `scripts/test_endpoint.sh` so future sessions don't rewrite it.
3. Clean up `.tmp/sessions/` and `.planning/phases/` artifacts.

## Critical Context
- `.env` connects to `shared-postgres` container at `localhost:5432`, user `postgres`, database `academio`.
- Super admin credentials after seed: `playbit / Password123!`.
- Provisioning runs as an asynq background task; frontend must poll `GET /api/v2/schools/:id` until `database_status` is `"active"`.
- Use `make db-init DROP_TENANT=true && make migrate && make seed` to reset the database.
- `models.School` has a `DatabaseStatus` field (enum: `pending`, `active`, `provisioning_failed`).
- Docker containers `shared-postgres` (5432) and `shared-redis` (6379) always running.
- Build time ~2 min cold, ~15-30s warm.
- Server start: `cd backend && ./bin/server` (binds :8080). Queue worker runs as goroutine inside same process.
- `.env` at `backend/.env` with `JWT_SECRET`, `ENCRYPTION_KEY`, `DB_*`, `REDIS_*` config.

## Relevant Files
- `backend/scripts/test_endpoint.sh` — integration test suite, 40 tests, full flow. Run after `make db-init && make migrate && make seed && ./bin/server`.
- `backend/internal/database/migrations/school/user_infos.go` — provisioning migration: multi‑statement `db.Exec()` → 7 individual calls.
- `backend/internal/modules/reports/service.go`: 13 discard patterns fixed (log-and-continue).
- `backend/internal/modules/communication/service.go`: 3 discard patterns fixed (log), import added.
- `backend/internal/modules/admission/service.go`: 2 discard patterns fixed (error return).
- `backend/internal/modules/cba/service.go`: 3 discard patterns fixed (2 log, 1 sig change `gradeExamAnswers`).
- `backend/internal/middleware/csrf.go`: `logger.Warnf` when `APP_SECRET` unset; nonce-based tokens.
- `backend/internal/database/tenant/config.go` + `backend/internal/config/config.go`: `DSN()` uses `net/url`.
- `backend/internal/database/tenant/provisioning.go`: DB name regex guard + seed methods receive `ctx`.
- `backend/pkg/storage/s3_backup.go`: All 4 methods accept `ctx`.
- `backend/internal/modules/alumni/service.go`: `GetDashboardInsights` accepts `ctx` (handler updated).
- `backend/internal/database/tenant/connection_manager.go`: `GetTenantDB`/`GetTenantDBByUUID` accept `ctx`; `healthLoop` uses `sync.WaitGroup`.
- `backend/internal/database/models/school.go`: School model with `DatabaseStatus` field.
- `backend/internal/modules/auth/repository.go`: `CreateUserWithChecks()` with advisory lock.
- `backend/internal/modules/auth/service.go`: Register, BatchDelete, ChangePassword, Logout fixes.
- `backend/internal/modules/score/service.go`: build/marshal errors, type safety, repos helper, page cap.
- `backend/internal/middleware/cors.go`: Credentials only with explicit origin.
