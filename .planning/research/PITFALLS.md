# Pitfalls Research

**Domain:** Python AI Engine + pgvector RAG in a multi-tenant school ERP (Academio)
**Researched:** 2026-07-31
**Confidence:** HIGH (multi-source agreement on core claims; some tuning numbers MEDIUM — single-source)

## Critical Pitfalls

### Pitfall 1: Tenant data leakage via app-layer-only vector filtering (school A reads school B's documents)

**What goes wrong:**
A document uploaded by School A appears in School B's AI assistant answers, RAG search results, or document status. The leak is silent — no error, no log line. A 2026 study of multi-tenant enterprise retrieval measured 62–100% cross-tenant leakage under adversarial probing when retrieval was ungated. Because embeddings are near-reversible (research has recovered ~92% of 32-token inputs from embeddings alone), a mis-scoped read is a full *content* leak, not a metadata leak. This is the difference between a support ticket and a breach notification.

**Why it happens:**
The instinctive design is `WHERE tenant_id = $1` on every vector query ("a metadata filter"). That filter is an application-layer promise, not a boundary. It fails the day a new query path skips it, a refactor drops it, an agent tool takes `tenant_id` as a parameter, a cached retrieval outlives its session, or a background worker runs without an uncleared context. It also fails structurally: the HNSW index walks *all* tenants' graph nodes before the filter discards candidates, so the search path itself sees other schools' vectors. Every forgotten `WHERE` is a cross-tenant read that "looks completely healthy."

**How to avoid:**
1. **Decide the isolation model deliberately (P1):** Academio already uses schema-per-tenant for every school model. Putting `ai_vectors` in the tenant schema (via `middleware.GetTenantDB`) makes isolation structural — School B's query physically cannot touch School A's table. If a shared `public.ai_vectors` table with `tenant_id` + partial indexes is chosen instead (per PGV-04), you inherit the entire RLS/post-filter complexity below. Schema-per-tenant is the lower-risk choice for this codebase.
2. **Never trust a tenant identifier from a request body, prompt, tool argument, or cached object.** Resolve tenancy once from the authenticated session/JWT in Go; pass it to Python as an explicit scoped context; Python re-asserts it as a mandatory filter on *every* vector read. Treat the LLM/agent as an untrusted caller — a retrieval tool exposed to an agent should take a query and nothing else.
3. **If a shared table is used:** enable RLS with a session variable (`SET LOCAL app.tenant_id`), `FORCE ROW LEVEL SECURITY`, and — critical — never mark the vector search function `SECURITY DEFINER` (the copy-pasted `match_documents` trap that silently bypasses RLS). Audit `pg_roles.rolbypassrls` for every login role; enforce `NOT NULL` on `tenant_id` so unscoped/orphaned rows cannot vanish or become undeletable.
4. **Tenant-scope the semantic cache.** Redis prompt/response caching (INT-03) must include `tenant_id` in the cache key or cached responses become an active cross-tenant channel. A 2026 study found ~half of shared-vocabulary queries hit another tenant's cached response at the common 0.70 similarity threshold.
5. **Prove it in CI (P5/TES-01):** cross-tenant probe suite — seed two synthetic schools with distinctive canary documents, then query as School A with terms that only match School B's canaries and assert zero hits. Cover every retrieval entry point: `/v1/search`, agent tool calls, cached retrievals, reranking, background jobs, admin impersonation.

**Warning signs:**
- A test or manual query returns results when the tenant filter is commented out (means nothing underneath catches it)
- `tenant_id` appears in request DTOs or prompt templates as an *input* rather than derived context
- Any vector-search SQL function declared `SECURITY DEFINER`
- No cross-tenant probe test exists in the test suite
- Cache keys built from query embedding only, no tenant component

**Phase to address:**
Phase 1 (PGV-03/PGV-04 — isolation model + table design), Phase 2 (PYE-05 — Python re-enforces tenant filter), Phase 4 (INT-03 — tenant-scoped cache), Phase 5 (TES-01 — cross-tenant probe suite in CI).

---

### Pitfall 2: HNSW post-filter recall collapse — tenants silently get incomplete answers

**What goes wrong:**
School B asks a question; the system returns 2 chunks instead of 10, or "no results found" for content that definitely exists. No error is raised. The HNSW index fetches a candidate list sized by `ef_search` (default 40), then the tenant filter is applied *after* the scan. With a filter matching 10% of rows, only ~4 of 40 candidates survive — the query returns short or empty. It gets worse as more schools are added, because each tenant's share of the shared index shrinks.

**Why it happens:**
pgvector's ANN index does not "see" a tenant boundary — it walks a graph across all tenants and reconciles visibility afterward. Teams tune recall against a single-tenant test set, ship defaults (`ef_search=40`), and never measure recall *per tenant* on production-shaped data. A whale school's documents crowd small schools' neighbors out of the candidate window.

**How to avoid:**
1. **Prefer schema-per-tenant tables** (Pitfall 1): the HNSW index then contains only that school's vectors — zero dilution, no RLS-vs-index interaction at all.
2. **If a shared table is chosen:** enable `hnsw.iterative_scan` (pgvector ≥0.8.0, October 2024) with `SET hnsw.iterative_scan = strict_order` (or `relaxed_order` + MATERIALIZED CTE reorder), bounded by `hnsw.max_scan_tuples`. Iterative scans re-enter the index until enough rows pass the filter.
3. **Over-fetch:** ask for more candidates than you need (e.g., `LIMIT 20` for 10 results) so post-filtering still yields k.
4. **Measure recall under isolation:** compare RLS/tenant-scoped ANN results against a tenant-scoped exact (seq-scan) ground truth per tenant. Verify with `EXPLAIN (ANALYZE, BUFFERS)` that the tenant predicate lands on the index scan, not a late `Filter` — a `Seq Scan` where you expected an `Index Scan`, or high `Rows Removed by Filter`, means the policy is a post-filter and both security and latency suffer.

**Warning signs:**
- Results count drops when tenant filtering is added (e.g., always exactly 1–2 results)
- `EXPLAIN` shows `Seq Scan` or heavy `Rows Removed by Filter`
- Small/new schools complain "search finds nothing" while large schools work fine
- Recall looks fine in aggregate but collapses for small tenants

**Phase to address:**
Phase 1 (PGV-04 — index design, iterative_scan config, EXPLAIN verification), Phase 5 (TES-01 — RAG-accuracy tests per tenant, not globally).

---

### Pitfall 3: Qdrant → pgvector migration corrupts vector space, IDs, or distance semantics

**What goes wrong:**
After cutover, search returns garbage or nothing. Root causes are typically: (a) **dimension mismatch** — new embeddings from a different model/dimension than the column's `vector(n)` (Postgres raises or silently mis-sorts); (b) **distance semantics inverted** — Qdrant returns *similarity* (higher = closer), pgvector returns *distance* (lower = closer); cosine in Qdrant vs `<=>` (cosine distance) in pgvector must be subtracted from 1; (c) **ID collisions** — Qdrant point IDs (UUID strings) mapped to pgvector bigint IDs differently than the application expects; (d) **metadata dropped** — Qdrant payload fields (`tenant_id`, `document_id`, `visibility`) that the Go `vector.Store` interface relies on for filtering never make it into the `ai_vectors` columns; (e) **mixing old and new embedding models** during re-embed — vectors from different models live in different, incommensurable spaces; distances between them are meaningless, not just worse.

**Why it happens:**
Migration tools copy vectors but don't reconcile semantics. The plan (PGV-05) correctly rates the *volume* risk LOW (no live collections), but the *schema/semantics* risk is real: the existing Qdrant `Store` implementation and the new pgvector one must produce byte-equivalent behavior for the RAG layer, or every downstream agent silently degrades.

**How to avoid:**
1. **Reconcile semantics before writing code:** map Qdrant collection → table, point → row, payload → metadata columns, and write the distance/similarity conversion explicitly (`similarity = 1 - distance` for cosine) in the new store.
2. **Verify counts and dimensions exactly:** `SELECT COUNT(*)` (not `n_live_tup`), assert dimension matches the column type, assert distance metric and operator class match (`vector_cosine_ops` with `<=>`).
3. **If any re-embedding is involved:** dual-write (both stores), backfill in the background, validate recall on a held-out query set, then cut over atomically via config flag (existing `AI_QDRANT_*` → pgvector DSN swap). Keep Qdrant code behind the interface until cutover verified.
4. **Version every vector (see Pitfall 4).** Never mix embedding-model generations in one searchable index.
5. **Interface-conformance test:** the pgvector `Store` must pass the same behavioral tests as the Qdrant `Store` (insert/search/delete/filter) before the RAG layer is pointed at it.

**Warning signs:**
- Migration log shows row/vector counts that don't match the source
- Post-cutover search returns different-looking results than Qdrant for identical queries
- `vector` column dimension ≠ embedding output dimension (index build fails or planner falls back)
- Scores are inverted (best results have highest distance)

**Phase to address:**
Phase 1 (PGV-03..PGV-06 — store implementation, migration tool, config swap), Phase 6 (RET-02 — Qdrant retirement only after verified cutover).

---

### Pitfall 4: The HNSW index is silently not used — or the build dies from default settings

**What goes wrong:**
Vector queries get slow, or the index build fails/hangs. Two distinct traps: (a) **operator class mismatch** — index created with `vector_l2_ops` (or `vector_ip_ops`) but queries use `<=>` (cosine), or any implicit type cast on the vector column: Postgres silently skips the index and sequential-scans the whole table. Nothing in the logs says "index missed." (b) **`maintenance_work_mem` default of 64 MB** — building an HNSW index over even a few hundred thousand 1536-dim vectors at the default spills to a 10–50× slower on-disk build, and can outright fail on larger tables. Additionally, the HNSW working set must fit in RAM (~20–25 KB per 1536-dim vector) or query latency falls off a cliff.

**Why it happens:**
pgvector ships conservative defaults that are "safe but not fast." Teams copy the index DDL, never run `EXPLAIN ANALYZE`, and benchmark recall on 10k-row samples.

**How to avoid:**
1. **Match the ops class to the operator:** `USING hnsw (embedding vector_cosine_ops)` with `ORDER BY embedding <=> $1 LIMIT k`. If you output the distance in the SELECT clause for display, keep the ORDER BY form intact — the index only applies to `ORDER BY embedding <=> $1 LIMIT k` shape.
2. **Raise `maintenance_work_mem` to 8–16 GB for the build, then revert.** Use `CREATE INDEX CONCURRENTLY` (never lock writes for a multi-hour build) — in dev this is a one-shot migration step; still do it right.
3. **HNSW over IVFFlat** for this workload (continuous ingest, no training step, can create on an empty table, no `lists` re-tuning as data grows).
4. **Verify with `EXPLAIN (ANALYZE, BUFFERS)` on every similarity query in the test suite** — assert `Index Scan using ..._hnsw` is chosen. Add `pg_stat_statements` to see seq-scan regressions.
5. **Right-size the dev Postgres memory:** `shared_buffers` 25–40% of RAM; document the RAM budget per vector so the schema doesn't outgrow the dev box.

**Warning signs:**
- `EXPLAIN` shows `Seq Scan` on vector queries (unless intentionally exact for small tables)
- Index build takes hours or OOMs in CI/dev
- Query latency jumps after N rows are inserted (working set outgrew RAM)
- Recall@k collapses between dev sample and production-shaped data

**Phase to address:**
Phase 1 (PGV-04 — index DDL with correct ops class + build settings; migration must run with raised `maintenance_work_mem`), Phase 5 (TES-01 — EXPLAIN assertions in tests).

---

### Pitfall 5: Scanned/mixed PDFs silently dropped — RAG indexes incomplete documents and "reports success"

**What goes wrong:**
A 50-page school policy has 47 digital pages and 3 scanned signature pages. Naive extraction (PyMuPDF text layer) returns text for 47 pages and *blank strings* for 3. The pipeline marks the document "processed," the knowledge base silently misses 6% of its content, and nobody notices until a user asks about page 48. Adobe's 2025 survey: 38% of business PDFs contain at least one scanned page (65%+ in legal/healthcare). OCR-everything wastes 90%+ of compute (Tesseract ~1.8s/page vs PyMuPDF 0.01s/page).

**Why it happens:**
Scanned PDFs are images in a PDF container — there is no text layer to extract. Every text-based extractor returns empty, and an empty string is indistinguishable from "blank page" unless the pipeline distinguishes them. Teams pick one parser for the whole document instead of routing per page.

**How to avoid:**
1. **Page-level routing (P2/PYE-02):** classify each page with cheap heuristics (<1ms each) — text density (<50 chars → likely scanned), image coverage (>80% → scan), font embedding (zero fonts → scan), encoding sanity (replacement chars → broken text layer), character distribution. Route: digital → PyMuPDF; scanned → OCR; table-heavy → table-aware extractor. `Extract` result must record *which extractor ran per page* and per-page confidence.
2. **Quality gates, not just extraction:** if a page yields <50 chars of text, flag it; if OCR confidence is below threshold, mark the document for human review rather than passing garbage downstream. Add a fallback trigger: chars/page < 50, table fragmentation, or effective-character ratio < 30% → re-extract with a stronger engine.
3. **DPI and preprocessing for OCR:** render at ≥300 DPI (below 200 DPI, Tesseract error rate climbs to 12–18%); deskew, denoise, binarize before OCR; handle orientation.
4. **Expose extraction quality in the pipeline status:** `GET /api/v2/ai/documents/:id/status` (PIP-02) should report per-document char count, pages OCR'd, and confidence so "processed" never means "silently lossy."
5. **Pin library choices for edge cases:** `pdf2image` needs poppler installed; pypdf has *no* table extraction; pdfplumber needs a text layer (fails silently on scans); Tesseract has no reading-order model for multi-column pages.

**Warning signs:**
- Extraction returns empty text for a page that visibly has content (test with a scanned sample in the test suite)
- "Processed" documents have suspiciously low char/page counts in status
- No scanned-PDF fixture in the pytest corpus
- Extracted text interleaves columns of academic/financial documents (reading order broken)

**Phase to address:**
Phase 2 (PYE-02 — extraction routing, OCR, quality gates, confidence scoring), Phase 3 (PIP-02 — status surfaces quality metrics), Phase 5 (TES-01 — scanned/mixed/table fixtures in pytest).

---

### Pitfall 6: Multi-provider LLM failover causes cost explosion and silent quality regression

**What goes wrong:**
Three failure modes in one: (a) **cost explosion** — primary provider degrades, traffic shifts to a more expensive fallback, monthly bill triples; a retry loop spends $1,800 in an afternoon (real incident); (b) **reroute tax** — a cheap model fails at a task, the router re-runs it on the flagship model, and you're now paying for *both* calls plus double latency on a meaningful share of traffic; (c) **silent degradation** — the fallback model returns well-formed, HTTP-200 output that is worse (shorter, lazier, wrong format), and nothing alarms because the error rate is zero.

**Why it happens:**
Failover logic treats "provider failed" as a binary, but providers fail in gradations. Router error classification is wrong (retrying non-retryable 4xx on every provider wastes money; retrying the same rate-limited provider burns time). No cost caps. No per-task quality evaluation. Different providers also differ in ways that look like success: tokenizer token counts vary ~40% for the same text (cost tracking in tokens, not currency, misleads), and context-window truncation is provider-specific (Claude truncates the *beginning*, GPT-5.4 truncates the *middle*) — fallback to a smaller-window provider silently drops conversation context.

**How to avoid:**
1. **Classify errors, not just "failed":** 429 → fail over to next provider (never retry the same one; respect `Retry-After`); 5xx/timeout → retry same provider once, then fail over; other 4xx → permanent, do not fail over (a malformed request fails the same way everywhere).
2. **Cost controls that fire before spend (INT-03):** per-request cost cap + per-tenant daily spend cap in Redis; a runaway retry loop must trip the cap and page, not bill. Track **cost-per-successful-task** (including retries and escalations), not tokens or per-call cost.
3. **Circuit breakers on the existing ModelRouter pattern:** 5 failures/30s cooldown with half-open probing already exists in Go — apply the same policy to Python providers; use continuous health scores (decrement on 429/5xx/slow, recover via probe traffic) rather than binary open/closed where possible.
4. **Dialect translation layer:** OpenAI/Anthropic/DeepSeek request+response shapes differ (system prompt handling, `max_tokens`, content blocks, stream event formats). Naive failover that points an OpenAI client at Anthropic fails immediately; streaming clients parsing one format against another provider's stream get garbled output *with no error*. Normalize every provider's stream to one canonical event shape at the router; strip routing metadata from the conversation before sending.
5. **Provider-aware context management:** before fallback, check the target provider's context window; proactively summarize older messages instead of silently truncating.
6. **Eval-driven routing (P2/PYE-01):** per-task eval set re-run when models change; A/B mirror new providers against production on a % of traffic before promoting. "The model returned a confident answer" ≠ "correct answer" — you cannot route responsibly without distinguishing them.
7. **Ollama self-hosted is always behind an API fallback** — it has different operational shape (capacity during bursts, upgrades).

**Warning signs:**
- Daily cost spikes correlate with provider incidents (fallback-to-expensive)
- Same workload's token count varies wildly across providers (tokenizer mismatch)
- Streaming responses garble after a provider switch mid-conversation
- Quality complaints with a flat error rate (silent regression — watch fallback rate and per-task quality scores)
- Conversations "forget" earlier turns after a fallback (truncation point differs)

**Phase to address:**
Phase 2 (PYE-01 — provider abstraction with dialect normalization), Phase 4 (INT-03 — rate limits, quotas, cost caps, circuit breakers on Python calls, Redis cache with tenant scoping), Phase 5 (OBS-01 — cost-per-task, fallback-rate, quality metrics).

---

### Pitfall 7: SSE streaming breaks in production — buffered tokens, 60-second deaths, garbled mid-stream failover

**What goes wrong:**
Three distinct failures: (a) **buffering** — user sees the spinner for 5–30s then the whole response arrives at once; classic "works on localhost, breaks in prod" because nginx/ALB/CDN buffer streaming responses by default; (b) **idle timeout** — the stream dies at exactly 60 seconds (nginx `proxy_read_timeout` default, ALB idle timeout) or 100s (Cloudflare free tier) when the model pauses for tool use or long reasoning; the client reconnects and re-sends the entire prompt, billing twice; (c) **the Go hop** — this project has *two* streaming hops: Go → Python (`/v1/chat/stream`) and Go → browser (`POST /api/v2/ai/chat/stream`). Both must be non-buffering, and the Go side must parse Python's SSE correctly.

**Why it happens:**
Every layer defaults to request/response semantics: nginx buffers (4–8 KB) until the body completes — an infinite stream never completes; gzip on `text/event-stream` buffers *forever*; uvicorn's `--timeout-keep-alive` defaults to 5s (502s on any request >5s); heartbeats, if sent, sit in an upstream buffer and never reach the client. The dev path (browser → Vite :4000 → Go :8080 → Python) has no proxy, so it never reproduces the production failure.

**How to avoid:**
1. **Python side:** `StreamingResponse` with `media_type="text/event-stream"`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` headers. Send `: ping\n\n` comment frames every 15–30s (FastAPI's SSE helpers do this). Never gzip the endpoint.
2. **Proxy/ingress (P0/FND-02 docker-compose):** `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 3600s`, `proxy_set_header Connection ''`, `proxy_http_version 1.1` for the streaming route; if any Go middleware (e.g., gzip/compression) wraps the response writer, disable it for `text/event-stream` — it will destroy streaming and `Flusher` support.
3. **Go side (INT-01):** the handler must flush per event (`c.Writer.Flush()` / `http.Flusher`) — never buffer Python's chunks; stream with `Content-Type: text/event-stream`; propagate `X-Request-ID`. The Go EngineClient reading Python's SSE must use a scanner with a larger buffer (default `bufio.Scanner` limit is 64 KB per token — one long `data:` line with retrieved documents/tool calls exceeds it and silently kills the stream).
4. **Timeouts:** set uvicorn `--timeout-keep-alive 0` for streaming; never let Go's overall request timeout be shorter than the worst-case stream duration; use a separate, generous timeout budget for the stream path vs. non-streaming chat.
5. **Client (frontend):** `EventSource` only supports GET — chat needs POST + JWT, so use `fetch` + `ReadableStream`; detect incomplete streams (stream closed without a `done` event) and surface "connection lost" rather than silently truncating; handle `retry:` and `Last-Event-ID` semantics for reconnects.
6. **Test through a real proxy in CI** — a staging nginx with default settings reproduces buffering/timeout bugs that localhost hides.

**Warning signs:**
- Streaming works against `:8080` directly but bursts through the deployed ingress
- Streams die at a consistent N seconds (60/100) regardless of content
- 502s on requests >5s (uvicorn keep-alive default)
- First-token latency spikes at the proxy layer (buffering)
- Client receives truncated responses with no error

**Phase to address:**
Phase 0 (FND-02 — docker-compose ingress/health for ai-engine), Phase 2 (PYE-04 — Python SSE endpoint correctness), Phase 4 (INT-01 — Go SSE route + EngineClient SSE parsing), Phase 5 (TES-01 — streaming integration test through a proxy).

---

### Pitfall 8: Go ↔ Python seam: no timeout, no circuit breaker, trusted-but-unaudited service boundary

**What goes wrong:**
The Go `EngineClient` calls Python with a bare `http.Client{}` — Go's default client has *no timeout*, so a hung Python process hangs the Go worker goroutine forever. Or: timeouts exist but are uniform (a 5-minute OCR extraction of a large PDF gets killed by a 30s request timeout, so every big document permanently fails). Or: `AI_ENGINE_TOKEN` is sent as a query parameter (leaks into logs/proxies). Or: Python trusts a `tenant_id`/`school_id` field in the JSON body (Pitfall 1). Or: the Go handler doesn't propagate context (Rule B2 violation) and the user's disconnect leaves the Python call running.

**Why it happens:**
Internal HTTP seams get treated as "local calls are fast and reliable." They are not — they time out, rate limit, hang, and return unexpected status codes. The two codebases drift because JSON is lenient: Go DTO and Python schema can disagree on field names/types/enums for months before anyone notices, and it always surfaces as a confusing runtime error.

**How to avoid:**
1. **Timeout discipline (P0/FND-03):** `http.Client` with granular transport timeouts (dial 3s, TLS handshake 5s, response-header 5s, overall per-call budget). Different endpoints get different budgets: `/v1/extract` (minutes — OCR) vs `/v1/chat` (seconds) vs `/v1/chat/stream` (streaming — no overall cap, idle keepalive only).
2. **Context propagation:** every EngineClient call takes `ctx` from the caller; asynq worker handlers get the task context (respect `asynq.Timeout`/`Deadline`); never `context.Background()` in request-scoped code (Rule B2).
3. **Circuit breaker + retry classification on Python calls (INT-03):** retry only 429/5xx/timeouts with backoff+jitter; 4xx is permanent. Wrap Python in a circuit breaker so a degraded Python service doesn't stack timeouts on every request.
4. **Service auth (FND-04):** `AI_ENGINE_TOKEN` in a header (`Authorization: Bearer` or `X-Service-Token`), *never* in the URL; constant-time comparison; fail closed at startup if unset (Rule B12). Python authenticates every internal request — "internal network location is not identity." Include `aud`/scope claims if a JWT; plan rotation from day one.
5. **Tenant context:** Go resolves tenancy from the JWT session and passes school_id as an explicit context field; Python must *not* accept tenant from unverified body input beyond that scoped context (see Pitfall 1).
6. **Contract + correlation:** FastAPI auto-generates OpenAPI — add a CI contract check that the Go client DTOs match the Python schemas (additive fields only; never remove/rename/enum-shuffle without version bump). Propagate `X-Request-ID` end to end (OBS-01) so a failure is traceable across Go→Python in one lookup.
7. **Never log raw payloads** — school documents are student PII; log sizes/hashes, not content (Rule B3 logger discipline + SEC-01 PII masking).

**Warning signs:**
- EngineClient calls lack `context.WithTimeout` or reuse a bare `http.Client`
- `AI_ENGINE_TOKEN` appears in URLs, log lines, or request bodies
- Same failure appears as different errors in Go vs Python (contract drift)
- A large-PDF upload consistently fails after N seconds (timeout budget mismatch)
- No `X-Request-ID` in Python logs

**Phase to address:**
Phase 0 (FND-03/FND-04 — client seam, auth, config validation), Phase 4 (INT-03 — retries/circuit breakers), Phase 5 (OBS-01 — correlation, metrics; SEC-01 — PII masking, audit).

---

### Pitfall 9: Doc-ingest pipeline is at-least-once but handlers aren't idempotent — duplicate vectors, duplicate notifications

**What goes wrong:**
A worker crashes after Python embedded chunks but before the completion event/notification fires. asynq redelivers the task (at-least-once is the only guarantee that survives crashes). The retry re-runs extract → chunk → embed → insert, and now pgvector holds *two copies* of every chunk (or worse, three after another retry). Search results silently double, citations point at duplicated chunks, and storage grows per retry. Alternatively the worker marks the task complete before the event fires and the notification is lost.

**Why it happens:**
Handlers are written as "do the work" instead of "make the work's effect a single, repeatable, detectable state." At-least-once delivery means every task *will* run more than once — that's the design, and it's not a bug in asynq; it's a contract the handler must honor.

**How to avoid:**
1. **Idempotent ingest (P3/PIP-01):** unique constraint on `(tenant_id, document_id, chunk_index)` (or a `chunk_hash`) in `ai_vectors` — retries `INSERT ... ON CONFLICT DO NOTHING` instead of duplicating. Record pipeline status transitions in the document record *atomically with* the vector writes (same transaction where possible; otherwise an idempotency ledger with a unique key per (document_id, stage)).
2. **Progress state machine, not boolean:** document status goes `queued → extracting → chunking → embedding → completed/failed`; a retry resumes from the recorded stage instead of re-running everything (big win for OCR, which is the expensive step).
3. **Classify errors:** return `asynq.SkipRetry` for permanent failures (unsupported file type, corrupt PDF) so they fail fast to the archive instead of burning the retry budget; wrap transient failures (Python 5xx, timeouts) normally.
4. **Per-task timeouts that fit the work:** `asynq.Timeout` must exceed worst-case OCR (a 200-page scanned PDF can take minutes). An ignored task context that keeps running blocks the worker concurrency slot — check `ctx.Err()` in long loops (also Rule B2).
5. **Use `asynq.Unique(...)`** to dedupe enqueue (double-click on upload), and route doc-ingest to its own queue with its own priority so OCR doesn't starve `ai:scoring` tasks.
6. **Monitor the archive (DLQ) as an SLO:** asynq's archived state *is* the dead-letter queue. Alert on depth — a growing archive is the leading indicator that processing is broken, not a backlog to clear quarterly. Provide an admin re-run path (`asynq.Inspector` → `RunTask`) and a triage runbook: transient → replay; permanent → discard; poison → code fix before any replay.

**Warning signs:**
- `ai_vectors` has duplicate rows for the same document after a worker restart
- Archive (dead-letter) depth grows without alerting
- Task retry counts climb for a class of documents (e.g., all large PDFs → timeout budget wrong)
- Document status stuck in `processing` with no timeout path (orphaned active tasks)

**Phase to address:**
Phase 3 (PIP-01 — idempotent ingest, status state machine, unique constraint), Phase 1 (PGV-04 — unique constraint in `ai_vectors` DDL), Phase 4 (INT-03 — queue config, DLQ monitoring), Phase 5 (TES-01 — kill-worker-mid-pipeline test asserting no duplicates).

---

### Pitfall 10: Embedding model unversioned — future model upgrades silently corrupt retrieval

**What goes wrong:**
Six months in, someone upgrades the embedding model for better accuracy. If vectors are re-embedded in place or mixed with old-model vectors, the index now contains two incommensurable vector spaces. Cosine similarity between a model-A vector and a model-B vector is not a worse number — it's a meaningless one. Retrieval silently degrades, and there is no column anywhere recording which model produced which vector, so nobody can even diagnose it. Rollback requires a full rebuild.

**Why it happens:**
Vector stores ship with no migration framework — no `ALTER VECTOR TABLE`, no per-row provenance. Teams treat an embedding upgrade like a config flip. Every recall-change investigation that follows ("did we change chunking? cleaning? metadata?") is guesswork without version tags.

**How to avoid:**
1. **Add a per-vector version tag from day one (P1/PGV-04):** `embedding_model` + `model_version` + `chunking_version` columns on `ai_vectors` (metadata columns are already planned — add these). A short string like `text-embedding-3-small@2026-03/chunk-512` per row. Cost ≈ zero now; cost of retrofitting ≈ a migration project.
2. **Scope every query to one version:** ingestion and retrieval must use the same model; the search layer filters by active version so the two spaces never meet in a ranking.
3. **When a model change is real:** dual-write new-model vectors to a new column/table, background backfill, validate recall against a golden query set, flip reads via config/flag, keep old vectors for rollback (the config-flag pattern already planned for Qdrant→pgvector cutover generalizes to embedding upgrades).
4. **Version the chunker too:** most recall regressions come from simultaneous chunking/metadata changes, not the model.

**Warning signs:**
- No column records which embedding model/version produced each vector
- Search quality changes between deploys with no model change logged
- Backfill or re-embed scripts overwrite vectors in place

**Phase to address:**
Phase 1 (PGV-04 — version columns in DDL), Phase 2 (PYE-02 — embedder stamps version), Phase 6 (RET — migration discipline for future model upgrades).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `tenant_id` filter in app code only, no RLS/structural isolation | Fast to build | School-to-school data breach; retrofitting RLS after data exists is a migration | **Never** — this is the platform's core trust boundary |
| One PDF parser for all documents | One line of code | 5–40% of content silently missing from knowledge base; unrecoverable silently | **Never** for production; acceptable only for a demo corpus |
| Uniform HTTP timeout for all Python endpoints | Simple config | Large-document OCR permanently fails; streaming gets killed | Only as a placeholder with a follow-up ticket; use per-endpoint budgets |
| Cost tracking in tokens instead of currency | Free (SDK gives token counts) | 40%+ cost accounting error across providers; no spend control | Never for quota/cost-cap decisions |
| Copy-pasted `match_documents` SQL function with `SECURITY DEFINER` | "Just works" in dev | Every tenant's vectors reachable through one call | **Never** |
| No embedding version column | Skip a column | Future model upgrade = full rebuild + undiagnosable recall drift | Never — add the column now, it's one migration |
| SSE tested only against localhost/Vite proxy | Faster dev loop | Buffering/timeout bugs ship to production | Never for the stream path; always add a proxy-in-the-middle test |
| Static `AI_ENGINE_TOKEN` with no rotation plan | One config value | Compromised token = unlimited internal API access forever | Only in dev; plan rotation + audit before anything non-dev |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Qdrant → pgvector | Copy vectors without converting similarity↔distance | `similarity = 1 - distance` for cosine; assert dimension, count, metric, metadata parity (P1) |
| pgvector index | `vector_l2_ops` index queried with `<=>` | Match ops class to operator (`vector_cosine_ops` + `<=>`); assert `Index Scan` in EXPLAIN (P1) |
| Python providers | Failover to Anthropic with an OpenAI-shaped request | Dialect translation layer; normalize stream event shapes at the router (P2) |
| Python SSE → Go | Go `bufio.Scanner` default 64 KB limit chokes on long `data:` lines | Larger scanner buffer (or incremental reader) in EngineClient (P4) |
| Go SSE → browser | gzip/compression middleware wraps the response writer | Exclude `text/event-stream` from compression; flush per event (P4) |
| Go worker → Python `/v1/extract` | Task timeout shorter than OCR worst case | `asynq.Timeout` ≥ worst-case extraction; check `ctx.Err()` in loops (P3) |
| Redis cache | Cache key omits tenant | Include tenant + embedding version in key; tenant-scoped TTLs (P4) |
| asynq payload | No schema version in task payload | Version the payload struct; never reuse field meanings (P3) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| HNSW working set outgrows RAM | Query latency cliff after N rows | Budget ~20–25 KB/1536-dim vector; right-size dev/CI Postgres (P1) | ~hundreds of thousands to low millions of vectors, depending on box |
| HNSW build at default `maintenance_work_mem` (64 MB) | Index build takes hours/OOMs | Raise to 8–16 GB for the build; `CREATE INDEX CONCURRENTLY` (P1) | Any multi-hundred-K vector build |
| Shared-table tenant filter post-scan | Small tenants return short/empty results; latency varies by tenant | Schema-per-tenant table (or `hnsw.iterative_scan` + over-fetch) (P1) | When the largest tenant dominates the shared graph |
| OCR-everything extraction | 10,000-PDF ingest takes days | Page routing: PyMuPDF for digital, OCR only scanned (P2) | ~10k+ documents; also wasteful at any scale |
| SSE without heartbeat/buffering-off | Streams die at 60/100s; tokens burst | Heartbeat ≤30s; `proxy_buffering off`; `X-Accel-Buffering: no` (P2/P4) | The first real proxy in front |
| Uniform timeout across endpoints | Large OCR fails; streams cut | Per-endpoint budgets; no overall cap on stream path (P0) | First document >30s to process |
| Retrying rate-limited provider | 429 storm, wasted spend, thundering herd | 429 → failover to next provider + `Retry-After` respect (P4) | First provider rate-limit event at peak |
| Concurrent SSE connections | FD exhaustion (`too many open files`) | `ulimit -n`, `--limit-concurrency`, load test at 10× expected peak (P2) | ~900–1000 concurrent streams per worker |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Vector queries scoped only by app-layer tenant filter | Cross-school document leak; embedding inversion makes leaks content-level | Structural isolation (schema-per-tenant) or RLS + `FORCE ROW LEVEL SECURITY`; CI cross-tenant probes (P1/P5) |
| `SECURITY DEFINER` on vector search function | RLS bypassed; all tenants reachable | `SECURITY INVOKER`; if definer is unavoidable, filter inside and pin `search_path` (P1) |
| `AI_ENGINE_TOKEN` in URL/query/logs | Token leak via access logs | Header-only; constant-time compare; never log; rotation plan (P0/FND-04) |
| Python trusts tenant/school from request body | Tenant spoofing via JSON | Tenant resolved in Go from session; Python enforces as mandatory scoped context (P2/PYE-05) |
| Caching responses without tenant in key | Cross-tenant semantic cache channel | Tenant-scoped cache keys (P4/INT-03) |
| Logging raw document/extracted text | Student PII in log aggregation systems | Log sizes/hashes/IDs, not content; PII masking (P5/SEC-01) |
| Static service token, no expiry/audience | Compromised or replayable internal access | Short-lived tokens with `aud` validation + rotation (P0) |
| OCR/extract endpoint unauthenticated ("internal network is safe") | SSRF/reachability from any container; data exfil | Every Python endpoint requires service token (P0) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Processed" status on lossy extraction | Teacher asks about a policy page that was silently dropped | Status reports pages extracted/OCR'd, char count, confidence; low confidence → review state (P3) |
| SSE stream dies mid-answer | User sees truncated advice, thinks it's the final answer | Client detects missing `done` event → "connection lost, retry?"; auto-reconnect with retry backoff (P4) |
| Streaming bursts instead of token-by-token | Feels broken/slow; user abandons | Proxy buffering off + flush-per-event (P2/P4) |
| Fallback provider silently worse at the task | Confident-sounding wrong answers (report comments, parent letters) | Eval-gated routing; per-task quality metrics; A/B before promoting providers (P2/P5) |
| Document stuck "processing" forever | User re-uploads, duplicates pile up | Status timeout path + idempotent re-upload (unique enqueue) (P3) |
| Duplicate chunks after worker retry | Search returns the same passage 2–3×, citations doubled | Unique (tenant, document, chunk_index) + ON CONFLICT DO NOTHING (P3) |

## "Looks Done But Isn't" Checklist

- [ ] **Vector store cutover:** Index is built and query returns results — but did you run `EXPLAIN (ANALYZE, BUFFERS)` to confirm `Index Scan` (not `Seq Scan`)? Did you assert Qdrant-vs-pgvector result parity for identical queries?
- [ ] **Tenant isolation:** Retrieval returns correct data when the tenant filter is *present* — but did you run the cross-tenant probe (query as School A with School B's canary terms, assert zero hits) across *every* entry point including cache, reranking, and agent tools?
- [ ] **SSE streaming:** Stream works against `localhost:8080` directly — but did you test through the actual ingress/proxy with default buffering and a 60s idle gap? Did you verify the Go hop flushes per event and the scanner buffer is large enough for long `data:` lines?
- [ ] **PDF extraction:** PyMuPDF extracts the test PDFs — but did the corpus include scanned pages, multi-column pages, tables, and CID-encoded fonts? Does the pipeline distinguish "empty text" from "scanned page"?
- [ ] **Provider failover:** Fallback fires on a hard 5xx — but does it fire on a 429 with `Retry-After`, a slow-but-200 provider, and a degraded-stream (200, garbage) case? Is there a daily spend cap that trips *before* the bill arrives?
- [ ] **Doc pipeline idempotency:** Pipeline completes when everything works — but kill the worker between embed and event, redeliver the task, and verify zero duplicate vectors and exactly one notification.
- [ ] **Cost tracking:** You log tokens per call — but do you compute cost per *successful task* (including retries and reroute tax) in currency, per tenant, with a per-tenant quota?
- [ ] **Service auth:** Python endpoints require `AI_ENGINE_TOKEN` — but do they reject wrong-audience/expired tokens, and does Go fail closed at startup if the token is unset?
- [ ] **Embedding versioning:** Vectors have metadata — but does the metadata record which embedding model/version and chunking version produced each row?

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Tenant data leak discovered | HIGH | Immediate: disable affected retrieval entry points; rotate all service tokens; audit audit-logs for which schools' vectors were read by whom; notify per policy. Permanent: add structural isolation (schema-per-tenant or RLS), add CI cross-tenant probes |
| Mixed embedding spaces in one index | HIGH | Freeze ingestion; identify which rows have which model version (needs version column — retrofit if absent); rebuild index for one version; re-enable queries scoped to one version |
| Duplicate vectors from retries | MEDIUM | Dedup query on (tenant, document, chunk) — delete extras; add unique constraint + ON CONFLICT for the future |
| Streaming broken in prod | LOW | Fix ingress/nginx buffering + timeouts; add heartbeat; re-test through proxy in CI |
| Cost explosion from failover | MEDIUM | Cut spend at per-tenant cap; tighten router to cheaper fallbacks; instrument cost-per-successful-task before reopening |
| Silent OCR data loss in knowledge base | MEDIUM | Re-run extraction with quality gates on the affected corpus; flag low-confidence docs for re-extraction or human review |
| Archive (DLQ) filling | LOW | Triage runbook: classify transient (replay) vs permanent (discard) vs poison (fix code); fix timeout budgets for large docs |
| Go/Python contract drift | MEDIUM | Add OpenAPI contract check in CI; additive-field rule; version endpoints on breaking change |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Tenant data leakage (app-layer filter only) | P1 (PGV-03/PGV-04 isolation model) + P2 (PYE-05) + P4 (INT-03 cache) | P5/TES-01 cross-tenant probe suite in CI — zero canary hits across all entry points |
| HNSW post-filter recall collapse | P1 (schema-per-tenant or iterative_scan + over-fetch) | P5 per-tenant recall vs exact ground truth; EXPLAIN shows predicate on index scan |
| Qdrant→pgvector semantics mismatch | P1 (PGV-03..06) | P1 store interface-conformance tests + count/dimension/distance parity asserts |
| Silent seq-scan / build defaults | P1 (PGV-04 DDL + build settings) | P5 EXPLAIN assertions in test suite; index build completes in CI with raised work_mem |
| Scanned/mixed PDF silent loss | P2 (PYE-02 routing + quality gates) | P5 pytest corpus includes scanned/multi-column/table/CID fixtures; chars/page metric surfaced in PIP-02 |
| LLM failover cost + silent regression | P2 (PYE-01) + P4 (INT-03) | P5 cost-per-successful-task, fallback-rate, quality drift metrics; per-tenant spend caps tripped in tests |
| SSE buffering/timeouts | P0 (FND-02) + P2 (PYE-04) + P4 (INT-01) | P5 streaming test through a real proxy with 60s idle gap; kill-mid-stream client test |
| Go↔Python seam (timeout/auth/skew) | P0 (FND-03/FND-04) + P4 (INT-03) | P5 contract check in CI; correlation IDs present end-to-end; startup fails closed on missing token |
| Non-idempotent doc pipeline | P3 (PIP-01) + P1 (unique constraint) | P5 kill-worker-mid-pipeline test → zero duplicates, one notification |
| Embedding model unversioned | P1 (PGV-04 version columns) | Code review + migration check: every ai_vectors row has model+chunking version |

## Sources

- **Multi-tenant vector isolation:** DEV Community — "Your WHERE clause is not a security boundary" (2026-06); Pradeep Bhandari — "Hard Multi-Tenancy for pgvector" (2026-07); Particula Tech — "Multi-Tenant RAG: Silo, Pool, or Bridge" (2026-07, cites pgvector 0.8.0 iterative scan, embedding-inversion research ~92% recovery, 62–100% leakage study); perfecXion.ai — "How RAG Systems Leak Data Across Tenant Boundaries" (2026-03, semantic cache collisions, hybrid RAG pivot attacks); index-management.org — "Security Boundaries for Vector Data" (2026-07, BYPASSRLS audit, NULL discriminator, seq-scan fallback) — **HIGH confidence, multi-source agreement**
- **pgvector tuning/migration:** Particula Tech — "pgvector HNSW Tuning for 10M+ Rows" (2026-07); selfhost.dev — "pgvector in Production: 2026 Reality Check" (2026-05); tomodahinata.com — "Complete Guide to pgvector Tuning" (2026-06); bigdataboutique — "pgvector in Production" (2026-07); open-techstack — "pgvector vs Qdrant 2026" (2026-04); Qdrant migration docs (embedding-model migration, data-integrity verification); oh-bug.com — "LLM Embedding Index Migration in Production" (2026-07); tianpan.co — "Per-Vector Version Tags" (2026-04); dreaming.press — "Migrate Embedding Models Without Wrecking Retrieval" (2026-06); pgvector official README/CHANGELOG (v0.8.0 iterative scan, defaults) — **HIGH for behavioral claims (multi-source), MEDIUM for exact tuning numbers (e.g., m=32 vs 16, ef_construction 256–512 vs 128–200 — sources disagree; measure on own data)**
- **OCR/PDF:** pdfmux blog (OCR-PDF extraction 2026-06; PDF extraction routing 2026-06; PyMuPDF vs pdfplumber 2026-07); unstract.com — "Extract Tables from PDF" (2024-07, still current); cfgnotes — "PyMuPDF + PaddleOCR-VL hybrid" (2026-05, quality-gate fallback heuristics); subhajitbhar.com — "Extract Data from Scanned PDFs" (2026-03) — **HIGH on scanned-PDF failure modes (multi-source agreement), MEDIUM on exact CER numbers (vendor-benchmarked)**
- **Multi-provider LLM routing:** DevOpsNess — "Multi-Provider LLM Routing" (2026-05); DEV — "Multi-LLM routing failure modes" (2026-07); promptunit.ai — "LLM Provider Failover That Actually Works" (2026-06); niteagent.com — "Multi-Provider LLM Router with Fallback Chains" (2026-06); DEV xidao — "5 Hidden Failure Modes Routing Between 10+ Providers" (2026-05, tokenizer variance, context truncation differences); DevOpsNess gateway post (2026-07, $1,800 runaway incident); storypros.io — "LLM Failover Engineering" (2026-07) — **HIGH confidence (consistent multi-source patterns)**
- **SSE:** server-sent-events.com FastAPI guide (2026-05); FastAPI official SSE docs; markaicode — uvicorn timeout guide (2026-06); DEV martin_palopoli — "End-to-End SSE Through Nginx" (2026-04); blog.authon.dev — "Why your LLM SSE stream dies after 60 seconds" (2026-05); tianpan.co — "The SSE Keep-Alive Your Reverse Proxy Stripped" (2026-06); how2.sh nginx SSE guide (2026-02); python.elitedev.in — FastAPI streaming/backpressure (2026-04) — **HIGH confidence**
- **Go↔Python seams:** ademawan.medium.com — "10 Mistakes in Go External Service Layer" (2026-07, Go client timeouts, retry classification); aakashx.com — "API Contracts in Microservices" (2026-05) and "Service-to-Service Authentication" (2026-06); thelinuxcode.com — Python requests auth patterns (2026-02) — **HIGH confidence**
- **Async jobs/asynq:** hibiken/asynq official docs (v0.26.0, 2026-02 — task states, retries, archived = dead letter, unique tasks, timeout/deadline); oneuptime.com — asynq DLQ guide (2026-01); digitalapplied.com — "Background Jobs and Queues: 2026 Engineering Reference" (2026-06, at-least-once, idempotency, DLQ-as-SLO); gofaq.org — asynq distributed queues (2026-04); redis.io — Redis job queue tutorial (2026-03) — **HIGH confidence**
- **Project context:** `.planning/PROJECT.md`, `docs/plans/AI-platform-for-Academio.md`, `docs/plans/AI-PLATFORM-IMPLEMENTATION-PLAN.md` (phases P0–P6, PGV-01..06, PYE-01..05, PIP-01..02, INT-01..04, OBS-01, SEC-01, TES-01, RET-01..03), `AGENTS.md` (rules B1–B13, F1–F5)

---
*Pitfalls research for: Academio AI Platform (Python ai-engine + pgvector RAG + multi-provider LLM + SSE + doc pipeline)*
*Researched: 2026-07-31*
