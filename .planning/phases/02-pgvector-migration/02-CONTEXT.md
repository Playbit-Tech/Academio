# Phase 2: pgvector Migration - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Vector storage moves from Qdrant to per-tenant pgvector behind the existing `vector.Store` interface, with a locked canonical embedding model and a structurally isolated `ai_vectors` table — zero RAG/agent changes. This phase delivers:

- Postgres image swapped to a pinned pgvector image (≥0.8.2, CVE-2026-3172) in docker-compose
- `CREATE EXTENSION IF NOT EXISTS vector` in both shared (core) and per-tenant migrations
- `pgvector.go` implementing the existing `vector.Store` interface (Insert/Search/Delete/Close), tenancy resolved from `context.Context`, collection strings unchanged
- `ai_vectors` table in each `school_{id}` TENANT schema with metadata columns + HNSW index
- Canonical embedding model + dimension locked in config (`AI_EMBEDDING_DIM`) BEFORE any `ai_vectors` DDL (PGV-04a hard blocker)
- Qdrant → pgvector data copy tool with parity asserts (low risk: no live collections)
- Config swap `AI_QDRANT_*` → pgvector DSN; Qdrant service retired from compose

</domain>

<decisions>
## Implementation Decisions

### Canonical Embedding Model (PGV-04a — HARD BLOCKER)
- **D-01:** Canonical embedding model = **`text-embedding-3-small` (OpenAI), 1536-dim**, locked in config as `AI_EMBEDDING_DIM=1536`. Rationale: it is already the Go pipeline's OpenAI embedding path (`internal/ai/openai.go`), 1536d ≤ 2000-dim HNSW cap on `vector` type, and matches the existing embedding space so no re-embedding is needed for current data.
- **D-02:** Gemini `text-embedding-004` (3072d) is NOT the canon — exceeds the 2000-dim cap for HNSW on `vector`; the ModelRouter's `GenerateEmbeddings` continues to route to its primary provider, which must be configured to the canonical model.
- **D-03:** Nigerian-language multilingual quality eval spike runs DURING planning (a planning artifact, not a phase deliverable): a small corpus (English + Yoruba/Hausa/Igbo/Pidgin) confirms `text-embedding-3-small` adequacy before DDL. If the spike surfaces a material quality gap, the canonical model decision is revisited BEFORE writing the `ai_vectors` migration.
- **D-04:** `embedding_model` column stores the model id per chunk; a migration/validation guard rejects writes whose embedding dimension ≠ `AI_EMBEDDING_DIM`.

### Store Tenancy Resolution (PGV-03)
- **D-05:** `pgvector.go` keeps the existing `vector.Store` interface EXACTLY (Insert/Search/Delete/Close with `collection string`) — zero RAG/agent changes. Tenancy is resolved from `context.Context` (schoolID), matching the research pattern: "pgvector.go resolves schoolID from ctx → schema-scoped DB → `school_{id}.ai_vectors WHERE collection = ?`".
- **D-06:** `collection` becomes a column filter inside the tenant schema (agents pass "curriculum", "policies", etc. unchanged). The tenant boundary is the SCHEMA, not the collection.
- **D-07:** All tenant queries go through the schema-scoped DB (`middleware.GetTenantDB`-style); never the raw core DB (Rule B8).

### ai_vectors Table Shape (PGV-04)
- **D-08:** Table lives in each `school_{id}` schema (NOT `public`, NOT shared+partial-indexes) — structural tenant isolation.
- **D-09:** Columns: `document_id`, `chunk_index`, `embedding vector(AI_EMBEDDING_DIM)`, `content text`, `collection text`, `metadata jsonb`, `embedding_model`, `model_version`, `chunking_version`, timestamps. Unique constraint on `(document_id, chunk_index)`.
- **D-10:** Per-schema HNSW index with `vector_cosine_ops` + `<=>` operator, built with raised `maintenance_work_mem`.
- **D-11:** New tenants get the table automatically via `SchoolMigrations()`; EXISTING provisioned tenants get it via `MigrateAllSchemaTenants` (parallel, concurrency-limited) — both use the existing per-schema migration machinery (`ApplySchoolMigrationsForSchema` with `SET LOCAL search_path`).

### Qdrant Cutover (PGV-05 / PGV-06)
- **D-12:** Phase 2 swaps config `AI_QDRANT_*` → pgvector DSN and retires the `qdrant` service from docker-compose (PGV-06). `RET-02` (Phase 7) becomes the final verification that no lingering qdrant references/config remain.
- **D-13:** The Qdrant → pgvector copy tool ships WITH parity asserts (count, dimension, distance semantics `similarity = 1 - distance` for cosine). With zero live collections it runs as a documented no-op; it is reused for Phase 7 cutover verification.

### Dimension Fail-Fast (PGV-06 / Rule B12)
- **D-14:** `AI_EMBEDDING_DIM` is a required config value, validated at startup. Startup also validates the embedder's actual output dimension matches the `vector(n)` column type — fail-fast on mismatch (Rule B12, no silent fallback).

### the agent's Discretion
- HNSW index tuning values (m, ef_construction, ef_search) — planner selects sensible defaults for a school-sized corpus
- Exact migration ID string for the `ai_vectors` DDL + extension migration
- Copy tool CLI shape (flags, output format) — must include the parity asserts
- Whether `metadata` uses jsonb vs individual columns — jsonb recommended for parity with Qdrant payload map
- `model_version`/`chunking_version` default values and bump policy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Research (already locked)
- `.planning/research/ARCHITECTURE.md` — §"Decision 2: One canonical embedding model + dimension" (lines ~103-111), §"Go path" (lines ~280-281), §"Critical path" (lines ~332-355) — the schema-per-tenant pgvector design, tenancy-from-ctx, embedding canon rationale, HNSW 2000-dim cap
- `.planning/research/SUMMARY.md` — embedding canon recommendation (`text-embedding-3-small`, 1536d), HNSW caps at 2000 dims, multilingual verification requirement, migration risk assessment (no live collections)

### Requirements
- `.planning/REQUIREMENTS.md` — PGV-01..PGV-06 definitions (lines 18-24)

### Existing Code (implementation targets)
- `backend/internal/ai/vector/store.go` — the `Store` interface to implement without changes
- `backend/internal/ai/vector/qdrant.go` — existing Qdrant implementation (reference for semantics/parity)
- `backend/internal/ai/rag/pipeline.go` — RAG pipeline consuming `vector.Store` (must stay unchanged)
- `backend/internal/ai/openai.go` §GenerateEmbeddings (lines ~213-280) — canonical embedding path `text-embedding-3-small`
- `backend/internal/ai/model_router.go` §GenerateEmbeddings (lines ~170-180) — primary provider routing
- `backend/internal/database/migrations/school/school.go` — per-tenant migration list (add extension + ai_vectors here)
- `backend/internal/database/migrations/core/ai.go` — shared-schema AI migrations pattern (conversation tables)
- `backend/internal/database/tenant/migration_service.go` — `ApplySchoolMigrationsForSchema`, `MigrateAllSchemaTenants` (existing schema-per-tenant migration machinery)
- `backend/internal/config/config.go` — `AIConfig` struct (lines ~95-115); add `AI_EMBEDDING_DIM`, swap `AI_QDRANT_*` → pgvector DSN fields
- `backend/internal/router/setup.go` — vecStore wiring (lines ~688-720)
- `backend/docker-compose.yml` — postgres service (lines 4-15, `postgres:alpine`), qdrant service (lines 35-49)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `vector.Store` interface + `QdrantStore` — the interface stays; qdrant.go is the behavioral reference for the pgvector implementation
- `ApplySchoolMigrationsForSchema` / `MigrateAllSchemaTenants` — complete per-schema migration machinery with `SET LOCAL search_path` + non-prepared-statement GORM connection (DDL-safe)
- `rag.Pipeline` + agents (`academic_tutor`, `teacher_assistant`) — untouched consumers; collection strings "curriculum", "policies"
- `middleware.GetTenantDB(c)` — schema-scoped GORM DB access pattern (Rule B8)

### Established Patterns
- Tenant migrations use raw SQL for extension setup (e.g., `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` in school.go) — the `vector` extension follows the same pattern
- Core migrations use `db.AutoMigrate` for shared-schema tables; tenant migrations use a consolidated AutoMigrate + explicit raw-SQL steps
- Config fail-fast (Rule B12) — new `AI_EMBEDDING_DIM` and pgvector DSN validate at startup

### Integration Points
- `internal/router/setup.go` builds `vecStore` (currently `NewQdrantStore` gated on `cfg.AI.QdrantURL != ""`) → swap to pgvector store construction
- Compose `postgres` service image change → `pgvector/pgvector:0.8.6-pg18-trixie` (≥0.8.2, CVE-2026-3172); verify data volume `postgres_data` survives image swap (same major PG version)

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the locked research and ROADMAP success criteria — this is a backend/infrastructure phase with clear technical scope. Implementation follows established Academio patterns (schema-per-tenant migrations, config fail-fast, `vector.Store` interface parity).

</specifics>

<deferred>
## Deferred Ideas

- **Corpus re-embed tooling (EMB-01)** — already tracked as v2 requirement; NOT in Phase 2 scope. The copy tool must not be extended into a general re-embedding utility.
- **Multilingual embedding expansion (MULTI-01)** — v2 requirement; the Nigerian-language eval spike in D-03 only VERIFIES the canonical model, it does not build expansion tooling.
- **Reranker selection benchmark (RERANK-01)** — v2 requirement; reranking ships in Phase 3 Python engine, not here.

</deferred>

---

*Phase: 02-pgvector-migration*
*Context gathered: 2026-08-01*
