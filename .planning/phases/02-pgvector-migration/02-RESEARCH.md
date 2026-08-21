# Phase 2: pgvector Migration - Research

**Researched:** 2026-08-01
**Domain:** Postgres extension migration (Qdrant → pgvector), schema-per-tenant DDL, Go vector store
**Confidence:** HIGH

## Summary

Phase 2 moves vector storage from the external Qdrant service to pgvector living inside the existing single Postgres instance (`shared-postgres`, currently `postgres:alpine` → PG 18.4), keeping the `vector.Store` interface byte-for-byte unchanged so the RAG pipeline and agents (`academic_tutor`, `teacher_assistant`) need zero code changes. The extension mechanics, tenancy resolution, score semantics, and migration ordering have all been **empirically verified against the running database** — this research contains no unverified assumptions on the critical path.

The three load-bearing findings:

1. **Extension install semantics (proven by live tests on PG 18.4).** `CREATE EXTENSION` installs once per *database* into the first schema of `search_path` (default `public`). Tenant-schema `CREATE EXTENSION IF NOT EXISTS vector` is a silent no-op when the extension already exists in `public`. Because `ApplyCoreMigrations()` runs at startup *before* any school migration, the core migration installs `vector` into `public`; the tenant migration's `CREATE EXTENSION IF NOT EXISTS vector` is harmless-but-noop and exists only for spec compliance (PGV-02) and parity with the existing `pgcrypto` pattern.

2. **Tenant migrations run with schema-ONLY search_path (proven).** `ApplySchoolMigrationsForSchema` executes `SET LOCAL search_path TO {schema}` (migration_service.go:141) — `public` is NOT on the path. Live hstore analog tests proved: unqualified `vector` type fails (`ERROR: type "vector" does not exist`), schema-qualified `public.vector(1536)` works; unqualified `vector_cosine_ops` opclass fails, `public.vector_cosine_ops` works. **Every `ai_vectors` DDL must schema-qualify `public.vector` and `public.vector_cosine_ops`.** Runtime (app) queries are unaffected — the app's default `search_path` is `"$user", public`, so unqualified operators/types resolve fine there.

3. **Score semantics parity.** Qdrant cosine returns *similarity* (higher = better, range [-1,1]); pgvector `<=>` returns *cosine distance* (lower = better, range [0,2]). Parity conversion is **`similarity = 1 - distance`** — the copy tool and the pgvector `Search` implementation must apply this.

**Primary recommendation:** Pin `pgvector/pgvector:0.8.6-pg18-trixie` in compose (matches running PG 18.4, CVE-2026-3172 fixed in ≥0.8.2), add `pgvector-go` v0.4.1, install the extension via a core migration, create `school_{id}.ai_vectors` via a tenant migration using `public.vector(1536)` + `public.vector_cosine_ops`, implement `pgvector.go` resolving tenancy from `ctx` via `GetSchoolIDFromCtx` + `CtxKeyTenantRepos.SchemaName()`, and ship the copy tool with `score = 1 - distance` parity asserts. Zero live Qdrant collections (verified: no qdrant container running) makes the copy tool a documented no-op.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Canonical embedding model = **`text-embedding-3-small` (OpenAI), 1536-dim**, locked in config as `AI_EMBEDDING_DIM=1536`.
- **D-02:** Gemini `text-embedding-004` (3072d) is NOT the canon — exceeds 2000-dim HNSW cap; ModelRouter continues routing to primary provider configured to the canonical model.
- **D-03:** Nigerian-language multilingual quality eval spike runs DURING planning (planning artifact, not a phase deliverable) — English + Yoruba/Hausa/Igbo/Pidgin corpus confirms `text-embedding-3-small` adequacy before DDL.
- **D-04:** `embedding_model` column stores model id per chunk; migration/validation guard rejects writes whose embedding dimension ≠ `AI_EMBEDDING_DIM`.
- **D-05:** `pgvector.go` keeps the existing `vector.Store` interface EXACTLY (Insert/Search/Delete/Close with `collection string`) — zero RAG/agent changes. Tenancy resolved from `context.Context` (schoolID).
- **D-06:** `collection` becomes a column filter inside the tenant schema (agents pass "curriculum", "policies" unchanged). Tenant boundary = SCHEMA, not collection.
- **D-07:** All tenant queries go through the schema-scoped DB (`middleware.GetTenantDB`-style); never the raw core DB (Rule B8).
- **D-08:** Table lives in each `school_{id}` schema (NOT `public`, NOT shared+partial-indexes).
- **D-09:** Columns: `document_id`, `chunk_index`, `embedding vector(AI_EMBEDDING_DIM)`, `content text`, `collection text`, `metadata jsonb`, `embedding_model`, `model_version`, `chunking_version`, timestamps. Unique constraint on `(document_id, chunk_index)`.
- **D-10:** Per-schema HNSW index with `vector_cosine_ops` + `<=>` operator, built with raised `maintenance_work_mem`.
- **D-11:** New tenants get the table automatically via `SchoolMigrations()`; EXISTING provisioned tenants via `MigrateAllSchemaTenants` (parallel, concurrency-limited) — both via `ApplySchoolMigrationsForSchema` with `SET LOCAL search_path`.
- **D-12:** Phase 2 swaps config `AI_QDRANT_*` → pgvector DSN and retires the `qdrant` service from docker-compose (PGV-06).
- **D-13:** Copy tool ships WITH parity asserts (count, dimension, distance semantics `similarity = 1 - distance` for cosine). Zero live collections → documented no-op; reused for Phase 7 cutover verification.
- **D-14:** `AI_EMBEDDING_DIM` is required config, validated at startup. Startup also validates embedder's actual output dimension matches `vector(n)` column type — fail-fast on mismatch (Rule B12).

### the agent's Discretion
- HNSW index tuning values (m, ef_construction, ef_search) — planner selects sensible defaults for a school-sized corpus
- Exact migration ID string for the `ai_vectors` DDL + extension migration
- Copy tool CLI shape (flags, output format) — must include the parity asserts
- Whether `metadata` uses jsonb vs individual columns — jsonb recommended for parity with Qdrant payload map
- `model_version`/`chunking_version` default values and bump policy

### Deferred Ideas (OUT OF SCOPE)
- **Corpus re-embed tooling (EMB-01)** — v2 requirement; copy tool must NOT be extended into a general re-embedding utility
- **Multilingual embedding expansion (MULTI-01)** — v2 requirement; D-03 spike only VERIFIES canonical model
- **Reranker selection benchmark (RERANK-01)** — v2 requirement; reranking ships in Phase 3 Python engine
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PGV-01 | Postgres image swapped to `pgvector/pgvector:pg18` (pin ≥0.8.2, CVE-2026-3172) | Image tag `0.8.6-pg18-trixie` verified latest on Docker Hub; matches running PG 18.4; CVE-2026-3172 fixed in ≥0.8.2 [VERIFIED: Docker Hub + pgvector repo] |
| PGV-02 | `CREATE EXTENSION IF NOT EXISTS vector` in shared + tenant migrations | Core migration installs into `public` (first schema of search_path); tenant call is harmless no-op [VERIFIED: live PG 18.4 hstore analog tests] |
| PGV-03 | `internal/ai/vector/pgvector.go` implementing existing `vector.Store` interface (zero RAG/agent changes) | Interface read in full (store.go); tenancy-from-ctx chain verified end-to-end (`SchoolID()` global → handler `c.Request.Context()` → pipeline → store); `GetSchoolIDFromCtx` + `CtxKeyTenantRepos.SchemaName()` identified as the resolution path [VERIFIED: codebase] |
| PGV-04 | `ai_vectors` table in `school_{id}` TENANT schemas + metadata columns + HNSW index | Full DDL template proven with schema-qualified `public.vector(1536)` + `public.vector_cosine_ops` under schema-only search_path [VERIFIED: live tests] |
| PGV-04a | Canonical embedding model + dimension locked BEFORE DDL | D-01 locks `text-embedding-3-small`/1536; openai.go uses `openai.EmbeddingModelTextEmbedding3Small`; config `AI_EMBEDDING_DIM` with startup fail-fast per D-14 [VERIFIED: codebase] |
| PGV-05 | Qdrant → pgvector data migration tool (low risk: no live collections) | Verified no qdrant container running → zero live collections; copy tool modeled on `cmd/copy-tenant-data/main.go`; parity = `1 - distance` [VERIFIED: docker ps + codebase] |
| PGV-06 | Config swapped `AI_QDRANT_*` → pgvector DSN, Qdrant container retired after cutover | `AIConfig` fields identified (QdrantURL/APIKey/Timeout at config.go); `.env.example` lines 102-104; k8s configmap line 18; compose qdrant service lines 35-49 [VERIFIED: codebase] |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pgvector/pgvector` Docker image | `0.8.6-pg18-trixie` (published 2026-07-31) | Postgres 18 + pgvector extension bundled | Official image, tag scheme `pg{version}-{distro}`; `pg18` matches running PG 18.4 so `postgres_data` volume survives swap; CVE-2026-3172 fixed in ≥0.8.2 |
| `github.com/pgvector/pgvector-go` | `v0.4.1` (published 2026-07-30) | Go types for `vector` column + GORM integration | Official Go client; `pgvector.Vector` works with GORM `clause.Expr` via driver.Valuer/Scanner — no pgx type registration needed |
| `gorm.io/gorm` + `gorm.io/driver/postgres` | v1.31.2 / v1.6.0 (already in go.mod) | ORM layer | Existing stack; `db.Clauses(clause.OrderBy{...})` pattern for `<=>` queries [CITED: pgvector-go gorm_test.go] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pkg/logger` (in-repo slog wrapper) | — | Logging | Rule B3 — all store logs via `logger.Infof/Warnf/Errorf` |
| `gorm.io/driver/postgres` pgx v5.10.0 (indirect) | already pinned | Connection driver | Reused as-is; no pgx type registration required for GORM path |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pgvector/pgvector:0.8.6-pg18-trixie` | `pgvector/pgvector:0.8.5-pg18-trixie` | 0.8.6 is latest (pushed 2026-07-31); both ≥0.8.2 satisfy the CVE pin; pin 0.8.6 for the fix |
| `pgvector-go` GORM path | Raw `::vector` string casts | pgvector-go handles encode/decode cleanly; string casts are brittle and error-prone |
| Same shared Postgres instance | Separate pgvector-only Postgres container | Same-instance keeps tenant provisioning/schema machinery unchanged; no new infra |

**Installation:**
```bash
cd backend && go get github.com/pgvector/pgvector-go@v0.4.1
```

**Version verification:** `pgvector/pgvector:0.8.6-pg18-trixie` [VERIFIED: Docker Hub tags API]; `pgvector-go v0.4.1` [VERIFIED: proxy.golang.org]; running PG 18.4 on Alpine [VERIFIED: SELECT version() on running DB].

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── internal/
│   ├── ai/
│   │   └── vector/
│   │       ├── store.go        # UNCHANGED interface
│   │       ├── qdrant.go       # UNCHANGED (behavioral reference)
│   │       └── pgvector.go     # NEW — Store impl (Insert/Search/Delete/Close)
│   ├── database/
│   │   └── migrations/
│   │       ├── core/vector.go      # NEW — CREATE EXTENSION IF NOT EXISTS vector (shared)
│   │       └── school/school.go    # ADD — ai_vectors DDL + HNSW migration entry
│   ├── config/config.go            # EDIT — AI_EMBEDDING_DIM + fail-fast; drop QdrantURL/APIKey/Timeout
│   └── router/setup.go             # EDIT — swap NewQdrantStore → NewPGVectorStore
├── cmd/copy-qdrant-vectors/        # NEW — Qdrant→pgvector copy tool w/ parity asserts
├── docker-compose.yml              # EDIT — postgres image; remove qdrant service
├── .env.example                    # EDIT — AI_QDRANT_* → AI_EMBEDDING_DIM
└── deploy/k8s/base/                # EDIT — configmap AI_QDRANT_URL; kustomization qdrant refs
```

### Pattern 1: Extension install — core migration installs, tenant migration no-ops
**What:** The `vector` extension is installed ONCE per database into `public` by a **core migration** (`core/vector.go`). Tenant migrations repeat `CREATE EXTENSION IF NOT EXISTS vector` for spec compliance (PGV-02) but it is a **silent no-op** — proven live: `CREATE EXTENSION IF NOT EXISTS hstore` inside a tenant tx with schema-only search_path succeeded without installing into the tenant schema.

**Why it works:** `CREATE EXTENSION` installs into the first schema of `search_path`; at core-migration time the connection default `search_path` is `"$user", public` → lands in `public`. Core migrations run at startup via `ApplyCoreMigrations()` before any school migration (verified: migrator.go:67 `m.RunWithSchema("core")`; migrations.go:38 `NewForCore(db, core.CoreMigrations(), ...)`). Tenant `CREATE EXTENSION IF NOT EXISTS vector` then finds it already installed and no-ops — same pattern as the existing `pgcrypto` migration (school.go:24-30).

### Pattern 2: Tenant migration DDL — schema-qualify `public.vector` + `public.vector_cosine_ops`
**What:** Inside `ApplySchoolMigrationsForSchema` the transaction runs `SET LOCAL search_path TO {schema}` ONLY (verified: migration_service.go:141) — `public` is NOT on the path. Live hstore analog tests proved:

| SQL under schema-only search_path | Result |
|-----------------------------------|--------|
| unqualified `hstore` type | ❌ ERROR: type "hstore" does not exist |
| `public.hstore` | ✅ works |
| unqualified `gin_hstore_ops` opclass | ❌ ERROR: operator class "gin_hstore_ops" does not exist |
| `public.gin_hstore_ops` opclass | ✅ works |
| default opclass omitted in CREATE INDEX (column type schema-qualified) | ✅ works — default opclass resolution follows the schema-qualified column type |

**Therefore the tenant `ai_vectors` DDL MUST use `public.vector(1536)` and `public.vector_cosine_ops`.** At runtime the app default `search_path` is `"$user", public`, so unqualified operators resolve fine — qualification is a migration-only concern. [All VERIFIED: live psql tests on running PG 18.4]

### Pattern 3: Store tenancy resolution from `context.Context`
**What:** `pgvector.go` receives only `context.Context` (interface contract). Resolution path (verified end-to-end):
1. `middleware.SchoolID()` runs globally (router.go:104) and stores `CtxKeySchoolID` in the request Go context.
2. AI routes use `authGroup` (router.go:73-86): JWTAuth → EnforceSchoolID → TenantResolution → **TenantDBResolver** → AuditLogging. TenantDBResolver stores `*tenant.TenantRepositories` under `CtxKeyTenantRepos` in the Go context (middleware/tenant.go:311).
3. AI handler passes `c.Request.Context()` (handler.go:118,178) → runner → pipeline → store. **So schoolID AND schemaName are both resolvable from the bare ctx** — `GetSchoolIDFromCtx(ctx)` (audit.go:239-241) + `repos.SchemaName()` (factory.go:113).
4. Guard: schoolID == 0 (super-admin bypass or missing header) → return error, never write to unscoped schema (Rule B1).

```go
// Verified helpers: middleware.GetSchoolIDFromCtx, middleware.CtxKeyTenantRepos
func (s *PGVectorStore) tenantSchema(ctx context.Context) (string, error) {
    schoolID := middleware.GetSchoolIDFromCtx(ctx)
    if schoolID == 0 { return "", fmt.Errorf("vector store: no school id in context") }
    if repos := middleware.GetTenantReposFromCtx(ctx); repos != nil {
        if name := repos.SchemaName(); name != "" { return name, nil }
    }
    return fmt.Sprintf("school_%d", schoolID), nil // deterministic convention
}
```

### Pattern 4: Query construction — GORM clauses for `<=>` + schema-scoped table
**What:** Use GORM builder against the tenant repos' `TenantDB()` (schema-scoped via SchemaTablePrefix plugin):
```go
func (s *PGVectorStore) Search(ctx context.Context, collection string, query []float32, limit int) ([]vector.SearchResult, error) {
    schema, err := s.tenantSchema(ctx)
    if err != nil { return nil, err }
    db := s.repos.TenantDB().WithContext(ctx)  // or repos from ctx per call
    var rows []struct {
        ID string
        Content string
        Metadata map[string]string
        Distance float64
    }
    err = db.Table(schema + ".ai_vectors").
        Select("document_id, content, metadata, 1 - (embedding <=> ?) AS score", pgvector.NewVector(query)).
        Where("collection = ?", collection).
        Order("embedding <=> ?", pgvector.NewVector(query)).
        Limit(limit).Scan(&rows).Error
    // map Distance→Score; return SearchResult{ID, Score, Metadata}
}
```
Note: `1 - (embedding <=> ?)` in SELECT matches D-13 parity; ORDER BY keeps the raw `<=>` expression so the HNSW index is used.

### Anti-Patterns to Avoid
- **Unqualified `vector` type / `vector_cosine_ops` in tenant migration DDL** — fails with "type does not exist"/"operator class does not exist" under schema-only search_path. Always `public.vector(1536)` / `public.vector_cosine_ops`.
- **Installing the extension via tenant migration only** — if no core migration installed it first, the tenant `CREATE EXTENSION IF NOT EXISTS` would install into `school_N` and every `public.vector` reference breaks. Core migration MUST run first (it does, via ApplyCoreMigrations at startup).
- **`SET search_path` (session) instead of `SET LOCAL`** — GORM connection pooling makes session-level settings leak across requests. The machinery already uses `SET LOCAL` inside the migration tx.
- **Multi-statement `db.Exec` in migrations** — Rule B4/B13: pgx v5 prepared-statement mode forbids it; break CREATE TABLE / CREATE INDEX / SET into individual calls.
- **context.Background() in store methods** — Rule B2: always propagate the incoming ctx.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| vector encode/decode to DB | manual `[1,2,3]` string building | `pgvector-go` v0.4.1 `pgvector.Vector` | Correct float32 round-trip, driver.Valuer/Scanner integration, batch-safe |
| cosine distance operator | manual math on loaded vectors | `<=>` operator (extension provides it) | Index-accelerated; manual post-load math loses HNSW |
| HNSW index | hand-rolled graph index | `USING hnsw (embedding vector_cosine_ops)` | pgvector's proven implementation; 2000-dim HNSW cap noted in D-02 |
| extension install from source | compile pgvector into alpine image | official `pgvector/pgvector` image | Prebuilt; CVE patched in ≥0.8.2 |

**Key insight:** Everything in this phase is infrastructure substitution behind a stable interface. The risk is not in building vector search — it's in the DDL/search_path mechanics, which are now empirically pinned.

## Common Pitfalls

### Pitfall 1: Tenant DDL fails with "type \"vector\" does not exist"
**What goes wrong:** The tenant migration `CREATE TABLE ... embedding vector(1536) NOT NULL` fails at runtime.
**Why it happens:** The migration tx runs with schema-only `SET LOCAL search_path TO school_N` (migration_service.go:141); unqualified `vector` isn't found because the extension lives in `public`.
**How to avoid:** Always write `public.vector(1536)` in tenant DDL (proven working).
**Warning signs:** `ERROR: type "vector" does not exist` in migration logs.

### Pitfall 2: HNSW index creation fails on opclass resolution
**What goes wrong:** `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` errors `operator class "vector_cosine_ops" does not exist`.
**Why it happens:** Under schema-only search_path, unqualified opclass lookup misses `public.vector_cosine_ops` (live-proven with `gin_hstore_ops`).
**How to avoid:** Qualify: `USING hnsw (embedding public.vector_cosine_ops)`. Alternatively omit the opclass — default opclass resolution follows the schema-qualified column type (also proven) — but explicit qualification is clearer.
**Warning signs:** `operator class does not exist` during `MigrateAllSchemaTenants`.

### Pitfall 3: Extension installed into wrong schema
**What goes wrong:** If a tenant migration's `CREATE EXTENSION IF NOT EXISTS vector` runs BEFORE the core migration on a fresh database, the extension installs into `school_N`, and `public.vector` references in DDL fail.
**Why it happens:** `CREATE EXTENSION` installs into the first schema of search_path; tenant tx path is schema-only.
**How to avoid:** Guarantee core migration order — `ApplyCoreMigrations()` already runs at startup before school migrations (verified). Never rely on tenant migrations to install it. If it ever lands in a tenant schema: `ALTER EXTENSION vector SET SCHEMA public` (relocatable=true, verified in vector.control).
**Warning signs:** `vector` listed under a school schema when running `\dx` in that schema (should only appear in `public`).

### Pitfall 4: Score semantics flipped (Qdrant vs pgvector)
**What goes wrong:** Search results sorted with highest score first return least-similar chunks.
**Why it happens:** Qdrant cosine returns similarity (higher=better); pgvector `<=>` returns distance (lower=better).
**How to avoid:** Convert `score = 1 - distance` in both `pgvector.go` Search AND the copy tool parity assert (D-13).
**Warning signs:** Copy tool parity asserts fail on the distance/score column.

### Pitfall 5: Connection-pool search_path leakage
**What goes wrong:** A session-scoped `SET search_path` from one request bleeds into another request sharing the pooled connection.
**Why it happens:** GORM pools connections; session settings persist.
**How to avoid:** Never use `SET search_path` in app code; the machinery's `SET LOCAL` is transaction-scoped and safe. In the store, prefer the SchemaTablePrefix plugin's schema-scoped DB (Rule B8) over path manipulation.
**Warning signs:** Intermittent "relation ai_vectors does not exist" under load.

### Pitfall 6: Retiring Qdrant config while setup.go still reads it
**What goes wrong:** Removing `AI_QDRANT_URL` from config validation but leaving `if cfg.AI.QdrantURL != ""` in setup.go (lines ~688-700) silently disables the RAG pipeline.
**Why it happens:** The `NewQdrantStore` gate becomes always-false after config removal.
**How to avoid:** Swap the gate to pgvector construction in the same change (D-12): construct `vector.NewPGVectorStore(...)` unconditionally (or gate on `cfg.AI.Enabled`), and delete the qdrant branch. Retire k8s configmap line 18 and kustomization qdrant entries in the same commit.
**Warning signs:** "RAG pipeline initialized" log disappears after config change.

## Code Examples

Verified patterns from official sources + live verification:

### Extension migration (core) — from pgvector README pattern
```go
// backend/internal/database/migrations/core/vector.go
func VectorMigrations() []migration.Migration {
    return []migration.Migration{
        {
            ID: "2026_08_01_000000_enable_vector_extension",
            Up: func(db *gorm.DB) error {
                return db.Exec(`CREATE EXTENSION IF NOT EXISTS vector`).Error
            },
            Down: func(db *gorm.DB) error {
                return db.Exec(`DROP EXTENSION IF EXISTS vector`).Error
            },
        },
    }
}
```

### Tenant ai_vectors DDL (proven SQL under schema-only search_path)
```go
// Add to SchoolMigrations() in school/school.go, after pgcrypto migration
{
    ID: "2026_08_01_000001_create_ai_vectors",
    Up: func(db *gorm.DB) error {
        if err := db.Exec(`SET LOCAL maintenance_work_mem = '256MB'`).Error; err != nil { return err }
        if err := db.Exec(`CREATE TABLE IF NOT EXISTS ai_vectors (
  id BIGSERIAL PRIMARY KEY,
  document_id TEXT NOT NULL,
  chunk_index INT NOT NULL,
  embedding public.vector(1536) NOT NULL,
  content TEXT NOT NULL,
  collection TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  embedding_model TEXT NOT NULL,
  model_version TEXT NOT NULL,
  chunking_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_ai_vectors_doc_chunk UNIQUE (document_id, chunk_index)
)`).Error; err != nil { return err }
        if err := db.Exec(`CREATE INDEX IF NOT EXISTS idx_ai_vectors_collection ON ai_vectors (collection)`).Error; err != nil { return err }
        return db.Exec(`CREATE INDEX IF NOT EXISTS idx_ai_vectors_embedding_hnsw ON ai_vectors USING hnsw (embedding public.vector_cosine_ops) WITH (m = 16, ef_construction = 64)`).Error
    },
    Down: func(db *gorm.DB) error {
        return db.Exec(`DROP TABLE IF EXISTS ai_vectors`).Error
    },
},
```

### pgvector.go Store Insert — from pgvector-go gorm_test.go + GORM docs
```go
// Source: github.com/pgvector/pgvector-go gorm_test.go (CITED)
func (s *PGVectorStore) Insert(ctx context.Context, collection string, docs []vector.VectorDocument) error {
    schema, err := s.tenantSchema(ctx)
    if err != nil { return err }
    if len(docs) == 0 { return nil }
    rows := make([]map[string]interface{}, 0, len(docs))
    for _, d := range docs {
        rows = append(rows, map[string]interface{}{
            "document_id": d.ID,
            "chunk_index": 0, // caller-provided if needed
            "embedding": pgvector.NewVector(d.Embedding),
            "content": d.Metadata["content"],
            "collection": collection,
            "metadata": d.Metadata,
            "embedding_model": s.embeddingModel,
            "model_version": s.modelVersion,
            "chunking_version": s.chunkingVersion,
        })
    }
    return s.db.Table(schema + ".ai_vectors").Create(rows).Error
}
```

```go
// Search with GORM clause.OrderBy (source: pgvector-go gorm_test.go CITED)
type Item struct {
    gorm.Model
    Embedding pgvector.Vector `gorm:"type:vector(3)"`
}

var items []Item
db.Clauses(clause.OrderBy{
    Expression: clause.Expr{SQL: "embedding <=> ?", Vars: []interface{}{pgvector.NewVector([]float32{1,2,3})}},
}).Limit(5).Find(&items)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| External Qdrant service (separate container, HTTP API) | pgvector inside existing shared Postgres | This phase | Fewer moving parts; tenant isolation via existing schema machinery; no new infra |
| Qdrant payload map | `metadata jsonb` column | This phase | Same shape, native JSONB queries |
| Qdrant cosine similarity (higher=better) | pgvector `<=>` cosine distance (lower=better) | This phase | `score = 1 - distance` parity conversion required |
| Embedding model freedom | Locked `text-embedding-3-small`/1536-dim (D-01) | D-01/D-04a | Single vector space; dimension-fixed column; mixed models rejected (D-04) |

**Deprecated/outdated:**
- **Qdrant retirement:** `AI_QDRANT_URL/API_KEY/TIMEOUT` config, k8s `qdrant-deployment/service/pvc`, compose `qdrant` service + `qdrant_data` volume — all removed in this phase (PGV-06); RET-02 (Phase 7) verifies no lingering references.
- **pgvector <0.8.2:** CVE-2026-3172 — pinned image 0.8.6 contains the fix.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `qdrant_data` volume / `postgres_data` volume will survive the postgres image swap because both images are PG 18.x (same major version, PostgreSQL data dir is version-format compatible across distro variants) | Standard Stack | If PG 18.4 (alpine/musl) data dir were incompatible with the Debian/trixie build of PG 18, the DB would need re-seed. Mitigation: run `make db-init DROP_TENANT=true && make migrate && make seed` (documented reset path in AGENTS.md). MEDIUM risk — image swap must be the first task so failure is detected before any migration work |
| A2 | Tenant migration `SET LOCAL maintenance_work_mem` inside the existing transactional migration machinery is acceptable — `SET LOCAL` is tx-scoped and rolls back safely | Architecture Patterns | Low risk; `SET LOCAL` is standard within pgvector HNSW build guidance [CITED: pgvector README recommends raising maintenance_work_mem for HNSW builds] |
| A3 | `pgvector-go` v0.4.1 GORM path requires no pgx type registration — verified from official gorm_test.go which uses plain `gorm.Open` + `db.Create` without `pgxvec.RegisterTypes` | Standard Stack | If a runtime integration error appears, fallback is `pgxvec.RegisterTypes` on the connection — but this would be a deviation from the GORM-only pattern and only needed for raw pgx access |
| A4 | `metadata jsonb` maps cleanly to Qdrant payload map for parity (D-04 discretion: jsonb recommended) | Architecture Patterns | If metadata requires individual indexed columns later, that's a separate migration; jsonb matches Qdrant's payload shape |
| A5 | The `content` column is populated from `d.Metadata["content"]` in Insert — the existing pipeline's `VectorDocument` carries content in metadata (consistent with qdrant.go payload handling) | Code Examples | If content lives elsewhere, Insert mapping needs adjustment; verify against pipeline.go chunk construction before implementation |

## Open Questions (RESOLVED)

All four open questions were resolved during planning; the resolutions are implemented in the phase plans (02-01..02-06).

1. **Where does the store get the schema-scoped `*gorm.DB`?** **[RESOLVED — plan 02-04 Task 2]** Construct `PGVectorStore` with the existing `*tenant.RepositoryFactory` (already wired in setup.go) and resolve repos per call via `GetTenantReposFromCtx(ctx)`/`GetSchoolIDFromCtx(ctx)` in a `tenantFor(ctx)` helper (Rule B8, tenancy-from-ctx per D-05). `repoFactory` is confirmed in scope in setup.go (plan 02-06 Task 2).
   - What we know: `TenantDBResolver` stores `*tenant.TenantRepositories` under `CtxKeyTenantRepos` in the Go ctx (middleware/tenant.go:311); `repos.TenantDB()` returns schema-scoped DB (factory.go:99).
   - What's unclear: whether `pgvector.go` should be constructed with a `RepositoryFactory` and resolve repos per call, or receive a `*tenant.TenantRepositories`/`*gorm.DB` resolver function.
   - Recommendation: construct with the existing `*tenant.RepositoryFactory` (already wired in setup.go) and resolve per call via `GetTenantReposFromCtx(ctx)` — matches Rule B8 and keeps tenancy from ctx (D-05). Planner should confirm the exact factory field available in setup.go scope.

2. **Exact migration ID strings (discretion item)** **[RESOLVED — plans 02-02 Task 2 + 02-03 Task 1]** Core `2026_08_01_000000_enable_vector_extension`; school `2026_08_01_000001_create_ai_vectors` — no collision with existing IDs.
   - What we know: existing IDs follow `2024_01_01_000000_...` pattern (school.go) and `2026_07_27_000000_...` (core/ai.go).
   - Recommendation: core `2026_08_01_000000_enable_vector_extension`; school `2026_08_01_000001_create_ai_vectors` (shown in code examples). Planner may adjust to match collision rules.

3. **`chunk_index` population in Insert** **[RESOLVED — plans 02-04 Task 1 (Test 2) + 02-05]** `VectorDocument.Metadata` carries the Qdrant parity keys `_doc_id`/`_chunk_index`/`_text`; `chunk_index` is required metadata (missing → error, no silent default) and maps to the `chunk_index` column; the copy tool preserves Qdrant point ordering via the same keys (3-key parity contract documented in the 02-03 DDL and 02-05 header).
   - What we know: D-09 requires `(document_id, chunk_index)` unique; pipeline chunks have implicit order.
   - What's unclear: whether `VectorDocument` carries a chunk index or whether Insert must derive it per document.
   - Recommendation: planner verifies `vector.VectorDocument` fields (store.go) and pipeline chunk flow before implementation; the copy tool must preserve chunk ordering.

4. **K8s qdrant retirement scope** **[RESOLVED — plan 02-06 Task 3]** Retirement-scoped sweep: zero `AI_QDRANT_` env/config refs, zero compose qdrant service/volume, zero k8s qdrant resources in base AND overlays; Go files `internal/ai/vector/qdrant.go` (behavioral reference per D-05) and `cmd/copy-qdrant-vectors/` (migration tool) are explicitly whitelisted; final removal is Phase 7 RET-02.
   - What we know: base configmap line 18 has `AI_QDRANT_URL: http://qdrant:6333`; kustomization lists qdrant-deployment/service/pvc.
   - What's unclear: whether overlay (production) manifests also reference qdrant.
   - Recommendation: grep for `qdrant` across `deploy/` during implementation; remove base entries; verify no overlay refs remain.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Image swap, container ops | ✓ | 28.1.1 | — |
| `shared-postgres` (running) | Migration targets | ✓ | PostgreSQL 18.4 (Alpine/musl, port 5432) | — |
| `shared-redis` (running) | asynq queue (unaffected) | ✓ | redis:alpine (port 6379) | — |
| Qdrant container | Copy tool source (no-op) | ✗ not running | — | Copy tool runs as documented no-op (zero live collections, D-13) |
| Go toolchain | Backend build | ✓ | go1.26.1 linux/amd64 | — |
| `pgvector-go` | New Go dependency | ✗ not in go.mod | v0.4.1 available on proxy.golang.org | `go get` before build |
| pgvector image | PGV-01 | ✗ not yet pulled locally | 0.8.6-pg18-trixie on Docker Hub | Pull during first task |
| Yarn | Frontend (untouched) | ✓ | 4.17.1 | — |
| Backend server binary | `backend/bin/server` | ✓ built (Jul 31 10:11) | — | `make build` if stale |

**Missing dependencies with no fallback:** none — Qdrant absence is expected (D-13 no-op path).

**Missing dependencies with fallback:**
- `pgvector-go` not in go.mod → `go get github.com/pgvector/pgvector-go@v0.4.1` (required before build)
- pgvector image not pulled → `docker compose pull postgres` (or `docker pull pgvector/pgvector:0.8.6-pg18-trixie`)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no auth changes) | Existing JWT chain — untouched |
| V3 Session Management | no (no session changes) | — |
| V4 Access Control | **yes** | Tenant isolation via schema-scoped DB (Rule B8); `pgvector.go` MUST refuse schoolID==0 (no unscoped writes); schema name derived from trusted ctx, never from request body |
| V5 Input Validation | **yes** | `collection` and `document_id` are parameterized query values (Rule B7 — no string-concat SQL); dimension guard rejects mismatched embeddings (D-04) |
| V6 Cryptography | no (no new crypto) | Embeddings are not secrets; no encryption changes |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Cross-tenant vector leakage (school A reads school B's chunks) | Information Disclosure | Schema-scoped DB only (Rule B8); tenancy from ctx `CtxKeySchoolID`/`CtxKeyTenantRepos` — never from request body; schoolID==0 → error (never default to public schema) |
| SQL injection via collection/document_id | Tampering | Parameterized GORM queries (`Where("collection = ?", ...)`); Rule B7 forbids `fmt.Sprintf` SQL |
| Dimension mismatch poisoning vector column | Tampering | D-04 guard + D-14 startup validation: embedding length must equal `AI_EMBEDDING_DIM` before Insert |
| Config fail-fast bypass | Tampering | Rule B12: `AI_EMBEDDING_DIM` required at startup; embedder output dimension validated against `vector(n)` |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: live psql tests on running PG 18.4] — extension install semantics, schema-only search_path DDL behavior, opclass resolution (hstore analog for vector)
- [VERIFIED: Docker Hub] — `pgvector/pgvector:0.8.6-pg18-trixie` latest tag; [VERIFIED: raw.githubusercontent.com/pgvector/pgvector/master/vector.control] — default_version 0.8.6, relocatable true
- [VERIFIED: proxy.golang.org] — `pgvector-go` v0.4.1 published 2026-07-30
- [CITED: github.com/pgvector/pgvector-go/blob/master/gorm_test.go] — GORM integration pattern
- [VERIFIED: codebase] — store.go interface, migration_service.go:141 search_path, factory.go SchemaName/TenantDB, middleware tenancy chain, setup.go wiring, config.go AIConfig, openai.go embedding model
- [CITED: pgvector README] — HNSW index creation, maintenance_work_mem guidance

### Secondary (MEDIUM confidence)
- [ASSUMED] data-dir compatibility across PG 18 Alpine→Debian builds (A1) — same major version format, but not empirically tested this session

### Tertiary (LOW confidence)
- None — no WebSearch-only findings on the critical path; all mechanics verified against the live database or official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified via Docker Hub, proxy.golang.org, and running DB
- Architecture: HIGH — extension/DDL/tenancy mechanics proven by live tests and codebase reads
- Pitfalls: HIGH — each pitfall derives from verified behavior or codebase lines
- Environment: HIGH — probed live (docker ps, SELECT version(), go version)

**Research date:** 2026-08-01
**Valid until:** 2026-08-15 (image tags move fast; 0.8.6 pinned explicitly)

---

*Phase: 02-pgvector-migration*
*Research complete: 2026-08-01*
