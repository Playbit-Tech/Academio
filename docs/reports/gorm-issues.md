# GORM Issues with `SchemaTablePrefix` Plugin

**GORM version**: `v1.31.2`
**Go version**: 1.26
**PostgreSQL driver**: `pgx/v5`
**Project**: Schema-per-tenant multi-tenant backend (∼58K lines Go, 39 modules)

---

## Context

We implement PostgreSQL schema-per-tenant isolation using a GORM plugin (`SchemaTablePrefix`) registered on the shared/core database connection. The plugin intercepts all query types (`Create`, `Query`, `Update`, `Delete`, `Row`, `Raw`) and prepends the tenant schema to `Statement.Table` — e.g., `users` → `school_42.users`.

```go
// Plugin registration (once, on the shared/core DB)
coreDB.Use(SchemaTablePrefix())

// Tenant-scoped session factory
func (s *SchemaDB) DB() *gorm.DB {
    ctx := context.WithValue(context.Background(), schemaCtxKey{}, s.schemaName)
    return s.db.Session(&gorm.Session{Context: ctx}).
        Set("schema_table_prefix", s.schemaName)
}
```

The plugin callback:

```go
func (p *schemaTablePrefixPlugin) prefix(db *gorm.DB) {
    schema, _ := db.Get("schema_table_prefix")
    schemaStr, _ := schema.(string)
    if schemaStr == "" || db.Statement.Table == "" {
        return
    }
    prefix := schemaStr + "."
    if !strings.HasPrefix(db.Statement.Table, prefix) {
        db.Statement.Table = prefix + db.Statement.Table
    }
}
```

---

## Issue 1: `PrepareStmt: true` + schema prefix callback → `Create` panics

### Severity
**CRITICAL** — crashes the server on insert operations.

### Description

When `PrepareStmt: true` is set in `gorm.Config`, the first `Create` call that goes through a schema-scoped session (with the `SchemaTablePrefix` plugin active) **panics** with a field-type mismatch inside GORM's prepared statement machinery.

The panic occurs because the prepared statement cache caches the field-index mapping **before** the schema prefix plugin modifies `Statement.Table`. When `Create` executes, GORM's `ConvertToCreateValues` uses the cached field-index mapping from the prepared statement, but the model's field metadata now references the schema-prefixed table name, causing a type mismatch in the auto-timestamp values (e.g., setting `time.Time` on a `*string` field).

### Stack trace (simplified)

```
panic: interface conversion: interface {} is time.Time, not *string

goroutine XXX [running]:
gorm.io/gorm/callbacks.ConvertToCreateValues(...)
    /go/pkg/gorm.io/gorm@v1.31.2/callbacks/create.go:XXX
gorm.io/gorm/callbacks.BeforeCreate(...)
    /go/pkg/gorm.io/gorm@v1.31.2/callbacks/create.go:XXX
```

### Root cause

The `PrepareStmt` cached prepared statement stores field metadata indexed by the **original** table name. The `SchemaTablePrefix` plugin mutates `Statement.Table` from `users` → `school_X.users` in its `Before("*")` callback. When GORM later resolves field indices for auto-updating timestamps (`CreatedAt`, `UpdatedAt`), it uses the stale mapping, causing `time.Time` values to be cast against `*string` fields (or similar type mismatches).

### Workaround

```go
// postgres.go
db, err := gorm.Open(postgres.Open(cfg.DSN()), &gorm.Config{
    PrepareStmt: false,  // ← disable prepared statement caching
    // ...
})
```

Setting `PrepareStmt: false` on the **shared** (plugin-registered) DB eliminates the panic. Tenant-specific connections (per-school direct PostgreSQL connections) can still use `PrepareStmt: true` safely since they don't use the `SchemaTablePrefix` plugin.

```go
// connection_manager.go — per-tenant direct connections (no plugin)
db, err := gorm.Open(postgres.Open(cfg.DSN()), &gorm.Config{
    PrepareStmt: true,  // ← safe on per-tenant DSN connections
})
```

### Impact

Loss of prepared statement caching on the shared DB reduces query performance for cross-schema administrative queries. All 85+ `Create` operations that go through the shared DB (e.g., `User` registration in the shared `users` table) require `PrepareStmt: false`.

### Reproduction

1. Register `SchemaTablePrefix` plugin on a GORM DB with `PrepareStmt: true`.
2. Create a session via `db.Session(&gorm.Session{Context: ctx}).Set("schema_key", schemaName)`.
3. Call `.Create(&model{})` on that session.
4. Observe panic on the first or second creation with auto-timestamp fields.

---

## Issue 2: Many-to-many `Preload` returns empty results with `SchemaTablePrefix` plugin

### Severity
**HIGH** — silent data loss; no error, just empty results.

### Description

When a model uses a **many-to-many** `Preload` (e.g., `Preload("Curriculums")` through a join table), and the `SchemaTablePrefix` plugin is registered on the shared DB, GORM returns **empty results** for the many-to-many association. The join table is not schema-prefixed, and the query silently fails to find rows.

Has-many and belongs-to `Preload` relations work correctly — the issue is specific to **many-to-many** associations.

### Examples

#### Works correctly (has-many)

```go
// assessments has-many grade_items — WORKS
db.Preload("Assessments.GradeItems").Find(&curriculum)
// Generated SQL:
//   SELECT * FROM school_9.assessments WHERE curriculum_id IN (1)     ✓ prefixed
//   SELECT * FROM school_9.grade_items WHERE assessment_id IN (1,2,3) ✓ prefixed
```

#### Returns empty results (many-to-many)

```go
// sessions many-to-many curriculums via session_curriculum join — EMPTY
db.Preload("Curriculums.Assessments.GradeItems").First(&session, id)
// Generated SQL:
//   SELECT * FROM session_curriculum WHERE session_id = 1             ← NOT prefixed!
//   (returns 0 rows because the real table is school_9.session_curriculum)
```

The join table query (`session_curriculum`) is **not** schema-prefixed even though the callback is registered. Has-many Preloads (e.g., `assessments`, `grade_items`) use the main model's prefixed table name to resolve the foreign key, which works because the main query already has the prefix. Many-to-many Preloads generate a **new** table reference for the join table, and the callback does not apply the prefix to this derived reference.

### Root cause

GORM's many-to-many Preload generates join-table SQL in the `Preload` callback chain, creating a new `Statement.Table` reference for the join table. The `SchemaTablePrefix` plugin's `Before("*")` callback is called, but the join table name in the generated SQL does not go through the same callback resolution path. The field-index mapping that associates the many-to-many relationship with the join table appears to be computed before the plugin modifies `Statement.Table`, causing the schema prefix to be lost specifically for many-to-many join tables.

### Workaround

Replace many-to-many `Preload` with manual raw SQL using explicit schema prefix:

```go
func (r *AcademicRepository) loadSessionCurriculums(ctx context.Context, s *models.Session, preloadAssessments bool) error {
    schemaName := tenant.SchemaNameFromDB(r.db)

    // Step 1: Query join table with explicit schema prefix
    var linkIDs []uint
    if err := r.db.WithContext(ctx).Raw(
        fmt.Sprintf("SELECT curriculum_id FROM %s.session_curriculum WHERE session_id = ?", schemaName),
        s.ID,
    ).Scan(&linkIDs).Error; err != nil {
        return err
    }

    // Step 2: Query curriculums with explicit schema prefix
    var curriculums []models.Curriculum
    curSQL := fmt.Sprintf("SELECT * FROM %s.curriculums WHERE id IN (?)", schemaName)
    if err := r.db.WithContext(ctx).Raw(curSQL, linkIDs).Scan(&curriculums).Error; err != nil {
        return err
    }

    // Step 3: Load nested has-many (works with standard GORM Preload)
    if preloadAssessments {
        for i := range curriculums {
            var assessments []models.Assessment
            assSQL := fmt.Sprintf("SELECT * FROM %s.assessments WHERE curriculum_id = ? ORDER BY sort_order ASC", schemaName)
            if err := r.db.WithContext(ctx).Raw(assSQL, curriculums[i].ID).Scan(&assessments).Error; err != nil {
                return err
            }
            // Load grade items similarly...
            curriculums[i].Assessments = assessments
        }
    }

    s.Curriculums = curriculums
    return nil
}
```

### Impact

Every many-to-many `Preload` in the codebase must be replaced with manual raw SQL workarounds. For our project, this affects:
- `Session` ↔ `Curriculum` (via `session_curriculum`)
- All other many-to-many relationships through the shared DB

### Reproduction

1. Register `SchemaTablePrefix` plugin on a GORM DB.
2. Define a model with a many-to-many relationship (e.g., `Session` ↔ `Curriculum` via `session_curriculum`).
3. Call `db.Session(&Session{Context: ctx}).Set("schema_key", schemaName).Preload("Curriculums").First(&session)`.
4. Observe that `session.Curriculums` is empty, with no error raised.
5. Verify data exists in the join table with a direct query.

---

## Combined impact

| Feature | Status | Workaround |
|---|---|---|
| `Create` with `PrepareStmt: true` | **Panics** | Set `PrepareStmt: false` on shared DB |
| Has-many `Preload` | **Works** | No workaround needed |
| Belongs-to `Preload` | **Works** | No workaround needed |
| Many-to-many `Preload` | **Empty results** | Replace with raw SQL with explicit schema prefix |
| `WithContext()` on schema session | **Loses context key** | Use `Set()` to carry schema value (survives clone) or `InjectSchemaToContext` helper |

## Suggested fixes (GORM upstream)

1. **PrepareStmt + plugin callbacks**: When `Statement.Table` is modified by a `Before("*")` callback, invalidate or re-index the prepared statement cache entry for that query.

2. **Many-to-many Preload + table prefix plugins**: Ensure that join table references generated during many-to-many Preload resolution respect any table prefix modifications applied by registered callbacks. Alternatively, expose the join table name through the same callback path that main queries use.

---

*Report generated from production codebase analysis — GORM v1.31.2, PostgreSQL 16 via pgx/v5, Go 1.26, schema-per-tenant multi-tenant architecture.*
