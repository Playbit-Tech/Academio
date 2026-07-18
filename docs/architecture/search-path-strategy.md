# Search Path Isolation Strategy

> **Status**: Adopted  
> **Date**: 2026-07-18  
> **Scope**: Schema-per-tenant isolation in shared PostgreSQL database  
> **Related**: `10-AUDIT-CHECKLIST.md` §13 (Tenant Isolation), `schema_db.go`, `migration_service.go`, `provisioning.go`, `backup/service.go`, `restore/service.go`

---

## Problem

Academio uses schema-per-tenant isolation — each school's data lives in its own PostgreSQL schema (`school_{id}`). Every query must target the correct tenant schema. PostgreSQL's `search_path` controls which schema unqualified table references resolve to — but setting `search_path` at the connection level is incompatible with PgBouncer transaction pooling because:

1. **Connection multiplexing**: PgBouncer pools connections across users. A `SET search_path` on one connection leaks to the next user reusing that connection, routing their queries to the wrong tenant schema.

2. **`SET LOCAL` scoping**: `SET LOCAL search_path` survives only inside a transaction — any query outside a transaction uses the default `search_path`, causing unqualified table references to miss the tenant schema entirely.

3. **DDL conflicts**: `pgx` v5 prepared-statement caching is invalidated by DDL (ALTER TABLE, CREATE TABLE). Migration code must use a separate connection without prepared statements, making search_path management even more fragile.

---

## Strategy: GORM `SchemaTablePrefix` Plugin (Default)

The primary isolation mechanism is a **GORM plugin** that prefixes every table name with the schema at the SQL statement level — before the query reaches PostgreSQL. This approach:

- **Works with any connection pool mode** (PgBouncer transaction, session, or statement).
- **Survives `.WithContext()`, session cloning, and connection pool reuse** because the prefix is baked into the SQL string, not stored in connection state.
- **Covers all GORM operations**: Create, Query, Update, Delete, Row, Raw callbacks.
- **Requires zero PostgreSQL session state changes**.

### How It Works

```
┌──────────────┐     SchemaTablePrefix plugin      ┌──────────────┐
│  GORM Query  │ ──→  db.Statement.Table =          │  PostgreSQL  │
│  .Find(&u)   │      "school_42.users"             │  school_42   │
└──────────────┘     (prefix applied in callback)    └──────────────┘
```

The schema name is carried via:
1. **GORM `Statement.Set("schema_table_prefix", ...)`** — survives `Statement.clone()` deep-copies during `.Session()` and `.WithContext()`.
2. **Context value (`schemaCtxKey{}`)** — fallback for legacy paths; set by `InjectSchemaToContext()`.

---

## Decision: GORM Plugin over `SET search_path`

| Approach | PgBouncer Compatible | Survives Connection Pool Reuse | Scope of Effect | Used Where |
|----------|---------------------|-------------------------------|-----------------|------------|
| **GORM `SchemaTablePrefix` plugin** | ✅ Yes | ✅ Yes | Per-`*gorm.DB` session | All API queries (CRUD via GORM models) |
| **`SET LOCAL search_path` in transaction** | ✅ Yes (inside tx only) | ❌ No (reset on tx end) | Per-transaction | Tenant migrations (DDL) |
| **`SET search_path` (connection-level)** | ❌ No | ❌ No (leaks across users) | Per-connection | ❌ Not used anywhere |

### Rationale

| Criterion | Plugin Wins Because |
|-----------|-------------------|
| **PgBouncer transaction mode** | No session state mutation — SQL is self-contained |
| **Connection pool reuse** | Prefix is in the SQL string, not the connection |
| **Multi-statement safety** | Each statement is independently qualified |
| **Prepared statements** | Compatible with pgx prepared-statement cache |
| **DDL safety** | No search_path dependency for CREATE TABLE/ALTER |

The plugin is **not used** for:
- `pg_dump`/`pg_restore` (CLI tools, not GORM) — uses `--schema=` flag
- `CREATE SCHEMA` (raw SQL, not table-level) — uses explicit schema name
- Tenant migrations (DDL with prepared-statement conflicts) — uses `SET LOCAL` in transaction

---

## Code Paths

### 1. API Queries (All GORM Model Operations)

```
All Create / Query / Update / Delete / Row / Raw callbacks
```

| Property | Value |
|----------|-------|
| **Mechanism** | `SchemaTablePrefix` GORM plugin |
| **Coverage** | Every GORM callback registered in `Initialize()` |
| **File** | `backend/internal/database/tenant/schema_db.go` |
| **Entry point** | `SchemaDB.DB()` or `SchemaDB.DBWithContext(ctx)` |
| **Correctness** | ✅ Schema prefix survives `Statement.clone()` via `Set`/`Get` (not `InstanceSet`) |
| **Verification** | Plugin registers before all 6 callback types: Create, Query, Update, Delete, Row, Raw |

**Code flow:**

```go
// schema_db.go
func (s *SchemaDB) DB() *gorm.DB {
    ctx := context.WithValue(context.Background(), schemaCtxKey{}, s.schemaName)
    return s.db.Session(&gorm.Session{Context: ctx}).Set("schema_table_prefix", s.schemaName)
}

// Plugin callback prefixes db.Statement.Table with "school_N."
func (p *schemaTablePrefixPlugin) prefix(db *gorm.DB) {
    // Checks Set() first (survives clone), falls back to context
    settingsVal, settingsOK := db.Get("schema_table_prefix")
    schema := settingsVal  // or ctxVal from schemaNameFromContext()
    db.Statement.Table = schema + "." + db.Statement.Table
}
```

### 2. Tenant Migrations (DDL)

```
ApplySchoolMigrationsForSchema()
```

| Property | Value |
|----------|-------|
| **Mechanism** | `SET LOCAL search_path` inside GORM `Transaction()` |
| **Coverage** | All DDL (CREATE TABLE, ALTER TABLE) and DML in school migrations |
| **File** | `backend/internal/database/tenant/migration_service.go` |
| **Entry** | `ApplySchoolMigrationsForSchema(sharedDB, schemaName, schoolID)` |
| **Correctness** | ✅ Transaction boundary prevents connection leakage — `SET LOCAL` is automatically reverted on transaction commit/rollback |
| **Why not plugin** | DDL invalidates pgx prepared-statement cache; migration code uses a separate `gorm.DB` without `PrepareStmt` and without the plugin |

**Code flow:**

```go
// migration_service.go
func (s *MigrationService) ApplySchoolMigrationsForSchema(sharedDB *gorm.DB, schemaName string, schoolID uint) error {
    // Open a migration-scoped connection without prepared statements (DDL-safe)
    migrationDB := gorm.Open(postgres.New(postgres.Config{Conn: rawDB, PreferSimpleProtocol: true}), ...)

    return migrationDB.Transaction(func(tx *gorm.DB) error {
        // SET LOCAL search_path — scoped to this transaction only
        tx.Exec("SET LOCAL search_path TO " + schemaName)
        return migrations.NewForSchool(tx).RunWithSchema(schemaName)
    })
    // After commit: search_path reverts to default automatically
}
```

**Why this is safe**: The `SET LOCAL` is inside a `GORM.Transaction()` callback. PostgreSQL automatically resets `SET LOCAL` options at transaction end (COMMIT or ROLLBACK). Even if a connection is returned to the pool, the `search_path` is restored to its default — no leakage.

### 3. `pg_dump` / `pg_restore` (Backup & Restore)

```
CreateTenantBackup() / RestoreBackup()
```

| Property | Value |
|----------|-------|
| **Mechanism** | `--schema=` CLI flag |
| **Coverage** | `pg_dump --schema=school_N` / `pg_restore --schema=school_N` |
| **Files** | `backend/internal/backup/service.go`, `backend/internal/restore/service.go` |
| **Correctness** | ✅ Explicit schema targeting — `--schema=` is the most precise way to dump/restore a single schema |
| **Edge case** | `pg_restore --schema=` still drops/recreates only objects within that schema; the `--schema=` flag is the authoritative scoping mechanism |

**Code flow:**

```go
// backup/service.go
args := []string{
    "-d", dsn,
    "--schema=" + schemaName,      // Explicit schema target
    "--no-owner", "--no-acl", "-Fc",
}
cmd := exec.CommandContext(ctx, "pg_dump", args...)
```

### 4. `CREATE SCHEMA` (Schema Creation)

```
ProvisionSchoolSchema() / CreateSchemaAndMigrate()
```

| Property | Value |
|----------|-------|
| **Mechanism** | Explicit schema name in raw SQL |
| **Coverage** | `CREATE SCHEMA IF NOT EXISTS school_{id}` |
| **Files** | `backend/internal/database/tenant/provisioning.go`, `migration_service.go` |
| **Correctness** | ✅ Schema name is built from school ID (`school_%d`) and validated against `safeSchemaNameRegex` before use |
| **Verification** | Regex guard (`^[a-z][a-z0-9_]*$`) catches injection via malformed school ID |

**Code flow:**

```go
// provisioning.go
schemaName := fmt.Sprintf("school_%d", schoolID)
if !safeSchemaNameRegex.MatchString(schemaName) {
    return fmt.Errorf("invalid schema name %q", schemaName)
}
rawDB.ExecContext(ctx, "CREATE SCHEMA IF NOT EXISTS "+schemaName)
```

---

## Raw SQL with Explicit Schema Qualifiers

Several modules use raw SQL with explicit schema-qualified table names. This is an acceptable pattern — it does **not** depend on `search_path` because the schema is baked into the SQL:

| Module | File | Pattern | Purpose |
|--------|------|---------|---------|
| Academic | `repository.go` | `%s.session_curriculum`, `%s.curriculums`, `%s.assessments`, `%s.grade_items` | Preloading linked curricula with assessments and grade items |
| Academic | `service.go` | `%s.students` | Promoting students to next level |
| School | `service.go` | `public.schools` | Updating school status after provisioning (explicit `public` to avoid leaked search_path) |

These are correct-by-construction: the `%s` is always the tenant schema name resolved from context, and the resulting SQL is a fully-qualified reference.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Dangerous |
|---|---|
| `SET search_path` (without `LOCAL`) at connection level | Leaks to other users on pooled connections — PgBouncer incompatible |
| `SET search_path` outside a transaction | Even with `SET LOCAL`, effective only during a transaction |
| Assuming `search_path` includes tenant schema | Schema scope is set programmatically; relying on PG defaults is fragile |
| Hardcoded schema names in SQL | Must be resolved from `schools` table at runtime |
| `fmt.Sprintf` for raw SQL without schema qualifier | Unqualified table name uses `search_path` (defaults to `public`) |

**Rule of thumb**: If the query touches a tenant table, either:
1. Use `SchemaDB.DB()` (GORM plugin prefix) — for all GORM model queries.
2. Use `%s.tablename` with schema name from `SchemaNameFromDB(ctx)` — for raw SQL.
3. Use `--schema=` flag — for `pg_dump`/`pg_restore`.
4. Use `SET LOCAL search_path` inside a transaction — for migrations only.

---

## Verification

After any code changes, verify no connection-level `SET search_path` leaks exist:

```bash
cd backend && rg "SET search_path" internal/ | grep -v "SET LOCAL" | grep -v "^\s*//"
```

Expected output: empty (zero matches).

---

## References

- `backend/internal/database/tenant/schema_db.go` — `SchemaTablePrefix` plugin
- `backend/internal/database/tenant/migration_service.go` — `SET LOCAL search_path` in migration transactions
- `backend/internal/database/tenant/provisioning.go` — `CREATE SCHEMA` with explicit name
- `backend/internal/backup/service.go` — `pg_dump --schema=` flag
- `backend/internal/restore/service.go` — `pg_restore --schema=` flag
- `backend/internal/modules/school/service.go` — `public.schools` explicit qualifier
- `backend/internal/modules/academic/repository.go` — Raw SQL with `%s.*` schema qualifiers
- `docs/architecture/10-AUDIT-CHECKLIST.md` §13 — Tenant Isolation
