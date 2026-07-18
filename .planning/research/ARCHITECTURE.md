# Architecture — Advanced Feature Integration Patterns

**Domain:** School Management System (multi-tenant, modular monolith)
**Researched:** 2026-07-18
**Focus:** How real-time notifications, calendar sync (CalDAV/iCal), parent-teacher communication, automated report generation, and multi-campus management integrate into the existing architecture

---

## Current Architecture Foundation

The existing system is a **modular monolith** (Go/Gin, 39 modules) with:

- **Handler → Service → Repository** layered pattern per module
- **Schema-per-tenant** PostgreSQL isolation via `SchemaTablePrefix` GORM plugin
- **WebSocket** hub (`backend/internal/ws/`) with room-based messaging (gorilla/websocket)
- **Asynq task queue** for background jobs (email, SMS, backups, report generation)
- **Redis** for tenant context cache, rate limiting, session management
- **Single-process** server (no horizontal scaling yet)

This document analyzes how the five advanced features integrate into this foundation, providing component boundaries, data flow patterns, and build order dependencies.

---

## 1. Real-Time Notifications

### Current State

**Status: ALREADY BUILT — needs production hardening**

| Component | Location | Completeness |
|-----------|----------|-------------|
| WebSocket hub | `backend/internal/ws/hub.go` | ✅ Complete |
| Connection management | `backend/internal/ws/connection.go` | ✅ Complete (rate limiting, ping/pong, auto-reconnect) |
| Room management | `backend/internal/ws/room.go` | ✅ Complete |
| JWT auth for WS | `backend/internal/ws/auth.go` | ✅ Complete |
| Message routing | `backend/internal/ws/router.go` | ✅ Complete (8 event types) |
| Prometheus metrics | `backend/internal/ws/metrics.go` | ✅ Complete |
| Notification CRUD | `backend/internal/modules/notifications/` | ✅ Complete |
| WS broadcast on create | `backend/internal/modules/notifications/service.go` | ✅ Complete |
| NotificationProvider interface | `backend/internal/modules/communication/service.go` | ✅ Complete |

### Architecture

```
Email/SMS Task (Asynq)
     ↓
CommunicationService.SendBroadcast()
     ↓                                         WebSocket Hub
NotificationService.Create() ─────────────────→ Broadcast to UserRoom(schoolID, userID)
     ↓                                                 ↓
Notification DB (tenant schema)            Connected browser clients receive instantly
```

**Room naming convention:**
```
school:{schoolID}                    — All members of a school
school:{schoolID}:user:{userID}      — Specific user
school:{schoolID}:class:{classID}    — Class-specific (for announcements)
school:{schoolID}:admissions         — Admission pipeline notifications
```

### Integration Points

| Integration | How It Works | Notes |
|-------------|-------------|-------|
| Any module creates notification | Call `NotificationService.Create()` which persists + broadcasts via WS | Injected as optional dependency |
| Communication broadcasts | `CommunicationService.SendBroadcast()` creates notifications for each recipient + optionally enqueues email/SMS | Uses `NotificationProvider` interface |
| Report generation complete | Asynq task handler can call `NotificationService.Create()` on completion | Not yet wired up |
| Score/publication events | Grade publication → notification to affected students | Future integration |

### Scaling Gap

The current hub is **in-process only** — all connections live in one process. To scale horizontally:

- Replace direct in-process broadcast with **Redis Pub/Sub**
- Each server instance subscribes to `school:*` channels
- Connected users receive messages from any instance

**Build order:** Phase 1 — WS hub is already built. Redis pub/sub scaling is a later optimization (needed only when multiple server instances exist).

---

## 2. Calendar Sync (CalDAV/iCal)

### Current State

**Status: NOT BUILT — timetable engine exists, sync layer missing**

| Component | Location | Completeness |
|-----------|----------|-------------|
| Timetable CRUD | `backend/internal/modules/timetable/` | ✅ Complete |
| Bulk create | `backend/internal/modules/timetable/service.go` | ✅ Complete |
| Calendar editor | `frontend/src/components/timetable/calendar-grid.tsx` | ✅ Complete |
| Calendar model | `backend/internal/database/models/school.go` | ✅ Timetable model exists |
| iCal export | Not built | ❌ Missing |
| CalDAV server endpoint | Not built | ❌ Missing |
| Google Calendar API sync | Not built | ❌ Missing |
| Recurrence rule model | Not built | ❌ Missing |

### Recommended Architecture

The system should adopt a **two-tier approach**: iCal export first (low effort, high value), CalDAV read-write sync second (complex, niche).

#### Tier 1: iCal Export (Phase 2-3)

```
GET /api/v2/timetables/ical?user_id=X&from=2026-09-01&to=2026-12-31
     ↓
TimetableService → query timetables for user/student
     ↓
Generate .ics file using go-ical library
     ↓
Return as file download with Content-Type: text/calendar
```

**Component boundaries:**
- New package: `backend/internal/ical/` — iCalendar generation library wrapper
- One handler route on timetable module: `GET /timetables/ical`
- No new infrastructure needed — synchronous response

**iCal format** (RFC 5545):
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Academio//School Timetable//EN
BEGIN:VEVENT
UID:timetable-{id}@academio
DTSTART:20260901T083000Z
DTEND:20260901T092000Z
SUMMARY:Mathematics - Grade 10A
DESCRIPTION:Mr. Smith - Room 201
RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR
END:VEVENT
END:VCALENDAR
```

**Go library options (MEDIUM confidence — WebSearch only):**

| Library | Stars | Features | Notes |
|---------|-------|----------|-------|
| `github.com/arran4/golang-ical` | 300+ | RFC 5545 compliance, VEVENT, VTODO, VJOURNAL, RRULE, timezone | Most popular pure Go iCal library |
| `github.com/apognu/gocal` | 200+ | Parser-focused (read .ics) | Not suitable for generation |
| Manual construction | — | Full control, no dependency | Simple XML/text templating |

**Recommendation:** Use `github.com/arran4/golang-ical` — well-maintained, handles RRULE, timezone, and serialization. Add as a new dependency.

#### Tier 2: CalDAV Server (Phase 7+)

CalDAV is a WebDAV extension protocol. Hosting a CalDAV server means:

```
Client (Apple Calendar, Thunderbird, etc.)
     ↓  CalDAV (WebDAV + XML + iCalendar)
Academio CalDAV endpoint: /caldav/{schoolID}/{userID}/
     ↓
CalDAVHandler → Parse DAV XML requests (PROPFIND, REPORT, MKCALENDAR, PUT, DELETE)
     ↓
TimetableService → CRUD timetables + events
     ↓
PostgreSQL (tenant schema)
```

**CalDAV integration pattern — host vs proxy:**

| Approach | Complexity | Use Case | Recommendation |
|----------|-----------|----------|----------------|
| **Host CalDAV endpoint** | High | Provide read-write sync from any CalDAV client | Defer — niche need for most schools |
| **Export iCal subscription** | Low | Read-only calendar view in external apps | **Build first** — handles 90% of use cases |
| **Google Calendar API sync (outbound)** | Medium | Bidirectional sync with Google Calendar | Consider if parent/teacher demand justifies it |

**Data flow for iCal subscription:**
```
1. School admin enables "Calendar Publishing" for a timetable
2. System generates a unique, unguessable URL: /ical/pub/{uuid}.ics
3. Teachers/parents subscribe to this URL in their calendar app
4. Calendar app polls URL periodically (or refreshes on open)
5. Academio generates fresh .ics on each request
```

**Key complexity:** Timetable recurrence. A weekly class is one timetable entry with a recurrence pattern, not 36 individual entries. The `Timetable` model needs:
- `recurrence_rule` (string — RFC 5545 RRULE like `FREQ=WEEKLY;BYDAY=MO,WE,FR`)
- `recurrence_end` (date — term end date)
- Exception handling (cancelled individual sessions)

### Integration Points

| Integration | How It Works | Notes |
|-------------|-------------|-------|
| Timetable → iCal | Service transforms timetable entries into VEVENT components | 1:1 mapping, no new DB queries |
| Student timetable → iCal | Resolve student's enrolled classes, export combined calendar | Requires level timetable association |
| Notifications → calendar | Upcoming class reminders via in-app notification | Separate concern from iCal sync |

### Build Order

1. **Phase 2-3:** iCal download endpoint (one route, one new package, minimal effort)
2. **Phase 4:** Recurrence model for timetables (modify existing model + migration)
3. **Phase 5:** iCal subscription with UUID URLs (cache generated .ics for performance)
4. **Phase 7+:** CalDAV read-write endpoint (only if schools explicitly request it)

---

## 3. Parent-Teacher Communication

### Current State

**Status: PARTIALLY BUILT — internal messaging + communication module exist, but no integrated parent-teacher conversation system**

| Component | Location | Completeness |
|-----------|----------|-------------|
| Internal messaging CRUD | `backend/internal/modules/messages/` | ✅ Complete |
| Communication templates | `backend/internal/modules/communication/` | ✅ Complete (templates, campaigns, broadcast) |
| Email/SMS delivery | `backend/internal/communication/` + Asynq tasks | ✅ Complete (SendGrid, Twilio) |
| Parent dashboard | `backend/internal/modules/parentdashboard/` | ✅ Complete (child progress, attendance, fees) |
| Parent dedup + sibling reuse | `backend/internal/modules/user/service.go` | ✅ Complete |
| NotificationProvider interface | `backend/internal/modules/communication/service.go` | ✅ Complete |
| WebSocket hub | `backend/internal/ws/` | ✅ Ready for real-time message delivery |
| Threaded conversations | Not built | ❌ Missing |
| Read receipts | Not built | ❌ Missing |
| Typing indicators | Not built | ❌ Missing |
| File/photo sharing in messages | Not built | ❌ Missing |

### Recommended Architecture

Parent-teacher communication should be **layered on top of existing messaging infrastructure** rather than building a separate system.

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React SPA)               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Conversation │  │ Inbox        │  │ Real-time  │  │
│  │ List         │  │ (message     │  │ WS Client  │  │
│  │              │  │  threads)     │  │            │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬─────┘  │
└─────────┼─────────────────┼──────────────────┼────────┘
          │ HTTP REST       │ HTTP REST        │ WS
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────┐
│                  Go Backend (Gin)                    │
│  ┌──────────────────────────────────────────────┐   │
│  │        Messages Module (enhanced)            │   │
│  │  ┌─────────┐  ┌──────────┐  ┌────────────┐  │   │
│  │  │Conversa-│  │ Message  │  │ File       │  │   │
│  │  │tion      │  │ CRUD     │  │ Attachment │  │   │
│  │  │Management│  │(threaded)│  │ Handler    │  │   │
│  │  └────┬────┘  └────┬─────┘  └─────┬──────┘  │   │
│  │       └────────────┼──────────────┘         │   │
│  │                    ▼                        │   │
│  │           MessageService                    │   │
│  │  ┌──────────────────────────────────────┐   │   │
│  │  │ WebSocket broadcast to room          │   │   │
│  │  │ Notification creation                │   │   │
│  │  │ Email/SMS fallback (if offline)      │   │   │
│  │  └──────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────┘   │
│                                                    │
│  ┌────────────────────┐  ┌──────────────────────┐  │
│  │ Communication      │  │ Notification        │  │
│  │ Module (broadcast) │  │ Module (in-app)     │  │
│  └────────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Key Methods |
|-----------|---------------|-------------|
| `ConversationService` | Create/manage conversations, participant management, archive | `CreateConversation`, `AddParticipant`, `Archive` |
| `MessageService` | Send messages (text + file), read receipts, history | `SendMessage`, `MarkRead`, `GetHistory` |
| `WebSocket.Hub` | Real-time delivery of new messages, typing indicators | `Broadcast(room, msg)` |
| `CommunicationService` | Email/SMS fallback for offline parents | `SendBulk`, `CreateCampaign` |
| `NotificationService` | In-app notification for new messages | `Create` + WS broadcast |

### Data Model

```sql
-- Existing: messages table (needs conversation_id)
ALTER TABLE messages ADD COLUMN conversation_id BIGINT NOT NULL;
ALTER TABLE messages ADD COLUMN parent_message_id BIGINT; -- for threading
ALTER TABLE messages ADD COLUMN has_attachments BOOLEAN DEFAULT FALSE;
ALTER TABLE messages ADD COLUMN read_at TIMESTAMP;

-- New: conversations table
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL,
    subject VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active', -- active, archived
    last_message_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- New: conversation_participants table
CREATE TABLE conversation_participants (
    conversation_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role VARCHAR(20) DEFAULT 'participant', -- participant, moderator
    last_read_at TIMESTAMP,
    joined_at TIMESTAMP,
    PRIMARY KEY (conversation_id, user_id)
);
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Enhance existing messages module** rather than building a new one | Less code, existing patterns, reuses WebSocket infrastructure |
| **Conversation = shared inbox** not 1:1 chat | Teachers talk to parents, not just parent-teacher pairs. Multiple teachers may communicate about one student |
| **WebSocket for online delivery, email/SMS as fallback** | Parents may not be online. Email/SMS ensures delivery |
| **Conversation scoped to school schema** | Normal tenant isolation. Parent sees only their children's conversations |
| **File attachments via existing multimedia module** | Reuse `backend/internal/modules/multimedia/` for upload + permission checks |

### Integration Points

| Integration | How It Works | Notes |
|-------------|-------------|-------|
| Teacher sends message | Creates message → WS broadcast to all conversation participants → Creates notification for offline users → Optional email fallback | Integrates with existing NotificationProvider + CommunicationService |
| Parent dashboard shows unread | `ParentDashboardService` queries conversation participants table for unread count | Already partially in parentdashboard module |
| Attendance alert → parent notification | Auto-create conversation with attendance summary | Future: triggered by attendance service |
| Grade published → parent notification | Auto-create conversation with grade summary | Future: triggered by score service |

### Build Order

1. **Phase 2:** Enhance messages module — add conversation model + threaded messaging + file attachments
2. **Phase 3:** WebSocket-based real-time delivery for new messages + typing indicators
3. **Phase 3:** Parent inbox in parent dashboard (unread count, conversation list)
4. **Phase 4:** Email/SMS fallback for offline parents (reuse CommunicationService)
5. **Phase 5:** Auto-created conversations for attendance/grade events

---

## 4. Automated Report Generation

### Current State

**Status: FULLY BUILT — one of the most mature feature areas**

| Component | Location | Completeness |
|-----------|----------|-------------|
| Report builder (custom configs) | `backend/internal/modules/reportbuilder/` | ✅ Complete |
| Report card generation | `backend/internal/modules/reportcard/` | ✅ Complete |
| Predefined reports | `backend/internal/modules/reports/` | ✅ Complete |
| Asynq `report:generate` task | `backend/internal/queue/handlers/` | ✅ Complete |
| PDF generation | Via Asynq task handler | ✅ Complete |
| Report scheduling | `reportbuilder/service.go` | ✅ Complete |

### Architecture

```
API Request (manual or scheduled)
     ↓
ReportBuilderService.GenerateReport()
     ↓
Enqueue Asynq Task: report:generate
     ↓
Asynq Worker (goroutine in same process)
     ↓
ReportTaskHandler
     ↓  Queries tenant DB
Query data (scores, attendance, demographics, etc.)
     ↓
Generate PDF (or XLSX, CSV)
     ↓
Store in filesystem/S3 via Storage driver
     ↓
Notify user via NotificationService.Create() + WS broadcast
```

### Integration Points

| Integration | How It Works | Notes |
|-------------|-------------|-------|
| Score module → report data | Reports query `scores` + `grade_items` tables | Already works — standard tenant DB queries |
| Attendance → attendance reports | Reports query `student_attendances` | Already works |
| Finance → financial reports | Reports query `journals`, `budgets`, `expenses` | Already works |
| Report completion → notification | Handler calls `NotificationService.Create()` | Already works |
| Scheduled reports → cron-like scheduling | Asynq periodic tasks via `PeriodicTaskManager` | Already works |

### Scaling Considerations

| Concern | Current Approach | At Scale |
|---------|-----------------|----------|
| Concurrent report generation | Serial within single worker goroutine | Need configurable concurrency via `asynq.Server` options |
| Long-running reports | Timeout via context | Add context deadline propagation |
| Storage | Local filesystem or S3 | Already abstracted via `Storage` interface |
| Memory (large datasets) | All loaded in memory | Add streaming/chunked processing for PDF generation |

### Build Order

**No additional build needed.** This is the reference pattern for other async workflows.

---

## 5. Multi-Campus Management

### Current State

**Status: NOT BUILT — schema-per-tenant model treats each school as fully independent**

### The Core Problem

Multi-campus management is fundamentally about **hierarchical tenancy**:
- A "district" or "trust" owns multiple schools
- Each school is a separate tenant (schema-isolated)
- The district needs **read-only cross-tenant visibility** (consolidated reports, analytics)
- Some resources (teachers, curricula) may be **shared across campuses**
- Users may need a **single login** that spans multiple campuses

### Architecture Patterns

#### Pattern A: Schema-per-Campus (existing model + cross-schema queries)

```
┌────────────────────────────────────────────────┐
│              District Dashboard                 │
│  (public schema — cross-tenant analytics)      │
└────────────────┬───────────────────────────────┘
                 │ queries each tenant schema
    ┌────────────┼────────────┐
    ▼            ▼            ▼
schema_1      schema_2     schema_3
(High School) (Middle Sch) (Elem Sch)
```

**Pros:**
- Strongest data isolation (existing model)
- Each campus can have different configurations
- Existing schema-per-tenant code unchanged

**Cons:**
- Cross-campus queries require N+1 schema queries
- No shared resources between campuses
- User must re-auth or context-switch between campuses

**Implementation approach:**
```go
// CrossTenantQuery executes a query across all tenant schemas in a district
func (s *MultiCampusService) CrossTenantQuery(ctx context.Context, districtID uint, query func(db *gorm.DB) (interface{}, error)) (map[uint]interface{}, error) {
    schools, err := s.schoolRepo.FindByDistrict(ctx, districtID)
    // ...
    results := make(map[uint]interface{})
    for _, school := range schools {
        tenantDB, err := s.tenantResolver.GetTenantDB(ctx, school.ID)
        // ...
        result, err := query(tenantDB)
        // ...
        results[school.ID] = result
    }
    return results, nil
}
```

#### Pattern B: Shared Schema for Shared Data + Schema-per-Campus for Local Data

```
public schema:
  teachers (shared — can teach across campuses)
  curricula (shared — standardized across district)
  campuses (school records — mapping to schemas)

per-tenant schema:
  students (campus-specific)
  scores, attendance, timetables (campus-specific)
  classes/groups (campus-specific)
```

**Pros:**
- Truly shared resources
- Cross-campus teacher timetable visibility
- Standard curricula across district

**Cons:**
- Schema split confusion (which data lives where?)
- Migration complexity (teacher table moves from tenant to public)
- Foreign keys across schemas are awkward with GORM

#### Pattern C: Tenant Group + Read Replica (future architecture)

```
                    ┌─────────────────┐
                    │  Analytics View │
                    │  (read replica) │
                    └────────┬────────┘
                             │ async replication
┌───────────┐   ┌───────────┴───────────┐   ┌───────────┐
│ Campus A  │   │      Central DB       │   │ Campus C  │
│ (schema)  │──▶│   (aggregated view)   │◀──│ (schema)  │
└───────────┘   └───────────────────────┘   └───────────┘
```

**Pros:**
- No impact on tenant isolation
- Read replica can be optimized for analytics
- Async replication avoids runtime cross-schema queries

**Cons:**
- Operational complexity (logical replication setup)
- Data staleness (replication lag)
- Not needed until hundreds of campuses

### Recommendation

**For Phase 3-5:** Implement **Pattern A (schema-per-campus + cross-schema queries)** with a district admin role. This is the lowest-effort path and uses existing infrastructure.

**Key components:**

| Component | Location | Purpose |
|-----------|----------|---------|
| `School.DistrictID` | Existing school model (add column) | Group schools into a district |
| `MultiCampusService` | New module: `internal/modules/multicampus/` | Cross-schema queries, shared resource management |
| `DistrictAdmin` role | Existing RBAC | Super-admin view across campus group |
| `CrossTenantAnalytics` | `analytics/service.go` (extend) | Consolidated dashboards across campuses |

### Data Model Addition

```sql
-- Add to schools table (public schema)
ALTER TABLE schools ADD COLUMN district_id BIGINT;
ALTER TABLE schools ADD COLUMN campus_type VARCHAR(50) DEFAULT 'main'; -- main, branch, affiliate

-- New: districts table (public schema)
CREATE TABLE districts (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    settings JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Integration Points

| Integration | How It Works | Notes |
|-------------|-------------|-------|
| Auth (cross-campus user) | Enrich JWT claims with `district_id` + list of accessible campus IDs | JWTAuth already handles claims |
| Analytics (consolidated) | Query each school in district → merge results server-side | Use goroutines for parallel queries |
| Report generation | ReportBuilder can generate "district-wide" reports by running same report across all campuses | Async via Asynq per-campus tasks |
| Shared teachers | Teacher assignment to multiple schools → cross-schema lookup | Complex — defer to later phase |
| Consolidated finance | Query all campus finance tables → unified GL | High demand from district admins |

### Build Order

1. **Phase 3:** Add `district_id` + `campus_type` to school model (simple migration)
2. **Phase 3:** District admin role + consolidated dashboard (reuse analytics module)
3. **Phase 4:** Cross-campus reporting (extend ReportBuilder to target multiple schemas)
4. **Phase 5:** Cross-campus user auth (JWT with campus list claims + school context switching)
5. **Phase 7+:** Shared resources (teachers, curricula across campuses) — only if explicitly needed
6. **Phase 9+:** Read replica for cross-tenant analytics — only at scale (100+ campuses)

---

## Feature Dependencies Graph

```
Phase 2                         Phase 3                        Phase 4
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│                  │     │                      │     │                      │
│ Parent-Teacher   │     │  Multi-Campus v1     │     │  Calendar Sync v1    │
│ Messages v1      │     │  (districts +        │     │  (iCal export)       │
│ (conversations + │     │   consolidated       │     │                      │
│  WebSocket)      │     │   dashboard)         │     │  iCal subscription   │
│                  │     │                      │     │                      │
└───────┬──────────┘     └──────────┬───────────┘     └──────────┬───────────┘
        │                          │                            │
        ▼                          ▼                            ▼
┌──────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│ Phase 5          │     │ Phase 6              │     │ Phase 7+             │
│                  │     │                      │     │                      │
│ Parent-Teacher   │     │ Multi-Campus v2      │     │ CalDAV server        │
│ Messages v2      │     │ (shared resources)   │     │ Google Calendar sync │
│ (email fallback, │     │                      │     │                      │
│  auto-alerts)    │     │ Cross-campus         │     │                      │
│                  │     │ reporting            │     │                      │
└──────────────────┘     └──────────────────────┘     └──────────────────────┘

                    Phase 2-4 (parallel)
                    ┌──────────────────────┐
                    │  Automated Reports   │
                    │  (ALREADY COMPLETE)  │
                    │  ─ Reference pattern │
                    │  for async workflows │
                    └──────────────────────┘
```

---

## Cross-Cutting Integration Patterns

### Pattern A: Service → Notification → WebSocket (for user-facing events)

```
Service.SaveScore()
  → ScoreService (business logic)
  → NotificationService.Create(gradePublished, userID, ...)
    → Save notification to tenant DB
    → WebSocket Hub.Broadcast(userRoom(schoolID, userID), notification)
      → Connected browser receives real-time toast/notification
```

**Used by:** Scores published, attendance marked, messages received, report generated

### Pattern B: Service → Queue → Service → Notification (for async workflows)

```
ReportService.Generate()
  → Enqueue Asynq task
  → Worker processes (PDF generation, may take seconds/minutes)
  → Worker calls NotificationService.Create() on completion
  → NotificationService persists + WS broadcasts
```

**Used by:** Report generation, backups, bulk email/SMS delivery

### Pattern C: Cross-Tenant Query (for multi-campus analytics)

```
DashboardService.GetDistrictAnalytics(districtID)
  → Find all schools in district
  → For each school (in goroutines):
      GetTenantDB(schoolID) → query relevant data
  → Merge results server-side
  → Return consolidated response
```

**Used by:** Multi-campus dashboards, district reporting

---

## Sources

- **WebSocket hub code** — `backend/internal/ws/` (HIGH confidence — read from codebase)
- **Notifications module** — `backend/internal/modules/notifications/` (HIGH confidence — read from codebase)
- **Communication module** — `backend/internal/modules/communication/` (HIGH confidence — read from codebase)
- **Messages module** — `backend/internal/modules/messages/` (HIGH confidence — exists but needs enhancement)
- **Report builder** — `backend/internal/modules/reportbuilder/` (HIGH confidence — read from codebase)
- **Parent dashboard** — `backend/internal/modules/parentdashboard/` (HIGH confidence — read from codebase)
- **iCal library recommendation** — `github.com/arran4/golang-ical` (MEDIUM confidence — WebSearch only, not verified with Context7)
- **Multi-tenant architecture patterns** — Bytebase blog, AWS SaaS Lens (MEDIUM confidence — multiple web sources agree)
- **CalDAV protocol** — RFC 4791, sabre.io, Easy!Appointments blog (MEDIUM confidence — well-established standards, multiple sources)
- **Parent-teacher communication patterns** — Edunation, HelloParent (MEDIUM confidence — vendor sources, consistent patterns)
