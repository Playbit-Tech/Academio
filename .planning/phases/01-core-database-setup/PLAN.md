# Phase 1: Core Database Setup — Execution Plan

> Four sub-plans building the foundation for database-per-tenant architecture.

## Dependency Graph

```
Wave 1 (parallel):  01-01 (EncryptionService)   01-02 (Schema Migration)
                                |                          |
Wave 2:              01-03 (DatabaseConnectionManager)    |
                                |                          (reads schools config)
Wave 3:              01-04 (RepositoryFactory)
```

| Plan | Wave | Depends On | Files Modified | Autonomous |
|------|------|------------|----------------|------------|
| 01-01 | 1 | none | `internal/crypto/encryption.go`, `internal/config/config.go` | yes |
| 01-02 | 1 | none | `internal/database/migrations/phase_multitenant.go`, `internal/database/migrations/migrations.go`, `internal/database/models/mt_school.go`, `internal/database/models/mt_database_connection.go`, `internal/database/models/mt_tenant_backup.go` | yes |
| 01-03 | 2 | 01-01, 01-02 | `internal/database/tenant/connection_manager.go`, `internal/database/tenant/config.go` | yes |
| 01-04 | 3 | 01-03 | `internal/database/tenant/factory.go` | yes |

## Decision Coverage Matrix

| ID | Requirement | Plan | Task | Coverage |
|----|-------------|------|------|----------|
| GSD-R1 | EncryptionService AES-256-GCM | 01-01 | 1-2 | Full |
| GSD-R2 | Schema migration (schools + new tables) | 01-02 | 1-2 | Full |
| GSD-R3 | DatabaseConnectionManager (sync.Map, pool, health) | 01-03 | 1-2 | Full |
| GSD-R4 | RepositoryFactory pattern | 01-04 | 1 | Full |

---

## 01-01: EncryptionService (AES-256-GCM)

**Wave:** 1 | **Depends on:** none | **Autonomous:** yes

### Files Modified
- `backend/internal/crypto/encryption.go` (CREATE)
- `backend/internal/config/config.go` (MODIFY)

### Must-Haves

```yaml
truths:
  - "EncryptionService can encrypt plaintext with AES-256-GCM, producing a base64 string"
  - "EncryptionService can decrypt a previously encrypted string back to original plaintext"
  - "Decryption with wrong AAD (different school ID) returns an error"
  - "Decryption with wrong key returns an error"
  - "Key is loaded from ENCRYPTION_KEY env var (64 hex chars = 32 bytes)"
  - "Config struct has Encryption section with Key field"

artifacts:
  - path: "backend/internal/crypto/encryption.go"
    provides: "Service struct, NewService(), Encrypt(), Decrypt()"
    exports: ["Service", "NewService", "KeySize", "NonceSize"]
  - path: "backend/internal/config/config.go"
    provides: "EncryptionConfig struct, Encryption field on Config"
    contains: "EncryptionConfig.Key"

key_links:
  - from: "encryption.go::NewService"
    to: "config.go::EncryptionConfig.Key"
    via: "cfg.Encryption.Key"
    pattern: "NewService\\(cfg\\.Encryption\\.Key\\)"
```

### Tasks

<task type="auto">
  <name>Task 1: Add EncryptionConfig to config.go</name>
  <files>backend/internal/config/config.go</files>
  <action>
    Add to the Config struct (after Communication field, before closing brace):
    
    ```go
    // Encryption holds AES-256-GCM encryption configuration for multi-tenant credentials.
    Encryption EncryptionConfig
    ```

    Add new struct after CommunicationConfig:

    ```go
    // EncryptionConfig defines settings for AES-256-GCM credential encryption.
    type EncryptionConfig struct {
    	Key string // 64 hex chars = 32 bytes for AES-256. Required for multi-tenant.
    }
    ```

    In `Load()`, add after the Communication section:

    ```go
    Encryption: EncryptionConfig{
    	Key: getEnv("ENCRYPTION_KEY", ""),
    },
    ```

    Add validation in `validate()`: if multi-tenant is enabled (check if ENCRYPTION_KEY is non-empty), validate the key format (32 bytes when decoded). Add:

    ```go
    if c.Encryption.Key != "" {
    	key, err := hex.DecodeString(c.Encryption.Key)
    	if err != nil {
    		return fmt.Errorf("ENCRYPTION_KEY must be valid hex: %w", err)
    	}
    	if len(key) != 32 {
    		return fmt.Errorf("ENCRYPTION_KEY must decode to 32 bytes (64 hex chars), got %d bytes", len(key))
    	}
    }
    ```

    Add `"encoding/hex"` to imports.

    Per user decision: encryption key from env var, not KMS (deferred to production).
  </action>
  <verify>
    <automated>cd backend && go build ./internal/config/</automated>
  </verify>
  <done>
    Config struct has EncryptionConfig field. ENCRYPTION_KEY env var validation works. Build passes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement EncryptionService in internal/crypto/</name>
  <files>backend/internal/crypto/encryption.go</files>
  <action>
    Create directory `backend/internal/crypto/` and file `encryption.go`.

    Package `crypto` providing AES-256-GCM encryption/decryption using Go stdlib only (crypto/aes, crypto/cipher, crypto/rand).

    **Design (per RESEARCH.md patterns):**

    1. **Constants:** `KeySize = 32`, `NonceSize = 12`
    2. **Service struct:** holds `key []byte`
    3. **NewService(hexKey string) (*Service, error):** decodes hex to 32 bytes, validates length, returns Service
    4. **Encrypt(plaintext []byte, aad []byte) (string, error):**
       - Create AES cipher block from key
       - Create GCM mode from block  
       - Generate 12-byte random nonce via `crypto/rand`
       - Seal: `gcm.Seal(nil, nonce, plaintext, aad)` → produces `nonce || ciphertext || tag`
       - Prepend nonce: `result = append(nonce, ciphertext...)`
       - Return `base64.StdEncoding.EncodeToString(result)`
    5. **Decrypt(encoded string, aad []byte) ([]byte, error):**
       - Base64 decode
       - Validate length >= NonceSize + 1
       - Split nonce (first 12 bytes) and ciphertext (rest)
       - Create cipher + GCM
       - Open: `gcm.Open(nil, nonce, ciphertext, aad)`
       - On failure (wrong key, wrong AAD, tampered): returns error
    6. **Convenience methods** accepting string plaintext (convert to `[]byte`):
       - `EncryptString(plaintext string, schoolID string) (string, error)`
       - `DecryptString(ciphertext string, schoolID string) (string, error)`
       - These convert schoolID to `[]byte` for AAD

    **Security enforcement (from RESEARCH.md security domain):**
    - Nonce MUST be generated internally via `crypto/rand` per call — never accept external nonce (Pitfall 1)
    - Never log key, plaintext, or ciphertext content
    - AAD binds ciphertext to school ID: pass `[]byte(schoolID)` as AAD
    - Use Go stdlib only — no external crypto libraries (per "Don't Hand-Roll" rules)

    **Imports needed:** `crypto/aes`, `crypto/cipher`, `crypto/rand`, `encoding/base64`, `encoding/hex`, `errors`, `fmt`, `io`

    Create package-level test file `encryption_test.go` with:
    - TestEncryptDecrypt: encrypt then decrypt should return original
    - TestDecryptWrongAAD: decrypt with different school ID should fail
    - TestDecryptWrongKey: create second Service, should fail
    - TestNewServiceKeyLengthError: wrong key length should fail
    - TestNonceRandomness: two encryptions of same data produce different outputs

    All tests use t.Parallel().
  </action>
  <verify>
    <automated>cd backend && go test ./internal/crypto/ -v -count=1 -run TestEncrypt</automated>
    <automated>cd backend && go vet ./internal/crypto/</automated>
  </verify>
  <done>
    EncryptionService implemented. Encrypt/Decrypt roundtrip works. Wrong AAD returns error. 
    Wrong key returns error. Tests pass. Lint passes.
  </done>
</task>

---

## 01-02: Schema Migration (Schools Enhancement + New Tables)

**Wave:** 1 | **Depends on:** none | **Autonomous:** yes

### Files Modified
- `backend/internal/database/migrations/phase_multitenant.go` (CREATE)
- `backend/internal/database/migrations/migrations.go` (MODIFY)
- `backend/internal/database/models/mt_school_connection.go` (CREATE)
- `backend/internal/database/models/mt_database_connection.go` (CREATE)
- `backend/internal/database/models/mt_tenant_backup.go` (CREATE)

### Must-Haves

```yaml
truths:
  - "schools table has new DB connection columns: database_name, database_host, database_port, database_username, database_password_encrypted, database_status, connection_pool_size"
  - "database_connections table exists with proper schema"
  - "tenant_backups table exists with proper schema"
  - "SchoolConnection Go model exists with connection fields only (not GORM-managed for schools table)"
  - "DatabaseConnection Go model tracks per-school connection metadata"
  - "TenantBackup Go model tracks backup history"
  - "Migration is registered in migrations.go and runs idempotently"

artifacts:
  - path: "backend/internal/database/migrations/phase_multitenant.go"
    provides: "MultiTenantMigrations() function"
    exports: ["MultiTenantMigrations"]
  - path: "backend/internal/database/migrations/migrations.go"
    provides: "Updated New() with MultiTenantMigrations registered"
  - path: "backend/internal/database/models/mt_school_connection.go"
    provides: "SchoolConnection struct (maps to schools table, connection fields only)"
  - path: "backend/internal/database/models/mt_database_connection.go"
    provides: "DatabaseConnection struct"
  - path: "backend/internal/database/models/mt_tenant_backup.go"
    provides: "TenantBackup struct"

key_links:
  - from: "migrations.go::New()"
    to: "phase_multitenant.go::MultiTenantMigrations()"
    via: "for _, m := range MultiTenantMigrations() { m.Register(m) }"
```

### Tasks

<task type="auto">
  <name>Task 1: Create multi-tenant migration file</name>
  <files>
    backend/internal/database/migrations/phase_multitenant.go
    backend/internal/database/migrations/migrations.go
  </files>
  <action>
    Create `backend/internal/database/migrations/phase_multitenant.go`:

    Package `migrations`. Function `MultiTenantMigrations() []Migration` returning 3 Migration entries:

    **Migration 1 — `2026_06_29_000001_enhance_schools_database_columns`:**
    ```go
    Migrate: func(db *gorm.DB) error {
        if err := db.Exec(`ALTER TABLE schools 
            ADD COLUMN IF NOT EXISTS database_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS database_host VARCHAR(255),
            ADD COLUMN IF NOT EXISTS database_port INTEGER DEFAULT 5432,
            ADD COLUMN IF NOT EXISTS database_username VARCHAR(100),
            ADD COLUMN IF NOT EXISTS database_password_encrypted TEXT,
            ADD COLUMN IF NOT EXISTS database_status VARCHAR(20) DEFAULT 'shared',
            ADD COLUMN IF NOT EXISTS connection_pool_size INTEGER DEFAULT 25
        `).Error; err != nil {
            return err
        }
        return nil
    },
    Rollback: func(db *gorm.DB) error {
        // Remove columns on rollback — use IF EXISTS for idempotency
        return db.Exec(`ALTER TABLE schools 
            DROP COLUMN IF EXISTS database_name,
            DROP COLUMN IF EXISTS database_host,
            DROP COLUMN IF EXISTS database_port,
            DROP COLUMN IF EXISTS database_username,
            DROP COLUMN IF EXISTS database_password_encrypted,
            DROP COLUMN IF EXISTS database_status,
            DROP COLUMN IF EXISTS connection_pool_size
        `).Error
    },
    ```

    **Migration 2 — `2026_06_29_000002_create_database_connections`:**
    ```go
    Migrate: func(db *gorm.DB) error {
        if err := db.Exec(`CREATE TABLE IF NOT EXISTS database_connections (
            id            BIGSERIAL PRIMARY KEY,
            school_id     BIGINT  NOT NULL,
            database_name VARCHAR(100) NOT NULL,
            database_host VARCHAR(255) NOT NULL,
            database_port INTEGER NOT NULL DEFAULT 5432,
            username      VARCHAR(100) NOT NULL,
            password_encrypted TEXT NOT NULL,
            status        VARCHAR(20) NOT NULL DEFAULT 'active',
            connected_at  TIMESTAMPTZ,
            disconnected_at TIMESTAMPTZ,
            error_message TEXT,
            is_primary    BOOLEAN NOT NULL DEFAULT TRUE,
            created_at    TIMESTAMPTZ,
            updated_at    TIMESTAMPTZ
        )`).Error; err != nil {
            return err
        }
        if err := db.Exec(`CREATE INDEX IF NOT EXISTS idx_database_connections_school_id ON database_connections(school_id)`).Error; err != nil {
            return err
        }
        return db.Exec(`CREATE INDEX IF NOT EXISTS idx_database_connections_status ON database_connections(status)`).Error
    },
    Rollback: func(db *gorm.DB) error {
        return db.Exec(`DROP TABLE IF EXISTS database_connections CASCADE`).Error
    },
    ```

    **Migration 3 — `2026_06_29_000003_create_tenant_backups`:**
    ```go
    Migrate: func(db *gorm.DB) error {
        if err := db.Exec(`CREATE TABLE IF NOT EXISTS tenant_backups (
            id            BIGSERIAL PRIMARY KEY,
            school_id     BIGINT  NOT NULL,
            backup_name   VARCHAR(255) NOT NULL,
            backup_path   VARCHAR(500) NOT NULL,
            database_name VARCHAR(100) NOT NULL,
            backup_type   VARCHAR(20) NOT NULL DEFAULT 'manual',
            size_bytes    BIGINT DEFAULT 0,
            checksum      VARCHAR(64),
            status        VARCHAR(20) NOT NULL DEFAULT 'pending',
            restore_point TIMESTAMPTZ,
            error_message TEXT,
            metadata      JSONB DEFAULT '{}',
            started_at    TIMESTAMPTZ,
            completed_at  TIMESTAMPTZ,
            created_at    TIMESTAMPTZ
        )`).Error; err != nil {
            return err
        }
        if err := db.Exec(`CREATE INDEX IF NOT EXISTS idx_tenant_backups_school_id ON tenant_backups(school_id)`).Error; err != nil {
            return err
        }
        return db.Exec(`CREATE INDEX IF NOT EXISTS idx_tenant_backups_status ON tenant_backups(status)`).Error
    },
    Rollback: func(db *gorm.DB) error {
        return db.Exec(`DROP TABLE IF EXISTS tenant_backups CASCADE`).Error
    },
    ```

    **Modify `migrations.go`:** In `New()`, after the existing AuthRewriteMigrations registration, add:

    ```go
    // Register multi-tenant migrations (Phase 1 of DB-per-tenant migration)
    for _, migration := range MultiTenantMigrations() {
        m.Register(migration)
    }
    ```

    **IMPORTANT (per research):** 
    - MUST use raw SQL for `ALTER TABLE schools` because schools table is owned by Laravel DB user
    - MUST use `ADD COLUMN IF NOT EXISTS` for idempotency (migration system tracks by ID, but double-safe)
    - DO NOT use `db.AutoMigrate()` — it will try to FK-enforce on schools and fail
    - Use `CREATE TABLE IF NOT EXISTS` for new tables (standard pattern in this codebase)
    - Each `db.Exec()` call is separate (GORM doesn't support multi-statement Exec)
    - Per user decisions: backward-compatible, zero-downtime, RAW SQL not AutoMigrate
  </action>
  <verify>
    <automated>cd backend && go build ./internal/database/migrations/</automated>
  </verify>
  <done>
    MultiTenantMigrations() returns 3 migrations. All use raw SQL. ALTER TABLE uses ADD COLUMN IF NOT EXISTS. New tables use CREATE TABLE IF NOT EXISTS. Build passes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create Go models for multi-tenant entities</name>
  <files>
    backend/internal/database/models/mt_school_connection.go
    backend/internal/database/models/mt_database_connection.go
    backend/internal/database/models/mt_tenant_backup.go
  </files>
  <action>
    Create 3 model files in `backend/internal/database/models/`:

    **File 1: `mt_school_connection.go`**
    ```go
    package models

    // SchoolConnection maps to the schools table but only contains
    // database connection fields. This avoids GORM AutoMigrate issues
    // with the schools table (owned by Laravel DB user). Use raw SQL
    // or gorm:"-" tagged queries for reads/writes.
    type SchoolConnection struct {
    	SchoolID                 uint   `gorm:"column:id" json:"school_id"`
    	DatabaseName             string `gorm:"column:database_name" json:"database_name"`
    	DatabaseHost             string `gorm:"column:database_host" json:"database_host"`
    	DatabasePort             int    `gorm:"column:database_port" json:"database_port"`
    	DatabaseUsername         string `gorm:"column:database_username" json:"database_username"`
    	DatabasePasswordEncrypted string `gorm:"column:database_password_encrypted" json:"database_password_encrypted"`
    	DatabaseStatus           string `gorm:"column:database_status" json:"database_status"`
    	ConnectionPoolSize       int    `gorm:"column:connection_pool_size" json:"connection_pool_size"`
    }

    // TableName returns the schools table name (not managed by GORM).
    func (SchoolConnection) TableName() string {
    	return "schools"
    }
    ```

    **File 2: `mt_database_connection.go`**
    ```go
    package models

    import "time"

    // DatabaseConnection tracks a school's database connection metadata.
    type DatabaseConnection struct {
    	ID                uint       `gorm:"primaryKey" json:"id"`
    	SchoolID          uint       `gorm:"index:idx_dc_school;not null" json:"school_id"`
    	DatabaseName      string     `gorm:"size:100;not null" json:"database_name"`
    	DatabaseHost      string     `gorm:"size:255;not null" json:"database_host"`
    	DatabasePort      int        `gorm:"default:5432" json:"database_port"`
    	Username          string     `gorm:"size:100;not null" json:"username"`
    	PasswordEncrypted string     `gorm:"type:text;not null" json:"-"`
    	Status            string     `gorm:"size:20;default:'active'" json:"status"`
    	ConnectedAt       *time.Time `json:"connected_at,omitempty"`
    	DisconnectedAt    *time.Time `json:"disconnected_at,omitempty"`
    	ErrorMessage      *string    `gorm:"type:text" json:"error_message,omitempty"`
    	IsPrimary         bool       `gorm:"default:true" json:"is_primary"`
    	CreatedAt         time.Time  `json:"created_at"`
    	UpdatedAt         time.Time  `json:"updated_at"`
    }

    func (DatabaseConnection) TableName() string {
    	return "database_connections"
    }
    ```

    **File 3: `mt_tenant_backup.go`**
    ```go
    package models

    import (
    	"encoding/json"
    	"time"
    )

    // TenantBackup tracks a backup operation for a school's database.
    type TenantBackup struct {
    	ID           uint              `gorm:"primaryKey" json:"id"`
    	SchoolID     uint              `gorm:"index:idx_tb_school;not null" json:"school_id"`
    	BackupName   string            `gorm:"size:255;not null" json:"backup_name"`
    	BackupPath   string            `gorm:"size:500;not null" json:"backup_path"`
    	DatabaseName string            `gorm:"size:100;not null" json:"database_name"`
    	BackupType   string            `gorm:"size:20;default:'manual'" json:"backup_type"`
    	SizeBytes    int64             `gorm:"default:0" json:"size_bytes"`
    	Checksum     *string           `gorm:"size:64" json:"checksum,omitempty"`
    	Status       string            `gorm:"size:20;default:'pending'" json:"status"`
    	RestorePoint *time.Time        `json:"restore_point,omitempty"`
    	ErrorMessage *string           `gorm:"type:text" json:"error_message,omitempty"`
    	Metadata     json.RawMessage   `gorm:"type:jsonb;default:'{}'" json:"metadata,omitempty"`
    	StartedAt    *time.Time        `json:"started_at,omitempty"`
    	CompletedAt  *time.Time        `json:"completed_at,omitempty"`
    	CreatedAt    time.Time         `json:"created_at"`
    }

    func (TenantBackup) TableName() string {
    	return "tenant_backups"
    }
    ```

    **Design notes:**
    - `SchoolConnection` does NOT embed BaseModel — it's a read-only projection, not GORM-managed
    - `database_password_encrypted` is tagged `json:"-"` on SchoolConnection to prevent accidental serialization
    - `PasswordEncrypted` on DatabaseConnection is also tagged `json:"-"` for the same reason
    - Use `uint` IDs to match existing codebase convention (BaseModel comment: "Uses uint IDs to match the Laravel v2 schema")
  </action>
  <verify>
    <automated>cd backend && go build ./internal/database/models/</automated>
  </verify>
  <done>
    Three model files created. SchoolConnection maps to schools table (read-only). DatabaseConnection and TenantBackup have proper TableName(). PasswordEncrypted fields have json:"-" tags. Build passes.
  </done>
</task>

---

## 01-03: DatabaseConnectionManager

**Wave:** 2 | **Depends on:** 01-01 (EncryptionService), 01-02 (Schema Migration) | **Autonomous:** yes

### Files Modified
- `backend/internal/database/tenant/connection_manager.go` (CREATE)
- `backend/internal/database/tenant/config.go` (CREATE)

### Must-Haves

```yaml
truths:
  - "ConnectionManager.GetConnection(schoolID) returns a configured *gorm.DB for that school's database"
  - "First call for a school ID creates a new connection (cache miss path)"
  - "Second call for same school ID returns cached connection (cache hit path within <50ms)"
  - "Connection pool settings are configured from SchoolConnection (max open, max idle, max lifetime)"
  - "Health checks run periodically via time.Ticker, evict stale connections"
  - "CloseConnection(schoolID) closes the connection and removes from cache"
  - "Decryption of password uses EncryptionService.Decrypt with school ID as AAD"

artifacts:
  - path: "backend/internal/database/tenant/connection_manager.go"
    provides: "ConnectionManager struct with GetConnection, CloseConnection, health checks"
    exports: ["ConnectionManager", "NewConnectionManager"]
  - path: "backend/internal/database/tenant/config.go"
    provides: "Config struct for ConnectionManager settings"

key_links:
  - from: "connection_manager.go::buildConnection"
    to: "encryption.go::Decrypt"
    via: "encSvc.Decrypt(school.DatabasePasswordEncrypted, []byte(schoolID))"
    pattern: "encSvc\\.Decrypt"
  - from: "connection_manager.go::healthCheckLoop"
    to: "connection_manager.go::evictConnection"
    via: "cm.evictConnection(schoolID)"
```

### Tasks

<task type="auto">
  <name>Task 1: Create ConnectionManager config and base structure</name>
  <files>backend/internal/database/tenant/config.go</files>
  <action>
    Create `backend/internal/database/tenant/` directory and `config.go`:

    ```go
    package tenant

    import "time"

    // Config defines the configuration for the ConnectionManager.
    type Config struct {
    	// HealthCheckInterval controls how often the background health checker
    	// pings cached connections. Default: 30 seconds.
    	HealthCheckInterval time.Duration

    	// ConnectionMaxLifetime is the maximum lifetime of a connection.
    	// Default: 5 minutes (matching postgres.go pattern).
    	ConnectionMaxLifetime time.Duration

    	// ConnectionMaxIdle is the maximum number of idle connections per tenant pool.
    	ConnectionMaxIdle int

    	// DefaultPoolSize is the default connection pool size per tenant DB
    	// when school.ConnectionPoolSize is not set or < 5.
    	DefaultPoolSize int
    }

    // DefaultConfig returns a Config with sensible defaults.
    func DefaultConfig() Config {
    	return Config{
    		HealthCheckInterval:   30 * time.Second,
    		ConnectionMaxLifetime: 5 * time.Minute,
    		ConnectionMaxIdle:     10,
    		DefaultPoolSize:       25,
    	}
    }
    ```
  </action>
  <verify>
    <automated>cd backend && go build ./internal/database/tenant/</automated>
  </verify>
  <done>
    tenant package directory created. Config struct with DefaultConfig() works. Build passes.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement ConnectionManager with cache, pool, and health checks</name>
  <files>backend/internal/database/tenant/connection_manager.go</files>
  <action>
    Create `connection_manager.go` in `internal/database/tenant/`:

    **Structs and init:**
    ```go
    package tenant

    import (
    	"context"
    	"fmt"
    	"sync"
    	"time"

    	"gorm.io/driver/postgres"
    	"gorm.io/gorm"
    	"gorm.io/gorm/logger"

    	"github.com/playbits/schoolcare-v2/internal/crypto"
    	"github.com/playbits/schoolcare-v2/internal/database/models"
    )
    ```

    **ConnectionManager struct:**
    ```go
    // ConnectionManager manages per-tenant GORM database connections.
    // Uses sync.Map for thread-safe cache with background health checks.
    type ConnectionManager struct {
    	mu     sync.RWMutex
    	pool   map[uint]*gorm.DB // schoolID -> GORM connection
    	cfg    Config
    	encSvc *crypto.Service
    	coreDB *gorm.DB
    	stopCh chan struct{}
    }

    // NewConnectionManager creates a new ConnectionManager and starts
    // the background health check loop.
    func NewConnectionManager(cfg Config, encSvc *crypto.Service, coreDB *gorm.DB) *ConnectionManager {
    	cm := &ConnectionManager{
    		pool:   make(map[uint]*gorm.DB),
    		cfg:    cfg,
    		encSvc: encSvc,
    		coreDB: coreDB,
    		stopCh: make(chan struct{}),
    	}
    	go cm.healthCheckLoop(cfg.HealthCheckInterval)
    	return cm
    }
    ```

    **GetConnection:**
    ```go
    // GetConnection returns a GORM connection for the given school.
    // Fast path: returns cached connection. Slow path: builds new connection
    // from school's DB credentials in the core database.
    func (cm *ConnectionManager) GetConnection(ctx context.Context, schoolID uint) (*gorm.DB, error) {
    	// Fast path — check cache
    	cm.mu.RLock()
    	if db, ok := cm.pool[schoolID]; ok {
    		cm.mu.RUnlock()
    		return db, nil
    	}
    	cm.mu.RUnlock()

    	// Slow path — build new connection
    	return cm.buildConnection(ctx, schoolID)
    }
    ```

    **buildConnection (private):**
    ```go
    func (cm *ConnectionManager) buildConnection(ctx context.Context, schoolID uint) (*gorm.DB, error) {
    	// 1. Fetch school connection config from core DB
    	// Use SchoolConnection model (read-only projection of schools table)
    	var conn models.SchoolConnection
    	if err := cm.coreDB.WithContext(ctx).
    		Table("schools").
    		Select("id, database_name, database_host, database_port, database_username, database_password_encrypted, database_status, connection_pool_size").
    		Where("id = ?", schoolID).
    		First(&conn).Error; err != nil {
    		return nil, fmt.Errorf("cm: school %d not found: %w", schoolID, err)
    	}

    	// 2. Validate school can accept connections
    	if conn.DatabaseStatus != "" && conn.DatabaseStatus != "active" && conn.DatabaseStatus != "shared" {
    		return nil, fmt.Errorf("cm: school %d database status is '%s', cannot connect", schoolID, conn.DatabaseStatus)
    	}

    	// 3. Decrypt password using EncryptionService with school ID as AAD
    	password, err := cm.encSvc.DecryptString(conn.DatabasePasswordEncrypted, fmt.Sprintf("%d", schoolID))
    	if err != nil {
    		return nil, fmt.Errorf("cm: decrypt password for school %d: %w", schoolID, err)
    	}

    	// 4. Build DSN
    	port := conn.DatabasePort
    	if port == 0 {
    		port = 5432
    	}
    	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
    		conn.DatabaseHost, port, conn.DatabaseUsername, password, conn.DatabaseName,
    	)

    	// 5. Create GORM connection (same pattern as database.postgres.Connect)
    	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
    		Logger:                 logger.Default.LogMode(logger.Warn),
    		SkipDefaultTransaction: true,
    		PrepareStmt:            true,
    	})
    	if err != nil {
    		return nil, fmt.Errorf("cm: connect school %d database: %w", schoolID, err)
    	}

    	// 6. Configure pool
    	sqlDB, err := db.DB()
    	if err != nil {
    		return nil, fmt.Errorf("cm: get sql.DB for school %d: %w", schoolID, err)
    	}
    	poolSize := conn.ConnectionPoolSize
    	if poolSize < 5 {
    		poolSize = cm.cfg.DefaultPoolSize
    	}
    	sqlDB.SetMaxOpenConns(poolSize)
    	sqlDB.SetMaxIdleConns(cm.cfg.ConnectionMaxIdle)
    	sqlDB.SetConnMaxLifetime(cm.cfg.ConnectionMaxLifetime)

    	// 7. Verify connection
    	if err := sqlDB.Ping(); err != nil {
    		return nil, fmt.Errorf("cm: ping school %d database: %w", schoolID, err)
    	}

    	// 8. Cache it
    	cm.mu.Lock()
    	cm.pool[schoolID] = db
    	cm.mu.Unlock()

    	return db, nil
    }
    ```

    **CloseConnection:**
    ```go
    // CloseConnection closes and removes a school's database connection from the cache.
    func (cm *ConnectionManager) CloseConnection(schoolID uint) error {
    	cm.mu.Lock()
    	defer cm.mu.Unlock()

    	if db, ok := cm.pool[schoolID]; ok {
    		sqlDB, err := db.DB()
    		if err != nil {
    			return fmt.Errorf("cm: get sql.DB for close school %d: %w", schoolID, err)
    		}
    		if err := sqlDB.Close(); err != nil {
    			return fmt.Errorf("cm: close connection for school %d: %w", schoolID, err)
    		}
    		delete(cm.pool, schoolID)
    	}
    	return nil
    }
    ```

    **Health check loop:**
    ```go
    func (cm *ConnectionManager) healthCheckLoop(interval time.Duration) {
    	ticker := time.NewTicker(interval)
    	defer ticker.Stop()

    	for {
    		select {
    		case <-ticker.C:
    			cm.runHealthCheck()
    		case <-cm.stopCh:
    			return
    		}
    	}
    }

    func (cm *ConnectionManager) runHealthCheck() {
    	cm.mu.RLock()
    	schoolIDs := make([]uint, 0, len(cm.pool))
    	for id := range cm.pool {
    		schoolIDs = append(schoolIDs, id)
    	}
    	cm.mu.RUnlock()

    	for _, schoolID := range schoolIDs {
    		cm.mu.RLock()
    		db, ok := cm.pool[schoolID]
    		cm.mu.RUnlock()
    		if !ok {
    			continue
    		}

    		sqlDB, err := db.DB()
    		if err != nil {
    			cm.evictConnection(schoolID)
    			continue
    		}

    		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    		pingErr := sqlDB.PingContext(ctx)
    		cancel()

    		if pingErr != nil {
    			cm.evictConnection(schoolID)
    		}
    	}
    }

    func (cm *ConnectionManager) evictConnection(schoolID uint) {
    	cm.mu.Lock()
    	defer cm.mu.Unlock()

    	if db, ok := cm.pool[schoolID]; ok {
    		if sqlDB, err := db.DB(); err == nil {
    			sqlDB.Close()
    		}
    		delete(cm.pool, schoolID)
    	}
    }
    ```

    **Shutdown:**
    ```go
    // Shutdown stops the health check loop and closes all cached connections.
    func (cm *ConnectionManager) Shutdown() error {
    	close(cm.stopCh)

    	cm.mu.Lock()
    	defer cm.mu.Unlock()

    	for schoolID, db := range cm.pool {
    		if sqlDB, err := db.DB(); err == nil {
    			sqlDB.Close()
    		}
    		delete(cm.pool, schoolID)
    	}
    	return nil
    }
    ```

    **Size/Len helpers:**
    ```go
    // ConnectionCount returns the number of cached connections.
    func (cm *ConnectionManager) ConnectionCount() int {
    	cm.mu.RLock()
    	defer cm.mu.RUnlock()
    	return len(cm.pool)
    }
    ```

    **Design decisions (per research):**
    - Uses `sync.RWMutex` + `map[uint]*gorm.DB` (not sync.Map) for explicit eviction control (Pitfall 3 mitigation)
    - Health checks use `PingContext` with 5s timeout to prevent blocking (Pitfall 3)
    - Connection eviction on health check failure (Pitfall 3 & 4 mitigation)
    - Pool settings follow same pattern as `database.postgres.Connect()`
    - Decrypt uses school ID as AAD (binds ciphertext to tenant)
    - Shutdown() for clean teardown, callable from main.go
    - Zero-downtime: GetConnection handles cache miss by building fresh connection
    - Per user decision: no global mutable state, dependency-injected
  </action>
  <verify>
    <automated>cd backend && go build ./internal/database/tenant/</automated>
  </verify>
  <done>
    ConnectionManager implemented with sync.RWMutex+map pool. GetConnection has fast/slow paths. buildConnection decrypts password, creates GORM connection, configures pool, pings, caches. CloseConnection closes and evicts. Health check loop evicts stale connections. Shutdown() cleans up all. Build passes.
  </done>
</task>

---

## 01-04: RepositoryFactory

**Wave:** 3 | **Depends on:** 01-03 (ConnectionManager) | **Autonomous:** yes

### Files Modified
- `backend/internal/database/tenant/factory.go` (CREATE)

### Must-Haves

```yaml
truths:
  - "RepositoryFactory.ForSchool(schoolID) returns TenantRepositories with tenant DB connection"
  - "Core DB repositories (Auth, School, User) use the core *gorm.DB"
  - "Tenant DB repositories use the tenant *gorm.DB from ConnectionManager"
  - "ErrRepositoryNotImplemented is returned when a repository type is not yet wired"
  - "Factory pattern matches existing New*Repository(db *gorm.DB) constructor pattern"

artifacts:
  - path: "backend/internal/database/tenant/factory.go"
    provides: "RepositoryFactory, TenantRepositories, ErrRepositoryNotImplemented"
    exports: ["RepositoryFactory", "NewRepositoryFactory", "TenantRepositories", "ErrRepositoryNotImplemented"]

key_links:
  - from: "factory.go::ForSchool"
    to: "connection_manager.go::GetConnection"
    via: "cm.GetConnection(ctx, schoolID)"
```

### Tasks

<task type="auto">
  <name>Task 1: Implement RepositoryFactory with TenantRepositories struct</name>
  <files>backend/internal/database/tenant/factory.go</files>
  <action>
    Create `factory.go` in `internal/database/tenant/`:

    ```go
    package tenant

    import (
    	"context"
    	"errors"
    	"fmt"

    	"gorm.io/gorm"

    	"github.com/playbits/schoolcare-v2/internal/modules/auth"
    	"github.com/playbits/schoolcare-v2/internal/modules/school"
    	"github.com/playbits/schoolcare-v2/internal/modules/user"
    )
    ```

    ```go
    // ErrRepositoryNotImplemented is returned when a requested repository type
    // is not yet available through the factory. This is expected during the
    // phased migration from core-DB-only to tenant-DB-aware repositories.
    var ErrRepositoryNotImplemented = errors.New("repository not implemented for tenant factory")
    ```

    ```go
    // RepositoryFactory creates tenant-aware repository instances.
    // Core DB repositories always use the shared core database.
    // Tenant DB repositories use the school's dedicated database.
    //
    // This is the bridge to Phase 2 where all 30+ module repositories
    // will be accessible through this factory.
    type RepositoryFactory struct {
    	cm     *ConnectionManager
    	coreDB *gorm.DB
    }
    ```

    ```go
    // NewRepositoryFactory creates a new RepositoryFactory.
    func NewRepositoryFactory(cm *ConnectionManager, coreDB *gorm.DB) *RepositoryFactory {
    	return &RepositoryFactory{
    		cm:     cm,
    		coreDB: coreDB,
    	}
    }
    ```

    ```go
    // ForSchool returns a TenantRepositories set scoped to a specific school.
    // Core repos use the shared core DB; tenant repos use the school's own DB.
    //
    // ctx: request context for connection creation (supports timeout/cancellation).
    // schoolID: the school to create repositories for.
    func (f *RepositoryFactory) ForSchool(ctx context.Context, schoolID uint) (*TenantRepositories, error) {
    	tenantDB, err := f.cm.GetConnection(ctx, schoolID)
    	if err != nil {
    		return nil, fmt.Errorf("factory: get tenant db for school %d: %w", schoolID, err)
    	}

    	return &TenantRepositories{
    		// Core DB repositories (always query core database)
    		Auth:   auth.NewAuthRepository(f.coreDB),
    		School: school.NewSchoolRepository(f.coreDB),
    		User:   user.NewUserRepository(f.coreDB),

    		// Tenant DB repositories (query school's dedicated database)
    		// Phase 2: populate these from tenant DB
    		// Academic: academic.NewAcademicRepository(tenantDB),
    		// Score:    score.NewScoreRepository(tenantDB),
    		// ...
    	}, nil
    }
    ```

    ```go
    // TenantRepositories groups all repository instances for a specific tenant.
    // Core DB repositories handle cross-tenant concerns (auth, schools, users).
    // Tenant DB repositories handle per-school data (students, classes, etc.).
    type TenantRepositories struct {
    	// Core (always from core DB)
    	Auth   *auth.AuthRepository
    	School *school.SchoolRepository
    	User   *user.UserRepository

    	// Tenant (Phase 2: populated from tenant DB)
    	// Academic      *academic.AcademicRepository
    	// Score         *score.ScoreRepository
    	// Result        *result.ResultRepository
    	// Student       *user.StudentRepository
    	// Teacher       *user.TeacherRepository
    	// Timetable     *timetable.TimetableRepository
    	// Bill          *bill.BillRepository
    	// Payment       *payment.PaymentRepository
    	// Exam          *exam.ExamScheduleRepository
    	// ExamResult    *exam.ExamResultRepository
    	// Multimedia    *multimedia.MultimediaRepository
    	// Invitation    *invitation.InvitationRepository
    	// CBA           *cba.CBARepository
    	// Book          *library.BookRepository
    	// BookIssue     *library.BookIssueRepository
    	// Hostel        *hostel.HostelRepository
    	// HostelBed     *hostel.HostelBedRepository
    	// Transport     *transport.TransportRepository
    	// Message       *messages.MessageRepository
    	// Notification  *notifications.NotificationRepository
    	// AssetCategory *inventory.AssetCategoryRepository
    	// InventoryAsset *inventory.InventoryAssetRepository
    	// Maintenance   *inventory.MaintenanceRecordRepository
    	// Wellness      *pastoral.WellnessSurveyRepository
    	// Counseling    *pastoral.CounselingSessionRepository
    	// Alumni        *alumni.AlumniRepository
    	// ChartOfAccount *finance.ChartOfAccountRepository
    	// JournalEntry  *finance.JournalEntryRepository
    	// Budget        *finance.BudgetRepository
    	// Expense       *finance.ExpenseRepository
    	// Department    *hr.DepartmentRepository
    	// Staff         *hr.StaffRepository
    	// Leave         *hr.LeaveRepository
    	// Payslip       *hr.PayslipRepository
    	// ... (all 30+ module repos move here in Phase 2)
    }
    ```

    ```go
    // CreateRepository returns a repository for a given tenant by type name.
    // Returns ErrRepositoryNotImplemented for types not yet migrated.
    // This is the dynamic lookup version used when the caller only knows
    // the repository type as a string (e.g., from configuration).
    func (f *RepositoryFactory) CreateRepository(ctx context.Context, schoolID uint, repoType string) (interface{}, error) {
    	repos, err := f.ForSchool(ctx, schoolID)
    	if err != nil {
    		return nil, err
    	}

    	switch repoType {
    	case "auth":
    		return repos.Auth, nil
    	case "school":
    		return repos.School, nil
    	case "user":
    		return repos.User, nil
    	// Phase 2+: add cases for academic, score, result, student, teacher, etc.
    	default:
    		return nil, fmt.Errorf("%w: %s", ErrRepositoryNotImplemented, repoType)
    	}
    }
    ```

    **Design decisions:**
    - Matches existing `New*Repository(db *gorm.DB)` pattern exactly
    - Core DB repos (auth, school, user) always use the shared core DB — these contain cross-tenant data
    - Tenant DB repos will use the school-specific `*gorm.DB` (populated in Phase 2)
    - `CreateRepository()` switch allows string-based lookup (useful for middleware/dispatch patterns)
    - `ErrRepositoryNotImplemented` is a sentinel error, checkable with `errors.Is()`
    - Per user decisions: backward-compatible, non-breaking, bridge to Phase 2
  </action>
  <verify>
    <automated>cd backend && go build ./internal/database/tenant/</automated>
  </verify>
  <done>
    RepositoryFactory created. ForSchool returns TenantRepositories with core+tenant DB separation. CreateRepository dispatches by type. ErrRepositoryNotImplemented for unknown types. Build passes.
  </done>
</task>

---

## Threat Model

### Trust Boundaries

| Boundary | Description |
|----------|-------------|
| App → EncryptionService | Plaintext credentials cross this boundary |
| ConnectionManager → Tenant DB | Encrypted credentials are decrypted, then cross to tenant DB |
| Schools table | Encrypted credentials stored at rest in `database_password_encrypted` column |

### STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | EncryptionService | mitigate | Sanitize ENCRYPTION_KEY from log output; never log key, plaintext, or ciphertext content |
| T-01-02 | Tampering | EncryptionService (GCM nonce) | mitigate | Generate nonce per-call via crypto/rand; never accept external nonce (Pitfall 1 guard) |
| T-01-03 | Information Disclosure | schools table | mitigate | Never store plaintext passwords; encrypt with AAD bound to school ID |
| T-01-04 | Information Disclosure | ConnectionManager logs | mitigate | Never log decrypted passwords or DSN strings containing plaintext passwords |
| T-01-05 | Elevation of Privilege | ConnectionManager | mitigate | Validate school.database_status before connecting; reject 'failed'/'disabled' schools |
| T-01-06 | Spoofing | ConnectionManager | accept | School ID comes from JWT claims validated by auth middleware (Phase 4 concern) |
| T-01-07 | Denial of Service | ConnectionManager pool | accept | Pool size limits (SetMaxOpenConns) prevent runaway connections per school; global limit not enforced until needed |
| T-01-08 | Repudiation | Schema migration | accept | Migration IDs in schema_migrations table provide audit trail for schema changes |

---

## Verification

```bash
# 1. Build all modified packages
cd backend && go build ./internal/crypto/ ./internal/config/ ./internal/database/migrations/ ./internal/database/models/ ./internal/database/tenant/

# 2. Run encryption unit tests
go test ./internal/crypto/ -v -count=1 -run TestEncrypt

# 3. Vet all new packages
go vet ./internal/crypto/ ./internal/database/tenant/

# 4. Run all tests (ensure no regressions)
go test ./internal/... -count=1 -timeout 120s
```

## Success Criteria

1. ✅ `crypto.Service.Encrypt(plaintext, aad)` produces a valid base64 string; decrypt roundtrip returns original
2. ✅ `schools` table has all 7 new database connection columns (via raw SQL, idempotent)
3. ✅ `database_connections` and `tenant_backups` tables exist with correct schemas
4. ✅ Go models exist: `SchoolConnection`, `DatabaseConnection`, `TenantBackup`
5. ✅ `ConnectionManager.GetConnection(schoolID)` returns configured GORM connection with proper pool settings
6. ✅ ConnectionManager health checks evict stale connections automatically
7. ✅ `RepositoryFactory.ForSchool(schoolID)` returns `TenantRepositories` with core-DB repos populated
8. ✅ `ErrRepositoryNotImplemented` returned for unimplemented repository types
9. ✅ All packages build cleanly, all tests pass

## Post-Execution

After all 4 sub-plans complete, update:
- `.planning/ROADMAP.md` — mark Phase 1 as complete, update plan checkbox status
- `.planning/REQUIREMENTS.md` — mark GSD-R1 through GSD-R4 as Complete
- Create `.planning/phases/01-core-database-setup/01-01-SUMMARY.md` through `01-04-SUMMARY.md`
