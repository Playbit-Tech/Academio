# Feature Research

**Domain:** AI Platform for a multi-tenant school ERP (document intelligence/RAG, multi-provider LLM routing, education AI features, SSE streaming, usage quotas/audit)
**Researched:** 2026-07-31
**Confidence:** HIGH (core pipeline/gateway/streaming patterns — multiple 2026 sources agree); MEDIUM (Nigerian edtech competitive claims — vendor marketing sites, unverified)

## Executive Summary

Production AI features in 2026 have converged on a well-documented set of patterns. **RAG is a multi-stage pipeline, not a single similarity query**: offline indexing (parse → chunk → embed → upsert) strictly separated from the online query path (hybrid retrieve → rerank → generate with citations → log trace). 72% of enterprises run RAG in production (Q1 2026), and the quality levers are now table stakes: structure-aware chunking, hybrid dense+BM25 retrieval fused with Reciprocal Rank Fusion, a cross-encoder reranker, metadata filters, and an evaluation harness with faithfulness/context-precision metrics. "Skipping the reranker is the most expensive shortcut" and "you cannot ship production RAG without an evaluation harness" are consensus 2026 positions.

For multi-provider LLM routing, the industry has standardized on the gateway pattern (LiteLLM/OpenRouter): unified OpenAI-compatible API, fallback chains with cooldowns, retries with backoff, per-request cost/token accounting, and rate-limit awareness. The guidance is explicit that you should NOT build a full gateway when your orchestration layer already owns routing — Academio's Go `ModelRouter` already does failover + circuit breakers, so Python should use direct provider SDKs (matches STACK.md). Mid-stream provider failover is deliberately NOT transparent: a good gateway is "honest about this boundary."

Education AI (2026) is a crowded, fast-moving market — MagicSchool (80+ purpose-built teacher tools), Khanmigo, Diffit, Eduaide and 60+ others. **The teacher-side table stakes are: report card comment generation, lesson-plan generation, quiz/question generation, rubrics, and parent-communication drafts — all human-in-the-loop ("AI drafts, you review and finalize") with curriculum alignment and PII guardrails.** The Nigerian market already has AI-native competitors (EDVES, Eedu, Oponeko, Provsy, Acceede, Mariobee) all competing on WAEC/NECO/JAMB/UTME alignment, NERDC curriculum grounding, report-card AI, and offline/low-bandwidth resilience — this raises the floor for what Nigerian schools expect.

SSE streaming has a mature operational playbook: correct headers, 10–15s heartbeats, typed events (delta/done/error), client-disconnect → upstream abort (stop paying for tokens nobody reads), three timeouts (first-byte, inter-token, total), and proxy-buffering-off. Resumable streams are a differentiator only where mobile networks dominate; for chat, "restart is simpler and good enough." AI usage quotas/audit have likewise standardized: audit EVERY request with per-tenant attribution, enforce per-tenant request+token quotas and rate limits, track cost per model (not just tokens), and treat unbounded consumption as an OWASP-ranked security control — "attackers don't always come for your data, sometimes they just come for your compute bill."

**The core-value sentence for the roadmap:** the differentiator is *grounded, tenant-safe document intelligence* — Nigerian school documents (policies, handbooks, lesson notes, past WAEC/NECO papers) searchable and quotable through the AI assistant — not the breadth of the provider catalog or the number of prompt templates.

## Feature Landscape

### Table Stakes (Users Expect These)

#### Document Intelligence / RAG Pipeline

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Async document ingestion** (upload → queue → extract → chunk → embed → indexed + notify) | Synchronous processing blocks requests; docs take minutes. "Everything must be asynchronous" is both user expectation and 2026 architecture consensus (offline indexing path vs online query path). | HIGH | Spec PIP-01 is correct: Go validates → saves → asynq → Go worker → Python `/v1/extract` → pgvector → event → notify. Reuse `ai:scoring` handler pattern. |
| **Multi-format parsing with type routing** (digital PDF / scanned PDF / DOCX / PPTX / TXT / CSV / image) | Documents come in every format; a single parser fails. 2026 pattern: native text → fast parser (PyMuPDF/Docling), scanned → OCR, complex → VLM fallback. | MEDIUM | Docling (STACK.md) covers PDF/DOCX/PPTX/HTML. Distinguish native vs scanned PDF up front (text-length heuristic: <100 chars → scanned). |
| **OCR for images + scanned docs** (Tesseract per spec) | Exam papers, handwritten notes, photographed pages are common in Nigerian schools (teachers photograph marked work). | MEDIUM | pytesseract is the spec choice; PaddleOCR is significantly more accurate on messy layouts/handwriting and has built-in layout+table structure — flag as upgrade path (see Differentiators). Tesseract needs `tesseract-ocr-eng` system package. |
| **Structure-aware chunking** (heading/section-aware, not fixed-size only) | "Chunking determines retrieval quality more than any other preprocessing step." Fixed-size cuts mid-sentence, separates questions from answers, merges unrelated topics. | MEDIUM | Docling `HybridChunker` (tokenizer-aligned, heading metadata) — already chosen in STACK.md. 256–512 token chunks for factual Q&A (exam questions), 512–1024 for narrative (policies/handbooks). Store chunk metadata (heading, page, section) for citation tracing. |
| **Metadata on every chunk** (tenant_id, school_id, module, document_type, document_id, uploaded_by, visibility, language, academic_calendar_id, curriculum_id, created_at) | Enables filtered retrieval + tenant isolation + document-scoped queries. "No vector should ever be shared across tenants." | MEDIUM | Spec PGV-04 defines these columns; they must ALSO live in Python's chunk metadata when embedding (not just the SQL table). |
| **Hybrid retrieval: dense + keyword (BM25) with RRF fusion** | Pure vector search misses exact terms (student names, subject codes like "CHEM 2", WAEC/NECO acronyms). Hybrid = ~17% recall gain for <6ms added latency. | MEDIUM | pgvector has NO built-in sparse index. Use Postgres full-text search (tsvector + GIN) alongside pgvector, fuse with Reciprocal Rank Fusion (k=60). Keeps infra simple — no OpenSearch. Spec PYE-05 lists hybrid search; this is the implementation. |
| **Re-ranking (cross-encoder, top-50 → top-5/8)** | "The single highest-ROI quality improvement after basic retrieval"; 10–30% precision lift for <100ms. | MEDIUM | Need a reranker: Cohere Rerank (API) or self-hosted BGE-reranker-v2-m3. NOT in STACK.md — flag as a stack gap. Only pay the 100–300ms when precision matters; always on for document Q&A. |
| **Citations in every RAG answer** (chunk IDs / source doc + page) | Users must be able to verify claims; "answer only from provided context, cite sources, say 'I don't have enough information' otherwise" is the 2026 default prompt contract. | LOW | Spec PYE-05 requires citations. Frontend must render source chips linking back to the document. |
| **Document status + failure visibility** (uploaded → extracting → chunking → embedding → indexed → failed, with retry) | Users need to know where their upload is; failed docs must be retryable, not silently dropped. | MEDIUM | Spec PIP-02 (`GET /api/v2/ai/documents/:id/status`). Add dead-letter queue + retry for unreadable docs; surface failure reasons to the UI. |
| **Same embedding model for indexing and querying** | Mixing models produces meaningless similarity; also a hard technical constraint (VECTOR(n) dim locked at DDL — Go and Python MUST share one embedding model; 1536-dim default per STACK.md). | LOW | Config-driven single embedding model. Treat embedding-model changes as index migrations (re-embed job with `model_version` metadata). |
| **RAG evaluation harness** (golden set of 50–100 QA pairs; faithfulness ≥0.85, context precision ≥0.75, context recall ≥0.8, answer relevancy ≥0.8) | "You cannot ship production RAG without evaluation infrastructure" — 2026 consensus. Without it, quality drift is discovered by users. | MEDIUM | RAGAS/DeepEval metrics; run on every chunking/embedding/prompt change (CI gate). Spec TES-01 (RAG-accuracy tests) is the seed; needs a golden dataset built from real school queries. |
| **Retrieval observability** (log query, filters applied, retrieved chunk IDs in rank order, reranker score, generation latency) | When an answer is wrong you must be able to prove whether retrieval failed or generation failed — separates the two failure modes. | MEDIUM | Spec OBS-01. Trace per stage; alert on reranker top-1 score dropping (retrieval quality degradation). |

#### Multi-Provider LLM Routing

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Unified provider abstraction** (normalized request/response, OpenAI-compatible surface) | One endpoint, many providers; zero migration cost between them. | MEDIUM | Spec PYE-01. In Go: wire Python providers into existing `ModelRouter` as `providerEntry`s (INT-04). In Python: `openai` SDK covers Azure/DeepSeek/OpenRouter/Ollama via `base_url`; `anthropic` SDK for Claude (STACK.md). |
| **Fallback chains + cooldowns** (provider down/429 → next provider; cooldown ~60s) | Provider outages are a fact of life (the "Fable 5 test": could you survive a provider cutting API access Friday 5pm?); 429s must deprioritize, not kill traffic. | MEDIUM | Go already has circuit breakers (5 fails/30s) — keep. Add provider-level cooldown on 429/503. Test failover in staging before production. |
| **Retries with exponential backoff + timeouts** (first-byte, inter-token, total) | Rate limits and transient errors are normal; three timeouts catch three different failure modes. | MEDIUM | Spec INT-03 (retries/circuit breakers on Python calls). First-byte 30s, inter-token 15s, total 180s. |
| **Per-request token + cost accounting** (model, prompt/completion tokens, cost, latency, cache hit) | Without per-request accounting you cannot do quotas, showback, or answer "why is the bill double last month". | MEDIUM | Spec OBS-01 + SEC-01 (audit every AI request). Write usage rows (aggregated) — see Quotas section. Existing `cost.go` in Go AI layer is the pattern. |
| **Provider status endpoint** (`GET /api/v2/ai/providers`) | Operators/schools need to see provider health; planned INT-02. | LOW | Circuit-breaker state + health check per provider; drives UI indicator. |
| **Streaming support at provider layer** (native SSE from all major providers) | All major providers stream via SSE; streaming is the default UX. | LOW | Existing Go `GenerateTextStream` + FastAPI `EventSourceResponse` (STACK.md). See SSE section. |
| **Rate limiting on AI endpoints** (per school/user) | Unbounded consumption is an OWASP top-ten LLM risk; runaway loops drain budgets. | MEDIUM | Spec SEC-01 + INT-03. Distinct from quotas: rate = requests/time; quota = tokens/period (see Quotas). |

#### Education AI Features

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Report comment generation** (from student scores/attendance/behaviour, bulk-batch, teacher reviews/edits) | THE #1 education AI use case — 5+ dedicated tools (MagicSchool, Khanmigo, Varsity, Knowt, CK-12) + 2026 "Google has flagged this as an unmet query". Nigerian competitors (Oponeko "AI Report Writer", EduTek "AI-Powered Report Card") all ship it. Teachers save 6h → 90min at term end. | MEDIUM | Spec PYE-03 (report comments prompt). **Differentiator within table stakes:** ground comments in actual student data via RAG/repository access (scores, CA totals, attendance %, behaviour records), not free-text prompts. **Bulk generation** (28–90 students) is the expected workflow — batch endpoint + collect-and-report errors (AGENTS.md Rule B9). Human review before publish is non-negotiable. |
| **Lesson plan generation** (curriculum-aligned, differentiated by level, with objectives/materials/activities) | MagicSchool/Diffit/Eduaide/Lessonsquill market this relentlessly; "standards-aligned, differentiated, customizable" is the floor. | MEDIUM | Spec PYE-03 (lesson plans). **Nigerian grounding is the moat:** align to NERDC scheme-of-work (JSS1–SS3, primary levels), not Common Core — this is what EDVES/Oponeko compete on. |
| **Question/quiz generation** (from topic, standard, or uploaded document) | Quizizz/Wayground, Diffit, Eduaide, Provsy all generate question sets from any doc in seconds; students expect practice materials. | MEDIUM | **Exam-paper analysis overlaps this**: past WAEC/NECO/JAMB questions are the highest-value corpus in the Nigerian market. Generate CBT-style questions + mark schemes. |
| **Rubric generation** | Part of every teacher-toolkit (MagicSchool rubric builder, Eduaide 75+ generators). Low effort, high perceived value. | LOW | Straightforward template feature. |
| **Parent-communication drafts** (letters, emails, WhatsApp-ready messages) | "Draft professional, empathetic emails — you review and send" saves teachers ~3h/week (MagicSchool's most-cited win). Parent letters are in spec PYE-03. | LOW | Nigerian schools communicate via WhatsApp heavily — output should be copy-paste-ready short messages + formal letter variants. |
| **Curriculum alignment + syllabus awareness** (NERDC / WAEC / NECO / BECE / JAMB/UTME / IGCSE) | Nigerian AI-native competitors (EDVES, Schoogle, Mariobee PrepBee, Provsy, Acceede) ALL sell on national-exam alignment. A lesson plan that doesn't name the syllabus won't clear a department head. | MEDIUM | Requires a curriculum/syllabus knowledge layer — seed via RAG over NERDC syllabus docs + past questions. This is the "education-domain RAG corpus" that differentiates from a generic chatbot. |
| **PII/data-protection guardrails** (no identifiable student data to unapproved providers; no training on student data; school-admin consent) | US FERPA warnings are loud (2025–2026 press); Nigerian equivalent: Nigeria Data Protection Act 2023. Schools are liability-averse about identifiable student data. | MEDIUM | Spec SEC-01 (PII masking). Policy: students identified by anonymized refs in provider payloads where possible; provider allowlist per school; BAA-equivalent posture documentation. |

#### SSE Streaming Chat

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Token streaming with correct SSE framing** (`event: delta` / `event: done` / `event: error`, `[DONE]` sentinel) | Streaming is the default UX for LLM chat (30s response streamed feels faster than 5s response delivered whole). | LOW | Spec INT-01 (`POST /api/v2/ai/chat/stream`) + PYE-04 (`/v1/chat/stream`). FastAPI native `EventSourceResponse`; typed events — never overload `data` with control signals. |
| **Heartbeat comments every 10–15s** (`: ping`) | Proxies/load balancers kill idle connections after 60–120s; long prefill gaps (30s+ "thinking") need keepalive. | LOW | STACK.md already specifies this. |
| **Client-disconnect → upstream abort** (stop provider generation when client leaves) | Otherwise you pay for tokens nobody reads; "the single highest-leverage cost optimization in streaming LLM services". | MEDIUM | FastAPI `await request.is_disconnected()` per token + `aclose()` upstream generator. In Go: abort on client close. |
| **Three timeouts** (first-byte 30s, inter-token 15s, total 180s) | Each catches a different failure; hung streams shouldn't pile up. | LOW | Race timeouts against the stream; on timeout abort upstream + send typed error. |
| **Correct headers + proxy-buffering-off** (`text/event-stream`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`) | nginx/CDN buffering silently destroys streaming; the #1 "why doesn't streaming work" cause. | LOW | Applies at the Vite proxy (dev) and any prod reverse proxy between Go↔Python and client↔Go. |
| **Partial-response honesty** (on mid-stream error: keep partial, mark incomplete, offer retry) | Users watched tokens appear; discarding them is bad UX. Don't auto-retry transparently. | LOW | `event: error` with `{partial: true}`; frontend shows "incomplete" badge + retry button. |
| **POST + fetch ReadableStream client** (not `EventSource`) | `EventSource` is GET-only and can't set Authorization headers — both fatal for authenticated chat. | LOW | Standard 2026 pattern: `fetch` POST, read `response.body`, parse SSE frames manually. |

#### AI Usage Quotas & Audit

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Audit every AI request** (school, user, action, provider, model, prompt-hash, tokens, cost, latency, cache hit, request ID, timestamp) | "Audit every AI request" is in the spec (SEC-01); also an AGENTS.md audit rule (B11) applied to AI. Compliance + debugging + quota accuracy all depend on it. | MEDIUM | Append-only `ai_usage_log` (shared schema, school-scoped). Write via asynq batch to avoid hot-path DB writes; keep `X-Request-ID` correlation across Go→Python (OBS-01). |
| **Per-school usage metrics** (tokens + estimated cost, daily/monthly, per model, per feature) | Schools/platform ops need visibility; "token metering as governance that produces a bill" — billing is a reporting layer on trusted controls. | MEDIUM | Aggregate from audit log; Prometheus + Grafana (OBS-01) for live; periodic rollups for long-term. |
| **Per-school request quotas + rate limits** (e.g., N requests/hour, M tokens/period) | One noisy school must not starve others or blow the shared provider budget; "one tenant's burst stays clear of another's production traffic". | MEDIUM | Spec INT-03. Enforce in Go AI Orchestrator (single choke point — all AI calls flow through Go). Pre-request check + Redis counters; 429 with clear error. |
| **Per-tenant audit queries** (school admin can see its own usage) | Self-service visibility builds trust and pre-empts billing disputes. | LOW | Reuse service-layer pagination (Rule B10). |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Document-grounded AI assistant** (school policies/handbooks/lesson notes searchable via RAG with citations) | Competitors (MagicSchool et al.) are generic SaaS; no one indexes the school's OWN documents into an assistant. This is the Core Value in PROJECT.md. | HIGH | Requires the full RAG stack (above). Surface as "ask your school's documents" with source chips. |
| **Exam paper intelligence** (upload past WAEC/NECO/JAMB papers → structured question bank + mark scheme + topic-tagged retrieval) | Nigerian market's hottest category; EDVES/Provsy/Acceede sell 15,000+ question banks. Uploading YOUR school's papers and getting searchable, topic-tagged questions is a step beyond generic generation. | HIGH | Heavy table/structure extraction (exam papers are dense tables/lists). Needs PP-Structure-class table handling or VLM fallback. High value, high cost — P3. |
| **Behaviour summary generation** (from incident/praise records + attendance, per student/class) | Eedu ("AI-powered behavioural reports — per student, per class, per school — auto-generated") and EduTek compete on character/behaviour tracking; parents in Nigerian schools value conduct reports (report cards carry "attitude to work/conduct" grades). | MEDIUM | Spec PYE-03 (behaviour summary). Ground in repository data, not free-text. Pair with deficit-filtered language guardrails. |
| **At-risk student flagging** (grades + attendance + behaviour patterns → early-warning list) | "AI surfaces patterns in incidents and praise; identify support cases automatically" (Eedu). Directly extends existing Go `risk_analyzer` agent — differentiate by grounding in RAG'd policy context. | MEDIUM | Existing Go agent + new data grounding. Careful: flag for staff, never auto-label for parents/students. |
| **Versioned prompt library with evaluation** (prompts as versioned artifacts with golden-set regression gates) | "Teams that treat prompts as config ship prompt changes 5–10x faster with fewer regressions"; prompt changes are the #1 cause of silent LLM regressions. | MEDIUM | Spec PYE-03 (versioned prompts). Git-backed YAML registry + eval harness (PromptForge/MLflow-registry pattern) + alias promotion (dev → staging → prod). Skip the SaaS; DIY covers 80% of value. |
| **Confidence-gated document processing** (OCR/extraction confidence score → auto-index vs human-review queue) | Instead of silently indexing garbage text, route low-confidence extractions (<0.7) to a review queue; auto-approve high (>0.9). | MEDIUM | The 2026 IDP pattern. Differentiator because it protects retrieval quality from bad OCR — which is the silent killer of document RAG. |
| **Cross-lingual support** (English + Nigerian languages, code-switching awareness) | Nigerian classrooms mix English with Yoruba/Hausa/Igbo/Pidgin; report comments and translations to local languages are genuinely valued. | MEDIUM | Spec PYE-03 (translation). Embedding model must handle the mix; `text-embedding-3-*` is weak on Nigerian languages — flag for evaluation against multilingual embedders (Cohere embed-v3 / BGE-m3) before locking the shared embedding model. |
| **Model-tier routing per school plan** (free-tier schools → cheap models/allowlist; premium schools → frontier models) | Monetizes the AI feature: plan-based model allowlists are a config change, not a code change (Bifrost pattern). | LOW | Model allowlist per school tier in Go Orchestrator; drives provider selection. |
| **Semantic caching** (embedding-similarity cache in Redis; cache-hit cost ≈ 0) | Report comments for similar students, repeated lesson-plan prompts — many schools will re-prompt; cache hits cut cost ~30–50%. | MEDIUM | Spec INT-03 (Redis prompt/response caching). Cache only for idempotent generations (never streaming), with TTL + per-tenant key scope; tag usage rows with cache_hit. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full LLM gateway product (LiteLLM-style) in Python** | "One gateway for 100+ providers" sounds efficient; the AI-platform spec lists 7 providers. | Duplicates Go ModelRouter's existing failover/circuit-breaker role; adds ~7.5ms/call overhead; every provider adds API drift, pricing-table and test burden. | Direct SDKs (anthropic + openai, with openai covering Azure/DeepSeek/OpenRouter/Ollama) — STACK.md locked. Revisit only if 100+ provider breadth becomes a product requirement. |
| **Transparent mid-stream provider failover** | "Failover everywhere" seems like reliability. | Providers aren't interchangeable mid-stream: partial tokens are sent, switching silently corrupts the response; "a good gateway is honest about this boundary." | Fail fast (<2s detection), cancel, restart on fallback with a visible "switched to backup model" UI indicator. |
| **Synchronous document processing** | Simpler code, immediate feedback. | Docs take minutes; request times out; no queue semantics; can't handle batch. "Coupling the paths is the most common architectural mistake." | Async pipeline (asynq) + status endpoint + notification (PIP-01/02). |
| **Fixed-size-only chunking** | It's the default in every tutorial. | Cuts sentences/tables mid-thought; retrieval quality is bounded by chunk quality — "80% of RAG failures trace to ingestion/chunking." | Structure-aware chunking (Docling HybridChunker) with size tiering by document type. |
| **RAG on every chat query** | "More context = better answers." | Only 20–40% of queries need retrieval ("What is the capital of France?"); forced retrieval adds latency + noise, and retrieval is the #1 hallucination vector. | Agent-aware retrieval: the assistant decides when to call the search tool (existing Go agent tool pattern already supports this). |
| **Silent fallback to LLM-without-context when retrieval fails** | "Always answer something." | Produces ungrounded answers that look authoritative — the worst failure mode for a school assistant (parents/teachers get confident wrong policy answers). | Fail closed: "I couldn't find this in your school's documents" + suggest uploading. |
| **AI-graded final scores** | "Grade 100 essays in minutes" is seductive. | Scores without teacher confirmation create integrity/liability issues; Gradescope's lesson is "you grade one, apply to similar, confirm." | AI drafts rubric-aligned feedback/comments; teacher confirms final scores (human-in-the-loop). Keep AI scoring strictly assistive in v1. |
| **AI detection (GPTZero/Turnitin-style)** | "Students will cheat with AI." | Documented false-positive problem; "AI detectors produce false positives and should open a conversation, not close a case"; detection is a separate, contested product category. | Out of scope for the AI platform milestone; if demanded, design assessment-integrity workflows (in-class writing, oral defense) instead. |
| **Student-facing tutor without guardrails** | "24/7 curriculum-aligned tutor" is the most-marketed student feature (Saka AI, Khanmigo). | Khanmigo's own founder called student-tutor results "a non-event for most learners"; age-appropriate guardrails, Socratic-not-answer-giving behavior, monitoring and moderation are a whole product of their own. | Ship the teacher/admin/parent side first (report comments, lesson plans, doc Q&A). Student-facing chat is a later, separately-designed milestone with guardrails from day one. |
| **Unbounded consumer-grade model access** (any provider, any model, no quotas) | "Power users want the best model." | OWASP ranks unbounded consumption as an LLM top-ten risk; a single school's runaway batch job can exhaust the shared provider budget and block every tenant. | Per-school quotas + rate limits + model allowlists; generous defaults, hard ceilings. |
| **Durable resumable streams (ring buffers, Last-Event-ID replay, multi-device fan-out)** | "Mobile networks drop connections; users shouldn't lose work." | One team reported weeks on session management; for chat UX, restart is simpler and good enough; cost only materializes on long agent runs. | Standard SSE + abort-on-disconnect + partial-response marking; let the user retry. Revisit only if agent runs routinely exceed minutes. |
| **Building a billing/invoicing platform** | Quotas suggest billing revenue. | Billing (invoices, payment collection, dunning) is a separate regulated product; "bolting on a full invoice platform first" is the classic overbuild. | Meter + audit + quotas now (governance that produces a bill); integrate Stripe/Metronome-style billing later when there's a pricing model. |
| **Handwriting recognition** (teachers photograph hand-marked answer sheets) | Real Nigerian workflow: scans/photos of handwritten work. | PaddleOCR handwriting accuracy is 80–90% on ideal inputs; Nigerian handwriting + pencil + phone photos is far below that; garbage text poisons retrieval. | OCR printed text only in v1; confidence-gate everything; route low-confidence docs to review; treat handwriting as a future dedicated project. |
| **AI proctoring / exam surveillance** | Competitors (Eedu) market AI-proctored CBT. | Privacy concerns with minors + biometrics; heavy legal/ethical surface; distracts from the core doc-intelligence value. | Existing Go `proctoring_analyzer` agent covers basic signals; no new camera/mic-based surveillance in this milestone. |

## Feature Dependencies

```
Document pipeline (upload→extract→chunk→embed→search)
    ├──requires──> Multi-format parsing + OCR routing
    ├──requires──> Structure-aware chunking (HybridChunker)
    ├──requires──> Single shared embedding model (1536-dim, config-locked with Go)
    ├──requires──> pgvector schema + HNSW index (PGV-01..04)
    └──requires──> Async queue (asynq `ai:doc-ingest` + Go worker)

Hybrid search (BM25 + dense + RRF)
    ├──requires──> pgvector (dense) + Postgres FTS tsvector/GIN (sparse)
    └──enhances──> Document pipeline (retrieval quality)

Re-ranking
    └──requires──> Hybrid search (reranks top-50 of a retrieval result)
    └──enhances──> RAG answers (10–30% precision lift)

Citations
    └──requires──> Chunk metadata (heading/page/doc_id) + document store
    └──enhances──> RAG answers (verifiability)

RAG evaluation harness (golden set + RAGAS/DeepEval)
    └──requires──> Working document pipeline (you eval what you ingest)
    └──gates──> Prompt library changes, chunking changes, embedding model changes

Report comment generation (grounded)
    ├──requires──> Prompt library (versioned report-comments template)
    ├──requires──> Student data access (scores/CA/attendance/behaviour) via Go service layer
    └──enhances──> Education AI value (grounded ≠ free-text generation)

Education feature set (lesson plans, exam questions, behaviour summaries)
    ├──requires──> Prompt library versioning
    ├──requires──> Curriculum grounding corpus (NERDC syllabus docs via RAG)
    └──conflicts──> Student-facing tutor (different product surface + guardrails; defer)

SSE streaming chat
    ├──requires──> Provider streaming support (Go GenerateTextStream + Python EventSourceResponse)
    ├──requires──> Proxy buffering disabled (Vite proxy + any reverse proxy)
    └──enhances──> All chat features (perceived latency)

Quotas/audit
    ├──requires──> Audit event emission (per-request usage rows: tokens, cost, model, school, user)
    ├──requires──> Rate limiter + quota counters (Redis) in Go AI Orchestrator (single choke point)
    └──enhances──> Multi-provider routing (budget-aware routing / model downgrade on quota pressure)

Multi-provider routing
    ├──requires──> Unified provider abstraction (PYE-01) + ModelRouter wiring (INT-04)
    └──enhances──> Quotas (per-provider budget enforcement), cost tracking
```

### Dependency Notes

- **Document pipeline is the foundation** — every RAG-dependent differentiator (doc-grounded assistant, exam paper intelligence, curriculum grounding, evaluation) builds on it. It must come first in sequencing.
- **Single embedding model is a hard dependency, not a preference**: `VECTOR(n)` dimension is locked at DDL and Go+Python write the same `ai_vectors` table. Picking/verifying the multilingual embedding model must happen BEFORE the pgvector migration ships (PGV-01..06), or a later model change means re-embedding the whole corpus.
- **Evaluation harness gates everything**: prompt library changes, chunking changes, and embedding changes are all silent-regression risks without a golden set. Build a small golden set (50–100 school-realistic QA pairs) in the same milestone as the document pipeline, not after.
- **Quotas/audit and multi-provider routing are mutually reinforcing but independently shippable**: audit rows power quota accounting; budget-aware routing (downgrade_model) is an enhancement on top of both.
- **Hybrid search's BM25 half is a stack gap**: pgvector alone is dense-only. Postgres full-text search keeps the "reduce infrastructure complexity" promise (no OpenSearch/Qdrant-style second system). Flag for ARCHITECTURE.md.
- **Re-ranking is a stack gap**: STACK.md does not pick a reranker. Cohere Rerank (API, ~100ms) or self-hosted BGE-reranker-v2-m3 (needs torch — already present via Docling) both work.
- **Reranker + citation + eval all enhance RAG quality but don't conflict** — the pipeline stages are additive in 2026's standard order: chunk → embed → hybrid retrieve → rerank → generate with citations → evaluate.

## MVP Definition

### Launch With (v1) — the "document intelligence that works" milestone

- [ ] **Async document pipeline** (PIP-01/02): upload → validate → save → asynq → Python extract → chunk → embed → pgvector → event → notify; status endpoint + failure/retry handling — *the Core Value; nothing else matters without it*
- [ ] **Multi-format parsing + OCR routing** (PYE-02): digital PDF (PyMuPDF/Docling), scanned PDF + images (Tesseract), DOCX, PPTX, TXT, CSV — with confidence-gated review for low-confidence OCR
- [ ] **Structure-aware chunking** (Docling HybridChunker, heading-aware, metadata per chunk)
- [ ] **Hybrid search (dense + Postgres FTS + RRF) + metadata filtering** (PYE-05 subset) — tenant isolation is a security control, not a feature
- [ ] **Citations in answers** — source doc + page/chunk references rendered in the assistant
- [ ] **Small RAG evaluation harness** — golden set (50–100 QA pairs), faithfulness + context precision gates in CI (TES-01 seed)
- [ ] **Versioned prompt library** (PYE-03 subset): report comments, lesson plans, parent letters — Git-backed YAML + alias resolution (dev/staging/production), *without* full eval-gated promotion yet (add in v1.x)
- [ ] **Report comment generation, grounded in student data, bulk + human-review** — the single highest-value education feature; teacher-facing
- [ ] **SSE streaming chat** (INT-01 + PYE-04): correct framing, heartbeats, abort-on-disconnect, three timeouts, partial-response marking
- [ ] **Per-school usage audit + quotas** (INT-03 subset): append-only usage log, per-school request rate limit + daily token quota with clear 429 messages
- [ ] **Multi-provider abstraction with fallback chains** (PYE-01 + INT-04): Anthropic/DeepSeek/OpenRouter/Azure/Ollama behind the existing ModelRouter; cooldowns + retries

### Add After Validation (v1.x)

- [ ] **Re-ranking (cross-encoder)** — once basic retrieval is proven, this is the highest-ROI quality addition; gate on eval-harness scores
- [ ] **Eval-gated prompt promotion + A/B serving** — prompt changes ship 5–10x faster with fewer regressions once the harness exists
- [ ] **Semantic caching** — cache-hit cost ≈ 0; add when token spend is observable (post-quotas)
- [ ] **Exam paper intelligence** (structured question bank from past WAEC/NECO papers) — requires table extraction maturity; the biggest Nigerian-market differentiator after doc-grounded chat
- [ ] **Behaviour summaries + at-risk flags** grounded in repository data — extends existing Go agents; requires behaviour/incident data quality
- [ ] **Model-tier routing per school plan** — monetization lever; requires quota + plan model
- [ ] **Curriculum grounding corpus** (NERDC syllabus + past questions indexed as RAG collections) — makes lesson plans/quiz generation curriculum-true

### Future Consideration (v2+)

- [ ] **Student-facing tutor** — separate product surface; needs guardrails, moderation, age-appropriate design; evidence (Khanmigo) says impact is modest — do not rush
- [ ] **Cross-lingual generation beyond English + common Nigerian languages** — depends on embedding/LLM multilingual evaluation
- [ ] **Resumable streams / multi-device fan-out** — only if long-running agent tasks become a product reality
- [ ] **Billing integration (Stripe/Metronome)** — only once pricing exists; meter and audit already in place
- [ ] **Handwriting recognition** — separate dedicated project with its own eval bar; don't pollute retrieval with garbage text
- [ ] **AI proctoring / surveillance features** — privacy/ethics surface with minors; deliberately deferred

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Async document pipeline (ingest → index → notify) | HIGH | HIGH | P1 |
| Multi-format parsing + OCR routing | HIGH | MEDIUM | P1 |
| Structure-aware chunking | HIGH | MEDIUM | P1 |
| Hybrid search + metadata filtering (tenant-safe) | HIGH | MEDIUM | P1 |
| Citations in RAG answers | HIGH | LOW | P1 |
| RAG evaluation harness (golden set + metrics) | MEDIUM (ops) | MEDIUM | P1 |
| Versioned prompt library (Git-backed, aliases) | HIGH | MEDIUM | P1 |
| Report comment generation (grounded, bulk, review) | HIGH | MEDIUM | P1 |
| SSE streaming chat (framing/heartbeat/abort/timeouts) | HIGH | MEDIUM | P1 |
| Usage audit log (per-request, append-only) | HIGH (ops/security) | MEDIUM | P1 |
| Per-school quotas + rate limits | HIGH (ops/security) | MEDIUM | P1 |
| Multi-provider abstraction + fallback chains | MEDIUM | MEDIUM | P1 |
| Re-ranking (cross-encoder) | HIGH | MEDIUM | P2 |
| Lesson plan generation (curriculum-aligned) | HIGH | MEDIUM | P2 |
| Question/quiz generation from documents | HIGH | MEDIUM | P2 |
| Parent-communication drafts (WhatsApp-ready) | MEDIUM | LOW | P2 |
| Rubric generation | MEDIUM | LOW | P2 |
| Semantic caching | MEDIUM | MEDIUM | P2 |
| Eval-gated prompt promotion | MEDIUM (ops) | MEDIUM | P2 |
| Exam paper intelligence (structured banks) | HIGH | HIGH | P3 |
| Behaviour summaries + at-risk flags | MEDIUM | MEDIUM | P3 |
| Model-tier routing per school plan | MEDIUM | LOW | P3 |
| Curriculum grounding corpus (NERDC docs) | MEDIUM | MEDIUM | P3 |
| Cross-lingual generation (Nigerian languages) | MEDIUM | MEDIUM | P3 |
| Student-facing tutor | MEDIUM | HIGH | P3 (defer) |
| Resumable streams / fan-out | LOW | HIGH | P3 (defer) |
| Billing integration | MEDIUM | HIGH | P3 (defer) |
| Handwriting recognition | LOW | HIGH | P3 (defer) |
| AI proctoring / surveillance | LOW | HIGH | Anti-feature |

**Priority key:**
- P1: Must have for launch (the doc-intelligence Core Value + the governance/streaming floor)
- P2: Should have, add when possible (quality levers + education breadth)
- P3: Nice to have / future consideration (Nigerian-market differentiators that require P1 foundations)

## Competitor Feature Analysis

| Feature | MagicSchool (US) | Khanmigo (US) | EDVES (NG) | Eedu (NG) | Oponeko (NG) | Provsy (NG) | Our Approach |
|---------|------------------|---------------|------------|-----------|--------------|-------------|--------------|
| Report comment generation | ✓ (bulk, FERPA-compliant) | ✓ (free, conservative tone) | ✓ | ✓ (character + academic) | ✓ (AI Report Writer) | — | ✓ Grounded in school's own student data + human review (P1) |
| Lesson plan generation | ✓ (80+ tools, standards-aligned) | ✓ (Khan library) | ✓ (NERDC-aligned) | ✓ (AI quiz/lesson gen) | ✓ (prompt→plan) | — | ✓ Versioned templates + NERDC grounding (P2) |
| Exam/question generation | ✓ (quiz maker) | ✓ | ✓ (15k+ questions, WAEC/BECE/UTME) | ✓ (CBT + quizzes) | ✓ (assessments) | ✓ (AI papers, Bloom's mapping, WAEC/NECO/JAMB/IGCSE) | ✓ From uploaded exam papers via doc pipeline (P3 structured) |
| Document-grounded Q&A (RAG) | Limited | Limited | — | — | — | ✓ (Context Mapping reads teacher materials) | ✓ **Differentiator**: school's own docs indexed + cited (P1) |
| Behaviour analysis | — | — | ✓ (behavioural tracking) | ✓ (behavioural reports, at-risk flags) | — | — | P3 (extends existing Go agents) |
| AI usage dashboards/quota | — (SaaS) | — | — | ✓ ("AI usage" dashboard) | — | — | ✓ Per-school audit + quotas (P1) |
| Offline/low-bandwidth | — | — | — | ✓ (offline LAN CBT) | — | — | Not in scope (out-of-scope per PROJECT.md; note for future) |
| Human-in-the-loop review | ✓ (drafts) | ✓ (drafts) | ✓ | ✓ | ✓ ("ready for you to review") | ✓ | ✓ Mandatory review-before-publish (P1) |
| Provider breadth | SaaS (owns) | OpenAI-based | — | — | — | — | 7 providers, Go ModelRouter-owned fallback (P1) |
| Curriculum grounding | Common Core/TEKS/NGSS | Khan library | NERDC/WAEC/BECE/IGCSE | curriculum-aligned | NERDC (built for Nigeria) | WAEC/NECO/JAMB/IGCSE/GCSE/SAT | NERDC + national exams via RAG corpus (P3) |

**Competitive positioning:** US tools win on breadth-of-templates and compliance paperwork; Nigerian AI-native competitors win on national-curriculum alignment and local workflows but are shallow on document intelligence (most are prompt-driven generators, not RAG-over-school-documents). The defensible wedge for Academio is the intersection: **AI features that are (a) grounded in the school's own documents and data (RAG + repository access), (b) tenant-isolated by architecture, and (c) aligned to NERDC/WAEC/NECO** — which no current competitor combines. Oponeko is the nearest structural competitor (AI-native Nigerian SMS), but its AI is template-generation, not document-grounded.

## Anti-Feature Thresholds (guardrails to document in requirements)

1. **Human-in-the-loop is a hard requirement** for anything a parent or student sees (report comments, parent letters, behaviour summaries). Generated ≠ published.
2. **Identifiable student data** must never reach a provider that isn't in the school's approved list, and never be used for model training. Nigerian NDPA 2023 posture must be documented in requirements.
3. **Deficit-statement filtering** in education prompts: never generate language implying a student "failed" or "is behind" — use "is developing [skill]" phrasing (industry-standard safety wrapper, absent from most tools by default).
4. **Fail-closed retrieval**: no ungrounded LLM answers when RAG finds nothing.
5. **Quota ceilings, not just rate limits**: both request-frequency and token/cost ceilings per school, with clear user-facing messages (never silent blocking).

## Sources

- RAG pipeline production patterns 2026: Datarmatics "How to Build a RAG Pipeline" (2026-06), MetafiedLab "Production-Ready RAG 2026" (2026-06, 72% enterprise adoption stat), Krunal Kanojiya "RAG Architecture Explained" (2026-05), Unstructured "RAG Best Practices" (2026-02), FRE|Nxt Labs (2026-04), SuperML.dev (2026-06), Prompt20 "RAG in Production" (2026-05). Confidence: HIGH (consistent across 7 independent 2026 sources).
- LLM gateways/routing: OpenRouter "vs LiteLLM" (2026-06), LiteLLM routing docs, OpenRouter "LLM Gateway" (2026-06), open-techstack fallback guide (2026-06), theLLMs build-vs-buy (2026-05), Merge.dev (2026-03), Developers Digest comparison (2026-06). Confidence: HIGH.
- Education AI tools: FindSkill.ai report-card comparison (2026-05), ainexte "14 AI tools tested" (2026-06), rework.com "13 tools for educators" (2026-07), ForaSoft lesson-planning (2026-07), HeyGen 30-tools ranking (2026-06), MagicSchool product pages. Confidence: HIGH (multiple sources agree on the tool set and time-saving claims).
- Nigerian edtech: EDVES (edves.ng), Eedu (eedu.tech), Oponeko (oponeko.com), Provsy (provsy.com), Acceede (acceede.com), Mariobee (mariobee.com), EduTek (edutekacademy.com), Schoogle (schoogleng.com). Confidence: MEDIUM — vendor marketing claims, not independently verified; used for feature-fabric comparison only.
- SSE streaming: Ably "Resume tokens and last-event IDs" (2026-03), DHD Tech "Resumable, Cancellable AI SSE" (2026-05), websocket.org "AI Token Streaming" (2026-03), EzAI "Production AI Streaming with SSE" (2026-04), aitechconnect SSE at scale (2026-06), DevOpsNess "LLM Streaming UX in Production" (2026-05), LetsBuild "Streaming LLM Responses in Production" (2026-03). Confidence: HIGH.
- Quotas/audit/governance: Governix (tenant-aware metering/audit OSS), slahiri/llm-gateway (WORM audit), abliteration.ai token quotas, day0ops/quota-management (hierarchical budgets, pre-flight reservation), Bifrost/Maxim "budget and rate-limit architecture for multi-tenant LLM platforms", SpectroCloud "Token metering for AI clouds" (2026-06, OWASP unbounded consumption), FluxMeter (streaming metering). Confidence: HIGH.
- OCR/document parsing: PaddleOCR 3.x/PP-StructureV3 official docs + GitHub (2026), agentbus PaddleOCR vs Tesseract (2026-02), GIGAGPU OCR pipeline (2026-04), youngju.dev document parsing guide (2026-03), PaddleOCR 3.0 technical report (arXiv 2507.05595). Confidence: HIGH for capabilities; the Tesseract-vs-PaddleOCR accuracy gap is corroborated across sources.
- Prompt versioning/LLMOps: PromptForge (GitHub/PyPI 2026-03), MLflow Prompt Registry docs (2026-06), promptci, prompt-version-control, niteagent "prompt versioning guide" (2026-06). Confidence: HIGH.

---
*Feature research for: Academio AI Platform (Python AI Engine + pgvector RAG milestone)*
*Researched: 2026-07-31*
