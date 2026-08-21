---
phase: 03-python-ai-engine
plan: 07
subsystem: ai-engine
tags: [python, fastapi, jinja2, pyyaml, prompts, pye-03]

# Dependency graph
requires:
  - phase: 03-python-ai-engine
    provides: "app/config.py settings.AI_PROMPTS_DIR (default ./prompts), jinja2 3.1.6 in uv.lock, app/api/chat.py ChatRequestIn + /v1/chat + /v1/chat/stream (03-02/03-03)"
provides:
  - "Nine Git-backed prompt types (report-comments, lesson-plans, questions, rubrics, behaviour-summary, attendance-analysis, parent-letters, meeting-minutes, translation), each with prompt.yaml metadata + Jinja2 template.txt"
  - "app/prompts/prompt_library.py: load/cache/render with dev/staging/prod alias resolution (D-08) and StrictUndefined fail-loud rendering"
  - "Optional prompt_type/prompt_alias fields on /v1/chat and /v1/chat/stream — renders a library system prompt, Go ChatRequest shape untouched"
affects: [03-python-ai-engine future plans, ROADMAP criterion 5 consumers]

# Tech tracking
tech-stack:
  added: [pyyaml>=6 (explicit direct dep, was transitive-only)]
  patterns:
    - "Git-backed prompt versioning (D-08): prompts are files in the repo, not DB rows"
    - "PromptLibrary load/cache/render with _SUPPORTED allowlist — no request-derived paths"
    - "Strict render() vs lenient render_system() split (chat pipeline carries no variables)"

key-files:
  created:
    - ai-engine/prompts/{9 types}/prompt.yaml + template.txt
    - ai-engine/app/prompts/__init__.py
    - ai-engine/app/prompts/prompt_library.py
    - ai-engine/tests/test_prompts.py
  modified:
    - ai-engine/app/api/chat.py
    - ai-engine/pyproject.toml
    - ai-engine/uv.lock

key-decisions:
  - "D-08: dev/staging/prod aliases resolve to version selectors in code defaults (dev->working, staging->latest, prod->latest); unknown alias treated as raw selector"
  - "render() uses StrictUndefined (missing vars raise ValueError, no literal {{ var }} leak); chat pipeline uses render_system() — lenient Undefined because the Go ChatRequest carries no variables"
  - "prompt_type/prompt_alias are additive optional fields on ChatRequestIn; Go decoder ignores unknown JSON fields so the ChatRequest{model, messages, stream} shape stays 1:1"
  - "model_hint fallback: when prompt_type set and model omitted, req.model falls back to meta model_hint; explicit model always wins"

patterns-established:
  - "Prompt library pattern: allowlist -> load yaml+template -> cache by (type, alias) -> render"

requirements-completed: [PYE-03]

# Metrics
duration: 11min
completed: 2026-08-01
---

# Phase 3 Plan 7: Versioned Prompt Library Summary

**Nine Git-backed prompt types (prompt.yaml + Jinja2 template.txt) with a cached PromptLibrary (dev/staging/prod aliases, StrictUndefined rendering) wired into /v1/chat + /v1/chat/stream as an optional Go-compatible prompt_type**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-01T10:02:22Z
- **Completed:** 2026-08-01T10:13:32Z
- **Tasks:** 3
- **Files modified:** 25 (18 prompt files + 7 code/config/test files)

## Accomplishments
- All nine PYE-03 prompt types ship as Git-backed `prompt.yaml` + `template.txt` (18 files) — Git IS the versioning mechanism (D-08)
- `PromptLibrary` loads/caches/renders with dev/staging/prod alias resolution; `StrictUndefined` fails render loudly on missing vars instead of leaking `{{ var }}` placeholders (T-03-07-01)
- Chat pipeline serves library prompts: optional `prompt_type`/`prompt_alias` on `/v1/chat` and `/v1/chat/stream` prepends a rendered system message with model_hint fallback — additive fields, Go `ChatRequest{model, messages, stream}` shape untouched
- 12 new tests (8 library + 4 chat wiring) — full suite 109 passed, 9 skipped (7 DB-gated skip cleanly without `AI_PGVECTOR_DSN`); ruff + pyright clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Nine Git-backed prompt types (prompt.yaml + Jinja2 template.txt)** - `4101cfe` (feat)
2. **Task 2 dep: add explicit pyyaml>=6 dependency** - `17d8af7` (chore)
3. **Task 2: prompt_library — load/cache/render with dev/staging/prod aliases** - `87c6c38` (feat)
4. **Task 3: wire optional prompt_type into /v1/chat + /v1/chat/stream** - `fab5374` (feat)

**Plan metadata:** not committed (`.planning/` is excluded from commit scope)

_Note: pyyaml dependency was promoted to a direct dep in its own commit before the module that imports it, per plan instruction._

## Files Created/Modified
- `ai-engine/prompts/{report-comments,lesson-plans,questions,rubrics,behaviour-summary,attendance-analysis,parent-letters,meeting-minutes,translation}/prompt.yaml` - name/version/description/model_hint metadata (canonical keys, version "1.0")
- `ai-engine/prompts/{...}/template.txt` - Jinja2 templates, `{{ var }}` placeholders only (zero `{% %}` control blocks — verified)
- `ai-engine/app/prompts/__init__.py` - re-exports `PROMPT_TYPES`, `PromptLibrary`, `library` singleton
- `ai-engine/app/prompts/prompt_library.py` - core module: `_SUPPORTED` allowlist, `_load`, `_resolve_alias`, `get_prompt` (cached), strict `render()`, lenient `render_system()`
- `ai-engine/app/api/chat.py` - `ChatRequestIn` extended (model optional, prompt_type/prompt_alias), `_resolve_messages()` helper, both routes wired
- `ai-engine/tests/test_prompts.py` - 12 tests (8 library: render w/ vars, missing-var ValueError, unknown-type ValueError, all-nine coverage, alias resolution, cache no-reread, AI_PROMPTS_DIR override, zero control blocks; 4 wiring: passthrough unchanged, system prepend + model_hint fallback, unknown type 400, stream SSE intact)
- `ai-engine/pyproject.toml`, `ai-engine/uv.lock` - `pyyaml>=6` promoted to explicit direct dependency (6.0.3 resolved)

## Decisions Made
- **Strict vs lenient render split:** plan Task 2 (b) required missing vars -> ValueError (StrictUndefined), but Task 3 test (b) requires rendering a system prompt with no variables for the chat pipeline. Resolved with `render()` (strict, for callers holding full vars maps) and `render_system()` (lenient Undefined — unfilled slots degrade to empty strings, never executable content since templates are server-authored `{{ var }}`-only). Verified empirically: StrictUndefined raises, lenient renders.
- **Cache keyed on resolved alias:** `get_prompt` caches by `(type, resolved_alias)` dict instead of plan's `@lru_cache` sketch — the cache-test (monkeypatched `Path.read_text` count == 2) proves single file-read per (type, alias).
- **model_hint fallback semantics:** `anthropic:claude-3-5-sonnet-latest` model_hint -> provider `anthropic`, model `claude-3-5-sonnet-latest` (test asserts the bare model name after composite parse).
- **400 on unknown prompt_type** with sanitized detail (T-03-07-05) — no file contents or keys in the error.
- **Explicit `pyyaml>=6` dependency:** the plan notes yaml "not present in Phase 1 lock" — confirmed, added via `uv add pyyaml>=6` (promoted from transitive-only; no fastapi version bump).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Lenient `render_system()` added for chat pipeline**
- **Found during:** Task 3 (chat wiring tests)
- **Issue:** Plan Task 2 (b) requires missing vars -> ValueError (StrictUndefined), but Task 3 (b) renders the chat system prompt with `{}` variables — strict rendering would always raise for the chat path (Go ChatRequest carries no variables), making the wiring unusable.
- **Fix:** Added `PromptLibrary.render_system(prompt_type, alias)` — lenient `Undefined` environment for the chat pipeline; kept strict `render()` for callers with full vars maps. Templates remain `{{ var }}`-only, so unfilled slots are whitespace, never literal placeholders or executable logic.
- **Files modified:** ai-engine/app/prompts/prompt_library.py, ai-engine/app/api/chat.py, ai-engine/tests/test_prompts.py
- **Verification:** test (b) wiring passes; tests (a)/(b) of library still prove strict ValueError behavior
- **Committed in:** `fab5374` (Task 3 commit)

**2. [Rule 1 - Bug] `get_prompt` cache was not used**
- **Found during:** Task 2 (post-write self-review before tests)
- **Issue:** Initial `get_prompt` implementation ignored `self._cache` (recomputed on every call), defeating the cache test (f) requirement of single file-read per (type, alias).
- **Fix:** `get_prompt` now consults `self._cache` keyed on `(type, resolved_alias)` and stores the loaded dict on miss.
- **Files modified:** ai-engine/app/prompts/prompt_library.py
- **Verification:** cache test (f) — monkeypatched `Path.read_text` count == 2 (prompt.yaml + template.txt read exactly once)
- **Committed in:** `87c6c38` (Task 2 commit)

**3. [Rule 1 - Bug] Fix-test corrections in Task 3 wiring tests**
- **Found during:** Task 3 (test run)
- **Issue:** Two wiring tests asserted filled variable values ("Ada", "Mathematics") in the chat system message — wrong: `render_system()` renders with NO variables by design.
- **Fix:** Asserted the actual contract: system role prepended, template static text present, zero `{{` leak, model_hint fallback model name.
- **Files modified:** ai-engine/tests/test_prompts.py
- **Verification:** 12/12 pass; full suite 109 passed
- **Committed in:** `fab5374` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (1 missing critical, 2 test/implementation corrections)
**Impact on plan:** All fixes were necessary for the plan's own test requirements to hold. No scope creep.

## Issues Encountered
- **Plan internal contradiction** (strict missing-var ValueError vs chat-with-empty-vars render) — resolved with the strict/lenient split documented above; flagged here as a plan-text inconsistency future plans should avoid.
- ruff I001 import-sort and UP043 type-argument findings on new files — fixed inline (import ordering, `AsyncGenerator[AsyncClient]` instead of two-arg form).
- `test_chat.py` import of `httpx` unused in test_prompts.py — removed (only needed for Ollama ping in test_chat.py).

## User Setup Required
None - no external service configuration required. All tests hermetic (no network, no DB keys; 9 skips are the pre-existing DB-gated tests skipping cleanly without `AI_PGVECTOR_DSN`).

## Next Phase Readiness
- ROADMAP criterion 5 satisfied: the versioned prompt library (Git-backed YAML, dev/staging/prod aliases) serves every PYE-03 template, wired into a live pipeline.
- All nine types render with canonical vars; chat wiring proven with recording providers (no live provider needed).
- Full suite: 109 passed, 9 skipped (DB-gated); ruff + pyright clean.

---
*Phase: 03-python-ai-engine*
*Completed: 2026-08-01*

## Self-Check: PASSED

All 7 files verified present (6 code/config + SUMMARY), all 4 task commits verified in git history (`4101cfe`, `17d8af7`, `87c6c38`, `fab5374`). Full gate suite: `uv run pytest tests/ -q` → 109 passed, 9 skipped; `uv run ruff check .` → clean; `uv run pyright` → 0 errors.
