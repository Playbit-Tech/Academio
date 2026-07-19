# Architecture

**Analysis Date:** 2026-07-18

## High-Level Architecture

**Academio** is a multi-tenant school management system delivered as a modular monolith with separate frontend and backend processes.

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

The `SchemaTablePrefix` GORM plugin (`backend/internal/database/tenant/schema_db.go`) automatically prefixes all table names with the tenant schema during GORM operations — a query like `db.Find(&students)` becomes `SELECT * FROM school_42.students`.

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
All Go backend code lives in a single binary (`backend/cmd/server/main.go`) organized into ~39 modules under `backend/internal/modules/`. Each module follows a consistent **Handler → Service → Repository** layered pattern:

```
handler.go  (HTTP concerns: parse request, validate, call service, return response)
      ↓
service.go  (Business logic, orchestration, cross-cutting concerns)
      ↓
repository.go  (Data access, GORM queries, DB interactions)
dto.go  (Request/response types)
```

### Schema-Per-Tenant Isolation Layers

The tenant isolation has three layers, set up in `backend/internal/router/setup.go`:

1. **`tenant.SchemaTablePrefix()` GORM plugin** — registered once at startup on the shared DB connection. All subsequent GORM sessions prefix table names with a schema name passed via session context.

2. **`middleware.TenantResolution()`** — resolves school UUID/ID to `TenantContext` (plan, features, schema name), cached in Redis with 5-minute TTL. Implemented in `backend/internal/database/tenant/resolution_service.go`.

3. **`middleware.TenantDBResolver()`** — creates a per-request `SchemaDB` wrapper that scopes all GORM operations to the tenant's schema. Stored in Gin context as `TenantRepositories` (accessible via `middleware.GetTenantRepos(c)`).

### Middleware Chain (Order Matters)

Defined in `backend/internal/router/router.go` global chain:

```
1. Recovery()           — Panic recovery
2. RequestID()          — X-Request-ID propagation
3. Tracing()            — OpenTelemetry distributed tracing
4. ErrorHandler()       — Catches c.Errors after handler chain
5. Logger()             — Structured request logging
6. SecurityHeaders()    — HSTS, CSP, X-Frame-Options, etc.
7. CORS()               — Origin whitelist
8. BodyLimit()          — Request body size limit
9. SchoolID()           — Extracts x-school-id header (exempts public routes)
```

Per-route middleware (applied via `authGroup()` helper):
```
JWTAuth() → EnforceSchoolID() → TenantResolution() → TenantDBResolver() → AuditLogging()
```

### Dependency Injection

Wiring happens in `backend/internal/router/setup.go`:
- All repositories, services, handlers are constructed manually
- Shared infrastructure (DB, Redis, queue, AI provider) passed as dependencies
- `Handlers` struct holds all handler references
- `NewRouter()` function builds everything and returns `*gin.Engine`

### Background Task Queue (Asynq)

Defined in `backend/internal/queue/`:
- `client.go` — Queue client for enqueueing tasks
- `worker.go` — Background worker goroutine started in `setup.go`
- `tasks.go` — Task type constants and payload types
- `handlers/` — Task handler implementations (email, SMS, backup, restore, report gen, AI scoring)

Task handlers registered in `setup.go`:
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
Request → SchoolID middleware (extracts x-school-id)
       → JWTAuth (validates JWT, extracts school_id from claims)
       → TenantResolution (checks Redis cache → core DB schools table)
       → TenantDBResolver (creates SchemaDB wrapper → stores in context)
       → Handler (calls middleware.GetTenantRepos(c).TenantDB())
```

Key files:
- `backend/internal/middleware/auth.go` — `JWTAuth()`
- `backend/internal/middleware/schoolid.go` — `SchoolID()`
- `backend/internal/middleware/tenant.go` — `TenantResolution()`, `TenantDBResolver()`
- `backend/internal/database/tenant/resolution_service.go` — `TenantResolutionService.ResolveTenant()`
- `backend/internal/database/tenant/schema_db.go` — `SchemaDB.DB()` and `SchemaTablePrefix` plugin
- `backend/internal/database/tenant/factory.go` — `RepositoryFactory.ForSchool()`

### Authentication Flow

```
POST /api/v2/auth/login → AuthHandler.Login → AuthService.Login
  → Validate credentials (bcrypt)
  → Generate JWT access + refresh tokens
  → Store refresh token in Redis
  → Return tokens + user profile

Subsequent requests:
  → Middleware chain applies CSRF (state-changing methods)
  → JWTAuth validates access token, checks Redis blacklist
  → Extract user_id, school_id, role from claims → Gin context
```

Key files:
- `backend/internal/middleware/auth.go` — JWT validation, Redis blacklist check
- `backend/internal/middleware/csrf.go` — HMAC-SHA256 stateless CSRF token
- `backend/internal/modules/auth/service.go` — Login, Register, Logout, RefreshToken
- `backend/internal/modules/auth/handler.go` — HTTP handlers
- `backend/pkg/jwt/service.go` — Token creation and validation

### School Provisioning Flow

```
POST /api/v2/schools (admin) → SchoolHandler.Create → SchoolService.Create
  → Create school record (public schema) with database_status = 'pending'
  → Return school ID

Client polls GET /api/v2/schools/:id until database_status = 'active'

ProvisioningService.ProvisionSchool() [called synchronously in Create handler]:
  1. Generate schema name: "school_{schoolID}"
  2. CREATE SCHEMA IF NOT EXISTS
  3. Store schema_name on school record
  4. Run school migrations inside schema (via SchemaDB)
  5. Create admin UserInfo in tenant schema
  6. Seed default data (levels, subjects, grade items)
  7. Mark school as database_status = 'active'
```

Key files:
- `backend/internal/database/tenant/provisioning.go` — `ProvisioningService`
- `backend/internal/database/tenant/migration_service.go` — `MigrationService`
- `backend/internal/modules/school/service.go` — `SchoolService.Create()`
- `backend/internal/database/migrations/school/school.go` — Default seed data

### Admission Application Flow

```
Public form: POST /api/v2/public/admissions/applications
  → No auth required
  → Creates application record with reference number
  → Optional file upload via documents endpoint

Admin management (authenticated):
  → Screen applications → Record exam results → Create offers
  → Enroll accepted students → Provision user accounts
```

Key files:
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

All modules live under `backend/internal/modules/`:

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

**Strategy**: Domain-specific error types + centralized error middleware

- `backend/internal/errors/errors.go` — `AppError` with code, message, HTTP status category
- `backend/internal/middleware/error.go` — Catches `c.Errors`, maps `AppError` to JSON responses
- `backend/pkg/response/` — Helper functions: `response.Error()`, `response.Success()`, `response.Unauthorized()`, etc.
- Log-and-continue pattern for non-critical analytics/report queries (best-effort)
- Error return for state-mutating operations

## Cross-Cutting Concerns

**Logging**: `backend/pkg/logger/` — slog wrapper with `logger.Infof`, `logger.Warnf`, `logger.Errorf`, `logger.Fatal`

**Validation**: `backend/pkg/validator/` — custom validators; also `go-playground/validator/v10` via Gin binding

**Authentication**: JWT (access + refresh tokens), CSRF nonce tokens, TOTP 2FA, Redis blacklist for revocation

**Rate Limiting**: `backend/internal/middleware/ratelimit.go` — in-memory fallback; `backend/internal/middleware/ratelimit_redis.go` — Redis-backed sliding window

**Audit Logging**: `backend/internal/middleware/audit.go` — async audit logger that writes to `audit_logs` table

**Telemetry**: OpenTelemetry tracing via `backend/internal/telemetry/` with GORM plugin and Redis hook

**Storage Abstraction**: `backend/pkg/storage/` — `Driver` interface with Local and S3 implementations

## Entry Points

| Entry Point | File | Purpose |
|-------------|------|---------|
| Server | `backend/cmd/server/main.go` | Config load → DB/Redis connect → migrations → router → HTTP server |
| Schema migrator | `backend/cmd/migrate-schemas/main.go` | Schema migration utility tool |
| Data copy | `backend/cmd/copy-tenant-data/main.go` | Legacy data migration tool |
| Frontend | `frontend/src/main.tsx` | React app bootstrap with TanStack Router + Query |

---

*Architecture analysis: 2026-07-18*
