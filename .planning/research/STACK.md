# Technology Stack — Advanced School Management Additions

**Researched:** 2026-07-18
**Mode:** Ecosystem (gap analysis)
**Confidence:** MEDIUM (some libraries verified via Context7, others via web search)

## Context

This document identifies **missing stack components** needed for advanced school management features. The existing stack (Go 1.26 / Gin / GORM / PostgreSQL / React 19 / Vite / TanStack Router / shadcn/ui / Redis) is well-established and not re-evaluated here. Focus is on what the current stack **lacks** that equivalent school management platforms commonly use.

**Things the existing system already has (not re-researched):**
- Email (SendGrid via plain HTTP — no SDK dependency)
- SMS (Twilio via plain HTTP — no SDK dependency)
- AI (OpenAI + Gemini with custom gateway)
- Vector store (Qdrant via REST API)
- Observability (OpenTelemetry, Prometheus)
- Task queue (Asynq, Redis-backed)
- WebSockets (gorilla/websocket with room-based pub/sub)
- Excel generation (excelize v2.11.0)
- S3 storage (AWS SDK v2)
- Caching (Redis CacheService)
- Rate limiting (Redis sliding window + in-memory)
- API docs (Swagger via swaggo)
- Tenant feature flags (DB-based, per-school feature toggles)
- HTML report cards (Go template — HTML only, no actual PDF conversion)

---

## Recommended Additions

### 1. PDF Generation (Backend — High Priority)

**Current state:** `backend/pkg/pdf/generator.go` generates HTML only via Go templates. No actual PDF is produced — just an HTML string. The report card feature renders HTML, but there is no mechanism to deliver a downloadable/printable PDF.

**Recommendation:** Gotenberg v8.34.0 + nativebpm/gotenberg-client v1.9.2

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Gotenberg | v8.34.0 (Docker) | Headless Chromium HTML→PDF conversion service | Pixel-perfect PDF rendering with CSS/font support, office doc conversion, PDF merge/split/watermark |
| `github.com/nativebpm/gotenberg-client` | v1.9.2 | Go HTTP client for Gotenberg API | Stream-first, minimal deps, supports webhooks for async PDF generation |

**Why Gotenberg over alternatives:**
- **chromedp** — Requires embedding Chrome/Chromium in the Go binary. Heavy, complex to deploy, need to manage browser lifecycle. Gotenberg is a separate Docker container — cleaner separation.
- **wkhtmltopdf** — Unmaintained, outdated rendering engine. No CSS Grid/Flexbox support.
- **go-wkhtmltopdf** — Same problem as wkhtmltopdf.
- **@react-pdf/renderer** — Frontend-only solution (see below). Good for client-side preview, wrong for server-side batch generation.

**What to build:**
```
backend/pkg/pdf/
├── generator.go      # Existing HTML-only generator (keep)
├── gotenberg.go       # NEW: Gotenberg client wrapper
│   └── ConvertHTML(ctx, html, options) → (io.Reader, error)
│   └── ConvertURL(ctx, url, options) → (io.Reader, error)
│   └── Merge(ctx, pdfs...) → (io.Reader, error)
```

**Installation:**
```bash
# Go dependency
go get github.com/nativebpm/gotenberg-client@v1.9.2

# Docker (docker-compose addition)
services:
  gotenberg:
    image: gotenberg/gotenberg:8.34.0
    ports:
      - "3000:3000"
```

**Use cases:**
- Report cards (currently HTML-only)
- Transcripts
- Student certificates
- Invoices
- Admission letters
- Bulk PDF generation via Asynq queue

**Confidence:** HIGH (verified via Context7 — Gotenberg is mature, 12.5K GitHub stars, 68M+ Docker pulls)

---

### 2. PDF Generation (Frontend — Optional, for Client-Side Preview)

**Recommendation:** @react-pdf/renderer v4.5.1

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@react-pdf/renderer` | ^4.5.1 | Client-side PDF preview/generation in React | Same component model as React, works for print-preview dialogs |

**When to use:** Client-side PDF **preview** (before server generates the final version), or for simple PDFs where server-side generation is overkill (e.g., printing a single student's timetable).

**When NOT to use:** Batch PDF generation, document merging, complex formatting with dynamic fonts — use Gotenberg server-side instead.

**Installation:**
```bash
yarn add @react-pdf/renderer@^4.5.1
```

**Confidence:** HIGH (verified via npm registry — 3.5M weekly downloads, active maintenance)

---

### 3. Push Notifications (Mobile + Browser — Medium Priority)

**Current state:** In-app notifications work via WebSocket when the user is actively on the site. There is NO push notification delivery:
- No Firebase Cloud Messaging (FCM) for mobile apps
- No Web Push API for browser notifications
- Parents/teachers miss time-sensitive alerts (fee reminders, attendance notifications, grade postings)

**Recommendation:** firebase.google.com/go (Firebase Admin SDK) + Web Push API

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `firebase.google.com/go/v4` | v4.20.0 | Firebase Admin SDK for Go | Official Google SDK for FCM messaging — supports Android, iOS, Web |
| `github.com/appleboy/go-fcm` | v1.2.11 | Alternative lightweight FCM client | Lighter than full Admin SDK, good if only FCM is needed (not other Firebase services) |

**Why FCM over alternatives:**
- **Firebase Cloud Messaging** — Free, cross-platform (Android/iOS/Web), integrates with Web Push API, device group messaging, topic-based subscriptions
- **OneSignal** — Third-party dependency, paid tier for volume
- **Custom Web Push** — Possible but requires managing VAPID keys, service workers, subscription storage. FCM wraps this with a simpler API.

**Architecture:**
```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  Backend     │────▶│  FCM Server  │────▶│  Mobile App    │
│  (Go/Gin)    │     │  (Google)    │     │  (Push)        │
└─────────────┘     └──────────────┘     └────────────────┘
       │                                        │
       │  WebSocket (existing)                   │
       ▼                                        ▼
┌─────────────┐                         ┌────────────────┐
│  Web App    │                         │  Browser Push   │
│  (In-app)   │                         │  (Web Push API) │
└─────────────┘                         └────────────────┘
```

**Integration points:**
- `backend/internal/communication/` — Add FCM as a push notification provider alongside existing SendGrid/Twilio providers
- `backend/internal/queue/handlers/` — Create `push_handler.go` for async push delivery via Asynq

**Implementation pattern (consistent with existing communication providers):**
```go
// backend/internal/communication/fcm.go
type FCMProvider struct {
    client *messaging.Client
}

func (p *FCMProvider) Send(ctx context.Context, token string, title, body string) error {
    msg := &messaging.Message{
        Token: token,
        Notification: &messaging.Notification{Title: title, Body: body},
    }
    _, err := p.client.Send(ctx, msg)
    return err
}
```

**Use cases:**
- Fee payment confirmation
- Attendance alerts to parents
- Grade posting notifications
- Timetable change alerts
- Admission status updates

**Confidence:** MEDIUM (FCM ecosystem is mature but school mobile app may not exist yet — verify mobile strategy first)

---

### 4. OAuth / SSO (Medium Priority)

**Current state:** Only email/password authentication exists. No social login or enterprise SSO (Google Workspace, Microsoft 365). Many schools use Google/Microsoft for staff accounts and expect SSO integration.

**Recommendation:** markbates/goth v1.80+

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `github.com/markbates/goth` | v1.80+ | Multi-provider OAuth/OAuth2/SSO library | 30+ providers (Google, Microsoft, Apple, Facebook, GitHub), clean API, widely adopted |

**Why Goth over alternatives:**
- **Goth** — Most comprehensive provider list, battle-tested (2.5K+ GitHub stars), designed for exactly this use case
- **coreos/go-oidc/v3** — OpenID Connect only, single-protocol. Good if ONLY Google Workspace is needed. Goth handles OAuth2 providers without OIDC.
- **Custom implementation** — Not worth the effort for 30+ providers.

**Architecture:**
```
┌──────────────────────────────────────┐
│  Existing Auth Flow                  │
│  ┌─────────┐    ┌───────────────┐   │
│  │ Login   │───▶│ JWT Generation │   │
│  │ (email) │    │ (auth service) │   │
│  └─────────┘    └───────────────┘   │
├──────────────────────────────────────┤
│  OAuth/SSO Flow (NEW)               │
│  ┌─────────┐    ┌──────┐    ┌────┐  │
│  │ Google  │───▶│ Goth │───▶│ JWT │  │
│  │ Microsoft│   │      │    │     │  │
│  │ Apple   │   └──────┘    └────┘  │
│  └─────────┘                        │
└──────────────────────────────────────┘
```

**Key constraint:** OAuth users must still be linked to existing User records (shared `public.users` table). The SSO provider email becomes the lookup key.

**What NOT to do:** Don't replace the existing auth system. Add OAuth as an additional authentication method alongside email/password.

**Use cases:**
- Staff login via Google Workspace / Microsoft 365
- Parent portal login via Google/Microsoft accounts
- Eliminates password management for SSO-connected users

**Confidence:** HIGH (Goth is well-established, Context7 score 86, used in production by thousands of apps)

---

### 5. Image Processing & Optimization (Medium Priority)

**Current state:** Files are uploaded and stored as-is (via `backend/internal/modules/multimedia/` and S3). No resizing, thumbnail generation, or format optimization. Student photos, staff photos, and school logos are stored at full resolution.

**Recommendation:** disintegration/imaging v1.6.2

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `github.com/disintegration/imaging` | v1.6.2 | Pure Go image resizing/cropping/optimization | Zero CGO dependencies, simple API, supports JPEG/PNG/GIF/WebP |

**Why imaging over alternatives:**
- **imaging** — Pure Go, no system deps. Resize, thumbnail, rotate, adjust colors. Perfect for server-side image ops.
- **nfnt/resize** — Abandoned (last commit 2018). Avoid.
- **govips/libvips** — Requires C library (libvips). Faster but adds deployment complexity.
- **ImageMagick CLI** — Subprocess management, terrible for concurrency. Avoid.

**Integration:**
```go
// In multimedia upload pipeline
import "github.com/disintegration/imaging"

func processUpload(file io.Reader) (original, thumbnail io.Reader, err error) {
    img, err := imaging.Decode(file)
    if err != nil { return nil, nil, err }
    
    thumb := imaging.Thumbnail(img, 200, 200, imaging.Lanczos)
    // Save both original and thumbnail
}
```

**When to process:** During upload (synchronous or via Asynq task). Store full-resolution original + generate thumbnails. Thumbnails serve in lists/grids; full-res serves on detail view.

**Storage approach:** Store thumbnails alongside originals in S3 with a naming convention:
- `media/photos/student_42.jpg` (original)
- `media/photos/thumb_student_42.jpg` (200x200 thumbnail)

**Use cases:**
- Student/staff profile photos
- School logo (generate favicon sizes)
- Document thumbnails in admission forms
- Photo gallery

**Confidence:** MEDIUM (imaging is well-maintained, but verify v1.6.2 is latest — GitHub: disintegration/imaging)

---

### 6. Scheduled Job / Cron System (Medium Priority)

**Current state:** Asynq handles ad-hoc task queuing but has **no built-in cron/scheduling**. There is no mechanism for daily, weekly, or monthly recurring jobs (e.g., nightly backup verification, weekly attendance reports, monthly fee reminders, daily grade digest emails).

**Recommendation:** robfig/cron v3

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `github.com/robfig/cron/v3` | v3.0.1+ | Cron expression parser and job scheduler | De facto standard Go cron library, timezone support, recovery from panics |

**Why cron over alternatives:**
- **robfig/cron** — Most popular Go cron library (5K+ GitHub stars), stable API, supports `@weekly`, `@monthly`, etc.
- **Asynq Scheduler** — Asynq has a `Scheduler` type, but it's experimental and less documented. Using robfig/cron is more reliable.
- **System cron** — Not portable across deployment environments. Docker containers may not have crond.

**Architecture:**
```
┌─────────────────────────────────────────┐
│  Cron Runner (goroutine in server)      │
│  ┌─────────────────────────────────────┐│
│  │  Daily 02:00 → Asynq: backup tenant ││
│  │  Weekly Mon 08:00 → Asynq: report   ││
│  │  Monthly 1st 09:00 → Asynq: billing ││
│  │  @every 30m → Health check          ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
         │ enqueue tasks to
         ▼
┌─────────────────┐
│  Asynq Queue    │ (existing)
└─────────────────┘
```

**Implementation pattern:**
- A single `CronRunner` struct that initializes cron jobs at server startup
- Each cron job enqueues an Asynq task (not directly executes work) — keeps execution decoupled, retry-able, and observable
- Cron config could be managed via the tenant feature flags for per-school scheduled tasks

**What NOT to do:** Don't run business logic directly in cron callbacks. Always delegate to Asynq so work survives restarts and can be retried.

**Use cases:**
- Nightly tenant backup verification
- Weekly attendance report generation
- Monthly fee invoice batch generation
- Scheduled report card publication
- Daily grade digest emails to parents
- Automatic stale session cleanup

**Confidence:** HIGH (robfig/cron is the Go community standard, Context7 score 87+)

---

### 7. Internationalization (i18n) — Backend (Low Priority)

**Current state:** No i18n support anywhere. All UI text is hardcoded in English. School systems often serve multilingual communities (parents, students speaking different languages).

**Recommendation:** nicksnyder/go-i18n v2

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `github.com/nicksnyder/go-i18n/v2` | v2.4+ | Go i18n library with pluralization support | Battle-tested (2.5K GitHub stars), supports JSON/YAML/TOML message files, plural rules for 200+ languages |

**Why go-i18n over alternatives:**
- **go-i18n** — Most mature Go i18n library, active maintenance, `goi18n` CLI for extracting/merging translations
- **Custom map approach** — Fragile, doesn't scale. Avoid.

**Implementation approach:**
- Start with translations for **email/SMS templates** (most impactful — communication goes to parents)
- Then API error messages → notification text → eventually UI
- Use accept-language header for API-level locale detection

**What NOT to do:** Don't attempt full frontend i18n until the backend is internationalized first. Start with the most visible touchpoint: parent-facing communications.

**Use cases:**
- Fee reminder emails in parent's language
- SMS notifications in local language
- Report card comments in multiple languages
- Admission form labels

**Confidence:** HIGH (go-i18n is well-established in the Go ecosystem)

---

### 8. Internationalization (i18n) — Frontend (Low Priority)

**Recommendation:** react-i18next v15+

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `react-i18next` | ^15.x | React internationalization framework | 9K+ GitHub stars, supports lazy loading translation files, TypeScript, interpolation |

**Why react-i18next over alternatives:**
- **react-i18next** — De facto React i18n standard, works with SSR, supports namespacing
- **react-intl (FormatJS)** — Good but heavier, more ICU-message-focused
- **LinguiJS** — Newer, smaller bundle, but less ecosystem

**Defer until backend i18n is complete.** The frontend should consume locale from the backend (accept-language header → return translated strings in API responses). Don't maintain two independent translation systems.

**Confidence:** HIGH (react-i18next is the React community standard)

---

### 9. Error Tracking (Low Priority)

**Current state:** Errors are logged via `pkg/logger` (slog wrapper) and surfaced via OpenTelemetry traces. There is no centralized error aggregation, alerting, or trend analysis.

**Recommendation:** Sentry

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `github.com/getsentry/sentry-go` | v0.29+ | Error tracking and performance monitoring | Industry standard, Go SDK, Gin integration, breadcrumb support |

**Why Sentry over alternatives:**
- **Sentry** — Free tier, Gin middleware available (`sentrygin`), breadcrumb support for debugging, release tracking
- **Honeybadger** — Paid-only, smaller Go ecosystem
- **Rollbar** — Paid-only, less Go-native feel
- **Log-based (ELK/Promtail/Loki)** — Different use case (general logs vs error tracking)

**Integration:**
```go
import (
    "github.com/getsentry/sentry-go"
    sentrygin "github.com/getsentry/sentry-go/gin"
)

func main() {
    sentry.Init(sentry.ClientOptions{
        Dsn: cfg.SentryDSN,
        Environment: cfg.Environment,
    })
    
    r := gin.Default()
    r.Use(sentrygin.New(sentrygin.Options{}))
}
```

**What Sentry adds beyond current logging:**
- Error grouping and deduplication
- Alerting on new/critical errors
- Performance monitoring (transaction traces)
- Release tracking (see which version introduced an error)
- User feedback on errors

**Confidence:** MEDIUM (Sentry Go SDK is mature, but pricing may be a concern at scale — verify free tier limits)

---

### 10. API Gateway / Advanced Rate Limiting (Deferred)

**Current state:** A basic rate limiter exists (in-memory + Redis sliding window) in `backend/internal/middleware/security.go`. It's sufficient for current scale.

**Recommendation:** Defer. If rate limiting becomes a bottleneck, consider a reverse proxy layer:
- **Nginx** — Built-in rate limiting, IP whitelisting, request buffering
- **Kong** — Plugin-based API gateway with rate limiting, auth, observability
- **Cloudflare** — If deployed behind Cloudflare, their rate limiting + WAF is superior

**Why defer:** The existing middleware-level rate limiting handles DDoS protection and abuse prevention. API gateway complexity is not justified until the system serves 50+ schools.

---

### 11. Search Infrastructure (Deferred)

**Current state:** PostgreSQL `ILIKE` queries for basic search. One tsvector reference in enrollment forecaster. No dedicated search infrastructure.

**Recommendation:** Defer. Use PostgreSQL full-text search (`tsvector`/`tsquery` with GIN indexes) before introducing Elasticsearch or Meilisearch. PostgreSQL FTS is sufficient for:
- Student name search
- Class/level search
- Subject/topic search

**Trigger for Elasticsearch/Meilisearch:** When pgFTS query latency exceeds 200ms or the system needs fuzzy search across 100K+ records.

**Confidence:** HIGH (PostgreSQL FTS is well-documented and sufficient at this scale)

---

## Comparison: Addressed vs Deferred

| Category | Recommended | Status | Priority | Confidence |
|----------|-------------|--------|----------|------------|
| PDF generation (server) | Gotenberg + Go client | 🔴 Missing | HIGH | HIGH |
| Push notifications | Firebase Cloud Messaging | 🔴 Missing | MEDIUM | MEDIUM |
| OAuth/SSO | Goth | 🔴 Missing | MEDIUM | HIGH |
| Image processing | disintegration/imaging | 🔴 Missing | MEDIUM | MEDIUM |
| Scheduled jobs | robfig/cron | 🔴 Missing | MEDIUM | HIGH |
| i18n (backend) | go-i18n | 🔴 Missing | LOW | HIGH |
| i18n (frontend) | react-i18next | 🔴 Missing | LOW | HIGH |
| Error tracking | Sentry | 🔴 Missing | LOW | MEDIUM |
| API gateway | Defer | ✅ Deferred | — | — |
| Search index | PostgreSQL FTS → Meilisearch | ✅ Deferred | — | — |
| Feature flags | DB-based (existing) | ✅ Existing | — | — |
| PDF preview (frontend) | @react-pdf/renderer | 🔴 Missing | Optional | HIGH |

## Anti-Recommendations (What NOT to Use)

| Technology | Why Not |
|------------|---------|
| wkhtmltopdf | Unmaintained, no CSS Flexbox/Grid support, security issues |
| nfnt/resize (Go) | Abandoned since 2018 — use disintegration/imaging instead |
| Chromedp for PDF | Embeds full browser in binary — 200MB+ bloat, deployment headache |
| Elasticsearch | Overkill for current scale. PostgreSQL FTS + GIN indexes suffice for <100K records |
| LaunchDarkly / Flagsmith | Per-school DB feature flags are sufficient. External feature flag service adds latency, cost, and another dependency for minimal gain |
| Write our own OAuth | Never write auth from scratch. Goth covers 30+ providers with tested, audited code |
| FCM legacy HTTP API | Use HTTP v1 API (Firebase Admin SDK or appleboy/go-fcm). Legacy uses API keys with broader permissions |

## Go Dependency Additions Summary

```bash
# HIGH priority
go get github.com/nativebpm/gotenberg-client@v1.9.2

# MEDIUM priority
go get github.com/markbates/goth@v1.80.0
go get github.com/disintegration/imaging@v1.6.2
go get github.com/robfig/cron/v3@v3.0.1
go get github.com/appleboy/go-fcm@v1.2.11

# LOW priority
go get github.com/nicksnyder/go-i18n/v2@v2.4.0
go get github.com/getsentry/sentry-go@v0.29.0
```

## Frontend Dependency Additions Summary

```bash
# Optional (client-side PDF preview)
yarn add @react-pdf/renderer@^4.5.1

# LOW priority (after backend i18n)
yarn add react-i18next@^15.0.0 i18next@^24.0.0
```

## Docker Additions

```yaml
# docker-compose.yml addition for PDF generation
services:
  gotenberg:
    image: gotenberg/gotenberg:8.34.0
    ports:
      - "3000:3000"
    # No volumes needed — stateless
    restart: unless-stopped
```

## Sources

- Context7: `/gotenberg/gotenberg/v8` — MEDIUM confidence (library verified, version via web search)
- Context7: `/markbates/goth` — HIGH confidence (Context7 score 86)
- Context7: `/disintegration/imaging` — HIGH confidence (Context7 score 97.5)
- Context7: `/robfig/cron` — HIGH confidence (Context7 score 87+)
- Context7: `/nicksnyder/go-i18n` — HIGH confidence (Context7 score 87+)
- npm registry: `@react-pdf/renderer@4.5.1` — HIGH confidence
- pkg.go.dev: `github.com/appleboy/go-fcm@v1.2.11` — MEDIUM confidence
- pkg.go.dev: `github.com/nativebpm/gotenberg-client@v1.9.2` — MEDIUM confidence (newer library)
- Codebase audit: `backend/pkg/pdf/generator.go`, `backend/internal/communication/`, `backend/internal/modules/notifications/` — HIGH confidence (directly verified)

---

*Research for roadmap phase planning. Integrate with SUMMARY.md for phase ordering decisions.*
