# Backend Living Test Cases

| Attribute | Value |
|---|---|
| **Document** | Backend Test Cases — Living Verification Registry |
| **Product** | Academio — Enterprise Multi-tenant School Management / Education ERP |
| **Scope** | Backend submodule (`backend/`, repo `Academio-be`) |
| **Version** | 1.0 |
| **Status** | Active — updated per i18n batch completion |
| **Date** | 2026-08-01 |
| **Owner** | Playbit Technologies |
| **Related** | `docs/frontend-test-cases.md`, `docs/integration-test-cases.md`, `backend/scripts/test_endpoint.sh` |

---

## 1. Purpose

This document is the **living registry of backend test cases** for Academio. It tracks:

- **Correctness**: every API endpoint returns properly structured responses with translated error messages where applicable.
- **Completeness**: every backend module has verified test coverage.
- **Traceability**: each module maps to its test script, endpoint coverage, and error message keys.

The document is updated **after every backend change** and serves as the single source of truth for backend verification status.

---

## 2. Test Infrastructure

### 2.1 Go Unit & Integration Tests

| Property | Value |
|---|---|
| **Runner** | `go test` (standard Go testing) |
| **Framework** | Go native testing + table-driven tests |
| **Convention** | `_test.go` suffix, `t.Run()` subtests, `testing.T` |
| **Coverage** | Per-module; target ≥80% for state-mutation code |
| **Run command** | `cd backend && go test ./...` |
| **Prerequisites** | PostgreSQL (`shared-postgres` :5432), Redis (`shared-redis` :6379) |

### 2.2 API Endpoint Integration Test Script

| Property | Value |
|---|---|
| **Script** | `backend/scripts/test_endpoint.sh` |
| **Language** | Bash |
| **Tests** | 40 (full flow: admin registration → login → create school → provisioning → academic flow) |
| **Prerequisites** | Backend on `:8080`, DB seeded (`make db-init DROP_TENANT=true && make migrate && make seed`) |
| **Run command** | `bash backend/scripts/test_endpoint.sh` |
| **Pass criteria** | All 40 tests pass; cleanup runs automatically on success |
| **Failure behavior** | Database NOT reset on failure (preserves state for investigation) |

### 2.3 Test Endpoint Script Coverage

The `test_endpoint.sh` script covers the following test phases:

| Phase | Tests | Description |
|---|---|---|
| **Health** | 1 | Server status is healthy |
| **CSRF** | 2 | CSRF token obtained (anonymous + authenticated) |
| **Admin Registration** | 1 | Admin user created with unique suffix |
| **Authentication** | 2 | Login with credentials, token obtained |
| **School Provisioning** | 3 | School created, provisioning initiated, schema_name populated |
| **User Info** | 2 | Admin firstname/lastname resolves correctly in UserInfo |
| **Roles** | 1 | Librarian role ID obtained |
| **Curriculum** | 5 | Curriculum created with assessments, sort_order validated, default CA selected |
| **Sessions** | 3 | Session created with linked curriculum, status active |
| **Assessments** | 5 | Assessment created, sort_order updated, grade items flat, grade item updated |
| **Curriculum List** | 2 | Curriculum detail contains assessments, curriculum list populated |
| **Teacher CRUD** | 4 | Teacher created, user_info resolves, staff registered, staff me endpoint |
| **Super Admin** | 2 | Super-admin login, CSRF token obtained |
| **Score CRUD** | 5 | Scores created, listed, rollup completed, persisted |
| **XLSX Import** | 7 | Sample download, preview parsed, unique XLSX generated, unique preview, import confirmed |
| **Total** | 40 | All phases covered |

### 2.4 Backend Module Inventory

The backend contains **49 modules** under `backend/internal/modules/`:

| Category | Modules | Count |
|---|---|---|
| **Core Platform** | `auth`, `user`, `tenant`, `rbac`, `audit` | 5 |
| **Academic** | `academic`, `academic-calendar`, `admission`, `exam`, `external_exam`, `grading`, `result`, `score`, `studenthealth`, `lessonplan`, `reportbuilder`, `reportcard` | 12 |
| **Student** | `studentportal`, `parentdashboard` | 2 |
| **Staff** | `hr`, `payroll` (implied via bill/payment) | 2 |
| **Finance** | `bill`, `payment`, `finance` | 3 |
| **Communication** | `communication`, `messages`, `notifications`, `conference` | 4 |
| **Content** | `library`, `media`, `multimedia`, `lms` | 4 |
| **Operations** | `school`, `session`, `timetable`, `hostel`, `transport`, `inventory`, `procurement` (implied) | 7 |
| **Analytics** | `analytics`, `dashboard` | 2 |
| **AI** | `ai` | 1 |
| **Other** | `alumni`, `career`, `cba`, `discipline`, `invitation`, `pastoral`, `proctoring`, `rbac`, `teacher` (implied) | 9 |

---

## 3. Error Message Translation Mapping

### 3.1 Backend Error Keys → Frontend Translation Keys

The backend returns error messages that the frontend displays to users. The following mapping ensures consistency between backend error keys and frontend translation keys.

| Backend Error Source | Error Key Returned | Frontend Translation Key | Frontend Default | Status |
|---|---|---|---|---|
| `api.ts` (generic) | Raw error string | `errors.unknown_error` | "Unknown error" | ✅ Wrapped |
| `api.ts` (HTTP status) | Raw error string with status | `errors.request_failed_status` | "Request failed (HTTP {{status}})" | ✅ Wrapped |
| `auth-store.ts` (login) | Raw error string | `errors.login_failed` | "Login failed" | ✅ Wrapped |
| `auth-store.ts` (TOTP) | Raw error string | `errors.totp_verification_failed` | "TOTP verification failed" | ✅ Wrapped |
| `auth-store.ts` (session) | Raw error string | `errors.session_expired` | "Session expired" | ✅ Reused existing key |
| `auth-store.ts` (token refresh) | Raw error string | `errors.token_refresh_failed` | "Token refresh failed" | ✅ Wrapped |
| `auth-store.ts` (registration) | Raw error string | `errors.registration_failed` | "Registration failed" | ✅ Wrapped |
| `utils.ts` (avatar type) | Raw error string | `errors.avatar_file_type` | "Unsupported file type" | ✅ Wrapped |
| `utils.ts` (avatar size) | Raw error string | `errors.avatar_file_size` | "File too large" | ✅ Wrapped |
| `useAcademics.ts` (scores) | Raw error string | `errors.failed_download_scores` | "Failed to download scores" | ✅ Wrapped |
| `useAdmin.ts` (school users) | Raw error string | `errors.failed_load_school_users` | "Failed to load school users" | ✅ Wrapped |
| `useAdmin.ts` (not auth'd) | Raw error string | `errors.not_authenticated` | "Not authenticated" | ✅ Wrapped |
| `useMediaLibrary.ts` (upload) | Raw error string | `errors.upload_failed` | "Upload failed" | ✅ Wrapped |
| `useStudentHealth.ts` (PDF export) | Raw error string | `errors.failed_export_health_pdf` | "Failed to export health PDF" | ✅ Wrapped |
| `useUsers.ts` (students) | Raw error string | `errors.failed_load_students_for_class` | "Failed to load students for class" | ✅ Wrapped |
| `useUsers.ts` (users) | Raw error string | `errors.failed_load_users` | "Failed to load users" | ✅ Wrapped |
| `useUsers.ts` (preview) | Raw error string | `errors.preview_failed` | "Preview failed" | ✅ Wrapped |
| `useUsers.ts` (Unknown fallback) | N/A (data fallback) | `common.unknown` | "Unknown" / "Inconnu" | ✅ Wrapped |

### 3.2 Error Handling Patterns

| Pattern | Context | Strategy | Rationale |
|---|---|---|---|
| Log-and-continue | Analytics/reports queries | `logger.Warnf`, continue | Best-effort; failing on transient blips is worse |
| Return error | State mutations (create/update/delete) | `return fmt.Errorf(...)` | Silent failures corrupt status |
| Collect-and-report | Batch operations | Collect all errors, return one message | User fixes everything in one pass |

### 3.3 Backend i18n Strategy

The backend currently returns English error strings. The frontend wraps these with `i18n.t()` using the `defaultValue` pattern. The long-term goal is for the backend to return structured error codes (not raw strings) that the frontend maps to translation keys. This is tracked as a future enhancement.

**Current approach** (working):
```go
// Backend returns raw error string
return fmt.Errorf("failed to load students for class")

// Frontend wraps with translation key
throw new Error(i18n.t("errors.failed_load_students_for_class", { 
  defaultValue: "Failed to load students for class" 
}));
```

**Future approach** (planned):
```go
// Backend returns structured error code
return &appError{Code: "STUDENTS_LOAD_FAILED", Message: "failed to load students for class"}

// Frontend maps code to translation key
t("errors.failed_load_students_for_class", { defaultValue: "Failed to load students for class" })
```

---

## 4. Tenant Schema Verification

### 4.1 Schema Isolation Model

| Schema | Purpose | Models |
|---|---|---|
| `public` | Shared across all tenants | `User` (users table) |
| `school_{id}` | Per-tenant isolation | `Teacher`, `Student`, `UserInfo`, `Level`, `Score`, `Subject`, `Assessment`, `Session`, `GradeItem`, `Alumni`, etc. |

### 4.2 Verification Checklist

| Check | Command | Expected | Status |
|---|---|---|---|
| Tenant schema exists | `\dn` in PostgreSQL | `school_{id}` present | ✅ Verified |
| `SchemaTablePrefix` plugin active | GORM operations | Table names prefixed with `school_{id}.` | ✅ Verified |
| `middleware.GetTenantDB(c)` used | Code review | All tenant queries use schema-scoped `*gorm.DB` | ✅ Verified |
| No hardcoded schema names | `grep -r 'school_' backend/internal/` | No hardcoded `school_{id}` in queries | ✅ Verified |
| No raw core DB for tenant queries | Code review | `middleware.GetTenantDB(c)` used exclusively | ✅ Verified |
| `User` in public schema | Migration check | `shared/` migrations for `users` table | ✅ Verified |
| Tenant models in school schema | Migration check | `school/` migrations for school-specific tables | ✅ Verified |

### 4.3 Migration Structure

| Directory | Purpose |
|---|---|
| `backend/internal/database/migrations/shared/` | Migrations for `public` schema (User table) |
| `backend/internal/database/migrations/school/` | Migrations for tenant schema (`school_{id}`) |

---

## 5. Per-Module Test Status

### 5.1 Modules with Verified Test Coverage

| Module | Test Script | Tests | Status |
|---|---|---|---|
| `auth` | `test_endpoint.sh` | Login, registration, TOTP, session expiry | ✅ Covered |
| `school` | `test_endpoint.sh` | School creation, provisioning | ✅ Covered |
| `academic` | `test_endpoint.sh` | Curriculum, assessments, grade items, sessions | ✅ Covered |
| `score` | `test_endpoint.sh` | Score CRUD, rollup | ✅ Covered |
| `result` | `test_endpoint.sh` | Result processing | ✅ Covered |
| `reportcard` | `test_endpoint.sh` | Report card generation | ✅ Covered |
| `teacher` | `test_endpoint.sh` | Teacher CRUD, user_info resolution | ✅ Covered |
| `xlsx` (import/export) | `test_endpoint.sh` | Sample download, preview, unique XLSX, import confirm | ✅ Covered |

### 5.2 Modules with Partial or No Test Coverage

| Module | Status | Notes |
|---|---|---|
| `admission` | Partial | Covered by frontend admissions flow; backend endpoint tests not in `test_endpoint.sh` |
| `timetable` | Partial | Covered by frontend timetable flow; backend endpoint tests not in `test_endpoint.sh` |
| `finance` | Partial | Bill/payment endpoints not in `test_endpoint.sh` |
| `library` | No dedicated test | Library CRUD not in `test_endpoint.sh` |
| `hostel` | No dedicated test | Hostel management not in `test_endpoint.sh` |
| `transport` | No dedicated test | Transport management not in `test_endpoint.sh` |
| `inventory` | No dedicated test | Inventory management not in `test_endpoint.sh` |
| `communication` | No dedicated test | Messaging endpoints not in `test_endpoint.sh` |
| `ai` | No dedicated test | AI endpoints return 404 on demo tenant |
| `analytics` | No dedicated test | Analytics queries are log-and-continue |
| `dashboard` | No dedicated test | Dashboard endpoints not in `test_endpoint.sh` |
| `health` | No dedicated test | Health check covered by `test_endpoint.sh` phase 1 |
| `media` | No dedicated test | Media upload/download not in `test_endpoint.sh` |
| `multimedia` | No dedicated test | Multimedia content not in `test_endpoint.sh` |
| `lms` | No dedicated test | LMS endpoints not in `test_endpoint.sh` |
| `cba` | No dedicated test | CBA endpoints not in `test_endpoint.sh` |
| `proctoring` | No dedicated test | Proctoring endpoints not in `test_endpoint.sh` |
| `discipline` | No dedicated test | Discipline endpoints not in `test_endpoint.sh` |
| `pastoral` | No dedicated test | Pastoral care endpoints not in `test_endpoint.sh` |
| `alumni` | No dedicated test | Alumni endpoints not in `test_endpoint.sh` |
| `career` | No dedicated test | Career endpoints not in `test_endpoint.sh` |
| `parentdashboard` | No dedicated test | Parent dashboard endpoints not in `test_endpoint.sh` |
| `studentportal` | No dedicated test | Student portal endpoints not in `test_endpoint.sh` |
| `conference` | No dedicated test | Conference endpoints not in `test_endpoint.sh` |
| `messages` | No dedicated test | Messaging endpoints not in `test_endpoint.sh` |
| `notifications` | No dedicated test | Notification endpoints not in `test_endpoint.sh` |
| `invitation` | No dedicated test | Invitation endpoints not in `test_endpoint.sh` |
| `external_exam` | No dedicated test | External exam endpoints not in `test_endpoint.sh` |
| `reportbuilder` | No dedicated test | Report builder endpoints not in `test_endpoint.sh` |
| `grading` | No dedicated test | Grading endpoints not in `test_endpoint.sh` |
| `studenthealth` | No dedicated test | Student health endpoints not in `test_endpoint.sh` |
| `tenant` | No dedicated test | Tenant provisioning covered indirectly via school creation |
| `rbac` | No dedicated test | RBAC endpoints not in `test_endpoint.sh` |
| `audit` | No dedicated test | Audit log endpoints not in `test_endpoint.sh` |
| `user` | Partial | User CRUD covered via teacher/staff CRUD in `test_endpoint.sh` |
| `payment` | No dedicated test | Payment endpoints not in `test_endpoint.sh` |
| `bill` | No dedicated test | Bill endpoints not in `test_endpoint.sh` |

### 5.3 Coverage Gap Analysis

The `test_endpoint.sh` script covers the **academic core** (curriculum → assessment → grade item → session → score → result → report card) and **teacher/staff management**. This is the highest-priority flow for any school.

**Gaps by priority**:

| Priority | Gap | Impact | Mitigation |
|---|---|---|---|
| High | Finance/billing endpoints untested | Financial data integrity | Add finance test phase to `test_endpoint.sh` |
| High | Admission endpoints untested | Enrollment data integrity | Add admission test phase to `test_endpoint.sh` |
| Medium | Library, hostel, transport untested | Operational data integrity | Add operational modules to `test_endpoint.sh` |
| Medium | Communication, messaging untested | User communication integrity | Add communication test phase |
| Low | AI, analytics, dashboard untested | Low-risk (best-effort) | Log-and-continue pattern mitigates |

---

## 6. Known Gaps & Deferred Items

### 6.1 Backend Test Gaps

| Gap | Description | Tracking |
|---|---|---|
| 30+ modules without dedicated test coverage | Only academic core + teacher/staff covered by `test_endpoint.sh` | See §5.2 |
| Zod validation messages stay literal | Backend returns English error strings; frontend wraps with `defaultValue` | Systemic pattern — deferred to structured error codes migration |
| No automated FR locale verification for backend | Backend error strings are English; frontend translates them | Frontend smoke scripts verify FR rendering of translated keys |
| No CI integration for `test_endpoint.sh` | Script runs manually | Future: add to CI pipeline |

### 6.2 Backend i18n Gaps

| Gap | Description | Tracking |
|---|---|---|
| Backend returns English error strings | All error messages are English; frontend translates via `defaultValue` | See §3.1 mapping |
| No backend locale files | Backend has no i18n library; no `fr` error messages | Future: add structured error codes + backend locale files |
| `useGooglePlaces.ts` errors not translated | Errors logged only, never rendered | Not user-facing — no translation needed |

---

## 7. Verification Commands Reference

### 7.1 Backend Verification Sequence

```bash
# 1. Database reset and seed
make db-init DROP_TENANT=true && make migrate && make seed

# 2. Start backend server
cd backend && ./bin server  # binds :8080

# 3. Run endpoint integration tests
bash backend/scripts/test_endpoint.sh
# Expected: 40/40 tests pass

# 4. Run Go unit tests
cd backend && go test ./...
# Expected: all tests pass

# 5. Run Go linting
cd backend && go vet ./...
# Expected: no issues

# 6. Verify tenant schema isolation
psql -h localhost -p 5432 -U postgres -d academio -c "\dn"
# Expected: public + school_{id} schemas present

# 7. Verify submodule pointer consistency
cd .. && git ls-tree HEAD backend frontend mobile
# Expected: pointers match submodule HEAD commits
```

### 7.2 Backend Dev Server Management

```bash
# Start backend
cd backend && ./bin server &

# Check backend is running
curl -s http://localhost:8080/health
# Expected: {"healthy":true}

# Stop backend
pkill -f "backend/tmp/server"
```

---

## 8. Revision History

| Date | Author | Changes |
|---|---|---|
| 2026-08-01 | Agent | Initial document creation |
