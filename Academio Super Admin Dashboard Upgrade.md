# Academio Super Admin Dashboard — Comprehensive & Futuristic Frontend Architecture Plan

You are acting as a **Senior Product Architect, Principal Frontend Engineer, UX Architect, and SaaS Platform Designer** working on Academio.

We now want to take the Academio Super Admin experience to a significantly higher level.

Before writing or changing frontend code, your first responsibility is to **understand what Academio already has** and design the Super Admin experience around the capabilities that actually exist in the backend.

Do not create a generic school-management dashboard.

Design the **control plane for Academio itself**.

---

## PRIMARY OBJECTIVE

Analyze:

1. Everything currently implemented for Super Admin on the frontend.
2. Everything currently implemented in the Academio backend that is relevant to Super Admin.
3. Existing APIs, services, permissions, workflows, models, events, notifications, analytics, tenant management, and platform infrastructure.
4. Existing frontend architecture, routing, state management, components, design system, and patterns.

Then produce a **comprehensive, futuristic, scalable Super Admin Dashboard plan** that can evolve with Academio from Alpha → Beta → Production → large-scale SaaS platform.

The goal is not simply to make the dashboard look better.

The goal is to create a **professional platform operations console** for managing and understanding the entire Academio ecosystem.

---

# 1. AUDIT BEFORE DESIGN

Do not start by designing screens.

First inspect the existing codebase.

Analyze:

### Frontend

* Current Super Admin routes
* Existing pages
* Existing components
* Navigation
* Layout
* Tables
* Forms
* Charts
* Filters
* Modals
* Search
* Notifications
* Loading states
* Error states
* Empty states
* Permissions
* Responsive behavior
* Existing design system

### Backend

Inspect all relevant:

* Routes
* Controllers/handlers
* Services
* Repositories
* Models
* DTOs
* Permissions
* RBAC
* Middleware
* Authentication
* Tenant management
* School management
* User management
* Academic calendar
* Curriculum
* Workflow engine
* Notifications
* AI/RAG infrastructure
* Background jobs
* Redis/Asynq
* Audit logs
* Platform configuration
* Billing/payment infrastructure where implemented
* File/storage management
* System health/monitoring endpoints where available

Do not assume an API exists because a dashboard feature would be useful.

Only design features that are:

1. Already supported by the backend,
2. Clearly planned and architecturally compatible, or
3. Explicitly identified as a future capability.

Clearly label category 3 as **Future/Roadmap**.

---

# 2. CREATE A BACKEND → FRONTEND CAPABILITY MAP

Before designing the dashboard, produce a matrix:

| Backend Capability | API Available | Super Admin Need | Existing UI | Proposed UI | Status |
| ------------------ | ------------- | ---------------- | ----------- | ----------- | ------ |

Map every relevant backend capability.

This becomes the foundation of the dashboard architecture.

Do not build UI that has no backend support without explicitly marking it as future work.

---

# 3. DEFINE THE SUPER ADMIN ROLE

Clearly define what Super Admin means in Academio.

Super Admin should represent the **platform operator**, not an individual school's administrator.

Think of the distinction as:

```text
Academio Platform
        │
        ├── Super Admin
        │      ↓
        │   Platform Control Plane
        │
        ├── School A
        │      └── School Admin
        │
        ├── School B
        │      └── School Admin
        │
        └── School C
               └── School Admin
```

Super Admin should be able to understand and manage the platform without unnecessarily exposing normal school-level functionality.

---

# 4. FUTURISTIC DASHBOARD VISION

Design the Super Admin dashboard as a **Platform Operations Center**.

The dashboard should answer immediately:

### Platform

* How many schools?
* How many active schools?
* How many users?
* How many students?
* How many teachers?
* How many active tenants?
* Platform growth?
* New schools?
* Active users?
* System health?

### Operations

* What requires attention?
* Failed jobs?
* Failed notifications?
* Pending platform actions?
* Suspicious activity?
* System errors?
* Infrastructure issues?

### Business

Where supported:

* Subscription status
* Revenue
* Usage
* Growth
* School conversion
* Plan distribution

### Product

* Feature adoption
* Most-used modules
* User activity
* API usage
* Storage usage
* Notification usage
* AI usage

---

# 5. DASHBOARD INFORMATION ARCHITECTURE

Propose a clear navigation structure.

For example:

```text
Super Admin
│
├── Overview
│
├── Schools
│   ├── All Schools
│   ├── Onboarding
│   ├── School Types
│   └── School Health
│
├── Users
│   ├── Users
│   ├── Roles
│   ├── Invitations
│   └── Access
│
├── Academic Platform
│   ├── Calendars
│   ├── Curricula
│   └── Education Standards
│
├── Platform Operations
│   ├── Workflows
│   ├── Notifications
│   ├── Background Jobs
│   ├── Audit Logs
│   └── System Events
│
├── AI Platform
│   ├── AI Usage
│   ├── Knowledge Base
│   ├── RAG
│   └── AI Health
│
├── Analytics
│
├── Security
│   ├── Access Logs
│   ├── Security Events
│   └── Sessions
│
├── Platform Settings
│
└── System Health
```

Do not blindly follow this example.

Derive the actual navigation from the backend audit.

---

# 6. OVERVIEW PAGE

Design a high-value Super Admin overview.

Avoid filling the screen with meaningless statistics.

Prioritize actionable information.

Example sections:

### Platform Health

```text
Schools       Users       Students
1,245         38,902      412,301
```

### Growth

* Schools over time
* Users over time
* Active users
* New registrations

### Operational Health

```text
API              Healthy
Database         Healthy
Redis            Healthy
Workers          Healthy
Notifications    Healthy
AI Engine        Healthy
```

Only display health indicators that can actually be backed by real data.

### Action Center

Surface things requiring attention:

* Failed jobs
* Failed notifications
* Pending approvals
* Security events
* System warnings

---

# 7. SCHOOL / TENANT MANAGEMENT

Design a powerful tenant management experience.

Super Admin should be able to:

* Search schools
* Filter schools
* View school details
* View school status
* View school type
* View subscription/plan where supported
* View usage
* View user count
* View student count
* View health
* View onboarding status
* Suspend/reactivate where supported
* Access appropriate administrative actions

Create a detailed **School Overview** page.

Example:

```text
School
├── Overview
├── Users
├── Students
├── Academic Structure
├── Usage
├── Activity
├── Notifications
├── Audit
└── Platform Status
```

Do not expose dangerous actions without confirmation and appropriate authorization.

---

# 8. USER MANAGEMENT

Design platform-level user management.

Support where backend capabilities exist:

* Search
* Filtering
* Role
* School
* Status
* Last activity
* Account status
* Invitations
* Access management

Include powerful search but prevent accidental cross-tenant data exposure.

---

# 9. PLATFORM ANALYTICS

Design a future-ready analytics layer.

Consider:

### Adoption

* Schools onboarded
* Active schools
* Active users
* Active students

### Engagement

* Daily active users
* Weekly active users
* Monthly active users

### Product usage

* Most-used modules
* Feature adoption
* Workflow usage
* Notification usage

### Infrastructure

* API requests
* Background jobs
* Queue activity
* Storage
* AI usage

Only implement metrics that can be reliably sourced.

---

# 10. NOTIFICATION OPERATIONS

Since Academio's notification system is becoming an important Alpha capability, provide a Super Admin operational view.

Display:

* Notifications sent
* Delivery success
* Delivery failures
* Email failures
* Push failures
* Queue backlog
* Retry count
* Provider status
* Recent notification events

Allow appropriate investigation without exposing sensitive notification content unnecessarily.

Example:

```text
Notification Operations

Delivered       98.7%
Failed           1.1%
Retrying         0.2%

Email     ✓
Push      ✓
In-App    ✓
```

---

# 11. WORKFLOW OPERATIONS

Academio contains workflow-driven operations.

Design a platform-level workflow monitoring interface.

Display:

* Active workflows
* Completed workflows
* Failed workflows
* Pending workflows
* Average processing time
* Failed workflow executions

Allow Super Admin to investigate workflow failures where backend capabilities support it.

---

# 12. BACKGROUND JOB OPERATIONS

Academio uses Redis + Asynq.

Where appropriate, provide operational visibility into:

* Queue health
* Pending jobs
* Processing jobs
* Failed jobs
* Retry counts
* Job latency
* Worker health

Do not build a full Asynq replacement UI unless justified.

Provide only the operational capabilities useful to Academio administrators.

---

# 13. AUDIT & SECURITY

Design a serious audit interface.

Support where backend data exists:

* Actor
* Action
* Resource
* Tenant
* Timestamp
* IP where available
* Result
* Correlation ID

Provide filtering:

```text
Tenant
User
Action
Resource
Date
Status
```

Audit logs should be immutable from the frontend.

---

# 14. AI PLATFORM

Academio will contain AI/RAG capabilities.

Design a future-ready AI administration area based on the actual backend implementation.

Potential areas:

* AI usage
* Knowledge bases
* Vector data
* Document ingestion
* RAG activity
* AI requests
* AI errors
* Token/usage metrics where available
* AI engine health

Respect the existing distinction between:

```text
Global/Public Knowledge
        +
School/Tenant Knowledge
        +
Vector Data
```

Do not expose one school's knowledge base to another.

---

# 15. ACADEMIC PLATFORM MANAGEMENT

Academio is evolving toward a flexible academic architecture.

Where supported by the backend, consider Super Admin visibility into:

* Academic calendars
* School types
* Education standards
* Curriculum templates
* Regional standards
* Platform defaults

The Super Admin should be able to understand how Academio's education model is configured globally.

---

# 16. GLOBAL SEARCH

Design a platform-wide search experience.

Super Admin should eventually be able to search across authorized platform entities:

```text
School
User
Student
Event
Workflow
Notification
Audit Event
```

Use contextual search results.

Example:

```text
Search: "St. Mary's"

Schools
Users
Events
Audit Logs
```

Do not create a search system that bypasses backend authorization.

---

# 17. COMMAND CENTER

Consider a future command-center experience.

The Super Admin should be able to see:

```text
┌─────────────────────────────────────────┐
│ Academio Platform                      │
│                                         │
│ System Health        ✓ Operational      │
│ Schools              1,245              │
│ Active Users         31,902             │
│ Notifications        99.1% delivered    │
│ Background Jobs      Healthy             │
│ AI Engine            Healthy             │
│                                         │
│ ⚠ 3 Issues Require Attention            │
└─────────────────────────────────────────┘
```

This should be actionable, not merely decorative.

---

# 18. DESIGN SYSTEM

Use the existing Academio frontend design system.

Maintain:

* Existing typography
* Existing color system
* Existing spacing
* Existing components
* Existing Tailwind conventions
* Existing shadcn/ui components

Improve consistency rather than introducing a completely different visual language.

The Super Admin should feel like Academio, but more operational and information-dense.

---

# 19. UX PRINCIPLES

The Super Admin interface must prioritize:

### Clarity

Important information should be immediately understandable.

### Density

Super Admin requires more information density than normal school dashboards.

### Hierarchy

Critical events should stand out.

### Speed

Frequently used administrative actions should require minimal navigation.

### Safety

Dangerous operations require confirmation.

### Context

Always show:

* What entity?
* Which school?
* Which user?
* What action?
* What changed?
* When?

### Progressive disclosure

Do not overwhelm the initial dashboard.

Show summaries first and allow drilling into details.

---

# 20. TABLES

Design reusable enterprise-grade tables.

Support:

* Server-side pagination
* Sorting
* Filtering
* Search
* Column visibility
* Export where appropriate
* Bulk operations where safe
* Responsive behavior

Avoid rendering enormous datasets directly in the browser.

---

# 21. RESPONSIVE DESIGN

The Super Admin dashboard is primarily desktop-oriented but must remain usable on:

* Laptop
* Tablet
* Mobile

Do not attempt to force every desktop table into a tiny mobile screen.

Use appropriate responsive transformations.

---

# 22. LOADING / ERROR / EMPTY STATES

Every major dashboard component must have:

* Loading state
* Error state
* Empty state
* Retry action where appropriate

Never leave blank screens while data loads.

---

# 23. PERFORMANCE

Use the existing TanStack architecture effectively.

Consider:

* Query caching
* Parallel queries
* Lazy loading
* Route-level code splitting
* Virtualized tables where required
* Prefetching
* Server-side filtering
* Debounced search

Do not make the dashboard issue dozens of unnecessary API requests on initial load.

---

# 24. PERMISSION-AWARE UI

The frontend must reflect backend permissions.

Do not rely on hidden buttons as security.

For every privileged operation:

```text
Frontend permission check
        +
Backend authorization
```

The backend remains the ultimate authority.

---

# 25. ALPHA → BETA → FUTURE ROADMAP

Divide the proposed dashboard into:

## Alpha

Only what is necessary for operating and testing Academio.

## Beta

Operational analytics, deeper tenant management, notification operations, workflow monitoring, etc.

## Future

Advanced platform analytics, AI operations center, automated platform intelligence, advanced billing, advanced observability, and other capabilities supported by future backend evolution.

Do not attempt to build everything at once.

---

# 26. IMPORTANT — DO NOT OVERENGINEER

Academio is currently Alpha.

The architecture should be future-ready without building unnecessary enterprise complexity today.

Prefer:

```text
Simple
Reliable
Observable
Extensible
```

over:

```text
Complex
Over-engineered
Difficult to maintain
```

---

# 27. REQUIRED OUTPUT BEFORE CODING

Before making frontend changes, provide:

### 1. Current Super Admin Audit

What currently exists.

### 2. Backend Capability Audit

What the backend actually supports.

### 3. Gap Analysis

What is missing.

### 4. Super Admin Product Vision

What the dashboard should become.

### 5. Information Architecture

Complete navigation structure.

### 6. Page Inventory

Every proposed page and its purpose.

### 7. Dashboard Wireframe Concepts

Describe the structure of major screens.

### 8. Backend/API Mapping

Map every frontend capability to existing APIs.

### 9. Permission Model

Define which Super Admin capabilities require which permissions.

### 10. Alpha/Beta/Roadmap Priorities

Clearly separate immediate implementation from future functionality.

### 11. Technical Architecture

Explain how the frontend should implement the dashboard using the existing:

* React
* Vite
* TanStack Router
* TanStack Query
* Tailwind
* shadcn/ui

### 12. Implementation Plan

Provide a phased implementation plan.

---

# 28. IMPLEMENTATION RULE

Do NOT immediately start coding.

First return the complete analysis and proposed architecture.

Wait for the implementation phase unless the existing workflow explicitly requires implementation immediately.

If implementation is requested after the analysis:

1. Implement incrementally.
2. Reuse existing components.
3. Avoid unnecessary rewrites.
4. Preserve existing routes and functionality.
5. Preserve backend API contracts.
6. Add tests.
7. Run type checking.
8. Run linting.
9. Run production build.
10. Verify responsive behavior.

---

# FINAL OBJECTIVE

The final Super Admin experience should feel like the **operating system control center for Academio** rather than another CRUD administration dashboard.

It should allow the platform team to answer:

> "What is happening across Academio right now, what requires my attention, and where can I drill down to understand or resolve it?"

Design for the Academio of today while establishing a strong architectural foundation for the Academio of tomorrow.
