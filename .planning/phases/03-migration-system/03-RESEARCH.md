# Phase 3 — Migration System Research

## Current State

All 12 migration groups live in a flat package `internal/database/migrations/`:

```
internal/database/migrations/
├── migrations.go          # Migration struct, migrator (unexported), New(), Run(), Rollback()
├── phase1.go              # CORE: schools, roles, users, user_infos, tenants
├── phase2.go              # SCHOOL: attendance, cba_*, books, hostels, transport, exam_*, reports
├── phase3.go              # SCHOOL: audit_logs
├── phase4.go              # SCHOOL: courses, lessons, LMS tables
├── phase5.go              # SCHOOL: report_cards
├── phase_auth_rewrite.go  # CORE: access_tokens, blacklisted_tokens, token_families
├── phase_auth_phase2.go   # CORE: validation_tokens
├── phase_multitenant.go   # CORE: school DB connection fields, database_connections, tenant_backups
├── phase_core_models.go   # SCHOOL (misnamed): subjects, levels, students, teachers, scores, timetables, bills, etc.
├── phase_modules.go       # SCHOOL: inventory, pastoral care, alumni, HR, finance, etc.
├── admissions.go          # SCHOOL: admission_intakes, applications, etc.
└── rbac.go                # CORE: system roles, immutable flags, role seeding
```

### Classification

| Category | Files | Tables Created |
|----------|-------|---------------|
| **CORE** (shared DB) | phase1, phase_auth_*, phase_multitenant, rbac | schools, roles, users, tokens, DB configs |
| **SCHOOL** (per-tenant DB) | phase2-5, core_models, modules, admissions | academic, scores, LMS, admissions, inventory, pastoral care, HR, finance |

### Architecture constraints

1. `migrator` struct is **unexported** — only accessible via `migrations.New(db)` / `.Run()` / `.Rollback()`
2. All migrations are registered **at construction time** in `New()` — no way to select subsets
3. `schema_migrations` table is managed by the migrator itself (created in `Run()`)
4. Core DB is created/maintained by Laravel — our Go migrations only **add** to existing tables
5. `cmd/server/main.go` calls `migrations.New(db).Run()` at startup

### Design considerations

- School migrations must run **on each tenant's dedicated database**, not the core DB
- Each tenant DB needs its own `tenant_schema_migrations` tracking table
- `migrator` logic (table creation, idempotent apply, rollback) is reusable with any `*gorm.DB`
- Existing `migrations.New(db)` must remain functional for backward compatibility
- Parallel tenant migration must respect a configurable concurrency limit

## Proposed Architecture

```
internal/database/migrations/
├── core/                      # Core migration definitions (shared DB)
│   └── core.go                #   CoreMigrations() []Migration
├── school/                    # School migration definitions (per-tenant DB)
│   └── school.go               #   SchoolMigrations() []Migration
├── migrator.go                # ReusableMigrator (exported, works with any []Migration + *gorm.DB)
├── migrations.go              # Existing package — refactored to use ReusableMigrator internally

internal/database/tenant/
├── migration_service.go       # MigrationService with ApplyCore + ApplySchool + MigrateAllTenants
├── connection_manager.go      # No changes needed
└── factory.go                 # No changes needed
```

### ReusableMigrator design

```go
// Exported, works with any []Migration and any *gorm.DB
type ReusableMigrator struct {
    db         *gorm.DB
    migrations []Migration
    tableName  string  // "schema_migrations" for core, "tenant_schema_migrations" for school
}
```

### MigrationService design

```go
type MigrationService struct {
    coreDB  *gorm.DB
    manager *ConnectionManager
    factory *RepositoryFactory
}

func (s *MigrationService) ApplyCoreMigrations() error
func (s *MigrationService) ApplySchoolMigrations(tenantDB *gorm.DB, schoolID uint) error
func (s *MigrationService) GetCoreStatus() ([]MigrationStatus, error)
func (s *MigrationService) GetSchoolStatus(tenantDB *gorm.DB) ([]MigrationStatus, error)
func (s *MigrationService) MigrateAllTenants(ctx context.Context, concurrency int) (*MigrationReport, error)
```

### MigrationStatus

```go
type MigrationStatus struct {
    ID        string
    AppliedAt *time.Time  // nil = pending
}

type MigrationReport struct {
    Total     int
    Succeeded int
    Failed    int
    Results   []SchoolMigrationResult
}

type SchoolMigrationResult struct {
    SchoolID  uint
    SchoolName string
    Status    string  // "success", "failed", "skipped"
    Error     string
}
```

### Backward compatibility

```go
// migrations/migrations.go — Updated constructor
func New(db *gorm.DB) *migrator {
    allMigrations := append(core.CoreMigrations(), school.SchoolMigrations()...)
    return newMigratorWithTable(db, allMigrations, "schema_migrations")
}
```

No changes to `cmd/server/main.go` required.
