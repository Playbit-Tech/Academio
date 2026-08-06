"""Adversarial cross-tenant probe suite (D-08, D-09).

D-08 requires the Python search/extract entry points to be probed for
cross-tenant leakage. Each DB-gated test seeds a unique marker
(``PRIVATE-FOR-SCHOOL-ONE-<uuid>`` / ``PRIVATE-FOR-SCHOOL-TWO-<uuid>``) into
BOTH tenant schemas and proves a tenant can ONLY ever retrieve its own marker
— through the REAL ASGI routes (POST /v1/search and POST /v1/documents), with
only the embedding provider stubbed (FakeEmbeddingClient) so no live
AI_OPENAI_API_KEY is needed. Assertions fail-loud on any leak.

Gating mirrors test_search.py: tests skip unless ``AI_PGVECTOR_DSN`` is set
(D-12) AND both ``school_1`` and ``school_2`` tenant schemas exist. Schemas
are provisioned by the backend, never by tests; the CI rag-eval workflow
provisions school_1 and MUST ALSO provision school_2 for this suite to run.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from psycopg_pool import AsyncConnectionPool

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

PROBE_COLLECTION = "probe"  # marker collection for the direct-seed probe


class FakeEmbeddingClient:
    """Stands in for EmbeddingClient (rag + documents) with no live key."""

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


# --- DB helpers (mirror test_search.py's get_pool + raw-SQL pattern) ---


async def _require_tenant_schemas(pool: AsyncConnectionPool) -> None:
    """Both tenant schemas must exist, else skip (provisioning is backend-only).

    We never create schemas from a test; the CI rag-eval workflow provisions
    school_1 and MUST ALSO provision school_2 so the adversarial pair can run.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name IN ('school_1', 'school_2') ORDER BY schema_name"
        )
        rows = await cur.fetchall()
    found = {str(r[0]) for r in rows}
    missing = sorted({"school_1", "school_2"} - found)
    if missing:
        pytest.skip(
            "cross-tenant probe requires school_1 AND school_2 tenant schemas; "
            f"missing: {missing} (CI rag-eval must provision school_2 too)"
        )


async def _cleanup_collection(pool: AsyncConnectionPool, schema: str, collection: str) -> None:
    """DELETE every probe row from a tenant schema (teardown, crash-safe)."""
    stmt = sql.SQL("DELETE FROM {}.ai_vectors WHERE collection = %s").format(
        sql.Identifier(schema)
    )
    async with pool.connection() as conn:
        await conn.execute(stmt, (collection,))


async def _count_document(pool: AsyncConnectionPool, schema: str, document_id: str) -> int:
    """Rows for a document id inside one tenant schema (write-path isolation)."""
    stmt = sql.SQL("SELECT count(*) FROM {}.ai_vectors WHERE document_id = %s").format(
        sql.Identifier(schema)
    )
    async with pool.connection() as conn:
        cur = await conn.execute(stmt, (document_id,))
        row = await cur.fetchone()
    return int(row[0]) if row else 0


async def _seed_marker(schema: str, marker: str, document_id: str) -> int:
    """Seed one probe chunk via the real insert_chunks path (collection=probe).

    The marker text carries benign filler words so the chunk is not ONLY the
    marker (searchability + realism); the marker itself is a unique token.
    """
    text = f"{marker} academic attendance records timetable"
    return await insert_chunks(
        schema,
        PROBE_COLLECTION,
        document_id,
        [{"index": 0, "text": text, "embedding": VECTOR_1536}],
        "test",
    )


# --- hermetic gate (c) ---


async def test_schema_header_required(client: AsyncClient, settings: Settings) -> None:
    """(c) Tenant routes without X-School-Schema -> 400, no fallback (D-07/D-09)."""
    resp = await client.post("/v1/search", json={"query": "hello"}, headers=_headers(settings))
    assert resp.status_code == 400
    assert "X-School-Schema" in resp.json()["detail"]

    resp = await client.post(
        "/v1/documents",
        json={"document_path": "/tmp/x.txt"},
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "X-School-Schema" in resp.json()["detail"]


# --- live-DB adversarial probes ---


@LIVE_DB
async def test_cross_tenant_search(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed PRIVATE-FOR-SCHOOL-{ONE,TWO} markers in both schemas; each tenant's
    search must return ONLY its own marker (fail-loud on any leak)."""
    monkeypatch.setattr("app.rag.hybrid.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    await _require_tenant_schemas(pool)

    marker_one = f"PRIVATE-FOR-SCHOOL-ONE-{uuid.uuid4().hex}"
    marker_two = f"PRIVATE-FOR-SCHOOL-TWO-{uuid.uuid4().hex}"
    doc_one = f"probe-one-{uuid.uuid4().hex}"
    doc_two = f"probe-two-{uuid.uuid4().hex}"

    try:
        # Clean slate: a crashed prior run must not leave stale probe rows.
        await _cleanup_collection(pool, "school_1", PROBE_COLLECTION)
        await _cleanup_collection(pool, "school_2", PROBE_COLLECTION)

        assert await _seed_marker("school_1", marker_one, doc_one) == 1
        assert await _seed_marker("school_2", marker_two, doc_two) == 1

        # Search as school_1 for school_2's marker token: school_2's rows
        # physically cannot be in school_1.ai_vectors — prove it fail-loud.
        resp = await client.post(
            "/v1/search",
            json={
                "query": marker_two,
                "filters": [{"key": "collection", "value": PROBE_COLLECTION}],
            },
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["schema"] == "school_1"
        assert doc_two not in {r["document_id"] for r in body["results"]}, (
            "school_2 document leaked into school_1 search results"
        )
        assert marker_two not in body["context"], (
            "school_2 marker text leaked into school_1 search context"
        )
        assert marker_one in body["context"], (
            "school_1 marker must be retrievable from its own search"
        )

        # Symmetric: search as school_2 for school_1's marker token.
        resp = await client.post(
            "/v1/search",
            json={
                "query": marker_one,
                "filters": [{"key": "collection", "value": PROBE_COLLECTION}],
            },
            headers=_headers(settings, schema="school_2"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["schema"] == "school_2"
        assert doc_one not in {r["document_id"] for r in body["results"]}, (
            "school_1 document leaked into school_2 search results"
        )
        assert marker_one not in body["context"], (
            "school_1 marker text leaked into school_2 search context"
        )
        assert marker_two in body["context"], (
            "school_2 marker must be retrievable from its own search"
        )
    finally:
        await _cleanup_collection(pool, "school_1", PROBE_COLLECTION)
        await _cleanup_collection(pool, "school_2", PROBE_COLLECTION)


@LIVE_DB
async def test_cross_tenant_extract_documents(
    client: AsyncClient,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ingest a marker document into each school via the REAL POST /v1/documents
    path (only the embedding provider is stubbed); each school's store must
    contain ONLY its own document id + marker."""
    monkeypatch.setattr("app.documents.pipeline.EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr("app.rag.hybrid.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    await _require_tenant_schemas(pool)

    collection = f"cross-tenant-docs-{uuid.uuid4().hex[:8]}"
    marker_one = f"PRIVATE-FOR-SCHOOL-ONE-{uuid.uuid4().hex}"
    marker_two = f"PRIVATE-FOR-SCHOOL-TWO-{uuid.uuid4().hex}"
    doc_one = f"ingest-one-{uuid.uuid4().hex}"
    doc_two = f"ingest-two-{uuid.uuid4().hex}"

    file_one = tmp_path / "school_one.txt"
    file_two = tmp_path / "school_two.txt"
    file_one.write_text(f"{marker_one} academic attendance records timetable", encoding="utf-8")
    file_two.write_text(f"{marker_two} academic attendance records timetable", encoding="utf-8")

    try:
        # Real ingest into each school (extract -> chunk -> embed -> store).
        resp = await client.post(
            "/v1/documents",
            json={
                "document_path": str(file_one),
                "collection": collection,
                "document_id": doc_one,
            },
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["document_id"] == doc_one
        assert resp.json()["chunks"] > 0

        resp = await client.post(
            "/v1/documents",
            json={
                "document_path": str(file_two),
                "collection": collection,
                "document_id": doc_two,
            },
            headers=_headers(settings, schema="school_2"),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["document_id"] == doc_two
        assert resp.json()["chunks"] > 0

        # Write-path isolation: each document id landed ONLY in its own schema.
        assert await _count_document(pool, "school_1", doc_one) > 0
        assert await _count_document(pool, "school_2", doc_one) == 0
        assert await _count_document(pool, "school_2", doc_two) > 0
        assert await _count_document(pool, "school_1", doc_two) == 0

        # Read-path isolation through the REAL hybrid SQL: school_1 must never
        # surface school_2's ingested marker (and vice versa).
        resp = await client.post(
            "/v1/search",
            json={
                "query": marker_two,
                "filters": [{"key": "collection", "value": collection}],
            },
            headers=_headers(settings, schema="school_1"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert doc_two not in {r["document_id"] for r in body["results"]}, (
            "school_2 ingested document leaked into school_1 search"
        )
        assert marker_two not in body["context"], (
            "school_2 marker text leaked into school_1 search context"
        )
        assert marker_one in body["context"]

        resp = await client.post(
            "/v1/search",
            json={
                "query": marker_one,
                "filters": [{"key": "collection", "value": collection}],
            },
            headers=_headers(settings, schema="school_2"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert doc_one not in {r["document_id"] for r in body["results"]}, (
            "school_1 ingested document leaked into school_2 search"
        )
        assert marker_one not in body["context"], (
            "school_1 marker text leaked into school_2 search context"
        )
        assert marker_two in body["context"]
    finally:
        await _cleanup_collection(pool, "school_1", collection)
        await _cleanup_collection(pool, "school_2", collection)
