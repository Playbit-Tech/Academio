"""Tenant DB layer tests — schema gate + idempotent insert (D-07/D-12).

Regex/validation tests are hermetic (no DSN, no DB). Live tests are gated on
``AI_PGVECTOR_DSN`` and skip cleanly when absent (D-12) — the existence and
insert tests require the real shared-postgres with a ``school_1`` tenant
schema (Phase 2 migration).
"""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings as app_settings
from app.db.pool import get_pool
from app.db.schema import validate_schema_name
from app.db.vectors import insert_chunks
from app.main import app

LIVE_DB = pytest.mark.skipif(
    not os.getenv("AI_PGVECTOR_DSN"),
    reason="no AI_PGVECTOR_DSN (DB-gated tests skip cleanly, D-12)",
)

EMBEDDING = "text-embedding-3-small"
VECTOR_1536 = [0.1] * 1536  # non-zero norm, locked dimension (PGV-04a)


async def test_validate_schema_name_none_raises() -> None:
    """(a) Missing header -> ValueError BEFORE any SQL (T-03-05-02)."""
    with pytest.raises(ValueError, match="X-School-Schema"):
        await validate_schema_name(None, AsyncMock())


@pytest.mark.parametrize(
    "bad",
    [
        "school_",
        "school_01x",
        "SCHOOL_1",
        "public",
        "school_1; DROP TABLE",
        "school_1.sql",
        " school_1",
    ],
)
async def test_validate_schema_name_rejects_bad_names(bad: str) -> None:
    """(b) Regex gate rejects everything that is not ^school_[0-9]+$ (T-03-05-01)."""
    with pytest.raises(ValueError, match="must match"):
        await validate_schema_name(bad, AsyncMock())


async def test_validate_schema_name_rejects_nonexistent() -> None:
    """(c) Valid regex but non-existent schema -> ValueError (existence check)."""
    conn = AsyncMock()
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(ValueError, match="does not exist"):
        await validate_schema_name("school_999999", conn)
    conn.execute.assert_called_once()  # exactly one existence probe, no SQL fallback


@LIVE_DB
async def test_validate_schema_name_live_school_1() -> None:
    """(d) Live: existing school_1 returns the validated name unchanged."""
    pool = await get_pool()
    async with pool.connection() as conn:
        assert await validate_schema_name("school_1", conn) == "school_1"


@LIVE_DB
async def test_insert_chunks_idempotent() -> None:
    """(e) Live: same (document_id, chunk_index) twice -> 0 rows on re-insert."""
    pool = await get_pool()
    # Confirm the tenant schema actually exists before writing (D-07 gate).
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'school_1'"
        )
        if await cur.fetchone() is None:
            pytest.skip("school_1 tenant schema does not exist")

    doc_id = str(uuid.uuid4())
    chunks = [{"index": 0, "text": "hello academio", "embedding": VECTOR_1536}]
    try:
        first = await insert_chunks("school_1", "test", doc_id, chunks, EMBEDDING)
        second = await insert_chunks("school_1", "test", doc_id, chunks, EMBEDDING)
        assert first == 1
        assert second == 0  # ON CONFLICT DO NOTHING -> exactly-once (PIP-01)
    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM school_1.ai_vectors WHERE document_id = %s", (doc_id,)
            )


@LIVE_DB
async def test_search_malformed_schema_400_no_fallback() -> None:
    """(f) Live: malformed X-School-Schema -> 400 (D-06 no-fallback).

    The API layer must reject a malformed schema with 400 — never silently
    default the schema to something else. ``get_pool`` runs before the regex
    gate inside hybrid_search, so this is DB-gated; the regex itself is
    exercised hermetically by ``test_validate_schema_name_rejects_bad_names``.
    """
    app_settings.AI_ENGINE_TOKEN = "test-token-123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for bad in ("not_a_schema", "school_abc", "school_1; DROP TABLE"):
            resp = await c.post(
                "/v1/search",
                json={"query": "hello"},
                headers={
                    "X-AI-Engine-Token": app_settings.AI_ENGINE_TOKEN,
                    "X-School-Schema": bad,
                },
            )
            assert resp.status_code == 400, f"{bad}: got {resp.status_code}"
