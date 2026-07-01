# Phase 5: API Compatibility - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 05-api-compatibility
**Areas discussed:** Route param ID strategy, Request body ID fields, Query param handling, Service/repo layer impact, Migration scope

---

## Route Param ID Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid parser | Single `helpers.ParseParamID()` — tries UUID first, falls back to uint64 | ✓ |
| Dual route params | Separate `:id` and `:uuid` params with distinct routes | |
| Type-prefixed | Accept both in same param via string detection | |

**User's choice:** Hybrid parser (recommended)
**Notes:** User selected recommended approach. Minimal disruption to existing handler pattern.

---

## Request Body ID Fields

| Option | Description | Selected |
|--------|-------------|----------|
| Dual fields | Add `*uuid.UUID` fields alongside existing `uint` fields in DTOs | ✓ |
| String fields with custom unmarshaler | Custom type that parses both uint and UUID | |
| Separate UUID-specific DTOs | New DTOs for UUID-based requests | |

**User's choice:** Dual fields (recommended)
**Notes:** User selected recommended approach. Keeps existing serialization intact while adding UUID support.

---

## Query Param Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Same hybrid parser | `helpers.ParseQueryID()` consistent with route params | ✓ |
| Separate UUID query params | `level_uuid` alongside `level_id` | |

**User's choice:** Same hybrid parser (recommended)
**Notes:** Consistent with route param approach.

---

## Service/Repo Layer Impact

| Option | Description | Selected |
|--------|-------------|----------|
| Repo-level resolution | Repository `FindByID(where)` takes either uint or uuid | ✓ |
| Service dual-methods | Separate `GetByID` + `GetByUUID` on services | |
| Service-level resolution | Pass generic identifier type through services | |

**User's choice:** Repo-level resolution (recommended)
**Notes:** Minimal service changes — existing `GetByID(uint)` remains, new `FindByID(*ResourceID)` at repo level.

---

## Migration Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All-at-once with utility | Create parser utility, batch-convert all 38 handlers | ✓ |
| Per-module phased | Convert module by module across multiple sub-plans | |

**User's choice:** All-at-once (recommended)
**Notes:** Single plan covering all handlers. The utility function makes this feasible — each handler change is a mechanical replacement.

---

## Deferred Ideas

- Removing uint ID support — Phase 6
- API contract documentation — Phase 6
- Logging/metrics for ID type tracking — Phase 6
- Client migration guide — Phase 6
