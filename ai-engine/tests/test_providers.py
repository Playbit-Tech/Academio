"""Provider health + /v1/providers route tests (D-10) — no live network.

Part 1: ProviderHealth unit tests with a monkeypatched httpx client.
Part 2 (extended in Task 3): GET /v1/providers route tests via ASGITransport.
"""

import time
from typing import Any

import httpx
import pytest

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
