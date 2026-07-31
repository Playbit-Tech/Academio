from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.config import settings as app_settings
from app.main import app


@pytest.fixture
def settings() -> Settings:
    s = Settings(AI_ENGINE_TOKEN="test-token-123")
    # The app's require_token dependency reads the module-level singleton;
    # share the test token with that same instance so the valid-token test
    # is deterministic.
    app_settings.AI_ENGINE_TOKEN = s.AI_ENGINE_TOKEN
    return s


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_health_unauthenticated(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-engine"


async def test_v1_health_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/v1/health")
    assert resp.status_code == 401


async def test_v1_health_rejects_wrong_token(client: AsyncClient) -> None:
    resp = await client.get("/v1/health", headers={"X-AI-Engine-Token": "wrong"})
    assert resp.status_code == 401


async def test_v1_health_accepts_valid_token(client: AsyncClient, settings: Settings) -> None:
    resp = await client.get(
        "/v1/health", headers={"X-AI-Engine-Token": settings.AI_ENGINE_TOKEN}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
