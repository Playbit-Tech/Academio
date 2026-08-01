"""Lazy AsyncConnectionPool singleton (D-07).

DSN is read from the environment ONLY (``AI_PGVECTOR_DSN``) — never hardcoded
(RESEARCH Pitfall 4, Rule B6 spirit). The pgvector type adapter is registered
per connection via ``configure=register_vector_async`` so ``pgvector.Vector``
values round-trip without per-query registration (RESEARCH Pattern 2,
live-verified). The pool is opened lazily so tests without a DSN never
construct it (D-12 env-gated skips). max_size=4 bounds concurrent tenant
connections (T-03-05-08).
"""

from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from app.config import settings

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        if not settings.AI_PGVECTOR_DSN:
            raise RuntimeError("AI_PGVECTOR_DSN is not configured")
        _pool = AsyncConnectionPool(
            settings.AI_PGVECTOR_DSN,
            open=False,
            configure=register_vector_async,
            min_size=1,
            max_size=4,
        )
        await _pool.open()
        await _pool.wait()
    return _pool
