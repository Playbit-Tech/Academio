"""Hybrid retrieval (D-06): dense pgvector HNSW `<=>` + PostgreSQL `ts_rank`
BM25 fused with Reciprocal Rank Fusion (RRF, k=60), scoped to a validated
tenant schema (D-07/D-09).

Every request runs BOTH legs inside ONE pooled connection so the schema gate
(``validate_schema_name``) executes exactly once, before any SQL. The only
interpolated identifier is the validated schema name, composed via
``sql.Identifier`` (defense-in-depth quoting on top of the ``^school_[0-9]+$``
allowlist — T-03-06-01/T-03-06-02); every other value is a ``%s`` parameter.
Metadata filters are allowlisted AND-clauses (T-03-06-03); unknown filter keys
are silently ignored, never interpolated.

Score parity with the Go seam (backend/internal/ai/vector/pgvector.go:244):
dense score = ``1 - (embedding <=> %s)``, ordered by ``embedding <=> %s`` so
the ``vector_cosine_ops`` HNSW index applies (T-03-06-06). The query embedding
is zero-norm rejected by ``embed_texts`` BEFORE SQL runs (RESEARCH Pitfall 2).
"""

from typing import Any, LiteralString, cast

from pgvector import Vector
from psycopg import sql

from app.db.pool import get_pool
from app.db.schema import validate_schema_name
from app.providers.embedding import EmbeddingClient

RRF_K = 60  # D-06: RRF constant (standard default)
DENSE_LIMIT = 20  # candidates per leg
BM25_LIMIT = 20

_FILTER_ALLOWLIST = {"collection", "document_id", "embedding_model", "chunk_index"}


def rrf_merge(dense: list[dict], bm25: list[dict], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)) across both ranked
    lists. Pure function — unit-testable without DB (D-12)."""
    scores: dict[tuple, float] = {}
    seen: dict[tuple, dict] = {}
    for lst in (dense, bm25):
        for rank, row in enumerate(lst, start=1):
            key = (row["document_id"], row["chunk_index"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in seen:
                seen[key] = {
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "collection": row.get("collection", "default"),
                    **{k2: v for k2, v in row.items() if k2.endswith("_score")},
                }
    merged = [dict(seen[key], score=s) for key, s in scores.items()]
    merged.sort(key=lambda r: r["score"], reverse=True)
    return merged


def build_filters_where(filters: list[dict] | None) -> tuple[str, list[Any]]:
    """Metadata AND filters (D-06): allowlisted keys collection/document_id/
    embedding_model/chunk_index. Values ALWAYS parameterized (%s). Unknown keys
    are ignored (never interpolated — T-03-06-03)."""
    clauses: list[str] = []
    params: list[Any] = []
    for f in filters or []:
        if f.get("key") in _FILTER_ALLOWLIST:
            clauses.append(f"{f['key']} = %s")
            params.append(str(f["value"]))
    where = " AND " + " AND ".join(clauses) if clauses else ""
    return where, params


async def hybrid_search(
    schema_name: str,
    query: str,
    filters: list[dict] | None = None,
    top_k: int = 10,
    language: str = "english",
) -> list[dict]:
    """Hybrid dense + BM25 search with RRF merge (k=60), schema-gated (D-06)."""
    pool = await get_pool()
    query_vec = (await EmbeddingClient().embed_texts([query]))[0]  # 1536 asserted; zero-norm -> 400
    where, fparams = build_filters_where(filters)
    async with pool.connection() as conn:
        schema = await validate_schema_name(schema_name, conn)  # gate BEFORE any SQL (D-07)

        # Dense leg — parity with pgvector.go:244-248; HNSW vector_cosine_ops
        # where contains ONLY allowlisted keys + %s placeholders (T-03-06-03);
        # cast to LiteralString for sql.SQL — schema is the only interpolated
        # identifier and it is composed via sql.Identifier below.
        where_sql = cast(LiteralString, where)
        dense_stmt = sql.SQL(
            "SELECT document_id, chunk_index, text, collection, "
            "1 - (embedding <=> %s) AS score "
            "FROM {}.ai_vectors WHERE 1=1{} "
            "ORDER BY embedding <=> %s LIMIT %s"
        ).format(sql.Identifier(schema), sql.SQL(where_sql))
        dense: list[dict] = []
        cur = await conn.execute(
            dense_stmt, [Vector(query_vec), *fparams, Vector(query_vec), DENSE_LIMIT]
        )
        for row in await cur.fetchall():
            dense.append(
                {
                    "document_id": row[0],
                    "chunk_index": int(row[1]),
                    "text": row[2],
                    "collection": row[3],
                    "dense_score": float(row[4]),
                }
            )

        # BM25 leg — ts_rank over runtime to_tsvector (D-06, RESEARCH Pattern 2)
        bm25_stmt = sql.SQL(
            "SELECT document_id, chunk_index, text, collection, "
            "ts_rank(to_tsvector(%s, text), plainto_tsquery(%s, %s)) AS score "
            "FROM {}.ai_vectors WHERE 1=1{} "
            "ORDER BY score DESC LIMIT %s"
        ).format(sql.Identifier(schema), sql.SQL(where_sql))
        bm25: list[dict] = []
        cur = await conn.execute(
            bm25_stmt, [language, language, query, *fparams, BM25_LIMIT]
        )
        for row in await cur.fetchall():
            bm25.append(
                {
                    "document_id": row[0],
                    "chunk_index": int(row[1]),
                    "text": row[2],
                    "collection": row[3],
                    "bm25_score": float(row[4]),
                }
            )
    return rrf_merge(dense, bm25)[:top_k]
