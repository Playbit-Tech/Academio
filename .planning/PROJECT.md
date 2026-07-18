# Academio

## What This Is

Academio is a multi-tenant school management system that provides K-12 and higher education institutions with tools for academic management, admissions, student information, finance, HR, communication, and reporting. Each school runs in its own database schema, with shared user authentication across the platform.

## Core Value

Students can be enrolled, tracked through their academic journey, and assessed — with every school's data isolated and secure in its own tenant schema.

## Requirements

### Validated

<!-- Shipped and confirmed valuable via existing codebase. -->

- ✓ **Auth**: User registration with email/password, JWT login/logout, CSRF nonce protection, 2FA, password reset, refresh tokens, Redis-based session revocation — existing
- ✓ **Multi-Tenant**: Schema-per-tenant isolation via `SchemaTablePrefix` GORM plugin, Redis-cached tenant resolution, per-request tenant DB resolver — existing
- ✓ **School Management**: School CRUD, provisioning with automatic schema creation + migrations + seed data, config/feature management — existing
- ✓ **Academic Structure**: Academic sessions/terms, curriculum management, subjects, levels/classes, grade items with sum-to-100 validation — existing
- ✓ **Admissions**: Intake management, dynamic form builder (custom sections + fields), public application forms, document upload, screening pipeline (screen → exam → offer → enrollment) — existing
- ✓ **User Management**: Student/staff/parent CRUD, batch import with XLSX, role assignment, parent dedup by email/phone/username, sibling reuse — existing
- ✓ **Assessment & Scoring**: Computer-based assessments (CBA), exam results, grade item scores with bulk save/rollup/export — existing
- ✓ **Attendance**: Student attendance (roll-call, bulk upsert, records with name resolution), teacher/staff clock-in/out — existing
- ✓ **Timetable**: CRUD, bulk create, calendar editor with conflict highlighting — existing
- ✓ **Report Cards**: Report card generation, templates, batch generation — existing
- ✓ **Communication**: Email (SendGrid) / SMS (Twilio) templates, campaigns, broadcast, delivery logging — existing
- ✓ **AI Integration**: Gemini + OpenAI providers, RAG pipeline with Qdrant vector store, AI-powered applicant scoring — existing
- ✓ **Finance**: Chart of accounts, journal entries, budgets, expenses, billing — existing
- ✓ **HR**: Departments, staff management, leaves, payroll, appraisals, recruitment — existing
- ✓ **LMS**: Courses, modules, lessons, assignments, discussions — existing
- ✓ **Timetable**: CRUD, bulk create, calendar editor with conflict highlighting — existing
- ✓ **Backup/Restore**: S3-backed tenant backup via `pg_dump`/`pg_restore`, 14-backup retention — existing
- ✓ **Reporting & Analytics**: Predefined reports, custom report builder, enrollment/revenue/academic/attendance analytics with forecasts — existing
- ✓ **Observability**: OpenTelemetry distributed tracing, Prometheus metrics, Swagger API docs, structured logging via `pkg/logger` — existing
- ✓ **Security**: Rate limiting (in-memory + Redis sliding window), CORS, security headers, audit logging, RBAC — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] **ADM-01**: Dynamic admission form builder features (phone/checkbox field types, field reordering, form config caching via TanStack Query) — in progress
- [ ] **QOL-01**: Backend performance improvements (bubble sort → sort.Slice, N+1 query elimination, unnecessary DB reload removal) — completed
- [ ] **QOL-02**: XLSX subject dropdown column shift fix — completed

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Mobile native app** — Web-first; mobile responsive via Tailwind CSS
- **Real-time collaboration** — No Google Docs-style concurrent editing needed
- **Video conferencing** — Out of scope for a school management system
- **Custom landing pages** — School branding via config, not a CMS

## Context

**Codebase State:**
- ~58K-line Go backend across 39 modules under `backend/internal/modules/`
- ~15K-line TypeScript/React frontend under `frontend/src/`
- 40+ integration tests via `test_endpoint.sh` (64 tests, all passing)
- `go build ./...`, `go vet ./...`, `npx tsc --noEmit`, `yarn vite build` all clean
- Multi-tenant: Schema-per-tenant PostgreSQL, single shared database

**Recent Work:**
- Admission Form Builder fully implemented (models, admin CRUD, public rendering, dynamic form validation, custom field types, field reordering, form config caching)
- Various code quality fixes: error discard patterns (21 fixes), security hardening (CSRF, DSN sanitization, DB name validation), context propagation (GetTenantDB, provisioning, S3 backups)
- XLSX subjects dropdown column shift bug fixed
- Backend perf improvements (bubble sort, N+1 elimination, reload removal)
- TypeScript zero-errors achieved (46 pre-existing type errors fixed)
- Teacher assessment score grid enhancements (persisted filters, dirty scores, AlertDialog, proportional totals)

**Known Concerns:**
- 18 intentional error discards in auth service (best-effort: cache/revocation operations)
- Some `context.Background()` usage in audit batch insert and S3 operations
- S3 URL hardcodes AWS domain (breaks MinIO-compatible storage for URL generation)
- Low test coverage for some modules (alumni, analytics, inventory, library, etc.)

## Constraints

- **Tech Stack**: Go 1.26+, GORM v1.31+, Gin, pgx/v5, PostgreSQL — no migrations to other languages/frameworks
- **Multi-Tenant**: Schema-per-tenant isolation — must never leak data between schools
- **Database**: Single PostgreSQL instance shared across all tenants — connection pool must be carefully managed
- **Public Endpoints**: Admission forms are public (no auth) — must be secured via rate limiting and reference numbers
- **Background Tasks**: Asynq queue for async operations — Redis required for tenant provisioning

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Dynamic form builder with custom sections/fields | Schools need different application forms; pre-built templates are inflexible | ✓ Good |
| Schema-per-tenant isolation | Strongest data isolation without per-tenant database overhead | ✓ Good |
| Modular monolith (39 modules) | Simpler than microservices at current scale; modules provide clear boundaries | ✓ Good |
| SchemaTablePrefix GORM plugin | Seamless multi-tenant GORM queries without modifying every query | ✓ Good |
| Public admissions forms via slug+reference | No auth needed for applicants; reference number tracks status | ✓ Good |

---
*Last updated: 2026-07-18 after initialization*
