# Feature Landscape

**Domain:** School Management System (SIS) — Nigerian-focused, multi-tenant
**Researched:** 2026-07-18
**Competitive set:** PowerSchool SIS, FACTS SIS (RenWeb), Gradelink, OpenSIS, sERP Nigeria, SchoolOS Nigeria, EduSync Nigeria, RosarioSIS, Infinite Campus

## Feature Inventory: Current State

Academio already has **39 backend modules** covering core SIS functionality. Before identifying gaps, here is the confirmed inventory:

| Module | Status | Notes |
|--------|--------|-------|
| Auth (JWT, 2FA, RBAC) | ✅ Complete | CSRF, refresh tokens, Redis revocation |
| Multi-Tenant (schema-per-tenant) | ✅ Complete | GORM SchemaTablePrefix plugin |
| School/Provisioning | ✅ Complete | Auto-migration, seeding |
| Academic Structure (sessions/terms/curriculum/levels) | ✅ Complete | Grade items with sum-to-100 |
| Admissions (form builder, pipeline) | ✅ Complete | Dynamic forms, public apps |
| User/Student/Staff/Parent CRUD | ✅ Complete | XLSX batch, sibling reuse, parent dedup |
| Assessment & Scoring | ✅ Complete | Grade items, bulk save, rollup, export |
| Attendance (student + staff) | ✅ Complete | Roll-call, bulk upsert, clock-in/out |
| Timetable | ✅ Complete | CRUD, bulk create, calendar editor, conflicts |
| Report Cards | ✅ Complete | Templates, batch generation |
| Communication (Email/SMS) | ✅ Complete | SendGrid, Twilio, templates, campaigns |
| AI Integration (Gemini, OpenAI, RAG) | ✅ Complete | Qdrant vector store, applicant scoring |
| Finance (CoA, journals, budgets, billing) | ✅ Complete | Chart of accounts, expenses |
| HR (departments, leave, payroll, appraisals) | ✅ Complete | Recruitment |
| LMS (courses, modules, lessons, assignments) | ✅ Complete | Discussions |
| Library | ✅ Complete | |
| Hostel | ✅ Complete | |
| Transport (routes, vehicles, assignments) | ✅ Complete | |
| Inventory | ✅ Complete | |
| Alumni | ✅ Complete | Dashboard insights |
| CBA (computer-based assessments) | ✅ Complete | |
| Proctoring | ✅ Complete | |
| Exam (schedule + results) | ✅ Complete | |
| Career (profiles, assessments, recommendations) | ✅ Complete | |
| Pastoral (wellness surveys, counseling) | ✅ Complete | |
| Health (system monitoring) | ✅ System-level only | **NOT student health records** |
| Analytics/Reporting | ✅ Complete | Custom report builder, predefined reports |
| Notifications | ✅ Complete | |
| Multimedia (file upload/storage) | ✅ Complete | |
| Backup/Restore (S3, pg_dump) | ✅ Complete | 14-backup retention |
| Observability (OTel, Prometheus, Swagger) | ✅ Complete | |
| Payment Processing | ✅ Complete | |

---

## Table Stakes

Features that Nigerian schools (and schools generally) expect. Missing these makes the product feel incomplete vs. competitors like PowerSchool, FACTS SIS, or sERP Nigeria.

### HIGH Priority

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Student Health Records** | Every mature SIS (PowerSchool, FACTS, OpenSIS, Gradelink) has health tracking — immunizations, allergies, medications, nurse visits, screenings. The existing `health` module is system-level health checks, not student health. | **Medium** | This is the #1 feature gap. Nigerian schools track immunization records (polio, BCG, hepatitis), sickle cell status, allergy alerts, and medication administration. The pastoral module partially covers well-being but not physical health. |
| **Discipline / Behavior Management** | All major SIS platforms (Gradelink, OpenSIS, PowerSchool, Infinite Campus) include discipline tracking — incident logging, behavior categories, detention management, suspension tracking, parent notifications. The `pastoral` module covers wellness but not behavioral incidents. | **Low-Medium** | Nigerian schools require this for tracking student conduct, suspensions, expulsions, and communicating with parents about behavioral issues. Links naturally to communication module for automatic SMS/email alerts. |
| **Parent-Teacher Conference Management** | Expected by parents and teachers. Scheduling, slot booking, confirmation, reminders. PowerSchool and FACTS both have this. | **Low** | Relatively simple to build on top of the existing communication and timetable infrastructure. Could be a quick win. |
| **Graduation / Degree Audit Tracking** | OpenSIS and PowerSchool track graduation requirements — credits needed vs earned, subject completion status, readiness for WAEC/NECO. The existing `exam` and `score` modules have partial data but no graduation audit. | **Medium** | Nigerian secondary schools need to track which students have met JSS/SSS promotion requirements and WAEC/NECO eligibility. |
| **End-of-Year Rollover / Student Promotion** | Annual process where students advance to next grade level, archived data is sealed, and new academic year is configured. PowerSchool and OpenSIS automate this. | **High** | Critical operational feature. Currently the system has sessions/terms but no automated promotion workflow that moves cohorts, archives grades, and locks previous year data. Missing this causes major admin pain annually. |
| **Competency/Grading Scale Configuration (CA/Exam split)** | Nigerian schools operate on a Continuous Assessment (CA) + exam model (30/70, 40/60, 50/50 splits). WAEC uses A1–F9 scale. sERP Nigeria and EduSync offer this as core. | **Medium** | The `score` module has grade items with sum-to-100, but CA/Exam split configuration per subject/class/session and automatic WAEC/NECO grade-scale mapping may need explicit support. Verify current implementation depth. |

### MEDIUM Priority

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Cafeteria / Food Service Management** | FACTS SIS, Gradelink, OpenSIS, and PowerSchool integrate meal management — lunch orders, dietary tracking, meal plan billing, POS integration. Nigerian boarding schools especially need this. | **High** | Would integrate with `finance` (meal billing), `inventory` (food stock), and `hostel` (boarding students). However, the Nigerian market may not widely adopt this — prioritize only if targeting boarding schools specifically. |
| **Fee Structure Configuration** | Nigerian schools have complex fee structures — tuition, PTA levies, development fees, exam fees, sports fees, uniform fees, bus fees. sERP Nigeria and SchoolOS offer flexible fee configuration per term/class/student. The current `finance` module has billing but verify it handles Nigerian fee complexity (waivers, partial payments, term installments, late fees). | **Medium** | Verify existing `finance` module supports: fee itemization, per-class fee structures, term-based billing, discounts/scholarships, and debtors list (all standard in sERP Nigeria). |
| **SMS Billing Alerts** | Nigerian parents expect SMS notifications for fee reminders, payment confirmations, and debt notices. sERP Nigeria and SchoolOS highlight this as a must-have. The `communication` module supports SMS via Twilio but verify NGN-compatible billing alerts specifically. | **Low** | Low complexity — mostly configuration and template work on top of existing communication module. |
| **Multi-Branch / Multi-Campus Management** | Schools with multiple branches (common in Nigeria — e.g., nursery/primary/secondary on separate campuses) need consolidated management. sERP Nigeria offers this. Currently Academio is multi-tenant (per-school) but not multi-campus within a school. | **High** | Significant architectural change. Each "campus" could be a sub-tenant or use a shared schema with campus_id filter. Not urgent for initial MVP. |
| **Student Timetable Portal / Mobile View** | Parents and students expect to see timetables on their portal/mobile. FACTS and PowerSchool offer this. Currently timetables exist in the admin interface but student/parent portal display may need work. | **Low** | Mostly frontend — read timetable data through existing API and display in parent/student dashboard. |
| **WhatsApp Notification Integration** | EduSync Nigeria differentiates with WhatsApp-first communication. Nigerian parents are more responsive on WhatsApp than email. Adding WhatsApp notification channel (via Twilio WhatsApp API or similar) would be a strong local differentiator. | **Medium** | Requires building a new notification channel provider. Low backend complexity if Twilio is already used for SMS. |

---

## Differentiators

Features that set Academio apart. Some already exist; some should be emphasized in marketing; some could be strengthened.

### Existing Differentiators (Strengthen & Market)

| Feature | Current State | Recommendation |
|---------|--------------|----------------|
| **Multi-Tenant Schema Isolation** | ✅ Complete. Schema-per-tenant with GORM plugin. | This is stronger than most competitors (who use row-level tenant filtering). Market this as a security differentiator. |
| **AI Integration** | ✅ Complete. Gemini + OpenAI, RAG with Qdrant, AI applicant scoring. | Few SIS platforms have this. Lead with it. Could expand to AI lesson plan generation, AI report card comments, AI behavior pattern analysis. |
| **CBA + Proctoring** | ✅ Complete. Computer-based assessments with remote proctoring. | WAEC/NECO is moving to full CBT by 2026 (per government announcement). This positions Academio perfectly. |
| **Custom Report Builder** | ✅ Complete. | Continue investing — the ad-hoc reporting gap is the #1 complaint in PowerSchool reviews. |
| **Career Guidance** | ✅ Complete. Career profiles, assessments, recommendations. | Differentiator vs Nigerian competitors. |
| **Pastoral Care / Wellness** | ✅ Complete. Wellness surveys, alerts, counseling sessions. | Strong differentiator — few SIS platforms have this. |
| **Schema-Aware Backup/Restore** | ✅ Complete. S3-backed, per-tenant pg_dump. | Enterprise-grade feature. |

### Buildable Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **WAEC/NECO CBT-Ready Certification** | Position Academio as the system that prepares students for WAEC/NECO's CBT transition (government mandate by 2026). CBA module + WAEC-style question bank + mock exam mode. | **Medium** | Build on top of existing CBA module. Add WAEC subject structure, time limits, past question banks. |
| **NERDC Curriculum Alignment** | Pre-loaded NERDC 2025 curriculum for all subjects from JSS1–SSS3. Nigeria-specific competitors (EduKit, sERP) offer this. | **High** | Requires building the curriculum database. Could partner with a curriculum content provider or build incrementally per subject. |
| **WhatsApp-First Parent Communication** | EduSync uses this as a differentiator. Parents don't need to install an app — they get results, fee reminders, and attendance alerts on WhatsApp. | **Medium** | Twilio WhatsApp API integration. Adds to existing communication module. |
| **AI-Powered Report Card Comments** | Many teachers spend hours writing report card remarks. AI-generated personalized comments (strengths, areas for improvement) save massive time. | **Low** | Already have AI providers. Feed assessment data → prompt → generate comment. |
| **Low-Bandwidth / Offline Mode** | Nigerian schools often have unreliable internet. PWA with offline-first capabilities (like SchoolOS offers) is a strong differentiator. | **High** | Significant frontend architecture work (service workers, IndexedDB, sync queues). |
| **LEA/State Compliance Dashboard** | Nigerian states (Lagos, Rivers, etc.) require specific data submissions. A dashboard that maps internal data to state reporting templates would be highly valued. | **High** | Requires research into each state's requirements. High value but incremental build. |

---

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Native Mobile Apps (iOS/Android)** | Costly to develop and maintain for two platforms. Most Nigerian SIS users access via browser on phone. SchoolOS proves PWA is sufficient. | Build a robust PWA — service workers, offline caching, add-to-home-screen. Already have mobile-responsive Tailwind CSS. |
| **Video Conferencing** | Out of scope for an SIS. No school expects video conferencing from their management system. | Integrate with Zoom/Google Meet links if needed (simple URL field). |
| **Custom Website Builder / Landing Pages** | Competes with dedicated tools. Schools already have websites or use WordPress. | School branding via config only (logo, colors, domain). Not a CMS. |
| **Real-Time Collaboration (Docs/Sheets)** | Google Classroom, Microsoft 365, and Canvas already solve this. Would be expensive to build, hard to compete. | Focus on data integration with LMS (existing) and Google Classroom sync. |
| **E-Commerce / School Store** | Not part of core SIS value prop. Payment module handles fee collection — don't expand to general e-commerce. | Keep payment processing scoped to fees and donations only. |
| **Full HRIS / Payroll Engine** | Nigerian payroll (PAYE, pension, NSITF) is complex and regulated. Building compliant payroll is a product unto itself. The existing HR module has payroll but consider keeping it simple or integrating with Nigerian payroll providers. | If payroll becomes complex, integrate with Nigerian payroll APIs rather than building in-house tax calculation. |
| **Exam Board Content Licensing** | WAEC/NECO question bank licensing would require legal agreements and possibly royalty payments. | Focus on mock exam creation tools (school creates own questions) rather than licensing WAEC past questions. |

---

## Feature Dependencies

```
Student Health Records
  └── Depends on: User module (student profiles exists), Communication module (parent alerts)

Discipline / Behavior Management
  └── Depends on: User module (student/staff), Communication module (parent notifications)
  └── Links to: Pastoral (wellness alerts), Attendance (truancy tracking)

Graduation / Degree Audit
  └── Depends on: Score module (grades), Academic module (curriculum requirements)
  └── Links to: Exam module (WAEC/NECO eligibility), Alumni module (graduate records)

End-of-Year Rollover
  └── Depends on: Academic module (sessions/terms), Score module (grade archiving)
  └── Depends on: Timetable module (archive old, create new)
  └── Links to: All modules that store year-scoped data

CA/Exam Split Grading
  └── Depends on: Score module (grade items), Academic module (assessment types)
  └── Links to: Report cards, Transcripts

Fee Structure Configuration (NGN)
  └── Depends on: Finance module (billing/invoicing)
  └── Links to: Payment module, Communication module (SMS alerts)

WhatsApp Notifications
  └── Depends on: Communication module (existing provider interface)
  └── Depends on: Twilio WhatsApp API account setup
```

---

## MVP / Phase Recommendations

### Phase 1 (Immediate — Critical Gaps)
Prioritize:
1. **Student Health Records** — Biggest missing table-stakes feature. Start with immunization tracking and allergy alerts (highly visible to parents).
2. **CA/Exam Split Grading Configuration** — Verify current depth; add if missing. Essential for Nigerian schools.
3. **Fee Structure Configuration (NGN)** — Verify existing `finance` module covers Nigerian fee complexity. Essential for revenue.

### Phase 2 (Near-term — Table Stakes)
Prioritize:
1. **Discipline / Behavior Management** — Incident logging, detention tracking, parent notifications.
2. **Parent-Teacher Conference Management** — Quick win, low complexity.
3. **End-of-Year Rollover / Promotion** — Critical annual operation. High complexity — plan carefully.
4. **WhatsApp Notification Integration** — Strong local differentiator. Build on existing Twilio integration.
5. **Graduation / Degree Audit Tracking** — WAEC/NECO eligibility tracking.

### Phase 3 (Growth — Differentiators)
Prioritize:
1. **NERDC Curriculum Alignment** — Pre-loaded curriculum per subject/class. High effort but high value for Nigerian market.
2. **WAEC/NECO CBT-Ready Certification** — Build on CBA module. Timely given government mandate.
3. **AI-Powered Report Card Comments** — Quick win leveraging existing AI providers.
4. **Low-Bandwidth / Offline PWA** — Major UX investment. Consider user research first.

### Phase 4 (Mature — Expansion)
Consider:
1. **Multi-Campus Management** — Only if acquiring multi-branch school chains.
2. **LEA/State Compliance Dashboards** — Target specific states with largest customer bases.
3. **Cafeteria Management** — Only for boarding school segment.
4. **Biometric Integration** — fingerprint/face for attendance (Nigerian schools interested in this).

---

## Sources

| Source | Type | Confidence |
|--------|------|------------|
| PowerSchool SIS — TrustRadius features page (trustradius.com) | Third-party review aggregation | MEDIUM |
| PowerSchool SIS official product page (powerschool.com) | Official documentation | HIGH |
| FACTS SIS / RenWeb feature list (various school pages using FACTS) | Primary research | MEDIUM |
| OpenSIS features page (opensis.com) | Official documentation | HIGH |
| OpenSIS Classic GitHub repository | Source code | HIGH |
| Gradelink features page (gradelink.com) | Official documentation | HIGH |
| sERP Nigeria feature tour (schoolerpnigeria.com) | Nigerian competitor | HIGH |
| SchoolOS Nigeria feature list (schoolosapp.com.ng) | Nigerian competitor | HIGH |
| EduSync Nigeria features (edusync.ng) | Nigerian competitor | HIGH |
| EduKit Nigeria (edukits.com.ng) | Nigerian competitor | MEDIUM |
| RosarioSIS feature list (sourceforge.net) | Open-source competitor | MEDIUM |
| SchoolDoc student health records (schooldoc.com) | Niche competitor | MEDIUM |
| EduHealth student health system (eduhealthsystem.com) | Niche competitor | MEDIUM |
| Nigerian government CBT transition announcement (technext24.com) | News source | HIGH |
| Various school management software reviews (softwareadvice.com, capterra.com) | Review aggregation | MEDIUM |
| Infinite Campus features documentation | Official documentation | MEDIUM |

**Research notes:**
- Nigerian competitor data gathered from product websites and feature pages (July 2026)
- International SIS data from official documentation and review sites
- Several findings (especially Nigerian-specific features like NERDC alignment) need validation with actual Nigerian school administrators
- The existing codebase has more features than initially communicated — career, pastoral, exam modules exist but were not listed in the milestone context
