"""RAG evaluation harness (TES-01): gates on context precision and faithfulness.

The harness loads the golden set (golden.jsonl), runs the REAL hybrid
retrieval path against the seeded corpus (embedding provider stubbed), scores
context precision deterministically, and scores faithfulness with the hermetic
judge stub. Gates: mean context precision >= 0.75, mean faithfulness >= 0.85.

DB-gated tests (retrieval + scoring) skip cleanly without AI_PGVECTOR_DSN;
the golden-set/consistency tests are hermetic and always run.
"""

import json
import os
from pathlib import Path

from conftest import (
    LIVE_DB,
    judge_stub,
    result_to_chunk_ref,
    run_retrieval,
)

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"

CONTEXT_PRECISION_GATE = 0.75
FAITHFULNESS_GATE = 0.85


def load_golden() -> list[dict]:
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_golden_set_size_in_band() -> None:
    """Hermetic: golden set has 50-100 entries (TES-01 / ROADMAP SC3)."""
    n = len(load_golden())
    assert 50 <= n <= 100, f"golden set has {n} entries, expected 50-100"


def test_golden_entries_have_schema() -> None:
    """Hermetic: every golden entry has question/expected_sources/expected_answer_fragments."""
    for entry in load_golden():
        assert "question" in entry and entry["question"].strip()
        assert "expected_sources" in entry and entry["expected_sources"]
        assert "expected_answer_fragments" in entry and entry["expected_answer_fragments"]


def test_golden_sources_reference_corpus_docs() -> None:
    """Hermetic: every expected source ref belongs to a corpus doc (no typos)."""
    from conftest import CORPUS_DOCS

    for entry in load_golden():
        for ref in entry["expected_sources"]:
            doc_id = ref.rsplit("_chunk", 1)[0]
            assert doc_id in CORPUS_DOCS, f"{ref} references unknown corpus doc {doc_id}"


def test_golden_fragments_contained_in_home_chunk() -> None:
    """Hermetic: every fragment is a verbatim substring of the doc AND fully
    contained in the chunk window named by expected_sources (real chunker).

    This is the alignment invariant the generator (tools/corpus_gen.py) is
    held to. If a corpus edit or golden regen breaks it, retrieval cannot
    return the referenced chunk, so the precision gate would be unreliable.
    """
    import re

    from conftest import CORPUS_DOCS

    from app.documents.chunker import chunk_text

    for entry in load_golden():
        q = entry["question"]
        frags = entry["expected_answer_fragments"]
        for ref in entry["expected_sources"]:
            m = re.match(r"^(.*)_chunk(\d+)$", ref)
            assert m, f"{ref} malformed in golden (question: {q})"
            doc_id, chunk_idx = m.group(1), int(m.group(2))
            doc = CORPUS_DOCS[doc_id]
            chunks = chunk_text(doc)
            assert chunk_idx < len(chunks), (
                f"{ref} out of range for {doc_id} ({len(chunks)} chunks); "
                f"regenerate via tools/corpus_gen.py (question: {q})"
            )
            window = chunks[chunk_idx]
            for f in frags:
                assert f in doc, f"fragment {f!r} not in corpus doc {doc_id} (question: {q})"
                assert f in window, (
                    f"fragment {f!r} not contained in {ref} window "
                    f"(question: {q}) — corpus/golden drifted; run "
                    f"`uv run python tests/rag_eval/tools/corpus_gen.py`"
                )


def test_judge_stub_deterministic() -> None:
    """Hermetic: the CI judge is deterministic and bounded 0..1."""
    out1 = judge_stub("q", ["chunk a b"], ["a", "b"])
    out2 = judge_stub("q", ["chunk a b"], ["a", "b"])
    assert out1 == out2
    assert 0.0 <= out1 <= 1.0
    # Fragment-ratio scoring: all found -> 1.0, half -> 0.5, none -> 0.0
    assert judge_stub("q", ["a b"], ["a", "b"]) == 1.0
    assert judge_stub("q", ["a b"], ["a"]) == 1.0
    assert judge_stub("q", ["a b"], ["a", "zz"]) == 0.5
    assert judge_stub("q", ["a b"], ["zz"]) == 0.0


# --- DB-gated scoring gates (skip without AI_PGVECTOR_DSN) ---


@LIVE_DB
async def test_context_precision_gate(seeded_corpus: list[dict]) -> None:
    """Mean context precision across the golden set >= 0.75 (TES-01).

    Context precision per entry = |expected_sources ∩ retrieved_sources| /
    |expected_sources|, where retrieved_sources are the top-K chunk refs from
    the REAL hybrid search.
    """
    assert seeded_corpus, "corpus ingestion produced no docs"

    golden = load_golden()
    precision_scores: list[float] = []

    for entry in golden:
        rows = await run_retrieval("school_1", entry["question"], top_k=8)
        retrieved = {result_to_chunk_ref(r) for r in rows}
        expected = set(entry["expected_sources"])
        if not expected:
            continue
        hits = len(expected & retrieved)
        precision_scores.append(hits / len(expected))

    assert precision_scores, "no golden entries scored"
    mean = sum(precision_scores) / len(precision_scores)
    worst = sorted(
        zip(precision_scores, [e["question"] for e in golden], strict=True)
    )[:3]
    assert mean >= CONTEXT_PRECISION_GATE, (
        f"context precision {mean:.3f} < {CONTEXT_PRECISION_GATE} (worst: {worst})"
    )


@LIVE_DB
async def test_faithfulness_gate(seeded_corpus: list[dict]) -> None:
    """Mean faithfulness across the golden set >= 0.85 (TES-01).

    Faithfulness per entry = judge_stub(question, retrieved chunk texts,
    expected_answer_fragments). CI uses the deterministic stub; the real
    LLM-as-judge runs nightly (deferred).
    """
    assert seeded_corpus, "corpus ingestion produced no docs"

    golden = load_golden()
    faithfulness_scores: list[float] = []

    for entry in golden:
        rows = await run_retrieval("school_1", entry["question"], top_k=8)
        chunk_texts = [str(r.get("text", "")) for r in rows]
        score = judge_stub(entry["question"], chunk_texts, entry["expected_answer_fragments"])
        faithfulness_scores.append(score)

    assert faithfulness_scores, "no golden entries scored"
    mean = sum(faithfulness_scores) / len(faithfulness_scores)
    assert mean >= FAITHFULNESS_GATE, (
        f"faithfulness {mean:.3f} < {FAITHFULNESS_GATE}"
    )


@LIVE_DB
async def test_hermetic_no_live_key(seeded_corpus: list[dict]) -> None:
    """The eval runs with a stubbed embedding provider — no live API key needed."""
    assert not os.getenv("AI_OPENAI_API_KEY"), (
        "eval must run without a live AI_OPENAI_API_KEY (embedding stubbed)"
    )
    # If the DSN is set and corpus seeded, retrieval works end-to-end.
    assert seeded_corpus
