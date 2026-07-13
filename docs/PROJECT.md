# SchoolCare v2 → v3 — Project Overview

This document describes the Academio/SchoolCare project — the codebase, architecture, key flows, and conventions. It is a standalone reference independent of any AI tool context.

---

## What It Is

**SchoolCare** is a multi-tenant school management SaaS platform. It covers the complete student lifecycle: prospect → applicant → admission → student → academic progress → graduate → alumni → lifelong engagement.

The v2 codebase is live. The v3 architecture (documented in `docs/architecture/`) describes the target evolution into an AI-native, event-driven platform at 1M+ student scale.

---

## Repository Layout

```
academio/                    # Parent monorepo (git submodule orchestration)
├── README.md               # Quick-start guide
├── AGENTS.md               # Internal AI assistant context (not for human consumption)
├── docs/
│   ├── PROJECT.md          # ← This file
│   ├── architecture/       # 11-doc v3 architecture spec
│   │   ├── 1-VISION-AND-STRATEGY.md
│   │   ├── 2-ARCHITECTURE-OVERVIEW.md
│   │   ├── 3-DATABASE-SCHEMA.md
│   │   ├── 4-API-SPECIFICATIONS.md
│   │   ├── 5-AI-ARCHITECTURE.md
│   │   ├── 6-SECURITY-INFRASTRUCTURE.md
│   │   ├── 7-USE-CASES.md
│   │   ├── 8-FUTURE-EXPANSION.md
│   │   ├── 9-ARCHITECTURAL-STANDARDS.md
│   │   └── 10-AUDIT-CHECKLIST.md
│   ├── audits/             # Code quality & security audits
│   └── plans/              # Implementation plans
├── scripts/
│   └── loadtest/           # k6 load testing scripts
├── backend/                # Git submodule — Go/Gin API server
└── frontend/               # Git submodule — React SPA
```

---

## Technology Stack

### Backend (`backend/`)

| Layer | Technology |
|-------|-----------|
| Language | Go 1.26 |
| Web framework | Gin v1.10 |
| ORM | GORM v1.30 (with pgx v5 driver) |
| Database | PostgreSQL 16 |
| Cache / queue | Redis 7 (asynq for background jobs) |
| Auth | JWT (golang-jwt v5) + refresh token rotation + optional TOTP 2FA |
| AI (via v3 roadmap) | OpenAI + Gemini via `google.ai` SDK, Qdrant vector DB, 10+ agents |
| Queue | Asynq (Redis-backed) for provisioning, email, SMS, backup, AI scoring |
| Telemetry | OpenTelemetry (OTLP), Prometheus metrics |
| Object storage | S3 (AWS SDK v2) or local filesystem |
| Crypto | AES-256-GCM for per-tenant DB credentials |

### Frontend (`frontend/`)

| Layer | Technology |
|-------|-----------|
| Framework | React 19 |
| Build | Vite 8 |
| Routing | TanStack Router v1 (file-based, type-safe) |
| Client state | Zustand v5 (with localStorage persistence) |
| Server state | TanStack React Query v5 |
| UI | shadcn/ui (Radix-based) + Base UI |
| Styling | Tailwind CSS v4 |
| Forms | React Hook Form + Zod v4 |
| Charts | Recharts |
| Package manager | Yarn 4 (via Corepack) |
| E2E tests | Playwright |

---

## Backend Architecture

### Entry Point (`cmd/server/main.go`)

Bootstrap sequence:
1. Load config from environment variables
2. Set log level (slog wrapper via `pkg/logger`)
3. Connect PostgreSQL (GORM + pgx v5, connection pooling)
4. Connect Redis (non-fatal if unavailable)
5. Run core migrations on shared database
6. Build router with dependency injection (39+ handler types)
7. Start HTTP server on `:8080` with graceful shutdown

### Module Structure (`internal/modules/<domain>/`)

Each module follows a layered pattern:
```
handler.go      # Gin HTTP handlers — parse request, call service, return response
service.go      # Business logic
repository.go   # Data access via GORM
dto.go          # Request/response structs
events.go       # Domain event publishers (optional)
```

**39 modules total**, organized by domain:

| Domain | Modules |
|--------|---------|
| Core | `health`, `auth`, `user`, `school`, `rbac` |
| Academic | `academic`, `score`, `result`, `exam`, `timetable` |
| Financial | `bill`, `payment`, `finance` |
| Operations | `multimedia`, `invitation`, `messages`, `notifications` |
| Extended | `admission`, `cba`, `lms`, `library`, `hostel`, `transport`, `inventory`, `pastoral` |
| People | `alumni`, `career`, `hr`, `parentdashboard` |
| Analytics | `analytics`, `reports`, `reportbuilder`, `reportcard`, `dashboard` |
| Infrastructure | `tenant`, `audit`, `communication`, `ai` |

### Middleware Chain (execution order)

1. `Recovery()` — panic recovery
2. `RequestID()` — unique per-request ID
3. `Tracing()` — OpenTelemetry span creation
4. `ErrorHandler()` — catch and format `c.Errors`
5. `Logger()` — structured request logging (slog)
6. `SecurityHeaders()` — HSTS, CSP, X-Content-Type-Options
7. `CORS()` — origin whitelist
8. `BodyLimit()` — max request body size
9. `SchoolID()` — extract `x-school-id` header
10. `RedisRateLimit()` — distributed sliding-window rate limiting
11. `CSRF()` — nonce-based CSRF token validation

Per-group middleware (applied after auth):
12. `JWTAuth()` — JWT validation + Redis blacklist check
13. `EnforceSchoolID()` — require `x-school-id` header
14. `TenantResolution()` — resolve plan/features from DB/Redis
15. `AuditLogging()` — log all mutations
16. `TenantDBResolver()` — get per-tenant DB connection

---

## Multi-Tenancy

Hybrid model with three layers:

1. **Shared database** (`academio`) — users, schools, tenants, roles, audit logs
2. **Per-tenant databases** (`academio_tenant_<uuid>`) — school-specific data: students, subjects, scores, etc.
3. **Connection Manager** — maintains a dynamic pool of GORM connections per tenant
   - DB credentials encrypted with AES-256-GCM
   - Health checks every 30 seconds per connection
   - Default pool: 20 connections per tenant

### Provisioning flow

```
School created → database_status: "pending"
       ↓
Asynq task tenant:provision queued
       ↓
Worker creates PostgreSQL database
       ↓
Runs school migrations on tenant DB
       ↓
Seeds initial data (curriculum, subjects, levels, etc.)
       ↓
Sets database_status: "active"
       ↓
Frontend polls GET /api/v2/schools/:id until active
```

---

## Key System Flows

### School onboarding

```
Register → Login → Create School (triggers provisioning async)
                                              ↓
User sees provisioning state                    Worker creates + seeds tenant DB
      ↓                                                   ↓
Poll GET /schools/:id until active ←────────── database_status = "active"
      ↓
Configure academic sessions → curriculum → subjects → levels → grade items
```

### Academic scoring workflow

```
Create Session (term) → Create Curriculum → Create Assessment → Create Grade Items
                                                                      ↓
Mark Attendance → Save Scores → Rollup Scores → Save Result → Generate Report Card (PDF)
```

### Tenant DB resolution

```
Request with x-school-id header
       ↓
Middleware: lookup school → ConnectionManager.get(schoolID)
       ↓
If no pool: decrypt stored credentials → create GORM connection
       ↓
Inject tenant DB into context → handlers use repos.TenantDB()
```

---

## Database Models

The shared database hosts core models (`User`, `UserInfo`, `School`, `Tenant`, `Role`, `Session`). Per-tenant databases host 29+ model types including: `Student`, `Teacher`, `Staff`, `Subject`, `Curriculum`, `Assessment`, `GradeItem`, `Score`, `Result`, `Attendance`, `Bill`, `Payment`, `CBAQuestion`, `CBAPaper`, `Book`, `Hostel`, `TransportRoute`, `Alumni`, and more.

Each model embeds a `BaseModel` struct with `ID`, `UUID`, `CreatedAt`, `UpdatedAt`, `DeletedAt`, and audit fields.

---

## Infrastructure Services

| Service | Location | Purpose |
|---------|----------|---------|
| JWT Service | `pkg/jwt/` | Token creation/validation |
| Token Service | `internal/services/token_service.go` | Refresh token rotation |
| Blacklist Service | `internal/services/blacklist_service.go` | JWT revocation via Redis |
| Cache Service | `internal/services/cache_service.go` | Generic Redis caching |
| Encryption Service | `internal/crypto/` | AES-256-GCM |
| Queue Client/Worker | `internal/queue/` | Asynq task management |
| Task Handlers | `internal/queue/handlers/` | Email, SMS, Backup, Restore, Provisioning, AI Scoring |
| Communication | `internal/communication/` | SendGrid (email), Twilio (SMS + WhatsApp) |
| AI Provider | `internal/ai/` | OpenAI + Gemini abstraction |
| RAG Pipeline | `internal/ai/rag/` | Chunking → Embedding → Qdrant search |
| AI Agents | `internal/ai/agents/` | 10 specialized agents (tutor, assistant, risk analyzer, etc.) |
| WebSocket Hub | `internal/ws/` | Real-time notifications |
| Backup Service | `internal/backup/` | S3-based tenant DB backups |
| PDF Generator | `pkg/pdf/` | HTML→PDF for report cards |

---

## Frontend Architecture

### Route structure (TanStack Router, file-based)

```
src/routes/
├── __root.tsx                   # Root layout: ThemeProvider, ErrorBoundary, Sonner Toaster
├── login.tsx / register.tsx     # Public auth pages
├── forgot-password.tsx / reset-password.tsx / confirm-email.tsx
├── _public/                     # Public pages (landing, about, schools, admissions)
├── _onboarding/                 # School setup wizard
└── _dashboard/                  # Authenticated app (40+ route files)
    ├── dashboard.tsx
    ├── school.tsx               # School settings, sessions, curriculum
    ├── users.tsx                # Student/teacher/staff CRUD (1910-line file, being refactored)
    ├── academics.tsx / exams.tsx / timetable.tsx
    ├── cba.tsx / lms.tsx / payments.tsx
    ├── hostel.tsx / transport.tsx / library.tsx / inventory.tsx
    ├── admissions/ / alumni.tsx / career.tsx
    ├── analytics/ / reports.tsx / report-cards/
    ├── communication/ / ai-assistant.tsx
    └── ... (settings, profile, audit-logs, etc.)
```

### API client (`src/lib/api.ts`)

- Native `fetch()` — no Axios
- Auto-injects Bearer token from Zustand store
- 401 interceptor triggers token refresh (deduplicated)
- CSRF token acquisition (lazy, cached) for mutating requests
- Network retry — 2 attempts, exponential backoff (500ms → 1000ms)
- 30-second request timeout via AbortController
- Cross-tab auth sync via BroadcastChannel API
- Unwraps `{ success, data, error, meta }` response envelope

### State management

- **Zustand** — auth state (`accessToken`, `refreshToken`, `user`, `session`) persisted to localStorage via `zustand/middleware`
- **TanStack React Query** — server data with 60s stale time, 1 retry

---

## Security

- **Defense-in-depth**: HSTS, CSP headers, CORS origin whitelist, body size limits
- **JWT with refresh rotation**: short-lived access tokens, refresh tokens rotated on each use
- **Redis blacklist**: revoked tokens blacklisted until natural expiry
- **CSRF**: nonce-based tokens for all mutating requests
- **Rate limiting**: Redis-backed sliding window (per-IP, per-plan tier)
- **TOTP 2FA**: optional second factor
- **Input validation**: `go-playground/validator` + parameterized SQL queries
- **Tenant isolation**: separate PostgreSQL database per school
- **Encryption at rest**: AES-256-GCM for stored DB credentials
- **Audit logging**: all mutations logged to `audit_logs` table

---

## Development Setup

```bash
# Prerequisites
docker                          # PostgreSQL 16 + Redis 7
go 1.26+                        # Backend
yarn 4+ (corepack)              # Frontend
air                             # Backend hot reload

# Start infrastructure
docker compose up -d            # Starts shared-postgres + shared-redis

# Reset and start backend
cd backend
make db-init DROP_TENANT=true   # Drop + recreate databases
make migrate                    # Run all migrations
make seed                       # Seed super admin + demo data
./bin/server                    # Starts on :8080

# Frontend (separate terminal)
cd frontend
yarn install && yarn dev        # Starts on :4000, proxies /api → :8080
```

**Default credentials** (after seed): `playbit` / `Password123!`

### Integration testing

```bash
# Requires Docker + running server with fresh DB
cd backend
bash scripts/test_endpoint.sh   # 40 tests, full flow: health → auth → school → scores
```

---

## Coding Conventions

### Backend (Go)

- `go build ./...` and `go vet ./...` must pass clean
- Run `go mod tidy` when adding/removing dependencies
- Logging via `pkg/logger` (`logger.Warnf` / `logger.Errorf`) — not `log.Printf`
- Error returns for state mutations; log-and-continue for best-effort analytics queries
- Multi-statement `db.Exec()` is incompatible with pgx v5 prepared-statement mode — break into individual calls

### Frontend (TypeScript)

- `npx tsc --noEmit` must pass with zero errors
- Run `yarn dedupe` after adding dependencies
- Use `@/` path alias for imports
- Components go in `src/components/<domain>/`; routes in `src/routes/`
- Use the API client in `src/lib/api.ts` — don't call `fetch()` directly
- Form validation via Zod schemas + React Hook Form

### Frontend audit status

A comprehensive enterprise-grade frontend audit (`docs/audits/FRONTEND-ENTERPRISE-AUDIT.md`) identified **58 issues**:

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| Critical | 9 | 9 | 0 |
| High | 15 | 15 | 0 |
| Medium | 20 | 0 | 20 |
| Low | 14 | 0 | 14 |

All critical (auth trust model, WebSocket token leakage, missing ErrorBoundary, request timeout, hardcoded passwords) and high-severity issues (dead code, 404 route, scroll restoration, code splitting, network retry, auth checks) are resolved. Remaining items are polish: CSS system unification, testing coverage, accessibility (`skip-to-content` link, color contrast), and performance (virtual scrolling, memoized columns).

---

## Key Constraints & Gotchas

- **pgx v5 prepared-statement mode** does not support multiple SQL statements in a single `db.Exec()` call. Always break into individual calls.
- **Redis** is required for the asynq queue (tenant provisioning). Docker container `shared-redis` at `localhost:6379`.
- **Provisioning** runs as an async background task. Frontend must poll `GET /api/v2/schools/:id` until `database_status` is `"active"`.
- **Use `scripts/test_endpoint.sh`** for integration testing — it handles CSRF tokens, bearer auth, provisioning polling, and all academic endpoints. Do not write ad-hoc test scripts.
- **CSP headers** in dev: the frontend dev server proxies `/api` to `:8080`, but CSP `connect-src` must allow both origins.

---

## Related Documentation

| Document | Path | Purpose |
|----------|------|---------|
| Architecture overview | `docs/architecture/2-ARCHITECTURE-OVERVIEW.md` | High-level system architecture |
| Database schema | `docs/architecture/3-DATABASE-SCHEMA.md` | ERD, tables, indexes |
| API spec | `docs/architecture/4-API-SPECIFICATIONS.md` | Endpoint catalog (25+ modules) |
| Security | `docs/architecture/6-SECURITY-INFRASTRUCTURE.md` | Auth flows, RBAC, tenancy |
| AI architecture | `docs/architecture/5-AI-ARCHITECTURE.md` | AI gateway, RAG, agents |
| Audit checklist | `docs/architecture/10-AUDIT-CHECKLIST.md` | Production readiness gate |
| Frontend audit | `docs/audits/FRONTEND-ENTERPRISE-AUDIT.md` | 58 findings, 24 fixed |
| Go style guide | `backend/STYLE.md` | Go code conventions |
