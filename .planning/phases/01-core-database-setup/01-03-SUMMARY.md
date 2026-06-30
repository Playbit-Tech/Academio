# 01-03: DatabaseConnectionManager

**Status:** Complete
**Completed:** 2026-06-29

## What was built

- `backend/internal/database/tenant/config.go` — `Config` struct with defaults (30s health check, 5min max lifetime, 25 pool size)
- `backend/internal/database/tenant/connection_manager.go` — `ConnectionManager` with:
  - Thread-safe connection cache using `sync.RWMutex` + `map[uint]*gorm.DB`
  - `GetTenantDB(schoolID)` with fast path (cache hit) and slow path (build new connection)
  - `buildConnection()`: fetches SchoolConnection from core DB, decrypts credentials, creates GORM connection, configures pool, pings, caches
  - `CloseTenantDB(schoolID)`: closes and evicts a single connection
  - `CloseAll()`: closes and clears all cached connections
  - `Stats()`: returns connection count for monitoring
  - Background health check loop via `time.Ticker` every 30s, evicts failed connections

## Key design decisions

- **`sync.RWMutex` + `map[uint]*gorm.DB`** (not `sync.Map`): explicit eviction control for credential rotation and health check failures
- **Double-check locking**: `RLock` → check → `RUnlock` → `Lock` → check again → build (prevents redundant connections)
- **AAD binding**: Credential decryption uses school ID as AAD via `crypto.Service`
- **Pool sizing**: Respects school-level `connection_pool_size` with floor of 5
- **Health check**: 5-second PingContext timeout, evicts on failure, next request rebuilds fresh

## Dependencies

- 01-01: EncryptionService (for credential decryption)
- 01-02: Schema Migration (for database_connections table)
