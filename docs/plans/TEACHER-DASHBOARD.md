# Teacher Dashboard

## Current State
- `/teacher/dashboard` exists but is a **placeholder** (empty card + quick links)
- Teachers are redirected to generic `/dashboard` which shows admin-style KPIs

## Proposed Content

```
┌─────────────────────────────────────────────────────┐
│  Welcome back, [Teacher Name]                       │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Active   │  │ My       │  │ Assigned │          │
│  │ Session  │  │ Classes  │  │ Subjects │          │
│  │ [name]   │  │ 3        │  │ 5        │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                                     │
│  ┌─ Current Assessment ─────────────────────────┐   │
│  │  Score entry for "First CA" (15%) is pending │   │
│  │  [Enter Scores →]                            │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ Quick Actions ──────────────────────────────┐   │
│  │  [📝 Enter Scores]  [📊 View Results]         │   │
│  │  [📅 My Timetable]  [📋 My Subjects]          │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ Recent Activity ───────────────────────────┐   │
│  │  • Entered scores for JSS 1A Mathematics     │   │
│  │  • Rolled up results for First CA           │   │
│  │  • Submitted results for approval           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Data Sources
| Section | Hook/Data |
|---------|-----------|
| Active session | `useSessions()` → active session name |
| My Classes | Teacher's assigned levels from their profile or `useTeacherDetail(userId)` |
| My Subjects | `useSubjects()` with school ID |
| Current assessment | `useAssessments()` → active assessment name |
| Quick actions | Hardcoded links to key teacher routes |
| Recent activity | Could be from a future `/teacher/activity` API |

## Implementation
1. Rewrite `teacher.dashboard.tsx` with real data components
2. Use existing hooks (`useSessions`, `useAssessments`, `useSubjects`, `useAuthStore`)
3. Add stat cards, assessment card, and quick actions
4. Wire the "Enter Scores" button to `/teacher/academics` with assessment pre-selected
