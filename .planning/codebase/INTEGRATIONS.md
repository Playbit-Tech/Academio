# External Integrations

**Analysis Date:** 2026-07-18

## Data Storage

### PostgreSQL (Primary Database)
- **Purpose:** All persistent data — shared user accounts and per-tenant school data
- **Connection:** `DB_HOST`, `DB_PORT` (default `localhost:5432`), `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- **Client:** GORM v1.31.2 via `gorm.io/driver/postgres` v1.6.0 (uses pgx/v5 internally)
- **Pattern:** Multi-tenant via **schema-per-tenant** — one PostgreSQL database, each school gets its own schema (`school_{id}`), isolated via GORM `SchemaTablePrefix` plugin
- **Shared schema (`public`):** `User` (users table) only
- **Tenant schemas:** All school-specific models (`Teacher`, `Student`, `Level`, `Score`, `Subject`, `Assessment`, `Session`, `GradeItem`, `Attendance`, `Timetable`, `Payment`, `Bill`, etc.)
- **Migration:** Custom migration system — `backend/internal/database/migrations/shared/` for public schema, `backend/internal/database/migrations/school/` for tenant schema
- **DSN Construction:** URL-safe via `net/url` in `backend/internal/config/config.go`

### Redis
- **Purpose:** Three distinct roles:
  1. **Asynq task queue broker** — `QueueConfig.RedisDB: 1` (separate from cache Redis)
  2. **Tenant resolution cache** — Caches school-to-DB mapping (`TenantResolutionService` in `backend/internal/database/tenant/resolution_service.go`)
  3. **Distributed rate limiting** — Sliding window counter (`middleware/ratelimit.go`)
  4. **Token blacklisting** — JWT refresh token revocation (`services/blacklist_service.go`)
  5. **User session cache** — `services/user_cache.go`, `services/refresh_token_cache.go`
- **Connection:** `REDIS_ADDR` (default `localhost:6379`), `REDIS_PASSWORD`, `REDIS_DB`
- **Client:** `github.com/redis/go-redis/v9` v9.21.0
- **Async queue client:** `github.com/hibiken/asynq` v0.26.0
- **Connection management:** `backend/internal/database/redis.go` and `backend/internal/queue/client.go`

## Object Storage

### S3-Compatible Storage (Backups)
- **Purpose:** Store tenant database backups (pg_dump output) for disaster recovery
- **Implementation:** `backend/pkg/storage/s3_backup.go`
- **Client:** AWS SDK v2 (`github.com/aws/aws-sdk-go-v2` v1.42.0, `service/s3` v1.104.1)
- **Configuration:** `S3Config` in `backend/internal/config/config.go`
  - `S3_REGION`, `S3_BACKUP_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`
  - `S3_ENDPOINT` — Custom endpoint for S3-compatible stores (MinIO, DigitalOcean Spaces, etc.)
  - `S3_BASE_URL` — Public URL prefix
- **Auth:** Static credentials via `credentials.NewStaticCredentialsProvider`
- **Operations:** PutObject, GetObject, DeleteObject (for backup lifecycle)
- **Retention:** 14 backups per tenant (`backend/internal/modules/tenant/service.go`)
- **Compatibility:** Path-style URLs enabled for MinIO-compatible endpoints

### Local Filesystem Storage
- **Purpose:** Multimedia uploads (profile pictures, documents, etc.)
- **Driver:** `"local"` (default), configured via `STORAGE_DRIVER=local` and `STORAGE_PATH=./uploads`
- **Implementation:** `backend/pkg/storage/local.go`
- **S3 Driver:** Also available via `STORAGE_DRIVER=s3` (`backend/pkg/storage/s3.go`)
- **Interface:** `storage.Driver` — implementations for both local and S3

## AI / LLM Providers

### Google Gemini
- **SDK:** `google.golang.org/genai` v1.62.0
- **Implementation:** `backend/internal/ai/gemini.go`
- **Config:** `AI_GEMINI_API_KEY`, `AI_GEMINI_MODEL` (default `gemini-2.0-flash`)
- **Capabilities:**
  - Text generation (sync + streaming)
  - Text embeddings via `text-embedding-004`
  - Token counting via `CountTokens`
- **Default provider** when `AI_PROVIDER=gemini`

### OpenAI
- **SDK:** `github.com/openai/openai-go` v1.12.0
- **Implementation:** `backend/internal/ai/openai.go`
- **Config:** `AI_OPENAI_API_KEY`, `AI_OPENAI_MODEL` (default `gpt-4o`)
- **Capabilities:**
  - Chat completions (sync + streaming)
  - Text embeddings via `text-embedding-3-small`
  - Token estimation (local approximation)

### AI Gateway
- **Location:** `backend/internal/ai/gateway.go`
- **Pattern:** Provider-agnostic interface with `GenerateText`, `GenerateTextStream`, `GenerateEmbedding`, `GenerateEmbeddings`, `CountTokens`
- **Routing:** Model router (`backend/internal/ai/model_router.go`) selects provider based on model name
- **Circuit Breaker:** `backend/internal/ai/circuit_breaker.go` — prevents cascading failures
- **Cost Tracking:** `backend/internal/ai/cost.go` — token-based cost calculation
- **Tracing:** OpenTelemetry spans for all AI operations (`backend/internal/ai/tracing.go`)
- **Prometheus Metrics:** `AIErrorsTotal`, request duration, token counts, cost

### AI Agent System
- **Location:** `backend/internal/ai/agents/`
- **Available Agents:**
  - `academic_tutor.go` — Academic tutoring assistant
  - `alumni_insights.go` — Alumni analytics
  - `career_guidance.go` — Career guidance advisor
  - `enrollment_forecaster.go` — Enrollment predictions
  - `executive_summarizer.go` — Executive report summaries
  - `parent_assistant.go` — Parent communication assistant
  - `proctoring_analyzer.go` — Exam proctoring analysis
  - `revenue_forecaster.go` — Revenue projections
  - `risk_analyzer.go` — Student risk assessment
  - `teacher_assistant.go` — Teacher productivity assistant
- **Base Agent:** `backend/internal/ai/agents/base.go`

### Vector Database

**Qdrant:**
- **Purpose:** Store and search vector embeddings for RAG (Retrieval Augmented Generation)
- **Config:** `AI_QDRANT_URL` (default `http://localhost:6333`), `AI_QDRANT_API_KEY`, `AI_QDRANT_TIMEOUT`
- **Implementation:** `backend/internal/ai/vector/qdrant.go` — REST API client
- **Interface:** `vector.Store` (`backend/internal/ai/vector/store.go`)
- **Operations:** Insert, Search, Delete vectors in named collections
- **RAG Pipeline:** `backend/internal/ai/rag/pipeline.go` — text chunking → embedding → Qdrant insert/search

## Communication

### Email (SendGrid)
- **Provider:** SendGrid
- **Config:** `COMMUNICATION_EMAIL_ENABLED`, `COMMUNICATION_EMAIL_PROVIDER=sendgrid`, `SENDGRID_API_KEY`
- **Implementation:** `backend/internal/communication/sendgrid.go`
- **Async Queue:** Email tasks enqueued via Asynq (`queue.NewEmailSendTask`)
- **Handler:** `backend/internal/queue/handlers/email_handler.go`
- **Provider Interface:** `communication.EmailProvider` (`backend/internal/communication/email.go`)

### SMS (Twilio)
- **Provider:** Twilio
- **Config:** `COMMUNICATION_SMS_ENABLED`, `COMMUNICATION_SMS_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- **Implementation:** `backend/internal/communication/twilio.go`
- **Async Queue:** SMS tasks enqueued via Asynq (`queue.NewSMSSendTask`)
- **Handler:** `backend/internal/queue/handlers/sms_handler.go`
- **Provider Interface:** `communication.SMSProvider` (`backend/internal/communication/sms.go`)
- **Provider Factory:** `backend/internal/communication/provider.go` — registers SendGrid and Twilio by name

## Maps & Geolocation

### Google Maps Platform
- **Integration:** Google Places API for address autocomplete
- **Frontend Hook:** `frontend/src/lib/hooks/useGooglePlaces.ts`
  - `fetchAutocompleteSuggestions` — Place autocomplete with `includedRegionCodes: ["ng"]`
  - `fetchDetails` — Fetch place details (location, address components)
  - Session-based token management
- **Config:** `VITE_GOOGLE_MAPS_API_KEY`
- **CSP:** `https://maps.googleapis.com` and `https://places.googleapis.com` allowed in script-src, connect-src, frame-src
- **Type Definitions:** `@types/google.maps` v3.65.2
- **Usage:** School address entry form (`frontend/src/routes/_dashboard/school.tsx`)

### Mapbox
- **Config:** `VITE_MAPBOX_ACCESS_TOKEN` (optional)
- **Usage:** Secondary map visualization (token present in env but no active usage identified)

## WebSockets

### Real-time Notifications
- **Backend:** `gorilla/websocket` v1.5.3
- **Hub:** `backend/internal/ws/hub.go` — connection management, room-based broadcasting
- **Auth:** Token via `Sec-WebSocket-Protocol` sub-protocol header (not query string)
- **Config:** `WS_ENABLED`, `WS_MAX_CONN_PER_USER`, `WS_MSG_RATE_LIMIT`, etc.
- **Communication Config:** `COMMUNICATION_WEBSOCKET_ENABLED` for real-time messaging
- **Frontend:** `frontend/src/lib/hooks/useWebSocket.ts` — auto-reconnect, message listeners
- **Notifications Hook:** `frontend/src/lib/hooks/useNotificationWS.ts` — transforms real-time notifications to Zustand store
- **Plan Gating:** WebSocket availability tiered by plan (Premium/Enterprise only)

## Task Queue

### Asynq (Redis-based)
- **Client:** `github.com/hibiken/asynq` v0.26.0
- **Redis:** Separate Redis DB (`QUEUE_REDIS_DB: 1`) from cache/rate-limit Redis
- **Config:** `QUEUE_CONCURRENCY` (10), `QUEUE_MAX_RETRIES` (5), `QUEUE_RETRY_DELAY_BASE` (30s)
- **Task Types:**
  - `email:send` — Transactional email delivery
  - `sms:send` — SMS message delivery
  - `report:generate` — Report card document generation
  - `ai:scoring` — AI-powered applicant scoring
  - `backup:create` — Tenant database backup
  - `restore:execute` — Tenant database restore
- **Worker:** Embedded goroutine in same process (`backend/internal/queue/worker.go`)
- **Client:** `backend/internal/queue/client.go`
- **Metrics:** Prometheus counters for task processing (`backend/internal/queue/metrics.go`)

## Observability

### OpenTelemetry
- **Purpose:** Distributed tracing and observability
- **SDK:** `go.opentelemetry.io/otel` v1.41.0
- **Exporter:** OTLP gRPC or HTTP (configurable via `OTEL_EXPORTER_TYPE`)
- **Endpoint:** `OTEL_ENDPOINT` (default `localhost:4317`)
- **Service Name:** `academio-backend`
- **Implementation:** `backend/internal/telemetry/provider.go`
- **Integrations:**
  - GORM tracing: `backend/internal/telemetry/gorm_tracing.go`
  - Redis tracing: `backend/internal/telemetry/redis_tracing.go`
  - AI operations: `backend/internal/ai/tracing.go`
  - HTTP middleware: `backend/internal/middleware/tracing.go`
- **Configuration:** `TelemetryConfig` in `backend/internal/config/config.go`

### Prometheus
- **Endpoint:** `/metrics` served via `prometheus/client_golang` v1.19.1
- **Metrics:** AI request counts, durations, token usage, costs; queue processing stats
- **Setup:** `backend/internal/router/router.go` mounts promhttp handler

### Swagger / OpenAPI
- **Spec:** Generated via `swaggo/swag` v1.16.6
- **UI:** `swaggo/gin-swagger` v1.6.1 at `/swagger/*`
- **Spec Location:** `backend/cmd/server/docs/`

## CI/CD

### GitHub Actions
- **File:** `.github/workflows/ci.yml`
- **Trigger:** Push to `main`/`develop`, PRs to `main`
- **Jobs:**
  - `vet` — `go vet ./...` (replaces golangci-lint, incompatible with Go 1.26)
  - `backend-tests` — Unit tests with race detection + coverage threshold
- **Dependency:** Uses `actions/setup-go@v5` with Go version from `go.mod`

### Vercel
- **Target:** Frontend SPA deployment
- **Config:** `vercel.json` (build uses `corepack yarn` for Yarn 4 compatibility)
- **Build Output:** `frontend/dist/`

## Webhooks & Callbacks

**Incoming:**
- None detected (payment processing is handled synchronously, no external payment gateway integration)

**Outgoing:**
- None detected (no outbound webhook system)

## Environment Configuration

**Required Environment Variables:**
| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `postgres` | PostgreSQL user |
| `DB_PASSWORD` | `academio` | PostgreSQL password |
| `DB_NAME` | `academio` | PostgreSQL database |
| `JWT_SECRET` | `change-me-in-production` | JWT signing key |
| `ENCRYPTION_KEY` | `""` | AES-256-GCM key for tenant DB credential encryption |
| `REDIS_ADDR` | `localhost:6379` | Redis address |
| `APP_SECRET` | `""` | CSRF token signing key |

**Optional (Integration-Specific):**
| Variable | Purpose |
|----------|---------|
| `SENDGRID_API_KEY` | SendGrid email delivery |
| `TWILIO_ACCOUNT_SID` | Twilio SMS account |
| `TWILIO_AUTH_TOKEN` | Twilio SMS auth |
| `TWILIO_FROM_NUMBER` | Twilio sender number |
| `AI_GEMINI_API_KEY` | Google Gemini AI |
| `AI_OPENAI_API_KEY` | OpenAI API |
| `AI_QDRANT_URL` | Qdrant vector DB |
| `S3_REGION`, `S3_BACKUP_BUCKET` | S3 backup storage |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | S3 credentials |
| `VITE_GOOGLE_MAPS_API_KEY` | Google Places autocomplete |
| `VITE_MAPBOX_ACCESS_TOKEN` | Mapbox maps |
| `OTEL_ENDPOINT` | OpenTelemetry collector |

**Secrets Location:**
- `backend/.env` file (not committed)
- In production, set via environment (Vercel env vars, Docker secrets, etc.)

## External APIs Consumed (Summary)

| Service | Type | SDK/Client | Authentication |
|---------|------|------------|---------------|
| Google Gemini | LLM | `google.golang.org/genai` | API key (`AI_GEMINI_API_KEY`) |
| OpenAI | LLM | `github.com/openai/openai-go` | API key (`AI_OPENAI_API_KEY`) |
| S3-compatible | Object Storage | `github.com/aws/aws-sdk-go-v2/service/s3` | Access key + Secret key |
| SendGrid | Email | Manual HTTP (SDK not used) | API key (`SENDGRID_API_KEY`) |
| Twilio | SMS | Manual HTTP (SDK not used) | Account SID + Auth Token |
| Google Places | Place Autocomplete | Browser-side JS API | API key (`VITE_GOOGLE_MAPS_API_KEY`) |
| Qdrant | Vector Database | REST API (HTTP client) | Optional API key |
| OpenTelemetry Collector | Trace Export | OTLP gRPC/HTTP | None (insecure by default) |

---

*Integration audit: 2026-07-18*
