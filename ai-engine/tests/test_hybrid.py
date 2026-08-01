"""Hybrid RAG tests (PYE-05, D-12): pure RRF/filters/rerank functions always
run without DB; hybrid_search DB path is covered by the env-gated route tests
in test_search.py. Pure functions keep the suite green without AI_PGVECTOR_DSN.
"""

from app.rag.hybrid import build_filters_where, rrf_merge


def _dense(doc: str, chunk: int, text: str = "dense text", score: float = 0.9) -> dict:
    return {
        "document_id": doc,
        "chunk_index": chunk,
        "text": text,
        "collection": "default",
        "dense_score": score,
    }


def _bm25(doc: str, chunk: int, text: str = "bm25 text", score: float = 0.5) -> dict:
    return {
        "document_id": doc,
        "chunk_index": chunk,
        "text": text,
        "collection": "default",
        "bm25_score": score,
    }


# --- rrf_merge (a)-(d), (g) ---


def test_rrf_same_doc_both_lists_ranks_first() -> None:
    """(a) A doc in BOTH ranked lists outranks docs in only one list."""
    dense = [_dense("a", 0), _dense("b", 0)]
    bm25 = [_dense("a", 0), _dense("c", 0)]
    merged = rrf_merge(dense, bm25)
    assert merged[0]["document_id"] == "a"  # 1/(61) + 1/(61) > 1/(62)
    assert merged[0]["chunk_index"] == 0
    assert {r["document_id"] for r in merged} == {"a", "b", "c"}


def test_rrf_swapping_lists_is_order_invariant() -> None:
    """(b) RRF symmetry: swapping list order yields the identical merged order."""
    dense = [_dense("x", 0), _dense("y", 0), _dense("z", 0)]
    bm25 = [_dense("y", 0), _dense("z", 0)]
    a = rrf_merge(dense, bm25, k=60)
    b = rrf_merge(bm25, dense, k=60)
    assert [r["document_id"] for r in a] == [r["document_id"] for r in b]
    assert [round(r["score"], 6) for r in a] == [round(r["score"], 6) for r in b]


def test_rrf_empty_lists_returns_empty() -> None:
    """(c) Empty inputs -> [] (no crash)."""
    assert rrf_merge([], []) == []
    assert rrf_merge([], [_dense("a", 0)])[0]["document_id"] == "a"


def test_rrf_dedup_sums_scores() -> None:
    """(d) A doc in both lists appears ONCE with the summed RRF score."""
    dense = [_dense("a", 0)]
    bm25 = [_bm25("a", 0)]
    merged = rrf_merge(dense, bm25)
    assert len(merged) == 1
    assert merged[0]["document_id"] == "a"
    # 1/(60+1) from dense rank 1 + 1/(60+1) from bm25 rank 1
    assert abs(merged[0]["score"] - (1 / 61 + 1 / 61)) < 1e-12


def test_rrf_leg_scores_survive_merge() -> None:
    """(g) dense_score/bm25_score survive into merged rows — a row that came
    from each leg keeps its leg score key."""
    dense = [_dense("a", 0, score=0.9), _dense("b", 0, score=0.8)]
    bm25 = [_bm25("c", 0, score=0.5)]
    merged = rrf_merge(dense, bm25)
    by_doc = {r["document_id"]: r for r in merged}
    assert by_doc["a"]["dense_score"] == 0.9
    assert by_doc["b"]["dense_score"] == 0.8
    assert by_doc["c"]["bm25_score"] == 0.5
    assert "dense_score" not in by_doc["c"]
    assert "bm25_score" not in by_doc["a"]


# --- build_filters_where (e)-(f) ---


def test_filters_allowlist_ignores_unknown_keys() -> None:
    """(e) collection kept, evil ignored; params == ["default"]."""
    where, params = build_filters_where(
        [{"key": "collection", "value": "default"}, {"key": "evil", "value": "x"}]
    )
    assert "collection = %s" in where
    assert "evil" not in where
    assert params == ["default"]


def test_filters_chunk_index_str_value_parameterized() -> None:
    """(f) chunk_index filter uses = %s with a str value — never interpolated."""
    where, params = build_filters_where([{"key": "chunk_index", "value": 3}])
    assert "chunk_index = %s" in where
    assert "3" not in where
    assert params == ["3"]  # str() coercion matches the varchar column


def test_filters_none_and_empty_produce_no_clause() -> None:
    where, params = build_filters_where(None)
    assert where == ""
    assert params == []
    where, params = build_filters_where([])
    assert where == ""
    assert params == []
