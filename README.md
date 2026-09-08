# Academio

School management system — monorepo with a Go/Gin API backend and a React 19 SPA frontend.

<a href="https://playbits.github.io/Academio/" target="_blank"><img src="https://img.shields.io/badge/docs-github_pages-8DD290?style=flat&logo=github" alt="Docs"></a>
<a href="https://github.com/Playbits/Academio" target="_blank"><img src="https://img.shields.io/badge/GitHub-181717?style=flat&logo=github" alt="GitHub"></a>
<img src="https://img.shields.io/badge/version-1.1.0-8DD290?style=flat" alt="Version">
<a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-keep_a_changelog-8DD290?style=flat" alt="Changelog"></a>

## Repositories

| Component | Description | Repository |
|-----------|-------------|------------|
| **Parent** (this repo) | Monorepo orchestration, dev script | `Playbits/Academio` |
| **Backend** (submodule) | Go/Gin REST API + PostgreSQL + Redis | `Playbits/Academio-Be` |
| **Frontend** (submodule) | React 19 + Vite 8 SPA | `Playbits/Academio-fe` |

## Quick Start

```bash
# Clone with submodules
git clone --recurse-submodules git@github.com:Playbits/Academio.git
cd Academio

# Start everything (Docker + backend + frontend + Antigravity IDE)
start_schoolcare
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
# Reset DB
cd backend && make db-init DROP_TENANT=true && make migrate && make seed

# Start server (Air hot reload — do NOT run ./bin/server directly, it may be a stale artifact)
cd backend && air

# Run tests
bash scripts/test_endpoint.sh
```

**Expected result:** 139 tests pass, 2 known cosmetic failures (missing verification email for a parent fixture; a result 404 for a combo with no result row — RBAC works). The script provisions a school, creates curriculum/assessments/grade items, and validates sum-to-100 constraints.

> **Note for AI sessions:** Always use `scripts/test_endpoint.sh` for integration testing. It handles CSRF token acquisition, bearer auth, provisioning polling, and all academic endpoints. Don't write ad-hoc test scripts.

## Versioning

This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The current version is `1.1.0` (see `VERSION`). Each submodule tracks its own version in its `CHANGELOG.md`; the parent repo records submodule pointer bumps.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the parent repo, and each submodule's `CHANGELOG.md` for component-level changes.