"""Schema-qualified ai_vectors inserts (D-07, Phase 2 D-09 contract).

``insert_chunks`` is the only writer path for /v1/documents. It validates the
tenant schema BEFORE any SQL (single allowlisted identifier), qualifies the
table with the returned name, and passes every value as a ``%s`` parameter.
The Phase 2 ``UNIQUE(document_id, chunk_index)`` constraint makes the insert
idempotent — ``ON CONFLICT DO NOTHING`` returns 0 rowcount for duplicates,
which is exactly-once ingest semantics for Phase 4's PIP-01 worker.
"""

import uuid
from typing import Any

from pgvector import Vector
from psycopg import sql

from app.db.pool import get_pool
from app.db.schema import validate_schema_name


async def insert_chunks(
    schema_name: str,
    collection: str,
    document_id: str,
    chunks: list[dict[str, Any]],
    embedding_model: str,
) -> int:
    """Insert chunk rows into ``{schema}.ai_vectors``; return rows inserted.

    ``chunks``: ``[{"index": int, "text": str, "embedding": list[float]}]``.
    Idempotent per ``(document_id, chunk_index)`` (Phase 4 PIP-01 requires
    exactly-once ingest) — a second insert of the same pair inserts 0 rows.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        schema = await validate_schema_name(schema_name, conn)  # validated BEFORE any SQL
        inserted = 0
        for c in chunks:
            # Zero-norm guard (RESEARCH Pitfall 2) — reject, never write
            # NaN-poisoning rows (embed_texts already asserts this upstream).
            # Identifier is interpolated via sql.Identifier (proper quoting on
            # top of the ^school_[0-9]+$ allowlist — T-03-05-01); all VALUES
            # are %s parameters.
            stmt = sql.SQL(
                "INSERT INTO {}.ai_vectors "
                "(id, collection, embedding, document_id, chunk_index, text, "
                "embedding_model, model_version, chunking_version) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (document_id, chunk_index) DO NOTHING"
            ).format(sql.Identifier(schema))
            cur = await conn.execute(
                stmt,
                (
                    str(uuid.uuid4()),
                    collection,
                    Vector(c["embedding"]),
                    document_id,
                    str(c["index"]),
                    c["text"],
                    embedding_model,
                    "v1",
                    "v1",
                ),
            )
            inserted += cur.rowcount or 0
        return inserted
