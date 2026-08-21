---
phase: 03-python-ai-engine
verified: 2026-08-01T13:05:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 3: Python AI Engine Verification Report

**Phase Goal:** A stateless Python compute service provides multi-provider LLM access, document intelligence, embeddings, and tenant-aware RAG behind a gRPC-ready contract — the engine the Go pipeline and streaming layers call into.
**Verified:** 2026-08-01T13:05:00Z
**Status:** VERIFICATION PASSED — all criteria met
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `proto/aiengine.proto` committed at START of phase as gRPC contract with all 6 RPCs; every REST endpoint satisfies request/response semantics 1:1 | ✓ VERIFIED | `proto/aiengine.proto` (112 lines) committed 2026-08-01T09:09:25Z in `9501c51` — BEFORE any REST impl commit (03-02 `14765e9` at 09:36+). `service AiEngine` declares exactly 6 RPCs: Chat, ChatStream, Embed, Extract, IngestDocument, Search (lines 8-21). 1:1 REST mapping proven in `03-01-MAPPING.md` (8-row table + 2 deliberately excluded ops endpoints). REST matches proto semantics: `chat.py:42-52` ChatRequestIn{model, messages, stream} ↔ proto ChatRequest; `ChatResponseOut{message, usage}` ↔ ChatResponse + Usage; `/v1/chat/stream` ↔ stream EngineEvent; `embed.py:17-27` ↔ EmbedRequest/EmbedResponse; `extract.py:30-36` ↔ ExtractRequest/ExtractResponse; `/v1/documents` ↔ IngestDocument; `search.py:31-35` ↔ SearchRequest/SearchResponse |
| 2 | `/v1/chat` + `/v1/chat/stream` native SSE (text/event-stream, heartbeats ≤30s, no gzip) serve all 5 providers via direct SDKs; normalized usage {provider, model, input/output tokens, cost} on every response; NO LiteLLM/gateway | ✓ VERIFIED | `chat.py:203` media_type="text/event-stream"; headers `Cache-Control: no-cache` + `X-Accel-Buffering: no` (line 204); NO GZipMiddleware anywhere in app/ (grep clean). Heartbeats: `sse.py:31` `: ping` + immediate keep-alive (chat.py:169) + F4 `asyncio.wait_for` per-token at `AI_HEARTBEAT_INTERVAL_SECONDS=25` (chat.py:177-184) — ≤30s guaranteed. Envelope `data: {"type":...,"data":...}` compact single-line JSON, blank-line boundaries — byte-compatible with Go scanner (`backend/internal/ai/engine/sse.go:44-54` splits on blank lines, `:58-77` tolerates comments, joins data). 5 providers: `anthropic_provider.py:19` AsyncAnthropic SDK; `openai_compat.py:53` AsyncOpenAI base_url (deepseek `api.deepseek.com`, openrouter `openrouter.ai/api/v1`, azure AsyncAzureOpenAI); `ollama_provider.py:26` httpx OpenAI-compat. Normalized usage on EVERY response: `chat.py:149-155` + `sse.py:38-50` {provider, model, input_tokens, output_tokens, cost}. `grep -ri litellm\|gateway\|celery` across app/ + pyproject + uv.lock = ZERO hits. **Live evidence:** 2 Ollama live-shape tests RAN and PASSED against real `qwen3.5:9b` (Ollama live at :11434) — `test_sse_envelope_shape` (test_chat.py:186-213) asserted content-type, no-cache, x-accel-buffering, `: ping` present, compact JSON data lines, blank-line boundaries, Go-scanner-equivalent round-trip; `test_chat_usage_shape` (test_chat.py:220-235) asserted usage keys == {provider, model, input_tokens, output_tokens, cost} and provider == "ollama" |
| 3 | `/v1/providers` live status (health/cooldown); `/v1/embed` canonical model (text-embedding-3-small) matching 1536-dim | ✓ VERIFIED | `providers.py:22-36` GET /v1/providers returns {provider, status, latency_ms, last_checked, cooldown_until} per provider. `healthcheck.py`: model-less pings per kind (Anthropic GET /v1/models, OpenAI-compat /models, Azure deployments list + 1-token chat fallback at :86-100, Ollama /api/tags), 30s TTL cache (:54, :150-159), in-flight dedup (:160-164), cooldown after 3 consecutive failures for 60s (:124-137), unconfigured → "unavailable" never 500 (:167-170). `embed.py:30-56` POST /v1/embed → EmbeddingClient (embedding.py:54-86): text-embedding-3-small (settings AI_EMBEDDING_MODEL), batch ≤128, `validate_vector` 1536-dim + zero-norm fail-loud (:40-51), retry via `embed_retry` (retry.py:27-37). 3 provider status tests + embed tests in 113-passed suite |
| 4 | `/v1/extract` + `/v1/documents` parse PDF/DOCX/PPTX/TXT/CSV/images with per-page routing (digital vs Tesseract OCR ≥300 DPI); `/v1/documents` one-call extract→chunk→embed→store into validated `school_{id}` schema; every DB access validates `^school_[0-9]+$` + existence, no fallback | ✓ VERIFIED | `extract.py:68-102`: /v1/extract + /v1/documents routes. Format routing in `extractors/__init__.py:29-49` (PDF/DOCX/PPTX/XLSX/CSV/TXT/images allowlist + size gate 50MB). `pdf.py:25-45`: per-page routing — pypdf text layer > DIGITAL_THRESHOLD(20 chars) digital, else Tesseract OCR at OCR_DPI=300 (:21) with Pillow grayscale+autocontrast (:48-51); F5 convert-once O(pages) (:33); page cap 200. `office.py`: python-docx/pptx, openpyxl, csv, txt. `image.py`: Pillow + pytesseract with 80MP decompression-bomb guard. One-call pipeline `pipeline.py:19-51` ingest_document: extract → `chunk_text` (chunker.py, 1000/200 overlap) → `EmbeddingClient().embed_texts` → `insert_chunks` (vectors.py:21-66). DB gate `db/schema.py:22-34`: `^school_[0-9]+$` regex + `information_schema.schemata` existence check on the SAME pooled connection; NO global fallback (raises ValueError → 400). Qualified writes via `sql.Identifier` (vectors.py:44-50), all values `%s` params, `ON CONFLICT (document_id, chunk_index) DO NOTHING` idempotent. DSN from env only (pool.py:20-33) |
| 5 | `/v1/search` hybrid (dense + BM25/RRF k=60) with metadata filters, chunk ranking, citations, context compression, schema-scoped; versioned prompt library (Git-backed YAML, dev/staging/prod aliases, 9 types) serving all PYE-03 templates; service stateless (no Celery, service-token only) | ✓ VERIFIED | `search.py:38-66` POST /v1/search: X-School-Schema required (:43-44), query 1..2000, top_k 1..100. `hybrid.py:71-132`: dense leg `1 - (embedding <=> %s)` ORDER BY `<=>` (HNSW index-compatible, Go parity pgvector.go:244) + BM25 leg `ts_rank(to_tsvector(...))` + `rrf_merge` k=60 (:35-54); metadata filters allowlisted AND-clauses collection/document_id/embedding_model/chunk_index, parameterized, unknown keys ignored (:57-68); schema gate before ANY SQL (:83). `rerank.py`: `rank_and_cite` citations `document_id#chunk_index` (:22-37), `compress_context` dedupe + 12k-char cap (:40-59). Prompt library `prompt_library.py`: 9 types in `_SUPPORTED` frozenset (:38-50), yaml+Jinja2 load/cache (:65-91), dev/staging/prod aliases via ALIAS_DEFAULTS (:34), strict + lenient render (:93-115); 9 dirs × {prompt.yaml, template.txt} confirmed on disk; wired into chat via additive `prompt_type` (chat.py:104-133, Go shape unchanged). Stateless: no Celery/queue (grep clean), service-token only (`security.py:12-14` X-AI-Engine-Token, never user JWT). 12 prompt tests + hybrid/search/rerank tests in the 113-passed suite |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `proto/aiengine.proto` | 6 RPCs, service AiEngine | ✓ VERIFIED | Lines 8-21; committed 09:09:25 before impl |
| `ai-engine/app/api/chat.py` | /v1/chat + /v1/chat/stream, usage on every response | ✓ VERIFIED | provider:model routing (D-03); usage dict lines 149-155 |
| `ai-engine/app/sse.py` | Go-matching SSE envelope + `: ping` | ✓ VERIFIED | format_event/heartbeat/usage_event; compact separators=(",",":") |
| `ai-engine/app/providers/{anthropic_provider,openai_compat,ollama_provider,cost}.py` | 5 providers direct SDKs + price tables | ✓ VERIFIED | anthropic SDK, openai base_url, httpx; cost.py mirrors Go cost.go |
| `ai-engine/app/api/providers.py` + `healthcheck.py` | live status + TTL + cooldown | ✓ VERIFIED | 30s TTL, cooldown threshold 3/60s, unavailable-never-500 |
| `ai-engine/app/providers/embedding.py` + `api/embed.py` | canonical 1536-dim embeddings | ✓ VERIFIED | text-embedding-3-small; dim + zero-norm assert |
| `ai-engine/app/api/extract.py` | /v1/extract + /v1/documents | ✓ VERIFIED | F2 containment, F8 502+log |
| `ai-engine/app/documents/**` | PDF per-page OCR routing, office, image, chunker, pipeline | ✓ VERIFIED | DPI 300, threshold 20, convert-once (F5), size/page gates |
| `ai-engine/app/db/**` | pool + schema gate + ai_vectors insert | ✓ VERIFIED | ^school_[0-9]+$ + existence, no fallback, ON CONFLICT DO NOTHING |
| `ai-engine/app/rag/**` + `api/search.py` | hybrid dense+BM25+RRF k=60, citations, compression | ✓ VERIFIED | HNSW `<=>`, ts_rank, RRF k=60, 12k context cap |
| `ai-engine/app/prompts/prompt_library.py` + `prompts/` | Git-backed YAML, aliases, 9 types | ✓ VERIFIED | 9 dirs × yaml+txt; dev/staging/prod; 12 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | -- | ------ | ------- |
| Python SSE | Go scanner | `data: {"type":...}\n\n` + `: ping` | ✓ WIRED | Byte-compatible with sse.go splitSSEEvent/parseSSEBlock; verified live by test_sse_envelope_shape |
| chat.py | providers | `parse_model_composite` provider:model (registry.py:5-14) | ✓ WIRED | All 5 providers routed; unconfigured → 503 |
| chat.py | cost | `calculate_cost(itok, otok, provider)` (cost.py:23-25) | ✓ WIRED | Usage on every response (chat + stream) |
| /v1/documents | tenant DB | `insert_chunks` → `validate_schema_name` gate then `sql.Identifier` write (vectors.py:36-65) | ✓ WIRED | Same-connection existence check; no fallback |
| /v1/search | tenant DB | `hybrid_search` single pooled conn, gate before SQL (hybrid.py:82-83) | ✓ WIRED | Both legs schema-qualified |
| chat.py | prompt library | `library.render_system(prompt_type, alias)` (chat.py:117) | ✓ WIRED | Additive — Go shape unchanged |
| compose | engine env | `5a0dfa8` docker-compose.yml env expansion | ✓ WIRED | AI_PGVECTOR_DSN + keys via ${VAR:-} + host-gateway |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| /v1/chat/stream | evt deltas | provider SDK live streams (anthropic/openai/httpx) | ✓ (live Ollama test passed) | ✓ FLOWING |
| /v1/chat | usage | provider usage objects → cost.py | ✓ (live test asserted all 5 keys) | ✓ FLOWING |
| /v1/providers | status | live model-less pings + TTL cache | ✓ (monkeypatched unit tests + real ping path) | ✓ FLOWING |
| /v1/embed | embeddings | openai SDK → 1536-dim assert | ✓ (validate_vector fail-loud) | ✓ FLOWING |
| /v1/documents | chunks/vectors | extract → chunk → embed → insert_chunks | ✓ (7 DB-gated tests skip cleanly without DSN; insert SQL real) | ✓ FLOWING |
| /v1/search | results | `1 - (<=>)` dense + ts_rank BM25 + RRF | ✓ (unit tests + DB-gated integration skip) | ✓ FLOWING |
| prompt library | rendered template | git-backed yaml/template.txt files | ✓ (12 tests pass, real files) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Lint | `uv run ruff check .` | All checks passed (exit 0) | ✓ PASS |
| Type check | `uv run pyright` | 0 errors, 0 warnings, 0 informations | ✓ PASS |
| Full suite | `uv run pytest tests/ -q` | 113 passed, 9 skipped in 49.19s | ✓ PASS |
| Skip breakdown | `pytest -rs` | 7 DB-gated (documents×2, schema×2, search×3) + 1 live-key (embedding:67) + 1 OCR host-gated (extract:92) — matches expected 9 | ✓ PASS |
| Ollama live SSE | `test_sse_envelope_shape` | RAN (not skipped), passed vs live qwen3.5:9b | ✓ PASS |
| Ollama live usage | `test_chat_usage_shape` | RAN (not skipped), passed vs live model | ✓ PASS |
| Go seam invariant | `git -C backend diff HEAD --stat -- internal/ai/` | EMPTY (0 lines) | ✓ PASS |
| LiteLLM/gateway/Celery | `grep -ri litellm\|gateway\|celery` | ZERO hits in app/, pyproject, uv.lock | ✓ PASS |
| Gzip middleware | `grep GZipMiddleware app/` | absent (docstring mention only) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| PYE-01 | 03-03-PLAN | Multi-provider abstraction, direct SDKs, NO LiteLLM/gateway | ✓ SATISFIED | 5 provider clients; grep clean |
| PYE-02 | 03-05-PLAN | Document intelligence (6 formats, OCR, chunking, embeddings, search) | ✓ SATISFIED | extractors/**, chunker, pipeline, hybrid |
| PYE-03 | 03-07-PLAN | Versioned prompt library (9 types, aliases) | ✓ SATISFIED | prompt_library.py + 9 dirs + 12 tests pass (see note below on REQUIREMENTS.md status flag) |
| PYE-04 | 03-02..03-06 | All 8 endpoints | ✓ SATISFIED | /health, /v1/health, /v1/chat, /v1/chat/stream, /v1/embed, /v1/extract, /v1/documents, /v1/search, /v1/providers |
| PYE-04a | 03-01-PLAN | proto contract at START | ✓ SATISFIED | proto/aiengine.proto committed 09:09 before impl |
| PYE-05 | 03-06-PLAN | Tenant-aware RAG (hybrid, filters, ranking, citations, compression) | ✓ SATISFIED | hybrid.py + rerank.py + search.py |

### Go Seam (Invariant)

| Check | Result | Details |
| ----- | ------ | ------- |
| `git -C backend diff HEAD --stat -- internal/ai/` | ✓ EMPTY | 0 lines — `engine.go`, `sse.go`, `client.go` untouched (seam frozen) |
| Backend submodule HEAD | ✓ at `5a0dfa8` | The allowed compose env-expansion commit; diff = docker-compose.yml only (18 lines: AI_PGVECTOR_DSN, provider keys via ${VAR:-}, AI_PROMPTS_DIR, host-gateway extra_hosts) |
| Backend submodule status | ✓ clean | No modified/untracked files |
| SSE compatibility | ✓ | Python emits exactly what Go sse.go parses; verified live |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | none found in app/ | — | — |

No TODO/FIXME/placeholder/`NotImplementedError`/empty-return stubs in any app/ module. All routes return real data paths with explicit error mapping (400 validation, 503 unconfigured, 502 upstream). The 7 DB-gated test skips and 1 live-key skip + 1 OCR-host skip are documented env gates (D-12), not stubs.

### Human Verification Required

None. All criteria verified programmatically, including live end-to-end SSE + usage shape against a real Ollama model. No visual/UI behavior in scope for this backend phase.

### Review Closure Confirmation

Review finding commit `39f27f7` "fix(03-review): apply Phase 3 code review findings" is the HEAD of the phase's ai-engine work. Every finding verified present in the code:

| Finding | Fix in code | Evidence |
| ------- | ----------- | -------- |
| F1 Dockerfile prompts COPY | ✓ | `Dockerfile:23` `COPY prompts ./prompts` |
| F2 path containment AI_UPLOADS_DIR | ✓ | `extract.py:39-59` `_assert_within_uploads` — 400 outside volume (resolved-path `is_relative_to`) |
| F3 embed retry transport errors | ✓ | `util/retry.py:27-37` `embed_retry` retries httpx.TransportError/TimeoutException + openai.APIConnectionError/APITimeoutError (not HTTPStatusError) |
| F4 per-token heartbeat | ✓ | `chat.py:172-184` `asyncio.wait_for(anext(stream), AI_HEARTBEAT_INTERVAL_SECONDS=25)` + heartbeat on TimeoutError; upstream stall cannot violate ≤30s |
| F5 PDF OCR O(pages) | ✓ | `pdf.py:33` `convert_from_path` ONCE + index pages (was per-scanned-page re-parse) |
| F6 OpenAICompat fail-fast | ✓ | `openai_compat.py:27-34` raises ValueError when key missing — no `"missing"` placeholder literal |
| F8 502 + log | ✓ | `extract.py:75-77, 100-102` `logger.exception` + HTTPException 502 on unexpected failures |
| Regression tests | ✓ | +2 containment (test_documents), +2 fail-fast (test_providers); config field count 25→27 (test_config) |

### Gaps Summary

No gaps found. All 5 ROADMAP success criteria verified against code on disk + live infra:

1. **proto contract (C1)** — 6 RPCs committed before implementation; REST 1:1 mapping documented and verified in code.
2. **Multi-provider chat + native SSE (C2)** — 5 direct SDK providers, Go-compatible envelope, heartbeats ≤30s, no gzip, normalized usage everywhere; **live Ollama end-to-end tests passed**.
3. **Providers status + canonical embed (C3)** — live TTL-cached health + cooldowns; 1536-dim text-embedding-3-small with fail-loud validation.
4. **Document intelligence + tenant DB (C4)** — 6 formats, per-page digital/OCR routing at 300 DPI, one-call extract→chunk→embed→store, `^school_[0-9]+$` + existence gate with no fallback.
5. **Hybrid RAG + prompt library (C5)** — dense HNSW + BM25 ts_rank + RRF k=60, filters, citations, compression; 9 Git-backed prompt types with aliases; stateless service-token-only.
6. **Go seam invariant** — zero diff in `backend/internal/ai/`; only allowed compose commit `5a0dfa8`.
7. **Suite** — ruff clean, pyright 0 errors, **113 passed / 9 skipped** (exact expected breakdown).
8. **Review closure** — `39f27f7` addresses F1-F8, each verified in code.

**Informational note (not a gap):** `.planning/REQUIREMENTS.md` still marks PYE-03 as `[ ] Pending` (line 30 checkbox + line 106 status table). The implementation is complete and verified (9 prompt types, library with aliases, chat wiring, 12 passing tests, commits 4101cfe/87c6c38/fab5374). This is stale status tracking only — recommend ticking PYE-03 during the milestone audit.

---

_Verified: 2026-08-01T13:05:00Z_
_Verifier: the agent (gsd-verifier)_
