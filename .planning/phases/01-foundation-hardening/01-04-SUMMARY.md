---
phase: 01-foundation-hardening
plan: 04
subsystem: infra
tags: [gotenberg, pdf, docker, report-cards]
requires:
  - phase: 01-foundation-hardening
    plan: 01
    provides: migration infrastructure, database models
provides:
  - Gotenberg Docker service with health check
  - GotenbergClient implementing Generator with HTML-to-PDF conversion
  - Fixed buildSubjectData() querying real scores from scores table
  - PDF generation on-the-fly for report card downloads
  - Dev-only PDF render endpoint for testing
affects: frontend report card download UI, deployment configuration
tech-stack:
  added:
    - gotenberg/gotenberg:8 (Docker)
  patterns:
    - Gotenberg PDF conversion via multipart HTTP POST
    - Type-assertion fallback for PDF generation (Gotenberg or HTML-only)
    - Dev-only route gating by APP_ENV
key-files:
  created:
    - backend/pkg/pdf/gotenberg.go
    - backend/pkg/pdf/gotenberg_test.go
  modified:
    - backend/docker-compose.yml
    - backend/internal/config/config.go
    - backend/pkg/pdf/generator.go
    - backend/internal/modules/reportcard/service.go
    - backend/internal/modules/reportcard/handler.go
    - backend/internal/router/setup.go
key-decisions:
  - "GotenbergClient uses type assertion to detect GeneratePDF support — HTMLGenerator returns error for PDF"
  - "PDF render endpoint gated by APP_ENV != production (dev-only)"
  - "buildSubjectData() adapted to actual schema (scores table with JSON blob) instead of plan's assumed grade_item_scores"
  - "session/term string matching via Session model lookup for score query filtering"
requirements-completed:
  - INFRA-04
  - INFRA-06
duration: 25min
completed: 2026-07-19
---

# Phase 01 Plan 04: Gotenberg PDF Integration Summary

**Gotenberg v8.x Docker service with Go client wrapper, fixed buildSubjectData() returning real scores, and on-the-fly PDF generation for report card downloads**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-19
- **Completed:** 2026-07-19
- **Tasks:** 2
- **Files modified:** 6 (+2 created)

## Accomplishments

- Added Gotenberg v8.x service to docker-compose.yml with health check and api dependency
- Created GotenbergClient implementing Generator with GeneratePDF via multipart HTTP POST to `/forms/chromium/convert/html`
- Extended Generator interface with GeneratePDF method (HTMLGenerator returns error as fallback)
- Fixed buildSubjectData() to query real subject scores from the scores table with subject name joins
- Added GeneratePDF service method for on-the-fly PDF generation with Gotenberg + HTML fallback
- Fixed DownloadReportCard handler to serve PDF bytes directly instead of redirecting to empty PDFURL
- Wired Gotenberg client in setup.go with env-conditional initialization
- Added dev-only POST /api/v2/pdf/render endpoint for testing Gotenberg conversion

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Gotenberg service + Go client** — `482fc57` / `5a616cd` (feat)
   - docker-compose.yml, config.go, generator.go, gotenberg.go, gotenberg_test.go
2. **Task 2: Wire Gotenberg into report card pipeline** — `00f2885` / `dc58ce3` (feat)
   - service.go, handler.go, setup.go

**Plan metadata:** (included in Task 2 commit)

## Files Created/Modified

- `backend/docker-compose.yml` - Added gotenberg service with health check, GOTENBERG_URL env, api dependency
- `backend/internal/config/config.go` - Added GotenbergConfig with GOTENBERG_URL env var
- `backend/pkg/pdf/generator.go` - Added GeneratePDF to Generator interface, HTMLGenerator fallback
- `backend/pkg/pdf/gotenberg.go` - **NEW** GotenbergClient implementing Generator with GeneratePDF via HTTP POST
- `backend/pkg/pdf/gotenberg_test.go` - **NEW** Unit tests for GotenbergClient and HTMLGenerator fallback
- `backend/internal/modules/reportcard/service.go` - Fixed buildSubjectData() with real score queries, added GeneratePDF method, updated generatePDF() with Gotenberg conversion
- `backend/internal/modules/reportcard/handler.go` - Fixed DownloadReportCard to serve PDF bytes directly
- `backend/internal/router/setup.go` - Wired Gotenberg client with HTML-only fallback, added dev-only /api/v2/pdf/render endpoint

## Decisions Made

- **GotenbergClient uses type assertion** (`s.pdfGen.(interface{ GeneratePDF(...) }`) instead of compile-time interface — preserves backward compatibility with HTMLGenerator and allows graceful fallback when Gotenberg is unavailable
- **buildSubjectData() adapted to actual schema** — the plan assumed a `grade_item_scores` table, but the actual schema uses a `scores` table with JSON blob. The implementation queries `scores` joined with `subjects` and `assessments`, extracting totals from the JSON's `total` field
- **Session resolution** — session/term strings are resolved to a Session ID via the `sessions` table before filtering scores; falls back to unfiltered query if session not found
- **Dev-only PDF render endpoint** — gated by `cfg.App.Env != "production"` per threat model T-04-04

## Deviations from Plan

None — plan executed as adapted to actual schema differences.

### Schema Adaptation

**1. buildSubjectData() query adapted to actual schema**
- **Found during:** Task 2 (buildSubjectData implementation)
- **Issue:** Plan assumed `grade_item_scores` table with flat score columns. Actual schema uses `scores` table with `SubjectID` FK and JSON blob for grade-item data.
- **Adaptation:** Query uses `scores` → `subjects` join with `scores.score->>'total'` JSON extraction instead of the planned `grade_item_scores` → `grade_items` → `assessments` → `curriculums` → `subjects` join chain.
- **Files modified:** backend/internal/modules/reportcard/service.go
- **Verification:** `go build ./internal/modules/reportcard/...` passes

---

**Total deviations:** 1 schema adaptation (actual data model differed from plan assumptions)
**Impact on plan:** Adaptation was necessary for correctness. The output (real subject data) matches the plan intent.

## Issues Encountered

- Build cache issue required `go clean -cache` before build would reflect actual source (pre-existing `provisioning.go` error was stale cache)
- The `response` package needed a direct import in `setup.go` since Go requires per-file imports (even within the same package)

## User Setup Required

None — Gotenberg runs as a Docker container. Ensure `docker compose up -d` includes the `gotenberg` service.

For local development without Docker, set `GOTENBERG_URL` to an empty string in `.env` — the system falls back to HTML-only generation.

## Next Phase Readiness

- Gotenberg service ready for report card, transcript, and certificate PDF generation
- PDF generation for report cards works on-the-fly with Gotenberg or falls back to HTML
- Future phases can reuse GotenbergClient for any HTML→PDF conversion needs
- The `SchoolName` field in report card data still needs school-level resolution (planned for future phase)

## Known Stubs

1. **GeneratePDF service method** — `SchoolName` and `SchoolAddress` fields are empty strings (need school record resolution in a future phase)
2. **generatePDF() in Generate flow** — `SchoolName` is hardcoded as "School Name" (MVP placeholder)

## Self-Check: PASSED

All 8 key files verified on disk. Summary file present. Build and vet clean for `pkg/pdf`, `internal/modules/reportcard`, and `internal/router`.

---
*Phase: 01-foundation-hardening*
*Completed: 2026-07-19*
