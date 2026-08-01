"""POST /v1/embed route tests (PYE-04 / D-05) — env-gated (D-12).

The live-dimension test skips cleanly without AI_OPENAI_API_KEY; all other
tests are hermetic (monkeypatched client, no network).
"""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.embed as embed_api
from app.config import Settings
from app.config import settings as app_settings
from app.main import app


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


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-AI-Engine-Token": settings.AI_ENGINE_TOKEN}


async def test_embed_requires_token(client: AsyncClient) -> None:
    """(a) No service token -> 401 (T-03-04-01)."""
    resp = await client.post("/v1/embed", json={"texts": ["hello"]})
    assert resp.status_code == 401


async def test_embed_validation(client: AsyncClient, settings: Settings) -> None:
    """(b) Empty texts list -> 422 (pydantic min_length=1)."""
    resp = await client.post(
        "/v1/embed", json={"texts": []}, headers=_headers(settings)
    )
    assert resp.status_code == 422


async def test_embed_missing_key_503_or_401(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) No AI_OPENAI_API_KEY -> clean error (503 configured-check), never
    a 200 and never an unhandled exception (D-12 env-gate)."""
    monkeypatch.setattr(app_settings, "AI_OPENAI_API_KEY", "")
    resp = await client.post(
        "/v1/embed",
        json={"texts": ["hello"]},
        headers=_headers(settings),
    )
    assert resp.status_code in {502, 503}
    assert "ai_openai_api_key" in resp.json()["detail"].lower()


@pytest.mark.skipif(
    not os.getenv("AI_OPENAI_API_KEY"),
    reason="no live AI_OPENAI_API_KEY",
)
async def test_embed_returns_1536_dim(
    client: AsyncClient, settings: Settings
) -> None:
    """(d) Live-key test: canonical model returns the locked 1536 dim (D-05)."""
    resp = await client.post(
        "/v1/embed",
        json={"texts": ["Academio embedding dimension test"]},
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "text-embedding-3-small"
    assert body["dimension"] == 1536
    assert len(body["embeddings"][0]) == 1536


async def test_embed_zero_vector_rejected(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(e) A zero-norm embedding -> 400 (RESEARCH Pitfall 2 — NaN cosine)."""
    async def fake_embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536]

    monkeypatch.setattr(embed_api.EmbeddingClient, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(app_settings, "AI_OPENAI_API_KEY", "sk-test")
    resp = await client.post(
        "/v1/embed", json={"texts": ["hello"]}, headers=_headers(settings)
    )
    assert resp.status_code == 400
    assert "zero-norm" in resp.json()["detail"]


async def test_embed_dimension_mismatch_rejected(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(f) Wrong-dimension embedding -> 400 (D-14 parity, fail-loud)."""
    async def fake_embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 512]

    monkeypatch.setattr(embed_api.EmbeddingClient, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(app_settings, "AI_OPENAI_API_KEY", "sk-test")
    resp = await client.post(
        "/v1/embed", json={"texts": ["hello"]}, headers=_headers(settings)
    )
    assert resp.status_code == 400
    assert "dimension" in resp.json()["detail"]


async def test_embed_rejects_overlong_text(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-03-04-07: per-text 8000-char cap -> 400 (checked before any network)."""
    monkeypatch.setattr(app_settings, "AI_OPENAI_API_KEY", "sk-test")
    resp = await client.post(
        "/v1/embed",
        json={"texts": ["x" * 8001]},
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "8000" in resp.json()["detail"]


async def test_embed_rejects_too_many_texts(
    client: AsyncClient, settings: Settings
) -> None:
    """T-03-04-07: more than 256 texts -> 422 (pydantic max_length=256)."""
    resp = await client.post(
        "/v1/embed",
        json={"texts": [f"t{i}" for i in range(257)]},
        headers=_headers(settings),
    )
    assert resp.status_code == 422
