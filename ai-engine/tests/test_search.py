"""POST /v1/search route tests (PYE-04/PYE-05, D-12).

Validation/rejection paths and the monkeypatched-search test are hermetic.
The full DB path (invalid-schema 400, seeded hybrid retrieval, filters) is
gated on ``AI_PGVECTOR_DSN`` + an existing ``school_1`` tenant schema (Phase 2
migration); the embedding provider is stubbed so the REAL hybrid SQL runs
deterministically without a live AI_OPENAI_API_KEY.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.config import settings as app_settings
from app.db.pool import get_pool
from app.db.vectors import insert_chunks
from app.main import app

LIVE_DB = pytest.mark.skipif(
    not os.getenv("AI_PGVECTOR_DSN"),
    reason="no AI_PGVECTOR_DSN (DB-gated tests skip cleanly, D-12)",
)

VECTOR_1536 = [0.1] * 1536  # non-zero norm, locked dimension (PGV-04a)


class FakeEmbeddingClient:
    """Stands in for app.rag.hybrid.EmbeddingClient (no live key)."""

    def __init__(self) -> None:
        pass

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [list(VECTOR_1536) for _ in texts]


@pytest.fixture
def settings() -> Settings:
    s = Settings(AI_ENGINE_TOKEN="test-token-123")
    # The app's require_token dependency reads the module-level singleton;
    # share the test token with that same instance (mirrors test_documents.py).
    app_settings.AI_ENGINE_TOKEN = s.AI_ENGINE_TOKEN
    return s


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _headers(settings: Settings, schema: str | None = None) -> dict[str, str]:
    h = {"X-AI-Engine-Token": settings.AI_ENGINE_TOKEN}
    if schema is not None:
        h["X-School-Schema"] = schema
    return h


# --- hermetic validation/rejection paths (a)-(e) ---


async def test_search_requires_token(client: AsyncClient) -> None:
    """(a) No service token -> 401 (T-03-04-01)."""
    resp = await client.post("/v1/search", json={"query": "hello"})
    assert resp.status_code == 401


async def test_search_missing_school_header(client: AsyncClient, settings: Settings) -> None:
    """(a) Tenant route without X-School-Schema -> 400 BEFORE any work (D-09)."""
    resp = await client.post(
        "/v1/search",
        json={"query": "hello"},
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "X-School-Schema" in resp.json()["detail"]


async def test_search_empty_query_422(client: AsyncClient, settings: Settings) -> None:
    """(c) Empty query -> 422 (pydantic min_length=1)."""
    resp = await client.post(
        "/v1/search",
        json={"query": ""},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 422


async def test_search_top_k_capped_422(client: AsyncClient, settings: Settings) -> None:
    """(d) top_k > 100 -> 422 (Field le — DoS bound T-03-06-05)."""
    resp = await client.post(
        "/v1/search",
        json={"query": "hello", "top_k": 101},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 422


async def test_search_monkeypatched_hybrid(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(e) hybrid_search stubbed (no DB) -> 200 with citation/score/text and a
    context block built from the canned merged list."""
    canned = [
        {
            "document_id": "doc1",
            "chunk_index": 0,
            "text": "hello academio",
            "collection": "default",
            "score": 0.8,
        },
        {
            "document_id": "doc2",
            "chunk_index": 3,
            "text": "hybrid search works",
            "collection": "default",
            "score": 0.5,
        },
    ]
    monkeypatch.setattr("app.api.search.hybrid_search", AsyncMock(return_value=canned))
    resp = await client.post(
        "/v1/search",
        json={"query": "hello"},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == "hello"
    assert body["schema"] == "school_1"
    assert body["results"][0]["citation"] == "doc1#0"
    assert body["results"][0]["score"] == 0.8
    assert body["results"][0]["text"] == "hello academio"
    assert body["results"][1]["citation"] == "doc2#3"
    assert "[doc1#0]" in body["context"]
    assert "[doc2#3]" in body["context"]


async def test_search_include_context_false(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """include_context=false -> context key present but null."""
    monkeypatch.setattr(
        "app.api.search.hybrid_search",
        AsyncMock(return_value=[{"document_id": "d", "chunk_index": 0, "text": "t", "score": 0.5}]),
    )
    resp = await client.post(
        "/v1/search",
        json={"query": "hello", "include_context": False},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 200
    assert resp.json()["context"] is None


# --- live-DB hybrid retrieval (f)-(g) ---


@LIVE_DB
async def test_search_invalid_schema_regex(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) Invalid schema (school_1x) -> 400 from validate_schema_name
    (T-03-06-01) — needs the DB path because hybrid_search opens the pool
    before the gate (mirrors 03-05 deviation 7)."""
    monkeypatch.setattr("app.rag.hybrid.EmbeddingClient", FakeEmbeddingClient)
    resp = await client.post(
        "/v1/search",
        json={"query": "hello"},
        headers=_headers(settings, schema="school_1x"),
    )
    assert resp.status_code == 400
    assert "must match" in resp.json()["detail"]


@LIVE_DB
async def test_search_hybrid_retrieval_citations(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(f) Seed school_1 with two chunks, hybrid search -> seeded chunk in
    results with a document_id#chunk_index citation; clean up after."""
    monkeypatch.setattr("app.rag.hybrid.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")

    doc_id = str(uuid.uuid4())
    collection = f"test-hybrid-{uuid.uuid4().hex[:8]}"
    chunks = [
        {"index": 0, "text": "academio hybrid search vector database", "embedding": VECTOR_1536},
        {"index": 1, "text": "the second chunk about timetables", "embedding": VECTOR_1536},
    ]
    try:
        inserted = await insert_chunks(
            "school_1", collection, doc_id, chunks, "text-embedding-3-small"
        )
        assert inserted == 2

        resp = await client.post(
            "/v1/search",
            json={
                "query": "academio hybrid search",
                "filters": [{"key": "collection", "value": collection}],
            },
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["schema"] == "school_1"
        hits = [r for r in body["results"] if r["document_id"] == doc_id]
        assert hits, "seeded document must appear in hybrid results"
        assert hits[0]["citation"] == f"{doc_id}#0"
        assert f"[{doc_id}#0]" in body["context"]
        # Hybrid fusion proof: chunk 0 matches BOTH legs (dense + BM25 on the
        # query terms) so RRF lifts it above chunk 1, which only matches the
        # dense leg (identical fake vector). The fused ranking is meaningful.
        ranked_citations = [h["citation"] for h in body["results"]]
        assert ranked_citations.index(f"{doc_id}#0") < ranked_citations.index(f"{doc_id}#1")
    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM school_1.ai_vectors WHERE document_id = %s", (doc_id,)
            )


@LIVE_DB
async def test_search_filters_collection(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(g) Two collections, filter collection=math -> only math chunks returned."""
    monkeypatch.setattr("app.rag.hybrid.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")

    math_id, science_id = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        await insert_chunks(
            "school_1",
            "math",
            math_id,
            [{"index": 0, "text": "algebra quadratic equations", "embedding": VECTOR_1536}],
            "text-embedding-3-small",
        )
        await insert_chunks(
            "school_1",
            "science",
            science_id,
            [{"index": 0, "text": "algebra quadratic equations", "embedding": VECTOR_1536}],
            "text-embedding-3-small",
        )

        # Without a filter both collections match (identical vectors + text).
        resp = await client.post(
            "/v1/search",
            json={"query": "algebra quadratic"},
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200
        doc_ids = {r["document_id"] for r in resp.json()["results"]}
        assert math_id in doc_ids and science_id in doc_ids

        # With collection=math only the math chunk survives (AND filter both legs).
        resp = await client.post(
            "/v1/search",
            json={
                "query": "algebra quadratic",
                "filters": [{"key": "collection", "value": "math"}],
            },
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200
        filtered = {r["document_id"] for r in resp.json()["results"]}
        assert math_id in filtered
        assert science_id not in filtered
    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM school_1.ai_vectors WHERE document_id IN (%s, %s)",
                (math_id, science_id),
            )
