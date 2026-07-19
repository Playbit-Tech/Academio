# Codebase Structure

**Analysis Date:** 2026-07-18

## Top-Level Layout

```
academio/
├── backend/           # Go API server (modular monolith)
├── frontend/          # React 19 + Vite + TanStack Router SPA
├── .planning/         # GSD planning artifacts (generated, not committed)
├── docs/              # Architecture docs, plans, PRDs
├── AGENTS.md          # Master agent instructions for the codebase
├── README.md          # Project overview
└── .github/           # CI workflows
```

---

## Backend Structure (`backend/`)

```
backend/
├── cmd/
│   ├── server/
│   │   ├── main.go              # Entry point: config → DB → Redis → migrations → router → HTTP server
│   │   └── docs/                # Swagger-generated documentation
│   ├── migrate-schemas/         # Schema migration utility (standalone CLI)
│   │   └── main.go
│   └── copy-tenant-data/        # Legacy tenant data copy tool
│       └── main.go
│
├── internal/
│   ├── config/
│   │   ├── config.go            # Config struct + env-based loading
│   │   ├── config_test.go
│   │   └── communication.go     # Email/SMS communication config
│   │
│   ├── database/
│   │   ├── postgres.go          # MustConnect() — PostgreSQL connection with retry
│   │   ├── redis.go             # ConnectRedis() — Redis client
│   │   │
│   │   ├── migrations/
│   │   │   ├── migrations.go    # Migration runner (core + school wrapper)
│   │   │   ├── migrator.go      # ReusableMigrator — tracks applied migrations
│   │   │   ├── types.go         # Migration type definitions
│   │   │   ├── core/            # Public schema migrations
│   │   │   │   ├── core.go, core_tables.go
│   │   │   │   ├── rbac.go, auth_tokens.go
│   │   │   │   ├── uuid_columns.go, validation_tokens.go
│   │   │   │   ├── avatar.go, s3_path.go, schema_name.go
│   │   │   │   ├── tenant_connections.go, totp_settings.go
│   │   │   │   ├── pg_trgm.go, read_source.go
│   │   │   │   └── ...
│   │   │   └── school/          # Tenant schema migrations
│   │   │       └── school.go    # All school-scoped tables + seed data
│   │   │
│   │   ├── models/              # GORM model structs (1 per file)
│   │   │   ├── base.go          # BaseModel (ID, timestamps)
│   │   │   ├── user.go          # User (public schema)
│   │   │   ├── school.go        # School, SchoolConnection (public schema)
│   │   │   ├── tenant.go        # TenantConfig
│   │   │   ├── multitenant.go   # Multi-tenant base model
│   │   │   ├── schema.go        # SchemaName model
│   │   │   ├── admission.go, assessment.go, attendance.go
│   │   │   ├── curriculum.go, score.go, grade_item.go
│   │   │   ├── cba.go, exam.go, result.go
│   │   │   ├── hr.go, finance.go, payment.go
│   │   │   ├── lms.go, library.go, career.go
│   │   │   ├── session.go, analytics.go
│   │   │   ├── communication.go, audit_log.go
│   │   │   ├── enums.go, interfaces.go
│   │   │   └── ...
│   │   │
│   │   ├── tenant/              # Schema-per-tenant infrastructure
│   │   │   ├── schema_db.py     → Actually: schema_db.go  # SchemaDB wrapper + SchemaTablePrefix GORM plugin
│   │   │   ├── factory.go       # RepositoryFactory — creates tenant-scoped repos
│   │   │   ├── tenant_context.go     # TenantContext struct + cache keys
│   │   │   ├── resolution_service.go # TenantResolutionService — resolve tenant from DB, cache in Redis
│   │   │   ├── connection_manager.go # Legacy connection manager (kept for backward compat)
│   │   │   ├── provisioning.go       # ProvisioningService — schema creation + seeding
│   │   │   ├── migration_service.go  # MigrationService — run migrations on tenant schema
│   │   │   ├── dual_write.go         # Dual-write support for migration
│   │   │   ├── config.go            # Tenant DB config (DSN with net/url)
│   │   │   ├── factory_test.go, integration_test.go, isolation_test.go
│   │   │   └── ...
│   │   │
│   │   └── uuid/                # UUID generation utilities
│   │       ├── uuid.go
│   │       └── uuid_test.go
│   │
│   ├── middleware/              # Gin middleware (1 per file)
│   │   ├── auth.go              # JWTAuth — JWT validation + Redis blacklist check
│   │   ├── auth_test.go
│   │   ├── schoolid.go          # SchoolID — extract x-school-id header
│   │   ├── schoolid_test.go
│   │   ├── tenant.go            # TenantResolution, TenantDBResolver, feature gating
│   │   ├── tenant_test.go
│   │   ├── cors.go              # CORS — origin whitelist
│   │   ├── csrf.go              # CSRF — HMAC nonce-based token validation
│   │   ├── ratelimit.go         # RateLimit — in-memory
│   │   ├── ratelimit_redis.go   # RedisRateLimit — Redis-backed sliding window
│   │   ├── ratelimit_test.go
│   │   ├── audit.go             # AuditLogging — async audit log writer
│   │   ├── error.go             # ErrorHandler — domain errors → JSON responses
│   │   ├── error_test.go
│   │   ├── logger.go            # Logger — structured request logging
│   │   ├── requestid.go         # RequestID — X-Request-ID propagation
│   │   ├── requestid_test.go
│   │   ├── security.go          # SecurityHeaders — HSTS, CSP, X-Frame-Options, etc.
│   │   ├── security_test.go
│   │   ├── bodylimit.go         # BodyLimit — request body size constraint
│   │   ├── tracing.go           # Tracing — OpenTelemetry
│   │   ├── validate.go          # Validate — request validation
│   │   └── recovery.go          # Recovery — panic recovery (part of Gin)
│   │
│   ├── modules/                 # Feature modules (39 total)
│   │   │                        # Each module typically has:
│   │   │                        #   handler.go   — HTTP routes
│   │   │                        #   service.go   — Business logic
│   │   │                        #   repository.go — Data access
│   │   │                        #   dto.go       — Request/response types
│   │   │                        #   *_test.go    — Tests
│   │   │
│   │   ├── academic/            # Sessions, curriculum, assessments, grade items, attendance
│   │   ├── admission/           # Intakes, applications, forms, offers, enrollment
│   │   ├── ai/                  # AI chat handler
│   │   ├── alumni/              # Alumni records, events, careers, donations, jobs
│   │   ├── analytics/           # Dashboard analytics, snapshots, forecasts
│   │   ├── audit/               # Audit log listing
│   │   ├── auth/                # Registration, login, 2FA, password reset, session management
│   │   ├── bill/                # Billing CRUD
│   │   ├── career/              # Career profiles, assessments, recommendations
│   │   ├── cba/                 # CBA questions, papers, exams, grading, proctoring
│   │   ├── communication/       # Templates, campaigns, broadcast, delivery logs
│   │   ├── dashboard/           # Dashboard stats
│   │   ├── exam/                # Exam schedules and results
│   │   ├── finance/             # Chart of accounts, journal entries, budgets, expenses
│   │   ├── health/              # Health check endpoints
│   │   ├── hostel/              # Hostel and bed management
│   │   ├── hr/                  # HR — departments, staff, payroll, leaves, appraisals, recruitment
│   │   ├── inventory/           # Asset categories, assets, assignments, maintenance
│   │   ├── invitation/          # User invitations
│   │   ├── library/             # Books, issues, returns
│   │   ├── lms/                 # Courses, modules, lessons, assignments, discussions
│   │   ├── messages/            # Internal messaging
│   │   ├── multimedia/          # File uploads and media
│   │   ├── notifications/       # In-app notifications
│   │   ├── parentdashboard/     # Parent dashboard, child monitoring
│   │   ├── pastoral/            # Wellness surveys, alerts, counseling
│   │   ├── payment/             # Payment CRUD
│   │   ├── proctoring/          # Webcam proctoring events
│   │   ├── rbac/                # Role-based access control
│   │   ├── reportbuilder/       # Custom report config and generation
│   │   ├── reportcard/          # Report card generation and templates
│   │   ├── reports/             # Predefined report listing
│   │   ├── result/              # Academic results and approval workflow
│   │   ├── school/              # School CRUD, subjects, levels, roles
│   │   ├── score/               # Grade item scores, bulk operations, export
│   │   ├── tenant/              # Tenant config and feature management
│   │   ├── timetable/           # Timetable CRUD, bulk create, calendar
│   │   ├── transport/           # Routes, vehicles, assignments
│   │   └── user/                # User CRUD, student/teacher/staff, batch import
│   │
│   ├── ai/                      # AI infrastructure (not a module, but internal service)
│   │   ├── agents/              # Specialized AI agents (tutor, assistant, forecaster, etc.)
│   │   │   ├── base.go          # Agent interface
│   │   │   ├── runner.go        # Agent runner — dispatches to agents
│   │   │   ├── tool.go          # Agent tool definitions
│   │   │   └── various agents
│   │   ├── conversation/        # Conversation store
│   │   ├── rag/                 # RAG pipeline: chunker, embedder, vector store
│   │   ├── vector/              # Qdrant vector store client
│   │   ├── search/              # Natural language search engine
│   │   ├── gateway.go           # AI provider abstraction
│   │   ├── gemini.go            # Gemini provider implementation
│   │   ├── openai.go            # OpenAI provider implementation
│   │   ├── model_router.go      # Model routing logic
│   │   ├── config.go            # AI configuration
│   │   ├── cost.go              # Cost tracking
│   │   ├── circuit_breaker.go   # Circuit breaker for API calls
│   │   ├── metrics.go           # Prometheus metrics
│   │   └── tracing.go           # OpenTelemetry spans
│   │
│   ├── communication/           # External communication providers
│   │   ├── email.go             # Email provider interface
│   │   ├── sms.go               # SMS provider interface
│   │   ├── provider.go          # Provider factory
│   │   ├── sendgrid.go          # SendGrid implementation
│   │   └── twilio.go            # Twilio implementation
│   │
│   ├── queue/                   # Asynq background task queue
│   │   ├── client.go            # QueueClient — enqueue tasks
│   │   ├── worker.go            # QueueWorker — process tasks
│   │   ├── tasks.go             # Task type constants + payload structs
│   │   ├── tasks_test.go
│   │   ├── config.go            # Queue configuration
│   │   ├── metrics.go           # Queue Prometheus metrics
│   │   └── handlers/            # Task handler implementations
│   │       ├── email_task.go
│   │       ├── sms_task.go
│   │       ├── backup_task.go
│   │       └── restore_task.go
│   │
│   ├── ws/                      # WebSocket infrastructure
│   │   ├── hub.go               # WebSocket hub (connection management)
│   │   ├── connection.go        # WebSocket connection wrapper
│   │   ├── auth.go              # WebSocket auth (token upgrade)
│   │   ├── router.go            # Message routing
│   │   ├── room.go              # Room management
│   │   └── metrics.go           # Prometheus metrics
│   │
│   ├── services/                # Shared application services
│   │   ├── token_service.go     # Refresh token caching + management
│   │   └── cache_service.go     # General Redis cache operations
│   │
│   ├── helpers/                 # Shared utility functions
│   │   ├── helpers.go           # General helpers
│   │   ├── errors.go            # Error mapping helpers
│   │   ├── id.go                # ID generation
│   │   ├── id_test.go
│   │   └── tx.go                # Transaction helper
│   │
│   ├── errors/                  # Domain error types
│   │   ├── errors.go            # AppError struct, error codes, categories
│   │   └── errors_test.go
│   │
│   ├── crypto/                  # Cryptographic utilities
│   │   ├── encryption.go        # AES-256-GCM encryption
│   │   ├── encryption_test.go
│   │   └── security_test.go
│   │
│   ├── telemetry/               # OpenTelemetry setup
│   │   └── ...                  # Tracer provider, GORM plugin, Redis hook
│   │
│   ├── backup/                  # Backup service
│   │   ├── service.go
│   │   ├── errors.go
│   │   └── service_test.go
│   │
│   └── restore/                 # Restore service
│       └── ...
│
├── pkg/                        # Shared libraries (may be extracted later)
│   ├── jwt/service.go          # JWT token creation + validation
│   ├── logger/                 # Structured logging (slog wrapper)
│   ├── response/               # HTTP response helpers
│   ├── storage/                # Storage abstraction (local + S3)
│   │   ├── driver.go           # Storage interface
│   │   ├── local.go            # Local filesystem
│   │   ├── s3.go               # S3-compatible
│   │   └── s3_backup.go        # S3 backup storage
│   ├── password/               # Password hashing + validation
│   ├── pdf/                    # PDF generation (HTML→PDF)
│   ├── totp/                   # TOTP implementation
│   └── validator/              # Custom validators
│
├── scripts/                    # Shell scripts for dev/test
│   ├── test_endpoint.sh        # Integration test suite (40 tests)
│   ├── migrate/main.go         # Migration runner script
│   ├── seed/main.go            # Database seed script
│   └── ...
│
├── deploy/                     # Deployment configurations
│   ├── k8s/                    # Kubernetes manifests (Kustomize)
│   │   ├── base/               # Base deployment, service, HPA, PDB, ingress
│   │   └── overlays/           # Production and staging overlays
│   ├── deployment-guide.md
│   └── runbooks.md
│
├── benchmarks/                 # Performance benchmarks
│   └── tenant_routing_bench_test.go
│
├── api/                        # API compatibility tests
│   └── compatibility_test.go
│
├── Makefile                    # Build, test, migrate, deploy commands
├── go.mod / go.sum             # Go module definitions
├── Dockerfile                  # Container build
├── docker-compose.yml          # Local dev services (PostgreSQL + Redis)
├── STYLE.md                    # Go coding conventions
├── TESTING.md                  # Testing patterns and guidelines
└── .air.toml                   # Air hot-reload config
```

---

## Frontend Structure (`frontend/`)

```
frontend/
├── src/
│   ├── main.tsx                # Entry point: TanStack Router + QueryClient setup
│   ├── routeTree.gen.ts        # Auto-generated route tree (TanStack Router)
│   ├── globals.css             # Global CSS + Tailwind imports
│   │
│   ├── routes/                 # TanStack Router file-based routes
│   │   ├── __root.tsx          # Root layout (Sonner Toaster, theme provider)
│   │   ├── _dashboard/         # Authenticated dashboard layout pages
│   │   │   ├── _dashboard.tsx  # Dashboard layout wrapper
│   │   │   ├── dashboard.tsx   # Main dashboard page
│   │   │   ├── academics.tsx   # Academic sessions, curriculum, assessments
│   │   │   ├── attendance.tsx   # Student attendance (roll-call + records)
│   │   │   ├── timetable.tsx   # Timetable (weekly/daily/events/calendar editor)
│   │   │   ├── users.tsx       # User management (student/teacher/staff)
│   │   │   ├── school.tsx      # School settings, subjects, levels
│   │   │   ├── admissions/     # Admin admission management pages
│   │   │   ├── analytics/      # Analytics dashboard pages
│   │   │   ├── communication/  # Communication templates, campaigns
│   │   │   ├── reports/        # Reports and report builder
│   │   │   ├── report-cards/   # Report card management
│   │   │   ├── lms/            # LMS course pages
│   │   │   ├── finance.tsx, hr.tsx, hostel.tsx, library.tsx
│   │   │   ├── inventory.tsx, transport.tsx, pastoral.tsx
│   │   │   ├── exams.tsx, cba.tsx, cba.exams.*.tsx
│   │   │   ├── alumni/, alumni.tsx, career.tsx
│   │   │   ├── messages.tsx, notifications.tsx
│   │   │   ├── parent/         # Parent dashboard pages
│   │   │   ├── teacher.*.tsx   # Teacher-specific pages
│   │   │   └── settings.tsx, profile.tsx, change-password.tsx
│   │   ├── _public/            # Public/pages (landing, about, terms, etc.)
│   │   │   ├── _public.tsx     # Public layout wrapper
│   │   │   ├── index.tsx       # Landing page
│   │   │   ├── admissions/     # Public admission forms
│   │   │   └── about.tsx, schools.tsx, privacy.tsx, etc.
│   │   ├── _onboarding/        # School onboarding flow
│   │   ├── _super/             # Super admin pages
│   │   ├── login.tsx, register.tsx, forgot-password.tsx
│   │   ├── reset-password.tsx, confirm-email.tsx
│   │   └── ...
│   │
│   ├── components/             # Reusable UI components
│   │   ├── ui/                 # shadcn/ui primitives
│   │   │   ├── button.tsx, card.tsx, dialog.tsx, sheet.tsx
│   │   │   ├── data-table.tsx, form.tsx, input.tsx, select.tsx
│   │   │   ├── tabs.tsx, table.tsx, badge.tsx, avatar.tsx
│   │   │   ├── popover.tsx, alert-dialog.tsx, dropdown-menu.tsx
│   │   │   ├── sonner.tsx (Sonner toast wrapper)
│   │   │   └── ...
│   │   ├── layout/             # Dashboard layout components
│   │   │   ├── dashboard-layout.tsx, sidebar.tsx, header.tsx
│   │   │   ├── main.tsx, breadcrumbs.tsx, user-dropdown.tsx
│   │   │   └── notifications-center.tsx
│   │   ├── admissions/        # Admission workflow components
│   │   ├── dashboard/          # Dashboard widgets (stats-card, quick-actions, etc.)
│   │   ├── academics/          # Score grid, curriculum form
│   │   ├── timetable/          # Calendar grid, bulk toolbar
│   │   ├── users/              # User forms, view sheets
│   │   ├── template-builder/   # Report card template editor
│   │   ├── auth-layout.tsx, theme-provider.tsx, theme-toggle.tsx
│   │   └── student-profile-card.tsx
│   │
│   ├── lib/                    # Shared library code
│   │   ├── api.ts              # Fetch-based API client with Bearer auth + 401 refresh
│   │   ├── utils.ts            # Tailwind merge, classname utilities
│   │   ├── auth/               # Auth provider, use-auth hook, protected routes
│   │   ├── stores/             # Zustand stores
│   │   │   ├── auth-store.ts   # Auth state (tokens, user, schools)
│   │   │   ├── notification-store.ts
│   │   │   └── sidebar-store.ts
│   │   └── hooks/              # TanStack Query hooks (1 per module)
│   │       ├── useSchool.ts, useUsers.ts, useAcademics.ts
│   │       ├── useTimetable.ts, useDashboard.ts
│   │       ├── useFinance.ts, useHR.ts, useInventory.ts
│   │       ├── useAdmissions.ts, useCBA.ts, useAlumni.ts
│   │       └── ... (35+ hook files)
│   │
│   ├── types/                  # TypeScript type declarations
│   │   └── naija-states.d.ts
│   │
│   └── __tests__/              # Component/hook unit tests (Vitest)
│       ├── button.test.tsx, data-table.test.tsx
│       ├── stats-card.test.tsx, export-csv.test.tsx
│       └── various hook tests
│
├── e2e/                        # Playwright E2E tests
│   ├── auth-smoke.spec.ts
│   └── navigation-smoke.spec.ts
│
├── .prettierrc                 # Prettier config
├── components.json             # shadcn/ui config
├── eslint.config.mjs           # ESLint flat config
├── tailwind.config.js          # Tailwind CSS config
├── vite.config.ts              # Vite config (dev server proxy to :8080)
├── vitest.config.ts            # Vitest config
├── tsconfig.json               # TypeScript config
├── vercel.json                 # Vercel deployment config
├── postcss.config.mjs          # PostCSS config
├── package.json                # Node dependencies (Yarn 4)
├── yarn.lock                   # Yarn lockfile
├── .yarnrc.yml                 # Yarn 4 config
└── playwright.config.ts        # Playwright config
```

---

## Naming Conventions

**Go Backend:**
- **Files**: `snake_case.go` — one file per major type/concern (e.g., `service.go`, `handler.go`, `dto.go` within a module)
- **Packages**: Single-word lowercase (e.g., `auth`, `user`, `school`, `tenant`)
- **Types**: PascalCase (e.g., `AuthHandler`, `UserService`, `TenantContext`)
- **Functions**: PascalCase for exported, camelCase for unexported
- **Tests**: `*_test.go` — co-located with source file (Go convention)

**Frontend (TypeScript/React):**
- **Files**: `kebab-case.tsx` for components, `camelCase.ts` for utilities
- **Components**: PascalCase (e.g., `DataTable`, `StatsCard`, `DashboardLayout`)
- **Hooks**: `camelCase` with `use` prefix (e.g., `useSchool`, `useTimetable`)
- **Stores**: `kebab-case-store.ts` (e.g., `auth-store.ts`, `sidebar-store.ts`)
- **Routes**: `kebab-case.tsx` matching URL path structure

---

## Key File Locations

| Purpose | Backend | Frontend |
|---------|---------|----------|
| Entry point | `backend/cmd/server/main.go` | `frontend/src/main.tsx` |
| Router setup | `backend/internal/router/setup.go` + `router.go` | `frontend/src/routeTree.gen.ts` (auto-generated) |
| Config | `backend/internal/config/config.go` | Vite env vars (`VITE_*`) |
| DB connection | `backend/internal/database/postgres.go` | — (API calls only) |
| Models | `backend/internal/database/models/` | `frontend/src/lib/api.ts` (ApiEnvelope type) |
| Middleware | `backend/internal/middleware/` | `frontend/src/lib/auth/` (auth provider) |
| Tenant infra | `backend/internal/database/tenant/` | — |
| API client | — | `frontend/src/lib/api.ts` |
| React Query hooks | — | `frontend/src/lib/hooks/` (35+ files) |
| Zustand stores | — | `frontend/src/lib/stores/` |
| UI components | — | `frontend/src/components/ui/` (shadcn) |
| Tests | `*_test.go` co-located | `frontend/src/__tests__/` |
| E2E tests | `backend/scripts/test_endpoint.sh` | `frontend/e2e/` |
| Deployment | `backend/deploy/k8s/` | `frontend/vercel.json` |

---

## Where to Add New Code

### New Feature Module (Backend)

1. Create directory: `backend/internal/modules/<name>/`
2. Create files in this order:
   - `dto.go` — Request/response structs
   - `repository.go` — Data access methods (GORM)
   - `service.go` — Business logic
   - `handler.go` — HTTP handlers (Gin)
   - `*_test.go` — Tests
3. Register route in `backend/internal/router/router.go` using `authGroup()` helper
4. Wire dependencies in `backend/internal/router/setup.go` (repo → service → handler)
5. Add model to models directory if needed: `backend/internal/database/models/<name>.go`

### New Feature Page (Frontend)

1. Add route file: `frontend/src/routes/_dashboard/<name>.tsx`
2. Add components: `frontend/src/components/<name>/`
3. Add TanStack Query hooks: `frontend/src/lib/hooks/use<Name>.ts`
4. Update API client if new endpoints needed: `frontend/src/lib/api.ts`

### New GORM Model

1. Add model file: `backend/internal/database/models/<name>.go`
2. Add migration: `backend/internal/database/migrations/school/school.go` (tenant schema) or `backend/internal/database/migrations/core/` (public schema)
3. Add migration registration in the appropriate `CoreMigrations()` or `SchoolMigrations()` list

### New Middleware

1. Add file: `backend/internal/middleware/<name>.go`
2. Register in middleware chain in `backend/internal/router/router.go` global chain or per-route

---

## Directory Purposes (backend/internal/)

| Directory | Purpose |
|-----------|---------|
| `config/` | Environment-based configuration loading |
| `database/` | DB connections, migrations, GORM models, tenant infrastructure |
| `middleware/` | HTTP middleware (auth, CORS, CSRF, rate limit, tenant, etc.) |
| `modules/` | Feature modules (39 total) — each is a bounded context |
| `ai/` | AI provider abstraction, agent system, RAG pipeline, vector search |
| `communication/` | Email/SMS provider abstraction (SendGrid, Twilio) |
| `queue/` | Asynq background task queue infrastructure |
| `ws/` | WebSocket hub and connection management |
| `services/` | Shared cross-cutting services (token caching, etc.) |
| `helpers/` | General-purpose utility functions |
| `errors/` | Domain error types and error codes |
| `crypto/` | Encryption utilities |
| `telemetry/` | OpenTelemetry initialization |
| `backup/` | Backup service (schema-aware pg_dump + S3) |
| `restore/` | Restore service (S3 download + pg_restore) |

---

## Special Directories

| Directory | Purpose | Generated | Committed |
|-----------|---------|-----------|-----------|
| `frontend/src/routeTree.gen.ts` | Auto-generated TanStack Router tree | Yes | Yes |
| `frontend/.tanstack/` | Router build temp files | Yes | No |
| `backend/tmp/` | Air hot-reload binary output | Yes | No |
| `backend/coverage.out/html` | Test coverage reports | Yes | No |
| `backend/bin/` | Compiled Go binary | Yes | No |
| `.planning/` | GSD planning artifacts | Yes | No |
| `.tmp/` | Session context files | Yes | No |

---

## Module Standard File Pattern

Every module under `backend/internal/modules/<name>/` follows this convention:

```
<name>/
├── dto.go              # Request/response DTOs (input/output structs)
├── handler.go          # Gin HTTP handlers (request parsing, response writing)
├── service.go          # Business logic layer
├── repository.go       # GORM data access methods
├── *_test.go           # Tests (service tests, mock repos)
└── mock_repository_test.go  # Mock implementations for testing (when needed)
```

The dependency chain is: `handler → service → repository`. Dependencies are injected via constructor functions (e.g., `NewXxxService(repo)`, `NewXxxHandler(svc)`).

---

*Structure analysis: 2026-07-18*
