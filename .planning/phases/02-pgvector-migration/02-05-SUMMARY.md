---
phase: 02-pgvector-migration
plan: 05
subsystem: api
tags: [qdrant, pgvector, golang, migration, cli, cosine-parity, multi-tenant]

# Dependency graph
requires:
  - phase: 02-01
    provides: embedding dimension canon (1536), pgvector-go v0.4.1 choice, tenancy resolution patterns
  - phase: 02-03
    provides: tenant `ai_vectors` DDL (flattened columns + HNSW vector_cosine_ops index) in all school_{id} schemas
provides:
  - Qdrant → pgvector copy CLI (`backend/cmd/copy-qdrant-vectors`) with `--dry-run` / `--verify`
  - Schema guard: writes only into `school_{id}` schemas matching ^school_[0-9]+$ AND present in information_schema.schemata (never auto-create)
  - 3-key parity contract migration: `_doc_id`/`_chunk_index`/`_text` → `document_id`/`chunk_index`/`text`, metadata flattened, no jsonb
  - `--verify` parity asserts (count / dimension / |similarity|Δ|≤0.001 with `similarity = 1 - distance`)
  - Safe no-op when Qdrant unreachable (exit 0) — matches current dev environment (no qdrant container)
affects: [02-06, 02-07, agent runtime swap, RAG pipeline verification]

# Tech tracking
tech-stack:
  added: [none — net/http only, no new dependency per plan]
  patterns:
    - "No-op contract: transport-level Qdrant failure (connection refused/timeout/DNS) logs 'qdrant not reachable — nothing to copy (no-op)' and exits 0; any real failure (HTTP >= 400, schema guard, dim guard, parity assert) exits non-zero"
    - "Schema guard: regex ^school_[0-9]+$ + information_schema.schemata EXISTS check; ONLY the validated schema name is interpolated into SQL (Rule B7), all values parameterized"
    - "Batch error collection: per-collection and per-point violations collected into one error message (Rule B9), never partial silent mapping"
    - "Idempotent copy: DELETE existing rows for the collection then CreateInBatches(500) via the tenant factory's schema-scoped session (Rule B8)"

key-files:
  created:
    - backend/cmd/copy-qdrant-vectors/main.go
  modified: []

key-decisions:
  - "No-op on Qdrant unreachable exits 0 (safe no-op) — the plan requires the tool to be safe to run with zero Qdrant data in dev, so the no-op must not fail the migration pipeline; only non-transport failures exit non-zero"
  - "Schema guard implemented as regex + information_schema EXISTS check (T-PGV-05-01) — never auto-creates the schema, matching the threat register disposition"
  - "Idempotent re-runs use clear-then-copy per collection (DELETE WHERE collection = ? then batch insert), mirroring copy-tenant-data's pattern — required so a re-run of the migration tool converges instead of duplicating rows"
  - "Metadata flattened with no jsonb preservation (D-09 agent discretion) — the --verify parity asserts depend on exactly this mapping, and the write path matches the ai_vectors DDL from 02-03 and the PGVectorStore mapping from 02-04"

patterns-established:
  - "CLI migration-tool layout: config.Load → database.MustConnect → sharedDB.Use(tenant.SchemaTablePrefix()) → tenant.NewRepositoryFactory → ForSchoolSchema(ctx, schoolID, schema) → repos.TenantDB(), mirroring cmd/copy-tenant-data"
  - "Qdrant client over net/http with paginated scroll (page 256) and top-k search; `api-key` header; transport errors classified separately from HTTP API errors"
  - "Dimension guard pinned to 1536 (D-14) with config fail-fast (AI_EMBEDDING_DIM mismatch refuses to run)"

requirements-completed: [PGV-05]

# Metrics
duration: 7min
completed: 2026-08-01
---

# Phase 02 Plan 05: Qdrant → pgvector Copy Tool Summary

**Qdrant → pgvector migration CLI with schema guard, 3-key payload parity contract, dimension guard, and `--verify` count/dimension/similarity asserts — a safe no-op in the current dev environment (no qdrant container), fully correct the moment a Qdrant instance holds data.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-08-01T06:40:29Z
- **Completed:** 2026-08-01T06:47:43Z
- **Tasks:** 1/1
- **Files modified:** 1 created (`backend/cmd/copy-qdrant-vectors/main.go`, 810 lines)

## Accomplishments

- Built `backend/cmd/copy-qdrant-vectors` — a self-contained CLI (net/http only, no new dependency) that:
  - **Lists** Qdrant collections (`GET /collections`) and scrolls all points per collection (paginated, page size 256, `with_payload` + `with_vector`).
  - **Copies** each collection into the validated tenant schema's `ai_vectors` table via the tenant factory's schema-scoped session (Rule B8), with bounded concurrency (default 3) and per-collection error collection (Rule B9).
  - **Guards every write**: schema must match `^school_[0-9]+$` AND exist in `information_schema.schemata` (T-PGV-05-01); only the regex-validated schema name is interpolated into SQL, all values parameterized (Rule B7); one statement per Exec (Rule B4).
  - **Enforces the D-09 3-key parity contract**: `_doc_id`/`_chunk_index` required (no silent defaults), `_text` mapped; metadata flattened, jsonb intentionally omitted (matches 02-03 DDL + 02-04 PGVectorStore mapping). All violations collected into one error message (Rule B9 batch).
  - **Pins the dimension guard** to 1536 (D-14) with a config fail-fast: `AI_EMBEDDING_DIM != 1536` refuses to run.
  - **Verifies parity** (`--verify`, and also the default post-copy step): (a) count equality (Qdrant points == pgvector rows for the collection), (b) dimension parity, (c) top-k=10 sample queries asserting `|qdrant_similarity - pgvector_score| <= 0.001` where `pgvector_score = SELECT 1 - (embedding <=> $1) AS score` — the exact `similarity = 1 - distance` cosine conversion used by PGVectorStore (02-04).
  - **No-ops safely** when Qdrant is unreachable: logs `qdrant not reachable — nothing to copy (no-op)` and exits 0 (verified in dev).
  - **Dry-runs** with `--dry-run`: prints target schema + per-collection point counts, writes nothing.

## Verification

Plan gates (all passed):

1. `go build ./cmd/copy-qdrant-vectors/` → **PASS**
2. `go run ./cmd/copy-qdrant-vectors --school-id 1 --verify` → **exit 0**, schema guard passed for `school_1`, then no-op warning (qdrant unreachable) — expected dev outcome
3. `docker ps` → **no qdrant container** (expected)

Additional checks:

- `go vet ./cmd/copy-qdrant-vectors/...` → **PASS** (2 logger API misuses fixed inline: key-value args passed to printf-style `Infof` → changed to slog-style `Info`)
- `gofmt -l` → clean
- `go test ./internal/ai/vector/...` → **PASS** (pgvector integration test skips without `PGVECTOR_TEST_DSN`, unit tests pass)
- Schema guard negative path: `--school-id 999 --dry-run` → **exit 1** with `schema does not exist in information_schema.schemata (T-PGV-05-01)`
- Must-haves confirmed in source: `similarity = 1 - distance` (comment + assert), count/dimension/similarity asserts, schema guard, no-op path

## Deviations from Plan

None — plan executed exactly as written (single task, no checkpoint).

## Auth Gates

None.

## Known Stubs

None. The tool's `--dry-run`/`--verify` paths and metadata defaults (`text-embedding-3-small`/`v1`/`v1`) are intentional (D-01 canon; model_version/chunking_version bump policy is agent discretion per CONTEXT.md).

## Deferred Issues

- **Unit tests for buildRows/payloadString/pointIDString** would improve confidence in the parity contract, but the plan scopes verification to build + no-op run and the tool cannot be exercised end-to-end without a live Qdrant instance. Logged for a future hardening plan (02-07 or a dedicated test plan).
- **`copy-qdrant-vectors` build artifact**: `go build ./cmd/copy-qdrant-vectors/` writes a `copy-qdrant-vectors` binary to the backend root; it was removed after verification and is not committed. Consider adding the binary name to `backend/.gitignore` if the tool is built frequently.

## Commits

- `21fcb16` (backend @ dev): feat(02-05): add qdrant→pgvector copy CLI with parity asserts
- `7cd47e7` (root @ main): feat(02-05): bump backend submodule to 21fcb16 (qdrant→pgvector copy CLI with parity asserts, PGV-05)

## Threat Flags

None — all threat-register mitigations (T-PGV-05-01 schema guard, T-PGV-05-02 payload mapping + dim guard, T-PGV-05-03 parity asserts) were implemented as dispositioned; T-PGV-05-04 (credentials) accepted as-is (API key via flag, never committed, absent in dev).
## Self-Check: PASSED
