# Technology Stack

**Analysis Date:** 2026-07-18

## Languages

**Primary:**
- **Go 1.26.1** — All backend services (`backend/`), 39+ modules
- **TypeScript ~5.x** — Frontend SPA (`frontend/src/`)

**Secondary:**
- **Bash** — Integration test suite (`backend/scripts/test_endpoint.sh`), CI scripts
- **JavaScript** — Load testing scripts (`scripts/loadtest/*.js`)
- **SQL (PostgreSQL)** — Database queries, GORM-generated, pg_dump/pg_restore

## Backend Runtime

**Language:** Go 1.26.1 (`backend/go.mod`)
**Package Manager:** Go modules (no vendoring; `go.mod` + `go.sum`)
**Framework:** Gin v1.12.0 (`github.com/gin-gonic/gin`)
**ORM:** GORM v1.31.2 (`gorm.io/gorm`) + GORM PostgreSQL driver v1.6.0 (`gorm.io/driver/postgres`)
**Database Driver:** pgx/v5 (via GORM postgres driver)
**Migration:** Custom migration system (`backend/internal/database/migrations/`)
**Task Queue:** Asynq v0.26.0 (`github.com/hibiken/asynq`) — Redis-backed
**Validation:** go-playground/validator v10.30.3
**JWT:** golang-jwt/jwt v5.3.1
**UUID:** google/uuid v1.6.0
**Password:** golang.org/x/crypto (bcrypt)
**Env:** joho/godotenv v1.5.1
**CSRF:** Custom middleware (nonce-based, `backend/internal/middleware/csrf.go`)

## Frontend Runtime

**Language:** TypeScript ~5.x (`frontend/tsconfig.json`, target ES2022)
**Package Manager:** Yarn 4.17.0 (`frontend/.yarnrc.yml`, `nodeLinker: node-modules`)
**Build Tool:** Vite 8.x (`frontend/vite.config.ts`)
**UI Framework:** React 19.2.4 (`react`, `react-dom`)
**Routing:** TanStack Router v1.170.0 (file-based routing via `@tanstack/react-router`)
**Plugin:** TanStack Router Vite Plugin v1.168.0 (auto code-splitting, route generation)
**Data Fetching:** TanStack React Query v5.99.2 (+ DevTools v5.101.2)
**UI Components:** shadcn/ui (via `shadcn` CLI v4.4.0), Radix UI primitives (`@radix-ui/react-slot`, `@radix-ui/react-switch`)
**CSS:** Tailwind CSS v4 (`tailwindcss`, `@tailwindcss/postcss`), `tw-animate-css` v1.4.0
**Forms:** react-hook-form v7.73.1 + `@hookform/resolvers` v5.2.2
**Validation:** Zod v4.3.6
**State (client-side):** Zustand v5.0.12
**Class Utils:** `class-variance-authority` v0.7.1, `clsx` v2.1.1, `tailwind-merge` v3.5.0
**Icons:** lucide-react v1.8.0
**Charts:** recharts v3.9.0
**Dates:** dayjs v1.11.21
**Toasts:** sonner v2.0.7
**Drag & Drop:** @dnd-kit/core v6.3.1, @dnd-kit/sortable v10.0.0, @dnd-kit/utilities v3.2.2
**QR Code:** qrcode v1.5.4 (`@types/qrcode` v1.5.6)
**Excel:** xlsx v0.18.5 (frontend preview)
**Select:** react-select v5.10.2
**Nigerian LGAs:** naija-state-local-government v1.1.2
**Base UI:** @base-ui/react v1.4.1

## Testing

**Backend:**
- Test Runner: `go test`
- SQL Mock: go-sqlmock v1.5.2
- Assertions: testify v1.11.1
- Integration: Custom Bash script (`backend/scripts/test_endpoint.sh`), 40 tests
- Containerized DB: testcontainers-go v0.43.0
- GORM SQLite driver v1.6.0 (for test isolation)

**Frontend:**
- Test Runner: Vitest v4.1.9
- Component Testing: @testing-library/react v16.3.2, @testing-library/dom v10.4.1, @testing-library/user-event v14.6.1
- DOM Assertions: @testing-library/jest-dom v6.9.1
- DOM Environment: jsdom v29.1.1
- E2E: Playwright v1.61.1 (`@playwright/test`)

## Infrastructure & DevOps

**Containerization:**
- Docker (`backend/Dockerfile`): Multi-stage build, golang:1.26-alpine → alpine:3.19
- Docker Compose: Managed externally (PostgreSQL `shared-postgres` on :5432, Redis `shared-redis` on :6379)

**CI/CD:**
- GitHub Actions (`.github/workflows/ci.yml`) — `go vet ./...`, backend tests with race detection, coverage threshold
- Vercel Deployment — Frontend SPA (Vite build, `vercel.json`)

**Development Tools:**
- **Air** — Go hot reload (binary at `backend/tmp/server`)
- **Makefile** — `make db-init`, `make migrate`, `make seed`, etc.
- **Swagger** — API docs via `swaggo/swag` v1.16.6, `swaggo/gin-swagger` v1.6.1, `swaggo/files` v1.0.1
- **Prometheus** — Metrics endpoint via `prometheus/client_golang` v1.19.1

## Configuration

**Backend Environment:**
- `.env` file loaded by godotenv (`backend/.env`)
- Config struct: `backend/internal/config/config.go`
- All config loaded from environment variables with sensible defaults

**Frontend Environment:**
- Vite env vars prefixed with `VITE_` (`import.meta.env`)
- `VITE_API_URL`, `VITE_WS_URL`, `VITE_GOOGLE_MAPS_API_KEY`, `VITE_MAPBOX_ACCESS_TOKEN`

## Go Dependencies (Key)

**Critical Infrastructure:**
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/gin-gonic/gin` | v1.12.0 | HTTP framework |
| `gorm.io/gorm` | v1.31.2 | ORM |
| `gorm.io/driver/postgres` | v1.6.0 | PostgreSQL driver (pgx/v5) |
| `github.com/redis/go-redis/v9` | v9.21.0 | Redis client |
| `github.com/hibiken/asynq` | v0.26.0 | Task queue |
| `github.com/aws/aws-sdk-go-v2` | v1.42.0 | AWS SDK (S3) |
| `github.com/aws/aws-sdk-go-v2/service/s3` | v1.104.1 | S3 storage |

**AI/ML Integration:**
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/openai/openai-go` | v1.12.0 | OpenAI API client |
| `google.golang.org/genai` | v1.62.0 | Google Gemini API client |

**Observability:**
| Package | Version | Purpose |
|---------|---------|---------|
| `go.opentelemetry.io/otel` | v1.41.0 | OpenTelemetry SDK |
| `go.opentelemetry.io/otel/sdk` | v1.35.0 | OTel SDK |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace` | v1.28.0 | OTLP trace exporter |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc` | v1.28.0 | OTLP gRPC transport |
| `go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp` | v1.28.0 | OTLP HTTP transport |
| `github.com/prometheus/client_golang` | v1.19.1 | Prometheus metrics |

**Other:**
| Package | Version | Purpose |
|---------|---------|---------|
| `github.com/xuri/excelize/v2` | v2.11.0 | Excel file generation |
| `github.com/gorilla/websocket` | v1.5.3 | WebSocket support |
| `gorm.io/datatypes` | v1.2.7 | GORM data types (JSON, etc.) |
| `gorm.io/driver/sqlite` | v1.6.0 | SQLite (test isolation) |
| `cloud.google.com/go` | v0.116.0 | GCP SDK (indirect, via Gemini/OTel) |

## Dependency Licenses

All Go dependencies are MIT, BSD, or Apache 2.0 licensed. Frontend dependencies are MIT or Apache 2.0 licensed.

---

*Stack analysis: 2026-07-18*
