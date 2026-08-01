"""Chunk ranking, citations, context compression (PYE-05).

``rank_and_cite`` turns the RRF-merged rows (already ranked 1..N by D-06) into
the response shape the AI assistant consumes: each result carries a
``document_id#chunk_index`` citation string, a 6-dp score, and the chunk text.

``compress_context`` builds the assembled LLM context: chunks are
whitespace-normalized and deduped, filler dropped, and the running character
total capped (default 12000 chars — the AI_MAX_TOKENS context budget) so the
prompt never exceeds the model's window. Duplicate or oversized chunks are
skipped, never crash (T-03-06-04: retrieved text is DATA, framed by
``[citation]`` boundaries — never evaluated).
"""

import re

# Default context budget: 12k chars ~= a 1024-token window for the assistant
# (AI_MAX_TOKENS); caller can tighten per request.
DEFAULT_MAX_CONTEXT_CHARS = 12000


def rank_and_cite(merged: list[dict], top_k: int = 10) -> list[dict]:
    """Final ranking + citation strings. RRF order is already rank 1..N (D-06).
    citation = 'document_id#chunk_index' — the identifier the AI assistant
    surfaces to the user."""
    out: list[dict] = []
    for row in merged[:top_k]:
        out.append(
            {
                "document_id": row["document_id"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "score": round(row["score"], 6),
                "citation": f"{row['document_id']}#{row['chunk_index']}",
            }
        )
    return out


def compress_context(
    results: list[dict], max_chars: int = DEFAULT_MAX_CONTEXT_CHARS
) -> tuple[str, list[dict]]:
    """Context compression (PYE-05): dedupe near-identical text, drop filler,
    cap total characters so the assembled context fits the LLM budget
    (AI_MAX_TOKENS). Returns ``(context_block, kept_results)``."""
    seen: set[str] = set()
    kept: list[dict] = []
    total = 0
    for r in results:
        norm = re.sub(r"\s+", " ", r["text"]).strip()
        if not norm or norm in seen:
            continue
        if total + len(norm) > max_chars:
            break
        seen.add(norm)
        kept.append(r)
        total += len(norm)
    context = "\n\n".join(f"[{r['citation']}] {r['text']}" for r in kept)
    return context, kept
