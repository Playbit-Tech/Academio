# Phase 2: pgvector Migration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-01
**Phase:** 02-pgvector-migration
**Areas discussed:** Embedding canon, Store tenancy, ai_vectors shape, Qdrant cutover, data migration tool, dimension fail-fast

---

## Auto Mode Note

This discussion ran in `--auto` mode (auto-advance from Phase 1 completion). All gray areas were auto-selected and the recommended option chosen for each. Decisions logged inline and captured in CONTEXT.md.

---

## Embedding Canon (PGV-04a)

| Option | Description | Selected |
|--------|-------------|----------|
| text-embedding-3-small 1536d | Already the Go OpenAI embedding path, ≤2000 HNSW cap, no re-embedding | ✓ |
| text-embedding-004 3072d | Gemini; exceeds vector-type HNSW cap | |
| Defer canon | Would block PGV-04 DDL — rejected | |

**User's choice:** [auto] text-embedding-3-small, 1536-dim
**Notes:** Nigerian-language eval spike runs during planning; revisable before DDL if material quality gap found (D-03)

## Store Tenancy Resolution (PGV-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve schoolID from ctx, collection as column filter | Keeps Store interface + agent calls unchanged | ✓ |
| Change Store interface to take schema | Violates "zero RAG/agent changes" | |

**User's choice:** [auto] ctx-based tenancy, collection stays a column filter (D-05..D-07)

## ai_vectors Table Shape (PGV-04)

| Option | Description | Selected |
|--------|-------------|----------|
| ROADMAP SC-3 spec as-is | metadata cols + unique(doc,chunk) + HNSW vector_cosine_ops | ✓ |
| Alternative column shapes | jsonb vs individual cols left to planner discretion | |

**User's choice:** [auto] ROADMAP spec; metadata as jsonb for Qdrant-payload parity (D-08..D-11)

## Qdrant Cutover (PGV-05/06)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 swap + retire qdrant from compose | PGV-06; RET-02 becomes Phase-7 no-lingering-refs check | ✓ |
| Keep qdrant until Phase 7 | Overlaps PGV-06's explicit retirement | |

**User's choice:** [auto] swap config + retire qdrant service in Phase 2 (D-12)

## Data Migration Tool (PGV-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Ship with parity asserts, no-op when empty | SC-5 mandates parity; reusable for Phase 7 | ✓ |
| Skip tool (no live data) | Would fail SC-5 | |

**User's choice:** [auto] ship tool with parity asserts (D-13)

## Dimension Fail-Fast

| Option | Description | Selected |
|--------|-------------|----------|
| AI_EMBEDDING_DIM config + startup validation | Rule B12, SC-5 | ✓ |
| No validation | Silent mismatch risk | |

**User's choice:** [auto] required config + startup fail-fast (D-14)

---

## the agent's Discretion

HNSW tuning values (m, ef_construction), migration ID strings, copy tool CLI shape, metadata jsonb vs columns, versioning defaults — planner flexibility.

## Deferred Ideas

- Corpus re-embed tooling (EMB-01) — v2, out of scope
- Multilingual embedding expansion (MULTI-01) — v2, out of scope
- Reranker selection benchmark (RERANK-01) — v2, out of scope
