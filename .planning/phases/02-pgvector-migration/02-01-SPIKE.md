# 02-01 Spike Report: Nigerian-Language Embedding Adequacy

**Plan:** 02-pgvector-migration / 02-01 (PGV-04a)
**Date:** 2026-08-01
**Test:** `go test ./internal/ai/ -run TestEmbeddingNigerianLanguageAdequacy -v`

## Canon (D-01, locked)

| Property | Value |
|----------|-------|
| Canonical model | `text-embedding-3-small` (OpenAI) |
| Canonical dimension | 1536 (`AI_EMBEDDING_DIM=1536`) |
| HNSW dim cap | 2000 (D-02 — 3072-dim Gemini is NOT the canon) |
| Code lock | `openai.EmbeddingModelTextEmbedding3Small` in `internal/ai/openai.go` |

## Result: SKIPPED (no API key)

**Status:** ⏭️ SKIPPED — `AI_OPENAI_API_KEY` not present in the environment.

**Skip rationale (T-PGV-01-03, accepted disposition):**
The spike test drives the real provider path (`ai.NewProvider` → OpenAI API) and
cannot call the OpenAI Embeddings API without credentials. The environment has
no `AI_OPENAI_API_KEY` (commented out in `backend/.env`), so the test skips
cleanly per the plan's documented behavior.

**Consequence for the canon (PGV-04a gate):**
The locked decision **D-01 stands**: `text-embedding-3-small` (1536-dim) remains
the canonical model. Rationale:

1. It is already the Go pipeline's OpenAI embedding path
   (`openai.EmbeddingModelTextEmbedding3Small`, verified in `openai.go:233`).
2. 1536 ≤ 2000-dim HNSW cap on the `vector` type (D-02).
3. Matches the existing embedding space → no re-embedding of current data.
4. **Pending:** a future eval run WITH a key must confirm semantic adequacy
   (paraphrase > 0.75, unrelated < 0.60) before final sign-off. The eval test
   (`embed_spike_test.go`) is real and runnable — it will surface a blocker on
   the canonical model if thresholds are not met, and will FAIL on a dimension
   mismatch (e.g. 3072-dim Gemini misconfig, T-PGV-01-02).

## How to run the real eval

```bash
cd backend
export AI_OPENAI_API_KEY=sk-...   # or set in backend/.env
go test ./internal/ai/ -run TestEmbeddingNigerianLanguageAdequacy -v
```

Expected outputs: per-pair cosine scores logged via `t.Log`, dimension assertion
== 1536 on every embedding, and PASS only if all paraphrase pairs > 0.75 and all
unrelated pairs < 0.60.

## Gate

No `ai_vectors` DDL has been written anywhere (verified: no matches in
`backend/internal/`). PGV-04a entry blocker remains satisfied — the canon is
locked in config (`AI_EMBEDDING_DIM`) and the adequacy gate is a runnable test.
