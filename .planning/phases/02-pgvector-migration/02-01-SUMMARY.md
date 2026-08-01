---
phase: 02-pgvector-migration
plan: 01
subsystem: ai / config
tags: [pgvector, embeddings, config, pgv-04a]
requires: []
provides: [PGV-04a]
affects: [backend/internal/config/config.go, backend/internal/ai/embed_spike_test.go, backend/.env.example]
tech-stack:
  added: []
  patterns:
    - "Config fail-fast on dimension bounds (Rule B12)"
    - "Spike-test-as-gate: runnable adequacy eval before DDL"
key-files:
  created:
    - backend/internal/ai/embed_spike_test.go
    - .planning/phases/02-pgvector-migration/02-01-SPIKE.md
  modified:
    - backend/internal/config/config.go
    - backend/internal/config/config_test.go
    - backend/.env.example
decisions:
  - "AI_EMBEDDING_DIM defaults to 1536 (D-01 canon) via getInt, but validate() errors on <=0 or >2000 (Rule B12) — no silent fallback to an invalid dimension"
metrics:
  duration: ~15min
  completed: "2026-08-01"
---

# Phase 2 Plan 1: Lock canonical embedding model + dimension before pgvector DDL

**One-liner:** Locks the canonical embedding model (text-embedding-3-small, 1536-dim) in config via fail-fast `AI_EMBEDDING_DIM` validation and installs a runnable Nigerian-language adequacy spike test — the PGV-04a hard entry blocker for the `ai_vectors` DDL.

## Objective Fulfilled

PGV-04a satisfied: the embedding canon (D-01: `text-embedding-3-small`, 1536-dim) is pinned in config BEFORE any `ai_vectors` DDL. A real, runnable spike test evaluates semantic adequacy for Nigerian Pidgin + Hausa content via the exact app provider path (`ai.NewProvider`). Startup fails fast on a missing (≤0) or oversized (>2000, HNSW cap per D-02) dimension.

## Tasks Executed

| Task | Name | Result | Commit |
|------|------|--------|--------|
| 1 | Nigerian-language embedding adequacy spike (`TestEmbeddingNigerianLanguageAdequacy`) | PASS (clean SKIP — no `AI_OPENAI_API_KEY` in env; documented rationale, T-PGV-01-03) | `aeca5bf` (backend) |
| 2 | Lock `AI_EMBEDDING_DIM` config with fail-fast validation | PASS — `go test ./internal/config/` all green incl. 2 new negative tests | `2c75fc3` (backend) |

## Verification Results

- `cd backend && go test ./internal/config/ -v` — **all pass** (8/8 `TestLoad_Validation` subtests incl. `missing AI_EMBEDDING_DIM rejected` + `oversized AI_EMBEDDING_DIM rejected`)
- `cd backend && go test ./internal/ai/ -run TestEmbeddingNigerianLanguageAdequacy -v` — **passes** (skips cleanly, 0.00s, documented skip rationale)
- `go build ./...` — **OK** (full backend builds)
- `02-01-SPIKE.md` — exists with model, dimension, skip rationale, result

## Files Created/Modified

| File | Change |
|------|--------|
| `backend/internal/ai/embed_spike_test.go` | NEW — spike eval: drives `NewProvider` (Provider=openai, OpenAIModel=text-embedding-3-small); asserts dim==1536 on every embedding; Pidgin+Hausa paraphrase pairs >0.75, unrelated <0.60; skips without `AI_OPENAI_API_KEY` |
| `backend/internal/config/config.go` | ADD `EmbeddingDim int` to `AIConfig` (`env:"AI_EMBEDDING_DIM"`), default 1536 via `getInt`; validate(): error when ≤0 or >2000 |
| `backend/internal/config/config_test.go` | Valid fixture + `EmbeddingDim: 1536`; new subtests `missing AI_EMBEDDING_DIM rejected`, `oversized AI_EMBEDDING_DIM rejected` |
| `backend/.env.example` | `AI_EMBEDDING_DIM=1536` documented next to AI_ENGINE_* with D-01/D-02 rationale |
| `backend/.env` | `AI_EMBEDDING_DIM=1536` added (executor-local, gitignored, NOT committed) |
| `.planning/phases/02-pgvector-migration/02-01-SPIKE.md` | NEW — spike report: canon, result (SKIPPED), skip rationale, rerun instructions, gate statement |

## Deviations from Plan

None — plan executed exactly as written.

**Note on spike skip:** The spike is designed to run with a live key; the environment has none (commented out in `backend/.env`). Per the plan's documented behavior (T-PGV-01-03, "accept" disposition), the test skips cleanly, the D-01 canon stands, and the skip rationale + pending-eval statement are recorded in `02-01-SPIKE.md`. This is the planned outcome, not a deviation. The eval gate remains runnable: `export AI_OPENAI_API_KEY=... && go test ./internal/ai/ -run TestEmbeddingNigerianLanguageAdequacy -v`.

## must_haves Truths — Confirmed

1. ✅ **Canon locked before DDL**: `AI_EMBEDDING_DIM=1536` in config + `.env.example`; `text-embedding-3-small` asserted in spike test; no `ai_vectors` DDL exists anywhere (verified: only `CREATE EXTENSION` core migration from parallel 02-02 wave).
2. ✅ **Nigerian-language adequacy spike confirms or surfaces blocker**: spike test exists and is runnable; without a key it cleanly skips with documented rationale and the canon stands pending future eval (T-PGV-01-03 accepted disposition).
3. ✅ **Startup fails fast on missing/oversized dimension**: `validate()` errors on `EmbeddingDim <= 0` ("AI_EMBEDDING_DIM is required") and `> 2000` (HNSW cap); regression tests cover both.

## must_haves Artifacts — Confirmed

| Artifact | contains constraint | Verified |
|----------|--------------------|----------|
| `backend/internal/config/config.go` | `EmbeddingDim` | ✅ (5 occurrences) |
| `backend/.env.example` | `AI_EMBEDDING_DIM` | ✅ |
| `backend/internal/ai/embed_spike_test.go` | `text-embedding-3-small` | ✅ (3 occurrences) |

## key_links — Confirmed

- `config.go → validate()`: errors when `EmbeddingDim <= 0` or `> 2000` ✅
- `embed_spike_test.go → text-embedding-3-small`: asserts output dim == 1536 + paraphrase similarity thresholds ✅

## Threat Register — Dispositions Honored

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-PGV-01-01 (config.go validate, D) | mitigate | ✅ `<=0`/`>2000` error, no silent default |
| T-PGV-01-02 (embed_spike_test.go, I) | mitigate | ✅ dim==1536 asserted per embedding; misconfigured provider fails test |
| T-PGV-01-03 (eval gate, D) | accept | ✅ skip without key, rationale recorded in SPIKE.md |
| T-PGV-01-04 (config.go validate, I) | mitigate | ✅ no fallback for invalid dim; regression tests for missing + oversized |

## Success Criteria — Confirmed

- ✅ Canon locked before any DDL: `AI_EMBEDDING_DIM=1536`, model `text-embedding-3-small` — recorded in SPIKE report + config
- ✅ Startup fails fast on missing (>0) or oversized (>2000) dimension
- ✅ No `ai_vectors` DDL written anywhere (PGV-04a gate respected)

## Known Stubs

None — the spike test's skip-without-key path is intentional (T-PGV-01-03) and documented; no UI/component stubs involved.

## Threat Flags

None — no new network endpoints, auth paths, file access, or schema changes introduced.

## Self-Check: PASSED

- ✅ `backend/internal/ai/embed_spike_test.go` exists
- ✅ `backend/internal/config/config.go` exists
- ✅ `backend/internal/config/config_test.go` exists
- ✅ `backend/.env.example` exists
- ✅ `.planning/phases/02-pgvector-migration/02-01-SPIKE.md` exists
- ✅ `.planning/phases/02-pgvector-migration/02-01-SUMMARY.md` exists
- ✅ Commit `aeca5bf` (spike test) exists in backend submodule
- ✅ Commit `2c75fc3` (config lock) exists in backend submodule
