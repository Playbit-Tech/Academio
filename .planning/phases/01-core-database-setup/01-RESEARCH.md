# Phase 1: Core Database Setup - Research

**Researched:** 2026-06-29
**Domain:** Multi-tenant database infrastructure (encryption, schema migration, connection management, repository factory)
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundation for SchoolCare v2's database-per-tenant architecture. The existing codebase has 30+ modules all using a single GORM connection (`*gorm.DB` singleton from `database.MustConnect`), with well-established patterns for repositories (interface + struct + constructor), migrations (raw SQL via `CREATE TABLE IF NOT EXISTS`), and configuration (env-based `Config` struct). No existing AES encryption or connection pooling infrastructure exists — these must be built from scratch following Go stdlib patterns.

**Primary recommendation:** Create `internal/crypto/` for EncryptionService, a new migration file `internal/database/migrations/phase_multitenant.go`, `internal/database/tenant/connection_manager.go` for the connection manager, and `internal/database/tenant/factory.go` for the repository factory. The `internal/database/tenant/` package aligns with the existing module structure and keeps multi-tenant infrastructure together.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Must maintain backward compatibility during migration
- Zero downtime deployment required
- All existing SchoolID-based row isolation must continue working
- Must support gradual per-school rollout
- Credential encryption required (never store plaintext DB passwords)

### the agent's Discretion
- Package naming and location decisions
- Encryption key management approach (env var vs KMS)
- Migration timing strategy (pre-apply vs on-demand)
- Health check interval and connection pool sizing defaults

### Deferred Ideas (OUT OF SCOPE)
- Phase 2+ concerns (repository refactoring across modules, tenant context middleware, per-school migration system)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **GSD-R1** | EncryptionService (AES-256-GCM encrypt/decrypt for DB credentials) | Go stdlib `crypto/aes` + `crypto/cipher` supports AES-256-GCM natively. Create `internal/crypto/` package. Key loaded from `ENCRYPTION_KEY` env var (must be 32 bytes hex-encoded). Nonce generated via `crypto/rand`. |
| **GSD-R2** | Schema migration (schools enhancement + database_connections + tenant_backups tables) | Current `School` model has only 6 user-facing fields. Must add 7 new columns via raw SQL `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (due to FK-owner issue with the `schools` table). Two new tables via `CREATE TABLE IF NOT EXISTS`. Migration function registered in `migrations.go` `New()`. |
| **GSD-R3** | DatabaseConnectionManager (sync.Map cache, GORM pool, health checks) | Follow existing `database.Connect()` pattern in `database/postgres.go` for creating GORM connections. Use `sync.Map` for thread-safe cache. Health checks via `sql.DB.Ping()` with configurable interval. Connection pool settings from `Config.DBConfig`. |
| **GSD-R4** | RepositoryFactory pattern (bridge to Phase 2) | Follow existing repository pattern (interface + struct + `New*Repository(db *gorm.DB)`). Factory returns tenant-aware repositories, accepting either `*gorm.DB` directly or `schoolID uint` for dynamic resolution. Unimplemented types return `ErrRepositoryNotImplemented`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Go stdlib `crypto/aes` | (stdlib) | AES-256 encryption | No external dependency needed; Go's stdlib is FIPS-140 certified and well-reviewed |
| Go stdlib `crypto/cipher` | (stdlib) | GCM mode (AEAD) | Required pairing with AES; provides authenticated encryption |
| Go stdlib `crypto/rand` | (stdlib) | Cryptographic nonce generation | Only stdlib source for secure random bytes |
| `sync.Map` | (stdlib) | Thread-safe connection cache | Built-in concurrent map; no external dependency; proven in high-concurrency patterns |
| `gorm.io/gorm` (existing) | v1.30.0 | ORM for database connections | Already in use across the entire codebase |
| `gorm.io/driver/postgres` (existing) | v1.5.9 | PostgreSQL driver | Already in use; must use same version |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `encoding/hex` | (stdlib) | Encryption key hex encoding/decoding | For loading the 32-byte key from env var |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `internal/crypto/` | `pkg/encryption/` | Both are valid; `pkg/` is for reusable external-facing packages while `internal/crypto/` is for internal-only. Since EncryptionService is consumed only by internal packages (ConnectionManager), `internal/` is correct. |
| `sync.Map` | `map[uint]*gorm.DB` + `sync.RWMutex` | `sync.Map` is simpler and proven; `RWMutex+map` gives more control over eviction. Use `sync.Map` for v1, optimize later if needed. |
| Raw SQL migrations | GORM AutoMigrate | AutoMigrate fails on `schools` table (FK-owner issue documented in `phase_modules.go` comment). Must use raw SQL for schools enhancement. `CREATE TABLE IF NOT EXISTS` works for new tables. |

**Version verification:**
```bash
# Already confirmed from go.mod:
gorm.io/gorm v1.30.0
gorm.io/driver/postgres v1.5.9
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── internal/
│   ├── crypto/                          # NEW: EncryptionService
│   │   └── encryption.go                # AES-256-GCM encrypt/decrypt
│   │
│   ├── database/
│   │   ├── postgres.go                  # EXISTING: GORM connection setup
│   │   ├── ...
│   │   └── tenant/                      # NEW: Multi-tenant infrastructure
│   │       ├── connection_manager.go    # DatabaseConnectionManager (sync.Map, GORM pool, health checks)
│   │       └── factory.go              # RepositoryFactory pattern
│   │
│   └── router/
│       └── setup.go                     # WILL UPDATE: wire ConnectionManager + Factory
│
├── cmd/server/
│   └── main.go                          # WILL UPDATE: init ConnectionManager, pass to router
```

### Pattern 1: EncryptionService (GSD-R1)
**What:** AES-256-GCM encryption service for database credentials. Encrypts before storing in `schools.database_password_encrypted`; decrypts before creating tenant GORM connections.

**When to use:** Every time a tenant DB connection needs to be established or credentials stored.

**Key design decisions:**
- **Key management:** Encryption key loaded from `ENCRYPTION_KEY` env var (64 hex chars = 32 bytes). In production, use a KMS (Vault, AWS KMS) but for Phase 1 env var is sufficient.
- **Nonce:** 12-byte random nonce generated by `crypto/rand` per encryption operation. Prepend to ciphertext.
- **Additional Data (AAD):** Include school ID as AAD to bind ciphertext to a specific tenant.
- **Output format:** `base64(nonce || ciphertext || tag)` — single string for DB storage.

```go
// Package crypto provides AES-256-GCM encryption for sensitive data.
// Source: Go stdlib documentation
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
)

const (
	// KeySize is the required AES-256 key length (32 bytes).
	KeySize = 32
	// NonceSize is the standard GCM nonce length (12 bytes).
	NonceSize = 12
)

// Service provides AES-256-GCM encryption and decryption.
type Service struct {
	key []byte
}

// NewService creates a new encryption service with the given hex-encoded 32-byte key.
func NewService(hexKey string) (*Service, error) {
	key, err := hex.DecodeString(hexKey)
	if err != nil {
		return nil, fmt.Errorf("crypto: invalid encryption key hex: %w", err)
	}
	if len(key) != KeySize {
		return nil, fmt.Errorf("crypto: encryption key must be %d bytes (got %d)", KeySize, len(key))
	}
	return &Service{key: key}, nil
}

// Encrypt encrypts plaintext with AES-256-GCM. AAD (additional authenticated data)
// is optional but recommended (pass school ID as AAD to bind ciphertext to tenant).
// Returns base64(nonce || ciphertext || tag).
func (s *Service) Encrypt(plaintext []byte, aad []byte) (string, error) {
	block, err := aes.NewCipher(s.key)
	if err != nil {
		return "", fmt.Errorf("crypto: create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("crypto: create GCM: %w", err)
	}

	nonce := make([]byte, NonceSize)
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("crypto: generate nonce: %w", err)
	}

	// Seal appends: nonce || ciphertext || tag
	ciphertext := gcm.Seal(nil, nonce, plaintext, aad)

	// Prepend nonce to ciphertext for storage
	result := append(nonce, ciphertext...)
	return base64.StdEncoding.EncodeToString(result), nil
}

// Decrypt decrypts a base64(nonce || ciphertext || tag) string.
func (s *Service) Decrypt(encoded string, aad []byte) ([]byte, error) {
	data, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, fmt.Errorf("crypto: decode base64: %w", err)
	}

	if len(data) < NonceSize+1 {
		return nil, errors.New("crypto: ciphertext too short")
	}

	nonce := data[:NonceSize]
	ciphertext := data[NonceSize:]

	block, err := aes.NewCipher(s.key)
	if err != nil {
		return nil, fmt.Errorf("crypto: create cipher: %w", err)
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("crypto: create GCM: %w", err)
	}

	plaintext, err := gcm.Open(nil, nonce, ciphertext, aad)
	if err != nil {
		return nil, fmt.Errorf("crypto: decrypt: %w", err)
	}

	return plaintext, nil
}
```

### Pattern 2: Schema Migration (GSD-R2)
**What:** A new migration function `MultiTenantMigrations()` returning `[]Migration` with:
1. **ALTER TABLE schools** to add 7 new columns (using `ADD COLUMN IF NOT EXISTS` for idempotency)
2. **CREATE TABLE database_connections** to track per-school connection metadata
3. **CREATE TABLE tenant_backups** to track backup history

**When to use:** Run as part of the standard migration pipeline in `migrations.go`.

**Critical constraint from codebase:** The `schools` table was created by the original Laravel migration and is owned by a different DB user. As documented in `phase_modules.go`:
> "Uses raw SQL CREATE TABLE IF NOT EXISTS because AutoMigrate tries to FK-enforce on the `schools` table which is owned by a different DB user. FK integrity is enforced at the application layer."

This means:
- **MUST use raw SQL** for `ALTER TABLE schools ADD COLUMN IF NOT EXISTS`
- **CANNOT use** `gorm.AutoMigrate(&models.School{})` for the enhanced School model
- **MUST use** `CREATE TABLE IF NOT EXISTS` for new tables (standard pattern)
- Index creation uses `CREATE INDEX IF NOT EXISTS` (already standard)

```go
// New columns to add to schools:
// database_name           VARCHAR(100)
// database_host           VARCHAR(255)
// database_port           INTEGER DEFAULT 5432
// database_username       VARCHAR(100)
// database_password_encrypted TEXT
// database_status         VARCHAR(20) DEFAULT 'shared'  -- shared|provisioning|active|failed|disabled
// connection_pool_size    INTEGER DEFAULT 25

// New tables:
// database_connections: school_id (FK), host, port, username, password_encrypted,
//     database_name, status, connected_at, disconnected_at, error_message,
//     is_primary, created_at, updated_at

// tenant_backups: school_id (FK), database_name, backup_type, status,
//     size_bytes, file_path, checksum, started_at, completed_at,
//     error_message, metadata (jsonb), created_at
```

### Pattern 3: DatabaseConnectionManager (GSD-R3)
**What:** Manages a cache of per-tenant GORM connections using `sync.Map`. Handles connection creation, health checks, and stale connection eviction.

**When to use:** Every time a tenant database connection is needed (replaces direct use of core `*gorm.DB` for tenant data).

```go
// Source: Based on existing database.Connect() pattern in postgres.go

type ConnectionManager struct {
	mu       sync.RWMutex
	pool     map[uint]*gorm.DB  // schoolID -> GORM connection
	config   Config
	encSvc  *crypto.Service
	coreDB  *gorm.DB  // core DB for looking up school connection details
}

func NewConnectionManager(cfg Config, encSvc *crypto.Service, coreDB *gorm.DB) *ConnectionManager {
	cm := &ConnectionManager{
		pool:    make(map[uint]*gorm.DB),
		config:  cfg,
		encSvc:  encSvc,
		coreDB:  coreDB,
	}
	// Start background health checker
	go cm.healthCheckLoop(cfg.HealthCheckInterval)
	return cm
}

func (cm *ConnectionManager) GetConnection(ctx context.Context, schoolID uint) (*gorm.DB, error) {
	// 1. Check cache (fast path)
	cm.mu.RLock()
	if db, ok := cm.pool[schoolID]; ok {
		cm.mu.RUnlock()
		return db, nil
	}
	cm.mu.RUnlock()

	// 2. Cache miss — build connection from school's credentials
	return cm.buildConnection(ctx, schoolID)
}

func (cm *ConnectionManager) buildConnection(ctx context.Context, schoolID uint) (*gorm.DB, error) {
	// Fetch school's DB credentials from core DB
	var school models.School
	if err := cm.coreDB.WithContext(ctx).First(&school, schoolID).Error; err != nil {
		return nil, fmt.Errorf("connection manager: school %d not found: %w", schoolID, err)
	}

	// Decrypt password
	password, err := cm.encSvc.Decrypt(school.DatabasePasswordEncrypted, []byte(fmt.Sprintf("%d", schoolID)))
	if err != nil {
		return nil, fmt.Errorf("connection manager: decrypt password for school %d: %w", schoolID, err)
	}

	// Build DSN
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		school.DatabaseHost, school.DatabasePort, school.DatabaseUsername,
		string(password), school.DatabaseName,
	)

	// Create GORM connection (same pattern as database.Connect)
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger:                 logger.Default.LogMode(logger.Warn),
		SkipDefaultTransaction: true,
		PrepareStmt:            true,
	})
	if err != nil {
		return nil, fmt.Errorf("connection manager: connect school %d: %w", schoolID, err)
	}

	// Configure pool
	sqlDB, _ := db.DB()
	poolSize := school.ConnectionPoolSize
	if poolSize < 5 {
		poolSize = 25 // default
	}
	sqlDB.SetMaxOpenConns(poolSize)
	sqlDB.SetMaxIdleConns(poolSize / 2)
	sqlDB.SetConnMaxLifetime(5 * time.Minute)

	// Cache it
	cm.mu.Lock()
	cm.pool[schoolID] = db
	cm.mu.Unlock()

	return db, nil
}
```

### Pattern 4: RepositoryFactory (GSD-R4)

**What:** Creates tenant-aware repository instances. Acts as bridge to Phase 2 where all module repositories will accept tenant-specific `*gorm.DB` connections.

```go
// Source: Based on existing repository pattern in auth/repository.go and school/repository.go

type RepositoryFactory struct {
	cm  *ConnectionManager
	// Core DB for repositories that need cross-tenant data (auth, schools)
	coreDB *gorm.DB
}

func NewRepositoryFactory(cm *ConnectionManager, coreDB *gorm.DB) *RepositoryFactory {
	return &RepositoryFactory{cm: cm, coreDB: coreDB}
}

// ErrRepositoryNotImplemented is returned when a repository type is not yet
// implemented for the factory pattern.
var ErrRepositoryNotImplemented = errors.New("repository not implemented for tenant factory")

// ForSchool returns a factory scoped to a specific tenant.
// The tenant repo uses the school's dedicated DB; the core repos use
// the shared core DB (for cross-tenant data like auth).
func (f *RepositoryFactory) ForSchool(ctx context.Context, schoolID uint) (*TenantRepositories, error) {
	tenantDB, err := f.cm.GetConnection(ctx, schoolID)
	if err != nil {
		return nil, fmt.Errorf("factory: get tenant db for school %d: %w", schoolID, err)
	}

	return &TenantRepositories{
		// Core DB repos (auth, schools, users — always query core DB)
		Auth:   auth.NewAuthRepository(f.coreDB),
		School: school.NewSchoolRepository(f.coreDB),
		User:   user.NewUserRepository(f.coreDB),

		// Tenant DB repos (will be populated in Phase 2)
		// Academic:  academic.NewAcademicRepository(tenantDB),   // Phase 2
		// Score:     score.NewScoreRepository(tenantDB),         // Phase 2
		// Bill:     bill.NewBillRepository(tenantDB),            // Phase 2
		// ... (all 30+ module repos move here in Phase 2)
	}, nil
}

type TenantRepositories struct {
	// Core (always from core DB)
	Auth   *auth.AuthRepository
	School *school.SchoolRepository
	User   *user.UserRepository

	// Tenant (Phase 2: populated from tenant DB)
	// Academic      *academic.AcademicRepository
	// ...
}
```

### Anti-Patterns to Avoid
- **Plaintext DB passwords in DB:** Never store unencrypted database passwords in the `schools` table. Always use EncryptionService.
- **Mixed FK enforcement:** Don't add GORM foreign key constraints to `schools` table — the DB user doesn't own the table (documented codebase issue).
- **Blocking on connection creation:** The `buildConnection` method creates a real TCP connection. Use context timeouts and circuit breakers to prevent cascading failures.
- **Global mutable state:** Don't add another global `*gorm.DB` like the existing `database.DB`. The ConnectionManager should be dependency-injected.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AES-256-GCM encryption | Custom cipher implementation | Go stdlib `crypto/aes` + `crypto/cipher` | Stdlib is FIPS-140-certified, audited, well-tested. Custom crypto is a security risk. |
| Thread-safe cache | Custom mutex-based map | `sync.Map` | Built-in, optimized for read-heavy workloads, simpler API. |
| GORM connection pools | Custom connection pooling | GORM's built-in `sql.DB` pool via `SetMaxOpenConns`/`SetMaxIdleConns` | Already used by `database.Connect()`. GORM wraps `database/sql` which handles pooling. |
| Background health checks | Custom scheduler | Simple `time.Ticker` in a goroutine | No need for cron library; ticker is sufficient for health check polling. |

**Key insight:** Each of these "don't hand-roll" items uses Go stdlib or GORM's built-in capabilities. The codebase already demonstrates these patterns in `database/postgres.go` (GORM pool config) and `internal/middleware/requestid.go` (uses `crypto/rand`). Stick with Go conventions.

## Common Pitfalls

### Pitfall 1: Nonce Reuse with AES-GCM
**What goes wrong:** If the same nonce is used twice with the same AES-GCM key, an attacker can recover the keystream and decrypt all messages encrypted with that key.
**Why it happens:** Copy-pasting or manually reusing a nonce value.
**How to avoid:** Always generate nonces via `crypto/rand` (12 bytes for GCM). Never accept a nonce parameter. The Encrypt method must internally generate a random nonce every call.
**Warning signs:** Hardcoded nonce, nonce passed as parameter, nonce derived from deterministic input.

### Pitfall 2: GORM AutoMigrate on FK-Owned Tables
**What goes wrong:** GORM's `AutoMigrate` tries to add foreign key constraints to related tables. When `schools` is owned by a different Postgres user, this fails with permission errors.
**Why it happens:** The `schools` table was created by the original Laravel migration and the Go backend's DB user cannot alter it.
**How to avoid:** Use raw SQL `ALTER TABLE schools ADD COLUMN IF NOT EXISTS` for the schools enhancement. Use raw SQL `CREATE TABLE IF NOT EXISTS` for new tables (database_connections, tenant_backups). Never use `db.AutoMigrate(&models.School{})` for the enhanced model.
**Warning signs:** Migration panics with `permission denied for table schools`.

### Pitfall 3: Stale Connections in sync.Map Cache
**What goes wrong:** A school's database credentials change (password rotation, host migration), but the ConnectionManager still serves the old connection from cache.
**Why it happens:** `sync.Map` has no TTL-based eviction built in.
**How to avoid:** Add an explicit `Evict(schoolID)` method called by a credential-update flow. Use health checks to detect stale connections (application-level ping with credential re-verification). Implement periodic full cache refresh.
**Warning signs:** Health check failures for pool connections; "connection refused" despite cache hit.

### Pitfall 4: Connection Leaks from Missing Close
**What goes wrong:** If a school is deleted, its GORM connection remains in the cache and the underlying `sql.DB` is never closed.
**Why it happens:** `sync.Map` only adds entries; it doesn't clean up on school deletion.
**How to avoid:** Add `CloseConnection(schoolID)` method that removes from cache and calls `sqlDB.Close()`. Wire this into a school-deletion event/handler.
**Warning signs:** Growing number of open PostgreSQL connections; stale connections to deleted databases.

## Code Examples

### Config Changes (GSD-R1)
```go
// backend/internal/config/config.go — add to Config struct
type Config struct {
    // ... existing fields ...
    Encryption EncryptionConfig  // NEW
}

type EncryptionConfig struct {
    Key string // 64 hex chars = 32 bytes for AES-256
}

// In Load():
Encryption: EncryptionConfig{
    Key: getEnv("ENCRYPTION_KEY", ""), // No default — must be set
},
```

### Main.go initialization flow (end state)
```go
// backend/cmd/server/main.go — updated initialization
func main() {
    cfg, err := config.Load()
    // ...

    // Connect to core PostgreSQL
    db := database.MustConnect(cfg.DB)

    // Initialize encryption service (required for multi-tenant)
    encSvc, err := crypto.NewService(cfg.Encryption.Key)
    if err != nil {
        logger.Fatal("Failed to init encryption service", "error", err)
    }

    // Initialize connection manager
    connManager := tenant.NewConnectionManager(tenant.Config{
        HealthCheckInterval: 30 * time.Second,
    }, encSvc, db)

    // Initialize repository factory
    repoFactory := tenant.NewRepositoryFactory(connManager, db)

    // Run migrations (now includes multi-tenant migrations)
    migrator := migrations.New(db)
    if err := migrator.Run(); err != nil {
        logger.Fatal("Migration failed", "error", err)
    }

    // Build router — pass connManager and repoFactory
    engine, tpShutdown := router.NewRouter(cfg, db, rdb, connManager, repoFactory)
    // ...
}
```

### Migration Registration Pattern (GSD-R2)
```go
// backend/internal/database/migrations/migrations.go — add in New():
func New(db *gorm.DB) *migrator {
    m := &migrator{db: db}
    // ... existing registrations ...
    
    // Register multi-tenant migrations (Phase 1 of migration plan)
    for _, migration := range MultiTenantMigrations() {
        m.Register(migration)
    }
    
    return m
}
```

### Health Check Pattern (GSD-R3)
```go
func (cm *ConnectionManager) healthCheckLoop(interval time.Duration) {
    ticker := time.NewTicker(interval)
    defer ticker.Stop()
    
    for range ticker.C {
        cm.mu.RLock()
        schools := make([]uint, 0, len(cm.pool))
        for schoolID := range cm.pool {
            schools = append(schools, schoolID)
        }
        cm.mu.RUnlock()
        
        for _, schoolID := range schools {
            cm.mu.RLock()
            db, ok := cm.pool[schoolID]
            cm.mu.RUnlock()
            if !ok {
                continue
            }
            
            sqlDB, err := db.DB()
            if err != nil || sqlDB.Ping() != nil {
                // Connection is stale — evict
                logger.Warn("Evicting stale connection", "school_id", schoolID)
                cm.mu.Lock()
                if oldDB, exists := cm.pool[schoolID]; exists {
                    if oldSqlDB, err := oldDB.DB(); err == nil {
                        oldSqlDB.Close()
                    }
                    delete(cm.pool, schoolID)
                }
                cm.mu.Unlock()
            }
        }
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single GORM connection via `database.MustConnect` | ConnectionManager with per-tenant GORM pool | Phase 1 | Existing code continues using core DB; new code uses ConnectionManager |
| Plaintext DB credentials in env | Encrypted per-school credentials in DB | Phase 1 | Mandatory for Phase 2+ where tenant DBs are created |
| Repositories always take core `*gorm.DB` | RepositoryFactory creates tenant-aware repos | Phase 1 (stub) → Phase 2 (full) | Phase 1 only defines the pattern; Phase 2 migrates 30+ module repos |

**Deprecated/outdated:**
- The `database.DB` global variable (`var DB *gorm.DB` in `postgres.go`) — fine for current code but not extensible for multi-tenant. New code should inject dependencies rather than using the global.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ENCRYPTION_KEY` env var is sufficient for key management in Phase 1 | EncryptionService | Low — production would use KMS, but env var is standard for v1 and can be upgraded later |
| A2 | `schools` table is owned by a different Postgres DB user (from Laravel migration) | Schema Migration | HIGH — if this is NOT true, we could use `AutoMigrate` instead of raw SQL. MUST verify before implementing. The comment in `phase_modules.go` API_DOCS says "AutoMigrate tries to FK-enforce on the `schools` table which is owned by a different DB user" |
| A3 | `sync.Map` is performant enough for expected school count | ConnectionManager | Low — < 1000 schools, read-heavy pattern, `sync.Map` is well-suited |
| A4 | The `School` model in Go maps to the same `schools` table owned by Laravel | Schema Migration | High — column conflicts if they diverge. Must verify exact column list from the actual Laravel schema before running ALTER TABLE |
| A5 | School `Name` field is unique enough for identification | ConnectionManager | Low — using uint ID as key, name is just display |

## Open Questions

1. **What is the exact current schema of the `schools` table (from the Laravel side)?**
   - What we know: Current Go model has `ID, Name, SchoolType, Location, Details, CreatedAt, UpdatedAt`
   - What's unclear: What columns exist on the actual PostgreSQL table that the Laravel app created. There may be additional columns (plan_type, subscription_status, features, modules, settings — mentioned in context.md as existing fields on School model)
   - Recommendation: **CRITICAL** — Run `\d schools` on the actual PostgreSQL database to get the real schema before writing ALTER TABLE migrations. The context.md mentions School model has `plan_type, subscription_status, features (jsonb), modules (string array), settings (jsonb)`, but the Go model struct doesn't have these fields. The Go model and actual DB schema may be out of sync.

2. **What's the actual DB user/permission setup?**
   - What we know: "schools table is owned by a different DB user" (from code comments)
   - What's unclear: Can the Go backend's DB user ALTER the schools table? The comment says "AutoMigrate tries to FK-enforce" which fails — but does `ALTER TABLE ADD COLUMN IF NOT EXISTS` also fail?
   - Recommendation: Test with the actual DB credentials before finalizing the migration approach.

3. **Should the `School` model be updated in Go to include the new DB connection fields?**
   - What we know: The model would need `database_name, database_host, database_port, database_username, database_password_encrypted, database_status, connection_pool_size` fields
   - What's unclear: If we update the Go model, AutoMigrate might try to alter the table and fail (FK issue). Alternatively, only add fields through raw SQL and keep the Go model fields as SQL-only (using `gorm:"-"` tag on the Go struct or keeping them separate)
   - Recommendation: Add fields to the Go School model with `gorm:"-"` tags (not managed by GORM) and handle them via raw SQL queries in a "school connection" accessor pattern. Or add them as regular GORM fields and rely on migrations for schema changes.

4. **Does the existing `School` model need to be updated for the new fields in this phase, or is that deferred?**
   - For Phase 1, we need to add the new DB connection fields so `ConnectionManager` can read them. The School repository will need to fetch these fields. This means either:
     a) Add to Go model (risks AutoMigrate FK issue)
     b) Use raw scan queries (more code but safer)
     c) Create a `SchoolConnection` struct/model separate from `School`
   - Recommendation: Option (c) — create a `SchoolConnection` struct (not in `AllModels()`) that maps to the same `schools` table but only has the connection-related fields. This avoids any AutoMigrate interaction with the schools table while giving us type-safe access to the new columns.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A for Phase 1 |
| V3 Session Management | no | Phase 4 concern |
| V4 Access Control | no | Phase 2-4 concern |
| V5 Input Validation | yes | Encryption key format validation (32 bytes hex) |
| V6 Cryptography | yes | AES-256-GCM via Go stdlib. Key rotation NOT implemented in Phase 1 (future concern). |

### Known Threat Patterns for Phase 1

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Encryption key leakage in logs/errors | Information Disclosure | Sanitize `ENCRYPTION_KEY` from log output. Never log key or ciphertext. |
| Nonce reuse in GCM | Tampering | Generate nonce per-call via `crypto/rand`. Never accept external nonce. |
| Connection credential in plaintext at rest | Information Disclosure | Never store plaintext passwords. Encrypt with AAD bound to school ID. |
| Timing side-channel on password comparison | Tampering | Not applicable — we decrypt, don't compare. But if we add password verification, use `hmac.Equal`. |

## Sources

### Primary (HIGH confidence)
- Go stdlib `crypto/aes`, `crypto/cipher`, `crypto/rand` — official Go documentation
- `backend/internal/database/postgres.go` — existing GORM connection pattern [VERIFIED]
- `backend/internal/database/migrations/migrations.go` — migration registration pattern [VERIFIED]
- `backend/internal/database/migrations/phase_modules.go` — raw SQL migration pattern + FK owner caveat [VERIFIED]
- `backend/internal/modules/auth/repository.go` — repository pattern (interface + struct + constructor) [VERIFIED]
- `backend/internal/modules/school/repository.go` — repository with `GetDB()` transaction support [VERIFIED]
- `backend/internal/router/setup.go` — DI wiring pattern [VERIFIED]
- `backend/internal/database/models/school.go` — current School model fields [VERIFIED]
- `backend/internal/config/config.go` — config structure pattern [VERIFIED]
- `backend/internal/database/models/tenant.go` — existing tenant infrastructure [VERIFIED]

### Secondary (MEDIUM confidence)
- `backend/pkg/jwt/jwt.go` — evidence of `pkg/` pattern for reusable packages [VERIFIED]
- `backend/internal/services/` — service-layer singleton patterns [VERIFIED]
- `backend/internal/database/migrations/phase1.go` — AutoMigrate-based migration pattern [VERIFIED]

### Tertiary (LOW confidence)
- None — all sources verified against actual codebase files.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components are Go stdlib or already in go.mod
- Architecture: HIGH — patterns are verbatim from existing codebase
- Pitfalls: MEDIUM — FK-owner issue verified in codebase comments but untested against actual DB
- Security: HIGH — AES-256-GCM is well-understood; Go stdlib implementation is authoritative

**Research date:** 2026-06-29
**Valid until:** 2026-07-29 (30 days for stable project)
