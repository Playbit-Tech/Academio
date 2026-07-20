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
- Provisioning runs synchronously (no background task); frontend must poll `GET /api/v2/schools/:id` until `schema_name` is non-empty (the provisioning completion signal).
- Use `make db-init DROP_TENANT=true && make migrate && make seed` to reset the database.
- `models.SchoolConnection` has a `SchemaName` field — if non-empty, the school is provisioned.
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

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Academio**

Academio is a multi-tenant school management system that provides K-12 and higher education institutions with tools for academic management, admissions, student information, finance, HR, communication, and reporting. Each school runs in its own database schema, with shared user authentication across the platform.

**Core Value:** Students can be enrolled, tracked through their academic journey, and assessed — with every school's data isolated and secure in its own tenant schema.

### Constraints

- **Tech Stack**: Go 1.26+, GORM v1.31+, Gin, pgx/v5, PostgreSQL — no migrations to other languages/frameworks
- **Multi-Tenant**: Schema-per-tenant isolation — must never leak data between schools
- **Database**: Single PostgreSQL instance shared across all tenants — connection pool must be carefully managed
- **Public Endpoints**: Admission forms are public (no auth) — must be secured via rate limiting and reference numbers
- **Background Tasks**: Asynq queue for async operations — Redis required for tenant provisioning
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- **Go 1.26.1** — All backend services (`backend/`), 39+ modules
- **TypeScript ~5.x** — Frontend SPA (`frontend/src/`)
- **Bash** — Integration test suite (`backend/scripts/test_endpoint.sh`), CI scripts
- **JavaScript** — Load testing scripts (`scripts/loadtest/*.js`)
- **SQL (PostgreSQL)** — Database queries, GORM-generated, pg_dump/pg_restore
## Backend Runtime
## Frontend Runtime
## Testing
- Test Runner: `go test`
- SQL Mock: go-sqlmock v1.5.2
- Assertions: testify v1.11.1
- Integration: Custom Bash script (`backend/scripts/test_endpoint.sh`), 40 tests
- Containerized DB: testcontainers-go v0.43.0
- GORM SQLite driver v1.6.0 (for test isolation)
- Test Runner: Vitest v4.1.9
- Component Testing: @testing-library/react v16.3.2, @testing-library/dom v10.4.1, @testing-library/user-event v14.6.1
- DOM Assertions: @testing-library/jest-dom v6.9.1
- DOM Environment: jsdom v29.1.1
- E2E: Playwright v1.61.1 (`@playwright/test`)
## Infrastructure & DevOps
- Docker (`backend/Dockerfile`): Multi-stage build, golang:1.26-alpine → alpine:3.19
- Docker Compose: Managed externally (PostgreSQL `shared-postgres` on :5432, Redis `shared-redis` on :6379)
- GitHub Actions (`.github/workflows/ci.yml`) — `go vet ./...`, backend tests with race detection, coverage threshold
- Vercel Deployment — Frontend SPA (Vite build, `vercel.json`)
- **Air** — Go hot reload (binary at `backend/tmp/server`)
- **Makefile** — `make db-init`, `make migrate`, `make seed`, etc.
- **Swagger** — API docs via `swaggo/swag` v1.16.6, `swaggo/gin-swagger` v1.6.1, `swaggo/files` v1.0.1
- **Prometheus** — Metrics endpoint via `prometheus/client_golang` v1.19.1
## Configuration
- `.env` file loaded by godotenv (`backend/.env`)
- Config struct: `backend/internal/config/config.go`
- All config loaded from environment variables with sensible defaults
- Vite env vars prefixed with `VITE_` (`import.meta.env`)
- `VITE_API_URL`, `VITE_WS_URL`, `VITE_GOOGLE_MAPS_API_KEY`, `VITE_MAPBOX_ACCESS_TOKEN`
## Go Dependencies (Key)
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/gin-gonic/gin` | v1.12.0 | HTTP framework |
| `gorm.io/gorm` | v1.31.2 | ORM |
| `gorm.io/driver/postgres` | v1.6.0 | PostgreSQL driver (pgx/v5) |
| `github.com/redis/go-redis/v9` | v9.21.0 | Redis client |
| `github.com/hibiken/asynq` | v0.26.0 | Task queue |
| `github.com/aws/aws-sdk-go-v2` | v1.42.0 | AWS SDK (S3) |
| `github.com/aws/aws-sdk-go-v2/service/s3` | v1.104.1 | S3 storage |
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/openai/openai-go` | v1.12.0 | OpenAI API client |
| `google.golang.org/genai` | v1.62.0 | Google Gemini API client |
| Package | Version | Purpose |
|---------|---------|---------|
| `go.opentelemetry.io/otel` | v1.41.0 | OpenTelemetry SDK |
| `go.opentelemetry.io/otel/sdk` | v1.35.0 | OTel SDK |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace` | v1.28.0 | OTLP trace exporter |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc` | v1.28.0 | OTLP gRPC transport |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp` | v1.28.0 | OTLP HTTP transport |
| `github.com/prometheus/client_golang` | v1.19.1 | Prometheus metrics |
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/xuri/excelize/v2` | v2.11.0 | Excel file generation |
| `github.com/gorilla/websocket` | v1.5.3 | WebSocket support |
| `gorm.io/datatypes` | v1.2.7 | GORM data types (JSON, etc.) |
| `gorm.io/driver/sqlite` | v1.6.0 | SQLite (test isolation) |
| `cloud.google.com/go` | v0.116.0 | GCP SDK (indirect, via Gemini/OTel) |
## Dependency Licenses
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Go Conventions
### Project Structure
- `dto.go` — Request/response DTOs with `json` struct tags and `binding` validation tags
- `handler.go` — HTTP handler with Gin `*gin.Context`, route parsing, response formatting
- `service.go` — Business logic with named `*Service` struct and `New*Service` constructor
- `repository.go` — Data access with GORM, repository interface defined at top
### Naming Conventions
| Construct | Convention | Example |
|---|---|---|
| Files | camelCase | `service.go`, `dto.go`, `handler.go` |
| Exported functions | PascalCase | `CreateUserWithChecks` |
| Unexported functions | camelCase | `findOrCreateParentUserInCore` |
| Service/Handler types | PascalCase | `UserService`, `UserHandler` |
| Interfaces | Meaningful `Interface` suffix | `UserRepositoryInterface` |
| Error vars | `Err` prefix | `ErrNotFound`, `ErrConflict` |
| Constants | PascalCase | `MaxPageSize`, `RoleParent` |
| Abbreviations | Keep case | `schoolID`, `userURL` |
| Receivers | 1-2 letter abbreviation | `s *UserService`, `r *UserRepository` |
### Import Organization
### Error Handling
| Context | Strategy | Rationale |
|---|---|---|
| Analytics/reports queries | Log warning, continue | Best-effort analytics |
| State mutations | Return error | Silent failures corrupt status |
| Batch operations | Collect all errors, return one message | Better UX — user fixes everything in one pass |
- `NewNotFoundError(entity string)` — 404
- `NewConflictError(msg string)` — 409
- `NewForbiddenError(msg string)` — 403
- `NewUnauthorizedError(msg string)` — 401
- `NewBadRequestError(msg string)` — 400
- `NewValidationError(msg string)` — 422
- Each has `.Code`, `.Category`, `.Message`, `.StatusCode()` fields
### GORM/ORM Patterns
- Use `BaseModel` to embed `ID`, `UUID`, `CreatedAt`, `UpdatedAt`, `DeletedAt`
- Tag columns with `gorm` and `json` tags
- `many2many` relationships use `gorm:"many2many:table_name;"`
- Always scope queries to tenant schema via `middleware.GetTenantDB(c *gin.Context)` returning `*gorm.DB` with `SchemaTablePrefix`
- List queries always capped with page limit, default 100, max 1000
- Multi-statement `db.Exec()` forbidden — break into individual calls
- Use `Select(...)` to scope updates (avoid many2many join tables)
- Parameterized queries always via GORM — never `fmt.Sprintf` for SQL
### Middleware Patterns
- `GetTenantDB(c *gin.Context)` — returns schema-scoped `*gorm.DB`
- `GetRole(c *gin.Context)` — returns role string from JWT context
- `requireAdminOrAbove(c *gin.Context) bool` — role guard in handlers (sends 403 if unauthorized)
### Context Propagation
### Logging
### Configuration
- `internal/config/` — loads from env vars via `os.Getenv`, validated at startup
- `.env` file at `backend/.env`
- `DSN()` uses `net/url` for safe DSN construction
- No hardcoded secrets
### Tests
### Common Go Anti-Patterns (Forbidden)
## TypeScript/React Conventions
### Component Patterns
### Route Structure (TanStack Router)
### Hooks and API Client
- Single fetch-based client with Bearer token auth
- Automatic 401 → refresh → retry
- Methods: `api.get<T>()`, `api.post()`, `api.put()`, `api.delete()`
- Returns typed response: `ApiEnvelope<T>` with `{ success, data, error, meta }`
### Form Patterns (react-hook-form + Zod)
### UI Component Library
- **shadcn/ui** components in `src/components/ui/` (client components)
- Icons from `lucide-react`
- Toast notifications via `sonner`
- Tables via `@tanstack/react-virtual` and custom `DataTable` component
### Custom Hooks Pattern
- `useTimetable()` — fetches timetable entries
- `useSchool()` / `useSchools()` / `useCreateSchool()` — school CRUD
- `useSessions()` — academic sessions
- `useSubjects()` — school subjects
- `useClasses()` — class/level data
### Styling (Tailwind CSS)
- Use `cn()` utility (`clsx` + `tailwind-merge`) for conditional classes
- shadcn/ui CSS variables for theming (`--primary`, `--muted-foreground`, etc.)
- `text-muted-foreground` for secondary text
- `animate-spin` for loading states
### Imports Organization
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## High-Level Architecture
- **Frontend**: React 19 + Vite + TanStack Router (file-based client-side routing) + TanStack React Query + Zustand + shadcn/ui
- **Backend**: Go 1.26+ / Gin web framework / GORM v1.31.2 / pgx v5 PostgreSQL driver
- **Cache & Queue**: Redis (tenant context cache, rate limiting, asynq task queue)
- **Database**: Single PostgreSQL instance with **schema-per-tenant** isolation
- **AI**: Gemini/OpenAI provider integration with Qdrant vector store for RAG
### Multi-Tenant Architecture
| Component | Location | Scope |
|-----------|----------|-------|
| `User` (users table) | `public` schema | Shared across all tenants |
| School-specific models (Teacher, Student, Score, Subject, etc.) | `school_{id}` schema | Per-tenant |
| Tenant config, plans, features | `public` schema | Shared, but resolved per-request |
### Project Technology Stack
| Component | Technology |
|-----------|-----------|
| Backend runtime | Go 1.26.1 |
| HTTP framework | Gin v1.12.0 |
| ORM | GORM v1.31.2 |
| DB driver | pgx v5 (via GORM postgres driver) |
| Cache | Redis (go-redis v9) |
| Auth | JWT (golang-jwt v5) + CSRF nonce |
| Background jobs | Asynq (hibiken/asynq) |
| AI providers | Gemini (google.golang.org/genai) + OpenAI (openai-go) |
| Vector store | Qdrant |
| Telemetry | OpenTelemetry (OTLP) |
| Monitoring | Prometheus metrics |
| Documentation | Swagger/OpenAPI |
| Storage | Local filesystem or S3-compatible |
| Communication | SendGrid (email) + Twilio (SMS) |
## Key Architectural Patterns
### Modular Monolith
```
```
### Schema-Per-Tenant Isolation Layers
### Middleware Chain (Order Matters)
```
```
```
```
### Dependency Injection
- All repositories, services, handlers are constructed manually
- Shared infrastructure (DB, Redis, queue, AI provider) passed as dependencies
- `Handlers` struct holds all handler references
- `NewRouter()` function builds everything and returns `*gin.Engine`
### Background Task Queue (Asynq)
- `client.go` — Queue client for enqueueing tasks
- `worker.go` — Background worker goroutine started in `setup.go`
- `tasks.go` — Task type constants and payload types
- `handlers/` — Task handler implementations (email, SMS, backup, restore, report gen, AI scoring)
| Task Type | Handler | Purpose |
|-----------|---------|---------|
| `email:send` | `EmailTaskHandler` | SendGrid email delivery |
| `sms:send` | `SMSTaskHandler` | Twilio SMS delivery |
| `report:generate` | Inline handler | PDF report generation |
| `ai:scoring` | Inline handler | AI-powered applicant scoring |
| `backup:create` | `BackupTaskHandler` | S3 tenant backup |
| `restore:execute` | `RestoreTaskHandler` | S3 tenant restore |
## Data Flows
### Tenant Resolution Flow
```
```
- `backend/internal/middleware/auth.go` — `JWTAuth()`
- `backend/internal/middleware/schoolid.go` — `SchoolID()`
- `backend/internal/middleware/tenant.go` — `TenantResolution()`, `TenantDBResolver()`
- `backend/internal/database/tenant/resolution_service.go` — `TenantResolutionService.ResolveTenant()`
- `backend/internal/database/tenant/schema_db.go` — `SchemaDB.DB()` and `SchemaTablePrefix` plugin
- `backend/internal/database/tenant/factory.go` — `RepositoryFactory.ForSchool()`
### Authentication Flow
```
```
- `backend/internal/middleware/auth.go` — JWT validation, Redis blacklist check
- `backend/internal/middleware/csrf.go` — HMAC-SHA256 stateless CSRF token
- `backend/internal/modules/auth/service.go` — Login, Register, Logout, RefreshToken
- `backend/internal/modules/auth/handler.go` — HTTP handlers
- `backend/pkg/jwt/service.go` — Token creation and validation
### School Provisioning Flow
```
```
- `backend/internal/database/tenant/provisioning.go` — `ProvisioningService`
- `backend/internal/database/tenant/migration_service.go` — `MigrationService`
- `backend/internal/modules/school/service.go` — `SchoolService.Create()`
- `backend/internal/database/migrations/school/school.go` — Default seed data
### Admission Application Flow
```
```
- `backend/internal/modules/admission/handler.go` — Public + admin admission routes
- `backend/internal/modules/admission/service.go` — Business logic
- `backend/internal/modules/admission/repository.go` — DB operations
## Layers
### Transport Layer (HTTP)
- **Location**: `backend/internal/modules/*/handler.go`
- **Responsibility**: Parse HTTP requests, validate input, call service, return JSON responses
- **Depends on**: Services, DTOs
- **Pattern**: Each handler method is a `gin.HandlerFunc` registered in `router.go`
### Business Logic Layer
- **Location**: `backend/internal/modules/*/service.go`
- **Responsibility**: Business rules, orchestration, cross-cutting concerns, error handling
- **Depends on**: Repositories, other services, infrastructure (queue, storage, etc.)
- **Pattern**: Struct with methods, dependencies injected via constructor
### Data Access Layer
- **Location**: `backend/internal/modules/*/repository.go`
- **Responsibility**: GORM queries, data persistence, transactional boundaries
- **Depends on**: `*gorm.DB` (tenant-scoped or core), models
- **Pattern**: Struct with methods, one per aggregate/model
### Infrastructure Layer
- **Database**: `backend/internal/database/` — connections, migrations, models, tenant infrastructure
- **Middleware**: `backend/internal/middleware/` — CORS, CSRF, Auth, Tenant, Rate limit, etc.
- **Queue**: `backend/internal/queue/` — Asynq client, worker, task definitions
- **Communication**: `backend/internal/communication/` — SendGrid/Twilio providers
- **AI**: `backend/internal/ai/` — Provider abstraction, agents, RAG pipeline, vector store
- **WebSocket**: `backend/internal/ws/` — Hub, connections, rooms
## Module Map
| Module | Package | Responsibility |
|--------|---------|----------------|
| Academic | `academic/` | Academic sessions, curriculum, assessments, grade items, attendance |
| Admission | `admission/` | Intake management, applications, document review, offers, enrollment |
| AI | `ai/` | Chat endpoint, agent listing, NL search |
| Alumni | `alumni/` | Alumni records, events, mentorships, campaigns, donations, jobs |
| Analytics | `analytics/` | Dashboard overview, enrollment/revenue/academic/attendance analytics, forecasts |
| Audit | `audit/` | Audit log listing |
| Auth | `auth/` | Register, login, logout, 2FA, session management, password reset |
| Bill | `bill/` | Billing CRUD |
| Career | `career/` | Career profiles, assessments, recommendations |
| CBA | `cba/` | Computer-Based Assessment — questions, papers, exams, proctoring |
| Communication | `communication/` | Templates, campaigns, broadcast, delivery logs |
| Dashboard | `dashboard/` | Dashboard stats |
| Exam | `exam/` | Exam schedules and results |
| Finance | `finance/` | Chart of accounts, journal entries, budgets, expenses, vendors |
| Health | `health/` | Health check endpoints (`/health`, `/livez`, `/readyz`, `/startupz`) |
| Hostel | `hostel/` | Hostel and bed management |
| HR | `hr/` | Departments, staff, leaves, payroll, attendance, appraisals, recruitment |
| Inventory | `inventory/` | Asset categories, assets, assignments, maintenance |
| Invitation | `invitation/` | User invitations |
| Library | `library/` | Books, issues, returns |
| LMS | `lms/` | Courses, modules, lessons, assignments, discussions |
| Messages | `messages/` | Internal messaging |
| Multimedia | `multimedia/` | File uploads and media management |
| Notifications | `notifications/` | In-app notifications |
| Parent Dashboard | `parentdashboard/` | Parent-specific dashboard, child progress/attendance/fees |
| Pastoral | `pastoral/` | Wellness surveys, alerts, counseling sessions |
| Payment | `payment/` | Payment CRUD |
| Proctoring | `proctoring/` | Webcam proctoring events |
| RBAC | `rbac/` | Role-based access control service |
| Report Builder | `reportbuilder/` | Custom report configs, generation, export, scheduling |
| Report Card | `reportcard/` | Report card generation, templates, batch generation |
| Reports | `reports/` | Predefined report listing and generation |
| Result | `result/` | Academic results, approval workflow |
| School | `school/` | School CRUD, subjects, levels, roles |
| Score | `score/` | Grade item scores, bulk save, rollup, export |
| Tenant | `tenant/` | Tenant config and feature management |
| Timetable | `timetable/` | Timetable CRUD, bulk create, calendar view |
| Transport | `transport/` | Routes, vehicles, assignments |
| User | `user/` | User CRUD, student/teacher/staff management, batch import |
## Error Handling
- `backend/internal/errors/errors.go` — `AppError` with code, message, HTTP status category
- `backend/internal/middleware/error.go` — Catches `c.Errors`, maps `AppError` to JSON responses
- `backend/pkg/response/` — Helper functions: `response.Error()`, `response.Success()`, `response.Unauthorized()`, etc.
- Log-and-continue pattern for non-critical analytics/report queries (best-effort)
- Error return for state-mutating operations
## Cross-Cutting Concerns
## Entry Points
| Entry Point | File | Purpose |
|-------------|------|---------|
| Server | `backend/cmd/server/main.go` | Config load → DB/Redis connect → migrations → router → HTTP server |
| Schema migrator | `backend/cmd/migrate-schemas/main.go` | Schema migration utility tool |
| Data copy | `backend/cmd/copy-tenant-data/main.go` | Legacy data migration tool |
| Frontend | `frontend/src/main.tsx` | React app bootstrap with TanStack Router + Query |
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
