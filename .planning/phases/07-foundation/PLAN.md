---
phase: 07-foundation
phase_number: 01
milestone: v2.0
status: pending
started:
completed:
---

# Phase 1: Foundation — Enhanced BaseModel + UUID Utilities

## Goal
Create the foundation for the UUID migration: enhanced BaseModel with dual-ID support (uint + uuid), model interfaces, UUID utilities, and pgcrypto setup. No existing code changes — this is purely additive.

## Deliverables

### 1. Enhanced BaseModel (`internal/database/models/base.go`)
- Add `UUID uuid.UUID` field alongside existing `ID uint`
- Add audit fields: `CreatedBy *uuid.UUID`, `UpdatedBy *uuid.UUID`
- Add `IsSystem bool` flag
- `BeforeCreate` hook: auto-generate UUID, set CreatedAt/CreatedBy
- `BeforeUpdate` hook: set UpdatedAt/UpdatedBy
- `GetID() uuid.UUID` helper method
- `GetTableName() string` interface method

### 2. Model Interfaces (`internal/database/models/interfaces.go`)
- `Model` interface: GetTableName, BeforeCreate, BeforeUpdate, Validate, GetID
- `TenantAwareModel` interface: Model + GetTenantID, SetTenantID
- `Auditable` interface: GetCreatedBy, GetUpdatedBy

### 3. UUID Utilities (`internal/database/uuid/`)
- `GenerateUUID() uuid.UUID` wrapper
- `ParseUUID(s string) (uuid.UUID, error)` wrapper
- `IsValidUUID(s string) bool` validation
- `UUIDFromBytes(b []byte) (uuid.UUID, error)` helper

### 4. UUID Module Package
- Package `internal/database/uuid` (or extend existing)

### 5. Pgcrypto Extension Setup (migration)
- Migration to enable `pgcrypto` extension (for `uuid_generate_v4()`)
- Update `internal/database/migrations/core/phase1.go` to include pgcrypto

## Test Plan
- BaseModel UUID generation: nonce uniqueness, BeforeCreate fires
- UUID utilities: roundtrip Parse/Generate, invalid UUID rejection
- Pgcrypto migration: verify SQL executes

## Files to Create/Modify
- `backend/internal/database/models/base.go` — modify (add UUID fields)
- `backend/internal/database/models/interfaces.go` — new
- `backend/internal/database/uuid/uuid.go` — new
- `backend/internal/database/uuid/uuid_test.go` — new
- `backend/internal/database/migrations/core/phase1.go` — modify (add pgcrypto)

## Validation
- `go build ./...` passes
- `go test ./internal/database/models/...` passes
- `go test ./internal/database/uuid/...` passes
- UUIDs are generated on BeforeCreate
