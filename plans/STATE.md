# Project State: Curriculum & Assessment Model

## Project Reference
- **Repository:** academio (schoolcare-v2)
- **Stack:** Go (Gin/GORM) backend, React (Vite/TanStack Router/shadcn/ui) frontend
- **Core Value:** Replace flat assessment scoring with nested Curriculum → Assessment → Grade Item hierarchy

## Current Position

| Phase | Status | Started | Completed |
|---|---|---|---|
| 1 — GradeItem CRUD | ✅ Completed | — | 2026-07-04 |
| 2 — Nested Curriculum | ✅ Completed | — | 2026-07-04 |
| 3 — Per-Grade-Item Scoring | ✅ Completed | 2026-07-04 | 2026-07-04 |

## Current Focus
All 3 phases of Curriculum & Assessment Model are complete. Consider next feature or refinement.

## Current State Before Implementation

### Backend
- `curriculums` table exists, many-to-many with `assessments` via `assessment_curriculum`
- `assessments` table exists, `grades` JSON holds letter-grade boundaries (A:80, B:60, etc.)
- `scores` table stores per-student scores as JSON per assessment
- `results` table aggregates scores
- **No `grade_items` table** — does not exist
- Academic module at `backend/internal/modules/academic/` with repo → service → handler pattern
- Score module at `backend/internal/modules/score/` (separate module)
- Router uses `authGroup()` middleware pattern for tenant-aware routes

### Frontend
- `useAcademics.ts` hooks for Sessions, Curriculums, Assessments, Results
- `school.tsx` has tabs: General, Sessions, Classes, Subjects — **no Curriculum tab**
- Curriculum types: `Curriculum`, `Session`, `Assessment`, `Result`
- **No `GradeItem` type** — does not exist
- Query keys centralized in `query-keys.ts`

## Architecture Decisions

1. **GradeItem in academic module** — Follow existing pattern; GradeItem is part of the academic domain, co-located with Assessment/Curriculum
2. **Incremental schema** — Add FK columns, don't remove old tables immediately; keep `assessment_curriculum` pivot for backward compat
3. **Nested creation in single endpoint** — `POST /academic/curriculum` accepts full nested payload (assessments → grade items), handled transactionally
4. **Score rollup as service layer** — Grade-item scores saved individually, rollup computed on-demand when assessment total is requested

## Files to Reference

- `CURRICULUM-PLAN.md` — full requirements document
- `plans/curriculum-assessment-roadmap.md` — this roadmap
- `backend/internal/modules/academic/*.go` — existing academic module
- `backend/internal/modules/score/*.go` — existing score module
- `backend/internal/database/models/curriculum.go` — curriculum model
- `backend/internal/database/models/assessment.go` — assessment model
- `backend/internal/database/models/score.go` — score model
- `backend/internal/database/models/schema.go` — AllModels() for migration
- `frontend/src/lib/hooks/useAcademics.ts` — frontend hooks for academic domain
- `frontend/src/routes/_dashboard/school.tsx` — school page (target for curriculum tab)

## Next Action

Approve roadmap, then begin Phase 1 implementation.
