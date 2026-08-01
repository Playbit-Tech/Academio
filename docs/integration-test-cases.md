# Integration Test Cases

| Attribute | Value |
|---|---|
| **Document** | Integration Test Cases — Frontend ↔ Backend Verification Registry |
| **Product** | Academio — Enterprise Multi-tenant School Management / Education ERP |
| **Scope** | Full-stack integration between frontend (`Academio-fe`), backend (`Academio-be`), and mobile (`academio-mobile`) |
| **Version** | 1.0 |
| **Status** | Active — updated per i18n batch completion |
| **Date** | 2026-08-01 |
| **Owner** | Playbit Technologies |
| **Related** | `docs/frontend-test-cases.md`, `docs/backend-test-cases.md`, `backend/scripts/test_endpoint.sh` |

---

## 1. Purpose

This document is the **living registry of integration test cases** for Academio. It tracks:

- **End-to-end flows**: complete user journeys from frontend action → backend API → database → response → frontend rendering.
- **Submodule consistency**: parent repo ↔ frontend submodule ↔ backend submodule pointer alignment.
- **Cross-boundary verification**: API returns correct data → frontend translates and displays correctly in both EN and FR.
- **Batch verification sequence**: the exact order to run checks after each i18n batch to ensure nothing is broken.

The document is updated **after every i18n batch** and serves as the single source of truth for full-stack verification.

---

## 2. Integration Test Strategy

### 2.1 Test Layers

| Layer | Tool | Scope | Run Command |
|---|---|---|---|
| **Unit** | Vitest (frontend), `go test` (backend) | Individual functions, components, handlers | `yarn vitest run` / `go test ./...` |
| **Component** | Vitest + jsdom | React component rendering, hook behavior | `yarn vitest run` |
| **API Integration** | `backend/scripts/test_endpoint.sh` | Full backend flow (40 tests) | `bash backend/scripts/test_endpoint.sh` |
| **E2E Smoke** | Playwright | Critical user flows in browser | `yarn playwright test` |
| **FR Smoke** | Custom Node.js scripts | French locale rendering verification | `NODE_PATH=frontend/node_modules node /tmp/opencode/academio-fr-smoke-*.cjs` |
| **Typecheck** | TypeScript compiler | Frontend type safety | `yarn tsc --noEmit` |
| **Build** | Vite | Production build | `yarn build` |
| **Raw-String Scan** | Custom Python script | Catch unwrapped user-facing strings | Per-batch scan script |

### 2.2 Test Environment Requirements

| Service | Port | Container | Purpose |
|---|---|---|---|
| PostgreSQL | 5432 | `shared-postgres` | Database (shared + tenant schemas) |
| Redis | 6379 | `shared-redis` | Asynq queue, caching |
| Backend | 8080 | `backend/tmp/server` | Go API server |
| Frontend Dev | 4000 | Vite dev server | React dev server (proxies `/api` → `:8080`) |
| Swagger UI | 8080 | Backend | API documentation (dev only) |

### 2.3 Environment Setup

```bash
# 1. Start infrastructure
docker start shared-postgres shared-redis

# 2. Reset and seed database
make db-init DROP_TENANT=true && make migrate && make seed

# 3. Start backend
cd backend && ./bin server &

# 4. Start frontend dev server
cd frontend && yarn dev &

# 5. Verify backend is healthy
curl -s http://localhost:8080/health
# Expected: {"healthy":true}

# 6. Verify frontend is running
curl -s http://localhost:4000 | head -5
# Expected: HTML response from Vite dev server
```

---

## 3. End-to-End Flow Definitions

### 3.1 Flow: Login → Dashboard → School Management

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Navigate to `/login` | Login page renders in EN | Playwright: `auth-smoke.spec.ts` "should render login page" |
| 2 | Switch locale to FR | Login page renders in FR | FR smoke script: login page FR labels |
| 3 | Enter credentials (`playbit` / `Password123!`) | Login succeeds, redirect to `/dashboard` | Playwright: `auth-smoke.spec.ts` "should login with valid credentials" |
| 4 | Verify dashboard loads | Dashboard renders with nav items in FR | FR smoke: `nav.dashboard` = "Tableau de bord" |
| 5 | Navigate to `/dashboard/school` | School management page loads | Playwright: `navigation-smoke.spec.ts` |
| 6 | Create a new school | School created, provisioning initiated | `test_endpoint.sh` school creation phase |
| 7 | Verify provisioning completes | `schema_name` is non-empty in `GET /api/v2/schools/:id` | Poll until `schema_name` populated |
| 8 | Verify school form renders in FR | All labels, placeholders, select options in French | FR smoke: school form FR labels |
| 9 | Logout | Session cleared, redirect to `/login` | `nav.logout` = "Déconnexion" |

### 3.2 Flow: Email Confirmation

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Navigate to `/confirm-email` without token | Missing state renders: title + description | FR smoke: `email_confirmation.missing_title`, `email_confirmation.missing_desc` |
| 2 | Navigate to `/confirm-email` with valid token | Confirming state renders | FR smoke: `email_confirmation.confirming` |
| 3 | Confirm email succeeds | Success message renders | FR smoke: `email_confirmation.success_message` |
| 4 | Click "Sign In" button | Redirect to `/login` | `auth.sign_in` key used (not raw "Sign In") |
| 5 | Navigate to `/confirm-email` with invalid token | Failed state renders | FR smoke: `email_confirmation.failed_title`, `email_confirmation.failed` |
| 6 | Click "Back to Sign In" | Redirect to `/login` | `email_confirmation.back_to_sign_in` key used |

### 3.3 Flow: 404 Not Found

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Navigate to any unknown route (e.g., `/nonexistent`) | NotFound page renders | FR smoke: `errors.not_found` in French |
| 2 | Click "Back to Home" | Redirect to `/dashboard` | `common.back_to_home` key used |

### 3.4 Flow: Onboarding Wizard

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Navigate to `/onboarding` | Onboarding wizard renders | FR smoke: onboarding pages |
| 2 | Navigate through wizard steps | All steps render correctly in FR | FR smoke: onboarding FR labels |
| 3 | Complete onboarding | Redirect to `/dashboard` | Navigation works |
| 4 | Verify navbar | Dashboard link = "Tableau de bord", Logout = "Déconnexion" | `nav.dashboard`, `nav.logout` keys |

### 3.5 Flow: Super Admin Layout

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Login as super admin (`playbit` / `Password123!`) | Dashboard loads | Playwright auth smoke |
| 2 | Navigate to `/super` | Super admin layout renders | FR smoke: super layout FR labels |
| 3 | Search schools | Search placeholder = "Rechercher des écoles..." | `common.search_schools` key |
| 4 | No schools match | Empty state = "Aucune école ne correspond à votre recherche." | `common.no_schools_match` key |
| 5 | No schools found | Empty state = "Aucune école trouvée." | `common.no_schools` key |
| 6 | Verify footer | Footer = "Tous droits réservés" | `pages.footer.copyright` key |

### 3.6 Flow: Education Country Labels

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Create school with WAEC framework | Term labels render as "Premier Trimestre", "Dexième Trimestre", "Troisième Trimestre" | `education.term_first`, `education.term_second`, `education.term_third` |
| 2 | Create school with BEPC framework | Term labels render as French equivalents (already French) | `formatTermLabel` returns BEPC labels as-is |
| 3 | Select WAEC school type | Type label translated via `getTypeLabelKey` | `education.type_nursery_primary`, `education.type_secondary` |
| 4 | Select BEPC school type | Type label not translated (null from `getTypeLabelKey`) | BEPC labels kept as-is |
| 5 | Select region | Region label translated via `getRegionLabelKey` | `education.region_state`, `education.region_lga`, etc. |
| 6 | Select district | District label translated via `getDistrictLabelKey` | `education.region_district`, `education.region_lga`, etc. |
| 7 | Summer term (WAEC) | Label = "Été" (from `education.term_summer`) | `formatTermLabel` handles `summer` → `education.term_summer` |
| 8 | Cercle district (Mali, BEPC) | Label = "Cercle" (from `education.region_cercle`) | `getDistrictLabelKey` maps Cercle → `education.region_cercle` |

### 3.7 Flow: Error Message Translation

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Trigger login error (wrong password) | Error message in FR: "Échec de la connexion" | `errors.login_failed` key |
| 2 | Trigger TOTP error | Error message in FR | `errors.totp_verification_failed` key |
| 3 | Trigger session expiry | Error message in FR | `errors.session_expired` key |
| 4 | Trigger 404 navigation | "Page non trouvée" | `errors.not_found` key |
| 5 | Trigger API error (non-2xx) | Error message with status code in FR | `errors.request_failed_status` with `{{status}}` |
| 6 | Trigger avatar upload error (wrong type) | Error message in FR | `errors.avatar_file_type` key |
| 7 | Trigger avatar upload error (too large) | Error message in FR | `errors.avatar_file_size` key |
| 8 | Trigger unknown error | "Erreur inconnue" | `errors.unknown_error` key |

### 3.8 Flow: Submodule Pointer Consistency

| Step | Action | Expected Result | Verification |
|---|---|---|---|
| 1 | Push frontend submodule | Frontend remote has new commits | `git push origin dev` in `frontend/` |
| 2 | Bump parent submodule pointer | Parent records new frontend commit SHA | `git add frontend && git commit` in parent |
| 3 | Push parent | Parent remote has new pointer commit | `git push origin main` in parent |
| 4 | Clone parent fresh | `git submodule update --init` checks out correct frontend commit | Verify `frontend/` HEAD matches parent's recorded SHA |
| 5 | Verify backend pointer is NOT pushed | Backend submodule stays at old commit | `git ls-tree HEAD backend` shows old SHA |

---

## 4. Submodule Consistency Checks

### 4.1 Pointer Alignment

| Check | Command | Expected | Frequency |
|---|---|---|---|
| Frontend pointer in parent matches frontend HEAD | `git ls-tree HEAD frontend` in parent == `git rev-parse HEAD` in frontend | Same SHA | After every frontend commit |
| Backend pointer in parent matches backend HEAD | `git ls-tree HEAD backend` in parent == `git rev-parse HEAD` in backend | Same SHA | After every backend commit |
| Mobile pointer in parent matches mobile HEAD | `git ls-tree HEAD mobile` in parent == `git rev-parse HEAD` in mobile | Same SHA | After every mobile commit |
| Parent HEAD is ahead of origin/main by N commits | `git log --oneline origin/main..HEAD \| wc -l` | N ≥ 0 | After every parent commit |
| Frontend HEAD is ahead of origin/dev by N commits | `git -C frontend log --oneline origin/dev..HEAD \| wc -l` | N ≥ 0 | After every frontend commit |
| Backend HEAD is ahead of origin/dev by N commits | `git -C backend log --oneline origin/dev..HEAD \| wc -l` | N ≥ 0 | After every backend commit |

### 4.2 Push Order

The correct push order to maintain submodule consistency:

```bash
# 1. Push backend submodule (if backend changes exist)
cd backend && git push origin dev

# 2. Push frontend submodule (if frontend changes exist)
cd ../frontend && git push origin dev

# 3. Bump parent submodule pointers
cd ..
git add backend frontend mobile
git commit -m "chore: bump submodule pointers"

# 4. Push parent
git push origin main
```

**Important**: Always push submodules BEFORE pushing the parent. If you push the parent first, the remote parent will reference submodule commits that don't exist on the submodule remotes yet, causing `git submodule update --init` to fail for new clones.

### 4.3 Push Order for i18n Batches (Current Workflow)

```bash
# 1. Push frontend submodule (i18n work is in frontend)
cd frontend && git push origin dev

# 2. Bump parent frontend pointer
cd ..
git add frontend
git commit -m "chore(frontend): bump submodule — i18n batch N ..."

# 3. Push parent
git push origin main

# 4. Do NOT push backend (per user instruction)
# 5. Do NOT push parent until frontend is pushed
```

---

## 5. Batch Verification Sequence

### 5.1 Per-Batch Verification Checklist

After completing each i18n batch, run the following verification sequence in order:

#### Step 1: Typecheck
```bash
cd frontend && yarn tsc --noEmit
```
- **Expected**: Exit 0, no TypeScript errors
- **On failure**: Fix type errors before proceeding

#### Step 2: Unit Tests
```bash
cd frontend && yarn vitest run --reporter=dot
```
- **Expected**: All 18 test files / 230 tests pass
- **On failure**: Investigate failing tests before proceeding

#### Step 3: Production Build
```bash
cd frontend && yarn build
```
- **Expected**: Exit 0, all chunks emitted, build time ~13-15s
- **On failure**: Fix build errors before proceeding

#### Step 4: FR Smoke Test
```bash
NODE_PATH=frontend/node_modules node /tmp/opencode/academio-fr-smoke-4c.cjs
```
- **Expected**: All smoke checks PASS
- **On failure**: Investigate FR rendering issues

#### Step 5: Raw-String Scan
```bash
# Custom Python scan of all batch files for unwrapped user-facing strings
python3 scan_batch4c_strings.py
```
- **Expected**: No unwrapped user-facing strings found (or only known false positives)
- **On finding**: Fix the miss, re-run scan

#### Step 6: Locale Parity Check
```bash
# Verify EN/FR leaf key count parity
python3 merge-batch4c.mjs --check-parity
```
- **Expected**: EN and FR have identical leaf key counts
- **On mismatch**: Fix missing FR keys or extra EN keys

#### Step 7: Commit
```bash
# Commit in frontend submodule
cd frontend && git add -A && git commit -m "i18n: wrap batch N strings ..."

# Bump parent submodule pointer
cd .. && git add frontend && git commit -m "chore(frontend): bump submodule — i18n batch N ..."
```

#### Step 8: Push
```bash
# Push frontend submodule
cd frontend && git push origin dev

# Push parent
cd .. && git push origin main
```

### 5.2 Batch Verification Results (Historical)

| Batch | Typecheck | Vitest | Build | FR Smoke | Raw-String Scan | Parity | Commits |
|---|---|---|---|---|---|---|---|
| 3a | ✅ | ✅ 18/230 | ✅ | ✅ | N/A | N/A | 2325cda / 7265562 |
| 3b | ✅ | ✅ 18/230 | ✅ | ✅ | N/A | N/A | dd6d67f / 8f96da8 |
| 3c | ✅ | ✅ 18/230 | ✅ | ✅ | N/A | N/A | 8ed2e04 / 6363d63 |
| Report-cards | ✅ | ✅ 18/230 | ✅ | ✅ | N/A | N/A | 707450f / 8cc4535 |
| Breadcrumb | ✅ | ✅ 18/230 | ✅ | ✅ | N/A | N/A | aeba694 / 06a42fb |
| 4a | ✅ | ✅ 18/230 | ✅ | ✅ 13/13 | N/A | N/A | 4c496fa / 5746422 |
| 4b | ✅ | ✅ 18/230 | ✅ | ✅ 6/6 | N/A | N/A | 8a00171 / 1e46f01 |
| 4c | ✅ | ✅ 18/230 | ✅ | ✅ | ✅ Clean | ✅ 64 sections / 4068 keys | b34d638 / d7dff9f |

---

## 6. CI/CD Integration Points

### 6.1 Current CI Pipeline

| Stage | Tool | Trigger | Purpose |
|---|---|---|---|
| Lint | ESLint | PR | Frontend code quality |
| Typecheck | `yarn tsc --noEmit` | PR | TypeScript safety |
| Unit Tests | Vitest | PR | Component/hook correctness |
| Build | `yarn build` | PR | Production build validation |
| Backend Tests | `go test ./...` | PR | Backend correctness |
| Integration Tests | `bash backend/scripts/test_endpoint.sh` | Manual / CI | Full backend flow |
| E2E Tests | Playwright | Manual / CI | Critical user flows |
| FR Smoke | Custom Node.js scripts | Manual | French locale verification |

### 6.2 Recommended CI Additions

| Stage | Tool | Purpose | Priority |
|---|---|---|---|
| Raw-string scan | Custom Python script | Catch unwrapped user-facing strings | High |
| Locale parity check | Merge script `--check-parity` | Ensure EN/FR key parity | High |
| Submodule pointer check | `git ls-tree` comparison | Ensure parent pointers match submodule HEADs | Medium |
| FR E2E smoke | Playwright with FR locale | Automated FR rendering verification | Medium |
| Backend locale check | Custom script | Verify backend error keys have frontend translations | Low |

### 6.3 CI Configuration (Proposed)

```yaml
# .github/workflows/frontend-ci.yml (proposed)
name: Frontend CI
on: [pull_request]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: cd frontend && yarn tsc --noEmit

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: cd frontend && yarn vitest run

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: cd frontend && yarn build

  raw-string-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: python3 scripts/scan-unwrapped-strings.py

  locale-parity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: node scripts/merge-locale-check-parity.mjs
```

---

## 7. Cross-Boundary Verification Matrix

### 7.1 API → Frontend Translation Verification

| API Endpoint | Backend Error Key | Frontend Translation Key | FR Value | Verified |
|---|---|---|---|---|
| `POST /api/v2/auth/login` | (raw error) | `errors.login_failed` | "Échec de la connexion" | ✅ |
| `POST /api/v2/auth/login` (TOTP) | (raw error) | `errors.totp_verification_failed` | "Échec de la vérification TOTP" | ✅ |
| `GET /api/v2/schools/:id` (404) | (raw error) | `errors.not_found` | "Page non trouvée" | ✅ |
| `POST /api/v2/schools/:id/confirm-email` | (raw error) | `email_confirmation.failed` | FR value | ✅ |
| `GET /api/v2/users/student` (non-2xx) | (raw error) | `errors.failed_load_students_for_class` | FR value | ✅ |
| `GET /api/v2/users` (non-2xx) | (raw error) | `errors.failed_load_users` | FR value | ✅ |
| `POST /api/v2/media/upload` (non-2xx) | (raw error) | `errors.upload_failed` | FR value | ✅ |
| `GET /api/v2/health` (non-2xx) | (raw error) | `errors.unknown_error` | "Erreur inconnue" | ✅ |
| Any API (non-2xx with status) | (raw error) | `errors.request_failed_status` | "La requête a échoué (HTTP {{status}})" | ✅ |

### 7.2 Frontend → Backend Data Flow Verification

| Flow | Frontend Action | Backend Endpoint | Expected Backend Behavior | Verified |
|---|---|---|---|---|
| School creation | Submit school form | `POST /api/v2/schools` | Creates school, returns school ID | ✅ |
| School provisioning | Poll `GET /api/v2/schools/:id` | Returns school data | `schema_name` populated when ready | ✅ |
| Session creation | Submit session form | `POST /api/v2/sessions` | Creates session with linked curriculum | ✅ |
| Assessment creation | Submit assessment form | `POST /api/v2/assessments` | Creates assessment with sort_order | ✅ |
| Grade item creation | Submit grade item form | `POST /api/v2/grade-items` | Creates grade item | ✅ |
| Score entry | Submit score form | `POST /api/v2/scores` | Creates score with rollup | ✅ |
| XLSX import | Upload XLSX file | `POST /api/v2/import/xlsx` | Parses, validates, imports rows | ✅ |
| Teacher creation | Submit teacher form | `POST /api/v2/teachers` | Creates teacher + user_info | ✅ |
| Staff registration | Submit staff form | `POST /api/v2/staff` | Registers staff user | ✅ |

---

## 8. Known Gaps & Deferred Items

### 8.1 Integration Gaps

| Gap | Description | Tracking |
|---|---|---|
| No automated FR E2E tests | Playwright E2E tests run in EN only; FR verification is manual via smoke scripts | Add FR locale to Playwright config |
| Backend error strings not translated | Backend returns English; frontend translates via `defaultValue` | See `docs/backend-test-cases.md` §3 |
| No CI for raw-string scan | Unwrapped strings caught manually per batch | Add to CI pipeline (see §6.3) |
| No CI for locale parity | EN/FR parity checked manually per batch | Add to CI pipeline (see §6.3) |
| Mobile submodule not tested | Mobile app (Flutter) has no integration tests with backend | Future: add mobile integration tests |
| AI engine submodule not tested | Python AI engine has no integration tests with frontend | Future: add AI engine integration tests |

### 8.2 Frontend-Backend Contract Gaps

| Gap | Description | Impact |
|---|---|---|
| Zod validation messages stay literal | Backend returns English; frontend displays English validation errors | Inconsistent with translated UI |
| No structured error codes | Backend returns raw error strings; frontend maps via `defaultValue` | Fragile — if backend changes error text, frontend `defaultValue` becomes stale |
| No backend locale files | Backend has no i18n library; no `fr` error messages | Backend errors always English |

### 8.3 Submodule Gaps

| Gap | Description | Impact |
|---|---|---|
| Backend submodule 18 commits ahead | Backend has unpushed commits; parent references backend at older commit | Parent's backend pointer is stale relative to backend's HEAD |
| Mobile submodule up to date | Mobile is clean and matches origin/dev | No action needed |
| Parent 36 commits ahead | Parent has uncommitted changes (.gitignore, .planning/*) | Parent not pushed; submodule pointers may be stale on remote |

---

## 9. Revision History

| Date | Author | Changes |
|---|---|---|
| 2026-08-01 | Agent | Initial document creation |
