# SchoolCare v3 — Master Implementation Plan

> **Objective**: Evolve SchoolCare from a School ERP into a modern AI-Powered School Operating System
> **Strategy**: Additive-only changes — zero removal of existing functionality, all on `/api/v2/`
> **Timeline**: 18 months, 9 phases, parallel-track execution
> **Total Estimated Effort**: ~2,500-3,500 engineering hours

---

## DEPENDENCY GRAPH (Phase Level)

```
Phase 1A ───────────────────────────────────────────────────────────┐
   (Architecture Hardening)                                         │
                                                                    │
Phase 1B ────► Phase 3 ────► Phase 4 ────► Phase 6 ────► Phase 8 ──┤
(Admissions)     (AI Layer)     (CBA+LMS)     (Extended Mod) (BI)   │
                     │              │                               │
                     ▼              ▼                               │
               Phase 2 ◄──── Phase 3 provides AI for Admissions     │
               Phase 5 ◄──── Phase 4 provides CBA for exams         │
                                                                    │
Phase 7 (Alumni + Career) ◄──── Depends on Phase 1B (enrollments)   │
                                                                    │
Phase 9 (Mobile + Scale) ◄──── Depends on all API stabilization      │
```

---

## EXECUTION STRATEGY

- **Parallel Track A**: Architecture Hardening + Infrastructure (Phase 1A → 9)
- **Parallel Track B**: Core Domain Modules (Phase 1B → 2 → 5 → 6 → 7)
- **Parallel Track C**: AI & Engagement (Phase 3 → 4 → 8)
- **Parallel Track D**: Mobile & Scale (Phase 9)

---

# PHASE 1A: Architecture Hardening
**Timeline**: Months 1-2 | **Effort**: ~200-300 hrs | **Track**: A
**Risk Level**: Low (pure additions, no existing changes)
**Parallelizable**: Yes — most tasks are independent

## Description
Harden the existing monolith for production-grade SaaS: observability, security, performance baselines, and deployment readiness. No new features — only platform improvements.

## Dependencies
- **None** — can start immediately on existing codebase

## Steps

### Step 1A.1: Distributed Tracing & Structured Logging
- [ ] Add OpenTelemetry Go SDK dependency
- [ ] Instrument all Gin handlers with HTTP spans
- [ ] Instrument GORM queries with DB spans
- [ ] Instrument Redis calls with cache spans
- [ ] Add `X-Request-ID` propagation to all services
- [ ] Configure OTLP exporter (Jaeger/Grafana Tempo)
- [ ] Add structured logging context (tenant_id, user_id, request_id) to all log entries
- [ ] Set log levels per-module

**Files affected**:
- `internal/middleware/logger.go` — upgrade to structured + context-aware
- `internal/middleware/requestid.go` — ensure propagation through all goroutines
- `internal/database/postgres.go` — add tracing
- `go.mod` — add OpenTelemetry packages

**Verification**: `go test ./...` passes; traces visible in Jaeger; logs include tenant_id + user_id

---

### Step 1A.2: Distributed Rate Limiting
- [ ] Implement Redis-backed sliding window rate limiter
- [ ] Per-IP rate limit (existing in-memory → Redis)
- [ ] Per-user rate limit (based on JWT claims)
- [ ] Per-tenant rate limit (based on plan tier)
- [ ] Per-endpoint rate limit (sensitive endpoints get lower limits)
- [ ] Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- [ ] Configuration via environment variables per tier

**Files affected**:
- `internal/middleware/ratelimit.go` — rewrite to use Redis
- `internal/config/config.go` — add rate limit tier configs
- `internal/services/rate_limiter.go` — new file

**Verification**: `curl -v` shows rate limit headers; exceeding limit returns 429; Redis stores counters

---

### Step 1A.3: Audit Logging
- [ ] Create `audit_logs` table migration
- [ ] Create audit middleware that captures all mutations
- [ ] Record: user_id, tenant_id, action, resource_type, resource_id, before/after diff, IP, user_agent
- [ ] Add audit to: user creation/update, student mutations, fee/payment mutations, result/score changes
- [ ] Implement async audit log writing (non-blocking via channel)
- [ ] Add admin UI for audit log viewer (read-only, searchable)

**Files affected**:
- `internal/model/` — new audit_log model
- `internal/database/migrations/phase3.go` — audit_logs table
- `internal/middleware/audit.go` — new file
- `internal/router/router.go` — register middleware
- `internal/modules/audit/` — new module
- `frontend/src/routes/_dashboard/` — new audit page

**Verification**: Every mutation creates an audit record; viewer shows paginated, searchable logs

---

### Step 1A.4: Performance Baselines & Load Testing
- [ ] Add k6 to dev dependencies
- [ ] Write load test scripts for critical endpoints:
  - `POST /api/v2/auth/login`
  - `GET /api/v2/academic/attendance`
  - `POST /api/v2/academic/scores`
  - `GET /api/v2/users/list`
  - `GET /api/v2/bills`
- [ ] Establish baseline: requests/sec, p50/p95/p99 latency, error rate
- [ ] Add to CI: performance regression detection
- [ ] Document current performance envelope

**Files affected**:
- `scripts/loadtest/` — new directory with k6 scripts
- `.github/workflows/ci.yml` — add performance test step
- `docs/performance-baseline.md` — new file

**Verification**: k6 scripts run successfully; baselines documented; CI passes

---

### Step 1A.5: Health Check Enhancement
- [ ] Add component-level health checks:
  - PostgreSQL connectivity + query ability
  - Redis connectivity + ping
  - Queue readiness
  - AI service availability (when added)
- [ ] Return detailed JSON breakdown per component
- [ ] Add startup probe delay for migrations
- [ ] Add `/metrics` endpoint for Prometheus scraping
- [ ] Register Prometheus metrics: request count, latency, error count, active goroutines

**Files affected**:
- `internal/modules/health/handler.go` — enhance with component checks
- `internal/middleware/metrics.go` — new file
- `internal/router/router.go` — register `/metrics`

**Verification**: `/health` returns detailed component status; `/metrics` returns Prometheus-format data

---

### Step 1A.6: Docker Configuration
- [x] Dockerfile with multi-stage build (existing — verified/optimized)
- [x] docker-compose.yml with PostgreSQL + Redis services
- [~] K8s manifests — SKIPPED (not needed for current deployment target)

**Files affected**:
- `Dockerfile` — verified
- `docker-compose.yml` — verified

**Verification**: `docker compose up` starts all services

---

### Step 1A.7: OpenAPI 3.1 Specification
- [ ] Add annotations to all existing handlers for OpenAPI 3.1
- [ ] Ensure request/response DTOs are fully documented
- [ ] Add examples for all endpoints
- [ ] Generate OpenAPI spec as part of build
- [ ] Add Swagger UI serving (already present — verify/enhance)

**Files affected**:
- All handler files — add/update OpenAPI annotations
- `cmd/server/docs/` — regenerate
- `go.mod` — swaggo/swag already present

**Verification**: `make swagger` generates valid OpenAPI 3.1 spec; Swagger UI renders all endpoints

---

### Step 1A.8: Tenant Isolation Strategy Implementation
- [ ] Implement `TenantResolver` middleware (domain → subdomain → header → JWT)
- [ ] Ensure ALL queries filter by `school_id` (audit existing)
- [ ] Create tenant configuration table and model
- [ ] Implement feature flags per tenant (plan-based)
- [ ] Add tenant configuration caching (Redis)

**Files affected**:
- `internal/middleware/tenant.go` — new file
- `internal/model/tenant.go` — new model
- `internal/router/router.go` — register tenant middleware
- All repository files — verify school_id filter exists

**Verification**: All queries across all modules filter by school_id; tenant config loads on request

---

### Step 1A.9: Queue Infrastructure
- [ ] Add Asynq/Redis Streams dependency
- [ ] Create queue client and worker infrastructure
- [ ] Implement task definitions:
  - `SendEmailTask`
  - `SendSMSTask`
  - `GenerateReportTask`
  - `ProcessAITask`
  - `AuditLogTask`
- [ ] Add retry logic with exponential backoff
- [ ] Add dead letter queue for failed tasks
- [ ] Add worker pool with configurable concurrency

**Files affected**:
- `internal/queue/` — new directory
- `internal/config/config.go` — queue config
- `internal/database/redis.go` — queue connection
- `cmd/server/main.go` — start worker pool

**Verification**: Queue processes tasks; failed tasks retry and land in DLQ after max retries

---

### Step 1A.10: WebSocket Infrastructure
- [ ] Implement WebSocket hub (connection manager)
- [ ] Implement room/channel management (per-school, per-user)
- [ ] Implement message types: notification, data update, AI stream
- [ ] Add JWT authentication for WS connections
- [ ] Add heartbeat/ping-pong for connection health
- [ ] Implement reconnection with last-event-id

**Files affected**:
- `internal/websocket/` — new directory
- `internal/middleware/auth.go` — WebSocket JWT support
- `internal/router/router.go` — WS route

**Verification**: Client connects, joins room, receives real-time messages, reconnects on drop

---

### Phase 1A Exit Criteria
- [ ] Traces visible in Jaeger for all request paths
- [ ] Logs structured with tenant_id, user_id, request_id
- [ ] Rate limiting works per-IP, per-user, per-tenant
- [ ] Audit logs capture all mutations
- [ ] Load tests establish baselines
- [ ] Health checks return component-level status
- [~] K8s manifests — skipped (not needed for current deployment)
- [ ] OpenAPI spec generated, all endpoints documented
- [ ] All queries filter by school_id
- [ ] Queue processes tasks with retry
- [ ] WebSocket connections authenticated and receiving messages

---

# PHASE 1B: Admissions & Enrollment Module
**Timeline**: Months 2-4 (can start after Step 1A.8, parallel with 1A.9/1A.10)
**Effort**: ~300-400 hrs | **Track**: B
**Risk Level**: Medium (first new module — establishes pattern for all others)

## Description
Build the complete student admissions lifecycle: from public application portal to enrollment and student record creation. This is the prospecting and conversion engine.

## Dependencies
- Phase 1A Steps 1A.1-1A.8 (needs: config, tenant isolation, queue, audit)
- Existing: user module, school module, academic module

## Steps

### Step 1B.1: Database Migrations — Admissions Tables
- [ ] Create migration for `admission_intakes` table
- [ ] Create migration for `applications` table
- [ ] Create migration for `application_documents` table
- [ ] Create migration for `screening_results` table
- [ ] Create migration for `entrance_exam_results` table
- [ ] Create migration for `admission_offers` table
- [ ] Create migration for `enrollments` table
- [ ] Create indexes for all new tables

**Files affected**:
- `internal/database/migrations/phase3.go` — new migration file
- `internal/model/admission/` — model files

**Verification**: `make migrate` creates all tables; `make migrate-rollback` drops them cleanly

---

### Step 1B.2: Admission Models & DTOs
- [ ] Create `internal/model/admission/intake.go` — Intake model
- [ ] Create `internal/model/admission/application.go` — Application model
- [ ] Create `internal/model/admission/document.go` — ApplicationDocument model
- [ ] Create `internal/model/admission/screening.go` — ScreeningResult model
- [ ] Create `internal/model/admission/offer.go` — AdmissionOffer model
- [ ] Create `internal/model/admission/enrollment.go` — Enrollment model
- [ ] Define DTOs for all admission operations

**Files affected**:
- `internal/model/admission/` — new directory with model files

**Verification**: Models compile, GORM AutoMigrate works, DTOs serialize/deserialize correctly

---

### Step 1B.3: Admissions Module — Backend
- [ ] Create `internal/modules/admission/handler.go`
- [ ] Create `internal/modules/admission/service.go`
- [ ] Create `internal/modules/admission/repository.go`
- [ ] Create `internal/modules/admission/dto.go`
- [ ] Implement intake CRUD endpoints
- [ ] Implement application submission (public + authenticated)
- [ ] Implement document upload handler
- [ ] Implement screening workflow
- [ ] Implement offer creation and acceptance
- [ ] Implement enrollment → student record creation
- [ ] Register all routes in router

**Files affected**:
- `internal/modules/admission/` — new module
- `internal/router/setup.go` — register dependencies
- `internal/router/router.go` — register routes

**Verification**: Full admission flow works end-to-end: intake → apply → screen → offer → accept → enroll

---

### Step 1B.4: Admissions Frontend — Public Portal
- [ ] Create public application form page (no auth required)
- [ ] Create intake selection and program picker
- [ ] Create multi-step application wizard
- [ ] Create document upload component
- [ ] Create application status tracker
- [ ] Create responsive design (mobile-first)

**Files affected**:
- `frontend/src/routes/_public/apply.tsx` — new route
- `frontend/src/routes/_public/apply/` — sub-routes
- `frontend/src/components/admission/` — new components

**Verification**: Unauthenticated user can submit application; status page shows progress

---

### Step 1B.5: Admissions Frontend — Dashboard
- [ ] Create admissions dashboard (applications overview)
- [ ] Create application review/management page
- [ ] Create document verification UI
- [ ] Create screening workflow UI
- [ ] Create offer management UI
- [ ] Create enrollment dashboard with analytics
- [ ] Create admission analytics (conversion funnel, trends)

**Files affected**:
- `frontend/src/routes/_dashboard/admissions/` — new route group
- `frontend/src/hooks/useAdmissions.ts` — new hook
- `frontend/src/lib/stores/admission-store.ts` — optional store

**Verification**: Admin can manage full admission flow; charts display correct analytics

---

### Step 1B.6: AI Applicant Scoring (Basic)
- [ ] Create `internal/ai/gateway.go` — AI provider abstraction (OpenAI)
- [ ] Implement applicant scoring prompt template
- [ ] Implement eligibility assessment logic
- [ ] Wire scoring into application submission flow (async)
- [ ] Store AI score on application record
- [ ] Add score display to admissions dashboard

**Files affected**:
- `internal/ai/` — new directory
- `internal/ai/gateway.go` — AI provider interface
- `internal/ai/prompts/` — prompt templates
- `internal/modules/admission/service.go` — add AI scoring call

**Verification**: New applications receive AI score; score visible in dashboard

---

### Phase 1B Exit Criteria
- [ ] Complete admission flow: intake → apply → screen → exam → offer → accept → enroll
- [ ] Public application form accessible without authentication
- [ ] Document upload with verification workflow
- [ ] Enrollment automatically creates student record
- [ ] AI scoring runs asynchronously on submission
- [ ] Dashboard shows conversion funnel and analytics

---

# PHASE 2: AI Services Layer
**Timeline**: Months 3-6 (starts after Phase 1B, overlaps with Phase 1A final steps)
**Effort**: ~400-500 hrs | **Track**: C
**Risk Level**: High (new AI infrastructure, external API dependencies)

## Description
Build the complete AI service architecture: multi-provider gateway, RAG engine, agent framework, and first production AI agents.

## Dependencies
- Phase 1A Steps 1A.1, 1A.3, 1A.8, 1A.9 (needs: tracing, audit, tenant, queue)
- Phase 1B Step 1B.6 (basic AI gateway already scaffolded)

## Steps

### Step 2.1: AI Gateway — Multi-Provider
- [ ] Implement provider abstraction (OpenAI + Anthropic)
- [ ] Implement model routing logic (cost/quality optimization)
- [ ] Implement retry with fallback (provider A fails → provider B)
- [ ] Implement rate limiting per provider
- [ ] Implement token counting and cost tracking
- [ ] Implement streaming support (SSE)
- [ ] Add circuit breaker pattern for provider outages

**Files affected**:
- `internal/ai/gateway.go` — expand with multi-provider
- `internal/ai/openai.go` — OpenAI implementation
- `internal/ai/anthropic.go` — Anthropic implementation
- `internal/ai/model_router.go` — routing logic
- `internal/config/config.go` — AI provider configs

**Verification**: Requests route to correct provider; streaming works; cost tracked per request

---

### Step 2.2: RAG Engine
- [ ] Set up Qdrant vector database (Docker + Go client)
- [ ] Implement document chunking strategies
- [ ] Implement embedding generation service
- [ ] Implement vector search retrieval
- [ ] Implement hybrid search (vector + keyword)
- [ ] Create document ingestion pipeline (curriculum, policies, FAQs)
- [ ] Implement context assembly (retrieved chunks → LLM context)

**Files affected**:
- `internal/database/vector.go` — Qdrant client
- `internal/ai/rag/` — RAG engine files
- `internal/config/config.go` — Qdrant config
- `docker-compose.yml` — add Qdrant service

**Verification**: Documents ingested, chunked, embedded; queries return relevant context

---

### Step 2.3: AI Agent Framework
- [ ] Implement base agent interface
- [ ] Implement agent execution loop (plan → act → observe → reflect)
- [ ] Implement tool system (tools that agents can call)
- [ ] Implement conversation memory management
- [ ] Implement agent prompt templates
- [ ] Implement agent cost tracking and quotas

**Files affected**:
- `internal/ai/agents/base.go` — agent interface
- `internal/ai/agents/runner.go` — execution loop
- `internal/ai/conversation/` — conversation store

**Verification**: Agent can plan, use tools, respond; conversation history maintained

---

### Step 2.4: AI Academic Assistant (Student)
- [ ] Implement homework help agent (RAG + curriculum context)
- [ ] Implement subject tutoring agent (conversational)
- [ ] Implement study plan generator
- [ ] Implement academic guidance (policy-aware)
- [ ] Create conversation API endpoints
- [ ] Create streaming response endpoint (SSE)
- [ ] Create frontend chat interface component

**Files affected**:
- `internal/ai/agents/academic_tutor.go`
- `internal/modules/ai/handler.go` — chat endpoints
- `internal/router/router.go` — AI routes
- `frontend/src/components/ai/` — chat UI components
- `frontend/src/routes/_dashboard/ai-assistant.tsx`

**Verification**: Student can ask homework questions, get tutoring, generate study plans

---

### Step 2.5: AI Teacher Assistant
- [ ] Implement lesson plan generator
- [ ] Implement question generator (by subject, topic, difficulty)
- [ ] Implement rubric creator
- [ ] Implement AI-assisted essay marking
- [ ] Implement classroom insights (patterns in grades/attendance)
- [ ] Create teacher AI dashboard

**Files affected**:
- `internal/ai/agents/lesson_planner.go`
- `internal/ai/agents/question_generator.go`
- `internal/ai/agents/essay_grader.go`
- `frontend/src/routes/_dashboard/teacher/ai-assistant.tsx`

**Verification**: Teacher generates lesson plans, questions; AI assists with grading

---

### Step 2.6: AI Parent Assistant
- [ ] Implement child performance summary generator
- [ ] Implement attendance insight generator
- [ ] Implement progress recommendation engine
- [ ] Create parent AI dashboard

**Files affected**:
- `internal/ai/agents/parent_summarizer.go`
- `frontend/src/routes/_dashboard/parent/ai-insights.tsx` (when parent module exists)

**Verification**: Parent requests child summary; AI generates personalized report

---

### Step 2.7: Natural Language Search Engine
- [ ] Implement NL query parser (text → structured intent)
- [ ] Implement intent-to-query builder (safe SQL/GORM)
- [ ] Implement schema-aware context provider
- [ ] Implement result formatter (raw data + AI summary)
- [ ] Implement query validation (permission checking)
- [ ] Implement search suggestions
- [ ] Create frontend search component (command palette)

**Files affected**:
- `internal/ai/search/` — search engine files
- `frontend/src/components/layout/command-palette.tsx` — enhance
- `internal/router/router.go` — search route

**Verification**: "Show students with attendance below 70%" returns correct filtered results

---

### Step 2.8: Academic Risk Prediction
- [ ] Implement risk analysis agent (multi-factor: grades, attendance, behavior, fees)
- [ ] Implement risk scoring model (0-100)
- [ ] Implement early warning triggers (event-driven)
- [ ] Implement intervention plan generator
- [ ] Create risk dashboard for counselors/admins

**Files affected**:
- `internal/ai/agents/risk_analyzer.go`
- `internal/modules/analytics/` — new module
- `frontend/src/routes/_dashboard/analytics/risk.tsx`

**Verification**: Students with declining performance flagged; intervention plans generated

---

### Phase 2 Exit Criteria
- [ ] AI Gateway routes to OpenAI/Anthropic with cost tracking
- [ ] RAG engine returns relevant context from institutional knowledge
- [ ] Academic Assistant answers homework questions correctly
- [ ] Teacher Assistant generates usable lesson plans
- [ ] Parent Assistant produces accurate child summaries
- [ ] NL Search returns correct results from natural language queries
- [ ] Risk prediction identifies at-risk students with actionable interventions

---

# PHASE 3: Computer-Based Assessment + LMS
**Timeline**: Months 5-8 (starts after Phase 2 core AI infrastructure ready)
**Effort**: ~400-500 hrs | **Track**: C (continues from Phase 2)

## Description
Build the CBA engine for online exams and the LMS for course management. These share the question bank and student progress infrastructure.

## Dependencies
- Phase 2 Steps 2.1-2.4 (AI Gateway, RAG for question generation)
- Phase 1A Steps 1A.9-1A.10 (Queue for async grading, WebSocket for exam sync)

## Steps

### Step 3.1: Database Migrations — CBA + LMS
- [ ] Create CBA tables: questions, question categories, exams, exam_questions
- [ ] Create CBA tables: exam_sessions, exam_answers, proctoring_logs, grading_rules
- [ ] Create LMS tables: courses, course_modules, lessons, course_enrollments, lesson_progress
- [ ] Create LMS tables: assignments, assignment_submissions, discussions

**Files affected**:
- `internal/database/migrations/phase4.go`
- `internal/model/cba/`
- `internal/model/lms/`

**Verification**: All tables created; indexes in place; rollback works

---

### Step 3.2: Question Bank Module
- [ ] Implement question CRUD with categories
- [ ] Implement question types: MCQ, essay, fill-blank, matching, true/false
- [ ] Implement question randomization engine
- [ ] Implement option shuffling
- [ ] Implement bulk import (CSV/Excel)
- [ ] Implement question tagging and search
- [ ] Implement difficulty tracking (based on answer statistics)

**Files affected**:
- `internal/modules/cba/` — new module
- `internal/model/cba/question.go`

**Verification**: Questions created, categorized, randomized; bulk import works

---

### Step 3.3: Exam Engine
- [ ] Implement exam CRUD with question selection
- [ ] Implement exam publishing workflow (draft → published → archived)
- [ ] Implement timed assessment engine
- [ ] Implement exam session management (start, pause, resume, submit)
- [ ] Implement auto-save every 30 seconds
- [ ] Implement auto-submit on timeout
- [ ] Implement WAEC/JAMB style exam support
- [ ] Implement practice mode (instant feedback)

**Files affected**:
- `internal/modules/cba/exam_service.go`
- `internal/model/cba/exam.go`

**Verification**: Full exam flow: student sees exam, answers questions, submits, gets auto-graded

---

### Step 3.4: Auto-Grading Engine
- [ ] Implement MCQ auto-grading (instant)
- [ ] Implement essay evaluation workflow (queued for AI)
- [ ] Implement AI-assisted essay grading (via Phase 2)
- [ ] Implement AI cheating detection (tab switches, timing anomalies)
- [ ] Implement manual grading override
- [ ] Implement grading rules engine (weighted scoring)

**Files affected**:
- `internal/modules/cba/grading_service.go`
- `internal/ai/agents/essay_grader.go` — integrate with CBA

**Verification**: MCQ graded instantly; essays queued and AI-graded; results accurate

---

### Step 3.5: Webcam Proctoring Integration
- [ ] Implement proctoring event capture API
- [ ] Implement face detection analysis (AI)
- [ ] Implement multiple-face detection
- [ ] Implement tab-switch detection
- [ ] Implement suspicious behavior flagging
- [ ] Implement proctoring dashboard for review

**Files affected**:
- `internal/modules/cba/proctoring_service.go`
- `internal/ai/proctoring/` — AI proctoring analysis
- `frontend/src/components/cba/proctoring/` — camera capture

**Verification**: Proctoring detects face loss, multiple faces, tab switches; flagged for review

---

### Step 3.6: CBA Frontend
- [ ] Create exam list page (available, upcoming, completed)
- [ ] Create exam-taking interface (timed, full-screen)
- [ ] Create question navigation (palette, flag for review)
- [ ] Create proctoring camera preview
- [ ] Create results page (score, breakdown, feedback)
- [ ] Create exam analytics dashboard (admin)
- [ ] Create question analysis dashboard (difficulty, discrimination)

**Files affected**:
- `frontend/src/routes/_dashboard/cba/`
- `frontend/src/hooks/useCBA.ts` — expand

**Verification**: Student takes exam end-to-end; admin views analytics

---

### Step 3.7: LMS — Course Management
- [ ] Implement course CRUD with modules/lessons structure
- [ ] Implement content types: video, text, PDF, quiz
- [ ] Implement course enrollment (student self-enroll or assigned)
- [ ] Implement lesson progress tracking
- [ ] Implement course completion workflow
- [ ] Implement file upload for course materials

**Files affected**:
- `internal/modules/lms/` — new module
- `internal/model/lms/`

**Verification**: Course created with modules and lessons; student enrolls, progresses, completes

---

### Step 3.8: LMS — Assignments & Discussions
- [ ] Implement assignment CRUD with due dates
- [ ] Implement assignment submission (file upload + text)
- [ ] Implement grading workflow (teacher grades, AI assist)
- [ ] Implement discussion forums (threaded)
- [ ] Implement discussion moderation

**Files affected**:
- `internal/modules/lms/assignment_service.go`
- `internal/modules/lms/discussion_service.go`

**Verification**: Assignment submitted, graded with AI assistance; forum posts created

---

### Step 3.9: LMS Frontend
- [ ] Create course catalog page
- [ ] Create course detail page with module navigation
- [ ] Create lesson viewer (video player, text renderer)
- [ ] Create progress tracking UI
- [ ] Create assignment submission UI
- [ ] Create discussion forum UI
- [ ] Create learning analytics dashboard

**Files affected**:
- `frontend/src/routes/_dashboard/lms/`
- `frontend/src/hooks/useLMS.ts`

**Verification**: Student views course, completes lessons, submits assignments; analytics show progress

---

### Phase 3 Exit Criteria
- [ ] Questions created, randomized, and used in exams
- [ ] Full exam flow: publish → start → answer → submit → grade
- [ ] Auto-grading correct for MCQ; AI assists with essays
- [ ] Proctoring detects cheating behaviors
- [ ] WAEC/JAMB exam styles supported
- [ ] Courses created with lessons and assignments
- [ ] Student enrollment, progress tracking, completion
- [ ] Discussion forums functional

---

# PHASE 4: Communication & Engagement
**Timeline**: Months 6-9 (overlaps with Phase 2 and 3)
**Effort**: ~250-350 hrs | **Track**: B (continues from Phase 1B)

## Description
Build the multi-channel communication hub, parent engagement platform, real-time notifications, and digital report card engine.

## Dependencies
- Phase 1A Step 1A.9 (Queue — for async message sending)
- Phase 1A Step 1A.10 (WebSocket — for real-time notifications)
- Phase 1B (Student records exist for parents to view)
- Phase 3 (Results exist for report cards)

## Steps

### Step 4.1: Communication Provider Abstraction
- [ ] Implement provider interface (SMS, Email, Push, WhatsApp)
- [ ] Implement Twilio SMS provider
- [ ] Implement SendGrid email provider
- [ ] Implement FCM push notification provider
- [ ] Implement WhatsApp provider (Twilio/360dialog)
- [ ] Implement in-app notification store
- [ ] Implement template rendering engine (variable substitution)
- [ ] Implement delivery tracking (sent, delivered, failed, opened)

**Files affected**:
- `internal/communication/` — new directory
- `internal/config/config.go` — provider configs
- `go.mod` — add Twilio, SendGrid deps

**Verification**: SMS, Email, Push, WhatsApp messages delivered; delivery status tracked

---

### Step 4.2: Communication Module Backend
- [ ] Create communication handler/service/repository module
- [ ] Implement single-send endpoints (SMS, Email, Push, WhatsApp)
- [ ] Implement bulk-send endpoint
- [ ] Implement campaign management
- [ ] Implement message history and search
- [ ] Implement webhook receivers (Twilio, SendGrid inbound)
- [ ] Implement message templates CRUD

**Files affected**:
- `internal/modules/communication/` — new module
- `internal/router/router.go` — communication routes

**Verification**: Messages sent through all channels; campaigns created and executed

---

### Step 4.3: Communication Frontend
- [ ] Create compose message UI (channel selector, template picker)
- [ ] Create message history viewer
- [ ] Create campaign management UI
- [ ] Create template editor
- [ ] Create delivery analytics dashboard

**Files affected**:
- `frontend/src/routes/_dashboard/communication/`
- `frontend/src/hooks/useCommunication.ts`

**Verification**: Admin composes and sends message through any channel

---

### Step 4.4: Real-Time Notification System
- [ ] Implement WebSocket notification delivery
- [ ] Implement notification preferences per user
- [ ] Implement notification types: system, academic, financial, communication
- [ ] Implement notification grouping and priority
- [ ] Implement push notification fallback (when WS disconnected)
- [ ] Implement notification center component (frontend)
- [ ] Implement unread badge and count

**Files affected**:
- `internal/modules/notification/` — new module
- `internal/websocket/` — integrate with notifications
- `frontend/src/components/layout/notifications-center.tsx` — enhance
- `frontend/src/hooks/useNotifications.ts` — WebSocket integration

**Verification**: Notifications appear in real-time; preferences respected; push fallback works

---

### Step 4.5: Parent Engagement Platform
- [ ] Create parent dashboard (overview of all children)
- [ ] Create child progress tracker (grades, trends, charts)
- [ ] Create attendance monitor
- [ ] Create fee status and payment widget
- [ ] Create school announcements feed
- [ ] Create teacher communication interface
- [ ] Create parent-teacher meeting scheduler

**Files affected**:
- `internal/modules/parent/` — new module (or existing user module enhanced)
- `frontend/src/routes/_dashboard/parent/`
- `frontend/src/hooks/useParent.ts`

**Verification**: Parent sees all children, views progress, pays fees, messages teachers

---

### Step 4.6: Digital Report Card Engine
- [ ] Implement report card generation service
- [ ] Implement PDF generation (gofpdf or similar)
- [ ] Implement report card templates (configurable layout)
- [ ] Implement GPA calculation and visualization
- [ ] Implement subject performance charts
- [ ] Implement performance trends over sessions
- [ ] Implement attendance summary section
- [ ] Implement teacher remarks section
- [ ] Implement AI academic summary generation
- [ ] Implement batch generation (entire class)

**Files affected**:
- `internal/modules/reportcard/` — new module
- `pkg/pdf/` — PDF generation utilities
- `go.mod` — add PDF library

**Verification**: Report card generated, PDF exported, charts accurate, AI summary generated

---

### Step 4.7: Report Card Frontend
- [ ] Create interactive report card view
- [ ] Create performance charts (recharts integration)
- [ ] Create GPA visualization
- [ ] Create PDF download button
- [ ] Create batch generation UI (admin)
- [ ] Create template builder UI (drag-and-drop)

**Files affected**:
- `frontend/src/routes/_dashboard/reports/report-card.tsx`
- `frontend/src/components/reportcard/`
- Existing template-builder — integrate with report card engine

**Verification**: Student views interactive report card; downloads PDF; admin generates batch

---

### Phase 4 Exit Criteria
- [ ] SMS, Email, Push, WhatsApp messages sent and delivered
- [ ] Campaigns created and executed
- [ ] Real-time notifications in-browser and via push
- [ ] Parent portal shows all children's progress
- [ ] Report cards generated as PDF with AI summary
- [ ] Report card templates configurable

---

# PHASE 5: Extended Modules (Library, Hostel, Transport, Inventory, HR, Finance)
**Timeline**: Months 8-11 (after Phase 1B, 3, 4 core infrastructure established)
**Effort**: ~400-500 hrs | **Track**: B

## Description
Build the remaining school operations modules. Each is a self-contained domain module following the established pattern.

## Dependencies
- Phase 1A (all infrastructure needed)
- Phase 1B (student records for hostel allocations)
- Existing: user, school, academic modules

## Steps

### Step 5.1: Library Management
- [ ] Create library models: books, ebooks, borrowings, digital resources
- [ ] Implement book CRUD with categories
- [ ] Implement barcode/ISBN scanning
- [ ] Implement borrowing/return workflow
- [ ] Implement overdue tracking and fines
- [ ] Implement digital resource management
- [ ] Create library dashboard (frontend)

**Files affected**:
- `internal/modules/library/` — new module
- `internal/model/library/`
- `frontend/src/routes/_dashboard/library/`

**Verification**: Books cataloged, borrowed, returned; overdue fines calculated

---

### Step 5.2: Hostel Management
- [ ] Create hostel models: hostels, rooms, beds, allocations, maintenance
- [ ] Implement hostel/room/bed CRUD
- [ ] Implement room allocation workflow (auto + manual)
- [ ] Implement bed management
- [ ] Implement hostel billing
- [ ] Implement maintenance request system
- [ ] Create hostel dashboard (frontend)

**Files affected**:
- `internal/modules/hostel/` — new module
- `internal/model/hostel/`
- `frontend/src/routes/_dashboard/hostel/`

**Verification**: Room assigned to student; billing calculated; maintenance request created

---

### Step 5.3: Transport Management
- [ ] Create transport models: buses, routes, stops, drivers, trips
- [ ] Implement bus/route/driver CRUD
- [ ] Implement route and stop management
- [ ] Implement trip scheduling
- [ ] Implement GPS tracking integration (future)
- [ ] Implement parent tracking view
- [ ] Create transport dashboard (frontend)

**Files affected**:
- `internal/modules/transport/` — new module
- `internal/model/transport/`
- `frontend/src/routes/_dashboard/transport/`

**Verification**: Routes created; students assigned to routes; drivers assigned to buses

---

### Step 5.4: Inventory & Asset Management
- [ ] Create inventory models: assets, categories, assignments
- [ ] Implement asset CRUD with categories
- [ ] Implement asset assignment (who has what)
- [ ] Implement maintenance tracking
- [ ] Implement depreciation calculation
- [ ] Implement audit scheduling
- [ ] Create inventory dashboard (frontend)

**Files affected**:
- `internal/modules/inventory/` — new module
- `internal/model/inventory/`
- `frontend/src/routes/_dashboard/inventory/`

**Verification**: Assets recorded, assigned, tracked; maintenance schedules created

---

### Step 5.5: HR & Payroll
- [ ] Create HR models: staff, payroll, leave, performance, recruitment
- [ ] Implement staff record management
- [ ] Implement payroll computation (basic salary, deductions, taxes)
- [ ] Implement leave management workflow
- [ ] Implement performance review cycle
- [ ] Implement recruitment/job posting
- [ ] Create HR dashboard (frontend)

**Files affected**:
- `internal/modules/hr/` — new module
- `internal/model/hr/`
- `frontend/src/routes/_dashboard/hr/`

**Verification**: Staff records managed; payroll computed; leave approved; performance reviewed

---

### Step 5.6: Finance & Accounting
- [ ] Create finance models: chart of accounts, transactions, budgets
- [ ] Implement chart of accounts management
- [ ] Implement double-entry bookkeeping
- [ ] Implement income/expense tracking
- [ ] Implement budgeting and budget tracking
- [ ] Implement financial reports (P&L, balance sheet, cash flow)
- [ ] Integrate with existing fees/payments modules
- [ ] Create finance dashboard (frontend)

**Files affected**:
- `internal/modules/finance/` — new module
- `internal/model/finance/`
- `frontend/src/routes/_dashboard/finance/`

**Verification**: Transactions recorded; reports generated; balances match payments module

---

### Phase 5 Exit Criteria
- [ ] Library: books cataloged, borrowed, returned with fines
- [ ] Hostel: rooms allocated, billed, maintained
- [ ] Transport: routes scheduled, students tracked
- [ ] Inventory: assets tracked, assigned, maintained
- [ ] HR: staff paid, leave managed, performance reviewed
- [ ] Finance: full accounting, reports generated

---

# PHASE 6: Alumni & Career Guidance
**Timeline**: Months 10-13 (after Phase 1B — needs student enrollment to exist)
**Effort**: ~300-400 hrs | **Track**: B

## Description
Build the complete alumni lifecycle: from graduation to lifelong engagement. Includes career services, fundraising, and verification.

## Dependencies
- Phase 1B (student records → alumni conversion)
- Phase 2 (AI for career guidance and engagement prediction)
- Existing: user module (for authentication)

## Steps

### Step 6.1: Database Migrations — Alumni
- [ ] Create alumni tables: alumni, alumni_careers, alumni_events
- [ ] Create alumni tables: mentorships, donations, fundraising_campaigns
- [ ] Create alumni tables: verification_requests, job_board, event_attendees

**Files affected**:
- `internal/database/migrations/phase5.go`
- `internal/model/alumni/`

**Verification**: All tables created; graduation auto-creates alumni record

---

### Step 6.2: Alumni Management Module
- [ ] Implement alumni profile CRUD
- [ ] Implement career history tracking
- [ ] Implement alumni directory with search/filter
- [ ] Implement event management and registration
- [ ] Implement mentorship matching
- [ ] Implement donation processing
- [ ] Implement fundraising campaigns
- [ ] Implement certificate/transcript verification
- [ ] Implement job board

**Files affected**:
- `internal/modules/alumni/` — new module
- `internal/router/router.go` — alumni routes

**Verification**: Alumni profiles created; events managed; donations processed; certificates verified

---

### Step 6.3: Verification Services
- [ ] Implement verification request workflow
- [ ] Implement data verification against alumni records
- [ ] Implement fee collection for verification
- [ ] Implement verification document generation
- [ ] Implement public verification portal (no auth required)
- [ ] Implement rate limiting for public verification

**Files affected**:
- `internal/modules/alumni/verification_service.go`
- `frontend/src/routes/_public/verify.tsx`

**Verification**: Third party verifies graduate status; paid verification generates document

---

### Step 6.4: Alumni Portal Frontend
- [ ] Create alumni dashboard
- [ ] Create profile management page
- [ ] Create career history tracker
- [ ] Create alumni directory (searchable)
- [ ] Create event listing and registration
- [ ] Create mentorship matching UI
- [ ] Create donation interface
- [ ] Create job board

**Files affected**:
- `frontend/src/routes/_dashboard/alumni/`

**Verification**: Alumni logs in, updates profile, registers for events, donates, posts jobs

---

### Step 6.5: AI Career Guidance Engine
- [ ] Implement career recommendation agent (from Phase 2)
- [ ] Implement university matching agent
- [ ] Implement skills assessment tool
- [ ] Implement scholarship matching agent
- [ ] Implement career roadmap generator
- [ ] Implement skills gap analysis

**Files affected**:
- `internal/ai/agents/career_guide.go`
- `internal/modules/career/` — new module
- `frontend/src/routes/_dashboard/career/`

**Verification**: Student receives career recommendations; university matches; roadmap generated

---

### Step 6.6: AI Alumni Insights
- [ ] Implement engagement likelihood prediction
- [ ] Implement donation potential scoring
- [ ] Implement event attendance prediction
- [ ] Implement mentorship matching (AI-optimized)
- [ ] Implement alumni engagement analytics

**Files affected**:
- `internal/ai/agents/alumni_insights.go`
- `internal/modules/alumni/analytics_service.go`

**Verification**: Alumni engagement predicted; donation probability scored; matches optimized

---

### Phase 6 Exit Criteria
- [ ] Alumni profiles auto-created on graduation
- [ ] Alumni directory searchable and filterable
- [ ] Events created and alumni register
- [ ] Donations processed with campaign tracking
- [ ] Certificates verified through public portal
- [ ] Career guidance provides recommendations
- [ ] Alumni insights predict engagement and donation

---

# PHASE 7: Business Intelligence & Analytics ✅ COMPLETE
**Timeline**: Months 12-15 | **Effort**: ~300 hrs | **Track**: C

## Description
The complete analytics and BI platform: executive dashboards, custom report builder, AI-powered executive summaries, and forecasting agents.

## Dependencies
- Phase 2 (AI for executive summaries and forecasts)
- Phase 3 (CBA/LMS data for academic analytics)
- Phase 5 (Finance, HR data for financial analytics)
- Phase 6 (Alumni data for alumni analytics)

## Steps

### Step 7.1: Analytics Data Pipeline ✅
- [x] Analytics data collection service (CollectSnapshot with 4 collectors)
- [x] AnalyticsSnapshot + AnalyticsMetric models
- [x] Periodic snapshot generation (daily, weekly, term via CollectSnapshot endpoint)
- [x] Data export ready (snapshots stored as JSONB for export)

**Files affected**:
- `internal/modules/analytics/` — full module (handler.go, service.go, repository.go, dto.go)
- `internal/database/models/analytics.go` — models
- `internal/router/router.go` — 6 endpoints registered

**Verification**: Snapshots generated correctly; aggregations match source data ✅

---

### Step 7.2: Executive Dashboards ✅
- [x] Enrollment trends dashboard (area chart + by-level bars)
- [x] Revenue/financial dashboard (area chart + fee-type bars)
- [x] Academic performance dashboard (subject/class bars + attendance)
- [x] Executive overview with 4 KPI cards + 3 chart types
- [x] Role-based navigation (admin: 4 routes, teacher: 3 routes)
- [x] Sidebar analytics nav group for admin + teacher

**Files affected**:
- `frontend/src/routes/_dashboard/analytics/` — 4 dashboard pages
- `frontend/src/components/layout/data/sidebar-data.ts` — nav groups

**Verification**: Dashboards display accurate data with Recharts; role-filtered via sidebar ✅

---

### Step 7.3: Custom Report Builder ✅
- [x] ReportConfig model + migration (report_configs table with JSONB filters/schedule)
- [x] Report builder backend module (8 endpoints: CRUD + generate + export + schedule)
- [x] Report builder frontend (config form + list page with actions)
- [x] Data source selection (enrollment, revenue, academic, attendance)
- [x] Chart type configuration (bar, line, pie, table, area)
- [x] Filter and group-by configuration
- [x] Report scheduling (JSONB cron configuration)
- [x] Report export (GET export endpoint, CSV format)

**Files affected**:
- `internal/modules/reportbuilder/` — new module (handler.go, service.go, repository.go, dto.go)
- `internal/database/models/report_config.go` — new model
- `internal/database/migrations/phase_modules.go` — migration 000034
- `frontend/src/routes/_dashboard/reports/index.tsx` — list page
- `frontend/src/routes/_dashboard/reports/builder.tsx` — config form
- `frontend/src/lib/hooks/useReportBuilder.ts` — typed hooks
- `frontend/src/lib/hooks/query-keys.ts` — report query keys

**Verification**: Report configs CRUD works; generate/export/schedule endpoints respond ✅

---

### Step 7.4: AI Executive Summaries ✅
- [x] ExecutiveSummarizer AI agent (3 tools: get_dashboard_summary, generate_summary, recommendations)
- [x] POST /analytics/summaries endpoint with structured response
- [x] Agent integration with analytics dashboard data
- [x] Natural language trend descriptions and recommendations
- [x] Agent registered in setup.go agentMap

**Files affected**:
- `internal/ai/agents/executive_summarizer.go` — new agent (no DB, pure AI)
- `internal/modules/analytics/handler.go` — GenerateSummary handler
- `internal/modules/analytics/service.go` — GenerateSummary method
- `internal/modules/analytics/dto.go` — summary DTOs

**Verification**: AI generates summaries from dashboard data; endpoint returns structured response ✅

---

### Step 7.5: Forecasting Models ✅
- [x] EnrollmentForecaster AI agent (2 tools: get_enrollment_history, generate_forecast)
- [x] RevenueForecaster AI agent (2 tools: get_revenue_history, generate_forecast)
- [x] GET /analytics/forecasts/enrollment endpoint
- [x] GET /analytics/forecasts/revenue endpoint
- [x] Both agents registered in setup.go agentMap with DB access

**Files affected**:
- `internal/ai/agents/enrollment_forecaster.go` — new agent with DB
- `internal/ai/agents/revenue_forecaster.go` — new agent with DB
- `internal/modules/analytics/handler.go` — EnrollmentForecast + RevenueForecast handlers
- `internal/modules/analytics/service.go` — forecast service methods
- `internal/modules/analytics/dto.go` — forecast DTOs

**Verification**: Agents query historical data and project trends via AI; endpoints return forecasts ✅

---

### Phase 7 Exit Criteria ✅
- [x] Executive dashboards show real-time data across 4 domains
- [x] Custom report builder with config CRUD + generate + export + schedule
- [x] AI summaries generate executive insights from dashboard data
- [x] Forecasting models project enrollment and revenue trends

---

# PHASE 8: Remaining Features — Cross-Phase Gaps
**Timeline**: Months 15-17 (after Phases 1-7 complete)
**Effort**: ~200-300 hrs | **Track**: D

## Description
Complete the four feature gaps identified during cross-phase review: webcam proctoring, LMS assignments & discussions, AI career guidance, and AI alumni insights.

## Dependencies
- Phase 2 (AI agents for Career Guidance)
- Phase 3 (CBA for proctoring, LMS for assignments/discussions)
- Phase 6 (Alumni data for career + alumni insights)

## Steps

### Step 8.1: Webcam Proctoring Integration (Phase 3 Gap — Step 3.5)
- [ ] Create `proctoring_events` table/model/migration
- [ ] Implement POST /cba/exams/:id/proctor/photo endpoint (or integrate into existing)
- [ ] Implement GET /cba/exams/:id/proctor/events for review
- [ ] Implement AI Proctoring Analysis agent (flag suspicious behavior)
- [ ] Build proctoring review dashboard for teachers
- [ ] Wire proctoring middleware into CBA exam flow

**Files affected**:
- `internal/database/models/proctoring_event.go` — new model
- `internal/database/migrations/phase_modules.go` — new migration
- `internal/modules/cba/` — extend with proctor handler/service/repo
- `internal/ai/agents/proctoring_analyzer.go` — new agent
- `internal/router/router.go` — proctor routes
- `frontend/src/routes/_dashboard/cba/proctor-review.tsx` — new review page

**Verification**: Photos attached to exams; review dashboard shows events; AI flags anomalies

---

### Step 8.2: LMS Assignments & Discussions (Phase 3 Gap — Step 3.8)
- [ ] Create `assignments` table + `assignment_submissions` table + migrations
- [ ] Create `discussion_threads` table + `discussion_posts` table + migrations
- [ ] Implement assignments submodule (CRUD + submission + grading)
- [ ] Implement discussions submodule (thread CRUD + post CRUD)
- [ ] Implement file attachment support for submissions
- [ ] Build assignments UI (list, detail, submission form)
- [ ] Build discussions UI (thread list, thread detail with posts)
- [ ] Wire grade sync from assignments to CBA results

**Files affected**:
- `internal/database/models/assignment.go` — new model
- `internal/database/models/discussion.go` — new model
- `internal/database/migrations/phase_modules.go` — 2 new migrations
- `internal/modules/lms/assignments/` — new submodule
- `internal/modules/lms/discussions/` — new submodule
- `internal/router/router.go` — assignment + discussion routes
- `frontend/src/routes/_dashboard/lms/assignments/` — assignment pages
- `frontend/src/routes/_dashboard/lms/discussions/` — discussion pages

**Verification**: Teachers create assignments; students submit; discussions threaded; grades sync

---

### Step 8.3: AI Career Guidance Engine (Phase 6 Gap — Step 6.5)
- [ ] Create `career_profiles` + `career_assessments` + `career_recommendations` models/migrations
- [ ] Implement AI Career Guidance agent (profile analysis, career matching, pathway generation)
- [ ] Implement POST /career/assessments (submit interest/skill assessment)
- [ ] Implement GET /career/recommendations (AI-generated career suggestions)
- [ ] Implement GET /career/pathways (education/certification roadmaps)
- [ ] Build career dashboard for students (profile, assessments, recommendations, pathways)

**Files affected**:
- `internal/database/models/career.go` — new model
- `internal/database/migrations/phase_modules.go` — new migration
- `internal/modules/career/` — new module (handler.go, service.go, repository.go, dto.go)
- `internal/ai/agents/career_guidance.go` — new agent
- `internal/router/router.go` — career routes
- `frontend/src/routes/_dashboard/career/` — new career pages

**Verification**: Student completes assessment; AI recommends careers; pathways displayed

---

### Step 8.4: AI Alumni Insights (Phase 6 Gap — Step 6.6)
- [ ] Create `alumni_insights` table/model/migration
- [ ] Implement AI Alumni Insights agent (engagement scoring, network analysis, opportunity matching)
- [ ] Implement GET /alumni/insights/dashboard (engagement stats)
- [ ] Implement GET /alumni/insights/opportunities (mentorships, jobs, events)
- [ ] Build alumni insights dashboard (engagement metrics, network map, opportunities)

**Files affected**:
- `internal/database/models/alumni_insight.go` — new model
- `internal/database/migrations/phase_modules.go` — migration
- `internal/modules/alumni/` — extend with insights handler/service/repo
- `internal/ai/agents/alumni_insights.go` — new agent
- `internal/router/router.go` — insight routes
- `frontend/src/routes/_dashboard/alumni/insights.tsx` — new dashboard page

**Verification**: Alumni engagement scored; opportunities matched; dashboard displays insights

---

### Phase 8 Exit Criteria
- [ ] Webcam proctoring captures photos; AI flags suspicious behavior; review dashboard functional
- [ ] Assignments and discussions fully operational; submissions grade-synced
- [ ] AI Career Guidance generates recommendations and pathways from student assessments
- [ ] AI Alumni Insights scores engagement and matches opportunities

---

# PHASE 9: Future Expansion Pre-Study
**Timeline**: Month 20+ | **Effort**: ~100-150 hrs (research + prototypes)

## Description
Investigate and prototype the future expansion opportunities identified in the architecture doc:
- Blockchain credentials
- Crypto/stablecoin payments
- Virtual classrooms/metaverse
- Biometric authentication
- IoT/smart campus

## Steps

### Step 9.1: Blockchain Credentials Prototype
- [ ] Research credential standards (W3C Verifiable Credentials, OpenCerts)
- [ ] Prototype diploma minting on testnet
- [ ] Build verification DApp prototype
- [ ] Estimate cost and timeline for production

### Step 9.2: Crypto Payments Research
- [ ] Evaluate payment providers (Stripe Crypto, MoonPay, direct on-chain)
- [ ] Prototype USDC payment acceptance
- [ ] Evaluate regulatory implications per market
- [ ] Build integration plan

### Step 9.3: Virtual Classroom Research
- [ ] Evaluate WebXR, Hubs, Decentraland, custom solutions
- [ ] Build prototype virtual classroom with Three.js
- [ ] Test with real teachers for feedback
- [ ] Build integration roadmap

### Step 9.4: Biometric Integration Prototype
- [ ] Evaluate WebAuthn/FIDO2 support
- [ ] Prototype fingerprint attendance
- [ ] Test face recognition for exam proctoring (enhance existing)

### Step 9.5: IoT/Smart Campus Research
- [ ] Evaluate RFID/NFC solutions
- [ ] Prototype RFID attendance integration
- [ ] Research MQTT for IoT device communication
- [ ] Build IoT integration architecture

---

## EFFORT SUMMARY

| Phase | Hours | Timeline | Parallel Tracks |
|-------|-------|----------|-----------------|
| 1A: Architecture Hardening | ✅ 200-300 | Months 1-2 | A ✅ |
| 1B: Admissions | ✅ 300-400 | Months 2-4 | B ✅ |
| 2: AI Services Layer | ✅ 400-500 | Months 3-6 | C ✅ |
| 3: CBA + LMS | ✅ 400-500 | Months 5-8 | C ✅ |
| 4: Communication & Engagement | ✅ 250-350 | Months 6-9 | B ✅ |
| 5: Extended Modules | ✅ 400-500 | Months 8-11 | B ✅ |
| 6: Alumni & Career | ✅ 300-400 | Months 10-13 | B ✅ |
| 7: BI & Analytics | ✅ 250-350 | Months 12-15 | C ✅ |
| 8: Remaining Gaps | ~200-300 | Months 15-17 | D |
| 9: Future Pre-Study | ~100-150 | Month 17+ | Post-MVP |
| **Total** | **~3,000-3,850** | **~17 months** | |

## PARALLEL EXECUTION MODEL

```
Month:  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17
       ┌─────────────────────────────────────────────────────┐
Track A: Architecture Hardening (complete)                    │
       ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│
                                                              │
Track B: Core Domains (complete)                             │
       ░░░░██████████████████████████████████████████████████░│
       1B      4-Comm        5-Extended Mod     6-Alumni      │
                                                              │
Track C: AI & Engagement (complete)                          │
       ░░░░░░░░████████████████████████████████████████░░░░░░░│
              2-AI Layer       3-CBA+LMS         7-BI        │
                                                              │
Track D: Gap Features                                        │
       ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████████░░│
                                                     8-Gaps  │
       └──────────────────────────────────────────────────────┘
```
