# Frontend Living Test Cases

| Attribute | Value |
|---|---|
| **Document** | Frontend Test Cases — Living Verification Registry |
| **Product** | Academio — Enterprise Multi-tenant School Management / Education ERP |
| **Scope** | Frontend submodule (`frontend/`, repo `Academio-fe`) |
| **Version** | 1.0 |
| **Status** | Active — updated per i18n batch completion |
| **Date** | 2026-08-01 |
| **Owner** | Playbit Technologies |
| **Related** | `docs/backend-test-cases.md`, `docs/integration-test-cases.md`, `backend/scripts/test_endpoint.sh` |

---

## 1. Purpose

This document is the **living registry of frontend test cases** for Academio. It tracks:

- **Correctness**: every user-facing string is wrapped in a translation key and renders correctly in both English and French.
- **Completeness**: every page, route, and component in the frontend test matrix has been verified.
- **Traceability**: each batch maps to specific files, locale keys, and smoke-test results.

The document is updated **after every i18n batch** and serves as the single source of truth for what has been verified and what remains pending.

---

## 2. Test Infrastructure

### 2.1 Unit & Component Tests (Vitest)

| Property | Value |
|---|---|
| **Runner** | Vitest v4.1.10 |
| **Environment** | jsdom |
| **Setup** | `frontend/src/setupTests.ts` |
| **CSS support** | Enabled (`css: true`) |
| **Excludes** | `e2e/`, `node_modules/` |
| **Baseline** | 18 test files / 230 tests (all passing) |
| **Run command** | `yarn vitest run` (from `frontend/`) |
| **Watch mode** | `yarn vitest` |

### 2.2 E2E Smoke Tests (Playwright)

| Property | Value |
|---|---|
| **Runner** | Playwright Test |
| **Test directory** | `frontend/e2e/` |
| **Browser** | Chromium |
| **Base URL** | `http://localhost:4000` |
| **Workers** | 1 (sequential, avoids state collision) |
| **Retries** | 1 |
| **Trace** | Retained on failure |
| **Screenshot** | On failure only |
| **Existing test files** | `auth-smoke.spec.ts`, `navigation-smoke.spec.ts` |
| **Run command** | `yarn playwright test` (from `frontend/`) |
| **Prerequisites** | Backend on `:8080`, frontend dev server on `:4000` |

### 2.3 FR Smoke Scripts (Node.js)

| Script | Location | Purpose |
|---|---|---|
| `academio-fr-smoke-3b.cjs` | `/tmp/opencode/` | Batch 3b FR verification |
| `academio-fr-smoke-3c.cjs` | `/tmp/opencode/` | Batch 3c FR verification (timetable + admissions) |
| `academio-fr-smoke-3c-template.cjs` | `/tmp/opencode/` | Template-builder FR verification |
| `academio-fr-smoke-3c-template-drag.cjs` | `/tmp/opencode/` | Template drag-and-drop FR verification |
| `academio-fr-smoke-batch-crumb.cjs` | `/tmp/opencode/` | Batch breadcrumb FR verification |
| `academio-fr-smoke-report-cards.cjs` | `/tmp/opencode/` | Report-cards route FR verification |
| `academio-fr-smoke-batch4a.cjs` | `/tmp/opencode/` | Batch 4a FR verification |
| `academio-fr-smoke-batch4a-final.cjs` | `/tmp/opencode/` | Batch 4a final verification |
| `academio-fr-smoke-batch4b.cjs` | `/tmp/opencode/` | Batch 4b FR verification |
| `academio-fr-smoke-batch4b-v2.cjs` | `/tmp/opencode/` | Batch 4b v2 FR verification (6/6 PASS) |

All scripts use `NODE_PATH=<frontend>/node_modules node /tmp/opencode/*.cjs` to resolve Playwright.

### 2.4 Typecheck & Build

| Command | Purpose | Expected |
|---|---|---|
| `yarn tsc --noEmit` | TypeScript type checking | Exit 0, no errors |
| `yarn build` | Production build | Exit 0, all chunks emitted |
| `yarn dev` | Dev server (Vite + TanStack Router) | Starts on `:4000` |

---

## 3. i18n Batch Verification Registry

### 3.1 Batch 3a — Shared Components (7 files)

| Property | Detail |
|---|---|
| **Commit** | `2325cda` (frontend) / `7265562` (parent) |
| **Files** | `add-user-form`, `FormFieldEditor`, `master-sheet`, `score-grid`, `curriculum-form`, `error-boundary`, `dashboard-layout` footer |
| **New keys** | Shared components section |
| **Verification** | typecheck ✅, vitest 18/230 ✅, FR smoke ✅ |
| **Status** | ✅ Complete |

### 3.2 Batch 3b — LMS Dialogs, Users View-Sheets, Profile Modals

| Property | Detail |
|---|---|
| **Commit** | `dd6d67f` (frontend) / `8f96da8` (parent) |
| **Files** | LMS dialog components, users view sheets, profile modals |
| **New keys** | LMS, users, profile sections |
| **Verification** | typecheck ✅, vitest 18/230 ✅, FR smoke ✅ |
| **Status** | ✅ Complete |

### 3.3 Batch 3c — Admissions, Timetable, Template-Builder, Onboarding

| Property | Detail |
|---|---|
| **Commit** | `8ed2e04` (frontend) / `6363d63` (parent) |
| **Files** | `admissions/*` (16 files + FormEditor), `timetable/*` (3 files), `template-builder/*` (6 files), `onboarding/*` (9 files) |
| **New keys** | 147 admissions + 36 timetable + 40 template_builder + 0 onboarding (already used `pages.onboarding.*`) |
| **Verification** | typecheck ✅, vitest 18/230 ✅, FR smoke ✅ (timetable FR, admissions FR, template-builder FR incl. dragged score-table, preview dialog) |
| **Conflicts resolved** | FormEditor.tsx: `admissions.loading_form`, `admissions.form_not_found` |
| **Plural convention** | `fields_count_*`, `file_count_*`, `files_uploaded_*` (matches existing `lms_discussions.replies_*`) |
| **Status** | ✅ Complete |

### 3.4 Report-Cards Route Follow-up

| Property | Detail |
|---|---|
| **Commit** | `707450f` (frontend) / `8cc4535` (parent) |
| **Files** | `src/routes/_dashboard/report-cards/index.tsx` |
| **Changes** | Wired `useTranslation` (was imported but unused), translated header, tabs, stats, status badges, empty states |
| **New keys** | `report_cards` (22 keys), `reportCards` (18 keys), `teacher_report_cards.no_report_cards`, extended `teacher.no_report_cards`, `student.recent_report_cards` + `no_report_cards`, `toast.report_cards_queued` + `failed_to_generate_report_cards` |
| **Verification** | typecheck ✅, vitest 18/230 ✅, FR smoke index+batch pages 15/15 ✅ |
| **Status** | ✅ Complete |

### 3.5 Batch Breadcrumb Follow-up

| Property | Detail |
|---|---|
| **Commit** | `aeba694` (frontend) / `06a42fb` (parent) |
| **Root cause** | `breadcrumbs.tsx` resolves unknown route segments via `t("nav.batch", { defaultValue: "Batch" })` — `nav.batch` was missing from locales, so `/report-cards/batch` rendered English "Batch" |
| **Fix** | Added `nav.batch` = "Batch" / "Génération par lot" to both locales |
| **Verification** | FR smoke breadcrumb on `/report-cards/batch` shows "Tableau de bord > Bulletins > Génération par lot", no raw "Batch" remains |
| **Status** | ✅ Complete |

### 3.6 Batch 4a — Shared Components (12 files)

| Property | Detail |
|---|---|
| **Commit** | `4c496fa` (frontend) / `5746422` (parent) |
| **Files** | `media/{media-upload-dialog,media-grid,media-picker}.tsx`, `academics/{grade-item-score-entry,excel-upload-step,promotion-preview}.tsx`, `academic-calendar/{dynamic-master-sheet,dynamic-session-form}.tsx`, `ai/{agent-selector,chat-interface}.tsx`, `dashboard/recent-activity.tsx`, `auth/change-password-form.tsx` |
| **New keys** | 56 sections / 4090 leaf keys each (EN=FR parity) |
| **Notable patterns** | `change-password-form.tsx`: zod schema moved inside component in `useMemo([t])` per login.tsx precedent; `agent-selector.tsx`: `SelectValue` children render function `{(v) => labelFor(v)}` translates current value regardless of popup mount state (Base UI closed-trigger fix) |
| **Verification** | typecheck ✅, vitest 18/230 ✅, FR smoke 13/13 PASS |
| **Known gaps** | `/academic-calendar/blueprints` and `/ai/agents` 404 on demo tenant (backend data gaps, not i18n); `/media` has no cards in demo tenant (card dropdown verified via code review + locale keys) |
| **Status** | ✅ Complete |

### 3.7 Batch 4b — UI Primitives, Layout, Forms

| Property | Detail |
|---|---|
| **Commit** | `8a00171` (frontend) / `1e46f01` (parent) |
| **Files** | `ui/{calendar,date-picker,multi-select}.tsx`, `theme-toggle.tsx`, `layout/command-palette.tsx`, `forms/{class-form-fields,subject-form-fields}.tsx` |
| **New keys** | 62 sections / 4140 leaf keys each (EN=FR parity, zero key loss) |
| **Notable patterns** | `class-form-fields`: replaced module-level `LEVEL_OPTIONS`/`ARM_OPTIONS`/`getEduLevelOptions` with translated inline arrays; `getEduLevelOptions` returns `labelKey` for non-BEPC (translated via `t()`), BEPC labels kept as-is (already French); `dayjs` date-picker adds `import "dayjs/locale/fr"` + `.locale(i18n.language === "fr" ? "fr" : "en")`; format from `date_picker.date_format` ("D MMM YYYY" → "31 juil. 2026") |
| **Dev-server gotcha** | Adding `dayjs/locale/fr` while dev server runs corrupts Vite pre-bundle cache ("dayjs.js does not provide an export named 't'") — must restart server. Prod build unaffected. |
| **Verification** | typecheck ✅, vitest 18/230 ✅, prod build ✅, FR smoke 6/6 PASS (theme dropdown Clair/Sombre/Système, command palette placeholder "Rechercher des pages...", DatePicker trigger "31 juil. 2026", calendar popup "juillet 2026", weekday "Lu", command-palette no-results "Aucun résultat pour « zzzzzzzz »") |
| **Status** | ✅ Complete |

### 3.8 Batch 4c — Lib, Hooks, Education Countries, Routes

| Property | Detail |
|---|---|
| **Commit** | `b34d638` (frontend) / `d7dff9f` (parent) |
| **Files wrapped** | `lib/stores/auth-store.ts`, `lib/api.ts`, `lib/utils.ts`; hooks `{useAcademics,useAdmin,useMediaLibrary,useStudentHealth,useUsers}.ts` (`useGooglePlaces` EXCLUDED — errors logged only, never rendered); `data/education-countries.ts`; routes `{confirm-email,__root,_onboarding,_super}.tsx` + `_super/super.index.tsx`; consumers `{school-form-fields,session-form-fields}.tsx`, `ui/school-type-tabs.tsx`, `_dashboard/school.tsx` |
| **New keys** | 64 sections / 4068 leaf keys each (EN=FR parity; 48 keys added vs HEAD, 0 removed) |
| **New sections** | `email_confirmation` (8 keys), `education` (18 keys: region_* 11, term_* 4, type_* 2, Cercle), `errors` (+14 keys), `common` (+8 keys) |
| **education-countries strategy** | `import i18n from "@/i18n/i18n"`; WAEC_TERMS gained `labelKey` fields; `formatTermLabel` translates WAEC via `i18n.t(labelKey, { defaultValue })`, handles `summer` → `education.term_summer`, returns BEPC labels as-is (already French); `getTypeLabelKey(schoolType, framework?)` (null for BEPC), `getRegionLabelKey`, `getDistrictLabelKey` helpers |
| **Non-React modules** | Use `i18n.t()` at source (auth-store, api, utils, 5 hooks import `i18n` singleton) |
| **React components** | Use `useTranslation` hook |
| **Verification scan** | Raw-string scan of all 4c files caught 2 real misses (fixed): `school-form-fields.tsx` "Street address" placeholder → `t("school.street_address_placeholder")`; `useUsers.ts` "Unknown" name fallback → `i18n.t("common.unknown")` |
| **Verification** | typecheck ✅, vitest 18/230 ✅, prod build ✅ (13.68s), raw-string scan clean |
| **Status** | ✅ Complete |

---

## 4. FR Smoke Test Matrix (Per Page / Route)

| Route | Page | EN Verified | FR Verified | Key Translation Points | Status |
|---|---|---|---|---|---|
| `/login` | Login page | ✅ | ✅ | `auth.sign_in`, `auth.sign_in`, validation errors | ✅ |
| `/dashboard` | Dashboard | ✅ | ✅ | `nav.dashboard`, `nav.logout`, `common.back_to_home` | ✅ |
| `/dashboard/school` | School management | ✅ | ✅ | `school.*` keys, `formatSchoolType` via `getTypeLabelKey`, `school.street_address_placeholder` | ✅ |
| `/dashboard/school` (create) | School form | ✅ | ✅ | `common.select_country`, `common.select_framework`, `common.select_types`, `common.select_region`, `common.enter_region` | ✅ |
| `/dashboard/school` (session) | Session form | ✅ | ✅ | `formatTermLabel` → `education.term_first/second/third/summer` | ✅ |
| `/confirm-email` | Email confirmation | ✅ | ✅ | `email_confirmation.title`, `email_confirmation.confirming`, `email_confirmation.success_message`, `email_confirmation.failed`, `email_confirmation.missing_title`, `email_confirmation.missing_desc`, `email_confirmation.confirmed_title`, `email_confirmation.failed_title`, `email_confirmation.back_to_sign_in` | ✅ |
| `/404` | NotFound | ✅ | ✅ | `errors.not_found`, `common.back_to_home` | ✅ |
| `/onboarding` | Onboarding wizard | ✅ | ✅ | `nav.dashboard`, `nav.logout`, `pages.onboarding.*` (pre-existing) | ✅ |
| `/super` | Super admin layout | ✅ | ✅ | `nav.dashboard`, `nav.logout`, `pages.footer.copyright`, `common.search_schools`, `common.no_schools_match`, `common.no_schools` | ✅ |
| `/ai/agents` | AI agent selector | ✅ | ✅ | `agent-selector` FR labels (Tuteur académique, Nouvelle discussion, Propulsé par) | ✅ |
| `/media` | Media library | ✅ | ✅ | `media.*` keys (Téléverser, Bibliothèque, Rechercher) | ✅ |
| `/report-cards` | Report cards index | ✅ | ✅ | `report_cards.*` (22 keys), `reportCards.*` (18 keys) | ✅ |
| `/report-cards/batch` | Batch generation | ✅ | ✅ | `nav.batch` = "Génération par lot", all batch form labels | ✅ |
| `/academic-calendar` | Calendar views | ✅ | ✅ | `calendar.*` (21 keys: month_* 12, weekday_* 7, previous/next_month) | ✅ |
| `/academic-calendar/dynamic` | Dynamic master sheet | ✅ | ✅ | `academic_calendar.*` keys | ✅ |
| `/academic-calendar/session` | Session form | ✅ | ✅ | `formatTermLabel` → French terms | ✅ |
| `/timetable` | Timetable views | ✅ | ✅ | `timetable.*` keys (36 keys) | ✅ |
| `/admissions/*` | Admissions flow | ✅ | ✅ | `admissions.*` keys (147 keys incl. plural) | ✅ |
| `/template-builder` | Template editor | ✅ | ✅ | `template_builder.*` keys (40 keys incl. canvas/properties/result_slip_preview/template_editor/toolbox) | ✅ |
| `/template-builder/preview` | Result slip preview | ✅ | ✅ | FR preview dialog (Note totale/Moyenne/Matière/Note/Mention/Appréciation) | ✅ |
| `/users` | Users view | ✅ | ✅ | `users.*` keys, `common.unknown` fallback | ✅ |
| `/profile` | Profile modals | ✅ | ✅ | `profile.*` keys | ✅ |
| `/dashboard/recent-activity` | Recent activity | ✅ | ✅ | `dashboard.recent_activity.*` keys | ✅ |
| `/dashboard/change-password` | Change password | ✅ | ✅ | `auth.change_password.*` keys, zod messages in `useMemo([t])` | ✅ |

---

## 5. Translation Key Conventions

### 5.1 Key Naming Pattern

```
{section}.{sub-section}.{descriptor}
```

Examples:
- `email_confirmation.title`
- `education.region_state`
- `education.term_first`
- `errors.unknown_error`
- `common.select_country`
- `school.street_address_placeholder`

### 5.2 Section Naming

| Section | Purpose | Example Keys |
|---|---|---|
| `auth.*` | Authentication UI | `sign_in`, `sign_up`, `forgot_password`, `change_password` |
| `common.*` | Shared/global UI | `back_to_home`, `loading`, `cancel`, `delete`, `select_country` |
| `errors.*` | Error messages | `unknown_error`, `login_failed`, `not_found`, `request_failed_status` |
| `email_confirmation.*` | Email confirmation flow | `title`, `confirming`, `success_message`, `failed` |
| `education.*` | Education-specific labels | `region_*`, `term_*`, `type_*`, `Cercle` |
| `nav.*` | Navigation labels | `dashboard`, `logout`, `batch` |
| `pages.*` | Page-level labels | `onboarding.greeting.welcome`, `footer.copyright` |
| `report_cards.*` | Report cards module | `loading`, `description`, `batch_generate`, stats |
| `reportCards.*` | Batch generation | `batchGenerate`, `generationSettings`, class/session/term selectors |
| `teacher_report_cards.*` | Teacher report cards | `no_report_cards` |
| `calendar.*` | Calendar UI | `month_*`, `weekday_*`, `previous_month`, `next_month` |
| `date_picker.*` | Date picker | `date_format` |
| `multi_select.*` | Multi-select | 3 keys |
| `theme.*` | Theme toggle | `toggle`, `light`, `dark`, `system` |
| `command_palette.*` | Command palette | 3 keys |
| `forms.*` | Form fields | `class_name`, `education_level`, `select_education_level`, etc. |
| `school.*` | School module | `street_address_placeholder`, `link_curriculum`, `curriculum_name_placeholder` |
| `media.*` | Media library | `upload`, `library`, `search` |
| `dashboard.*` | Dashboard | `recent_activity.*` |
| `template_builder.*` | Template builder | `canvas.*`, `properties.*`, `result_slip_preview.*`, `template_editor.*`, `toolbox.*` |
| `admissions.*` | Admissions | 147 keys incl. plural (`fields_count_*`, `file_count_*`, `files_uploaded_*`) |
| `timetable.*` | Timetable | 36 keys |
| `lms_discussions.*` | LMS discussions | `replies_*` (plural convention) |

### 5.3 Translation Patterns

#### Pattern A: React Component (useTranslation)

```tsx
import { useTranslation } from "react-i18next";

function MyComponent() {
  const { t } = useTranslation();
  return <h1>{t("section.key", { defaultValue: "English text" })}</h1>;
}
```

#### Pattern B: JSX with Trans (rich content)

```tsx
import { Trans } from "react-i18next";

<Trans i18nKey="section.key" defaults="Text with <strong>{{name}}</strong>">
  <strong>{{ name: value }}</strong>
</Trans>
```

#### Pattern C: Module-Level Code (i18n Singleton)

```ts
import i18n from "@/i18n/i18n";

const label = i18n.t("section.key", { defaultValue: "English text" });
```

#### Pattern D: Helper Function (education-countries)

```ts
import i18n from "@/i18n/i18n";

export function formatTermLabel(term: string, framework?: string): string {
  const termData = WAEC_TERMS.find((t) => t.value === term);
  if (termData?.labelKey) {
    return i18n.t(termData.labelKey, { defaultValue: termData.label });
  }
  if (term === "summer") return i18n.t("education.term_summer", { defaultValue: "Summer" });
  return term; // BEPC labels are already French
}
```

### 5.4 Select Dropdown Convention (Rule F1)

Select dropdowns must use **entity names as `SelectItem` values**, never numeric IDs. The current value is resolved back to its name for the `value` prop, and the selected name is resolved back to an ID in `onValueChange`.

```tsx
const currentName = options.find((o) => o.id === watch("field_id"))?.name ?? "";
<Select
  value={currentName}
  onValueChange={(name) => {
    const opt = options.find((o) => o.name === name);
    if (opt) setValue("field_id", opt.id, { shouldValidate: true });
  }}
>
  <SelectContent>
    {options.map((o) => (
      <SelectItem key={o.id} value={o.name}>{o.name}</SelectItem>
    ))}
  </SelectContent>
</Select>
```

---

## 6. Verification Commands Reference

### Per-Batch Verification Sequence

```bash
# 1. Typecheck (must pass before commit)
cd frontend && yarn tsc --noEmit

# 2. Unit tests (must pass before commit)
cd frontend && yarn vitest run --reporter=dot

# 3. Production build (must pass before commit)
cd frontend && yarn build

# 4. FR smoke test (run against dev server on :4000)
NODE_PATH=frontend/node_modules node /tmp/opencode/academio-fr-smoke-4c.cjs

# 5. Raw-string scan (catch unwrapped user-facing strings)
# (custom Python script — see merge-batch4c.mjs companion)

# 6. Commit in frontend submodule
cd frontend && git add -A && git commit -m "i18n: wrap batch 4c strings ..."

# 7. Bump parent submodule pointer
cd .. && git add frontend && git commit -m "chore(frontend): bump submodule — i18n batch 4c ..."
```

### Dev Server Management

```bash
# Start backend
cd backend && ./bin/server  # binds :8080, queue worker runs as goroutine

# Start frontend dev server
cd frontend && yarn dev  # binds :4000, proxies /api → :8080

# Restart frontend dev server (required after adding dayjs/locale/fr or Vite pre-bundle cache corruption)
pkill -f "vite"  # or kill the PID from nohup log
cd frontend && yarn dev &
```

---

## 7. Known Gaps & Deferred Items

### 7.1 Strings Not Yet Translated

| Category | Reason | Tracking |
|---|---|---|
| Zod validation messages (e.g., `"School name required"`, `"Title required"`) | Follow repo-wide convention of keeping zod messages as literal English; displayed as field-level errors | Systemic pattern across 10+ files (exams.tsx, alumni, library, cba, finance, school.tsx) — deferred to a future batch |
| `useGooglePlaces.ts` error strings | Errors are logged only (`logger.Warnf`), never rendered to the user | Not user-facing — no translation needed |
| Demo/mock data subject names ("Mathematics", "English Language") | Deliberately kept English as demo data | By design |
| `WAEC_TERMS` and `BEPC_TYPE_LABELS` proper nouns ("WAEC", "BEPC") | Proper nouns — not translated | By design |
| `FRAMEWORKS` labels "WAEC"/"BEPC" | Proper nouns — not translated | By design |

### 7.2 Frontend Modules Not Yet Covered by i18n

| Module | Status | Notes |
|---|---|---|
| `backend/` submodule | N/A | Backend is a separate Go codebase; its i18n is tracked in `docs/backend-test-cases.md` |
| `mobile/` submodule | Not started | Flutter/Dart app; i18n strategy TBD |
| `ai-engine/` submodule | Not started | Python FastAPI; i18n strategy TBD |

### 7.3 Dev-Server Gotchas

| Issue | Symptom | Fix |
|---|---|---|
| Adding `dayjs/locale/fr` while dev server runs | Vite pre-bundle cache corruption: "dayjs.js does not provide an export named 't'" | Restart dev server (`pkill -f vite && yarn dev`) |
| Submodule pointer mismatch | Parent repo references old frontend commit after push | Always push frontend first, then push parent to update pointer |

---

## 8. Key Mapping: Backend Error Keys → Frontend Translation Keys

This mapping ensures backend error messages displayed on the frontend are properly translated.

| Backend Error Key | Frontend Translation Key | Status |
|---|---|---|
| (backend returns raw error string) | `errors.unknown_error` | ✅ Wrapped in `api.ts` |
| (backend returns error with status) | `errors.request_failed_status` with `{{status}}` interpolation | ✅ Wrapped in `api.ts` |
| Login failure | `errors.login_failed` | ✅ Wrapped in `auth-store.ts` |
| TOTP verification failure | `errors.totp_verification_failed` | ✅ Wrapped in `auth-store.ts` |
| Session expired | `errors.session_expired` | ✅ Reused existing key |
| Token refresh failure | `errors.token_refresh_failed` | ✅ Wrapped in `auth-store.ts` |
| Registration failure | `errors.registration_failed` | ✅ Wrapped in `auth-store.ts` |
| Avatar file type error | `errors.avatar_file_type` | ✅ Wrapped in `utils.ts` |
| Avatar file size error | `errors.avatar_file_size` | ✅ Wrapped in `utils.ts` |
| Failed to download scores | `errors.failed_download_scores` | ✅ Wrapped in `useAcademics.ts` |
| Failed to load school users | `errors.failed_load_school_users` | ✅ Wrapped in `useAdmin.ts` |
| Not authenticated | `errors.not_authenticated` | ✅ Wrapped in `useAdmin.ts` |
| Upload failed | `errors.upload_failed` | ✅ Wrapped in `useMediaLibrary.ts` + `useUsers.ts` |
| Failed to export health PDF | `errors.failed_export_health_pdf` | ✅ Wrapped in `useStudentHealth.ts` |
| Failed to load students for class | `errors.failed_load_students_for_class` | ✅ Wrapped in `useUsers.ts` |
| Failed to load users | `errors.failed_load_users` | ✅ Wrapped in `useUsers.ts` |
| Preview failed | `errors.preview_failed` | ✅ Wrapped in `useUsers.ts` |

---

## 9. Revision History

| Date | Batch | Author | Changes |
|---|---|---|---|
| 2026-07-31 | 3a | Agent | Initial document creation |
| 2026-07-31 | 3b | Agent | Added 3b entries |
| 2026-07-31 | 3c | Agent | Added 3c entries (147 admissions + 36 timetable + 40 template_builder keys) |
| 2026-07-31 | Report-cards | Agent | Added report-cards route follow-up entries |
| 2026-07-31 | Breadcrumb | Agent | Added batch breadcrumb follow-up entries |
| 2026-07-31 | 4a | Agent | Added 4a entries (12 files, 56 sections / 4090 keys) |
| 2026-07-31 | 4b | Agent | Added 4b entries (7 files, 62 sections / 4140 keys) |
| 2026-08-01 | 4c | Agent | Added 4c entries (19 files, 64 sections / 4068 keys); added raw-string scan results; added known gaps section |
