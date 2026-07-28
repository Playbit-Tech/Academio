# Academio — Comprehensive Implementation Plan

> 23 phases covering all mobile screens, backend gaps, quality & security
> Generated from full codebase analysis on 27 July 2026

---

## How to Read This Plan

Each **Phase** is self-contained and ordered by dependency — earlier phases should be completed before later ones. Each **Sub-phase** is 1-4 hours of work and ends with a concrete deliverable (screens, providers, tests). Phases can be skipped or reordered, but check the **Depends on** section.

**Legend**
- 🐛 = Bug fix / existing issue
- 🧪 = Testing / quality
- 🎨 = UI / UX
- 🏗️ = New feature (mobile screen)
- 🔧 = Backend / infrastructure
- 🔒 = Security

Estimated totals at the end.

---

## Phase 1 — Bug Fixes (Current Code Issues)

> Fix all known bugs and regressions in existing code before building anything new.

### 1.1 — Fix Silent Error Discards 🐛

**Files:** `mobile/lib/providers/teacher_provider.dart`, `mobile/lib/providers/auth_provider.dart`

| Location | Issue | Fix |
|----------|-------|-----|
| `teacher_provider.dart:56` | `catch (_) {}` swallows error in student count loop | Log with `logger.warn`, continue loop |
| `auth_provider.dart:71` | `catch (_) { await _tryRefresh(); }` swallows original error | Log original error before refresh attempt |
| `auth_provider.dart:164` | `catch (_) { await logout(); }` swallows error | Log error before logout |

**Acceptance:** Every `catch` block either logs the error or re-throws, never silently discards.

### 1.2 — Fix Hardcoded IDs in Teacher Screens 🐛

**Files:** `teacher_attendance_screen.dart`, `teacher_class_screen.dart`, `teacher_academics_screen.dart`

| Screen | Hardcoded Value | Fix |
|--------|----------------|-----|
| `teacher_attendance_screen.dart:36` | `levelId: 2` | Fetch from teacher profile on init, use `selectedLevel.id` |
| `teacher_class_screen.dart:23` | `levelId: 2` | Fetch from teacher profile on init, use `selectedLevel.id` |
| `teacher_academics_screen.dart:171-172` | `assessmentId: 1, sessionId: 1` | Add assessment picker dropdown + fetch current session from API; default to first/found |

**Acceptance:** All three screens render with real level/assessment/session data from the API, not hardcoded seed IDs.

### 1.3 — Fix Student Dashboard Data Discard 🐛

**File:** `mobile/lib/providers/student_provider.dart`

**Issue:** `fetchDashboard()` calls `GET /api/v2/student/dashboard` at line 61-62 but discards the response. The dashboard screen shows only navigation cards, never actual stats.

**Fix:** Parse the dashboard response into typed fields (enrollment count, current GPA, attendance %, etc.) and expose them on the provider. Update `student_dashboard.dart` to display real data in the stat cards.

**Acceptance:** Student dashboard shows actual API values (not placeholder text) for enrollment, GPA, attendance stats.

### 1.4 — Add `dispose()` to All Providers 🐛

**Files:** All 10 providers in `mobile/lib/providers/`

**Issue:** Only `StudentProvider` calls `_api.dispose()`. The other 9 leak HTTP clients on every provider replacement.

**Fix:** Add `@override void dispose() { _api.dispose(); super.dispose(); }` to every provider.

**Acceptance:** `dart analyze` passes. No regressions in any screen.

### 1.5 — Fix TextEditingController Leak in TeacherAcademics 🐛

**File:** `mobile/lib/providers/teacher_academics_provider.dart`

**Issue:** The `_controllers` map caches `TextEditingController` instances for each `(studentId, gradeItemId)` pair but never clears them.

**Fix:** Clear `_controllers` when `loadScores` is called (stale cleanup). Ensure `dispose()` clears the map.

**Acceptance:** No stale controllers exist after data refresh.

### 1.6 — Add Assessment Picker to Teacher Academics 🐛

**File:** `mobile/lib/screens/teacher/teacher_academics_screen.dart`

**Issue:** The score grid uses hardcoded `assessmentId: 1` and `sessionId: 1`. Teachers need to pick which assessment term they're entering scores for.

**Fix:** 
1. Fetch available assessments from `/academic/curriculum`  
2. Fetch current session from `/academic/session`
3. Add a `Row` of `DropdownButton`s above the score grid for assessment + session
4. Pass selected IDs to `_ScoreGrid`

**Acceptance:** Teacher can switch between assessments (e.g. "Mid-Term", "Exam") and sessions before entering scores.

---

## Phase 2 — Quality & Polish

> Improve test coverage, remove code duplication, and add final UX polish.

### 2.1 — Merge Duplicate ResultModel Classes 🧪

**Files:** 
- `mobile/lib/providers/teacher_results_provider.dart` (inline `ResultModel`)
- `mobile/lib/providers/report_results_provider.dart` (if exists, inline)
- `mobile/lib/models/academic_models.dart` (`ResultModel`)

**Issue:** Three nearly identical `ResultModel` classes. Hard to maintain.

**Fix:** Consolidate into a single `ResultModel` in `academic_models.dart`. Update all providers and screens to use the canonical model.

**Acceptance:** Exactly one `ResultModel` class in the codebase. All imports reference `academic_models.dart`.

### 2.2 — Entrance Animations on Onboarding Screen 🎨

**File:** `mobile/lib/screens/shared/onboarding_screen.dart`

**Issue:** Static slides with only `AnimatedContainer` dots. No slide-in animations on content.

**Fix:** Wrap slide content (illustration, title, subtitle) in `EntranceFadeSlide` with staggered delays. Animate the page indicator dots with a spring transition.

**Acceptance:** Each onboarding slide's content animates in sequentially when the page becomes active.

### 2.3 — Widget Tests for Teacher Screens 🧪

**Files:** Create test files for:
- `test/screens/teacher/teacher_dashboard_screen_test.dart`
- `test/screens/teacher/teacher_class_screen_test.dart`
- `test/screens/teacher/teacher_academics_screen_test.dart`
- `test/screens/teacher/teacher_attendance_screen_test.dart`
- `test/screens/teacher/teacher_results_screen_test.dart`

**Pattern:** Each test verifies: shimmer on load → data renders → error state with retry → empty state works.

**Acceptance:** All 5 teacher screens have widget tests. `dart test` passes.

### 2.4 — Widget Tests for Student Screens 🧪

**Files:** Same pattern for 6 student screens.

**Acceptance:** 6 student screens have widget tests.

### 2.5 — Widget Tests for Admin Screens 🧪

**Files:** `more_screen_test.dart`, `person_detail_screen_test.dart`

**Acceptance:** 2 remaining admin screens have widget tests. Login screen test already exists.

### 2.6 — Widget Tests for Shared Screens 🧪

**Files:** `onboarding_gate_test.dart`, `onboarding_screen_test.dart`

**Acceptance:** All 19 screens have widget tests. Coverage ≥ 15% → ≥ 60%.

---

## Phase 3 — Parent Portal

> First major new feature. Backend has 4 ready endpoints. Parents can view child progress, attendance, and fees.

### 3.1 — Parent Models + Provider 🏗️

**Backend routes:**
- `GET /api/v2/parent/dashboard` → `ParentDashboardResponse` with `children []ChildSummary`
- `GET /api/v2/parent/children/:id/progress` → `ChildProgressResponse`
- `GET /api/v2/parent/children/:id/attendance` → `AttendanceResponse`
- `GET /api/v2/parent/children/:id/fees` → `FeeSummaryResponse`

**Create files:**
- `mobile/lib/models/parent_models.dart` — `ChildSummary`, `ChildProgress`, `ParentAttendance`, `ParentFees` with `fromJson`
- `mobile/lib/providers/parent_provider.dart` — `ParentProvider` with:
  - `fetchDashboard(token)` → children list
  - `fetchChildProgress(token, childId)` → progress details
  - `fetchChildAttendance(token, childId)` → attendance data
  - `fetchChildFees(token, childId)` → fee data
  - Standard: loading, error, shimmer triggers

**Acceptance:** Provider fetches all 4 endpoints. Models deserialize correctly. Error states propagate.

### 3.2 — Parent Dashboard Screen 🏗️

**File:** `mobile/lib/screens/parent/parent_dashboard.dart`

**Layout:**
- Greeting: "Welcome, {parent_name}" with `EntranceFadeSlide`
- Children cards (horizontal scroll or stacked): each shows avatar, name, class, current GPA
- Quick stats row: children count, outstanding fees total, overall attendance %
- Each card taps → child detail screen
- Shimmer loading → ErrorStateWidget retry

**Acceptance:** Screen loads children from API. Each child card shows real data. Tapping navigates to child detail.

### 3.3 — Parent Child Progress Screen 🏗️

**File:** `mobile/lib/screens/parent/child_progress_screen.dart`

**Layout:**
- Child info header (name, class, photo)
- Performance summary card: GPA, total/max score, subject count
- Subject list: each row shows subject name, score, grade, colored by performance
- Recent report cards section (list with download button)
- Tab or button row for: Progress | Attendance | Fees
- Shimmer loading → ErrorStateWidget retry
- `EntranceFadeSlide` on sections

**Acceptance:** Shows real progress data from API. Tapping between tabs loads correct data.

### 3.4 — Parent Child Attendance + Fees Tabs 🏗️

**Extend** `child_progress_screen.dart` with tab-based views:

**Attendance tab:**
- Stats card: present / absent / late counts, percentage with color coding
- Maybe a simple bar chart (use `fl_chart` or custom painted)

**Fees tab:**
- Summary: total due, total paid, outstanding balance
- Outstanding items list (if any)
- Last payment date display

**Acceptance:** Both tabs load real data. Attendance shows counts. Fees shows balance.

### 3.5 — Parent Menu Integration 🏗️

**File:** Integration into navigation:
- Add "Parent Portal" to the role-based routing in `onboarding_gate.dart` / `more_screen.dart`
- Parent dashboard accessible from login (after parent role detection)
- Back navigation works: dashboard → child detail → tabs

**Acceptance:** Parent can log in → see dashboard → tap child → see progress/attendance/fees.

---

## Phase 4 — Notifications

> Simple, high-value. Backend has 5 endpoints ready.

### 4.1 — Notifications Provider + Models 🏗️

**Backend routes:**
- `GET /api/v2/notifications` — paginated list
- `GET /api/v2/notifications/unread-count` — count
- `PUT /api/v2/notifications/:id/read` — mark single
- `PUT /api/v2/notifications/read-all` — mark all
- `DELETE /api/v2/notifications/:id` — delete

**Create files:**
- `mobile/lib/models/notification_models.dart` — `AppNotification` with `fromJson`
- `mobile/lib/providers/notification_provider.dart` — `NotificationProvider` with:
  - `fetchNotifications(token)`, `fetchUnreadCount(token)`
  - `markRead(token, id)`, `markAllRead(token)`, `delete(token, id)`
  - Loading/error states per operation

**Acceptance:** Provider loads, marks read, and deletes notifications.

### 4.2 — Notifications List Screen 🏗️

**File:** `mobile/lib/screens/shared/notifications_screen.dart`

**Layout:**
- AppBar with "Mark All Read" action
- List of notification cards: icon (by type), title, message, time, read/unread indicator
- Swipe to delete
- Tap to mark read and navigate (future)
- Empty state: "No notifications yet"
- Shimmer loading → ErrorStateWidget retry
- `EntranceFadeSlide` per item

**Acceptance:** List loads from API. Mark read/delete works. Unread count updates.

### 4.3 — Notification Badge Integration 🏗️

**Integrate** unread count badge into:
- Dashboard app bars (student/teacher/admin)
- More screen notification link
- Poll every 60s or on app resume

**Acceptance:** Badge shows real unread count across all dashboards.

---

## Phase 5 — Messages (Internal Chat)

> Internal messaging between school users. 8 backend endpoints ready.

### 5.1 — Messages Provider + Models 🏗️

**Backend routes:**
- `GET /api/v2/messages` — list messages
- `GET /api/v2/messages/conversations` — conversation threads
- `GET /api/v2/messages/unread-count`
- `POST /api/v2/messages` — send
- `GET /api/v2/messages/:id` — get single
- `PUT /api/v2/messages/:id/read` — mark read
- `PUT /api/v2/messages/:id/star` — toggle star

**Create files:**
- `mobile/lib/models/message_models.dart` — `Message`, `Conversation` with `fromJson`
- `mobile/lib/providers/message_provider.dart` — `MessageProvider` with conversation list, message list, send, mark read

**Acceptance:** Provider fetches conversations and messages. Send works.

### 5.2 — Messages List + Conversation Screen 🏗️

**File:** `mobile/lib/screens/shared/messages_screen.dart`

**Layout:**
- Conversations list: avatar, name, last message preview, time, unread badge
- Tap → opens conversation detail
- Compose FAB → new message screen
- Empty state: "No conversations yet"
- Shimmer loading → ErrorStateWidget retry
- `EntranceFadeSlide` per item

**Acceptance:** Conversations load from API. Unread count shown.

### 5.3 — Conversation Detail + Compose Screen 🏗️

**Files:**
- `mobile/lib/screens/shared/conversation_detail_screen.dart` — message thread with bubble UI, send input
- `mobile/lib/screens/shared/compose_message_screen.dart` — recipient picker, subject, body

**Layout (Conversation Detail):**
- Message bubbles (sent/received styling)
- Text input at bottom with send button
- Auto-scroll to bottom
- Mark messages as read on open

**Layout (Compose):**
- User search/select for recipients
- Subject field
- Body text area
- Send button → pop back to conversation list

**Acceptance:** Send message → appears in conversation. New conversations auto-create.

---

## Phase 6 — Library

> Book catalog + issue/return tracking. 7 backend endpoints ready.

### 6.1 — Library Provider + Models 🏗️

**Backend routes:**
- `GET/POST /api/v2/library/books` — list/create books
- `GET/PUT/DELETE /api/v2/library/books/:id` — book CRUD
- `GET/POST /api/v2/library/issues` — list/create issues
- `POST /api/v2/library/issues/:id/return` — return book

**Create files:**
- `mobile/lib/models/library_models.dart` — `Book`, `BookIssue` with `fromJson`
- `mobile/lib/providers/library_provider.dart` — `LibraryProvider` with:
  - `fetchBooks(token)`, `fetchIssues(token)`
  - `createIssue(token, bookId, studentId, dueDate)`
  - `returnBook(token, issueId)`

**Acceptance:** Provider lists books and issues. Create/return operations work.

### 6.2 — Book Catalog Screen 🏗️

**File:** `mobile/lib/screens/admin/library/book_catalog_screen.dart`

**Layout:**
- Search bar at top
- Filter chips: by category
- Book cards: cover image, title, author, ISBN, available/total quantity
- Tap → book detail
- Empty state: "No books found"
- Shimmer loading → ErrorStateWidget retry
- `EntranceFadeSlide` per card

**Acceptance:** Books load from API. Search filters work.

### 6.3 — Book Issues + Librarian Dashboard 🏗️

**File:** `mobile/lib/screens/admin/library/issues_screen.dart`

**Layout:**
- Current issues list: book title, student name, issue date, due date, overdue indicator
- "Issue Book" FAB → issue form (student picker + book picker + due date)
- Return action (swipe or button)
- Stats header: total books, issued, overdue count
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Issues list loads. Issue/return flow works.

---

## Phase 7 — Hostel Management

> Hostel + bed assignment tracking. 7 backend endpoints ready.

### 7.1 — Hostel Provider + Models 🏗️

**Backend routes:**
- `GET/POST /api/v2/hostels` — list/create hostels
- `GET/PUT/DELETE /api/v2/hostels/:id` — hostel CRUD
- `GET /api/v2/hostels/beds` — list beds
- `POST /api/v2/hostels/beds/assign` — assign bed
- `POST /api/v2/hostels/beds/:id/unassign` — unassign bed

**Create files:**
- `mobile/lib/models/hostel_models.dart` — `Hostel`, `Bed` with `fromJson`
- `mobile/lib/providers/hostel_provider.dart` — `HostelProvider` with CRUD + assign/unassign

**Acceptance:** Provider lists hostels and beds. Assignment works.

### 7.2 — Hostel List + Bed Management Screen 🏗️

**File:** `mobile/lib/screens/admin/hostel/hostel_screen.dart`

**Layout:**
- Hostel cards: name, type (boys/girls/mixed), capacity, occupied count, occupancy progress bar
- Tap → bed detail view
- "Add Hostel" FAB
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Hostels list loads. Occupancy shown.

### 7.3 — Bed Assignment Screen 🏗️

**File:** `mobile/lib/screens/admin/hostel/bed_assignment_screen.dart`

**Layout:**
- Grid or list of beds: room number, bed number, student name (or empty), status color
- Tap empty bed → assign form (student search/select)
- Tap occupied bed → option to unassign
- Unassign confirmation dialog

**Acceptance:** Beds display with status. Assign/unassign flow works.

---

## Phase 8 — Transport Management

> Routes, vehicles, and student assignments. 9 backend endpoints ready.

### 8.1 — Transport Provider + Models 🏗️

**Backend routes:**
- `GET/POST /api/v2/transport/routes` — CRUD routes
- `GET/PUT/DELETE /api/v2/transport/routes/:id`
- `GET/POST /api/v2/transport/vehicles` — CRUD vehicles
- `GET/POST /api/v2/transport/assignments` — list/create assignments
- `PUT /api/v2/transport/assignments/:id` — update

**Create files:**
- `mobile/lib/models/transport_models.dart` — `Route`, `Vehicle`, `Assignment` with `fromJson`
- `mobile/lib/providers/transport_provider.dart` — `TransportProvider`

**Acceptance:** Provider lists routes, vehicles, and assignments.

### 8.2 — Routes + Vehicles Screen 🏗️

**File:** `mobile/lib/screens/admin/transport/transport_screen.dart`

**Layout (two tabs):**
- **Routes tab:** route cards (name, area, distance, fare, vehicle count). Tap → detail/edit.
- **Vehicles tab:** vehicle cards (plate number, model, capacity, driver name). Tap → detail/edit.
- FAB for create on each tab
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Both tabs load data. Create/edit works.

### 8.3 — Student Assignment Screen 🏗️

**File:** `mobile/lib/screens/admin/transport/assignment_screen.dart`

**Layout:**
- Assignments list: route name, vehicle plate, student name, pickup point, status
- "New Assignment" FAB → form (student + route + vehicle + pickup point pickers)
- Filter by route
- Empty state + shimmer + error

**Acceptance:** Assignments list loads. Create assignment works.

---

## Phase 9 — Inventory Management

> Asset tracking with categories, assignments, maintenance. 12 backend endpoints ready.

### 9.1 — Inventory Provider + Models 🏗️

**Backend routes:**
- Category CRUD: `GET/POST /categories`, `PUT/DELETE /categories/:id`
- Asset CRUD: `GET/POST /assets`, `GET/PUT/DELETE /assets/:id`
- Assignments: `GET/POST /assignments`, `POST /assignments/:id/return`
- Maintenance: `GET/POST /assets/:id/maintenance`

**Create files:**
- `mobile/lib/models/inventory_models.dart` — `Asset`, `Assignment`, `MaintenanceRecord`
- `mobile/lib/providers/inventory_provider.dart` — `InventoryProvider`

**Acceptance:** Provider lists assets with category names. Assignment lifecycle works.

### 9.2 — Asset List + Detail Screen 🏗️

**File:** `mobile/lib/screens/admin/inventory/asset_screen.dart`

**Layout:**
- Filter: category dropdown, status chips (available/assigned/maintenance/retired)
- Asset cards: name, serial number, category, status chip, current value
- Tap → asset detail (full info + assignment history + maintenance log)
- "Add Asset" FAB
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Assets load with filtering. Detail screen shows full history.

### 9.3 — Assign + Return Flow 🏗️

**Extend** asset detail with action buttons:
- "Assign" → user picker + expected return date
- "Return" → confirmation (if currently assigned)
- Maintenance log section with "Add Maintenance" form

**Acceptance:** Assign/return flow creates records. Maintenance entries log correctly.

---

## Phase 10 — Discipline Management

> Behavior incidents, detentions, suspensions, conduct records. 13 endpoints.

### 10.1 — Discipline Provider + Models 🏗️

**Backend routes:** incidents CRUD, detentions CRUD with status, suspensions CRUD, conduct records, analytics/stats.

**Create:**
- Models: `Incident`, `Detention`, `Suspension`, `ConductRecord`
- Provider: `DisciplineProvider` with all CRUD operations

**Acceptance:** Provider loads incidents, detentions, suspensions, and stats.

### 10.2 — Incidents List + Create Screen 🏗️

**File:** `mobile/lib/screens/admin/discipline/incidents_screen.dart`

**Layout:**
- Filter chips: severity (mild/moderate/severe/critical), category, status
- Incident cards: student name, category, severity badge, date, status
- Tap → incident detail (full info, resolution notes, action taken)
- "Report Incident" FAB → form (student picker, category, severity, location, description)
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Incidents load with filtering. New incident creation works.

### 10.3 — Detention + Suspension Management 🏗️

**File:** `mobile/lib/screens/admin/discipline/disciplinary_actions_screen.dart`

**Tabs:**
- **Detentions:** list with assigned date, time, location, supervisor, status. Create/complete flow.
- **Suspensions:** list with type (in/out-of-school), date range, reason, status. Approve/complete flow.

**Acceptance:** Both tabs show real data. Status transitions work.

### 10.4 — Conduct Dashboard 🏗️

**File:** `mobile/lib/screens/admin/discipline/conduct_screen.dart`

**Layout:**
- Stats cards: total incidents, active detentions, active suspensions, monthly trend
- Student conduct search: search by name → shows full conduct record
- Conduct record: total incidents/detentions/suspensions, conduct grade, remarks
- Empty state + shimmer + error

**Acceptance:** Stats load. Student conduct records are searchable.

---

## Phase 11 — Student Health

> Medical records, immunizations, allergies, medications, nurse visits. 19 endpoints.

### 11.1 — Health Provider + Models 🏗️

**Models:** `HealthRecord`, `Immunization`, `AllergyAlert`, `MedicationLog`, `NurseVisit`
**Provider:** `StudentHealthProvider`

**Acceptance:** Provider reads/writes all health data types.

### 11.2 — Student Health Record Screen 🏗️

**File:** `mobile/lib/screens/admin/student_health/health_record_screen.dart`

**Layout:**
- Student search/select at top
- Health summary card: blood group, genotype, BMI, vision/hearing
- Tabbed view: Immunizations | Allergies | Medications | Visits
- Immunizations: list with vaccine name, dose, date, next due date
- Allergies: list with allergen, severity, reaction
- Medications: list with dosage, frequency, administered by
- Visits: list with date, symptoms, diagnosis, treatment
- Edit FAB for health record
- Empty state per tab + shimmer + error
- `EntranceFadeSlide` per section

**Acceptance:** All tabs load real data. Record editing works.

### 11.3 — Nurse Visit Check-in Flow 🏗️

**File:** `mobile/lib/screens/admin/student_health/nurse_checkin_screen.dart`

**Layout:**
- Quick student search
- Check-in form: symptoms, notes
- Auto-links to student record
- Visit history below

**Acceptance:** Nurse can check in a student, creating a visit record.

---

## Phase 12 — Exam Schedule Management

> Exam scheduling + results aggregation. 10 backend endpoints.

### 12.1 — Exam Provider + Models 🏗️

**Models:** `ExamSchedule`, `ExamResult`
**Provider:** `ExamProvider`

### 12.2 — Exam Schedule Screen 🏗️

**File:** `mobile/lib/screens/admin/exam/exam_schedule_screen.dart`

**Layout:**
- Calendar or list view of exams: class, subject, date, time, venue, duration, total marks
- Filter by class or month
- "Create Exam" FAB → form (title, class, subject, date/time, venue, marks)
- Tap → detail/edit
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Schedule loads. Create/edit works.

### 12.3 — Exam Results Screen 🏗️

**File:** `mobile/lib/screens/admin/exam/exam_results_screen.dart`

**Layout:**
- Select exam → results view
- Results card: total students, avg score, highest, lowest
- Student list with individual scores
- Publish toggle

**Acceptance:** Results show for selected exam. Publish works.

---

## Phase 13 — External Exam (WAEC/NECO) Management

> External exam results tracking + CSV import. 8 endpoints.

### 13.1 — External Exam Provider + Models 🏗️

**Models:** `ExternalExamResult`
**Provider:** `ExternalExamProvider`

### 13.2 — External Exam Results Screen 🏗️

**File:** `mobile/lib/screens/admin/external_exam/external_exam_screen.dart`

**Layout:**
- Filter: exam type (WAEC/NECO), session
- Result cards: admission number, subject, grade, credit flag
- Best results section: top 6 credit subjects
- Credit count display
- "Import CSV" button → file picker → preview → confirm
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Results load. CSV import flow works.

---

## Phase 14 — Computer-Based Assessment (CBA)

> Full exam engine: question bank, paper composition, live exam, auto-grading, proctoring. 28 endpoints.

### 14.1 — CBA Provider + Models 🏗️

**Models:** `CBAQuestion`, `CBAPaper`, `CBAExamSession`, `ProctoringEvent`
**Provider:** `CBAProvider`

### 14.2 — Question Bank Screen 🏗️

**File:** `mobile/lib/screens/admin/cba/question_bank_screen.dart`

**Layout:**
- Filter: category, difficulty, type (objective/subjective)
- Question cards: question text preview, type, difficulty badge, category
- Tap → full question edit
- "Add Question" FAB → form with question, options (for objective), answer, category, difficulty
- Categories and tags management section
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Question bank loads. CRUD works.

### 14.3 — Paper Composer Screen 🏗️

**File:** `mobile/lib/screens/admin/cba/paper_composer_screen.dart`

**Layout:**
- Paper list: title, description, time limit, pass mark
- Tap → paper detail with question list
- "Add Question" from bank (search/add by ID)
- Reorder questions (drag handle)
- Shuffle toggle, show results toggle
- Preview mode
- "Create Paper" FAB

**Acceptance:** Papers created with associated questions. Preview works.

### 14.4 — Student Exam Player Screen 🏗️

**File:** `mobile/lib/screens/student/exam_player_screen.dart`

**Layout:**
- Full-screen exam mode
- Timer countdown at top
- Question navigation sidebar (numbered grid)
- Current question card with options (objective) or text area (subjective)
- Question flag/bookmark for review
- Auto-save on answer
- Submit button with confirmation dialog
- Pause/resume support

**Acceptance:** Student can take exam, navigate questions, submit. Timer works.

### 14.5 — Proctoring Dashboard 🏗️

**File:** `mobile/lib/screens/admin/cba/proctoring_dashboard.dart`

**Layout:**
- Active exams list
- Per-exam: student list with proctoring status (OK/suspicious/flagged)
- Event log per student: timestamps, captured images, suspicious activity
- Review workflow: mark event as reviewed, dismiss, escalate
- Empty state + shimmer + auto-refresh

**Acceptance:** Proctoring events display. Review workflow works.

---

## Phase 15 — LMS (Learning Management System)

> Courses, modules, lessons, assignments, submissions, discussions. 24 endpoints.

### 15.1 — LMS Provider + Models 🏗️

**Models:** `LMSCourse`, `LMSModule`, `LMSLesson`, `LMSAssignment`, `Submission`, `DiscussionThread`
**Provider:** `LMSProvider`

### 15.2 — Course Catalog Screen 🏗️

**File:** `mobile/lib/screens/student/lms/course_catalog_screen.dart`

**Layout:**
- Course cards: name, code, subject, teacher, progress %, enrollment status
- Filter by subject or level
- "Enroll" button on unenrolled courses
- Tap → course detail
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Courses load. Enrollment works.

### 15.3 — Course Detail + Lesson Viewer 🏗️

**Files:**
- `course_detail_screen.dart` — module/lesson tree, progress per lesson, assignment list
- `lesson_viewer_screen.dart` — content display (text, video URL, embedded CBA), mark complete

**Layout (Course Detail):**
- Header: course name, teacher, progress bar
- Expandable module sections
- Lesson rows with completion checkmarks
- Assignment section with due dates

**Layout (Lesson Viewer):**
- Content display area
- "Mark Complete" button
- Link to CBA quiz if associated

### 15.4 — Assignment Submission + Grading 🏗️

**Files:**
- `assignments_screen.dart` — student assignment list with status/due dates
- `submission_screen.dart` — submit work (text/file upload)
- `grading_screen.dart` (teacher) — view submissions, enter scores/feedback

**Acceptance:** Student can view and submit assignments. Teacher can grade.

### 15.5 — Discussion Screen 🏗️

**File:** `mobile/lib/screens/student/lms/discussion_screen.dart`

**Layout:**
- Thread list per course
- Create thread (title, content)
- Post replies
- Empty state + shimmer

**Acceptance:** Discussions load per course. Create/post works.

---

## Phase 16 — Admissions Portal

> Full admissions lifecycle. 34 endpoints (28 admin + 6 public). Largest module.

### 16.1 — Admissions Provider + Models 🏗️

**Models:** `Intake`, `Application`, `AdmissionDocument`, `FormConfig`, `FormField`
**Provider:** `AdmissionsProvider` (admin) + `PublicAdmissionsProvider` (public)

### 16.2 — Intake Management Screen 🏗️

**File:** `mobile/lib/screens/admin/admissions/intake_screen.dart`

**Layout:**
- Intake cards: name, session, date range, status (draft/active/closed), application count
- Status badge with color coding
- "Create Intake" FAB → form (name, session, dates, max applications, link to form + CBA paper)
- Tap → intake detail with applications list
- Activate/close actions
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Intakes CRUD works. Status transitions work.

### 16.3 — Application Review Screen 🏗️

**File:** `mobile/lib/screens/admin/admissions/application_review_screen.dart`

**Layout:**
- Filter: status (submitted/screened/offered/accepted/declined/enrolled), intake
- Application cards: reference number, applicant name, email, status, date
- Tap → full application detail (all sections)
- Decision buttons: Screen → Offer → Accept/Decline
- AI score display (if scored)
- Document verification section
- Offer creation form (provisional/firm)
- Empty state + shimmer + error

**Acceptance:** Applications list loads by intake. Decision workflow works.

### 16.4 — Public Application Form 🏗️

**File:** `mobile/lib/screens/public/apply_screen.dart`

**Layout (multi-step wizard):**
- Step 1: Select intake (from available)
- Step 2: Fill form (dynamically rendered from form config)
- Step 3: Upload documents
- Step 4: Review + submit
- Reference number display after submit
- Track application: enter reference → see status

**Acceptance:** Public user can submit an application. Tracking works with reference number.

### 16.5 — Form Builder Screen 🏗️

**File:** `mobile/lib/screens/admin/admissions/form_builder_screen.dart`

**Layout:**
- Form list: name, slug, field count
- Tap → form editor with drag-reorderable fields
- Add field: type picker (text/email/number/date/select/radio/textarea/file/phone/checkbox), label, required, options, validation
- Preview mode
- Empty state + shimmer

**Acceptance:** Forms CRUD works. Field types and validation configurable.

---

## Phase 17 — Finance & Accounting

> Full double-entry accounting + fee management. 26 endpoints. Second-most complex.

### 17.1 — Finance Provider + Models 🏗️

**Models:** `Account`, `JournalEntry`, `Budget`, `Expense`, `Vendor`, `FeeItem`, `FeeStructure`, `DebtorSummary`
**Provider:** `FinanceProvider`

### 17.2 — Chart of Accounts Screen 🏗️

**File:** `mobile/lib/screens/admin/finance/accounts_screen.dart`

**Layout:**
- Hierarchical account tree (expandable): grouped by type (asset/liability/equity/income/expense)
- Each account: code, name, type, current balance
- "Add Account" FAB → form (code, name, type, parent account)
- Tap → account detail with journal entries
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Account tree loads. Create/edit works.

### 17.3 — Journal Entry Screen 🏗️

**File:** `mobile/lib/screens/admin/finance/journal_screen.dart`

**Layout:**
- Journal entries list: date, reference, type, total debit/credit, status
- Filter by date range
- "New Entry" FAB → double-entry form with minimum 2 lines
- Each line: account picker, debit/credit amount
- Auto-validation: debits must equal credits
- Post button → changes status to posted
- Empty state + shimmer + error

**Acceptance:** Journal entries list loads. New entry validates double-entry rule.

### 17.4 — Fee Management Screen 🏗️

**File:** `mobile/lib/screens/admin/finance/fee_screen.dart`

**Tabs:**
- **Fee Items:** list of fee types (tuition, sports, lab, etc.) with amount
- **Fee Structures:** fee item combinations with level/class assignments
- **Fee Waivers:** discounts/exemptions per student

**Acceptance:** Fee configuration CRUD works.

### 17.5 — Debtors + Payment Allocation 🏗️

**File:** `mobile/lib/screens/admin/finance/debtors_screen.dart`

**Layout:**
- Debtor list: student name, total due, total paid, balance, parent contact
- Tap → debtor detail with per-fee-item breakdown
- "Send Reminders" button
- Payment allocation: record payment, split across fee structures
- Empty state + shimmer + error

**Acceptance:** Debtors list shows real balances. Payment recording works.

### 17.6 — Budget + Expense Management 🏗️

**File:** `mobile/lib/screens/admin/finance/budget_screen.dart`

**Tabs:**
- **Budgets:** list with title, fiscal year, total amount, spent amount, progress bar
- **Expenses:** list with budget, account, amount, date, status (pending/approved/paid)
- Approval workflow: approve/reject expenses
- "Create Budget" / "Create Expense" FABs

**Acceptance:** Budget/expense CRUD works. Approval workflow works.

---

## Phase 18 — HR & Payroll

> Staff management, leaves, payroll, attendance, appraisals, recruitment. 33 endpoints.

### 18.1 — HR Provider + Models 🏗️

**Models:** `Staff`, `Department`, `Leave`, `Payslip`, `PayrollPeriod`, `StaffAttendance`, `Appraisal`, `Recruitment`
**Provider:** `HRProvider`

### 18.2 — Staff Directory + Detail Screen 🏗️

**File:** `mobile/lib/screens/admin/hr/staff_screen.dart`

**Layout:**
- Search bar + filter by department/status
- Staff cards: name, employee ID, department, job title, status badge
- Tap → staff detail: personal info, employment details, bank info, documents, leave balance
- "Add Staff" FAB → form
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Staff list loads. Detail shows all info. CRUD works.

### 18.3 — Leave Management Screen 🏗️

**File:** `mobile/lib/screens/admin/hr/leave_screen.dart`

**Layout:**
- Filter by status (pending/approved/rejected) and staff
- Leave cards: staff name, leave type, dates, duration, status
- Tap → leave detail with approve/reject buttons
- "Apply Leave" FAB (for staff self-service)
- Calendar view option
- Empty state + shimmer + error
- `EntranceFadeSlide` per item

**Acceptance:** Leaves list loads. Approve/reject workflow works.

### 18.4 — Payroll Screen 🏗️

**File:** `mobile/lib/screens/admin/hr/payroll_screen.dart`

**Tabs:**
- **Payroll Periods:** list with name, status (open/closed), close action
- **Payslips:** list by period, staff name, basic salary, allowances, deductions, net pay
- "Generate Payslips" batch button
- "Mark Paid" per payslip
- Empty state + shimmer + error

**Acceptance:** Payroll periods list loads. Batch payslip generation works.

### 18.5 — Staff Attendance + Appraisals 🏗️

**Files:**
- `attendance_screen.dart` — daily attendance log with clock in/out, summary
- `appraisal_screen.dart` — appraisal list by period, rating, comments, goals

**Acceptance:** Attendance shows real data. Appraisals CRUD works.

### 18.6 — Recruitment Screen 🏗️

**File:** `mobile/lib/screens/admin/hr/recruitment_screen.dart`

**Layout:**
- Job posting cards: title, department, type, position count, status (draft/published/closed)
- "Create Posting" FAB → form
- Publish/close actions
- Empty state + shimmer + error

**Acceptance:** Recruitment postings CRUD with publish/close workflow.

---

## Phase 19 — Alumni & Career

> Alumni profiles, events, mentorships, fundraising, job board. 26+ endpoints.

### 19.1 — Alumni Provider + Models 🏗️

**Models:** `AlumniProfile`, `AlumniEvent`, `Mentorship`, `Donation`, `Job`
**Provider:** `AlumniProvider`

### 19.2 — Alumni Directory Screen 🏗️

**File:** `mobile/lib/screens/admin/alumni/alumni_screen.dart`

**Layout:**
- Searchable alumni list: name, graduation year, current career, location
- Filter by graduation year/career
- Tap → alumni detail (full profile, career history)
- Empty state + shimmer + error
- `EntranceFadeSlide` per card

**Acceptance:** Alumni directory loads. Profile detail works.

### 19.3 — Events + Mentorships Screen 🏗️

**File:** `mobile/lib/screens/admin/alumni/events_screen.dart` (two tabs)

**Events tab:**
- Event cards: title, date, attendees count
- "Create Event" FAB → form with registration management
- Attendee list with attendance tracking

**Mentorships tab:**
- Mentorship pairs: mentor, mentee, status, start date
- "Create Mentorship" FAB
- Status tracking

**Acceptance:** Events and mentorships CRUD works.

### 19.4 — Fundraising + Job Board Screen 🏗️

**Files:**
- `fundraising_screen.dart` — campaigns with donation progress bars, donation list
- `job_board_screen.dart` — job listings with search, apply link

**Acceptance:** Campaigns and job board load.

---

## Phase 20 — Additional Modules

> Smaller modules: forum, conference, pastoral care, external exams, timetable builder.

### 20.1 — Forum Screen 🏗️

**File:** `mobile/lib/screens/student/forum_screen.dart`

**Features:**
- Forum list by type (school/class/subject)
- Posts with reactions, comments, polls
- Create post, comment, react
- Moderation: report, pin, lock
- Empty state + shimmer + error

### 20.2 — Parent-Teacher Conference Screen 🏗️

**File:** `mobile/lib/screens/parent/conference_screen.dart`

**Features:**
- List available conferences
- View teacher time slots
- Book a slot
- Cancel booking
- Teacher view: create slots, view bookings

### 20.3 — Pastoral Care Screen 🏗️

**File:** `mobile/lib/screens/admin/pastoral/pastoral_screen.dart`

**Features:**
- Wellness surveys: create, publish, close, view responses
- Wellness alerts: view, assign, resolve
- Counseling sessions: schedule, log, track

### 20.4 — Timetable Builder (Admin) 🏗️

**File:** `mobile/lib/screens/admin/timetable/timetable_builder_screen.dart`

**Features:**
- Visual timetable grid (days × periods)
- Drag lesson to slot
- Create/edit slot: subject, teacher, time, location
- Bulk create from template
- Break entries
- iCal export button

---

## Phase 21 — Reports & Analytics

> Dashboard overview, trends, executive summaries, report cards.

### 21.1 — Analytics Provider + Models 🏗️

**Models:** `DashboardOverview`, `EnrollmentTrend`, `RevenueData`, `AcademicPerformance`
**Provider:** `AnalyticsProvider`

### 21.2 — Analytics Dashboard Screen 🏗️

**File:** `mobile/lib/screens/admin/analytics/analytics_screen.dart`

**Layout (tabbed or scrollable):**
- **Overview:** enrollment count, revenue, academic average, attendance rate (4 stat cards)
- **Enrollment:** trend chart (daily new, total active, by class), direction indicator
- **Revenue:** daily collections chart, total revenue, outstanding, by fee type
- **Academic:** subject performance chart, class averages
- **Attendance:** daily rates chart, overall rate, by class
- Use `fl_chart` for line/bar charts
- "Generate Summary" AI button
- Empty state + shimmer + error
- `EntranceFadeSlide` per section

**Acceptance:** All 4 dashboard sections load real data. Charts render.

### 21.3 — Report Card Management Screen 🏗️

**File:** `mobile/lib/screens/admin/reports/report_card_screen.dart`

**Features:**
- List report cards by class/session/term
- Generate single or batch
- View with subject scores, GPA, conduct grade, comments
- Add teacher/principal comments
- Publish/unpublish
- Template customization (colors, logo, signature)
- PDF download/preview

**Acceptance:** Report cards generate and display. Template customization works.

---

## Phase 22 — Security & Infrastructure

> Fix backend gaps: RBAC, AI wiring, CSRF, API hardening.

### 22.1 — Implement RBAC Middleware 🔧🔒

**Files:** `backend/internal/modules/rbac/` — wire up handler + routes

**Tasks:**
- Create `rbac/handler.go` with CRUD endpoints for roles and permissions
- Create `rbac/dto.go` with request/response types
- Create `rbac/repository.go` to persist roles/permissions
- Register routes in `router.go`
- Create middleware that checks role/permission per route
- Apply to sensitive routes (finance, HR, admissions)

**Acceptance:** Roles and permissions CRUD works. Middleware blocks unauthorized access.

### 22.2 — Wire Up AI Module 🔧

**Files:** `backend/internal/modules/ai/`, `backend/router.go`

**Tasks:**
- Fix DI container to create `aiHandler` when `cfg.AI.Enabled` is true
- Remove dead `if aiHandler != nil` guard or fix the condition
- Configure AI provider at startup
- Verify `/api/v2/ai/chat`, `/agents`, `/search` respond

**Acceptance:** AI endpoints respond with real agent responses (not nil handler).

### 22.3 — CSRF Token Management 🔒

**File:** `mobile/lib/services/api_client.dart`

**Tasks:**
- Add CSRF token fetch on login
- Store token in provider
- Send CSRF header on all mutation requests (POST/PUT/DELETE)
- Handle 403 CSRF failure → re-fetch token → retry

**Acceptance:** All mutations include CSRF header. Token refresh works on 403.

### 22.4 — API Client Hardening 🔒

**File:** `mobile/lib/services/api_client.dart`

**Tasks:**
- Add request timeout (default 30s)
- Add retry logic for 5xx errors (max 2 retries)
- Add request/response logging in debug mode
- Standardize error parsing (unwrap API error messages)

**Acceptance:** Timeout, retry, and logging work.

---

## Phase 23 — Final Integration & Testing

> End-to-end verification, performance, and deployment readiness.

### 23.1 — Full E2E Flow Test 🧪

**Tasks:**
- Test complete auth flow: login → role-based dashboard → data loading
- Test parent flow: login → children → progress/attendance/fees
- Test admin flow: all management screens data loading
- Test teacher flow: classes, scores, attendance entry
- Test student flow: results, timetable, fees

### 23.2 — Performance Optimization 🎨

**Tasks:**
- Audit list performance: ensure all lists use `itemExtent` or are virtualized
- Check for unnecessary rebuilds: memoize widgets, use `const` where possible
- Image loading: add caching (cached_network_image)
- Shimmer placeholder optimization

### 23.3 — Production Readiness Audit 🔒

**Tasks:**
- Verify all API calls have proper error handling
- Verify all user-facing text is correct
- Verify navigation back-stack behaves correctly
- Verify all forms validate before submit
- Verify theme consistency across all screens
- Check for any debug prints/stubs remaining

---

## Effort Summary

| Phase | Description | Est. Hours | Sub-phases |
|-------|-------------|-----------|------------|
| 1 | Bug Fixes | 6 | 6 |
| 2 | Quality & Polish | 24 | 6 |
| 3 | Parent Portal | 16 | 5 |
| 4 | Notifications | 8 | 3 |
| 5 | Messages | 12 | 3 |
| 6 | Library | 10 | 3 |
| 7 | Hostel | 10 | 3 |
| 8 | Transport | 10 | 3 |
| 9 | Inventory | 10 | 3 |
| 10 | Discipline | 14 | 4 |
| 11 | Student Health | 10 | 3 |
| 12 | Exam Schedule | 8 | 3 |
| 13 | External Exam | 6 | 2 |
| 14 | CBA (Exam Engine) | 24 | 5 |
| 15 | LMS | 24 | 5 |
| 16 | Admissions Portal | 28 | 5 |
| 17 | Finance & Accounting | 28 | 6 |
| 18 | HR & Payroll | 28 | 6 |
| 19 | Alumni & Career | 18 | 4 |
| 20 | Additional Modules | 16 | 4 |
| 21 | Reports & Analytics | 16 | 3 |
| 22 | Security & Infrastructure | 12 | 4 |
| 23 | Final Integration | 16 | 3 |
| **Total** | | **~362 hours** | **85 sub-phases** |

**Realistic timeline (assuming 4h/day focused): ~90 working days**

---

## Recommended Execution Order

```
Phase 1 (Bugs) ─────────────────────────────── Always first
     │
Phase 2 (Quality/Polish) ───────────────────── Second (foundation)
     │
     ├── Phase 3 (Parent Portal) ────────────── Highest user value
     ├── Phase 4 (Notifications) ────────────── Quick win, affects all users
     ├── Phase 5 (Messages) ─────────────────── Internal communication
     │
     ├── Phase 6-11 (Library/Hostel/Transport/
     │   Inventory/Discipline/Health) ───────── Medium modules, can parallelize
     │
     ├── Phase 12-15 (Exam/CBA/LMS) ────────── Academic core
     │
     ├── Phase 16 (Admissions) ──────────────── Biggest module
     ├── Phase 17 (Finance) ─────────────────── Second biggest
     ├── Phase 18 (HR/Payroll) ──────────────── Third biggest
     │
     ├── Phase 19-20 (Alumni/Additional) ────── Nice-to-have
     ├── Phase 21 (Reports/Analytics) ───────── Views data from other phases
     │
     ├── Phase 22 (Security) ────────────────── Can parallelize, needed for prod
     └── Phase 23 (Final Integration) ───────── Always last
```

Each phase builds on the quality patterns established earlier (shimmer, error/empty states, entrance animations) and uses the same provider architecture. There is no architectural innovation needed — just consistent application of the established patterns.
