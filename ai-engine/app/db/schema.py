"""THE tenant gate (D-07/D-09, ROADMAP criterion 4 — no fallback).

``validate_schema_name`` is the single allowlist for schema identifiers: the
caller may interpolate its return value into a qualified table name ONLY
after this function returns it. The regex ``^school_[0-9]+$`` rejects anything
that is not a plain tenant schema id, and the ``information_schema.schemata``
existence check rejects valid-looking names that do not exist. Everything else
in a query must be a ``%s`` parameter (T-03-05-01, T-03-05-02).

The connection is passed in (from the pooled connection context) so the
existence check runs on the SAME connection that will execute the query.
"""

import re
from typing import Any

from psycopg import AsyncConnection

_SCHEMA_RE = re.compile(r"^school_[0-9]+$")


async def validate_schema_name(schema_name: str | None, conn: AsyncConnection[Any]) -> str:
    """Return the validated schema name or raise. NO global fallback (D-07)."""
    if not schema_name:
        raise ValueError("X-School-Schema header is required for tenant-scoped routes (D-09)")
    if not _SCHEMA_RE.match(schema_name):
        raise ValueError(f"invalid schema_name: {schema_name!r} (must match ^school_[0-9]+$)")
    cur = await conn.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema_name,)
    )
    exists = await cur.fetchone()
    if exists is None:
        raise ValueError(f"schema does not exist: {schema_name}")
    return schema_name
