"""Canonical embedding client (D-05): text-embedding-3-small, 1536-dim.

Shared embed path for /v1/embed (03-04), /v1/documents (03-05) and
/v1/search (03-06). Phase 2 locked the vector contract
(AI_EMBEDDING_DIM=1536, PGV-04a); every response is validated fail-loud and
zero-norm vectors are rejected (RESEARCH Pitfall 2 — NaN cosine `<=>` poison).

Instantiation is stateless per call (the plan allows either per-request or a
lazy module singleton; per-request is chosen here to keep tests deterministic
— the openai SDK pools connections internally, so the cost is negligible).
"""

import math
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry

from app.config import settings
from app.util.retry import embed_retry

MAX_TEXT_CHARS = 8000  # per-text DoS bound (T-03-04-07)


def _retried(preset: dict[str, Any]) -> Any:
    """Apply a tenacity preset as a decorator.

    tenacity's ``retry()`` is dual-mode (decorator factory vs. RetryCallState
    callable); pyright resolves ``@retry(**preset)`` to the wrong overload and
    types the decorated method as bool/float. Routing through this helper pins
    the decorator to ``Any`` (see the 03-04 SUMMARY deviation note).
    """
    return retry(**preset)


class EmbeddingNotConfiguredError(RuntimeError):
    """Raised when AI_OPENAI_API_KEY is absent (route maps it to 503)."""


def validate_vector(v: list[float], dim: int) -> None:
    """Fail-loud dimension + zero-norm guard (D-05, T-03-04-03).

    Mirrors Phase 2's D-14 dimension guard
    (backend/internal/ai/vector/pgvector.go) on the Python side; cosine `<=>`
    on a 0-vector yields NaN (RESEARCH Pitfall 2) — reject, never insert.
    """
    if len(v) != dim:
        raise ValueError(f"embedding dimension {len(v)} != locked {dim} (PGV-04a)")
    norm = math.sqrt(sum(x * x for x in v))
    if math.isclose(norm, 0.0, abs_tol=1e-12):
        raise ValueError("zero-norm embedding rejected (cosine NaN risk)")


class EmbeddingClient:
    """Stateless per-request embed client (D-05): batch <= 128, dim assert."""

    def __init__(self) -> None:
        if not settings.AI_OPENAI_API_KEY:
            raise EmbeddingNotConfiguredError("AI_OPENAI_API_KEY is not configured")
        self._client = AsyncOpenAI(
            api_key=settings.AI_OPENAI_API_KEY,
            base_url=settings.AI_EMBEDDING_BASE_URL,
            timeout=settings.AI_LLM_TIMEOUT_SECONDS,
        )
        self._dim = settings.AI_EMBEDDING_DIM
        self._batch = settings.AI_EMBEDDING_BATCH_SIZE  # <= 128 (D-05)

    @_retried(embed_retry)
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(
            model=settings.AI_EMBEDDING_MODEL, input=texts
        )
        # The API preserves input order — index by position (D-05)
        return [e.embedding for e in resp.data]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(len(t) > MAX_TEXT_CHARS for t in texts):
            raise ValueError("embedding input exceeds 8000 chars")
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            vectors.extend(await self._embed_batch(texts[i : i + self._batch]))
        for v in vectors:
            validate_vector(v, self._dim)
        return vectors
