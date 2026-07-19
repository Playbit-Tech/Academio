---
phase: 5
slug: gradebook-hardening
status: draft
shadcn_initialized: true
preset: shadcn default (tailwind.config.js + components.json)
created: 2026-07-19
---

# Phase 5 — Gradebook Hardening: UI Design Contract

> Visual and interaction contract for grade freeze indicators, admin override workflow, and correction history. All Phase 5 UI lives inside the existing `teacher.academics.tsx` route and `ScoreGrid` component — no new standalone pages.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn/ui |
| Preset | Tailwind CSS with CSS variables (`--primary`, `--muted-foreground`, `--destructive`, etc.) |
| Component library | Radix UI (via shadcn) |
| Icon library | lucide-react |
| Font | Inter (system font stack fallback) |

**Existing shadcn components in use:** `Button`, `Badge`, `Card`, `Tabs`, `TabsContent`, `TabsList`, `TabsTrigger`, `Select`, `SelectTrigger`, `SelectContent`, `SelectItem`, `SelectValue`, `Input`, `Textarea`, `Label`, `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle`, `SheetDescription`, `SheetTrigger`, `AlertDialog`, `AlertDialogAction`, `AlertDialogCancel`, `AlertDialogContent`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogHeader`, `AlertDialogTitle`, `DataTable`, `Table`, `Separator`, `Sonner` (toast), `EmptyState`, `StatCard`, `Loading`, `Switch`, `Popover`, `Progress`, `Form`, `Field`.

---

## Spacing Scale

Existing Tailwind spacing tokens; no phase-specific exceptions.

| Token | Value | Usage in Phase 5 |
|-------|-------|-------------------|
| xs | 4px | Icon gaps in freeze badge, status indicator padding |
| sm | 8px | Badge spacing, compact row gaps |
| md | 16px | Correction history card padding, banner padding |
| lg | 24px | Section spacer between banner and grid |
| xl | 32px | Dialog padding, layout gaps |
| 2xl | 48px | Empty state vertical padding |
| 3xl | 64px | Page-level spacing (reuse existing) |

Exceptions: none.

---

## Typography

Existing Tailwind type scale; reuse all current token values. No new type roles needed for Phase 5.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Body | 16px | 400 | 1.5 | Correction history table cells, banner subtext |
| Label | 14px | 500 | 1.25 | Filter labels, dialog section headers |
| Heading | 20px | 600 | 1.2 | Dialog titles, panel section headings |
| Display | 24px | 700 | 1.2 | Page title (reuse existing) |
| Caption | 12px | 400 | 1.5 | Timestamps, metadata, badge text |

---

## Color

Existing Tailwind color palette carries forward. Phase 5 introduces new semantic meanings for existing tokens.

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `background` (#F9F8F3) | Page background, surfaces |
| Secondary (30%) | `background-card` (#FFFFFF) / `muted` / `card` | Correction history card, banner container, dialog |
| Accent (10%) | `primary` (#A5A78F) , `secondary` (#FF7E5F) | Primary: CTA buttons, active assessment badge, Frozen state indicator borders. Secondary: Override Active badge, override timer |
| Destructive | `error` (#C87F7F) / `destructive` | Destructive actions only — discarding unsaved scores, revoking override |
| Warning | `warning` (#D4A574) / `amber` | Frozen state badge background, alert banner, `recalc_needed` warning |
| Success | `success` (#6B8E5A) / `green` | Saved indicator, Override Active confirmation |
| Info | `info` (#7B9AA1) / `muted-foreground` (#636E72) | Secondary text, metadata labels |

**Accent reserved for:** Override Grade Freeze button, Override Active badge, Frozen badge, Enable Override button, correction history "View Diff" button, session card Frozen status badge, recalc_needed warning badge.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| **Primary CTA** (admin override) | "Override Grade Freeze" — button label in ScoreGrid toolbar, visible only to admin/principal roles when session status is `completed` and no active override exists |
| **Override confirm title** | "Override Grade Freeze?" |
| **Override confirm body** | "This will allow score modifications for 24 hours. Only use for corrections. A reason is required for audit." |
| **Override confirm action** | "Override for 24h" |
| **Override reason placeholder** | "Required: Reason for override (e.g. 'Principal-approved grade correction for Mathematics CA')" |
| **Correction reason placeholder** (per score save) | "Reason for correction (e.g. 'Data entry error — score should be 7.5 instead of 6.0')" |
| **Correction reason label** | "Correction Reason" |
| **Frozen banner heading** | "Grades Frozen — Session Completed" |
| **Frozen banner body** | "This session's grades are locked. Contact an administrator to enable corrections." |
| **Override active banner heading** | "Grade Override Active" |
| **Override active banner body** | "Scores can be edited for {time remaining}. All changes are logged to the correction audit trail." |
| **Empty state heading** (correction history) | "No Corrections Recorded" |
| **Empty state body** | "Grade corrections for this session will appear here once an admin enables the override and modifies scores." |
| **Error state** (override failed) | "Failed to override grade freeze. The session may already have an active override, or your role lacks permission." |
| **Error state** (correction save failed) | "Failed to save correction. Reason is required. Check your connection and try again." |
| **Destructive confirmation** (discard pending override) | "Discard unsaved scores? You have unsaved score changes. Discarding will remove them." |
| **Recalc warning badge** | "Recalculation Needed" — tooltip: "Grade items have changed. Run rollup to recalculate assessment totals." |
| **Correction history panel title** | "Correction History" |
| **Correction diff column labels** | "Before", "After" |
| **Correction metadata labels** | "Corrected by", "Date", "Reason" |

---

## Component Inventory & Modifications

### 05-03: Grade Freeze Indicators (modify existing components)

| Component | File | Change |
|-----------|------|--------|
| `ScoreGrid` | `frontend/src/components/academics/score-grid.tsx` | Add prominent "Grades Frozen — Session Completed" banner above the table toolbar when `disabled=true` AND session is completed (not just disabled for other reasons). Banner uses amber/warning color, Lock icon, and descriptive text. |
| `ScoreGrid` toolbar | `score-grid.tsx` | Disable "Download Excel", "Import Excel", "Rollup All", "Save All" buttons when `disabled=true`. Buttons already accept `disabled` prop — ensure ALL toolbar buttons pass it. |
| `ScoreGrid` cell comments | `score-grid.tsx` | Disable comment popover button when `disabled=true`. |
| `ScoreGrid` input cells | `score-grid.tsx` | Inputs already get `disabled={disabled}` and show `opacity-60 cursor-not-allowed` styling. Add `title` attribute: "Session completed — scores are frozen" (already present). Add aria-label for screen readers: "Score input — currently frozen". |
| `TeacherSession` | `teacher.academics.tsx` | Already shows Lock icon + Frozen badge when `session.status === "completed"`. Already shows Override Active badge when override is active. **No change needed** — already implemented. |
| `ScoreGridWrapper` | `teacher.academics.tsx` | Already passes `disabled`, `isFrozen`, `isGradeOverridden`, `gradeOverrideExpiresAt` props. Already shows frozen/override badges in toolbar. **No change needed** — already implemented. |

**New sub-components for 05-03:**

| Component | File | Description |
|-----------|------|-------------|
| `FrozenBanner` | `frontend/src/components/academics/frozen-banner.tsx` | Full-width amber/warning banner with Lock icon, "Grades Frozen — Session Completed" heading, and descriptive body text. Props: `isFrozen: boolean`, `isOverridden: boolean`, `overrideExpiresAt?: string`. Renders null when neither frozen nor overridden. |
| `RecalcWarningBadge` | `frontend/src/components/academics/recalc-warning-badge.tsx` | Badge with `recalc_needed` flag from assessment model. Shows "Recalculation Needed" with tooltip when true. Triggers rollup suggestion. |

### 05-04: Versioned Grade Corrections (modify existing + new components)

**Existing (already implemented in teacher.academics.tsx):**

| Element | Location | Status |
|---------|----------|--------|
| "Override Grade Freeze" button | `ScoreGridWrapper` toolbar | ✅ Already implemented, admin-only via `isAdmin && isFrozen && !isGradeOverridden` |
| Override confirmation dialog | `ScoreGridWrapper` below toolbar | ✅ Already implemented as AlertDialog |
| `POST /academic/session/:id/grade-override` call | `ScoreGridWrapper` handleGradeOverride | ✅ Already implemented |
| Override active badge + countdown | `ScoreGridWrapper` toolbar | ✅ Already implemented |
| `isGradeOverridden` + `inputDisabled` logic | `TeacherAssessment` component | ✅ Already implemented |

**New additions needed for 05-04:**

| Component | File | Description |
|-----------|------|-------------|
| `OverrideReasonDialog` | New: `frontend/src/components/academics/override-reason-dialog.tsx` | Enhanced replacement for the existing override confirmation. Adds a `Textarea` field for correction reason (required). Fields: reason textarea (required), confirmation checkbox "I understand this bypasses grade freeze". Submit calls existing `/grade-override` endpoint. Reason is stored in the first correction log entry. |
| `CorrectionReasonField` | Inline in `ScoreGrid` | When `isGradeOverridden` is true, add an expandable reason field in the score save flow. After clicking "Save All", if dirty scores exist and override is active, show a modal/banner asking for a correction reason before saving. Reason is sent with the bulk save payload. |
| `CorrectionHistoryPanel` | New: `frontend/src/components/academics/correction-history-panel.tsx` | Sheet drawer showing audit trail for grade corrections. Triggered by "View Correction History" button in ScoreGrid toolbar (visible when corrections exist). Shows a DataTable or card list with columns: Date, Admin, Before, After, Reason. Data sourced from `GET /academic/scores/:assessmentId/corrections` endpoint. |
| Correction history button | `ScoreGridWrapper` toolbar | "View Corrections" button (Badge variant outline) — visible when `isGradeOverridden` OR when correction count > 0. Opens `CorrectionHistoryPanel` Sheet. |

**Session model additions (already on backend — just need frontend types):**

The `Session` interface in `useAcademics.ts` already has:
```typescript
grade_override?: boolean;
grade_override_expires_at?: string;
```
No frontend type changes needed.

**New types needed in useAcademics.ts:**

```typescript
export interface GradeCorrection {
  id: number;
  score_id: number;
  admin_id: number;
  admin_name?: string;          // resolved from user_info
  before: Record<string, number>;  // snapshot of Score.Score before edit
  after: Record<string, number>;   // snapshot after edit
  reason: string;
  created_at: string;
}
```

**New hooks needed:**

| Hook | Endpoint | Description |
|------|----------|-------------|
| `useCorrectionHistory(assessmentId)` | `GET /academic/scores/:assessmentId/corrections` | Fetch correction history for an assessment |
| `useSaveScoreWithCorrection()` | `POST /academic/scores/bulk` (extended) | Extended bulk save that accepts optional `correction_reason` field |

---

## Interaction States

### Grade Freeze State Machine

```
Session Status = "active"
├── Edits allowed (normal)
├── Toolbar: Save All, Rollup, Download, Import — all enabled
└── No freeze indicators shown

Session Status = "completed" AND no override
├── Edits blocked (frozen)
├── FrozenBanner visible (amber/warning)
├── ALL inputs disabled (opacity-60, cursor-not-allowed)
├── ALL toolbar buttons disabled
├── Lock icon + "Frozen" badge in toolbar
├── "Override Grade Freeze" button visible to admin/principal
└── "View Corrections" button visible (if corrections exist)

Session Status = "completed" AND override active (grade_override=true, not expired)
├── Edits allowed (24h window)
├── OverrideActiveBanner visible (green/info)
├── INPUTS re-enabled
├── Toolbar buttons re-enabled
├── ShieldAlert icon + "Override Active" badge + countdown timer
├── Correction reason required before save
├── "View Corrections" button visible
└── Automatic re-freeze when 24h expires (frontend checks via session data)

Session Status = "completed" AND override expired
├── Same as frozen state (no override)
└── Admin can request new override
```

### Correction History Panel States

| State | Behavior |
|-------|----------|
| **Loading** | Skeleton or spinner inside Sheet |
| **Empty** | "No corrections recorded" empty state with icon |
| **Has data** | DataTable with Date, Admin, Before, After, Reason columns |
| **Error** | Toast: "Failed to load correction history" |
| **Admin name not resolved** | Fallback to `Admin #{admin_id}` |

---

## Accessibility Requirements

1. **Frozen state** — all disabled inputs must have `aria-disabled="true"` and `aria-label` indicating frozen state. Current `disabled` prop on `<Input>` already provides this for keyboard users.
2. **Lock icon** — add `aria-label="Grades frozen"` to the Lock icon in FrozenBanner.
3. **Override countdown** — the countdown timer text `Expires ${date}` must be wrapped in a `<time>` element with `datetime` attribute for machine parsing.
4. **Correction reason** — the reason textarea in override dialog must have `aria-required="true"` and `aria-describedby` linking to the description text.
5. **Correction history** — DataTable must support keyboard navigation (existing DataTable pattern). Before/After diff cells should use `<del>` and `<ins>` semantic elements for screen readers.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | `Button`, `Badge`, `Card`, `AlertDialog`, `Sheet`, `DataTable`, `Table`, `Textarea`, `Input`, `Label` | not required |

No third-party registries or blocks. All needed components already exist in the project.

---

## Files Modified or Created

### Modified files:
1. `frontend/src/components/academics/score-grid.tsx` — Add FrozenBanner, disable all toolbar buttons on frozen, add correction reason flow
2. `frontend/src/routes/_dashboard/teacher.academics.tsx` — Already has freeze indicators and override. Add "View Corrections" button, integrate CorrectionHistoryPanel.
3. `frontend/src/lib/hooks/useAcademics.ts` — Add `GradeCorrection` type, `useCorrectionHistory` hook, extend `useBulkSaveScores` to accept `correction_reason`.

### New files:
1. `frontend/src/components/academics/frozen-banner.tsx` — Frozen/override status banner component
2. `frontend/src/components/academics/override-reason-dialog.tsx` — Override confirmation with reason field
3. `frontend/src/components/academics/correction-history-panel.tsx` — Sheet-based correction history audit trail

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
