# Phase 5: API Compatibility - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning
**Source:** Codebase analysis + user discussion

<domain>
## Phase Boundary

**Goal:** Accept both UUID and int IDs in route params, query params, and request bodies. Create a centralized ID parsing utility and update all handler files to use it.

**What this phase delivers:**
1. Centralized ID parsing utility (`helpers.ParseParamID`, `helpers.ParseQueryID`)
2. All ~120+ route/query param `strconv.ParseUint` call sites replaced with the hybrid parser
3. DTOs updated to accept both uint and UUID ID fields where applicable
4. Service/repository layer updated to resolve records by either ID type
5. `go build ./...` and `go vet ./...` pass clean

**What this phase does NOT deliver:**
- Removing uint ID support (Phase 6 handles eventual decommission)
- Data migration between ID schemes
- New API endpoints or features
- Documentation of the dual-ID API contract (logging/monitoring of transition — Phase 6)

</domain>

<decisions>
## Implementation Decisions

### Route and Query Param ID Parsing
- **D-01:** Create a single `helpers.ParseParamID(c *gin.Context, paramName string) (*ResourceID, error)` function that tries UUID parse first, falls back to `strconv.ParseUint(raw, 10, 64)`
- **D-02:** Create `helpers.ParseQueryID(c *gin.Context, queryName string) (*ResourceID, error)` — same hybrid logic for query params
- **D-03:** Return a `ResourceID` struct (`{ UintID uint64, UUID uuid.UUID }`) — handlers pass this to services, which resolve whichever is set
- **D-04:** Use consistent 64-bit parsing (match existing `10, 64` usage, not the inconsistent `10, 32` pattern)
- **D-05:** Centralized error handling — invalid params return consistent `appErr.NewBadRequestError("invalid id")`

### Request Body ID Fields
- **D-06:** Dual-field pattern on DTOs: keep existing `uint` fields and add optional `*uuid.UUID` fields alongside
  ```go
  LevelID  uint        `json:"level_id"`
  LevelUUID *uuid.UUID `json:"level_uuid,omitempty"`
  ```
- **D-07:** Service layer checks: if UUID field is set → resolve by UUID; otherwise use uint
- **D-08:** Apply dual-field pattern only to DTOs where UUID-based lookup makes sense (reference IDs to other entities — level, school, subject, student, teacher, etc.)

### Service and Repository Layer
- **D-09:** Repository methods gain a `FindByID(uid *ResourceID)` variant that performs `WHERE id = ? OR uuid = ?` queries
- **D-10:** Existing `FindByID(id uint)` methods remain for backward compatibility and internal use (no refactor of all service logic)
- **D-11:** Repositories determine which field to query based on `ResourceID.UUID` being nil vs set — clean single responsibility

### Migration Scope
- **D-12:** Apply changes across ALL 38 handler files in a single pass (not per-module phased)
- **D-13:** Only update handler files (param parsing) + DTOs (dual fields) + repository (FindByID) — service layer changes are minimal
- **D-14:** Coverage target: all route params that reference entity IDs, all query params filtering by entity ID, all request body DTOs with entity reference fields

### the agent's Discretion
- Exact `ResourceID` struct name and package location (within `internal/helpers/`)
- Whether to add a `helpers.ParseBodyID` or handle body resolution in service layer directly
- Which specific DTOs get dual fields vs which are low-value (e.g., rarely used report config DTOs)
- Exact naming of new repository method (`FindOne`, `Resolve`, `FindByResourceID`)
- Whether to add a `UUID` helper to `helpers` package or reuse existing `internal/database/uuid/`
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Handler patterns (read 2-3 for pattern reference)
- `backend/internal/modules/user/handler.go` — Representative handler with route params, query params, body binding
- `backend/internal/modules/school/handler.go` — Shows `10, 32` inconsistency, named params (`:roleId`)
- `backend/internal/modules/score/handler.go` — Multiple optional query param ID filters pattern

### DTO patterns
- `backend/internal/modules/user/dto.go` — DTOs with `uint` ID fields needing dual-field treatment
- `backend/internal/modules/auth/dto.go` — DTO with `[]uint` slice IDs (`BatchDeleteTokensRequest`)

### Existing utilities
- `backend/internal/helpers/helpers.go` — Existing helper pattern (GetUserID, GetSchoolID, etc.)
- `backend/internal/database/uuid/uuid.go` — Existing UUID parse utility (may reuse or wrap)

### Middleware (dual-ID pattern reference)
- `backend/internal/middleware/auth.go` — Shows existing dual-ID context keys (`CtxKeyUserID` + `CtxKeyUserUUID`)
- `backend/internal/middleware/schoolid.go` — Dual-ID header pattern (`x-school-id` / `x-school-uuid`)

### Model layer
- `backend/internal/database/models/base.go` — BaseModel with both `ID uint` and `UUID uuid.UUID`

### Migration/state tracking
- `.planning/phases/04-sql-to-gorm/04-CONTEXT.md` — Prior phase context (decisions carried forward)
- `.planning/STATE.md` — Current project state
- `.planning/PROJECT.md` — Guiding principles (esp. "API backward compatibility during transition")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/internal/helpers/helpers.go` — Existing pattern for context value extractors — new ID parsing utility fits here
- `backend/internal/database/uuid/uuid.go` — `ParseUUID()` and `IsValidUUID()` functions ready to use
- `backend/internal/middleware/auth.go` lines 20-28 — Dual-ID context key pattern (`CtxKeyUserID` + `CtxKeyUserUUID`) is the precedent to follow
- `backend/internal/helpers/helpers.go` — `ParsePagination()` demonstrates a centralized param parsing utility pattern

### Established Patterns
- **Handler pattern**: Every handler calls `c.Param("id")` + `strconv.ParseUint` → service call → response
  - Adding a `helpers.ParseParamID("id")` call is a drop-in replacement
- **Service pattern**: Most services accept `uint` IDs — minimal change needed (just `FindByID` at the repo layer)
- **DTO pattern**: `json` struct tags with `binding:"required"` — dual fields need `omitempty` on UUID fields
- **Error pattern**: `appErr.NewBadRequestError("invalid ...")` with `helpers.SendError` — consistent and reusable

### Integration Points
- All 38 handler.go files — each has at least 2-10 `strconv.ParseUint` call sites needing replacement
- All DTO files — dual-field additions needed on reference ID fields
- Repository files — new `FindByID(uid *ResourceID)` method for GORM queries
- Router file (`backend/internal/router/router.go`) — no changes needed (routes stay the same, only param parsing changes)

</code_context>

<specifics>
## Specific Ideas

- "Keep it simple — a single utility function per param type, all handlers updated in one pass"
- Follow the existing dual-ID pattern from middleware (uint + UUID context keys) as precedent for the handler layer
- The `ResourceID` approach keeps handler changes minimal: replace `strconv.ParseUint` lines with `helpers.ParseParamID` calls

</specifics>

<deferred>
## Deferred Ideas

- Removing uint ID support entirely — Phase 6 (Validation & Rollout)
- API contract documentation for the transition period — Phase 6
- Logging/metrics tracking which ID type each request uses — Phase 6
- Client migration guide — Phase 6

</deferred>

---

*Phase: 05-api-compatibility*
*Context gathered: 2026-07-01*
