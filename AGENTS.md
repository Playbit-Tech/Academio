## Goal
Apply code quality fixes (error discards, security, context propagation, code quality), validate end‑to‑end onboarding + scoring flows, and complete attendance + timetable features for a ~58K-line backend across 39 Go modules.

## Constraints & Preferences
- Go 1.26+, GORM v1.30.0, Gin framework, pgx/v5 PostgreSQL driver.
- Multi-tenant: schema-per-tenant isolation via GORM `SchemaTablePrefix` plugin. All schools share one PostgreSQL database; each school's data lives in its own schema (`school_{id}`).
- **🚨 CRITICAL — Shared Schema vs Tenant Schema**: `User` (users table) lives in the **`public` schema** (shared DB). All school-specific models (`Teacher`, `Student`, `UserInfo`, `Level`, `Score`, `Subject`, `Assessment`, `Session`, `GradeItem`, `Alumni`, etc.) live in the **tenant schema** (`school_{id}`). The `SchemaTablePrefix` plugin automatically prepends `school_{id}.` to all table names during GORM operations — so a query like `db.Find(&students)` becomes `SELECT * FROM school_42.students`. Before writing any query or repository method, always check which schema the model lives in. When in doubt, check the migration file: `backend/internal/database/migrations/school/` (tenant schema) vs `backend/internal/database/migrations/shared/` (public schema). Tenant context is resolved via `TenantDBResolver` middleware and cached in Redis via `TenantResolutionService`.
- Backend on :8080; frontend Vite dev server on :4000 proxies `/api` → :8080.
- Air handles hot reload (binary at `backend/tmp/server`).
- All fixes must pass `go build ./...`, `go vet ./...`, and auth tests.
- **Use `pkg/logger`** (slog wrapper) for logging; `logger.Warnf`/`logger.Errorf`.
- **Redis required** for asynq queue (tenant provisioning). Docker container `shared-redis` at localhost:6379.
- **Use `backend/scripts/test_endpoint.sh`** for integration testing — covers full flow (40 tests). Don't write ad-hoc test scripts.
- **pgx v5 prepared-statement mode** does NOT support multiple SQL statements in one `db.Exec()`. Break into individual calls.
- **Use `docs/architecture/10-AUDIT-CHECKLIST.md`** for production audit gate — run before any release. Covers architecture, security, DB, performance, observability, tenant isolation, testing, and consistency.

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
- **Parent/guardian validations (session changes + CR fixes):** Session edit drawer curriculum read-only; structured address in form JSONB; 2-step student wizard (checkboxes → address fields); XLSX sample 20 rows; `isEmptyAddress()` helper for `any`-type address; `json.Marshal` error handling at both call sites; role assignment logging via `logger.Warnf`; parent dedup by email→phone→username; sibling UserInfo reuse; combined error collection per parent.
- **Artifact cleanup** — Removed stale GSD artifacts (`.planning/`, `.tmp/`, stale plan files); plan persisted at `docs/plans/CR-CODE-REVIEW-FIXES.md`.
- `go build ./...` and `go vet ./...` clean.
- **TypeScript zero-errors** — 46 pre-existing typecheck errors fixed across 6 batches; `npx tsc --noEmit` passes clean.
- **Vercel/CI Yarn 4 fix** — `vercel.json` + GitHub CI use `corepack yarn` to bypass global Yarn 1.
- **Teacher assessment score grid fixes** — persisted filter selections, dirty scores, AlertDialog on filter change, logout cleanup; `persistDirty()` now called from `setCellValue`, comment `onChange`, `handleSaveAll`; `onKeyDown` guard + `type="number"` on score inputs; `is_active` filter for assessments; proportional total calculation `(studentSum / maxScoreSum) × assessmentTotal`; fixed student ID mismatch via `StudentID` DTO field.
- **Timetable feature (backend + frontend):** Added `subject_name`, `teacher_name`, `level_name` to `TimetableResponse` DTO with GORM Preloads; added missing `Teacher` relation on Timetable model. Frontend: 3-tab weekly/daily/events layout, CRUD Sheet dialog with react-hook-form + Zod validation, resolved display names, session/level filter bar.
- **Student attendance feature (backend + frontend):** Added `level_id`/`session_id` optional filters to `GET /academic/attendance`; new `POST /academic/attendance/bulk` upsert endpoint. Frontend: roll-call mode (select timetable → see class students → bulk mark present/absent/late → Save All to bulk endpoint), records tab with student name resolution, stats cards.
- **Teacher/staff attendance:** New teacher clock-in/out page (`/_dashboard/teacher/attendance`) with history table, weekly summary cards, role-gated to `requireRole(["teacher"])`.
- **Calendar-style bulk timetable editor:** New bulk create endpoint `POST /timetables/bulk` accepting an array of entries; new `GET /timetables/calendar?level_id=&session_id=` for class-wide grid view. Frontend: editable calendar grid component with click-to-create/update/delete popovers, conflict highlighting (red border on overlapping entries), bulk toolbar with Clear Day (confirm dialog) and Fill Week (per-day form → bulk create). Integrated as a new "Calendar Editor" tab on the timetable page alongside the existing read-only view.
- **Schema-aware backup/restore:** `CreateTenantBackup` uses `pg_dump --schema=<schema>`, S3 uploads, 14-backup retention. `RestoreTenantBackup` downloads from S3, drops/recreates schema, `pg_restore --schema=<schema>`, validates. Build/vet/tests all pass.
- **FK circular dependency fix verified:** 41/41 integration tests pass end-to-end (register → login → school create → provisioning → curriculum → sessions → assessments → grade items → sum-to-100).
- **SchemaTablePrefix debug logging removed:** Noisy `[schema:prefix_table] DEBUG` lines removed from `schema_db.go` — seed and runtime output much cleaner.

### Blocked

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
- **Parent dedup priority**: email → phone → username (email is strongest identifier).
- **Parent `UserInfo` skipped** in tenant DB if already exists (sibling reuse) — avoids duplicate-key error on `user_info.user_id` unique index.
- **`ParentData.Address` uses `any` type** to accept both flat string (XLSX compat) and structured map/object (form submission), stored in `UserInfo.Details` JSONB.
- **Session update** uses `Select("name","year","term","status","description","details").Updates(session)` — never touches many2many join tables.
- **Sonner `<Toaster />`** belongs in root layout (`__root.tsx`), not child routes, so toasts survive navigation and drawer close.
- **Timetable response includes resolved names** via GORM Preloads (`Subject`, `Teacher.UserInfo`, `Level`) so frontend can display names without additional lookups.
- **Attendance bulk upsert** uses `Where(...).Assign(...).FirstOrCreate(...)` — idempotent, handles both create and update in one call.
- **Attendance filter by level/session** resolves timetable IDs via a timetable query, then filters attendance by those IDs — avoids adding level_id/session_id as denormalized columns on attendance.
- **Timetable bulk create** uses GORM batch `Create(&entries)` in a single call — no need for manual transaction wrapping.
- **Timetable calendar grid** keeps existing single-entry Sheet dialog for fine-tuning, adds the visual calendar as a supplementary "Calendar Editor" tab.

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
- `backend/STYLE.md` — human-readable Go coding conventions (replaces running `.golangci.yml` locally). **Read this before writing any backend code.**
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
- `backend/internal/modules/user/service.go`: Parent validation rules (R1-R3, per-parent completeness), parent dedup by email→phone→username, sibling UserInfo reuse, `isEmptyAddress()` helper for `any`-type address, combined error collection in `BatchCreateStudents`, structured address in `UserInfo.Details` JSONB.
- `backend/internal/modules/user/dto.go`: `Address` as `any` on `ParentData`, additional import preview fields (`father_address`, `mother_address`, `guardian_address`).
- `backend/internal/modules/user/repository.go`: `FindByEmail`, `FindByPhone`, `FindUserInfoByUserID` for parent dedup.
- `backend/internal/database/models/curriculum.go`: `ActiveContinuousAssessmentID` FK documentation comment.
- `backend/internal/pkg/logger`: `logger.Warnf`/`logger.Errorf` used for error discards and role assignment logging.
- `frontend/src/routes/_dashboard/users.tsx`: 2-step student wizard (checkboxes → structured address fields), `buildAddress()` helper, `stepCircleClass()` helper, Zod validation with superRefine for per-parent fields.
- `frontend/src/routes/_dashboard/school.tsx`: Session save flow, curriculum read-only in edit drawer.
- `frontend/src/lib/hooks/useSchool.ts`: `useSubjects`/`useClasses` without `enabled` guard.
- `frontend/src/routes/__root.tsx`: Sonner `<Toaster />` placement for global toast visibility.
- `frontend/src/components/academics/excel-upload-step.tsx`: XLSX preview step with import confirmation.
- `docs/plans/CR-CODE-REVIEW-FIXES.md`: Phase plan for current CR work.
- `backend/internal/modules/timetable/`: Full CRUD for timetables (dto.go, handler.go, service.go, repository.go).
- `backend/internal/modules/academic/`: Student attendance endpoints (handler.go, service.go, repository.go, dto.go).
- `backend/internal/modules/hr/`: Staff attendance clock-in/out (handler.go, service.go, repository.go).
- `backend/internal/database/models/school.go`: Timetable model with Teacher GORM relation.
- `backend/internal/database/models/attendance.go`: Student Attendance model.
- `backend/internal/database/models/hr.go`: StaffAttendance model.
- `frontend/src/routes/_dashboard/timetable.tsx`: 4-tab weekly/daily/events/calendar-editor timetable page with CRUD dialogs + bulk calendar grid.
- `frontend/src/components/timetable/calendar-grid.tsx`: Editable calendar grid with click-to-create/update/delete popovers and conflict highlighting.
- `frontend/src/components/timetable/bulk-toolbar.tsx`: Bulk toolbar with Clear Day (confirm dialog) and Fill Week (per-day form) actions.
- `frontend/src/components/timetable/calendar-editor-view.tsx`: Wrapper combining calendar grid + toolbar with session/level filters.
- `frontend/src/routes/_dashboard/attendance.tsx`: Roll-call grid + records with student name resolution.
- `frontend/src/routes/_dashboard/teacher.tsx`: Teacher clock-in/out page.
- `frontend/src/lib/hooks/useTimetable.ts`: TimetableEntry interface + useTimetable hook.
