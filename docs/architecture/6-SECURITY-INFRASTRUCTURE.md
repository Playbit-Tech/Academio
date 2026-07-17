# SchoolCare v3 — Security, Multi-Tenant & Infrastructure Architecture

---

## 1. SECURITY ARCHITECTURE

### 1.1 Defense In Depth Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  L7: Application Security                                           │
│  ├── Input Validation (Zod/Validator)                               │
│  ├── Output Encoding                                                │
│  ├── CSRF Protection                                                │
│  ├── Rate Limiting (per-IP, per-user, per-tenant)                   │
│  ├── SQL Injection Prevention (GORM parameterized)                  │
│  ├── RBAC + ABAC Authorization                                      │
│  ├── Audit Logging (all mutations)                                  │
│  └── API Schema Validation (OpenAPI)                                │
├─────────────────────────────────────────────────────────────────────┤
│  L6: API Security                                                   │
│  ├── JWT Access + Refresh Tokens                                    │
│  ├── OAuth2 (for integrations)                                      │
│  ├── API Keys (for service-to-service)                              │
│  ├── Idempotency Keys                                               │
│  ├── Request Signing (webhooks)                                     │
│  └── CORS with origin whitelist                                     │
├─────────────────────────────────────────────────────────────────────┤
│  L5: Authentication & Authorization                                 │
│  ├── Multi-factor Authentication (TOTP)                             │
│  ├── Password Policy (bcrypt, min length, rotation)                 │
│  ├── Session Management (Redis-backed)                              │
│  ├── RBAC (Role-Based Access Control)                               │
│  ├── ABAC (Attribute-Based for data-level permissions)              │
│  └── Tenant Isolation (automatic by context)                        │
├─────────────────────────────────────────────────────────────────────┤
│  L4: Data Security                                                  │
│  ├── Encryption at Rest (PostgreSQL TDE / disk encryption)          │
│  ├── Encryption in Transit (TLS 1.3)                                │
│  ├── PII Data Encryption (column-level encryption)                  │
│  ├── Data Masking (for non-privileged users)                        │
│  ├── Backup Encryption                                              │
│  └── Secure Deletion (GDPR right to be forgotten)                   │
├─────────────────────────────────────────────────────────────────────┤
│  L3: Network Security                                               │
│  ├── VPC / Network Segmentation                                     │
│  ├── Security Groups / Firewall Rules                               │
│  ├── WAF (Web Application Firewall)                                 │
│  ├── DDoS Protection                                                │
│  └── Private Subnets for DB/Cache                                   │
├─────────────────────────────────────────────────────────────────────┤
│  L2: Infrastructure Security                                        │
│  ├── Container Security (Docker scanning)                           │
│  ├── Secrets Management (HashiCorp Vault / K8s Secrets)             │
│  ├── Regular Security Updates                                       │
│  ├── Immutable Infrastructure                                       │
│  └── Network Policies (K8s)                                         │
├─────────────────────────────────────────────────────────────────────┤
│  L1: Physical Security                                              │
│  ├── Cloud Provider Security (AWS/Azure/GCP)                        │
│  └── SOC 2 / ISO 27001 Certified Infrastructure                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Authentication Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Client  │         │ API/Gin  │         │  Redis   │
└────┬─────┘         └────┬─────┘         └────┬─────┘
     │                    │                     │
     │ POST /auth/login   │                     │
     │ {email, password}  │                     │
     ├───────────────────►│                     │
     │                    │ Verify credentials  │
     │                    ├─────► DB ────────►  │
     │                    │                     │
     │                    │ Generate tokens     │
     │                    │ Access: 15min       │
     │                    │ Refresh: 7d         │
     │                    │                     │
     │ {access_token,     │ Store refresh       │
     │  refresh_token}    ├──────────►          │
     │◄───────────────────┤ SET refresh:{id}    │
     │                    │                     │
     │                    │                     │
     │ GET /api/v2/users  │                     │
     │ Authorization:     │                     │
     │ Bearer access_token│                     │
     ├───────────────────►│                     │
     │                    │ Validate JWT        │
     │                    │ (stateless)         │
     │                    │                     │
     │                    │ Check blacklist     │
     │                    ├──────────►          │
     │                    │◄──────────          │
     │                    │                     │
     │                    │ Extract school_id   │
     │                    │ Apply RBAC          │
     │                    │                     │
     │ {success, data}    │                     │
     │◄───────────────────┤                     │
     │                    │                     │
     │ POST /auth/refresh │                     │
     │ {refresh_token}    │                     │
     ├───────────────────►│                     │
     │                    │ Verify in Redis     │
     │                    ├──────────►          │
     │                    │◄──────────          │
     │                    │ Rotate tokens       │
     │                    │ (old invalidated)   │
     │                    │                     │
     │ {new_access,       │                     │
     │  new_refresh}      │                     │
     │◄───────────────────┤                     │
```

### 1.3 Authorization Model

```
RBAC (Role-Based) + ABAC (Attribute-Based)

Core Roles:
├── super-admin        → Full system access (SchoolCare staff)
├── admin              → School-level admin (all modules)
├── principal          → School leadership (academic, reports)
├── teacher            → Their classes, subjects, students
├── student            → Own data, courses, results
├── parent             → Their children's data
├── accountant         → Financial modules only
├── librarian          → Library module only
├── hr                 → HR & Payroll only
├── admissions_officer → Admissions module only
├── counselor          → Career guidance, student support
├── transport_mgr      → Transport module only
├── hostel_mgr         → Hostel module only
└── alumni             → Alumni portal, own profile

Permission Levels:
├── OWN     → Own records only
├── LEVEL   → Records within assigned level(s)
├── DEPT    → Records within department
├── SCHOOL  → All records in school
├── CAMPUS  → All records in campus
└── SYSTEM  → All records (super-admin)

Data Filtering:
- All queries automatically filter by tenant_id (school_id)
- Teachers see only their assigned students/subjects
- Parents see only their children
- Students see only themselves
```

### 1.4 Audit Logging

```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    action VARCHAR(50) NOT NULL,        -- created, updated, deleted, viewed, exported
    resource_type VARCHAR(50) NOT NULL,  -- student, fee, result, etc.
    resource_id BIGINT,
    changes JSONB,                       -- before/after diff
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexed for fast querying
CREATE INDEX idx_audit_tenant_resource ON audit_logs(tenant_id, resource_type, resource_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
```

### 1.5 Data Privacy & Compliance

```
GDPR Capabilities:
├── Right to Access → Export all user data
├── Right to Rectification → Edit any personal data
├── Right to Erasure → GDPR delete (anonymize or remove)
├── Right to Portability → JSON/CSV export
├── Data Processing Records → Full audit trail
└── Consent Management → Opt-in/opt-out tracking

Data Classification:
├── PUBLIC    → School name, address, programs
├── INTERNAL  → Class schedules, curriculum
├── SENSITIVE → Student grades, attendance
├── PII       → Names, emails, phone numbers, DOB
└── RESTRICTED→ Medical records, disciplinary actions

Encryption:
├── At Rest: AES-256 (PostgreSQL TDE or disk encryption)
├── In Transit: TLS 1.3 minimum
├── PII Columns: pgcrypto column-level encryption
└── Backups: AES-256 encrypted
```

---

## 2. MULTI-TENANT STRATEGY

### 2.1 Tenant Isolation Model (Current Implementation)

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT ARCHITECTURE                           │
│                                                                  │
│  Schema-Per-Tenant (Implemented)                                │
│  ├── Single PostgreSQL database, per-school schemas             │
│  ├── Each school's data lives in `school_{id}` schema           │
│  ├── GORM `SchemaTablePrefix` plugin auto-prefixes table names  │
│  ├── ── `db.Find(&students)` → `SELECT * FROM school_42.students`
│  ├── `SET LOCAL search_path` for migration isolation            │
│  ├── Cross-schema FK constraints: `students.user_id` → `public.users`
│  ├── `User` and `School` tables in shared `public` schema       │
│  ├── Schema name cached in Redis via `TenantResolutionService`  │
│  ├── No per-school database connections (single connection pool) │
│  └── TenantDBResolver middleware injects schema-scoped `*gorm.DB`
│                                                                  │
│  Legacy: Database-Per-Tenant (retired)                          │
│  ├── `ConnectionManager` kept for CLI tooling backward compat   │
│  ├── No longer used at runtime                                  │
│  └── All new deployments use schema-per-tenant                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Tenant Resolution Middleware (Implemented)

```go
// Middleware chain for tenant resolution
func TenantDBResolver() gin.HandlerFunc {
    return func(c *gin.Context) {
        schoolID := GetSchoolID(c)
        if schoolID == 0 {
            c.Next()
            return
        }

        // Resolve schema name from Redis cache or DB
        tc, err := resolutionService.Resolve(c.Request.Context(), schoolID)
        if err != nil {
            c.AbortWithStatusJSON(500, ...)
            return
        }

        // Create schema-scoped GORM session
        repos, err := tenantDBRepoFactory.ForSchoolSchema(
            c.Request.Context(), schoolID, tc.SchemaName,
        )
        if err != nil {
            c.AbortWithStatusJSON(500, ...)
            return
        }
        c.Set(string(CtxKeyTenantRepos), repos)
        c.Next()
    }
}
```

**Resolution flow**:
1. School ID extracted from JWT claims (authenticated routes) or URL param
2. `TenantResolutionService.Resolve(ctx, schoolID)` checks Redis cache first
3. On cache miss: queries `schools` table in `public` schema → caches `schema_name` in Redis
4. `RepositoryFactory.ForSchoolSchema(ctx, schoolID, schemaName)` creates a `SchemaDB` wrapper
5. `SchemaDB.DB()` returns a GORM session with `schema_table_prefix` set in the session context
6. `SchemaTablePrefix` GORM plugin prepends the schema to every table name in queries

### 2.3 Tenant Configuration Model

```go
type TenantConfig struct {
    ID              uint            `json:"id"`
    Name            string          `json:"name"`
    Slug            string          `json:"slug"`
    Domain          string          `json:"domain"`
    Plan            string          `json:"plan"`       // starter, growth, premium, enterprise
    Status          string          `json:"status"`     // active, suspended, trial, cancelled
    Settings        json.RawMessage `json:"settings"`
    Features        json.RawMessage `json:"features"`   // feature flags per plan
    StorageQuota    int64           `json:"storage_quota"`
    StudentLimit    int             `json:"student_limit"`
    AIQuota         int             `json:"ai_quota"`   // daily AI requests
    CustomDomain    string          `json:"custom_domain"`
    AllowedIPs      []string        `json:"allowed_ips"`
    DataRetentionDays int           `json:"data_retention_days"`
}
```

### 2.4 Feature Flag System

```go
type FeatureFlags struct {
    // By module
    Admissions    bool `json:"admissions"`
    CBA           bool `json:"cba"`
    LMS           bool `json:"lms"`
    Alumni        bool `json:"alumni"`
    CareerGuide   bool `json:"career_guide"`
    AIAssistant   bool `json:"ai_assistant"`
    HR            bool `json:"hr"`
    Finance       bool `json:"finance"`
    Library       bool `json:"library"`
    Hostel        bool `json:"hostel"`
    Transport     bool `json:"transport"`
    Inventory     bool `json:"inventory"`
    ParentPortal  bool `json:"parent_portal"`
    WhatsApp      bool `json:"whatsapp"`
    SMS           bool `json:"sms"`
    BI            bool `json:"bi"`
    MobileApps    bool `json:"mobile_apps"`
    CustomDomain  bool `json:"custom_domain"`
    AuditLog      bool `json:"audit_log"`
    API           bool `json:"api"`        // API access tier
}
```

---

## 3. INFRASTRUCTURE ARCHITECTURE

### 3.1 Docker Compose (Development)

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
    environment:
      - APP_PORT=8080
      - DB_HOST=postgres
      - REDIS_ADDR=redis:6379
      - QDRANT_HOST=qdrant:6333
    volumes:
      - uploads_data:/app/uploads

  postgres:
    image: postgres:alpine
    environment:
      POSTGRES_DB: schoolcare
      POSTGRES_USER: schoolcare
      POSTGRES_PASSWORD: schoolcare
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U schoolcare"]
      interval: 5s

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: schoolcare
      MINIO_ROOT_PASSWORD: schoolcare123
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"

  # Optional for development
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    ports:
      - "8123:8123"
      - "9002:9000"
    volumes:
      - clickhouse_data:/var/lib/clickhouse

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  minio_data:
  clickhouse_data:
  uploads_data:
```

### 3.2 Kubernetes Deployment (Production)

```yaml
# Key K8s manifests needed:
apiVersion: apps/v1
kind: Deployment
metadata:
  name: schoolcare-api
spec:
  replicas: 3  # HPA: min=3, max=20 (CPU > 70%)
  selector:
    matchLabels:
      app: schoolcare-api
  template:
    spec:
      containers:
        - name: api
          image: schoolcare/api:latest
          ports:
            - containerPort: 8080
          env:
            - name: APP_ENV
              value: "production"
            - name: DB_HOST
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: host
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 2Gi
          livenessProbe:
            httpGet:
              path: /livez
              port: 8080
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8080
          startupProbe:
            httpGet:
              path: /livez
              port: 8080
            initialDelaySeconds: 10
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: schoolcare-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: schoolcare-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### 3.3 CI/CD Pipeline

```
GitHub Actions Workflow:
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Lint    │───►│  Build   │───►│   Test   │───►│  Docker  │
│ golangci │    │ go build │    │ go test  │    │  Build   │
│ eslint   │    │ tsc      │    │ vitest   │    │          │
└──────────┘    └──────────┘    └──────────┘    └────┬─────┘
                                                      │
                                                      ▼
                                              ┌──────────┐
                                              │  Push to │
                                              │  ECR/Docker│
                                              └────┬─────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │  Deploy to   │
                                           │  Staging     │
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │  Integration │
                                           │    Tests     │
                                           └──────┬───────┘
                                                   │
                                                   ▼
                                           ┌──────────────┐
                                           │  Deploy to   │
                                           │  Production  │
                                           └──────────────┘
```

### 3.4 Monitoring & Observability

```
Metrics (Prometheus):
├── API: Request rate, latency (p50/p95/p99), error rate, status codes
├── DB: Connection pool, query latency, slow queries (>100ms)
├── Redis: Hit rate, memory, connected clients
├── Queue: Queue depth, processing time, failure rate
├── AI: Request rate, latency, token usage, cost per tenant
├── Business: Active students, enrollments, revenue, AI usage
└── System: CPU, memory, disk, network, goroutines

Logging (Structured JSON):
├── All API requests (method, path, status, latency, user_id, tenant_id)
├── All database queries (SLOW_QUERY tag for >100ms)
├── All AI interactions (prompt, response, tokens, cost)
├── All mutations (with audit context)
└── All errors with stack traces

Tracing (OpenTelemetry):
├── Distributed tracing across services
├── Trace ID propagation (X-Request-ID header)
├── Span for: HTTP, DB query, Redis, AI call, Queue job
└── Integration with Jaeger or Grafana Tempo

Alerting:
├── P0: API down, DB down, error rate >5%
├── P1: Latency p99 > 2s, queue depth > 1000
├── P2: AI cost > budget, disk > 80%
└── P3: Slow queries, cache hit rate < 80%

Dashboards (Grafana):
├── Executive Dashboard (DAU, revenue, active schools)
├── API Performance Dashboard (latency, errors, throughput)
├── Infrastructure Dashboard (CPU, memory, disk)
├── AI Dashboard (usage, cost, latency per model)
├── Business Dashboard (enrollments, revenue, retention)
└── Tenant Health Dashboard (per-customer metrics)
```

---

## 4. MOBILE API STRATEGY

### 4.1 API Design for Mobile

```
Optimizations for Mobile:
├── GraphQL Federation (future) — reduce N+1 queries
├── Response compression (gzip)
├── Field selection (?fields=id,name,email)
├── Sparse field sets per app (student app needs different fields)
├── Cursor-based pagination for infinite scroll
├── ETags for conditional requests
├── Batch endpoints for offline sync
├── WebSocket for real-time updates
└── SSE for streaming AI responses

Mobile-Specific APIs:
├── POST /api/v2/mobile/sync      → Offline data sync
├── GET  /api/v2/mobile/init      → Initial app state (less data)
├── POST /api/v2/mobile/logs      → Client-side error logs
├── GET  /api/v2/mobile/config    → Feature flags, app config
└── POST /api/v2/mobile/feedback  → In-app feedback
```

### 4.2 Mobile App Architecture

```
Each mobile app uses:
├── React Native (Expo)
├── Zustand (state management, shared with web)
├── TanStack Query (server state, caching, offline)
├── WebSocket client (real-time)
├── SecureStore (JWT tokens)
├── MMKV (fast local storage)
└── expo-notifications (push)

Student App:
├── Dashboard (attendance, grades, next classes)
├── Timetable
├── AI Academic Assistant
├── CBA (take exams)
├── LMS (courses, lessons)
├── Fees (view, pay)
├── Profile
├── Notifications
└── Communication (messages)

Parent App:
├── Dashboard (children overview)
├── Child Progress (grades, attendance)
├── AI Parent Assistant
├── Fee Status & Payment
├── School Announcements
├── Timetable (view only)
├── Communication (teachers)
└── Notifications

Teacher App:
├── Dashboard (classes, upcoming)
├── My Classes (students, attendance)
├── Mark Attendance
├── Grade Entry
├── Timetable
├── AI Teacher Assistant
├── CBA (create exams)
├── LMS (manage courses)
├── Communication (parents, students)
└── Notifications

Admin App:
├── Dashboard (school metrics)
├── Student Management
├── Teacher Management
├── Fee Management
├── Admissions Dashboard
├── Reports
├── AI Analytics
├── Communication (broadcast)
└── Settings
```

---

## 5. NEW PACKAGE DEPENDENCIES

```go
// Additional Go dependencies for SchoolCare v3

// AI & NLP
github.com/sashabaranov/go-openai     // OpenAI API client
github.com/liushuangls/go-anthropic   // Anthropic API client
github.com/tmc/langchaingo            // LangChain for Go
github.com/qdrant/go-client            // Qdrant vector DB client

// Communication
github.com/twilio/twilio-go            // SMS, WhatsApp
github.com/sendgrid/sendgrid-go        // Email
github.com/dgrijalva/jwt-go/v4         // Already have v5; keep

// Queue & Events
github.com/hibiken/asynq               // Distributed task queue (Redis)
github.com/segmentio/kafka-go          // Kafka client (future)

// WebSockets
github.com/gorilla/websocket           // WebSocket library
github.com/coder/websocket             // Alternative: cleaner websocket

// Search
github.com/meilisearch/meilisearch-go  // MeiliSearch client

// Monitoring
go.opentelemetry.io/otel               // OpenTelemetry
go.opentelemetry.io/otel/exporters/otlp/otlptrace
go.opentelemetry.io/otel/sdk

// Storage
github.com/aws/aws-sdk-go-v2/service/s3  // S3/MinIO
github.com/minio/minio-go/v7

// Security
github.com/pquerna/otp/totp            // TOTP for MFA
golang.org/x/time/rate                  // Rate limiting enhancements

// Utilities
github.com/google/uuid                  // UUID generation
github.com/rs/xid                       // Unique ID generation
github.com/jszwec/csvutil               // CSV parsing
github.com/xuri/excelize/v2             // Excel file generation
github.com/jung-kurt/gofpdf            // PDF generation (report cards)
github.com/ledongthuc/pdf              // PDF reading/parsing
```
