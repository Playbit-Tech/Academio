"""Document route tests (PYE-04, D-12) — env-gated DB pipeline.

``/v1/extract`` and the X-School-Schema rejection paths are hermetic. The
full extract -> chunk -> embed -> store pipeline test is gated on
``AI_PGVECTOR_DSN`` + an existing ``school_1`` tenant schema (Phase 2
migration); the embedding provider is stubbed (no live AI_OPENAI_API_KEY) so
the REAL DB write path is exercised deterministically.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.config import settings as app_settings
from app.db.pool import get_pool
from app.main import app

LIVE_DB = pytest.mark.skipif(
    not os.getenv("AI_PGVECTOR_DSN"),
    reason="no AI_PGVECTOR_DSN (DB-gated tests skip cleanly, D-12)",
)

VECTOR_1536 = [0.1] * 1536  # non-zero norm, locked dimension (PGV-04a)


class FakeEmbeddingClient:
    """Stands in for app.documents.pipeline.EmbeddingClient (no live key)."""

    def __init__(self) -> None:
        pass

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [list(VECTOR_1536) for _ in texts]


@pytest.fixture
def settings() -> Settings:
    s = Settings(AI_ENGINE_TOKEN="test-token-123")
    # The app's require_token dependency reads the module-level singleton;
    # share the test token with that same instance (mirrors test_health.py).
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


async def test_documents_requires_token(client: AsyncClient) -> None:
    """(a) No service token -> 401 (T-03-04-01)."""
    resp = await client.post("/v1/documents", json={"document_path": "/tmp/x.txt"})
    assert resp.status_code == 401


async def test_documents_missing_school_header(client: AsyncClient, settings: Settings) -> None:
    """Tenant route without X-School-Schema -> 400 BEFORE any work (D-09)."""
    resp = await client.post(
        "/v1/documents",
        json={"document_path": "/tmp/x.txt"},
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "X-School-Schema" in resp.json()["detail"]


@LIVE_DB
async def test_documents_invalid_schema_regex(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid schema (school_1x) -> 400 from validate_schema_name (T-03-05-01)."""
    monkeypatch.setattr("app.documents.pipeline.EmbeddingClient", FakeEmbeddingClient)
    p = tmp_path / "doc.txt"
    p.write_text("academio tenant gate test", encoding="utf-8")
    resp = await client.post(
        "/v1/documents",
        json={"document_path": str(p)},
        headers=_headers(settings, schema="school_1x"),
    )
    assert resp.status_code == 400
    assert "must match" in resp.json()["detail"]


async def test_documents_nonexistent_file(
    client: AsyncClient, settings: Settings, tmp_path: Path
) -> None:
    """Valid header but missing file -> 400 (extract_document ValueError)."""
    missing = tmp_path / "nope.txt"
    resp = await client.post(
        "/v1/documents",
        json={"document_path": str(missing)},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 400
    assert "file not found" in resp.json()["detail"]


@LIVE_DB
async def test_documents_pipeline_store(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full pipeline: extract -> chunk -> embed -> store in school_1 (one call)."""
    monkeypatch.setattr("app.documents.pipeline.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")

    p = tmp_path / "ingest.txt"
    p.write_text("Academio document intelligence pipeline ingest test. " * 30, encoding="utf-8")

    first = await client.post(
        "/v1/documents",
        json={"document_path": str(p), "collection": "test-collection"},
        headers=_headers(settings, schema="school_1"),
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "success"
    assert body["chunks"] > 0
    doc_id = body["document_id"]
    assert doc_id

    # Rows actually landed in the tenant schema.
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT count(*) FROM school_1.ai_vectors WHERE document_id = %s", (doc_id,)
        )
        (row_count,) = (await cur.fetchone()) or (0,)
    assert row_count == body["chunks"]

    # Re-POST is a fresh document (new uuid) and stores again (PIP-01 idempotent
    # per document_id, not per content — exactly-once per ingest call).
    second = await client.post(
        "/v1/documents",
        json={"document_path": str(p), "collection": "test-collection"},
        headers=_headers(settings, schema="school_1"),
    )
    assert second.status_code == 200
    assert second.json()["document_id"] != doc_id
    assert second.json()["chunks"] > 0

    # Cleanup both documents.
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM school_1.ai_vectors WHERE document_id IN (%s, %s)",
            (doc_id, second.json()["document_id"]),
        )


async def test_ingest_document_no_text_passthrough_unit(tmp_path: Path) -> None:
    """(D-02) Ungated unit test — no-text path echoes the caller document_id.

    No DB needed: the no-text branch returns before touching the pool, so this
    runs everywhere (no AI_PGVECTOR_DSN gate).
    """
    from app.documents.pipeline import ingest_document

    p = tmp_path / "empty.txt"
    p.write_text("   ", encoding="utf-8")  # whitespace-only -> 0 chunks
    res = await ingest_document(str(p), "school_1", document_id="fixed-id")
    assert res["status"] == "success"
    assert res["document_id"] == "fixed-id"
    assert res["chunks"] == 0


async def test_documents_no_text_echoes_document_id(
    client: AsyncClient, settings: Settings, tmp_path: Path
) -> None:
    """(D-02) Route-level: optional document_id passes through on a no-text file."""
    p = tmp_path / "blank.txt"
    p.write_text("", encoding="utf-8")
    resp = await client.post(
        "/v1/documents",
        json={"document_path": str(p), "collection": "default", "document_id": "fixed-id"},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_id"] == "fixed-id"
    assert body["chunks"] == 0


@LIVE_DB
async def test_documents_idempotent_retry_same_document_id(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(D-02, ROADMAP criterion 4) Re-POSTing the same document_id is a no-op.

    A worker crash mid-ingest followed by a retry with the SAME document_id
    must hit ON CONFLICT (document_id, chunk_index) DO NOTHING — inserted 0
    rows, no duplicate vectors.
    """
    monkeypatch.setattr("app.documents.pipeline.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")
        # Clean slate: stale rows from an interrupted run must not skew the counts.
        await conn.execute("DELETE FROM school_1.ai_vectors WHERE document_id = 'fixed-id'")

    p = tmp_path / "retry.txt"
    p.write_text("Academio idempotent ingest retry test. " * 20, encoding="utf-8")

    first = await client.post(
        "/v1/documents",
        json={
            "document_path": str(p),
            "collection": "test-collection",
            "document_id": "fixed-id",
        },
        headers=_headers(settings, schema="school_1"),
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["document_id"] == "fixed-id"
    assert body["chunks"] > 0

    # Retry with the SAME document_id (the worker restart scenario) — no-op.
    second = await client.post(
        "/v1/documents",
        json={
            "document_path": str(p),
            "collection": "test-collection",
            "document_id": "fixed-id",
        },
        headers=_headers(settings, schema="school_1"),
    )
    assert second.status_code == 200, second.text
    assert second.json()["document_id"] == "fixed-id"
    assert second.json()["chunks"] == 0

    async with pool.connection() as conn:
        await conn.execute("DELETE FROM school_1.ai_vectors WHERE document_id = 'fixed-id'")


@LIVE_DB
async def test_documents_default_uuid4_document_id(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(D-02 regression) No document_id -> uuid4-shaped id (Phase 3 default intact)."""
    monkeypatch.setattr("app.documents.pipeline.EmbeddingClient", FakeEmbeddingClient)
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")

    p = tmp_path / "regress.txt"
    p.write_text("Academio default document id regression test. " * 20, encoding="utf-8")

    resp = await client.post(
        "/v1/documents",
        json={"document_path": str(p), "collection": "test-collection"},
        headers=_headers(settings, schema="school_1"),
    )
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["document_id"]
    assert doc_id
    assert str(uuid.UUID(doc_id)) == doc_id  # uuid4-shaped (Phase 3 default preserved)

    async with pool.connection() as conn:
        await conn.execute("DELETE FROM school_1.ai_vectors WHERE document_id = %s", (doc_id,))


async def test_extract_requires_token(client: AsyncClient) -> None:
    """/v1/extract is token-protected (service seam parity)."""
    resp = await client.post("/v1/extract", json={"document_path": "/tmp/x.txt"})
    assert resp.status_code == 401


async def test_extract_route_parses_txt(
    client: AsyncClient, settings: Settings, tmp_path: Path
) -> None:
    """Go ExtractRequest seam: pure parse, no tenant header required."""
    p = tmp_path / "seam.txt"
    p.write_text("extract seam", encoding="utf-8")
    resp = await client.post(
        "/v1/extract",
        json={"document_path": str(p)},
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["pages"] == 1
    assert body["chars"] == len("extract seam")


async def test_extract_path_outside_uploads_rejected(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F2: with AI_UPLOADS_DIR set, a path outside the volume -> 400."""
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(app_settings, "AI_UPLOADS_DIR", str(root))
    outside = tmp_path / "outside.txt"
    outside.write_text("outside volume", encoding="utf-8")
    resp = await client.post(
        "/v1/extract",
        json={"document_path": str(outside)},
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "AI_UPLOADS_DIR" in resp.json()["detail"]


async def test_extract_path_within_uploads_allowed(
    client: AsyncClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F2: a path inside the volume still works."""
    root = tmp_path / "uploads"
    root.mkdir()
    monkeypatch.setattr(app_settings, "AI_UPLOADS_DIR", str(root))
    inside = root / "doc.txt"
    inside.write_text("inside volume", encoding="utf-8")
    resp = await client.post(
        "/v1/extract",
        json={"document_path": str(inside)},
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
