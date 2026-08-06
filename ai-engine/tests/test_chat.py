"""POST /v1/chat + /v1/chat/stream route tests (PYE-04 / D-03 / D-12).

Hermetic tests never touch the network (503 path, max_tokens cap, in-band
error sanitization). The two live-shape tests are env-gated on a reachable
local Ollama (/api/tags ping, RESEARCH A4) and skip cleanly otherwise — NO
AI_*_API_KEY is ever required (D-12). The SSE test proves the D-02 wire
format: single-line compact-JSON ``data:`` events, blank-line boundaries,
``: ping`` heartbeats, correct headers, no gzip.
"""

import json
import os
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import app.api.chat as chat_api
from app.config import Settings
from app.config import settings as app_settings
from app.main import app


def _ollama_reachable() -> bool:
    """Live ping of /api/tags — env gate for the shape tests (D-12).

    Evaluated once at import; a default AI_OLLAMA_BASE_URL that is NOT
    reachable (e.g. CI) makes the live tests skip cleanly.
    """
    base = os.getenv("AI_OLLAMA_BASE_URL") or app_settings.AI_OLLAMA_BASE_URL
    if not base:
        return False
    try:
        resp = httpx.get(f"{base}/api/tags", timeout=2.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


OLLAMA_REACHABLE = _ollama_reachable()

OLLAMA_MODEL = "ollama:deepseek-coder:latest"


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


async def test_chat_requires_token(client: AsyncClient) -> None:
    """(a) No service token -> 401 (T-03-03-01)."""
    resp = await client.post(
        "/v1/chat",
        json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


async def test_chat_rejects_bad_token(client: AsyncClient) -> None:
    """(b) Wrong service token -> 401 (T-03-03-01)."""
    resp = await client.post(
        "/v1/chat",
        json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": "hi"}]},
        headers={"X-AI-Engine-Token": "wrong"},
    )
    assert resp.status_code == 401


async def test_chat_unknown_provider_503(
    client: AsyncClient, settings: Settings
) -> None:
    """(c) Unknown provider prefix -> 503 BEFORE any network call (T-03-03-02)."""
    resp = await client.post(
        "/v1/chat",
        json={"model": "notreal:model", "messages": [{"role": "user", "content": "hi"}]},
        headers=_headers(settings),
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "provider not configured: notreal"


async def test_chat_stream_requires_token(client: AsyncClient) -> None:
    """(d) No service token on /v1/chat/stream -> 401 (T-03-03-01)."""
    resp = await client.post(
        "/v1/chat/stream",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 401


async def test_chat_max_tokens_capped(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(e) max_tokens above the DoS bound is capped at AI_MAX_TOKENS (T-03-03-02).

    Hermetic (monkeypatched client, no network) — also proves the normalized
    usage payload shape on a non-stream response.
    """
    seen: dict[str, Any] = {}

    class FakeProvider:
        async def chat(
            self,
            model: str,
            messages: list[Any],
            max_tokens: int | None = None,
            temperature: float | None = None,
        ):
            seen["max_tokens"] = max_tokens
            return "hello from fake", 5, 3

    monkeypatch.setattr(chat_api, "_clients", lambda: {"ollama": FakeProvider()})
    resp = await client.post(
        "/v1/chat",
        json={
            "model": "ollama:qwen3.5:9b",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 999_999,
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert seen["max_tokens"] == app_settings.AI_MAX_TOKENS
    body = resp.json()
    assert body["message"] == {"role": "assistant", "content": "hello from fake"}
    assert set(body["usage"]) == {"provider", "model", "input_tokens", "output_tokens", "cost"}
    assert body["usage"]["provider"] == "ollama"
    assert body["usage"]["input_tokens"] == 5
    assert body["usage"]["output_tokens"] == 3
    assert body["usage"]["cost"] == 0.0  # ollama is local/free


async def test_chat_temperature_passthrough(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(i) temperature flows to the provider when set; absent -> None (MA-03).

    Mirrors test_chat_max_tokens_capped: hermetic fake provider records the
    kwargs it received. A request WITHOUT temperature must not supply one —
    backward compat (the route only populates kwargs when req.temperature is
    not None).
    """
    seen: dict[str, Any] = {}

    class FakeProvider:
        async def chat(
            self,
            model: str,
            messages: list[Any],
            max_tokens: int | None = None,
            temperature: float | None = None,
        ):
            seen["temperature"] = temperature
            return "hello from fake", 5, 3

    monkeypatch.setattr(chat_api, "_clients", lambda: {"ollama": FakeProvider()})
    resp = await client.post(
        "/v1/chat",
        json={
            "model": "ollama:qwen3.5:9b",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.7,
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert seen["temperature"] == 0.7

    seen.clear()
    resp = await client.post(
        "/v1/chat",
        json={
            "model": "ollama:qwen3.5:9b",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert seen["temperature"] is None  # omitted → provider default


async def test_stream_error_in_band_sanitized(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(f) Provider failure AFTER HTTP 200 -> in-band error event, secrets redacted (T-03-03-03)."""

    class FailingProvider:
        async def stream(
            self,
            model: str,
            messages: list[Any],
            max_tokens: int | None = None,
            temperature: float | None = None,
        ) -> AsyncIterator[dict]:
            key = app_settings.AI_OPENAI_API_KEY
            raise RuntimeError(
                f"401 unauthorized: https://api.example.com/path?api_key={key} "
                f"Authorization: Bearer {key}"
            )
            yield {}  # pragma: no cover — makes this a generator that raises on first anext()

    monkeypatch.setattr(app_settings, "AI_OPENAI_API_KEY", "sk-test-secret-xyz")
    monkeypatch.setattr(chat_api, "_clients", lambda: {"ollama": FailingProvider()})
    resp = await client.post(
        "/v1/chat/stream",
        json={
            "model": "ollama:test",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200  # stream already started
    assert resp.headers["content-type"].startswith("text/event-stream")
    body = resp.text
    assert 'data: {"type":"error"' in body
    assert "sk-test-secret-xyz" not in body
    assert "[REDACTED]" in body


@pytest.mark.skipif(
    not OLLAMA_REACHABLE,
    reason="no reachable Ollama (/api/tags) — live SSE shape test",
)
async def test_sse_envelope_shape(client: AsyncClient, settings: Settings) -> None:
    """(g) Live stream: D-02 envelope byte-shape — single-line compact-JSON
    ``data:`` events, blank-line boundaries, ``: ping``, no gzip, headers."""
    resp = await client.post(
        "/v1/chat/stream",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers.get("cache-control") == "no-cache"
    assert resp.headers.get("x-accel-buffering") == "no"
    body = resp.text
    assert ": ping" in body  # heartbeat comment line
    assert 'data: {"type":"delta"' in body
    assert 'data: {"type":"done"' in body
    assert "\n\n" in body  # blank-line event boundaries
    # Go-scanner-equivalent round-trip: every data: line is one compact JSON
    # event with no embedded newlines (RESEARCH Pitfall 3)
    for line in body.splitlines():
        if line.startswith("data: "):
            assert "\n" not in line
            payload = json.loads(line[len("data: "):])
            assert payload["type"] in {"delta", "usage", "error", "done"}


@pytest.mark.skipif(
    not OLLAMA_REACHABLE,
    reason="no reachable Ollama (/api/tags) — live usage shape test",
)
async def test_chat_usage_shape(client: AsyncClient, settings: Settings) -> None:
    """(h) Live non-stream chat: normalized usage on EVERY response (PYE-04)."""
    resp = await client.post(
        "/v1/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"]
    assert set(body["usage"]) == {"provider", "model", "input_tokens", "output_tokens", "cost"}
    assert body["usage"]["provider"] == "ollama"
    assert body["usage"]["cost"] == 0.0  # ollama is local/free
