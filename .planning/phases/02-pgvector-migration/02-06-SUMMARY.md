---
phase: 02-pgvector-migration
plan: 06
subsystem: api
tags: [pgvector, qdrant, rag, golang, gin, docker-compose, kubernetes, config]

# Dependency graph
requires:
  - phase: 02-04
    provides: PGVectorStore implementation (internal/ai/vector/pgvector.go)
  - phase: 02-05
    provides: qdrant→pgvector copy CLI (cmd/copy-qdrant-vectors), vector(n) column migration
provides:
  - AI vector config fully on AI_PGVECTOR_DSN (required, validated at startup)
  - RAG pipeline wired to PGVectorStore with D-14 startup dimension probe
  - Qdrant retired from docker-compose and k8s base manifests
affects: [Phase 7 RET-02 (final qdrant.go removal), ai-engine integration, docs/FSD AI sections]

# Tech tracking
tech-stack:
  added: [pgvector DSN config surface]
  patterns: [unconditional required config validation (Rule B6/B12), startup embedder dimension probe fail-fast (D-14), same-change swap to avoid silent-disable windows]

key-files:
  created: []
  modified:
    - backend/internal/config/config.go
    - backend/internal/config/config_test.go
    - backend/internal/ai/config.go
    - backend/.env.example
    - backend/internal/router/setup.go
    - backend/docker-compose.yml
    - backend/deploy/k8s/base/configmap.yaml
    - backend/deploy/k8s/base/kustomization.yaml
  deleted:
    - backend/deploy/k8s/base/qdrant-deployment.yaml
    - backend/deploy/k8s/base/qdrant-service.yaml
    - backend/deploy/k8s/base/qdrant-pvc.yaml

key-decisions:
  - "AI_PGVECTOR_DSN required unconditionally in validate() (mirrors AI_ENGINE_URL precedent; no default, Rule B6/B12) — server never starts without a vector backend"
  - "Config swap + router wiring landed in the SAME commit (T-PGV-06-03) so there is no window where RAG is silently disabled (RESEARCH pitfall 6)"
  - "D-14 startup probe: embedder invoked with a probe text; error or dimension mismatch → logger.Fatal (fail-fast; NewRouter has no error return, cmd/server precedent)"
  - "Qdrant Go code (qdrant.go, store.go comment, copy tool) whitelisted and retained per D-05 — final removal is Phase 7 RET-02"
  - "Compose api env gets AI_PGVECTOR_DSN + AI_EMBEDDING_DIM because validation is unconditional — container would fail startup otherwise (deviation Rule 3)"

patterns-established:
  - "Pattern: required config validated unconditionally in config.validate(), never gated on feature flags"
  - "Pattern: startup probe for embedder/column dimension parity, logger.Fatal on mismatch"

requirements-completed: [PGV-06]

# Metrics
duration: 10min
completed: 2026-08-01
---

# Phase 02 Plan 06: Cut Over to pgvector, Retire Qdrant Summary

**AI vector config swapped from AI_QDRANT_* to required AI_PGVECTOR_DSN, RAG pipeline wired to PGVectorStore behind the same vector.Store interface with a D-14 startup dimension probe, and Qdrant fully retired from docker-compose and k8s base manifests**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-01T06:55:43Z
- **Completed:** 2026-08-01T07:05:43Z
- **Tasks:** 3 (committed as 2 backend commits — Tasks 1+2 atomic per T-PGV-06-03, Task 3 separate)
- **Files modified:** 8 modified + 3 deleted (backend), 1 submodule pointer (root)

## Accomplishments
- Config fully swapped: `AIConfig` lost `QdrantURL/QdrantAPIKey/QdrantTimeout`, gained `PgVectorDSN` (`AI_PGVECTOR_DSN`, no default) with an unconditional `validate()` required-check — server refuses to start without a vector backend (verified: `AI_PGVECTOR_DSN is required` → exit 1)
- Router wires `vector.NewPGVectorStore(repoFactory, "text-embedding-3-small", "v1", "v1", cfg.AI.EmbeddingDim)` behind the same gate shape (now on the DSN) with chunker + embedder untouched (zero RAG/agent changes)
- D-14 startup probe: embedder invoked with "academio embedding dimension probe"; error or mismatch vs `AI_EMBEDDING_DIM` → `logger.Fatal` (never starts with a mis-dimensioned vector backend)
- Qdrant retired: qdrant service + `qdrant_data` volume removed from compose, 3 qdrant k8s manifests `git rm`'d + dropped from kustomization, configmap swaps to cluster-internal `AI_PGVECTOR_DSN` + `AI_EMBEDDING_DIM`
- Sweep gates all zero: `AI_QDRANT_` refs, compose `qdrant`, k8s `qdrant`; whitelisted Go files still present; `docker compose config --quiet` valid
- Server rebuilt and restarted on the new binary; health 200; fail-fast negative path proven (empty DSN → config validation error → exit 1)

## Task Commits

Each task was committed atomically:

1. **Task 1+2: swap AI config to pgvector DSN + wire PGVectorStore with D-14 probe** - `7c424d6` (feat; 5 files — config.go, config_test.go, ai/config.go, .env.example, setup.go)
2. **Task 3: cut over to pgvector, retire qdrant** - `debd63c` (feat; compose + k8s base, 3 qdrant yamls deleted)

**Plan metadata:** `58bd7e4` (root: feat(02-06), backend submodule 21fcb16 → debd63c)

_Note: Tasks 1+2 intentionally share one commit — T-PGV-06-03 mandates the DSN swap and wiring land in the SAME change so the RAG pipeline is never silently disabled (RESEARCH pitfall 6)._

## Files Created/Modified
- `backend/internal/config/config.go` - Removed QdrantURL/QdrantAPIKey/QdrantTimeout + defaults; added PgVectorDSN (AI_PGVECTOR_DSN, no default) + unconditional required check in validate()
- `backend/internal/config/config_test.go` - Valid fixture gains PgVectorDSN; new negative subtest "missing AI_PGVECTOR_DSN rejected" (ErrorContains "AI_PGVECTOR_DSN")
- `backend/internal/ai/config.go` - Dropped Qdrant vector.QdrantConfig field + FromAppConfig mapping; removed now-unused "time" and vector imports (compile-breaker fixed)
- `backend/.env.example` - AI_QDRANT_URL/API_KEY/TIMEOUT lines replaced with AI_PGVECTOR_DSN DSN
- `backend/internal/router/setup.go` - Qdrant store block replaced with NewPGVectorStore + D-14 probe + updated init log (pgvector_dsn); zero NewQdrantStore/qdrant_url refs
- `backend/docker-compose.yml` - Removed qdrant service + qdrant_data volume; api env gains AI_PGVECTOR_DSN + AI_EMBEDDING_DIM
- `backend/deploy/k8s/base/configmap.yaml` - AI_QDRANT_URL → AI_PGVECTOR_DSN (cluster DSN) + AI_EMBEDDING_DIM
- `backend/deploy/k8s/base/kustomization.yaml` - Dropped 3 qdrant resource refs
- `backend/deploy/k8s/base/qdrant-{deployment,service,pvc}.yaml` - Deleted (git rm)

## Decisions Made
- AI_PGVECTOR_DSN is required unconditionally in validate() — mirrors the AI_ENGINE_URL precedent, keeping the server from starting without a vector backend (Rule B6/B12)
- Config swap + wiring in ONE commit to avoid a silent-disable window (T-PGV-06-03)
- D-14 probe uses logger.Fatal (NewRouter has no error return; cmd/server precedent) — startup dimension check is mandatory
- Whitelisted Qdrant Go artifacts retained per D-05 (behavioral reference); final removal Phase 7 RET-02
- Compose api env must carry AI_PGVECTOR_DSN/AI_EMBEDDING_DIM — unconditional validation makes them mandatory in every deployment surface

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Compose api service would fail startup without AI_PGVECTOR_DSN**
- **Found during:** Task 3 (Qdrant retirement)
- **Issue:** Config validation for AI_PGVECTOR_DSN is unconditional (Task 1). Removing AI_QDRANT_URL from compose api env without adding the DSN would make the api container die at startup with "AI_PGVECTOR_DSN is required".
- **Fix:** Added `AI_PGVECTOR_DSN` (compose-internal DSN, academio user) + `AI_EMBEDDING_DIM: "1536"` to the api service environment in docker-compose.yml.
- **Files modified:** backend/docker-compose.yml
- **Verification:** `docker compose config --quiet` valid; all gates pass.
- **Committed in:** debd63c (part of Task 3 commit)

**2. [Rule 3 - Environment] Stale gitignored binaries retained old AI_QDRANT_ strings**
- **Found during:** Task 3 sweep
- **Issue:** `./server`, `./seed`, `./tmp/server` (gitignored build artifacts) still contained AI_QDRANT_ strings from prior builds; `seed-demo` is a tracked binary.
- **Fix:** Removed stale gitignored binaries (`server`, `seed`, `tmp/server`); restored the tracked `seed-demo` binary untouched (its committed content is pre-cutover and unchanged — binary grep matches go to stderr, not the gate's stdout count).
- **Files modified:** none tracked (only untracked artifacts removed)
- **Verification:** `grep -rin "AI_QDRANT_" --exclude-dir=vendor --exclude-dir=node_modules .` → 0 on stdout.
- **Committed in:** n/a (no tracked changes)

---

**Total deviations:** 2 auto-fixed (2× Rule 3)
**Impact on plan:** Both were correctness/operability necessities — compose would not boot, and stale artifacts polluted the sweep. No scope creep.

## Issues Encountered
- **RAG init log not visible in dev:** The plan's Task 2 done criterion mentions confirming the "RAG pipeline initialized" log on restart. In this dev environment `AI_ENABLED` is commented out and no provider keys are set, so the `aiProvider != nil && cfg.AI.Enabled` gate skips the RAG block — identical to pre-cutover behavior. Verified instead: build + vet pass, config validation is unconditional (empty DSN → exit 1), server starts healthy on the new binary. The RAG log will appear when AI is enabled in a real environment.
- **Negative startup test nuance:** `env -u AI_PGVECTOR_DSN` did NOT fail because godotenv loads the DSN from backend/.env (correct behavior). Fail-fast was proven with `AI_PGVECTOR_DSN=` (explicit empty) → `config validation: AI_PGVECTOR_DSN is required` → exit 1.
- **kubectl/kustomize unavailable:** `kubectl kustomize deploy/k8s/base` skipped per plan ("if available"); YAML parse validity verified via python yaml.safe_load for all three edited manifests.

## User Setup Required
None - no external service configuration required. Existing deployments must add `AI_PGVECTOR_DSN` (and `AI_EMBEDDING_DIM`) to their env/configmap; compose and k8s base manifests are already updated.

## Next Phase Readiness
- RAG pipeline runs on pgvector; config + compose + k8s fully on the new DSN
- Phase 7 RET-02 can remove the whitelisted Qdrant Go artifacts (qdrant.go behavioral reference, store.go comment, copy tool)
- Docs (gitignored, local) annotated as historical: docs/ops/deploy.md, docs/FSD/01-PRODUCT.md, 05-PLATFORM.md, 06-ENGINEERING.md, docs/architecture/5-AI-ARCHITECTURE.md

---
*Phase: 02-pgvector-migration*
*Completed: 2026-08-01*

## Self-Check: PASSED
- FOUND: .planning/phases/02-pgvector-migration/02-06-SUMMARY.md
- FOUND: backend commit 7c424d6 (Tasks 1+2)
- FOUND: backend commit debd63c (Task 3)
- FOUND: root commit 58bd7e4 (submodule bump)
- FOUND: backend/internal/config/config.go, internal/router/setup.go, internal/ai/vector/pgvector.go, whitelisted internal/ai/vector/qdrant.go, cmd/copy-qdrant-vectors/main.go
