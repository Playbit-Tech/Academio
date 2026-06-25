# SchoolCare v3 — Detailed Use Cases & Actor Definitions

---

## 1. ACTORS & PERSONAS

| Actor | Description | Key Goals |
|-------|-------------|-----------|
| **Super Admin** | SchoolCare operations staff | System monitoring, tenant management, billing, support |
| **School Admin** | School principal/administrator | Full school management, reports, configuration |
| **Teacher** | Classroom teacher | Mark attendance, grade entry, lesson planning, CBA creation |
| **Student** | Enrolled student | View schedule, results, take exams, AI tutoring |
| **Parent/Guardian** | Student's parent/guardian | Monitor child's progress, fees, communicate |
| **Accountant** | School finance staff | Fee management, payments, financial reports |
| **Librarian** | Library staff | Book management, borrowing, returns |
| **Admissions Officer** | Admissions staff | Process applications, screening, offers |
| **Counselor** | Guidance counselor | Career guidance, student support, interventions |
| **HR Manager** | School HR | Staff records, payroll, leave management |
| **Transport Manager** | Transport coordinator | Bus routes, driver management, trip tracking |
| **Hostel Manager** | Boarding house manager | Room allocation, bed management, billing |
| **Alumni** | Former student | Alumni network, events, donations, career services |
| **Applicant** | Prospective student | Apply for admission, upload docs, check status |
| **System** | Automated processes | Scheduled jobs, AI agents, event handlers |

---

## 2. DETAILED USE CASES

### UC-1: Online Admission
```
Actor: Applicant (Prospective Student/Parent)
Precondition: Intake is open
Flow:
  1. Applicant browses available programs/intakes
  2. Fills application form (personal info, previous school, program)
  3. Uploads required documents (photo, birth cert, transcripts)
  4. Submits application
  5. System sends confirmation email/SMS
  6. Applicant can track application status via portal
Postcondition: Application is in "submitted" status

AI Extension:
  - AI scores application automatically
  - AI checks eligibility based on previous grades
  - AI sends personalized follow-up if incomplete > 48hrs
```

### UC-2: Application Screening
```
Actor: Admissions Officer
Precondition: Application is "submitted"
Flow:
  1. Admissions Officer views application queue
  2. Reviews application details and documents
  3. Verifies document authenticity
  4. Records screening score/decision
  5. Marks as "pass" → moves to exam phase
  6. Marks as "fail" → sends rejection notification
Postcondition: Application is "screening" → "exam" or "rejected"

AI Extension:
  - AI pre-screens applications and highlights anomalies
  - AI suggests screening decision with confidence score
  - AI detects fraudulent documents (image analysis)
```

### UC-3: Entrance Examination
```
Actor: Applicant
Precondition: Application passed screening
Flow:
  1. System schedules entrance exam date
  2. Applicant receives exam invitation with instructions
  3. Applicant logs into CBA portal at scheduled time
  4. System starts proctoring (optional: webcam)
  5. Applicant answers questions (MCQ, essay)
  6. System auto-grades MCQ, flags essays for review
  7. Results added to application record
Postcondition: Entrance exam score is recorded

AI Extension:
  - AI generates entrance exam from question bank
  - AI detects cheating behavior (tab switches, face tracking)
  - AI assists in essay grading
```

### UC-4: Admission Offer & Acceptance
```
Actor: Admissions Officer / Applicant
Precondition: Application has exam/assessment scores
Flow:
  1. System computes aggregate score
  2. Admissions Officer creates offer (conditional/unconditional)
  3. Offer sent to applicant (email, SMS, portal)
  4. Applicant reviews offer, terms, and fees
  5. Applicant accepts/declines offer
  6. If accepted: system generates enrollment checklist
  7. Student record created upon enrollment
Postcondition: Applicant becomes Student

AI Extension:
  - AI predicts acceptance probability
  - AI recommends offer type based on profile
  - AI automates offer letter generation
  - AI forecasts enrollment yield
```

### UC-5: Take Computer-Based Assessment (CBA)
```
Actor: Student
Precondition: Exam is published and within time window
Flow:
  1. Student logs into CBA from dashboard
  2. System verifies identity (biometric/credentials)
  3. Displays exam instructions and rules
  4. Student starts timed exam
  5. Questions displayed one-at-a-time or scrollable
  6. Options shuffled (anti-cheating)
  7. Student navigates questions, flags for review
  8. Auto-save every 30 seconds
  9. Student submits when done (or time expires)
  10. MCQ graded instantly; essays queued for evaluation
  11. Results displayed if allowed by configuration
Postcondition: Exam is completed, pending grading

AI Extension:
  - AI detects unusual patterns (copy-paste, rapid answering)
  - AI proctoring: face detection, multiple faces, object detection
  - AI generates personalized feedback per question
```

### UC-6: Teacher Grades Essays with AI Assistance
```
Actor: Teacher
Precondition: Essays need grading
Flow:
  1. Teacher opens submission list for exam/assignment
  2. Selects a student submission
  3. Clicks "AI Assist" for essay grading
  4. AI reads essay, compares to rubric, suggests score
  5. AI highlights key points: argument strength, evidence, structure
  6. Teacher reviews AI suggestion
  7. Teacher adjusts score if needed
  8. Teacher adds written feedback
  9. Saves grade → marks as graded
Postcondition: Essay graded with AI assistance
```

### UC-7: Student Uses AI Academic Assistant
```
Actor: Student
Precondition: Student is authenticated
Flow:
  1. Student opens AI Assistant from dashboard
  2. Selects mode: Homework Help, Tutoring, Study Plan
  3. For homework: types question or uploads image
  4. AI retrieves relevant context (curriculum, subject)
  5. AI generates step-by-step explanation
  6. Student asks follow-up questions
  7. AI adapts to student's understanding level
  8. Session saved for later review
Postcondition: Student receives academic support

AI Flow:
  1. Student query → NLU → Intent classification
  2. Context assembly: subject, level, curriculum, past performance
  3. RAG retrieval from textbooks, solved examples
  4. Response generation with pedagogical approach
  5. Adaptive: simplify if struggling, challenge if excelling
```

### UC-8: Parent Views Child Performance Summary
```
Actor: Parent
Precondition: Parent has children enrolled
Flow:
  1. Parent opens Parent Dashboard
  2. Views overview of all children
  3. Selects a child to see detailed view
  4. Views: grades, attendance, behavior, fee status
  5. Clicks "AI Summary" for natural language analysis
  6. AI generates: strengths, areas for improvement, trends
  7. AI recommends: tutoring needs, parent-teacher meeting
  8. Parent can schedule meeting or message teacher
Postcondition: Parent has comprehensive understanding of child's progress
```

### UC-9: Teacher Generates Lesson Plan with AI
```
Actor: Teacher
Precondition: Teacher is authenticated
Flow:
  1. Teacher opens "AI Teacher Assistant"
  2. Selects "Generate Lesson Plan"
  3. Inputs: subject, topic, duration, class level, learning objectives
  4. AI generates structured lesson plan:
     - Learning objectives
     - Materials needed
     - Introduction/Warm-up (5 min)
     - Main activities (30 min)
     - Assessment/Check for understanding (10 min)
     - Homework/Extension (5 min)
  5. Teacher reviews, edits, saves
  6. Lesson plan saved to teacher's library
Postcondition: Lesson plan created and saved
```

### UC-10: Natural Language Search
```
Actor: Any authenticated user (role-permission filtered)
Precondition: User has permission to view requested data
Flow:
  1. User types in global search bar: "Show students with attendance below 70%"
  2. System parses query to structured filters
  3. System validates against user's permissions
  4. System executes safe query with tenant isolation
  5. Returns results: "23 students found. 15 in SS2, 8 in SS1"
  6. User can export results or drill down
Postcondition: User gets data from natural language query
```

### UC-11: Risk Detection & Intervention
```
Actor: System (Automated) / Counselor
Precondition: Academic or attendance data updated
Flow:
  1. System triggers risk analysis (event-driven or scheduled)
  2. AI analyzes: grades trend, attendance pattern, behavior, fee status
  3. Risk score calculated (0-100)
  4. If score > threshold → generate alert
  5. Counselor receives notification with risk details
  6. Counselor reviews AI recommendations
  7. Creates intervention plan (meeting, tutoring, counseling)
  8. System tracks intervention effectiveness
Postcondition: At-risk student identified; intervention initiated
```

### UC-12: Alumni Registration & Career Tracking
```
Actor: Graduate / Alumni
Precondition: Student has graduated
Flow:
  1. System automatically creates alumni profile on graduation
  2. Alumni receives welcome email with portal access
  3. Alumni completes profile (current employment, contact info)
  4. Alumni adds career history
  5. Alumni joins alumni directory (opt-in)
  6. Alumni can: register for events, find mentors, post jobs
  7. System tracks: engagement, donations, event attendance
Postcondition: Alumni registered and engaged
```

### UC-13: Certificate Verification
```
Actor: Third Party (Employer, University)
Precondition: -
Flow:
  1. Third party visits verification portal
  2. Enters: graduate name, graduation year, certificate number
  3. Or: submits verification request with consent
  4. System verifies against alumni records
  5. Returns: verified graduate status, degree, year of graduation
  6. If paid: payment processed first
Postcondition: Certificate verified
```

### UC-14: AI Career Guidance
```
Actor: Student / Alumni
Precondition: User has academic records or completed assessment
Flow:
  1. User opens Career Guidance
  2. Completes skills assessment (or uses academic data)
  3. AI analyzes: strengths, interests, academic performance
  4. AI recommends: career paths, suitable universities, scholarships
  5. AI identifies skills gaps and recommends courses
  6. AI generates career roadmap with milestones
  7. User can explore detailed career paths
Postcondition: User receives personalized career guidance
```

### UC-15: Multi-Campus Management
```
Actor: School Admin (Central Office)
Precondition: Tenancy is enterprise or multi-campus
Flow:
  1. Admin configures multiple campuses under one tenant
  2. Each campus has own: levels, classes, teachers, students
  3. Central admin can: view all campuses, cross-campus reports
  4. Campus-level admins manage only their campus
  5. Students can transfer between campuses
  6. Cross-campus events and shared resources
Postcondition: Multi-campus institution managed centrally
```

---

## 3. USE CASE MATRIX (Actor × Module)

```
                    │ Super  │School │Teacher│Student│ Parent│Account│Alumni │
                    │ Admin  │ Admin │       │       │       │  ant  │       │
════════════════════╪════════╪═══════╪═══════╪═══════╪═══════╪═══════╪═══════╡
Student Management  │   R    │  CRUD │   R   │   R   │   R   │   —   │   —   │
Teacher Management  │   R    │  CRUD │   R   │   —   │   —   │   —   │   —   │
Class/Level Mgmt    │   R    │  CRUD │   R   │   —   │   —   │   —   │   —   │
Subject Management  │   R    │  CRUD │   R   │   —   │   —   │   —   │   —   │
Timetable           │   R    │ CRUD  │  CRUD │   R   │   R   │   —   │   —   │
Attendance          │   R    │   R   │  CRUD │   R   │   R   │   —   │   —   │
Exams & Assessment  │   R    │  CRUD │  CRUD │   R   │   R   │   —   │   —   │
Results             │   R    │  CRUD │  CRUD │   R   │   R   │   —   │   —   │
Fees & Billing      │   R    │  CRUD │   —   │   R   │  CRUD │ CRUD  │   —   │
Payments            │   R    │   R   │   —   │  CRUD │ CRUD  │ CRUD  │   —   │
Admissions          │   R    │  CRUD │  screen│  —   │Create │   —   │   —   │
CBA (Exams)         │   R    │   R   │  CRUD │  Take  │  —    │   —   │   —   │
LMS                 │   R    │   R   │  CRUD │  Take  │   R   │   —   │   —   │
Library             │   R    │   R   │   R   │  CRUD │   —   │   —   │   —   │
Hostel              │   R    │  CRUD │   —   │   R   │   R   │   —   │   —   │
Transport           │   R    │  CRUD │   —   │   R   │   R   │   —   │   —   │
Inventory           │   R    │  CRUD │   —   │   —   │   —   │   —   │   —   │
HR & Payroll        │   R    │  CRUD │   R   │   —   │   —   │   R   │   —   │
Finance & Acct      │   R    │   R   │   —   │   —   │   —   │ CRUD  │   —   │
Alumni Management   │   R    │   R   │   —   │   —   │   —   │   —   │ CRUD  │
Career Guidance     │   R    │   R   │   —   │  CRUD │   —   │   —   │ CRUD  │
AI Assistant        │   R    │   R   │   R   │  CRUD │  CRUD │   —   │   R   │
Reports & BI        │  CRUD  │  CRUD │   R   │   R   │   R   │   R   │   R   │
Communication Hub   │   R    │  CRUD │  Send  │ Read  │ Read  │ Send  │ Read  │
Settings            │  CRUD  │  CRUD │   R   │   R   │   R   │   R   │   R   │

Legend: C=Create, R=Read, U=Update, D=Delete, — = No Access
```
