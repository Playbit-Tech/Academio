"""RAG eval fixtures (TES-01): seeded corpus, judge stub, real retrieval path.

The harness proves retrieval quality deterministically. Golden entries
(golden.jsonl) reference chunk identifiers of the form ``{doc_id}_chunk{N}``
and the corpus documents are authored so the referenced chunk index carries
the answering text (the same invariant ``test_context_precision_gate``
verifies via ``expected_sources`` and
``test_golden_fragments_contained_in_home_chunk`` guards hermetically).

The corpus text is assembled by ``tests/rag_eval/tools/corpus_gen.py``
(answer sections placed at target chunk offsets, padded with filler) and
IMPORTED here as ``CORPUS_DOCS`` — a single source of truth shared with the
golden-set generator, so the two can never drift apart.

The retrieval path is the REAL pipeline: extract -> chunk -> embed -> store ->
hybrid search (``ingest_document`` -> ``hybrid_search``), monkeypatching ONLY
the embedding provider so the real hybrid SQL runs deterministically without a
live AI_OPENAI_API_KEY.

FakeEmbeddingClient emits a deterministic content-overlap vector: each
lower-cased alphanumeric token (stopwords dropped) is mapped through a
token->dim table built from the corpus vocabulary (965 tokens, sorted, one
dimension each — well under the 1536-dim contract, so ZERO hash collisions),
then L2-normalised. This is deliberate: a constant vector would rank every
chunk equal and the RRF fusion would be meaningless; a raw md5 hash loses to
collision noise; the vocab table makes the dense leg EXACTLY content-token
overlap, so the dense leg and the BM25 leg (ts_rank) AGREE on the answer
chunk and the fused top-K is deterministic AND meaningful (see TES-01
SUMMARY note). Out-of-vocabulary query tokens are ignored — they occur in no
chunk, so they cannot help ranking.
"""

import math
import os
import re
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from app.config import settings
from app.documents.pipeline import ingest_document
from app.rag.hybrid import hybrid_search

LIVE_DB = pytest.mark.skipif(
    not os.getenv("AI_PGVECTOR_DSN"),
    reason="no AI_PGVECTOR_DSN (DB-gated tests skip cleanly, D-12)",
)

DIM = 1536  # locked vector contract (PGV-04a)

_WORD_RE = re.compile(r"[a-z0-9]+")

# English stopwords dropped from the fake embeddings so the dense leg carries
# content signal instead of common-word overlap (mirrors the tsvector/tsquery
# stopword behaviour of the BM25 leg).
_STOPWORDS = frozenset(
    """
    a an the and or but not no so as of to in on at for with by from than that
    this these those it its he she they them we you i me my our their his her
    there here what which who whom whose when where why how is are was were be
    been being am do does did done will would shall should can could may might
    must have has had about into over under between among through during before
    after above below up down out off again further then once
    """.split()
)

_TOKEN_DIM: dict[str, int] | None = None  # built lazily from the corpus


def _build_token_dim() -> None:
    """Map every corpus content token to a unique dim (sorted, deterministic).

    The corpus vocabulary (~965 tokens) fits comfortably in DIM=1536, so the
    mapping is injective: two chunks share a dim ONLY when they share the
    token, which makes cosine similarity exact content-token overlap.
    """
    global _TOKEN_DIM
    tokens = sorted(
        {
            token
            for text in CORPUS_DOCS.values()
            for token in _WORD_RE.findall(text.lower())
            if token not in _STOPWORDS
        }
    )
    _TOKEN_DIM = {token: i for i, token in enumerate(tokens)}


def _keyword_vector(text: str) -> list[float]:
    """Deterministic content-overlap vector (stopword-filtered, L2-normalised)."""
    global _TOKEN_DIM
    if _TOKEN_DIM is None:
        _build_token_dim()
    vec = [0.0] * DIM
    dims = _TOKEN_DIM
    assert dims is not None  # _build_token_dim() ran above
    for token in _WORD_RE.findall(text.lower()):
        if token in _STOPWORDS:
            continue
        dim = dims.get(token)  # OOV tokens occur in no chunk -> ignore
        if dim is not None:
            vec[dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        raise ValueError("zero-norm embedding rejected (cosine NaN risk)")
    return [v / norm for v in vec]


class FakeEmbeddingClient:
    """Deterministic embedding stub (no live key): keyword-overlap vectors.

    Mirrors test_search.py's shape (async ``embed_texts`` returning 1536-dim
    vectors) but derives each vector from the token content so the dense leg
    is meaningful. Used for BOTH ingest and hybrid_search in this eval.
    """

    def __init__(self) -> None:
        pass

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_keyword_vector(t) for t in texts]


# Golden entries reference doc_id prefixes; each doc is authored so the
# referenced chunk index carries the answering text. The corpus is assembled
# programmatically by tests/rag_eval/tools/corpus_gen.py (answer sections placed
# at target chunk offsets, padded with filler) — conftest imports the SAME dict
# from the tool so the corpus and golden.jsonl can never drift apart. If you need
# to change corpus content, edit the tool and run:
#   uv run python tests/rag_eval/tools/corpus_gen.py
# (the hermetic test test_golden_fragments_contained_in_home_chunk guards it).
from tools.corpus_gen import CORPUS as CORPUS_DOCS  # noqa: E402


def corpus_docs() -> list[dict]:
    """The school-topic corpus golden entries reference (doc_id -> text)."""
    return [{"document_id": k, "text": v} for k, v in CORPUS_DOCS.items()]


def judge_stub(question: str, retrieved_chunks: list[str], expected_fragments: list[str]) -> float:
    """Deterministic hermetic faithfulness scorer (TES-01, CI judge).

    Returns the FRACTION of expected answer fragments found in the retrieved
    chunks' text: hits / len(expected_fragments). This is the standard
    fragment-based faithfulness measure and keeps single-fragment entries on
    the same 0..1 scale as multi-fragment ones (a raw 0.9/0.6/0.3 step
    function caps every one-fragment question at 0.6, making a 0.85 mean gate
    mathematically unreachable). The real LLM-as-judge runs nightly
    (deferred) — CI uses this stub so the gate is deterministic.
    """
    lowered = " ".join(retrieved_chunks).lower()
    if not expected_fragments:
        return 0.0
    hits = sum(1 for f in expected_fragments if f.lower() in lowered)
    return hits / len(expected_fragments)


def chunk_ref(doc_id: str, chunk_index: int) -> str:
    """Translate a hybrid result to the golden-set chunk reference format."""
    return f"{doc_id}_chunk{chunk_index}"


def result_to_chunk_ref(row: dict) -> str:
    """Map a hybrid_search result row {document_id, chunk_index, ...} to a ref."""
    return chunk_ref(row["document_id"], row["chunk_index"])


@pytest.fixture(scope="session")
async def seeded_corpus() -> AsyncIterator[list[dict]]:
    """Ingest all corpus docs into school_1 (session-scoped, real pipeline).

    Uses the REAL extract -> chunk -> embed (stubbed) -> store path. Requires
    AI_PGVECTOR_DSN + an existing school_1 tenant schema (Phase 2 migration);
    tests using this fixture are marked LIVE_DB so they skip cleanly when the
    DSN is absent. Ingested docs are deleted from the tenant schema on teardown
    so repeated runs do not accumulate duplicate vectors.
    """
    settings.AI_ENGINE_TOKEN = "test-token-123"
    inserted: list[dict] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for d in corpus_docs():
                path = Path(tmp) / f"{uuid.uuid4().hex}.txt"
                path.write_text(d["text"], encoding="utf-8")
                result = await ingest_document(
                    str(path),
                    schema_name="school_1",
                    collection="rag_eval",
                    document_id=d["document_id"],
                )
                inserted.append({"document_id": d["document_id"], "chunks": result["chunks"]})
        yield inserted
    finally:
        # Cleanup: remove eval vectors so re-runs stay idempotent.
        from app.db.pool import get_pool

        try:
            pool = await get_pool()
            async with pool.connection() as conn:
                await conn.execute(
                    "DELETE FROM school_1.ai_vectors WHERE collection = %s",
                    ("rag_eval",),
                )
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def patch_embedding() -> Iterator[None]:
    """Patch EmbeddingClient with the deterministic stub for the WHOLE session.

    Session-scoped + autouse so the session-scoped ``seeded_corpus`` ingest and
    EVERY retrieval run through the stub. A function-scoped patch would race
    the session-scoped ingest (seeded_corpus sets up before the test's
    per-test fixtures), which is exactly the failure this avoids. Manual
    setattr/restore because pytest's ``monkeypatch`` is function-scoped only.
    """
    import app.documents.pipeline as pipeline_mod
    import app.rag.hybrid as hybrid_mod

    orig_pipeline = pipeline_mod.EmbeddingClient
    orig_hybrid = hybrid_mod.EmbeddingClient
    pipeline_mod.EmbeddingClient = FakeEmbeddingClient
    hybrid_mod.EmbeddingClient = FakeEmbeddingClient
    try:
        yield
    finally:
        pipeline_mod.EmbeddingClient = orig_pipeline
        hybrid_mod.EmbeddingClient = orig_hybrid


async def run_retrieval(schema_name: str, question: str, top_k: int = 8) -> list[dict]:
    """Run hybrid search for one question and return the top-K result rows."""
    merged = await hybrid_search(schema_name, question, None, top_k=top_k)
    return merged
