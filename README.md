# SchoolCare v2

School management system — monorepo with a Go/Gin API backend and a React 19 SPA frontend.

[![Docs](https://img.shields.io/badge/docs-github_pages-8DD290?style=flat&logo=github)](https://playbits.github.io/schoolcare-v2/)

## Repositories

| Component | Description | Repository |
|-----------|-------------|------------|
| **Parent** (this repo) | Monorepo orchestration, dev script | `Playbits/schoolcare-v2` |
| **Backend** (submodule) | Go/Gin REST API + PostgreSQL + Redis | `Playbits/schoolcare-be-v2` |
| **Frontend** (submodule) | React 19 + Vite 8 SPA | `Playbits/schoolcare-fe-v2` |

## Quick Start

```bash
# Clone with submodules
git clone --recurse-submodules git@github.com:Playbits/schoolcare-v2.git
cd schoolcare-v2

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
| Frontend | http://localhost:3000 |
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

# Start server
./bin/server &

# Run tests
bash scripts/test_endpoint.sh
```

**Expected result:** 40 tests pass, 0 fail. The script provisions a school, creates curriculum/assessments/grade items, and validates sum-to-100 constraints.

> **Note for AI sessions:** Always use `scripts/test_endpoint.sh` for integration testing. It handles CSRF token acquisition, bearer auth, provisioning polling, and all academic endpoints. Don't write ad-hoc test scripts.
