# SchoolCare v3 — Database Schema & Domain Models

---

## 1. DATABASE OVERVIEW

### Technology Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary DB | PostgreSQL 16+ | All transactional data |
| Cache | Redis 7+ | Sessions, rate limits, cache, queues |
| Object Storage | MinIO / S3 | Media, PDFs, uploads |
| Vector DB | Qdrant | Embeddings for RAG and AI search |
| Analytics DB | ClickHouse (optional) | BI dashboards, aggregations |

---

## 2. TENANCY MODEL

### Shared Schema with Tenant ID (Default)
All tables include `school_id` (existing pattern). This is the default for 90%+ of customers.

```sql
-- Current: school_id on every tenant-scoped table
ALTER TABLE users ADD COLUMN school_id BIGINT REFERENCES schools(id);
ALTER TABLE students ADD COLUMN school_id BIGINT NOT NULL REFERENCES schools(id);

-- NEW: Tenant table replacing simple school
CREATE TABLE tenants (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    plan VARCHAR(50) DEFAULT 'starter',
    settings JSONB DEFAULT '{}',
    features JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schools become tenant-aware
ALTER TABLE schools ADD COLUMN tenant_id BIGINT REFERENCES tenants(id);
```

### Schema-Per-Tenant (Enterprise Option)
For enterprise customers requiring data isolation:
```
-- Separate schema per tenant
CREATE SCHEMA tenant_{id};
SET search_path TO tenant_{id};

-- All tables replicated in each schema
```

---

## 3. COMPLETE ENTITY RELATIONSHIP DIAGRAM (Text)

```
TENANTS
  │
  ├── SCHOOLS ───────── CAMPUSES
  │     ├── LEVELS (classes/forms)
  │     ├── SUBJECTS
  │     ├── SESSIONS (academic terms)
  │     ├── CURRICULUMS
  │     ├── ASSESSMENTS ──── ASSESSMENT_CURRICULUM (pivot)
  │     ├── BILLS ──── FEES
  │     ├── TIMETABLES (slots)
  │     ├── ROLES
  │     ├── INVITATIONS
  │     └── MEDIA
  │
  ├── USERS
  │     ├── USER_INFOS
  │     ├── ROLE_USER (pivot: user ↔ school ↔ role)
  │     ├── STUDENTS ──── LEVELS
  │     │     ├── STUDENT_PARENT (pivot: student ↔ parent)
  │     │     ├── ATTENDANCE
  │     │     ├── SCORES
  │     │     ├── RESULTS
  │     │     ├── PAYMENTS
  │     │     └── STUDENT_ACTIVITIES
  │     ├── TEACHERS ──── LEVELS, SUBJECTS
  │     │     └── TEACHER_ATTENDANCE
  │     └── PARENTS ──── STUDENT_PARENT
  │
  ├── ADMISSION_INTAKES
  │     ├── APPLICATIONS
  │     │     ├── APPLICATION_DOCUMENTS
  │     │     ├── SCREENING_RESULTS
  │     │     ├── ENTRANCE_EXAM_RESULTS
  │     │     └── OFFERS
  │     └── ENROLLMENTS
  │
  ├── COURSES (LMS)
  │     ├── MODULES
  │     │     ├── LESSONS
  │     │     ├── QUIZZES
  │     │     └── ASSIGNMENTS
  │     ├── COURSE_ENROLLMENTS
  │     └── DISCUSSIONS
  │
  ├── CBA_EXAMS
  │     ├── QUESTION_BANK
  │     ├── EXAM_SESSIONS
  │     ├── PROCTORING_LOGS
  │     └── GRADING_RULES
  │
  ├── COMMUNICATIONS
  │     ├── TEMPLATES
  │     ├── MESSAGES
  │     └── CAMPAIGNS
  │
  ├── LIBRARY
  │     ├── BOOKS
  │     ├── E_BOOKS
  │     ├── BORROWINGS
  │     └── DIGITAL_RESOURCES
  │
  ├── HOSTELS
  │     ├── ROOMS
  │     │     ├── BEDS
  │     │     └── ALLOCATIONS
  │     └── MAINTENANCE_REQUESTS
  │
  ├── TRANSPORT
  │     ├── BUSES
  │     ├── ROUTES
  │     ├── STOPS
  │     └── TRIPS
  │
  ├── INVENTORY
  │     ├── ASSETS
  │     └── ASSET_ASSIGNMENTS
  │
  ├── HR
  │     ├── STAFF
  │     ├── PAYROLL
  │     ├── LEAVE
  │     └── PERFORMANCE
  │
  ├── FINANCE
  │     ├── ACCOUNTS (chart of accounts)
  │     ├── TRANSACTIONS
  │     └── BUDGETS
  │
  ├── ALUMNI
  │     ├── ALUMNI_CAREERS
  │     ├── ALUMNI_EVENTS
  │     ├── MENTORSHIPS
  │     ├── DONATIONS
  │     └── VERIFICATION_REQUESTS
  │
  ├── CAREER
  │     ├── SKILL_ASSESSMENTS
  │     ├── RECOMMENDATIONS
  │     └── SCHOLARSHIPS
  │
  ├── AI
  │     ├── CONVERSATIONS
  │     ├── EMBEDDINGS
  │     └── PROMPT_TEMPLATES
  │
  └── ANALYTICS
        ├── SNAPSHOTS
        └── DASHBOARDS
```

---

## 4. NEW DATABASE TABLES (Migration Phase 3-5)

### PHASE 3: Admissions & Enrollment

```sql
-- Admission Intake
CREATE TABLE admission_intakes (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    school_id BIGINT NOT NULL REFERENCES schools(id),
    name VARCHAR(255) NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft', -- draft, open, closed, completed
    max_applications INTEGER,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Application
CREATE TABLE applications (
    id BIGSERIAL PRIMARY KEY,
    intake_id BIGINT NOT NULL REFERENCES admission_intakes(id),
    tenant_id BIGINT NOT NULL,
    school_id BIGINT NOT NULL,
    applicant_id BIGINT REFERENCES users(id), -- null for public forms
    application_number VARCHAR(50) UNIQUE NOT NULL,
    firstname VARCHAR(100) NOT NULL,
    lastname VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(10),
    nationality VARCHAR(100),
    address JSONB,
    previous_school VARCHAR(255),
    previous_class VARCHAR(100),
    applying_for_level_id BIGINT REFERENCES levels(id),
    documents JSONB DEFAULT '[]',
    status VARCHAR(30) DEFAULT 'submitted',
    -- status flow: draft → submitted → screening → exam → offered → accepted → enrolled → rejected
    metadata JSONB DEFAULT '{}',
    ai_score DECIMAL(5,2),
    ai_eligibility VARCHAR(20),
    ai_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Application Documents
CREATE TABLE application_documents (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(id),
    document_type VARCHAR(50) NOT NULL, -- passport, birth_cert, transcript, etc.
    file_path VARCHAR(500) NOT NULL,
    file_name VARCHAR(255),
    file_size INTEGER,
    mime_type VARCHAR(100),
    verified BOOLEAN DEFAULT FALSE,
    verified_by BIGINT REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Screening Results
CREATE TABLE screening_results (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(id),
    screened_by BIGINT NOT NULL REFERENCES users(id),
    score DECIMAL(5,2),
    notes TEXT,
    decision VARCHAR(20), -- pass, fail, review
    criteria_breakdown JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entrance Exam Results (for CBA integration)
CREATE TABLE entrance_exam_results (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(id),
    exam_id BIGINT REFERENCES cba_exams(id),
    total_score DECIMAL(5,2),
    max_score DECIMAL(5,2),
    percentage DECIMAL(5,2),
    subject_breakdown JSONB DEFAULT '{}',
    passed BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admission Offers
CREATE TABLE admission_offers (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(id),
    offer_type VARCHAR(30), -- conditional, unconditional, provisional
    offered_level_id BIGINT REFERENCES levels(id),
    valid_until DATE,
    terms JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending', -- pending, accepted, declined, expired
    response_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enrollments
CREATE TABLE enrollments (
    id BIGSERIAL PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES applications(id),
    offer_id BIGINT REFERENCES admission_offers(id),
    student_id BIGINT NOT NULL REFERENCES students(id),
    enrollment_date DATE NOT NULL,
    enrollment_type VARCHAR(30), -- new, transfer, returning
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PHASE 3: CBA (Computer-Based Assessment)

```sql
-- Question Bank
CREATE TABLE question_bank_categories (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    name VARCHAR(255) NOT NULL,
    parent_id BIGINT REFERENCES question_bank_categories(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE questions (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    subject_id BIGINT NOT NULL REFERENCES subjects(id),
    category_id BIGINT REFERENCES question_bank_categories(id),
    difficulty VARCHAR(20) DEFAULT 'medium', -- easy, medium, hard
    question_type VARCHAR(30) NOT NULL, -- multiple_choice, essay, fill_blank, matching
    question_text TEXT NOT NULL,
    options JSONB, -- for multiple choice
    correct_answer TEXT,
    explanation TEXT,
    marks DECIMAL(5,2) NOT NULL,
    tags TEXT[],
    status VARCHAR(20) DEFAULT 'active',
    version INTEGER DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exams
CREATE TABLE cba_exams (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    session_id BIGINT REFERENCES sessions(id),
    subject_id BIGINT REFERENCES subjects(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    exam_type VARCHAR(30) NOT NULL, -- waec, jamb, internal, mock, practice
    duration_minutes INTEGER NOT NULL,
    total_marks DECIMAL(7,2),
    pass_mark DECIMAL(5,2),
    shuffle_questions BOOLEAN DEFAULT TRUE,
    shuffle_options BOOLEAN DEFAULT TRUE,
    show_results BOOLEAN DEFAULT TRUE,
    allow_review BOOLEAN DEFAULT TRUE,
    max_attempts INTEGER DEFAULT 1,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    proctoring_required BOOLEAN DEFAULT FALSE,
    browser_lockdown BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'draft',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Exam Questions (pivot with ordering and marks)
CREATE TABLE exam_questions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES cba_exams(id),
    question_id BIGINT NOT NULL REFERENCES questions(id),
    order_index INTEGER NOT NULL,
    marks DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Student Exam Sessions
CREATE TABLE exam_sessions (
    id BIGSERIAL PRIMARY KEY,
    exam_id BIGINT NOT NULL REFERENCES cba_exams(id),
    student_id BIGINT NOT NULL REFERENCES students(id),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    status VARCHAR(30) DEFAULT 'pending', -- pending, in_progress, completed, terminated, graded
    tab_switches INTEGER DEFAULT 0,
    connection_drops INTEGER DEFAULT 0,
    score DECIMAL(7,2),
    percentage DECIMAL(5,2),
    graded BOOLEAN DEFAULT FALSE,
    graded_by BIGINT REFERENCES users(id),
    graded_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Student Answers
CREATE TABLE exam_answers (
    id BIGSERIAL PRIMARY KEY,
    exam_session_id BIGINT NOT NULL REFERENCES exam_sessions(id),
    question_id BIGINT NOT NULL REFERENCES questions(id),
    answer TEXT,
    is_correct BOOLEAN,
    marks_awarded DECIMAL(5,2),
    ai_score DECIMAL(5,2),
    ai_feedback TEXT,
    graded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Proctoring Logs
CREATE TABLE proctoring_logs (
    id BIGSERIAL PRIMARY KEY,
    exam_session_id BIGINT NOT NULL REFERENCES exam_sessions(id),
    event_type VARCHAR(50) NOT NULL, -- face_detected, face_lost, multiple_faces, tab_switch, etc.
    timestamp TIMESTAMPTZ NOT NULL,
    screenshot_path VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grading Rules
CREATE TABLE grading_rules (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    name VARCHAR(255) NOT NULL,
    rules JSONB NOT NULL, -- grading criteria and formulas
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PHASE 3: LMS

```sql
CREATE TABLE courses (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    thumbnail VARCHAR(500),
    subject_id BIGINT REFERENCES subjects(id),
    level_id BIGINT REFERENCES levels(id),
    teacher_id BIGINT REFERENCES teachers(id),
    duration VARCHAR(50),
    difficulty VARCHAR(20),
    status VARCHAR(20) DEFAULT 'draft',
    enrollment_limit INTEGER,
    settings JSONB DEFAULT '{}',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE course_modules (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES courses(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE lessons (
    id BIGSERIAL PRIMARY KEY,
    module_id BIGINT NOT NULL REFERENCES course_modules(id),
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(30) NOT NULL, -- video, text, pdf, quiz, assignment
    content TEXT,
    video_url VARCHAR(500),
    duration_minutes INTEGER,
    order_index INTEGER NOT NULL,
    is_free BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE course_enrollments (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES courses(id),
    student_id BIGINT NOT NULL REFERENCES students(id),
    enrolled_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    progress DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    dropped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(course_id, student_id)
);

CREATE TABLE lesson_progress (
    id BIGSERIAL PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES course_enrollments(id),
    lesson_id BIGINT NOT NULL REFERENCES lessons(id),
    completed BOOLEAN DEFAULT FALSE,
    time_spent_seconds INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(enrollment_id, lesson_id)
);

CREATE TABLE assignments (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES courses(id),
    lesson_id BIGINT REFERENCES lessons(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date TIMESTAMPTZ,
    total_marks DECIMAL(5,2),
    submission_type VARCHAR(30), -- file, text, both
    settings JSONB DEFAULT '{}',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignment_submissions (
    id BIGSERIAL PRIMARY KEY,
    assignment_id BIGINT NOT NULL REFERENCES assignments(id),
    student_id BIGINT NOT NULL REFERENCES students(id),
    submission_text TEXT,
    file_path VARCHAR(500),
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'submitted',
    marks_awarded DECIMAL(5,2),
    feedback TEXT,
    ai_feedback TEXT,
    graded_by BIGINT REFERENCES users(id),
    graded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE discussions (
    id BIGSERIAL PRIMARY KEY,
    course_id BIGINT NOT NULL REFERENCES courses(id),
    lesson_id BIGINT REFERENCES lessons(id),
    user_id BIGINT NOT NULL REFERENCES users(id),
    parent_id BIGINT REFERENCES discussions(id),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PHASE 4: Alumni & Career

```sql
CREATE TABLE alumni (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    school_id BIGINT NOT NULL REFERENCES schools(id),
    graduation_year INTEGER NOT NULL,
    graduation_session_id BIGINT REFERENCES sessions(id),
    student_id BIGINT REFERENCES students(id),
    current_employer VARCHAR(255),
    current_position VARCHAR(255),
    industry VARCHAR(100),
    location VARCHAR(255),
    linkedin_url VARCHAR(500),
    bio TEXT,
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    newsletter_opt_in BOOLEAN DEFAULT TRUE,
    mentor_available BOOLEAN DEFAULT FALSE,
    donation_anonymous BOOLEAN DEFAULT FALSE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, school_id)
);

CREATE TABLE alumni_careers (
    id BIGSERIAL PRIMARY KEY,
    alumni_id BIGINT NOT NULL REFERENCES alumni(id),
    company VARCHAR(255) NOT NULL,
    position VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    location VARCHAR(255),
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alumni_events (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_type VARCHAR(30), -- reunion, networking, webinar, fundraiser
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    location VARCHAR(255),
    virtual_link VARCHAR(500),
    max_attendees INTEGER,
    registration_deadline TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'draft',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE event_attendees (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES alumni_events(id),
    alumni_id BIGINT NOT NULL REFERENCES alumni(id),
    registered_at TIMESTAMPTZ DEFAULT NOW(),
    attended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(event_id, alumni_id)
);

CREATE TABLE mentorships (
    id BIGSERIAL PRIMARY KEY,
    mentor_id BIGINT NOT NULL REFERENCES alumni(id),
    mentee_id BIGINT NOT NULL REFERENCES alumni(id),
    program_name VARCHAR(255),
    start_date DATE,
    end_date DATE,
    goals TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE donations (
    id BIGSERIAL PRIMARY KEY,
    alumni_id BIGINT NOT NULL REFERENCES alumni(id),
    campaign_id BIGINT REFERENCES fundraising_campaigns(id),
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    donation_type VARCHAR(30), -- one_time, monthly, annual
    payment_reference VARCHAR(255),
    anonymous BOOLEAN DEFAULT FALSE,
    dedication TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    donated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fundraising_campaigns (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    goal_amount DECIMAL(12,2),
    raised_amount DECIMAL(12,2) DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    start_date DATE,
    end_date DATE,
    campaign_type VARCHAR(30), -- scholarship, infrastructure, research, general
    status VARCHAR(20) DEFAULT 'draft',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE verification_requests (
    id BIGSERIAL PRIMARY KEY,
    alumni_id BIGINT REFERENCES alumni(id),
    requester_name VARCHAR(255) NOT NULL,
    requester_email VARCHAR(255) NOT NULL,
    requester_organization VARCHAR(255),
    verification_type VARCHAR(30) NOT NULL, -- certificate, transcript, enrollment
    verified_info JSONB NOT NULL,
    purpose TEXT,
    fee DECIMAL(10,2),
    payment_reference VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending',
    verified_by BIGINT REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    response_document VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE job_board (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT REFERENCES schools(id),
    posted_by BIGINT REFERENCES alumni(id),
    company VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT,
    location VARCHAR(255),
    work_type VARCHAR(30), -- remote, hybrid, onsite
    employment_type VARCHAR(30), -- full_time, part_time, contract, internship
    salary_range VARCHAR(100),
    application_url VARCHAR(500),
    application_email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    expires_at DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PHASE 5: AI & Analytics Tables

```sql
-- AI Conversations
CREATE TABLE ai_conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    school_id BIGINT REFERENCES schools(id),
    session_id VARCHAR(100),
    conversation_type VARCHAR(30) NOT NULL, -- academic_assist, teacher_assist, parent_assist, career_guide, search
    title VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE ai_messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES ai_conversations(id),
    role VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    model VARCHAR(100),
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document Embeddings (for RAG)
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),
    source_type VARCHAR(50) NOT NULL, -- curriculum, policy, faq, textbook, etc.
    source_id BIGINT,
    title VARCHAR(255),
    content TEXT NOT NULL,
    chunk_index INTEGER,
    embedding_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Prompt Templates
CREATE TABLE prompt_templates (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    template TEXT NOT NULL,
    variables JSONB DEFAULT '[]',
    model VARCHAR(100),
    temperature DECIMAL(3,2) DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2000,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analytics Dashboards
CREATE TABLE dashboards (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    dashboard_type VARCHAR(30), -- executive, academic, financial, alumni
    layout JSONB DEFAULT '{}',
    settings JSONB DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Analytics Snapshots (materialized aggregates)
CREATE TABLE analytics_snapshots (
    id BIGSERIAL PRIMARY KEY,
    school_id BIGINT NOT NULL REFERENCES schools(id),
    snapshot_type VARCHAR(50) NOT NULL, -- daily_enrollment, weekly_attendance, term_performance
    snapshot_date DATE NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. ENUM EXTENSIONS

```go
// New role constants for SchoolCare v3
const (
    RoleSuperAdmin      = "super-admin"
    RoleAdmin           = "admin"
    RolePrincipal       = "principal"
    RoleTeacher         = "teacher"
    RoleParent          = "parent"
    RoleStudent         = "student"
    RoleAccountant      = "accountant"     // NEW
    RoleLibrarian       = "librarian"      // NEW
    RoleHR              = "hr"             // NEW
    RoleCounselor       = "counselor"      // NEW
    RoleAlumni          = "alumni"         // NEW
    RoleApplicant       = "applicant"      // NEW
    RoleGuardian        = "guardian"       // NEW
    RoleTransportManager = "transport_mgr" // NEW
    RoleHostelManager   = "hostel_mgr"     // NEW
    RoleAdmissionsOfficer = "admissions_officer" // NEW
    RoleSystemAdmin     = "system-admin"   // NEW
)

// Subscription plan constants
const (
    PlanStarter   = "starter"
    PlanGrowth    = "growth"
    PlanPremium   = "premium"
    PlanEnterprise = "enterprise"
    PlanOnline     = "online-academy"
)

// Application status flow
const (
    AppDraft     = "draft"
    AppSubmitted = "submitted"
    AppScreening = "screening"
    AppExam      = "exam"
    AppOffered   = "offered"
    AppAccepted  = "accepted"
    AppEnrolled  = "enrolled"
    AppRejected  = "rejected"
)

// Exam types
const (
    ExamInternal = "internal"
    ExamWAEC     = "waec"
    ExamJAMB     = "jamb"
    ExamMock     = "mock"
    ExamPractice = "practice"
)

// Question types
const (
    QTypeMultipleChoice = "multiple_choice"
    QTypeEssay          = "essay"
    QTypeFillBlank      = "fill_blank"
    QTypeMatching       = "matching"
    QTypeTrueFalse      = "true_false"
)
```
