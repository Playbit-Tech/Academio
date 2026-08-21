---
phase: 01-foundation
plan: 05
subsystem: infra
tags: [github-actions, ci, uv, ruff, pyright, pytest, docker, fastapi]

# Dependency graph
requires:
  - phase: 01
    provides: ai-engine/ Python skeleton (pyproject.toml dev deps, committed uv.lock, Makefile lint/typecheck/test targets, multi-stage Dockerfile)
provides:
  - Root CI workflow .github/workflows/ai-engine.yml gating every ai-engine/** change with ruff lint, pyright typecheck, pytest, and docker build (blocks on failure)
  - Path-scoped triggers (push + pull_request) + workflow_dispatch manual runs; concurrency cancel-in-progress
  - Supply-chain-pinned setup-uv (v9.0.0 commit SHA) + uv sync --frozen (lockfile drift = CI failure)
affects: [Phase 2 PGV planning, Phase 3 Python endpoints, Phase 6 TES-01 eval harness in CI]

# Tech tracking
tech-stack:
  added: [astral-sh/setup-uv v9.0.0 (pinned c771a70e)]
  patterns:
    - "Root workflow mirrors docs.yml conventions: checkout@v4, submodules: false, paths filter, workflow_dispatch, permissions contents: read, concurrency group"
    - "One job per concern (lint/typecheck/test/docker-build) — each failure names the exact gate that broke"
    - "uv sync --frozen in every uv job — committed lockfile makes dependency drift a CI failure"

key-files:
  created:
    - .github/workflows/ai-engine.yml
  modified: []

key-decisions:
  - "setup-uv pinned to the verified v9.0.0 commit SHA (c771a70e...) with # v9.0.0 comment — never a floating @v9 tag (supply-chain hygiene, T-05-01)"
  - "uv sync --frozen in all three uv jobs — lockfile committed in Plan 01; drift fails CI instead of silently changing deps (T-05-04)"
  - "working-directory: ai-engine under defaults.run — keeps workflow readable, no cd prefixes (T-05-02 minimizes scope via path filter + read-only permissions)"
  - "docker-build job has NO uv steps and no registry login — only proves the multi-stage Dockerfile builds on a clean runner (T-05-03: no secrets in workflow)"

patterns-established:
  - "Pattern 1: root repo workflows gate root-tracked code (ai-engine/), while backend Go CI stays in the backend submodule repo (SC5)"
  - "Pattern 2: CI must run the exact commands the Makefile documents (lint/typecheck/test) so local and CI gates never drift"
  - "Pattern 3: action pins = commit SHA for critical supply-chain (setup-uv), major tag matching repo precedent (checkout@v4)"

requirements-completed: [FND-05]

# Metrics
duration: 3min
completed: 2026-07-31
---

# Phase 1 Plan 5: Root CI Workflow for ai-engine Summary

**Root GitHub Actions workflow (`.github/workflows/ai-engine.yml`) gating every `ai-engine/**` push/PR with ruff lint, pyright typecheck, pytest, and a clean-runner Docker build — setup-uv pinned to the v9.0.0 commit SHA, `uv sync --frozen` lockfile-enforced, all four gates verified green locally against the real Plan-01 artifacts, zero Go changes (SC5)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-31T21:39:10Z
- **Completed:** 2026-07-31T21:41:43Z
- **Tasks:** 2
- **Files modified:** 1 created

## Accomplishments
- `ai-engine` CI quality gate shipped (FND-05): 4 parallel jobs — `lint` (ruff), `typecheck` (pyright), `test` (pytest -v), `docker-build` — each failure names the exact gate that broke
- Triggers path-scoped on push AND pull_request (`ai-engine/**` + the workflow file itself), plus `workflow_dispatch` for manual runs; `permissions: contents: read` and a `cancel-in-progress` concurrency group mirror docs.yml
- All four CI commands proven green locally against the Plan-01 artifacts: `uv sync --frozen`, `uv run ruff check .`, `uv run pyright`, `uv run pytest -q` (4/4 tests) — and `docker build -t ai-engine:ci ./ai-engine` builds successfully
- Backend Go untouched and green (`go build ./...` + `go vet` pass) — SC5 satisfied; backend CI remains in the backend submodule repo

## Task Commits

Each task was committed atomically:

1. **Task 1: Create .github/workflows/ai-engine.yml** - `22605e7` (feat)
2. **Task 2: Verify workflow triggers, commands, and Docker buildability** - verification-only, no file changes (deliverable committed in `22605e7`)

**Plan metadata:** pending (SUMMARY/STATE/ROADMAP metadata commit)

_Note: Task 2 produced no diff — it verified the Task-1 commit against the real artifacts (uv gates, docker build, Go build). No empty commit was created._

## Files Created/Modified
- `.github/workflows/ai-engine.yml` - 4-job root CI: lint/typecheck/test (uv jobs: checkout@v4 submodules:false → setup-uv pinned v9.0.0 → uv sync --frozen → gate command) + docker-build (checkout + `docker build -t ai-engine:ci ./ai-engine`); path-scoped triggers, workflow_dispatch, contents: read, concurrency group `ai-engine-${{ github.ref }}`

## Decisions Made
- **setup-uv commit-pinned:** `c771a70e...` (v9.0.0) with inline `# v9.0.0` comment — verified pin from RESEARCH.md; floating `@v9` tags are tag-mutation targets (T-05-01 mitigate)
- **`uv sync --frozen` everywhere:** lockfile committed in Plan 01; any drift between pyproject.toml and uv.lock fails CI (pitfall #8, T-05-04 mitigate)
- **`submodules: false` on checkout:** matches docs.yml; `ai-engine/` is root-tracked (submodule-ready), no submodule init needed
- **One job per concern:** parallel execution; a lint failure doesn't get buried under test output
- **No secrets in the workflow:** no env vars, no registry login, no token passing (T-05-03 mitigate)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- **PyYAML 1.1 `on` key quirk (verification scripts only):** `yaml.safe_load` parses the `on:` trigger key as boolean `True`; verification scripts accessed it via `d.get('on', d.get(True))`. Cosmetic — the workflow file itself is correct (GitHub parses YAML 1.2 where `on` is a string key). No file change required.
- **`# v9.0.0` comment stripped by YAML parse:** expected — it is a YAML comment. Verified the SHA pin in the parsed value AND the comment in the raw file. Correct supply-chain documentation pattern.

## User Setup Required
None - no external service configuration required. CI runs on GitHub-hosted runners; local dev needs `uv` installed (present in this environment).

## Next Phase Readiness
- FND-05 satisfied: every `ai-engine/**` change is gated by ruff + pyright + pytest + docker build, blocking on failure
- Path-scoped triggers keep CI focused on the engine; `workflow_dispatch` gives humans a manual run button
- Existing Go CI untouched and locally green (SC5)
- Phase 01-foundation complete (5/5 plans) — ready for Phase 2 (pgvector) planning
- Residual risk: the workflow's first authoritative run happens on the first real push/PR to the root repo (local verification used the same commands and passed)

---
*Phase: 01-foundation*
*Completed: 2026-07-31*

## Self-Check: PASSED
- Workflow file exists on disk: `[ -f ".github/workflows/ai-engine.yml" ]` → verified (created and committed)
- Commit present: `git log --oneline | grep 22605e7` → verified
- No Go files modified by this plan (SC5): verified via `git status --porcelain`
- docs.yml untouched; backend submodule clean: verified
