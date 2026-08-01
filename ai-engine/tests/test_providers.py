"""Provider health + /v1/providers route tests (D-10) — no live network.

Part 1: ProviderHealth unit tests with a monkeypatched httpx client.
Part 2: GET /v1/providers route tests via ASGITransport (D-10 contract).
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import app.api.providers as providers_api
from app.config import Settings
from app.config import settings as app_settings
from app.main import app
from app.providers.healthcheck import ProviderHealth
from app.providers.registry import ProviderInfo


def _info(**overrides: Any) -> ProviderInfo:
    kwargs: dict[str, Any] = {
        "name": "openrouter",
        "kind": "openrouter",
        "key_env": "AI_OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "configured": True,
    }
    kwargs.update(overrides)
    return ProviderInfo(**kwargs)


class FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code


class FakeClient:
    """Stand-in for httpx.AsyncClient: records requests, returns fake status."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.calls: list[str] = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get(
        self, url: str, headers: dict[str, str] | None = None
    ) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse(self.status_code)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse(self.status_code)


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: fake)


async def test_unconfigured_provider_reports_unavailable() -> None:
    """(a) A provider without a key -> 'unavailable', never raises."""
    health = ProviderHealth()
    info = _info(configured=False)
    status = await health.check("openrouter", info)
    assert status.status == "unavailable"
    assert status.latency_ms is None


async def test_fresh_cache_avoids_second_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) A fresh cache entry is returned without a second network ping."""
    fake = FakeClient(200)
    _patch_client(monkeypatch, fake)
    health = ProviderHealth()
    info = _info()
    first = await health.check("openrouter", info)
    assert first.status == "healthy"
    second = await health.check("openrouter", info)
    assert second is first  # served from the 30s TTL cache
    assert len(fake.calls) == 1


async def test_three_failures_flip_to_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) 3 consecutive failures -> 'cooldown' with cooldown_until > now."""
    fake = FakeClient(500)
    _patch_client(monkeypatch, fake)
    health = ProviderHealth()
    health._ttl = 0.0  # force a fresh ping on every check
    info = _info()
    assert (await health.check("openrouter", info)).status == "degraded"
    assert (await health.check("openrouter", info)).status == "degraded"
    third = await health.check("openrouter", info)
    assert third.status == "cooldown"
    assert third.cooldown_until is not None
    assert third.cooldown_until > time.time()
    assert len(fake.calls) == 3


async def test_healthy_ping_resets_fail_streak(monkeypatch: pytest.MonkeyPatch) -> None:
    """(d) A healthy ping resets the fail streak."""
    fake = FakeClient(200)
    _patch_client(monkeypatch, fake)
    health = ProviderHealth()
    health._ttl = 0.0
    health._fail_streak["openrouter"] = 2
    status = await health.check("openrouter", _info())
    assert status.status == "healthy"
    assert "openrouter" not in health._fail_streak


async def test_ttl_expiry_triggers_reping(monkeypatch: pytest.MonkeyPatch) -> None:
    """(e) TTL expiry causes a fresh ping on the next check."""
    fake = FakeClient(200)
    _patch_client(monkeypatch, fake)
    health = ProviderHealth()
    info = _info()
    await health.check("openrouter", info)
    assert len(fake.calls) == 1
    # Rewind the cached check so the 30s TTL window has expired
    health._cache["openrouter"].last_checked -= 31.0
    await health.check("openrouter", info)
    assert len(fake.calls) == 2


# --------------------------------------------------------------------------
# Part 2: GET /v1/providers route tests (D-10 contract; no live network)
# --------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    s = Settings(AI_ENGINE_TOKEN="test-token-123")
    # The app's require_token dependency reads the module-level singleton;
    # share the test token with that same instance (mirrors test_embedding).
    app_settings.AI_ENGINE_TOKEN = s.AI_ENGINE_TOKEN
    return s


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-AI-Engine-Token": settings.AI_ENGINE_TOKEN}


async def test_providers_route_requires_token(client: AsyncClient) -> None:
    """(a) No service token -> 401 (T-03-04-01)."""
    resp = await client.get("/v1/providers")
    assert resp.status_code == 401


async def test_providers_route_no_keys_all_unavailable(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(b) No provider keys -> 200 with all five providers, each
    unavailable — never a 500 (RESEARCH Pitfall 5 / A3)."""
    monkeypatch.setattr(app_settings, "AI_OLLAMA_BASE_URL", "")  # hermetic: no localhost ping
    resp = await client.get("/v1/providers", headers=_headers(settings))
    assert resp.status_code == 200
    body = resp.json()
    names = {p["provider"] for p in body["providers"]}
    assert names == {"anthropic", "deepseek", "openrouter", "azure", "ollama"}
    for p in body["providers"]:
        assert p["status"] in {"unavailable", "cooldown"}
        assert p["latency_ms"] is None


async def test_providers_route_healthy(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(c) Key set + healthy ping -> openrouter reports healthy with
    latency_ms >= 0 (D-10 contract, consumed by Go INT-02)."""
    fake = FakeClient(200)
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr(app_settings, "AI_OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(app_settings, "AI_OLLAMA_BASE_URL", "")
    providers_api._health = ProviderHealth()  # fresh singleton (patched settings)
    resp = await client.get("/v1/providers", headers=_headers(settings))
    assert resp.status_code == 200
    by_name = {p["provider"]: p for p in resp.json()["providers"]}
    op = by_name["openrouter"]
    assert op["status"] == "healthy"
    assert op["latency_ms"] is not None and op["latency_ms"] >= 0
    assert op["cooldown_until"] is None
    assert fake.calls  # a ping actually happened


async def test_providers_route_cooldown(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(d) 3 failing pings -> cooldown surfaces in the route response."""
    fake = FakeClient(500)
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr(app_settings, "AI_OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(app_settings, "AI_PROVIDER_TTL_SECONDS", 0)  # force a re-ping per call
    monkeypatch.setattr(app_settings, "AI_PROVIDER_COOLDOWN_THRESHOLD", 3)
    monkeypatch.setattr(app_settings, "AI_OLLAMA_BASE_URL", "")
    providers_api._health = ProviderHealth()  # fresh singleton (patched settings)
    resp: httpx.Response | None = None
    for _ in range(3):
        resp = await client.get("/v1/providers", headers=_headers(settings))
        assert resp.status_code == 200
    assert resp is not None
    by_name = {p["provider"]: p for p in resp.json()["providers"]}
    assert by_name["openrouter"]["status"] == "cooldown"
    assert by_name["openrouter"]["cooldown_until"] is not None
    assert len(fake.calls) == 3


def test_openai_compat_fails_fast_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review F6: OpenAICompatProvider must not construct with a placeholder key."""
    from app.providers.openai_compat import OpenAICompatProvider

    monkeypatch.setattr(app_settings, "AI_OPENROUTER_API_KEY", "")
    with pytest.raises(ValueError, match="AI_OPENROUTER_API_KEY is not set"):
        OpenAICompatProvider(_info())


def test_openai_compat_constructs_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """F6 positive path: with the key set, construction succeeds."""
    from app.providers.openai_compat import OpenAICompatProvider

    monkeypatch.setattr(app_settings, "AI_OPENROUTER_API_KEY", "test-key")
    provider = OpenAICompatProvider(_info())
    assert provider._client is not None
