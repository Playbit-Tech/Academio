# Phase 5: Gradebook Hardening — Context & Decisions

## Phase Goal
Frozen grade UI indicators on completed sessions + boundary test suite for WAEC thresholds.

## Plans
- [ ] 05-01: Grade freeze frontend UI — frozen badge/banner indicators on completed sessions
- [ ] 05-02: Boundary test suite — WAEC grade thresholds at ±0.01 precision

### Nullified / Out of Scope
All backend/database hardening descoped (already sufficiently implemented or over-engineering):
- ~~Basis-point score migration~~ — already partially done; not critical
- ~~Sum-to-100 DB trigger~~ — app-level validation exists; DB trigger unnecessary
- ~~Grade freeze DB trigger~~ — app-level `canModifyScore` is sufficient
- ~~grade_corrections table + history panel~~ — not needed for current release
- ~~Post-mutation recalculation queue~~ — `RecalcNeeded` field exists; Asynq task overkill for now
- ~~Report card snapshotting~~ — deferred

## Key Decisions

### 1. Grade Freeze UI Scope
- Only **frontend visual indicators** — badge on session cards, banner on score pages
- No backend changes: app-level `canModifyScore()` + `disabled` prop on ScoreGrid already enforce read-only
- Toggle on `session.status === "completed"`
- No DB trigger, no admin override endpoint needed

### 2. Boundary Test Suite Scope
- Unit tests for WAEC A1-F9 boundary calculations at ±0.01 precision
- Test existing `RoundToBasisPoints()` / `BasisPointsToFloat()` utilities
- Test grade boundary comparison logic in grading service
- Integration test: verify frozen-grade read-only via ScoreGrid disabled state

## Prior Context Carried Forward
- Session.Status indicates completion (Phase 4)
- ScoreGrid already has `disabled` prop (existing)
- `canModifyScore()` already exists in grading service

## Canonical Refs
- `frontend/src/components/academics/score-grid.tsx` — ScoreGrid with `disabled` prop
- `frontend/src/routes/_dashboard/academics.tsx` — academics page with session cards
- `backend/internal/modules/grading/service.go` — `canModifyScore()` helper
- `backend/internal/pkg/rounding.go` — `RoundToBasisPoints`, `BasisPointsToFloat`
- `backend/internal/database/models/session.go` — Session model with Status field
