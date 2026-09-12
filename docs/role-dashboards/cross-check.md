# T6 Cross-Check: Matrix vs E2E Output

> **Audience:** QA, engineers.
> **Procedure:** For each matrix row, verify the role's asserted perm set matches E2E-observed set; every gated route in matrix matches registry declaration.

## Cross-Check Results

| # | Role | Matrix Claim | T4a E2E Check | T4b E2E Check | Status |
|---|------|-------------|---------------|---------------|--------|
| 1 | super_admin | `platform:manage` present, all perms | ✅ Session valid, platform ops | N/A (dedicated landing) | PASS |
| 2 | admin | `users:write` present, `platform:manage` absent | ✅ users:write confirmed, platform:manage fail-closed | ✅ /dashboard generic branch | PASS |
| 3 | teacher | `grading:read` present | ✅ grading:read confirmed, timetables accessible | N/A (dedicated /teacher/dashboard) | PASS |
| 4 | student | `timetable:read` present | ✅ timetable:read confirmed, student/dashboard portal | N/A (dedicated /academics) | PASS |
| 5 | parent | `health:read` present, school-summary 403 | ✅ health:read confirmed, PHI 403 | N/A (dedicated /parent) | PASS |
| 6 | principal | `sessions:write` present, `users:write` absent | ✅ sessions:write confirmed, users:write fail-closed, D-C approve → 200 | ✅ /dashboard principal branch | PASS |
| 7 | staff (zero) | Empty permissions | ✅ Empty permissions, empty state | ✅ Empty state, zero 403s | PASS |
| 8 | staff (granted) | `attendance:read` present, `hr:read` absent | ✅ attendance:read confirmed, hr:read fail-closed, section RBAC pass/deny | ✅ Held sections mount, unheld hidden | PASS |
| 9 | accountant | `finance:write` present | ✅ finance:write confirmed, invoices, expense approve → 200, audit-logs | ✅ /dashboard accountant branch | PASS |
| 10 | librarian | `library:write` present | ✅ library:write confirmed, summary, issue→return chain, forged expense 403 | ✅ /dashboard librarian branch | PASS |
| 11 | nurse | `health:manage` present | ✅ health:manage confirmed, school-summary → 200, visit audit row | ✅ /dashboard nurse branch | PASS |
| 12 | counselor | `pastoral:write` present, self-only | ✅ pastoral:write confirmed, self-only caseload, forged discipline 403 | ✅ /dashboard counselor branch | PASS |
| 13 | admissions | `admissions:write` present | ✅ admissions:write confirmed, SC3b chain completes | ✅ /dashboard admissions branch | PASS |

## Route Gate Cross-Check

| Route | Matrix Permission | Backend Gate | Status |
|-------|-------------------|--------------|--------|
| `/finance` | `finance:read` | ✅ Backend requires finance:read | PASS |
| `/library` | `library:read` | ✅ Backend requires library:read | PASS |
| `/student-health` | `health:read` | ✅ Backend requires health:read | PASS |
| `/hr` | `hr:read` | ✅ Backend requires hr:read | PASS |
| `/users` | `users:read` | ✅ Backend requires users:read | PASS |
| `/settings` | `schools:write` | ✅ Backend requires schools:write | PASS |
| `/audit-logs` | `audit:read` | ✅ Backend requires audit:read | PASS |
| `/career` | `career:read` | ✅ Backend requires career:read | PASS |
| `/pastoral` | `pastoral:read` | ✅ Backend requires pastoral:read | PASS |
| `/discipline` | `discipline:read` | ✅ Backend requires discipline:read | PASS |
| `/admissions` | `admissions:read` | ✅ Backend requires admissions:read | PASS |
| `/communication/compose` | `communication:write` | ✅ Backend requires communication:write | PASS |

## Forged-Call Spot-Checks

| Forger | Endpoint | Expected | T4a Result |
|--------|----------|----------|------------|
| teacher | `PUT /academic/result/:id/approve` | 403 | ✅ 403 |
| librarian | `POST /finance/expenses/:id/approve` | 403 | ✅ 403 |
| counselor | `POST /discipline/incidents` | 403 | ✅ 403 |
| principal | `POST /finance/expenses/:id/approve` | 403 | ✅ 403 |

## PHI Gate Cross-Check

| Role | Endpoint | Expected | T4a Result |
|------|----------|----------|------------|
| parent | `GET /student-health/school-summary` | 403 | ✅ 403 |
| nurse | `GET /student-health/school-summary` | 200 | ✅ 200 |
| principal | `GET /student-health/school-summary` | 200 | ✅ 200 |
| teacher | `GET /student-health/school-summary` | 403 | ✅ 403 (no health:manage) |

## D-C Approve Chain Cross-Check

| Step | Action | Expected | T4a Result |
|------|--------|----------|------------|
| 1 | Teacher save scores | 200 | ✅ 200 |
| 2 | Result status = teacher-approved | SessionID + AssessmentID set | ✅ Seed fix applied |
| 3 | Principal approve | 200 | ✅ 200 |
| 4 | Pending queue shrinks | Row gone from pending | ✅ Confirmed |
| 5 | Re-publish idempotent | 200 | ✅ 200 |

## SC Mapping

| Roadmap SC | Task | Runnable Check | Status |
|------------|------|----------------|--------|
| SC1 staff home functional | T2, T4a#7, T4b | branch test green + role-7 API + UI cases green | ✅ PASS |
| SC2 direct-URL redirect | T3 | librarian→`/finance` → `/dashboard` recorded | ✅ PASS |
| SC3 `<Can>` + backend 403 | T3, T4a, T4b | CTA enumeration + forged-call 403s + redirect cases green | ✅ PASS |
| SC4 fresh seed + all-12 E2E + docs truth | T1, T4a, T4b, T6 | clean-slate runs exit 0 + matrix cross-check | ✅ PASS |

## Conclusion

All 13 role matrix rows verified against T4a/T4b E2E output. All 12 route gates verified against backend. All 4 forged-call spot-checks pass. PHI gate verified. D-C approve chain verified. **Matrix cross-check: GO.**
