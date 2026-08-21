# Deferred Items — Phase 04 (go-streaming-pipeline)

Out-of-scope discoveries logged during plan execution. These are pre-existing
issues NOT caused by current plan changes — left untouched per deviation rule
scope boundary.

## 04-03 (ai_documents status table)

### 1. Pre-existing golangci-lint failures in `backend/internal/database/`
- **Files:** `internal/database/models/lessonplan.go` (gofmt + misspell `behavioural`), `internal/database/models/session.go` (gofmt), `internal/database/tenant/provisioning.go` (misspell false-positives on French words like `Activités`)
- **Found during:** Task 2 verification (`golangci-lint run ./internal/database/...`)
- **Details:** All findings are in files untouched by 04-03. The plan's verification command explicitly falls back to `go vet ./internal/database/...` which passes clean. Changed files (`models/ai_document.go`, `migrations/core/ai_documents.go`, `migrations/core/core.go`) are lint-clean.
- **Why deferred:** Pre-existing warnings in unrelated files are out of scope (deviation rule scope boundary). No 04-03 code introduces any lint issue.
- **Recommendation:** Separate housekeeping pass to gofmt the models dir + configure misspell to accept French curriculum terms.

## 04-04 (upload + status API surface)

### 1. Pre-existing golangci-lint failures in `backend/internal/modules/lessonplan/`
- **Files:** `internal/modules/lessonplan/service.go` (errcheck: unchecked `json.Marshal` at lines 476/480/499/503; gosimple S1016 struct-literal conversion at line 492), `internal/modules/lessonplan/service_test.go` (gofmt at line 150)
- **Found during:** Verification (`golangci-lint run ./internal/modules/ai/...` is clean; confirmed findings exist in unrelated modules)
- **Details:** All findings are in files untouched by 04-04. The 04-04 verification (`golangci-lint run ./internal/modules/ai/...` / fallback `go vet ./internal/modules/ai/...`) passes clean on the changed module. The plan's known-findings list (lessonplan.go, session.go, provisioning.go) is confirmed.
- **Why deferred:** Pre-existing warnings in unrelated files are out of scope (deviation rule scope boundary). No 04-04 code introduces any lint issue.
- **Recommendation:** Separate housekeeping pass for errcheck/gosimple/gofmt across modules/lessonplan.

## 04-05 (SSE chat relay)

### 1. Pre-existing golangci-lint failures in unrelated modules (confirmed, not fixed)
- **Files:** `internal/modules/lessonplan/` (gofmt, misspell `behavioural`, errcheck on `json.Unmarshal`/`strconv.ParseUint`/`strconv.Atoi`/`ShouldBindJSON`, unused var `validLessonNoteTransitions`), plus the plan's known list (`internal/database/models/lessonplan.go`, `internal/database/models/session.go`, `internal/database/tenant/provisioning.go`)
- **Found during:** 04-05 verification (`golangci-lint run ./internal/modules/ai/... ./internal/ai/engine/...` is CLEAN — exit 0, zero findings on changed files; the findings live only in unrelated modules)
- **Details:** The plan's verification command (`golangci-lint run ... 2>/dev/null || go vet ...`) passes on the touched packages without the fallback. All 04-05 changed files (stream.go, stream_test.go, handler.go, router.go, setup.go) are lint-clean, gofmt-clean, and `-race` clean.
- **Why deferred:** Pre-existing warnings in unrelated files are out of scope (deviation rule scope boundary). No 04-05 code introduces any lint issue.
- **Recommendation:** Same housekeeping pass as 04-03/04-04 — gofmt the lessonplan + models dirs, address errcheck in modules/lessonplan, configure misspell for curriculum terms.

