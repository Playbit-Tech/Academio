# Permission Matrix

> **Audience:** Engineers, QA, school admins.
> **Source of truth:** `backend/internal/rbac/defaults.go:26-108` (seed grants).
> **Cross-checked:** against T4a E2E results (75/75 green) + T4b frontend E2E (28/28 green).

## Legend

- ✅ = granted by default
- ❌ = absent by design
- 🔒 = fail-closed (absence proves a security boundary)
- `*` = platform-wide (super_admin bypass)

## Dashboard Branch Resolution

Branches resolve from permission sets, never role strings (`frontend/src/lib/auth/dashboard-branch.ts:45-66`).

| Branch | Discriminator | Order |
|--------|---------------|-------|
| `principal` | `sessions:write` ∧ ¬`users:write` ∧ ¬`schools:write` | 1st |
| `nurse` | `health:write` ∧ ¬`users:write` | 2nd |
| `counselor` | `pastoral:write` ∧ ¬`sessions:write` ∧ ¬`users:write` | 3rd |
| `admissions` | `admissions:write` ∧ ¬`users:write` | 4th |
| `accountant` | `finance:write` ∧ ¬`users:write` | 5th |
| `librarian` | `library:write` ∧ ¬`finance:write` ∧ ¬`sessions:write` ∧ ¬`users:write` | 6th |
| `generic` | (everything else) | 7th |

## Role × Permission Matrix

### System-Level

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `platform:manage` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### School-Level

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `schools:read` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `schools:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `users:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `users:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `roles:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `audit:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |

### Academic

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `sessions:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `sessions:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `sessions:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `grading:read` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `grading:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `results:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `results:publish` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅¹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `exams:read` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `exams:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅¹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `attendance:read` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌² | ❌ | ❌ | ❌ | ❌ | ❌ |
| `attendance:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌² | ❌ | ❌ | ❌ | ❌ | ❌ |
| `timetable:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `cba:read` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `cba:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `lms:read` | ✅* | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `lms:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Students & People

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `students:read` | ✅* | ✅ | ✅ | ❌ | ✅ | ✅ | ❌³ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `students:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `students:export` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Finance

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `finance:read` | ✅* | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `finance:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `finance:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `finance:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `finance:export` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `payments:pay` | ✅* | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Library

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `library:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `library:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `library:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `library:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

### Health

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `health:read` | ✅* | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `health:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `health:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `health:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅⁴ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |

### Pastoral & Discipline

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `pastoral:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `pastoral:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `pastoral:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `pastoral:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `discipline:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `discipline:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `discipline:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Career

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `career:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `career:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

### Admissions

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `admissions:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `admissions:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `admissions:delete` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `admissions:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `admissions:export` | ✅* | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

### Communication

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `communication:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `communication:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Reporting & Analytics

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `reports:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| `reports:export` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `analytics:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Other

| Permission | super_admin | admin | teacher | student | parent | principal | staff | accountant | librarian | nurse | counselor | admissions |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `dashboard:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌⁵ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `calendar:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `calendar:manage` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅¹ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `notifications:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `forum:read` | ✅* | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `forum:write` | ✅* | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `media:read` | ✅* | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `media:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ai:read` | ✅* | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ai:write` | ✅* | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `branding:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `branding:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `email_studio:read` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `email_studio:write` | ✅* | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Staff (grant-by-grant)

| Note | Description |
|------|-------------|
| ¹ | Dead grant — routes empty; kept for future use, not cleaned up (T8 default OFF). |
| ² | Staff gets `attendance:read`/`write` only when explicitly granted per school via RBAC admin. Zero defaults. |
| ³ | Staff gets `students:read` only when explicitly granted per school. |
| ⁴ | Principal gets `health:manage` for school-summary access. Parent holds only `health:read` → 403 on school-summary (PHI gate). |
| ⁵ | Staff gets `dashboard:read` only when explicitly granted. Zero-perm staff sees empty state. |

## Route × Permission Mapping

Every admin-nav href maps to exactly one permission (`frontend/src/lib/auth/role-config.ts:74-147`).

| Route | Required Permission |
|-------|-------------------|
| `/school` | `schools:read` |
| `/academics` | `schools:read` |
| `/academic-calendar` | `calendar:read` |
| `/timetable` | `timetable:read` |
| `/attendance` | `attendance:read` |
| `/lesson-plans` | `lms:read` |
| `/lms` | `lms:read` |
| `/career` | `career:read` |
| `/conferences` | `calendar:read` |
| `/external-exam` | `exams:read` |
| `/cba` | `cba:read` |
| `/cba/exams` | `cba:read` |
| `/proctoring` | `cba:read` |
| `/admissions` | `admissions:read` |
| `/media` | `media:read` |
| `/library` | `library:read` |
| `/hostel` | `hostel:read` |
| `/transport` | `transport:read` |
| `/inventory` | `inventory:read` |
| `/pastoral` | `pastoral:read` |
| `/discipline` | `discipline:read` |
| `/student-health` | `health:read` |
| `/finance` | `finance:read` |
| `/bills` | `finance:read` |
| `/hr` | `hr:read` |
| `/users` | `users:read` |
| `/invitations` | `users:read` |
| `/alumni` | `users:read` |
| `/alumni/insights` | `reports:read` |
| `/analytics` | `analytics:read` |
| `/reports` | `reports:read` |
| `/forum` | `forum:read` |
| `/communication/compose` | `communication:write` |
| `/communication/templates` | `communication:read` |
| `/communication/campaigns` | `communication:read` |
| `/communication/broadcast` | `communication:read` |
| `/communication/delivery` | `communication:read` |
| `/settings` | `schools:write` |
| `/audit-logs` | `audit:read` |
| `/ai-studio` | `ai:read` |

Always visible (no permission gate): `/dashboard`, `/notifications`, `/messages`, `/profile`.

## Staff Dashboard Sections

Staff is permission-less by design (zero defaults). When grants are assigned per school, sections compose via `<Can>` gates (`frontend/src/components/dashboard/staff-sections.tsx`).

| Section | Gate | Source |
|---------|------|--------|
| Attendance / Scan | `attendance:read` + `attendance:write` | `useStaffScanAttendance`, `useQrAttendance` |
| Leave Requests | `hr:read` | `useLeaveRequests`, `useCreateLeaveRequest` |
| Payslips | `hr:read` | `usePayslips` |
| Hostel Roster | `hostel:read` | `useHostelBlocks` |
| Messages | (always visible) | `ALWAYS_VISIBLE_HREFS` |
| Notifications | (always visible) | `ALWAYS_VISIBLE_HREFS` |

Zero-perm staff → empty state (existing Phase-1 fallback).
