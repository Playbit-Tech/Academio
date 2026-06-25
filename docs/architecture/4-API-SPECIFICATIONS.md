# SchoolCare v3 — API Specifications & Event Architecture

---

## 1. API DESIGN PRINCIPLES

```
Base URL:     /api/v2 (current, maintained)
Format:       JSON
Auth:         Bearer JWT (access_token) / OAuth2 (for integrations)
Versioning:   URL-based (/api/v2) — all new endpoints go here
Rate Limit:   100 req/min per IP (default), higher tiers available
Pagination:   Cursor-based for lists, Page-based for simple queries
Idempotency:  Idempotency-Key header for mutations
```

### Response Envelope (Backward Compatible)
```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "cursor": "eyJpZCI6MTUwfQ=="
  }
}
```

### Error Response
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "category": "VALID",
    "details": {
      "email": "Email is already in use",
      "password": "Password must be at least 8 characters"
    }
  },
  "meta": null
}
```

---

## 2. API GROUPS OVERVIEW

| Group | Base Path | Module | Existing? |
|-------|-----------|--------|-----------|
| Health | `/health`, `/livez`, `/readyz` | Health | ✅ |
| Auth | `/api/v2/auth` | Auth | ✅ Upgrade |
| Users | `/api/v2/users` | User | ✅ Upgrade |
| User Single | `/api/v2/user` | User | ✅ Upgrade |
| Schools | `/api/v2/schools` | School | ✅ Upgrade |
| Invitations | `/api/v2/invite` | Invitation | ✅ |
| Academic | `/api/v2/academic` | Academic | ✅ Upgrade |
| Scores | `/api/v2/scores` | Score | ✅ Upgrade |
| Results | `/api/v2/results` | Result | ✅ Upgrade |
| Timetables | `/api/v2/timetables` | Timetable | ✅ |
| Bills | `/api/v2/bills` | Bill | ✅ |
| Payments | `/api/v2/payments` | Payment | ✅ |
| Multimedia | `/api/v2/media` | Multimedia | ✅ |
| **Admissions** | `/api/v2/admissions` | Admission | **NEW** |
| **CBA** | `/api/v2/cba` | CBA | **NEW** |
| **LMS** | `/api/v2/lms` | LMS | **NEW** |
| **Report Cards** | `/api/v2/report-cards` | Report Card | **NEW** |
| **Communication** | `/api/v2/communication` | Communication | **NEW** |
| **Library** | `/api/v2/library` | Library | **NEW** |
| **Hostel** | `/api/v2/hostel` | Hostel | **NEW** |
| **Transport** | `/api/v2/transport` | Transport | **NEW** |
| **Inventory** | `/api/v2/inventory` | Inventory | **NEW** |
| **HR** | `/api/v2/hr` | HR | **NEW** |
| **Finance** | `/api/v2/finance` | Finance | **NEW** |
| **Alumni** | `/api/v2/alumni` | Alumni | **NEW** |
| **Career** | `/api/v2/career` | Career | **NEW** |
| **Analytics** | `/api/v2/analytics` | Analytics | **NEW** |
| **AI** | `/api/v2/ai` | AI | **NEW** |
| **Notifications** | `/api/v2/notifications` | Notifications | **NEW** |
| **Search** | `/api/v2/search` | Search | **NEW** |

---

## 3. NEW API ENDPOINTS (OpenAPI 3.1 Style)

### Admissions API
```
┌──────────────────────────────────────────────────────────────────┐
│ ADMISSIONS MODULE                                                │
├──────────────────────────────────────────────────────────────────┤

GET    /api/v2/admissions/intakes                     → List intakes
POST   /api/v2/admissions/intakes                     → Create intake
GET    /api/v2/admissions/intakes/:id                  → Get intake
PUT    /api/v2/admissions/intakes/:id                  → Update intake
DELETE /api/v2/admissions/intakes/:id                  → Delete intake

GET    /api/v2/admissions/applications                 → List applications
POST   /api/v2/admissions/applications                 → Submit application (public)
GET    /api/v2/admissions/applications/:id             → Get application
PUT    /api/v2/admissions/applications/:id             → Update application
POST   /api/v2/admissions/applications/:id/submit     → Submit draft

GET    /api/v2/admissions/applications/:id/documents   → List documents
POST   /api/v2/admissions/applications/:id/documents   → Upload document
DELETE /api/v2/admissions/applications/:id/documents/:docId

POST   /api/v2/admissions/applications/:id/screen     → Screen application
GET    /api/v2/admissions/applications/:id/screening   → Get screening result

POST   /api/v2/admissions/applications/:id/exam       → Record entrance exam score
GET    /api/v2/admissions/applications/:id/exam-result → Get exam result

POST   /api/v2/admissions/applications/:id/offer      → Create offer
GET    /api/v2/admissions/applications/:id/offers      → List offers
POST   /api/v2/admissions/applications/:id/accept      → Accept offer
POST   /api/v2/admissions/applications/:id/decline     → Decline offer

POST   /api/v2/admissions/enroll                       → Enroll student

GET    /api/v2/admissions/dashboard                   → Admissions analytics
GET    /api/v2/admissions/forecast                    → AI enrollment forecast

# AI-powered endpoints
POST   /api/v2/admissions/ai/score                    → AI applicant scoring
POST   /api/v2/admissions/ai/assess-eligibility       → AI eligibility check
POST   /api/v2/admissions/ai/auto-review              → AI automated review
```

### CBA (Computer-Based Assessment) API
```
┌──────────────────────────────────────────────────────────────────┐
│ CBA MODULE                                                       │
├──────────────────────────────────────────────────────────────────┤

# Question Bank
GET    /api/v2/cba/categories                          → List categories
POST   /api/v2/cba/categories                          → Create category

GET    /api/v2/cba/questions                           → List questions (filterable)
POST   /api/v2/cba/questions                           → Create question
GET    /api/v2/cba/questions/:id                       → Get question
PUT    /api/v2/cba/questions/:id                       → Update question
DELETE /api/v2/cba/questions/:id                       → Delete question
POST   /api/v2/cba/questions/bulk-import               → Bulk import questions (CSV/Excel)
POST   /api/v2/cba/questions/:id/duplicate             → Duplicate question

# Exams
GET    /api/v2/cba/exams                               → List exams
POST   /api/v2/cba/exams                               → Create exam
GET    /api/v2/cba/exams/:id                           → Get exam with questions
PUT    /api/v2/cba/exams/:id                           → Update exam
DELETE /api/v2/cba/exams/:id                           → Delete exam
POST   /api/v2/cba/exams/:id/publish                  → Publish exam
POST   /api/v2/cba/exams/:id/archive                  → Archive exam
POST   /api/v2/cba/exams/:id/questions                → Add question to exam
DELETE /api/v2/cba/exams/:id/questions/:questionId     → Remove question

# Exam Sessions
POST   /api/v2/cba/exams/:id/start                    → Start exam session
POST   /api/v2/cba/sessions/:id/submit                → Submit exam
GET    /api/v2/cba/sessions/:id                       → Get session status
POST   /api/v2/cba/sessions/:id/pause                 → Pause exam
POST   /api/v2/cba/sessions/:id/resume                → Resume exam

# Answers & Grading
POST   /api/v2/cba/sessions/:id/answer                → Save answer
PUT    /api/v2/cba/sessions/:id/answers/:answerId     → Update answer
POST   /api/v2/cba/sessions/:id/grade                 → Grade exam (auto-grade)
POST   /api/v2/cba/sessions/:id/grade-essays          → Grade essays only

# Proctoring
POST   /api/v2/cba/sessions/:id/proctoring-event      → Log proctoring event
GET    /api/v2/cba/sessions/:id/proctoring-logs       → Get proctoring logs
POST   /api/v2/cba/sessions/:id/flag                  → Flag suspicious activity

# Grading Rules
GET    /api/v2/cba/grading-rules                      → List rules
POST   /api/v2/cba/grading-rules                      → Create rule
PUT    /api/v2/cba/grading-rules/:id                   → Update rule

# Analytics
GET    /api/v2/cba/analytics/exams                   → Exam performance analytics
GET    /api/v2/cba/analytics/questions                → Question difficulty analysis
GET    /api/v2/cba/analytics/students                 → Student performance analysis

# AI
POST   /api/v2/cba/ai/generate-questions             → AI generate questions
POST   /api/v2/cba/ai/grade-essay                    → AI grade single essay
POST   /api/v2/cba/ai/detect-cheating                → AI cheating detection analysis
```

### LMS (Learning Management) API
```
┌──────────────────────────────────────────────────────────────────┐
│ LMS MODULE                                                       │
├──────────────────────────────────────────────────────────────────┤

# Courses
GET    /api/v2/lms/courses                             → List courses
POST   /api/v2/lms/courses                             → Create course
GET    /api/v2/lms/courses/:id                         → Get course
PUT    /api/v2/lms/courses/:id                         → Update course
DELETE /api/v2/lms/courses/:id                         → Delete course
POST   /api/v2/lms/courses/:id/publish                → Publish course
POST   /api/v2/lms/courses/:id/archive                → Archive course

# Modules & Lessons
GET    /api/v2/lms/courses/:id/modules                 → List modules
POST   /api/v2/lms/courses/:id/modules                 → Create module
PUT    /api/v2/lms/modules/:id                         → Update module
DELETE /api/v2/lms/modules/:id                         → Delete module
POST   /api/v2/lms/modules/:id/reorder                → Reorder modules

GET    /api/v2/lms/modules/:id/lessons                 → List lessons
POST   /api/v2/lms/modules/:id/lessons                 → Create lesson
GET    /api/v2/lms/lessons/:id                         → Get lesson
PUT    /api/v2/lms/lessons/:id                         → Update lesson
DELETE /api/v2/lms/lessons/:id                         → Delete lesson

# Enrollments
GET    /api/v2/lms/courses/:id/enrollments            → List enrollments
POST   /api/v2/lms/courses/:id/enroll                 → Enroll student
POST   /api/v2/lms/enrollments/:id/complete           → Mark complete
POST   /api/v2/lms/enrollments/:id/drop               → Drop student

# Progress
GET    /api/v2/lms/enrollments/:id/progress           → Get student progress
POST   /api/v2/lms/lessons/:id/progress               → Update lesson progress

# Assignments
GET    /api/v2/lms/courses/:id/assignments            → List assignments
POST   /api/v2/lms/courses/:id/assignments            → Create assignment
PUT    /api/v2/lms/assignments/:id                    → Update assignment
DELETE /api/v2/lms/assignments/:id                    → Delete assignment
POST   /api/v2/lms/assignments/:id/submit             → Submit assignment
GET    /api/v2/lms/assignments/:id/submissions        → List submissions
POST   /api/v2/lms/submissions/:id/grade              → Grade submission

# Discussions
GET    /api/v2/lms/courses/:id/discussions            → List discussions
POST   /api/v2/lms/courses/:id/discussions            → Create discussion post
POST   /api/v2/lms/discussions/:id/reply              → Reply to post

# Analytics
GET    /api/v2/lms/analytics/courses                  → Course analytics
GET    /api/v2/lms/analytics/student/:id              → Student learning analytics
```

### AI Assistant API
```
┌──────────────────────────────────────────────────────────────────┐
│ AI MODULE                                                        │
├──────────────────────────────────────────────────────────────────┤

# General AI
POST   /api/v2/ai/chat                                → Chat with AI assistant
POST   /api/v2/ai/chat/stream                         → Stream AI response (SSE)
DELETE /api/v2/ai/conversations/:id                    → Delete conversation
GET    /api/v2/ai/conversations                       → List conversations
GET    /api/v2/ai/conversations/:id/messages          → Get conversation messages

# Academic Assistant (Students)
POST   /api/v2/ai/academic/ask                        → Ask academic question
POST   /api/v2/ai/academic/homework-help              → Get homework help
POST   /api/v2/ai/academic/study-plan                 → Generate study plan
POST   /api/v2/ai/academic/tutor                      → Subject tutoring session

# Teacher Assistant
POST   /api/v2/ai/teacher/lesson-plan                → Generate lesson plan
POST   /api/v2/ai/teacher/generate-questions          → Generate assessment questions
POST   /api/v2/ai/teacher/create-rubric               → Create grading rubric
POST   /api/v2/ai/teacher/grade-essay                → AI-assisted essay grading
POST   /api/v2/ai/teacher/classroom-insights          → Classroom insights & patterns

# Parent Assistant
POST   /api/v2/ai/parent/child-summary               → Generate child performance summary
POST   /api/v2/ai/parent/attendance-insights          → Attendance pattern insights
POST   /api/v2/ai/parent/recommendations             → Progress recommendations

# Career Guidance
POST   /api/v2/ai/career/recommend                   → Career recommendations
POST   /api/v2/ai/career/university-match            → University matching
POST   /api/v2/ai/career/skills-assessment           → Skills assessment
POST   /api/v2/ai/career/scholarship-match           → Scholarship matching
POST   /api/v2/ai/career/roadmap                     → Career roadmap generation

# Risk & Analytics
POST   /api/v2/ai/risk/predict                       → Predict at-risk students
POST   /api/v2/ai/risk/intervention                  → Generate intervention plan
POST   /api/v2/ai/analytics/class-performance        → Class performance summary
POST   /api/v2/ai/analytics/student-performance      → Student deep analysis
POST   /api/v2/ai/analytics/executive-summary        → Executive summary generation
```

### Natural Language Search API
```
┌──────────────────────────────────────────────────────────────────┐
│ SEARCH MODULE                                                    │
├──────────────────────────────────────────────────────────────────┤

POST   /api/v2/search                              → Natural language search
# Body: { "query": "Show students with attendance below 70%" }
# Body: { "query": "Which students are likely to fail Mathematics?" }
# Body: { "query": "Show unpaid fees above ₦100,000" }

POST   /api/v2/search/suggest                      → Search suggestions
POST   /api/v2/search/explain                      → Explain search results
```

### Communication Hub API
```
┌──────────────────────────────────────────────────────────────────┐
│ COMMUNICATION MODULE                                             │
├──────────────────────────────────────────────────────────────────┤

# Templates
GET    /api/v2/communication/templates              → List templates
POST   /api/v2/communication/templates              → Create template
PUT    /api/v2/communication/templates/:id           → Update template

# Send Messages
POST   /api/v2/communication/send/sms               → Send SMS
POST   /api/v2/communication/send/email             → Send Email
POST   /api/v2/communication/send/push              → Send Push notification
POST   /api/v2/communication/send/whatsapp          → Send WhatsApp message
POST   /api/v2/communication/send/bulk              → Bulk send (multi-channel)

# Campaigns
GET    /api/v2/communication/campaigns              → List campaigns
POST   /api/v2/communication/campaigns              → Create campaign
POST   /api/v2/communication/campaigns/:id/send     → Send campaign
GET    /api/v2/communication/campaigns/:id/stats    → Campaign statistics

# Webhooks (inbound)
POST   /api/v2/communication/webhooks/twilio        → Twilio inbound
POST   /api/v2/communication/webhooks/sendgrid      → SendGrid inbound
POST   /api/v2/communication/webhooks/whatsapp      → WhatsApp inbound

# Logs
GET    /api/v2/communication/messages               → Message history
GET    /api/v2/communication/messages/:id           → Message details
GET    /api/v2/communication/delivery-stats         → Delivery statistics
```

### Report Card API
```
┌──────────────────────────────────────────────────────────────────┐
│ REPORT CARD MODULE                                               │
├──────────────────────────────────────────────────────────────────┤

GET    /api/v2/report-cards/students/:id            → Get student report card
GET    /api/v2/report-cards/students/:id/subjects   → Subject breakdown
GET    /api/v2/report-cards/students/:id/trends     → Performance trends
POST   /api/v2/report-cards/students/:id/generate   → Generate report card
POST   /api/v2/report-cards/batch/generate          → Batch generate (class)
GET    /api/v2/report-cards/students/:id/pdf        → Download PDF
GET    /api/v2/report-cards/templates               → List templates
POST   /api/v2/report-cards/templates               → Create template
POST   /api/v2/report-cards/ai/summary             → AI generate academic summary
```

### Alumni API
```
┌──────────────────────────────────────────────────────────────────┐
│ ALUMNI MODULE                                                    │
├──────────────────────────────────────────────────────────────────┤

GET    /api/v2/alumni                               → List alumni
POST   /api/v2/alumni                               → Register alumni
GET    /api/v2/alumni/:id                           → Get alumni profile
PUT    /api/v2/alumni/:id                           → Update profile
GET    /api/v2/alumni/directory                     → Searchable directory

GET    /api/v2/alumni/:id/careers                   → Career history
POST   /api/v2/alumni/:id/careers                   → Add career entry

GET    /api/v2/alumni/events                        → List events
POST   /api/v2/alumni/events                        → Create event
GET    /api/v2/alumni/events/:id                    → Get event
POST   /api/v2/alumni/events/:id/register           → Register for event

GET    /api/v2/alumni/mentorships                   → List mentorships
POST   /api/v2/alumni/mentorships                   → Request mentorship
PUT    /api/v2/alumni/mentorships/:id               → Update mentorship

GET    /api/v2/alumni/donations                     → List donations
POST   /api/v2/alumni/donations                     → Make donation

GET    /api/v2/alumni/campaigns                     → Fundraising campaigns
POST   /api/v2/alumni/campaigns                     → Create campaign

POST   /api/v2/alumni/verify                        → Submit verification request
GET    /api/v2/alumni/verification-requests         → List verification requests

GET    /api/v2/alumni/jobs                          → Job board
POST   /api/v2/alumni/jobs                          → Post job

GET    /api/v2/alumni/stats                         → Alumni statistics
GET    /api/v2/alumni/ai/engagement-prediction      → AI engagement prediction
GET    /api/v2/alumni/ai/donation-potential         → AI donation potential
```

---

## 4. EVENT ARCHITECTURE

### Event Bus Design

```
┌─────────────────────────────────────────────────────────────────┐
│                      EVENT BUS                                   │
│                                                                  │
│  Redis Streams → Kafka (future)                                   │
│                                                                  │
│  Publishers (modules) → Event Bus → Subscribers (handlers)       │
│                                                                  │
│  Each event has:                                                  │
│  - id (UUID)                                                      │
│  - type (string, e.g., "student.created")                         │
│  - source (module name)                                           │
│  - timestamp (RFC3339)                                            │
│  - data (JSON payload)                                            │
│  - metadata (tenant_id, user_id, correlation_id)                  │
└─────────────────────────────────────────────────────────────────┘
```

### Event Types

```
# Student Lifecycle Events
student.created                → New student record created
student.updated                → Student profile updated
student.transferred           → Student changed level/campus
student.graduated             → Student graduated
student.dropped_out          → Student dropped out

# Enrollment Events
application.submitted         → Application submitted
application.screened         → Application screened
application.offered          → Offer made
application.accepted         → Offer accepted
application.enrolled         → Student enrolled

# Academic Events
attendance.marked            → Attendance recorded
score.saved                  → Scores saved
result.approved             → Result approved
result.published             → Results published
report.card.generated       → Report card generated

# Financial Events
fee.bill.created            → Fee bill created
payment.received            → Payment received
payment.failed              → Payment failed
invoice.generated           → Invoice generated

# Communication Events
notification.sent           → Notification sent
sms.sent                    → SMS sent
email.sent                  → Email sent
whatsapp.sent               → WhatsApp sent

# AI Events
ai.analysis.completed       → AI analysis done
ai.risk.identified          → Risk flagged
ai.insight.generated        → Insight generated
ai.recommendation.created   → Recommendation made

# System Events
user.registered             → User registered
user.logged_in              → User logged in
user.password_changed       → Password changed
tenant.config.updated       → Tenant config changed
subscription.changed        → Plan changed
```

### Event Flow Examples

```
1. Student Enrollment Flow:
   application.accepted → student.created → enrollment.created
   → notification.sent (welcome email)
   → analytics.snapshot (enrollment count updated)
   → ai.analysis (enrollment forecast updated)

2. Fee Payment Flow:
   payment.received → fee.bill.updated
   → notification.sent (receipt)
   → analytics.snapshot (revenue updated)
   → student.status.updated (financial clearance)

3. Result Publication Flow:
   result.approved → result.published
   → notification.sent (result available)
   → report.card.generated
   → analytics.snapshot (performance data)
   → ai.analysis (risk assessment updated)
```

---

## 5. WEBHOOK ARCHITECTURE (Outbound)

SchoolCare can send webhooks to customer-configured endpoints for real-time integration.

```
POST /webhooks/tenant/:webhook_id   → Customer endpoint
Headers:
  X-SchoolCare-Signature: sha256=...
  X-SchoolCare-Event: student.created
  X-SchoolCare-Delivery: 1
  Content-Type: application/json

Body:
{
  "event": "student.created",
  "timestamp": "2026-06-24T12:00:00Z",
  "data": {
    "id": 12345,
    "name": "John Doe",
    "email": "john@example.com",
    "level": "SS1",
    "school_id": 42
  }
}
```

---

## 6. API VERSIONING STRATEGY

```
All endpoints: /api/v2/*     → Single version, continuously evolved

Principles:
1. Never remove an existing endpoint or change response field types
2. Add new fields to responses (clients ignore unknown fields)
3. Use query parameters for new optional behavior
4. Deprecate old behaviors with Sunset HTTP header
5. All new modules use the same /api/v2/ prefix
```

### Backward Compatibility Rules
All new modules and endpoints are added under the same `/api/v2/` prefix:
1. Never remove an existing endpoint
2. Never change an existing response field type or meaning
3. Add new fields to responses (clients ignore unknown fields)
4. Use query parameters for new optional behavior
5. Existing modules continue working exactly as before
6. New modules are additive — they don't modify existing module behavior
