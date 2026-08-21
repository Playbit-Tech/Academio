# Qdrant → pgvector Migration Guide

> **Scope**: Retire the Qdrant vector store from the Academio AI stack and complete the cutover to PostgreSQL pgvector (`ai_vectors` per-tenant tables).
> **Audience**: Platform engineers, DevOps, and backend developers performing the migration in dev, staging, or production.
> **Risk Level**: Medium — data-loss risk is low (copy-then-verify), but rollback requires coordination between Go and Python services.

---

## Table of Contents

1. [Background](#1-background)
2. [Pre-Migration Checklist](#2-pre-migration-checklist)
3. [Phase 1 — Data Migration (Qdrant → pgvector)](#3-phase-1--data-migration-qdrant--pgvector)
4. [Phase 2 — Parallel Run (Go AI + Python Engine)](#4-phase-2--parallel-run-go-ai--python-engine)
5. [Phase 3 — Qdrant Retirement](#5-phase-3--qdrant-retirement)
6. [Rollback Procedures](#6-rollback-procedures)
7. [Verification & Monitoring](#7-verification--monitoring)
8. [Post-Migration Cleanup](#8-post-migration-cleanup)

---

## 1. Background

### 1.1 Current State

The Academio AI layer uses **Qdrant** as the vector store for RAG (Retrieval-Augmented Generation). Qdrant runs as the `academio-qdrant` service in `backend/docker-compose.yml` and stores document embeddings for collections such as `curriculum`, `policy`, and `faq`.

The Go AI gateway (`backend/internal/ai/`) exposes a `vector.Store` interface with two implementations:

| Implementation | File | Status |
|---|---|---|
| `QdrantStore` | `backend/internal/ai/vector/qdrant.go` | **Legacy** — behavioral reference only |
| `PGVectorStore` | `backend/internal/ai/vector/pgvector.go` | **Canonical** — production target |

`PGVectorStore` writes to per-tenant `school_{id}.ai_vectors` tables using the pgvector extension. It is schema-scoped (Rule B8), parameterized (Rule B7), and enforces a 1536-dimensional embedding contract (D-14).

### 1.2 Target State

- **Qdrant is removed** from `docker-compose.yml` and all runtime dependencies.
- **All vector operations** flow through `PGVectorStore` into PostgreSQL.
- **The Python AI engine** (`ai-engine/`) continues to run alongside the Go backend during the parallel-run phase, but it also targets pgvector for document storage.
- **`QdrantStore`** is deleted after verification (Phase 7 RET-02).

### 1.3 Why This Matters

| Concern | Qdrant | pgvector |
|---|---|---|
| **Operational overhead** | Separate container, REST API, connection management | Single PostgreSQL instance; no extra infra |
| **Tenancy** | No native schema-per-tenant; app-level collection naming | Native schema-per-tenant via `school_{id}.ai_vectors` |
| **Backup/restore** | Separate volume + export/import | Included in standard PostgreSQL backups |
| **Query consistency** | REST round-trip per search | In-process SQL via GORM; lower latency |
| **Scoring parity** | Cosine similarity (higher = better) | `1 - (embedding <=> query)` cosine distance → similarity (higher = better) |

---

## 2. Pre-Migration Checklist

### 2.1 Environment Prerequisites

- [ ] PostgreSQL **pgvector** extension is installed and the `vector` type is available.
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- [ ] The `ai_vectors` table exists in the target tenant schema (`school_{id}`) with the correct DDL:
  ```sql
  CREATE TABLE school_{id}.ai_vectors (
      id              VARCHAR(255) PRIMARY KEY,
      collection      VARCHAR(255) NOT NULL,
      embedding       vector(1536),
      document_id     VARCHAR(255) NOT NULL,
      chunk_index     VARCHAR(255) NOT NULL,
      text            TEXT,
      embedding_model VARCHAR(255) NOT NULL,
      model_version   VARCHAR(255) NOT NULL,
      chunking_version VARCHAR(255) NOT NULL,
      created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
      updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
  );
  CREATE INDEX idx_ai_vectors_collection ON school_{id}.ai_vectors (collection);
  CREATE INDEX idx_ai_vectors_embedding ON school_{id}.ai_vectors USING hnsw (embedding vector_cosine_ops);
  ```
- [ ] `AI_EMBEDDING_DIM=1536` is set in `backend/.env` and `ai-engine/.env`.
- [ ] The Go backend builds cleanly: `cd backend && go build ./...`.
- [ ] The Python engine builds cleanly: `cd ai-engine && uv build` (or equivalent).

### 2.2 Backup

- [ ] **Backup Qdrant data** for every school/collection that has vectors.
  ```bash
  # Example: use the Qdrant REST API to export collections
  curl -X POST http://localhost:6333/collections/{collection_name}/snapshot
  ```
- [ ] **Backup PostgreSQL** (shared + tenant schemas):
  ```bash
  pg_dump -U academio -d academio -Fc -f academio-pre-migration.dump
  ```
- [ ] Record current **row counts per collection** for later parity verification:
  ```bash
  curl -s http://localhost:6333/collections | jq '.result.collections[] | {name, points_count}'
  ```

### 2.3 Code Readiness

- [ ] `backend/internal/ai/vector/pgvector.go` is present and passes tests:
  ```bash
  cd backend && go test ./internal/ai/vector/...
  ```
- [ ] `backend/cmd/copy-qdrant-vectors/main.go` is present and compiles:
  ```bash
  cd backend && go build ./cmd/copy-qdrant-vectors
  ```
- [ ] Feature flags are configured in `backend/.env`:
  ```env
  AI_PYTHON_PROVIDERS_ENABLED=true
  AI_RAG_ENABLED=true
  AI_STREAMING_ENABLED=true
  ```

---

## 3. Phase 1 — Data Migration (Qdrant → pgvector)

### 3.1 Overview

This phase copies all Qdrant collections into the per-tenant `ai_vectors` tables. It is **non-destructive**: Qdrant data remains untouched until Phase 3.

The migration tool (`copy-qdrant-vectors`) performs three parity asserts:

1. **Count equality** — Qdrant points == pgvector rows per collection.
2. **Dimension parity** — every vector is exactly 1536 dimensions.
3. **Similarity parity** — `|qdrant_similarity - pgvector_score| <= 0.001` for top-k sample queries.

### 3.2 Dry Run

First, inspect what would be copied without writing anything:

```bash
cd backend
go run ./cmd/copy-qdrant-vectors \
  --school-id 1 \
  --dry-run \
  --qdrant-url http://localhost:6333
```

Expected output:
```
copy-qdrant-vectors: dry-run — target schema school_1.ai_vectors, 3 collection(s)
copy-qdrant-vectors: dry-run: collection "curriculum": 1240 point(s)
copy-qdrant-vectors: dry-run: collection "policy": 856 point(s)
copy-qdrant-vectors: dry-run: collection "faq": 420 point(s)
```

If Qdrant is unreachable (e.g., no container running), the tool logs a warning and exits 0 — this is expected in environments where Qdrant has already been decommissioned.

### 3.3 Copy

Copy all collections for a single school:

```bash
cd backend
go run ./cmd/copy-qdrant-vectors \
  --school-id 1 \
  --qdrant-url http://localhost:6333 \
  --concurrency 3
```

Flags:

| Flag | Default | Description |
|---|---|---|
| `--school-id` | (required) | Tenant schema `school_{id}` |
| `--qdrant-url` | `http://localhost:6333` | Qdrant base URL |
| `--qdrant-api-key` | `""` | Optional API key for Qdrant Cloud |
| `--concurrency` | `3` | Parallel collection copies (bounded) |
| `--dry-run` | `false` | Print counts, write nothing |
| `--verify` | `false` | Run parity asserts only, write nothing |

### 3.4 Verify

Run parity asserts **before** and **after** copy:

```bash
# Pre-copy baseline (Qdrant has data, pgvector is empty — expect count mismatch)
go run ./cmd/copy-qdrant-vectors \
  --school-id 1 \
  --verify \
  --qdrant-url http://localhost:6333

# Post-copy verification (should pass all three asserts)
go run ./cmd/copy-qdrant-vectors \
  --school-id 1 \
  --verify \
  --qdrant-url http://localhost:6333
```

Expected success output:
```
copy-qdrant-vectors: parity verification passed for schema school_1
```

If verification fails, **do not proceed**. Inspect the error message:

- **Count mismatch**: Re-run copy; check for partial failures.
- **Dimension mismatch**: The offending point IDs are listed; investigate embedding pipeline.
- **Similarity divergence > 0.001**: Indicates a ranking change; review pgvector HNSW index parameters.

### 3.5 Repeat for All Schools

For multi-tenant deployments, iterate over all active schools:

```bash
for school_id in $(psql -U academio -d academio -t -c "SELECT id FROM schools WHERE database_status = 'active'"); do
  echo "Migrating school $school_id"
  go run ./cmd/copy-qdrant-vectors --school-id "$school_id" --concurrency 3
done
```

---

## 4. Phase 2 — Parallel Run (Go AI + Python Engine)

### 4.1 Objective

Run the **Go AI gateway** and the **Python AI engine** simultaneously during the migration. Both services target pgvector for document storage. The Go gateway continues to serve existing AI endpoints (`/api/v2/ai/chat`, `/api/v2/ai/search`) while the Python engine handles new document ingestion and provider routing.

### 4.2 Architecture During Parallel Run

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ACADEMIO API (Go)                            │
│  backend/internal/ai/                                               │
│   ├── ModelRouter (Gemini / OpenAI / Python providers)              │
│   ├── RAG Pipeline → PGVectorStore → school_{id}.ai_vectors         │
│   ├── NL Search Engine                                              │
│   └── Agent Framework                                               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PYTHON AI ENGINE                                │
│  ai-engine/                                                         │
│   ├── Document Ingest (PDF, DOCX, TXT)                              │
│   ├── Embedding Provider (OpenAI / Gemini)                           │
│   ├── pgvector Storage → school_{id}.ai_vectors                     │
│   └── Chat / Search / Embed Endpoints                               │
└─────────────────────────────────────────────────────────────────────┘
```

**Key invariant**: Both services write to the **same** `ai_vectors` table. The `ON CONFLICT (id) DO UPDATE` upsert in `PGVectorStore` and the Python engine's insert path must agree on the ID generation strategy (chunk ID from the RAG pipeline).

### 4.3 Feature Flags

Use feature flags to control the parallel run exposure:

| Flag | Env Variable | Default | Purpose |
|---|---|---|---|
| `PythonProvidersEnabled` | `AI_PYTHON_PROVIDERS_ENABLED` | `true` | Enable/disable all Python-engine providers in the Go ModelRouter |
| `RAGEnabled` | `AI_RAG_ENABLED` | `true` | Enable/disable document ingest + pgvector search |
| `StreamingEnabled` | `AI_STREAMING_ENABLED` | `true` | Enable/disable SSE streaming endpoints |

Per-school gating is handled by `TenantConfig.HasAI` (plan-level). Schools without AI access cannot reach either service.

### 4.4 Traffic Splitting

Do **not** route traffic by code branching. Instead:

1. **Go gateway** continues to serve all existing AI endpoints.
2. **Python engine** is reachable at `AI_ENGINE_URL` (e.g., `http://ai-engine:8000`).
3. The Go `ModelRouter` appends Python providers as discrete entries when `AI_ENGINE_URL` + `AI_ENGINE_TOKEN` are configured (`gateway.go` lines 228–241).
4. Document ingestion endpoints in the Go module (`POST /api/v2/ai/documents`) can be wired to either the Go RAG pipeline or the Python engine via a config flag.

**Recommended parallel-run sequence**:

| Step | Action | Verification |
|---|---|---|
| 1 | Deploy Go backend with `PGVectorStore` active and `AI_ENGINE_URL` configured. | Go tests pass; pgvector search returns results. |
| 2 | Deploy Python engine with pgvector storage (no Qdrant dependency). | Python engine health check returns 200. |
| 3 | Enable document upload UI in the frontend, pointing to the Go backend. | Uploads succeed; chunks appear in `ai_vectors`. |
| 4 | Monitor both services for 48–72 hours. | Compare Qdrant point counts vs pgvector row counts; watch for errors. |
| 5 | If stable, proceed to Phase 3 (Qdrant retirement). | Zero parity drift; no Qdrant-related errors in logs. |

### 4.5 Data Consistency During Parallel Run

Both services may write to `ai_vectors` concurrently. The table uses `ON CONFLICT (id) DO UPDATE`, so re-ingestion of the same chunk is idempotent.

**Rules**:

- **Chunk IDs must be deterministic**. The RAG pipeline (`backend/internal/ai/rag/pipeline.go`) generates chunk IDs; both Go and Python must use the same ID scheme.
- **Embedding dimension must be 1536**. Reject any embedding of a different length at insert time (`pgvector.go` line 149).
- **Collection names must match**. Go uses `collection` strings like `"curriculum"`; Python must use the same names.

### 4.6 Monitoring

Watch these metrics during parallel run:

| Metric | Source | Alert Threshold |
|---|---|---|
| `ai_vectors` row count per school | PostgreSQL | Should increase monotonically; flat = ingest failure |
| `ai_requests_total{provider="python:*"}` | Prometheus | Error rate > 5% |
| `ai_errors_total{error_type="api_error"}` | Prometheus | Spike > 2σ from baseline |
| Qdrant point count | Qdrant REST API | Should remain static (read-only during parallel run) |
| Python engine `/health` | HTTP | Non-200 = restart |

---

## 5. Phase 3 — Qdrant Retirement

### 5.1 Pre-Retirement Verification

Before removing Qdrant, confirm:

- [ ] All schools have been migrated (run `--verify` for every school).
- [ ] pgvector row counts match Qdrant point counts for every collection.
- [ ] Similarity parity passes for all schools (`|qdrant_similarity - pgvector_score| <= 0.001`).
- [ ] The Go backend has been running with `PGVectorStore` for at least 48 hours without Qdrant-related errors.
- [ ] The Python engine is storing documents in pgvector, not Qdrant.

### 5.2 Remove Qdrant from docker-compose

Edit `backend/docker-compose.yml` and **remove the entire `qdrant` service block** (if present) and any `depends_on` references.

If Qdrant is not in `docker-compose.yml` (it may have already been removed), skip this step.

### 5.3 Remove Qdrant Code

Delete the legacy behavioral reference:

```bash
rm backend/internal/ai/vector/qdrant.go
```

Update `backend/internal/ai/vector/store.go` to remove the Qdrant comment:

```go
// Package vector provides a storage abstraction for vector embeddings.
//
// The canonical backend is pgvector (PGVectorStore over per-tenant
// `ai_vectors` tables, Phase 2).
package vector
```

### 5.4 Remove Qdrant Configuration

Remove any Qdrant-specific config from:

- `backend/internal/ai/config.go` — remove `QdrantURL`, `QdrantAPIKey`, `QdrantTimeout` if present.
- `backend/.env.example` — remove `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_TIMEOUT` if present.
- `backend/internal/config/config.go` — remove Qdrant config struct fields and env parsing.

### 5.5 Remove Migration Tool (Optional)

`backend/cmd/copy-qdrant-vectors/main.go` is a one-time migration tool. After successful cutover, you may delete it or archive it under `backend/cmd/archive/` for audit purposes.

```bash
# Archive (recommended for audit trail)
mkdir -p backend/cmd/archive
mv backend/cmd/copy-qdrant-vectors backend/cmd/archive/
```

### 5.6 Update Documentation

- [ ] Update `docs/architecture/5-AI-ARCHITECTURE.md` to remove Qdrant references and reflect pgvector as the sole vector store.
- [ ] Update `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` if Qdrant is mentioned in standards.
- [ ] Update `AGENTS.md` if it contains Qdrant-specific warnings.

---

## 6. Rollback Procedures

### 6.1 Rollback Triggers

Initiate rollback if any of the following occur during parallel run or after Qdrant retirement:

- **Search result divergence**: pgvector returns different top-k results than Qdrant for the same query.
- **Ingest failures**: Document uploads fail or chunks are not stored in `ai_vectors`.
- **Performance regression**: pgvector search latency exceeds SLO (e.g., p95 > 500ms).
- **Data corruption**: Row counts decrease unexpectedly; foreign key violations appear.
- **Python engine instability**: The engine becomes unreachable or returns 5xx errors.

### 6.2 Rollback: Parallel Run → Qdrant Read Path

If issues arise during Phase 2 (parallel run) but Qdrant is still running:

1. **Stop writing to pgvector** from the Python engine. Set `AI_RAG_ENABLED=false` in `ai-engine/.env` and restart the engine.
2. **Switch the Go `ModelRouter`** back to Gemini/OpenAI providers only. Unset `AI_ENGINE_URL` in `backend/.env` and restart the Go backend.
3. **Re-point `PGVectorStore`** to read from Qdrant temporarily by swapping the store implementation in `backend/internal/ai/rag/pipeline.go`:
   ```go
   // Temporary rollback: use QdrantStore for reads
   store := vector.NewQdrantStore(vector.QdrantConfig{
       URL:     "http://localhost:6333",
       Timeout: 30 * time.Second,
   })
   ```
   **Note**: This requires `qdrant.go` to still be present. If it has been deleted, restore it from git history:
   ```bash
   git checkout HEAD -- backend/internal/ai/vector/qdrant.go
   ```
4. **Verify** that search results match the pre-migration baseline.

### 6.3 Rollback: Post-Retirement → Restore Qdrant

If Qdrant has already been removed from `docker-compose.yml` and code:

1. **Restore Qdrant service** in `docker-compose.yml`:
   ```yaml
   qdrant:
     image: qdrant/qdrant:v1.7.0
     container_name: academio-qdrant
     restart: unless-stopped
     ports:
       - "6333:6333"
     volumes:
       - qdrant_data:/qdrant/storage
   ```
2. **Restore Qdrant code** from git:
   ```bash
   git checkout HEAD -- backend/internal/ai/vector/qdrant.go
   git checkout HEAD -- backend/internal/ai/vector/store.go
   ```
3. **Restore Qdrant config** in `config.go` and `.env.example`.
4. **Re-import data** from the pgvector backup taken in Section 2.2:
   ```bash
   # If you have a Qdrant snapshot from pre-migration:
   curl -X POST http://localhost:6333/collections/{collection}/snapshot/restore \
     -H "Content-Type: application/json" \
     -d '{"snapshot_name": "pre-migration-2026-08-21.snapshot"}'
   ```
   Alternatively, use the `copy-qdrant-vectors` tool in reverse (pgvector → Qdrant) by writing a small script that reads `ai_vectors` and POSTs to Qdrant's `/points` endpoint.
5. **Restart** the Go backend and verify Qdrant is reachable.

### 6.4 Rollback Decision Tree

```
Qdrant still running?
├── YES → Switch store back to QdrantStore (6.2)
└── NO (retired)
    ├── Can restore from git + docker-compose? → Restore Qdrant (6.3)
    └── No git history / no snapshot? → Restore from PostgreSQL backup (2.2)
        └── pg_dump restore → re-run copy-qdrant-vectors forward
```

---

## 7. Verification & Monitoring

### 7.1 Automated Verification

Run the built-in parity tool after every migration step:

```bash
# Verify all schools
for school_id in $(psql -U academio -d academio -t -c "SELECT id FROM schools"); do
  go run ./cmd/copy-qdrant-vectors \
    --school-id "$school_id" \
    --verify \
    --qdrant-url http://localhost:6333
done
```

### 7.2 Manual Spot Checks

Pick 3–5 schools and run manual queries:

```sql
-- Count parity
SELECT 'qdrant' AS source, COUNT(*) AS count FROM qdrant.collection WHERE collection = 'curriculum'
UNION ALL
SELECT 'pgvector', COUNT(*) FROM school_1.ai_vectors WHERE collection = 'curriculum';

-- Similarity spot check (same query vector)
SELECT id, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS score
FROM school_1.ai_vectors
WHERE collection = 'curriculum'
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

Compare the top-5 IDs and scores against Qdrant's `/collections/curriculum/points/search` response.

### 7.3 Monitoring Dashboard

Add these queries to your Grafana dashboard:

```promql
# pgvector row count per school (increasing = healthy)
count({__name__=~"ai_vectors.*"})

# Go AI request rate by provider
rate(ai_requests_total[5m])

# Python engine error rate
rate(ai_errors_total{provider=~"python:.*"}[5m])
```

---

## 8. Post-Migration Cleanup

### 8.1 Code Cleanup

After Qdrant is retired and the parallel run is stable for **at least 2 weeks**:

- [ ] Delete `backend/internal/ai/vector/qdrant.go`.
- [ ] Delete `backend/cmd/copy-qdrant-vectors/` (or archive).
- [ ] Remove Qdrant config from `config.go`, `.env.example`, and `docker-compose.yml`.
- [ ] Remove Qdrant references from `docs/architecture/5-AI-ARCHITECTURE.md`.
- [ ] Update `docs/architecture/9-ARCHITECTURAL-STANDARDS.md` if it mentions Qdrant.

### 8.2 Database Cleanup

After **at least 4 weeks** of stable pgvector operation:

- [ ] **Drop Qdrant data** (collections and storage volume) to reclaim disk space.
  ```bash
  curl -X DELETE http://localhost:6333/collections/{collection_name}
  ```
- [ ] **Remove Qdrant volume** from `docker-compose.yml` and prune:
  ```bash
  docker compose down
  docker volume rm academio_qdrant_data
  ```

### 8.3 Final Verification

- [ ] Run the full test suite:
  ```bash
  cd backend && go test ./...
  cd ai-engine && uv run pytest
  ```
- [ ] Run integration tests:
  ```bash
  backend/scripts/test_endpoint.sh
  ```
- [ ] Confirm zero Qdrant references in the codebase:
  ```bash
  grep -r "qdrant" backend/ ai-engine/ docs/ || echo "No Qdrant references found"
  ```

---

## Appendix A — Quick Reference Commands

| Task | Command |
|---|---|
| Dry-run migration | `go run ./cmd/copy-qdrant-vectors --school-id 1 --dry-run` |
| Copy vectors | `go run ./cmd/copy-qdrant-vectors --school-id 1` |
| Verify parity | `go run ./cmd/copy-qdrant-vectors --school-id 1 --verify` |
| Check Qdrant collections | `curl -s http://localhost:6333/collections \| jq '.result.collections[].name'` |
| Check pgvector counts | `SELECT collection, COUNT(*) FROM school_1.ai_vectors GROUP BY collection;` |
| Restore Qdrant from git | `git checkout HEAD -- backend/internal/ai/vector/qdrant.go` |
| Archive migration tool | `mv backend/cmd/copy-qdrant-vectors backend/cmd/archive/` |

---

## Appendix B — Contact & Escalation

If migration verification fails or rollback is needed:

1. **Stop all writes** to `ai_vectors` by setting `AI_RAG_ENABLED=false`.
2. **Preserve logs** from both Go backend and Python engine.
3. **Restore from backup** (Section 2.2) if data corruption is suspected.
4. **Escalate** to the platform team with the parity tool output and PostgreSQL logs.
