---
phase: 03-python-ai-engine
plan: 02
subsystem: ai-engine-python
tags: [uv, pydantic-settings, fastapi, anthropic, openai, psycopg, pgvector, tenacity, tesseract, docker, compose]

# Dependency graph
requires:
  - phase: 03-python-ai-engine
    provides: plan 03-01 proto/aiengine.proto contract seam (unchanged by this plan)
provides:
  - Phase 3 dependency set locked in uv.lock (13 packages: anthropic, openai, psycopg[binary], psycopg-pool, pgvector, tenacity, pypdf, pdf2image, pytesseract, python-docx, python-pptx, openpyxl, pillow) with fastapi[standard]>=0.140,<0.141 pin preserved
  - Full Settings surface: 25 AI_* fields (D-01 keys, Azure endpoint/deployment/api-version, AI_OLLAMA_BASE_URL, AI_PGVECTOR_DSN, embeddings, prompts dir, DoS bounds, chunker, provider TTL/cooldown, doc gates) with http(s):// scheme fail-fast validation
  - Provider registry: parse_model_composite (first-colon split, '/' survives, openai default), build_provider_registry (5 providers + configured flags), get_provider, ProviderInfo frozen dataclass + Provider protocol
  - tenacity retry presets (provider_retry TransportError/Timeout, embed_retry HTTPStatusError; 3 attempts, exp backoff)
  - Dockerfile runtime apt layer: tesseract-ocr 5.5.0 + tesseract-ocr-eng + poppler-utils 25.03.0 (verified in built image)
  - Compose ai-engine env expansion: AI_PGVECTOR_DSN, provider keys (empty-safe interpolation), AI_PROMPTS_DIR, AI_OLLAMA_BASE_URL + host-gateway extra_hosts
affects: 03-03 (chat providers), 03-04 (providers/embed), 03-05 (documents), 03-06 (search), 03-07 (prompts)

# Tech tracking
tech-stack:
  added: [anthropic, openai, psycopg[binary], psycopg-pool, pgvector, tenacity, pypdf, pdf2image, pytesseract, python-docx, python-pptx, openpyxl, pillow]
  patterns: [pydantic-settings env-only config with fail-fast validators, Provider protocol + registry routing, tenacity retry presets as shared dicts, first-colon composite parsing]

key-files:
  created: [ai-engine/app/providers/__init__.py, ai-engine/app/providers/base.py, ai-engine/app/providers/registry.py, ai-engine/app/util/__init__.py, ai-engine/app/util/retry.py, ai-engine/tests/test_config.py, ai-engine/tests/test_registry.py]
  modified: [ai-engine/pyproject.toml, ai-engine/uv.lock, ai-engine/app/config.py, ai-engine/Dockerfile, backend/docker-compose.yml]

key-decisions:
  - "All 13 Phase 3 deps added via uv add with RESEARCH-verified minimum versions; jinja2/httpx left as transitive (never added explicitly)"
  - "Settings defaults are empty strings for keys; only non-secrets default (Ollama URL, Azure API version, embedding model/base_url/batch, prompts dir, DoS caps, chunker, TTL/cooldown, doc gates)"
  - "base_url scheme validation (http(s)://) as field validator on AI_OLLAMA_BASE_URL/AI_EMBEDDING_BASE_URL/AI_AZURE_OPENAI_ENDPOINT — T-03-02-03 fail-fast, Rule B12 spirit"
  - "parse_model_composite splits on FIRST colon so '/' survives in openrouter:openai/gpt-4o-mini; unprefixed models default to openai (D-03)"
  - "Compose provider keys use \${VAR:-} empty-safe interpolation — absent keys never block startup, /v1/providers reports unavailable (D-10, T-03-02-02)"
  - "AI_OLLAMA_BASE_URL compose default is http://host.docker.internal:11434 with extra_hosts host-gateway (Linux-only mapping; Docker Desktop auto-maps)"
  - "AI_ENABLED deliberately NOT wired — Go-side gate deferred to Phase 5 (RESEARCH open-question 4)"

patterns-established:
  - "Config: env-only secrets (Rule B6 spirit), empty-string defaults, extra='ignore', fail-fast validators for anything flowing to outbound HTTP"
  - "Provider abstraction: Protocol (chat/stream) + frozen ProviderInfo dataclass + registry keyed by provider name"
  - "Retry: shared tenacity preset dicts imported by future chat/embed code (3 attempts, wait_exponential 1-10s)"
  - "Composite model string 'provider:model' parsed on first colon (D-03)"

requirements-completed: [PYE-01, PYE-02, PYE-04]

# Metrics
duration: 30min
completed: 2026-08-01
---

# Phase 3 Plan 2: Python Foundation Summary

**uv-locked Phase 3 deps (13 packages, fastapi <0.141 pin intact), 25-field AI_* Settings surface with fail-fast URL validation, provider registry with first-colon `provider:model` routing (D-03), tenacity retry presets, Dockerfile OCR apt layer (tesseract 5.5.0 + poppler 25.03.0), and compose ai-engine env expansion — all CI gates green**

## Performance

- **Duration:** 30 min (Task 1–2 committed 08:08–08:09Z, Tasks 3–4 completed 08:38Z)
- **Started:** 2026-08-01T08:08:24Z
- **Completed:** 2026-08-01T08:38:15Z
- **Tasks:** 4
- **Files modified:** 12 (11 ai-engine + 1 backend submodule)

## Accomplishments

- **Task 1:** `uv add` locked all 13 Phase 3 deps (anthropic 0.120.2, openai 2.52.0, psycopg 3.3.4, psycopg-pool 3.3.1, pgvector 0.5.0, tenacity 9.1.4, pypdf 6.14.2, pdf2image 1.17.0, pytesseract 0.3.13, python-docx 1.2.0, python-pptx 1.0.2, openpyxl 3.1.5, pillow 12.3.0) in uv.lock; fastapi pin `>=0.140,<0.141` preserved (0.140.13 resolved); jinja2/httpx left transitive per plan. `uv sync --frozen` (73 packages), ruff, pyright all green.
- **Task 2:** `Settings` expanded to the exact 25-field AI_* surface with locked defaults (AI_EMBEDDING_DIM=1536, AI_OLLAMA_BASE_URL=http://localhost:11434, AI_EMBEDDING_BATCH_SIZE=128, AI_PROMPTS_DIR=./prompts, AI_AZURE_OPENAI_API_VERSION=2024-10-21, DoS bounds, chunker, D-10 TTL/cooldown, doc gates). http(s):// scheme validator added (T-03-02-03 fail-fast). test_config.py covers defaults, env override, and exact 25-field presence/count.
- **Task 3:** Provider skeleton — `base.py` (ProviderKind Literal, frozen ProviderInfo with configured flag, Provider chat/stream Protocol), `registry.py` (`parse_model_composite` first-colon split, `build_provider_registry` 5 providers reading Settings singleton, `get_provider` with ValueError), `util/retry.py` tenacity presets. All 6 registry test cases pass; ruff + pyright clean.
- **Task 4:** Dockerfile runtime stage apt-installs tesseract-ocr/tesseract-ocr-eng/poppler-utils (builder untouched); image built and inspected — tesseract 5.5.0, pdftoppm 25.03.0, all 13 runtime imports OK. Compose ai-engine env expanded (DSN, keys, prompts dir, Ollama base URL + host-gateway); `docker compose config --quiet` exit 0; AI_ENABLED not wired.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Phase 3 dependencies via uv and commit the lockfile** - `adaf597` (feat)
2. **Task 2: Expand Settings with the full AI_* surface** - `e4b6bda` (feat)
3. **Task 2 fix: pyright ignore for pydantic-settings _env_file kwarg** - `498e4c7` (fix)
4. **Task 3: Provider registry skeleton with provider:model routing** - `a6fa118` (feat)
5. **Task 4: Dockerfile OCR apt layer** - `14765e9` (feat)
6. **Task 4: compose ai-engine env expansion (backend submodule)** - `5a0dfa8` (feat, in backend repo)
7. **Submodule pointer bump (root repo)** - `e892585` (chore)

**Plan metadata:** completed via this SUMMARY + STATE/ROADMAP update commit (`.planning` docs commit_docs=false, tracking files still committed)

## Files Created/Modified

- `ai-engine/pyproject.toml` - 13 Phase 3 deps added; fastapi `>=0.140,<0.141` pin preserved
- `ai-engine/uv.lock` - 454-line diff, 13 new packages locked (73 total)
- `ai-engine/app/config.py` - Settings with full 25-field AI_* surface + http(s):// base_url validators
- `ai-engine/app/providers/__init__.py` - re-exports registry/base public symbols
- `ai-engine/app/providers/base.py` - ProviderKind Literal, ProviderInfo frozen dataclass, Provider Protocol
- `ai-engine/app/providers/registry.py` - parse_model_composite, build_provider_registry, get_provider
- `ai-engine/app/util/__init__.py` - re-exports retry presets
- `ai-engine/app/util/retry.py` - provider_retry + embed_retry tenacity dicts (D-05)
- `ai-engine/tests/test_config.py` - defaults/env-override/25-field presence tests
- `ai-engine/tests/test_registry.py` - 6 registry routing tests (deterministic, no keys)
- `ai-engine/Dockerfile` - runtime apt layer: tesseract-ocr tesseract-ocr-eng poppler-utils
- `backend/docker-compose.yml` - ai-engine env expansion + extra_hosts host-gateway

## Decisions Made

- All 13 deps pinned with RESEARCH-verified minimum versions; no explicit jinja2/httpx add (already transitive) per plan
- Settings keys default to empty strings (no hardcoded secrets, T-03-02-02); non-secret config gets locked defaults
- Added base_url scheme validator beyond the letter of the plan's field list — required by threat model T-03-02-03 (fail-fast, Rule B12 spirit) and confirmed by tests passing
- parse_model_composite: first-colon split; openai default for unprefixed (D-03)
- Compose provider keys `${VAR:-}` empty-safe — absent keys → `unavailable` (D-10), never startup failure (Pitfall 5)
- AI_OLLAMA_BASE_URL compose default `http://host.docker.internal:11434` + `extra_hosts: host.docker.internal:host-gateway` (Linux compose can't resolve host.docker.internal without it — W4)
- AI_ENABLED NOT wired (Go-side gate, Phase 5 — RESEARCH open-question 4)
- Compose change committed inside the backend submodule (`5a0dfa8`), root bumped via `e892585`

## Deviations from Plan

None in substance — plan executed exactly as written, with two execution-level adjustments:

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyright reportCallIssue on `Settings(_env_file=None)` in test_config.py**
- **Found during:** Task 2 verification (pyright gate)
- **Issue:** pyright does not statically model pydantic-settings' init-only `_env_file` kwarg in the synthesized `BaseModel.__init__`; both test calls errored (`reportCallIssue`). The plan's verify gate requires pyright clean.
- **Fix:** Added `# pyright: ignore[reportCallIssue]` on the reported lines (not the call's first line — pyright reports on the `_env_file` argument line); reformatted the env-override call to multi-line so the ignore lands on the flagged line.
- **Files modified:** ai-engine/tests/test_config.py
- **Verification:** `uv run pyright` → 0 errors; `uv run pytest tests/` → 13 passed
- **Committed in:** 498e4c7

**2. [Rule 3 - Blocking] `backend/docker-compose.yml` pathspec is in submodule 'backend'**
- **Found during:** Task 4 commit
- **Issue:** `backend/` is a git submodule (git@github.com:Playbits/Academio-be.git); the root-repo commit refused the compose file.
- **Fix:** Committed the compose change inside the backend submodule (`5a0dfa8`), then bumped the root pointer (`e892585`). Same result as a root-commit — compose change is the single sanctioned non-ai-engine file this phase.
- **Files modified:** backend/docker-compose.yml (backend submodule), backend pointer (root)
- **Verification:** `docker compose -f backend/docker-compose.yml config --quiet` exit 0 (run from root against submodule path)
- **Committed in:** 5a0dfa8 (backend) + e892585 (root bump)

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking)
**Impact on plan:** Both fixes were mechanical/execution-level; no scope creep, no behavior change. Plan content executed as written.

## Issues Encountered

- **Continuation state:** Tasks 1–2 were already committed (`adaf597`, `e4b6bda`) with a half-applied pyright fix left in the working tree; Task 3 files existed untracked. Verified Task 1/2 gates independently, completed the pyright fix, committed Task 3, then executed Task 4 from scratch. No rework of prior commits needed.
- **pyright `_env_file` false positive:** pydantic-settings' generated `__init__` isn't modeled by pyright; resolved with targeted ignores (documented in test file).

## User Setup Required

None - no external service configuration required. Provider API keys remain optional env vars (`AI_*_API_KEY`); absent keys are handled gracefully.

## Next Phase Readiness

- **03-03 (chat):** Provider protocol + registry + `provider:model` routing + retry presets ready; needs provider client implementations (anthropic SDK, openai SDK base_url, httpx Ollama) + cost.py + SSE envelope
- **03-04 (providers/embed):** Settings carries all keys, TTL/cooldown config, embedding model/dim/base_url/batch; needs /v1/providers ping logic + /v1/embed endpoint
- **03-05 (documents):** OCR binaries present in Docker image; Settings carries AI_MAX_DOC_PAGES/MB + chunker defaults; needs extractors + psycopg pool (D-07)
- **03-06 (search):** Settings has AI_PGVECTOR_DSN; needs hybrid RAG (dense + ts_rank + RRF k=60)
- **03-07 (prompts):** Settings has AI_PROMPTS_DIR; jinja2 already in lock (transitive)
- **Blockers:** None. Provider keys absent locally → live-provider tests will env-gate (D-12)

---
*Phase: 03-python-ai-engine*
*Completed: 2026-08-01*

## Self-Check: PASSED

- All 13 plan files found on disk (pyproject.toml, uv.lock, config.py, 3 providers files, 2 util files, 2 test files, Dockerfile, compose, SUMMARY)
- All 7 task commits found in git (adaf597, e4b6bda, 498e4c7, a6fa118, 14765e9, 5a0dfa8@backend, e892585)
- All 5 must_haves artifact `contains` constraints PASS (anthropic, AI_PGVECTOR_DSN ×2, parse_model_composite, tesseract-ocr)
- All plan verification gates green: uv sync --frozen (73 pkgs), ruff, pyright 0 errors, pytest 13 passed, compose config exit 0, fastapi pin grep
