---
phase: 03-python-ai-engine
plan: 01
subsystem: ai-engine-contract
tags: [grpc, proto, contract-seam, aiengine, rest-mapping, sse]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Go EngineClient seam (backend/internal/ai/engine/* — frozen shapes this proto mirrors)
  - phase: 02-pgvector-migration
    provides: AI_EMBEDDING_DIM=1536 canon (EmbedResponse.dimension), school_{id}.ai_vectors (IngestDocument/Search targets)
provides:
  - Root proto/aiengine.proto gRPC contract seam (service AiEngine, 6 RPCs) — single source of truth for request/response semantics
  - 03-01-MAPPING.md proving REST↔RPC 1:1 coverage (6 domain RPCs + 2 deliberately excluded ops endpoints)
  - Frozen contract constraints every later Phase 3 plan (03-03..03-06) builds its REST endpoints against
affects: [03-02, 03-03, 03-04, 03-05, 03-06, 03-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contract-seam-first: proto written BEFORE any REST implementation; every endpoint must satisfy proto message semantics 1:1 (D-11, ROADMAP criterion 1)"
    - "SSE envelope frozen in proto as EngineEvent{type, data} bytes — matches Go engine.go:20-23 (D-02)"

key-files:
  created:
    - proto/aiengine.proto
    - .planning/phases/03-python-ai-engine/03-01-MAPPING.md
  modified: []

key-decisions:
  - "Proto lives at repo ROOT (proto/aiengine.proto), sibling of backend/ and ai-engine/ — single source of truth importable by both submodules (D-11)"
  - "Service AiEngine exposes exactly 6 RPCs mapped 1:1 to REST: Chat, ChatStream, Embed, Extract, IngestDocument, Search"
  - "GET /v1/health and GET /v1/providers are deliberately NOT proto RPCs — infrastructure/ops surface, not domain calls"
  - "ChatRequest.Model carries provider:model composite; Usage normalized (provider, model, input/output tokens, cost) on every ChatResponse (D-03, ROADMAP criterion 2)"
  - "IngestDocumentRequest/SearchRequest carry schema_name with ^school_[0-9]+$ + existence validation semantics (D-07/D-09) — no global fallback"
  - "No gRPC runtime, no codegen, zero changes to backend/internal/ai/engine/* in this plan (PYE-04a, T-03-01-02)"

patterns-established:
  - "Contract seam: gRPC-ready proto as single source of truth; v1 transports REST/JSON + SSE; future gRPC swap is drop-in"
  - "EngineEvent SSE envelope: {type: delta|citation|usage|error|done, data: <compact JSON>} with : ping heartbeats ≤30s (D-02)"

requirements-completed: [PYE-04a]

# Metrics
duration: 12min
completed: 2026-08-01
---

# Phase 3 Plan 1: Root gRPC Contract Seam (PYE-04a) Summary

**Root `proto/aiengine.proto` committed at the START of Phase 3 — service `AiEngine` with exactly six RPCs (Chat, ChatStream, Embed, Extract, IngestDocument, Search) mapped 1:1 to the REST endpoints Go calls, defining the frozen contract seam every Phase 3 REST endpoint must satisfy (transport stays REST/JSON + SSE in v1, no gRPC runtime).**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-01T08:00:00Z
- **Completed:** 2026-08-01T08:11:04Z
- **Tasks:** 2 (auto)
- **Files modified:** 1 committed (proto/aiengine.proto); 1 planning artifact (03-01-MAPPING.md)

## Accomplishments

- Created `proto/` at repo root (did not exist) and wrote `proto/aiengine.proto` — byte-exact with the plan's specified content (verified via diff against the plan's code block).
- Declared service `AiEngine` with exactly 6 RPCs: `Chat`, `ChatStream` (server-streaming `EngineEvent`), `Embed`, `Extract`, `IngestDocument`, `Search` — matching ROADMAP criterion 1's list verbatim.
- Defined all 16 messages mirroring the frozen Go seam semantics exactly: `ChatMessage`/`ChatRequest` (provider:model composite, D-03), `Usage` (provider/model/input_tokens/output_tokens/cost), `ChatResponse` (message + usage on every response), `EngineEvent` (type discriminator delta|citation|usage|error|done, D-02), `EmbedRequest/Embedding/EmbedResponse` (1536-dim canon, D-05), `ExtractRequest/ExtractResponse` (document_path, pages/ocr_pages/chars), `IngestDocumentRequest/Response` (document_path + schema_name validation, D-07/D-09), `SearchRequest/SearchResult/SearchResponse` (hybrid dense+BM25 RRF k=60, citations, top_k cap).
- Validated the proto: `protoc` NOT installed on host and no pure-python protobuf available → plan-authorized structural grep validation passed (proto3 syntax, package aiengine.v1, all 6 `rpc X(` names, `grep -c "rpc "` == 6, 16 messages).
- Wrote `03-01-MAPPING.md` proving REST↔RPC 1:1 coverage for all 8 REST endpoints (6 domain RPCs + 2 ops endpoints deliberately out of proto scope) and recording the D-02 EngineEvent SSE wire contract for plan 03-03.
- Committed the contract to the ROOT repo as required (root is the cross-submodule public contract, D-11).
- Frozen Go seam untouched: `backend/internal/ai/engine/*` has zero changes (T-03-01-02).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write proto/aiengine.proto with the six-method AiEngine service** - `9501c51` (feat)
2. **Task 2: Prove proto validity + write the REST↔RPC mapping table** - (no root-repo files; mapping doc is a gitignored `.planning/` artifact, `commit_docs: false`)

**Plan metadata:** final docs commit skipped by tooling (`skipped_commit_docs_false` — project config `.planning/` gitignored + `commit_docs: false`; `.planning/` docs remain local-only)

## Files Created/Modified

- `proto/aiengine.proto` - The gRPC contract seam: service AiEngine with 6 RPCs + 16 messages (112 lines). Committed to root repo.
- `.planning/phases/03-python-ai-engine/03-01-MAPPING.md` - REST↔RPC 1:1 coverage table (8 endpoints), ops-endpoint exclusion rationale, D-02 SSE wire contract, validation record. Planning artifact (local only).

## Decisions Made

- Followed plan exactly as specified (proto content byte-exact, D-11 location at root, no gRPC runtime/codegen, no Go seam changes). No new decisions beyond the locked D-02/D-03/D-05/D-07/D-09/D-11 decisions the plan encodes.

## Deviations from Plan

**Total deviations:** 0 auto-fixed (no bugs, no missing functionality, no blocking issues — contract-only plan executed exactly as written)

**Environment notes (not deviations):**

1. **protoc not installed** — the plan's `<verify>` explicitly provides the fallback: structural grep validation when protoc is absent. All structural asserts passed. No pure-python protobuf (`google.protobuf`/`grpc_tools`) was available either, so full descriptor build is deferred to the future gRPC-runtime step (accepted risk, T-03-01-03).
2. **Docs commit skipped by tooling** — `commit_docs: false` + `.planning/` gitignored → `gsd-tools commit` returned `skipped_commit_docs_false` for the mapping doc. Expected per project config; the committed deliverable is `proto/aiengine.proto` (the ROADMAP criterion 1 artifact).
3. **Parallel wave-1 executor interleaving** — commits `adaf597`/`e4b6bda` (plan 03-02 work) were made by the concurrent wave-1 executor on the same branch; history is linear and conflict-free with my `9501c51`. Pre-existing/in-flight `ai-engine/` changes (config.py, test_config.py, providers/) belong to 03-02 — untouched, out of scope.

## Issues Encountered

None. Validation fell back exactly per the plan's documented protoc-absent path; verifications (`grep -c "rpc "` == 6, `service AiEngine`, proto3 syntax, mapping file present) all passed first try.

## Known Stubs

None — `proto/aiengine.proto` is a complete contract definition with all 16 messages fully specified; no placeholder fields, no mock data, no TODO markers. It is intentionally not executable code (contract seam only, PYE-04a).

## Self-Check: PASSED

- FOUND: proto/aiengine.proto (exists, committed 9501c51)
- FOUND: commit 9501c51 (feat(03-01): add root proto/aiengine.proto gRPC contract seam)
- FOUND: .planning/phases/03-python-ai-engine/03-01-MAPPING.md
- FOUND: `grep -c "rpc "` == 6, `service AiEngine` present, proto3 syntax, 16 messages
- FOUND: backend/internal/ai/engine/* unchanged (T-03-01-02 satisfied)
