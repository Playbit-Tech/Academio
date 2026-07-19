---
phase: 5
slug: gradebook-hardening
status: draft
shadcn_initialized: true
preset: shadcn default (tailwind.config.js + components.json)
created: 2026-07-19
---

# Phase 5 — Gradebook Hardening: UI Design Contract

> Visual contract for frozen grade indicators on completed sessions. All additions live inside existing `academics.tsx` and `ScoreGrid` — no new standalone pages.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn/ui |
| Preset | Tailwind CSS with CSS variables (`--primary`, `--muted-foreground`, `--destructive`, etc.) |
| Component library | Radix UI (via shadcn) |
| Icon library | lucide-react |
| Font | Inter (system font stack fallback) |

**Existing shadcn components in use:** `Button`, `Badge`, `Card`, `Tabs`, `Select`, `Input`, `Sheet`, `Sonner`, `EmptyState`, `Loading`.

---

## Spacing Scale

Existing Tailwind spacing tokens; no phase-specific exceptions.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Lock icon gap in badge |
| sm | 8px | Badge padding, compact row gaps |
| md | 16px | Banner inner padding |
| lg | 24px | Section spacer between banner and grid |
| xl | 32px | Banner outer margins |
| 2xl | 48px | Empty state vertical padding |

Exceptions: none.

---

## Typography

Existing Tailwind type scale; no new type roles needed.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Body | 16px | 400 | 1.5 | Banner subtext |
| Label | 14px | 500 | 1.25 | Badge text, filter labels |
| Heading | 20px | 600 | 1.2 | Banner heading |
| Caption | 12px | 400 | 1.5 | Timestamps, metadata |

---

## Color

Existing Tailwind color palette carries forward. Phase 5 introduces new semantic meanings for existing tokens.

| Role | Value | Usage |
|------|-------|-------|
| Warning | `warning` / `amber` / `#D4A574` | Frozen badge background, Frozen banner background |
| Muted foreground | `muted-foreground` / `#636E72` | "Grades locked" descriptive text |
| Destructive | `destructive` | Not used in Phase 5 |

**Warning/amber reserved for:** Frozen badge on session cards, Frozen banner background, Lock icon color.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| **Frozen badge text** | "Frozen" — displayed on session card when `status === "completed"` |
| **Frozen banner heading** | "Grades Frozen — Session Completed" |
| **Frozen banner body** | "This session's grades are locked. Scores are read-only." |
| **Input title tooltip** | "Session completed — scores are frozen" |
| **Empty state** (no frozen sessions) | Not applicable — badge only appears when relevant |

---

## Component Inventory & Modifications

### Modified Components

| Component | File | Change |
|-----------|------|--------|
| `ScoreGrid` | `frontend/src/components/academics/score-grid.tsx` | Add amber "Grades Frozen — Session Completed" banner above the toolbar when `disabled=true` AND session is completed. Disable all toolbar buttons (Download, Import, Rollup, Save All) when `disabled=true`. Inputs already get `disabled={disabled}` with `opacity-60 cursor-not-allowed` — add `title="Session completed — scores are frozen"` to each cell. |
| Session cards | `frontend/src/routes/_dashboard/academics.tsx` | Show a Lock icon + "Frozen" Badge (`variant="outline"` with amber styling) on session cards when `session.status === "completed"`. |
| Assessment rows | `academics.tsx` DataTable | Show a Lock icon + "Frozen" text in the status column when the assessment's session is completed (resolved via session lookup). |

### New Sub-Components

| Component | File | Description |
|-----------|------|-------------|
| `FrozenBanner` | `frontend/src/components/academics/frozen-banner.tsx` | Full-width amber/warning banner with Lock icon, "Grades Frozen — Session Completed" heading, and body text. Props: `isFrozen: boolean`. Renders `null` when `isFrozen` is false. Simple — no countdown, no override state. |

### Files NOT Modified

The following already work and need no changes:
- `TeacherSession` card component — already has frozen badge (check existing implementation)
- Backend `canModifyScore()` — already enforces read-only at app level
- Backend `POST /grade-override` — exists but not needed for this scope
- Backend `session.status` — already set correctly by Phase 4

---

## Interaction States

```
Session Status = "active" or "upcoming"
├── No freeze indicators
├── ScoreGrid: inputs enabled, toolbar enabled
└── Session card: no badge

Session Status = "completed"
├── FrozenBanner visible above ScoreGrid toolbar (amber/warning)
├── ALL ScoreGrid inputs disabled (opacity-60, cursor-not-allowed, title tooltip)
├── ALL ScoreGrid toolbar buttons disabled
├── Lock icon + "Frozen" Badge on session card
└── Lock icon in assessment status indicator
```

No override states, no countdown timers, no correction history.

---

## Accessibility Requirements

1. All disabled inputs must have `aria-disabled="true"` and `title` attribute indicating frozen state
2. Lock icon on FrozenBanner must have `aria-label="Grades frozen"`
3. "Frozen" Badge on session cards must have `aria-label="Session completed — grades frozen"`

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | `Button`, `Badge`, `Card`, `Input` | not required |

No third-party registries or blocks. All needed components already exist.

---

## Files Modified or Created

### Modified:
1. `frontend/src/components/academics/score-grid.tsx` — Add FrozenBanner, disable toolbar on frozen
2. `frontend/src/routes/_dashboard/academics.tsx` — Add Frozen badge + Lock icon on completed session cards

### New:
1. `frontend/src/components/academics/frozen-banner.tsx` — Frozen status banner component

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
