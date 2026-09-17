# Academio

School management system — monorepo with a Go/Gin API backend and a React 19 SPA frontend.

<a href="https://playbits.github.io/Academio/" target="_blank"><img src="https://img.shields.io/badge/docs-github_pages-8DD290?style=flat&logo=github" alt="Docs"></a>
<a href="https://github.com/Playbits/Academio" target="_blank"><img src="https://img.shields.io/badge/GitHub-181717?style=flat&logo=github" alt="GitHub"></a>
<img src="https://img.shields.io/badge/version-1.3.0-8DD290?style=flat" alt="Version">
<a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-keep_a_changelog-8DD290?style=flat" alt="Changelog"></a>

## Repositories

| Component | Description | Repository |
|-----------|-------------|------------|
| **Parent** (this repo) | Monorepo orchestration, dev script | `Playbits/Academio` |
| **Backend** (submodule) | Go/Gin REST API + PostgreSQL + Redis | `Playbits/Academio-Be` |
| **Frontend** (submodule) | React 19 + Vite 8 SPA | `Playbits/Academio-fe` |
| **Mobile** (submodule) | Flutter mobile app | `Playbit-Tech/academio-mobile` |
| **AI Engine** (submodule) | AI services | `Playbit-Tech/academio-ai-engine` |
| **Emails** (submodule) | Email studio / templates | `Playbit-Tech/academio-email-stuio` |

## Quick Start

```bash
# Clone with submodules
git clone --recurse-submodules git@github.com:Playbits/Academio.git
cd Academio

# Start everything (backend + frontend, separate terminals — see below)
# Backend:  cd backend && make dev
# Frontend: cd frontend && yarn dev
```

Or start services individually:

```bash
# Backend
cd backend && make dev

# Frontend (separate terminal)
cd frontend && yarn dev
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:4000 |
| Backend API | http://localhost:8080 |
| API docs (Swagger) | http://localhost:8080/swagger/index.html |

## Prerequisites

- **Docker** — PostgreSQL 16 + Redis 7
- **Go** 1.26+ — backend
- **Yarn** 4+ — frontend
- **Air** — backend hot reload (`go install github.com/air-verse/air@latest`)

## Submodule Management

```bash
# Pull latest from all submodules
git submodule update --remote

# Or update a specific one
git submodule update --remote backend
```

## Testing

### Integration Test Script

`backend/scripts/test_endpoint.sh` is a bash-based endpoint test suite that covers the full onboarding + academic workflow:

```
Health → CSRF → Register → Login → School Create → Provisioning Poll → Curriculum → Assessments → Sessions → Grade Items → Sum-to-100 Validation
```

**Run it** (requires Docker + backend server running with fresh DB):
```bash
# Reset DB — use seed-demo (NOT seed): the Phase 5 T4a section runs its
# 12-role matrix over the school-1 contract rows that only seed-demo plants
cd backend && make db-init DROP_TENANT=true && make migrate && make seed-demo

# Start server (Air hot reload — do NOT run ./bin/server directly, it may be a stale artifact)
cd backend && air

# Run tests
bash scripts/test_endpoint.sh
```

**Expected result:** historically ~139 passes with 2 known cosmetic failures (missing verification email for a parent fixture; a result 404 for a combo with no result row — RBAC works). Counts drift as suites grow — see `backend/CHANGELOG.md` and `frontend/CHANGELOG.md` for the latest numbers. The script provisions a school, creates curriculum/assessments/grade items, and validates sum-to-100 constraints. (Note: the script's own post-pass `RESET=true` cleanup uses `make seed` — super-admin only — which is correct for reset, not for pre-run.)

### Phase 5 E2E — 12-Role API Matrix

`backend/scripts/test_t4a.sh` is a standalone 12-role API E2E script (75 tests, idempotent). It resets seed data on each run and proves all role permissions, RBAC gates, D-C approve chain, PHI gate, forged-call 403s, issue→return chains, and admissions pipeline.

**Run it** (requires backend server running with seed-demo data):
```bash
cd backend && bash scripts/test_t4a.sh
```

**Expected result:** 75/75 pass, 0 fail. Fully idempotent — rerun-safe.

### Frontend E2E

`frontend/src/__tests__/phase5-e2e.test.ts` covers 12-role branch resolution, nav subset-closure, staff sections, and specialist ordering (28 tests).

```bash
cd frontend && yarn vitest run src/__tests__/phase5-e2e.test.ts
```

> **Note for AI sessions:** Always use `scripts/test_endpoint.sh` for integration testing. For Phase 5 role verification, use `scripts/test_t4a.sh`. Don't write ad-hoc test scripts.

## Tenancy + RBAC Primer

- `users` lives in the shared **`public`** schema; every school-scoped model (`Student`, `Teacher`, `Subject`, `Score`, …) lives in its **`school_{id}`** tenant schema (check `migrations/core/` (public) vs `migrations/school/` (tenant) before querying).
- The `SchemaTablePrefix` GORM plugin scopes tenant queries automatically — tenant code must go through `middleware.GetTenantDB(c)`, never the raw core DB or hardcoded schema names.
- New schools are provisioned async (asynq `provisioning:school` queue); poll `GET /api/v2/schools/:id` until `schema_name` is non-empty.
- RBAC is backend-authoritative with a 12-role matrix: resolved perms cache in Redis (`rbac:perms:{school}:{user}`, 5-min TTL) and fail closed on error.
- Prove permission changes with `bash scripts/test_t4a.sh` (75/75, idempotent) — grant *and* denial.

## CI (Self-Hosted)

Runners are self-hosted with persistent disks: every `actions/setup-go` step uses `cache: false` (the upload/download cache dance is pure overhead against the warm on-disk cache), and the Redis service container is remapped to host port **16379** (never the platform's 6379) — jobs point `REDIS_ADDR` / `QUEUE_REDIS_ADDR` at `localhost:16379` (see `.github/workflows/reusable-backend-ci.yml`).

## Versioning

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The current version is `1.3.0` (see `VERSION`). Each submodule tracks its own version in its `CHANGELOG.md`; the parent repo records submodule pointer bumps.

**Submodule-version truth (triple-sync rule):** on every release keep three anchors on the same version — parent `VERSION`, backend `ServiceVersion` (`internal/modules/health/handler.go`, mirrored in the Swagger comment in `cmd/server/main.go` and the telemetry resource in `internal/telemetry/provider.go`), and `frontend/package.json`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the parent repo, and each submodule's `CHANGELOG.md` for component-level changes.

## Documentation

- `docs/role-dashboards/` — Permission matrix, per-role guides, cross-check report, multi-school semantics, backend-authoritative note, ops runbook.