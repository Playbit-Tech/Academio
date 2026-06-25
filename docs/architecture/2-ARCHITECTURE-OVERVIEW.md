# SchoolCare v3 — Architecture Overview

---

## 1. HIGH-LEVEL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                      │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Web SPA  │  │ Student  │  │ Parent   │  │ Teacher  │  │ Admin Mobile │  │
│  │ (React)  │  │ Mobile   │  │ Mobile   │  │ Mobile   │  │              │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │             │              │             │               │          │
├───────┴─────────────┴──────────────┴─────────────┴───────────────┴──────────┤
│                          API GATEWAY / CDN                                    │
│                        (CloudFront / Kong / KrakenD)                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                     RATE LIMITING | AUTH | ROUTING | CACHING         │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────────────────┤
│                        SERVICE LAYER                                          │
│                                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────────┐  │
│  │  Core   │  │Admission│  │  LMS    │  │  CBA    │  │ Communication    │  │
│  │  SIS    │  │& Enroll │  │ Module  │  │ Engine  │  │ Hub              │  │
│  ├─────────┤  ├─────────┤  ├─────────┤  ├─────────┤  ├──────────────────┤  │
│  │Academics│  │Finance  │  │Library  │  │ Hostel  │  │ Transport        │  │
│  │         │  │& Billing│  │         │  │         │  │                  │  │
│  ├─────────┤  ├─────────┤  ├─────────┤  ├─────────┤  ├──────────────────┤  │
│  │  HR &   │  │ Alumni  │  │ Career  │  │Inventory│  │ Analytics & BI   │  │
│  │ Payroll │  │         │  │ Guidance│  │ & Assets│  │                  │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └──────────────────┘  │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                          AI SERVICE LAYER                                     │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ AI Gateway  │  │ RAG Engine  │  │ AI Agents   │  │ NL Search        │  │
│  │(LLM Router) │  │(Vector DB)  │  │(LangChain)  │  │ Engine           │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────────┘  │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                        EVENT STREAM / MESSAGE BUS                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │          Redis Streams → Kafka (at scale)                            │     │
│  │          Events: student.created, fee.paid, result.approved, etc.    │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                             │
│                                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │PostgreSQL│  │  Redis   │  │  MinIO   │  │ Qdrant   │  │   ClickHouse │  │
│  │  (Main)  │  │ (Cache)  │  │ (Object) │  │(Vector)  │  │ (Analytics)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MODULAR MONOLITH → MICROSERVICES EVOLUTION

### Phase 1: Hardened Modular Monolith (Months 1-6)
Keep the proven Go/Gin modular monolith. All modules in `internal/modules/` with clear boundaries.

**Advantages for early stage**:
- Simple deployment (single binary)
- Transactional consistency across modules
- No network overhead between modules
- Fast development velocity
- Easier debugging and testing

```
┌─────────────────────────────────────────────────────┐
│                  API Server (Single Binary)          │
│                                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│  │Auth  │ │User  │ │School│ │Acad  │ │Finance│ ... │
│  │Module│ │Module│ │Module│ │Module│ │Module│     │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘     │
│     └────────┴────────┴────────┴────────┴──        │
│                      │                              │
│              ┌───────┴────────┐                     │
│              │  Shared Kernel │                     │
│              │ (pkg/, errors, │                     │
│              │  middleware)   │                     │
│              └────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

### Phase 2: Domain Service Extraction (Months 6-12)
Extract high-traffic or high-complexity domains into independent services.

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ API      │  │ Auth     │  │ AI       │  │ CBA      │
│ Gateway  │─►│ Service  │  │ Service  │  │ Service  │
│ (Kong)   │  └──────────┘  └──────────┘  └──────────┘
│          │  ┌──────────┐  ┌──────────┐  ┌──────────┐
│          │─►│ Core SIS │  │ Finance  │  │ Comms    │
│          │  │ Service  │  │ Service  │  │ Service  │
│          │  └──────────┘  └──────────┘  └──────────┘
└──────────┘
```

### Phase 3: Full Microservices + Event Sourcing (12+ months)
Complete separation with event-driven communication.

---

## 3. MODULE ARCHITECTURE (Phase 1 - Modular Monolith)

Each module follows a strict layered pattern:

```
internal/modules/<domain>/
├── handler.go       # HTTP layer (Gin handlers)
├── handler_test.go  # Handler tests
├── service.go       # Business logic
├── service_test.go  # Service tests
├── repository.go    # Data access (GORM)
├── repository_test.go
├── dto.go           # Request/Response DTOs
├── events.go        # Domain events (publisher)
├── events_test.go
└── mock_repository_test.go  # Mock for service tests
```

### Dependency Flow
```
Handler → Service (interface) → Repository (interface) → GORM/DB
                            ↓
                   Events Publisher → Event Bus
                            ↓
                   External Services (AI, SMS, Email, etc.)
```

### Module Dependency Rules
1. Modules can depend on `pkg/` (shared kernel) freely
2. Modules can depend on `internal/errors/`, `internal/middleware/`
3. Modules depend on each other ONLY via interfaces (e.g., `UserRepository` interface in `rbac/`)
4. No circular dependencies between modules
5. Each module owns its data (table or table group)

---

## 4. NEW MODULES (Beyond Existing)

The following new modules will be added to `internal/modules/`:

| Module | Description | Dependencies |
|--------|-------------|--------------|
| `admission` | Online admissions, applications, offers | user, school, academic |
| `cba` | Computer-Based Assessment engine | academic, user, school |
| `lms` | Learning Management System | academic, user, multimedia |
| `ai` | AI Gateway, agents, NL search | all (via interfaces) |
| `communication` | SMS, Email, Push, WhatsApp, in-app | user, school |
| `reportcard` | Digital report card generation | academic, score, result |
| `parent` | Parent engagement portal | user, student, academic |
| `library` | Book/ebook management | school |
| `hostel` | Room/bed management | school, user, student |
| `transport` | Bus, route, driver management | school, user |
| `inventory` | Asset management | school |
| `hr` | Staff records, payroll, leave | user, school |
| `finance` | GL, budgeting, accounting | school, bill, payment |
| `alumni` | Alumni directory, engagement | user, school |
| `career` | Career guidance, job board | user, alumni |
| `bi` | Business intelligence, dashboards | all (read-only aggregate) |
| `analytics` | Student performance analytics | academic, score, result |
| `notification` | Real-time WebSocket notifications | all |

---

## 5. BACKEND FOLDER STRUCTURE (Evolved)

```
backend/
├── cmd/server/                    # Entry point
│   ├── main.go                    # Bootstrap
│   └── docs/                      # Swagger docs (auto-generated)
│
├── internal/
│   ├── config/
│   │   └── config.go              # Config (enhanced with AI, Comms, Queue, etc.)
│   │
│   ├── database/
│   │   ├── postgres.go            # GORM connection with pooling
│   │   ├── redis.go               # go-redis client
│   │   ├── queues.go              # Redis Streams / Asynq client
│   │   ├── vector.go              # Qdrant/Vector DB client
│   │   ├── clickhouse.go          # Analytics DB client
│   │   └── migrations/
│   │       ├── migrations.go      # Migration runner
│   │       ├── phase1.go          # Existing auto-migrate
│   │       ├── phase2.go          # Existing manual SQL
│   │       ├── phase3.go          # NEW: Admissions, CBA, LMS tables
│   │       ├── phase4.go          # NEW: Library, Hostel, Transport, Inventory
│   │       ├── phase5.go          # NEW: HR, Finance, Alumni
│   │       └── seed/              # Seed data scripts
│   │
│   ├── model/
│   │   ├── base.go                # BaseModel, Pagination (enhanced)
│   │   ├── enums.go               # Enums (expanded)
│   │   ├── tenant.go              # Tenant model
│   │   ├── user.go                # User, UserInfo, Role (enhanced)
│   │   ├── school.go              # School (enhanced), Campus
│   │   ├── subject.go             # Subject
│   │   ├── level.go               # Level
│   │   ├── session.go             # Academic Session
│   │   ├── curriculum.go          # Curriculum
│   │   ├── assessment.go          # Assessment
│   │   ├── attendance.go          # Attendance
│   │   ├── score.go               # Score
│   │   ├── result.go              # Result
│   │   ├── timetable.go           # Timetable
│   │   ├── fee.go                 # Fee, Bill
│   │   ├── payment.go             # Payment
│   │   ├── multimedia.go          # Multimedia
│   │   ├── invitation.go          # Invitation
│   │   │
│   │   ├── admission/             # NEW: Admission models
│   │   │   ├── application.go     # Application forms
│   │   │   ├── intake.go          # Admission intakes
│   │   │   ├── screening.go       # Screening results
│   │   │   ├── offer.go           # Admission offers
│   │   │   └── enrollment.go      # Enrollment records
│   │   │
│   │   ├── cba/                   # NEW: CBA models
│   │   │   ├── question.go        # Question bank
│   │   │   ├── exam.go            # Exam definitions
│   │   │   ├── exam_session.go    # Student exam sessions
│   │   │   ├── proctoring.go      # Proctoring logs
│   │   │   └── grading.go         # Auto-grading rules
│   │   │
│   │   ├── lms/                   # NEW: LMS models
│   │   │   ├── course.go          # Courses
│   │   │   ├── lesson.go          # Lessons
│   │   │   ├── module.go          # Course modules
│   │   │   ├── enrollment.go      # Course enrollment
│   │   │   ├── assignment.go      # Assignments
│   │   │   └── discussion.go      # Discussions
│   │   │
│   │   ├── communication/         # NEW: Communication models
│   │   │   ├── template.go        # Message templates
│   │   │   ├── message.go         # Outbound messages
│   │   │   ├── campaign.go        # Campaign management
│   │   │   └── webhook.go         # Inbound webhooks
│   │   │
│   │   ├── library/               # NEW: Library models
│   │   │   ├── book.go            # Books
│   │   │   ├── ebook.go           # E-books
│   │   │   ├── borrowing.go       # Borrow/return records
│   │   │   └── digital_resource.go
│   │   │
│   │   ├── hostel/                # NEW: Hostel models
│   │   │   ├── hostel.go          # Hostel definitions
│   │   │   ├── room.go            # Rooms
│   │   │   ├── bed.go             # Beds
│   │   │   ├── allocation.go      # Student allocations
│   │   │   └── maintenance.go     # Maintenance requests
│   │   │
│   │   ├── transport/             # NEW: Transport models
│   │   │   ├── bus.go             # Buses
│   │   │   ├── route.go           # Routes
│   │   │   ├── stop.go            # Pickup/drop points
│   │   │   ├── driver.go          # Driver records
│   │   │   └── trip.go            # Trip logs
│   │   │
│   │   ├── inventory/             # NEW: Inventory models
│   │   │   ├── asset.go           # Assets
│   │   │   ├── category.go        # Asset categories
│   │   │   ├── assignment.go      # Asset assignments
│   │   │   └── maintenance.go     # Maintenance records
│   │   │
│   │   ├── hr/                    # NEW: HR models
│   │   │   ├── staff.go           # Staff records
│   │   │   ├── payroll.go         # Payroll records
│   │   │   ├── leave.go           # Leave requests
│   │   │   ├── attendance.go      # Staff attendance
│   │   │   ├── performance.go     # Performance reviews
│   │   │   └── recruitment.go     # Job postings, applications
│   │   │
│   │   ├── finance/               # NEW: Finance models
│   │   │   ├── account.go         # Chart of accounts
│   │   │   ├── transaction.go     # Journal entries
│   │   │   ├── budget.go          # Budgets
│   │   │   └── report.go          # Financial reports
│   │   │
│   │   ├── alumni/                # NEW: Alumni models
│   │   │   ├── alumnus.go         # Alumni records
│   │   │   ├── career.go          # Career/employment
│   │   │   ├── event.go           # Events & reunions
│   │   │   ├── mentorship.go      # Mentorship programs
│   │   │   ├── donation.go        # Donations
│   │   │   ├── campaign.go        # Fundraising campaigns
│   │   │   ├── verification.go    # Certificate/transcript requests
│   │   │   └── job.go             # Job board
│   │   │
│   │   ├── career/                # NEW: Career guidance models
│   │   │   ├── assessment.go      # Skills assessments
│   │   │   ├── recommendation.go  # Career/university recommendations
│   │   │   ├── roadmap.go         # Career roadmaps
│   │   │   └── scholarship.go     # Scholarship matching
│   │   │
│   │   ├── analytics/             # NEW: Analytics models
│   │   │   ├── snapshot.go        # Periodic data snapshots
│   │   │   ├── metric.go          # Metric definitions
│   │   │   ├── dashboard.go       # Dashboard definitions
│   │   │   └── report.go          # Report configurations
│   │   │
│   │   └── ai/                    # NEW: AI models
│   │       ├── conversation.go    # AI conversation history
│   │       ├── embedding.go       # Document embeddings
│   │       ├── prompt.go          # Prompt templates
│   │       └── agent.go           # Agent configurations
│   │
│   ├── middleware/                # Existing (enhanced)
│   │   ├── auth.go
│   │   ├── bodylimit.go
│   │   ├── cors.go
│   │   ├── error.go
│   │   ├── logger.go
│   │   ├── ratelimit.go
│   │   ├── requestid.go
│   │   ├── schoolid.go (→ tenant.go)
│   │   ├── security.go
│   │   ├── validate.go
│   │   ├── tenant.go              # NEW: Multi-tenant resolver
│   │   ├── audit.go               # NEW: Audit logging middleware
│   │   ├── feature.go             # NEW: Feature flag middleware
│   │   └── subscription.go        # NEW: Tier/plan enforcement
│   │
│   ├── router/
│   │   ├── router.go              # Route definitions (expanded)
│   │   └── setup.go               # DI (expanded with new modules)
│   │
│   ├── events/                    # NEW: Event system
│   │   ├── bus.go                 # Event bus interface
│   │   ├── redis_streams.go       # Redis Streams implementation
│   │   ├── kafka.go               # Kafka implementation (future)
│   │   ├── publisher.go           # Event publisher
│   │   ├── subscriber.go          # Event subscriber
│   │   ├── handler.go             # Event handler registry
│   │   └── events.go              # Domain event definitions
│   │
│   ├── ai/                        # NEW: AI Service
│   │   ├── gateway.go             # LLM provider abstraction
│   │   ├── openai.go              # OpenAI provider
│   │   ├── anthropic.go           # Anthropic provider
│   │   ├── rag.go                 # RAG engine
│   │   ├── embeddings.go          # Embedding service
│   │   ├── vector_store.go        # Vector DB interface
│   │   ├── qdrant.go              # Qdrant implementation
│   │   ├── agents/                # AI agents
│   │   │   ├── academic_assistant.go
│   │   │   ├── teacher_assistant.go
│   │   │   ├── parent_assistant.go
│   │   │   ├── career_guide.go
│   │   │   ├── enrollment_forecaster.go
│   │   │   └── risk_analyzer.go
│   │   ├── search/                # NL Search
│   │   │   ├── engine.go          # Search engine
│   │   │   ├── parser.go          # NL query parser
│   │   │   └── index.go           # Search index
│   │   └── prompts/               # Prompt templates
│   │       ├── templates.go       # Go embedded prompts
│   │       └── prompts.yaml       # Externalized prompts
│   │
│   ├── communication/             # NEW: Communication engine
│   │   ├── provider.go            # Provider interface
│   │   ├── sms.go                 # SMS (Twilio/AfricasTalking)
│   │   ├── email.go               # Email (SendGrid/Mailgun)
│   │   ├── push.go                # Push (FCM/APNs)
│   │   ├── whatsapp.go            # WhatsApp (Twilio/360dialog)
│   │   ├── inapp.go               # In-app notification
│   │   └── template.go            # Template rendering
│   │
│   ├── search/                    # NEW: Full-text search
│   │   ├── engine.go              # Search engine wrapper
│   │   └── index.go               # Index management
│   │
│   ├── queue/                     # NEW: Job queue
│   │   ├── client.go              # Queue client
│   │   ├── worker.go              # Worker pool
│   │   ├── tasks/                 # Task definitions
│   │   │   ├── send_email.go
│   │   │   ├── send_sms.go
│   │   │   ├── generate_report.go
│   │   │   ├── process_ai.go
│   │   │   └── sync_data.go
│   │   └── middleware.go          # Retry, logging, metrics
│   │
│   ├── websocket/                 # NEW: WebSocket hub
│   │   ├── hub.go                 # Connection hub
│   │   ├── client.go              # Client connection
│   │   ├── message.go             # Message types
│   │   └── rooms.go               # Room/channel management
│   │
│   └── modules/                   # Existing + new modules
│       ├── health/
│       ├── auth/
│       ├── user/
│       ├── school/
│       ├── invitation/
│       ├── academic/
│       ├── score/
│       ├── result/
│       ├── timetable/
│       ├── bill/
│       ├── payment/
│       ├── multimedia/
│       ├── rbac/
│       │
│       ├── admission/             # NEW
│       ├── cba/                   # NEW
│       ├── lms/                   # NEW
│       ├── parent/                # NEW
│       ├── communication/         # NEW
│       ├── reportcard/            # NEW
│       ├── library/               # NEW
│       ├── hostel/                # NEW
│       ├── transport/             # NEW
│       ├── inventory/             # NEW
│       ├── hr/                    # NEW
│       ├── finance/               # NEW
│       ├── alumni/                # NEW
│       ├── career/                # NEW
│       ├── analytics/             # NEW
│       ├── bi/                    # NEW
│       └── notification/          # NEW
│
│   ├── services/                  # Existing (enhanced)
│   │   ├── blacklist_service.go
│   │   ├── refresh_store.go
│   │   ├── user_cache.go
│   │   ├── tenant_service.go      # NEW
│   │   ├── billing_service.go     # NEW
│   │   └── plan_service.go        # NEW
│   │
│   └── jobs/                      # NEW: Scheduled jobs
│       ├── scheduler.go           # Job scheduler
│       ├── fee_reminder.go        # Daily fee reminders
│       ├── attendance_report.go   # Weekly attendance
│       ├── performance_snapshot.go # Periodic analytics
│       └── data_cleanup.go        # Log/data cleanup
│
├── pkg/                           # Existing (enhanced)
│   ├── jwt/jwt.go
│   ├── logger/logger.go
│   ├── password/bcrypt.go
│   ├── response/response.go
│   ├── storage/local.go
│   ├── storage/s3.go              # NEW
│   ├── validator/validator.go
│   ├── pagination/pagination.go   # NEW
│   ├── dateutil/date.go           # NEW
│   └── converter/converter.go     # NEW
│
├── scripts/
│   ├── migrate/
│   ├── seed/
│   ├── loadtest.sh (→ k6)
│   └── test_e2e.sh
│
├── Dockerfile
├── docker-compose.yml (expanded)
├── Makefile (expanded)
├── go.mod
└── .env
```

---

## 6. KEY ARCHITECTURAL DECISIONS

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend Language | Go (Gin) | Performance, simplicity, goroutines for concurrent requests |
| ORM | GORM | Mature, auto-migration, matches existing investment |
| Multi-tenancy | school_id column (shared schema) | Simplicity for 90% of customers; schema-per-tenant option for enterprise |
| Event Bus | Redis Streams → Kafka | Redis for current scale; Kafka for 1M+ students |
| Queue Worker | Redis Streams / Asynq | Lightweight, Go-native, no additional infra |
| AI Provider | Multi-provider abstraction (OpenAI + Anthropic) | Avoid vendor lock-in, best model per task |
| Vector DB | Qdrant | Rust-based, high performance, Docker-friendly |
| Search | MeiliSearch / Typesense | Typo-tolerant, fast, easy to deploy |
| Analytics DB | ClickHouse | Columnar storage for fast aggregations |
| Frontend | React 19 + TanStack Router + Zustand | Current investment, proven scalability |
| Mobile | React Native (Expo) | Code sharing with web, TypeScript reuse |
| Real-time | WebSocket + Server-Sent Events | Bidirectional communication for dashboards |
| Auth | JWT + Redis blacklist + OAuth2 | Stateless, scalable, refresh rotation |
| API Docs | OpenAPI 3.1 + Swagger | Industry standard, code generation |
