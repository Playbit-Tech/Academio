"""Per-provider health pings with TTL cache + in-memory cooldown (D-10).

Data source for GET /v1/providers (PYE-04; consumed by Go INT-02 in Phase 5).
Design:
- model-less pings per provider kind (RESEARCH Pattern 4):
  Anthropic GET /v1/models, OpenAI-compat GET /models, DeepSeek GET /models,
  Ollama GET /api/tags, Azure deployments list (1-token chat ping fallback
  on 4xx, RESEARCH A1)
- 30s TTL cache so repeated status calls never hammer providers (T-03-04-04)
- in-memory fail-streak -> cooldown: AI_PROVIDER_COOLDOWN_THRESHOLD
  consecutive non-healthy pings flip a provider to "cooldown" for
  AI_PROVIDER_COOLDOWN_SECONDS (D-10)
- providers without API keys report "unavailable", never an error
  (RESEARCH Pitfall 5 / A3)

All state is in-memory per process — the service is stateless; cooldown is
per-replica (accepted for the single-replica dev deployment, D-10).
"""

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

from app.config import settings
from app.providers.registry import ProviderInfo

logger = logging.getLogger(__name__)

# Bounded ping timeout (D-10, T-03-04-04): never longer than the LLM timeout.
_PING_TIMEOUT_S = min(5.0, settings.AI_LLM_TIMEOUT_SECONDS)


@dataclass
class ProviderStatus:
    provider: str
    status: str  # "healthy" | "degraded" | "unavailable" | "cooldown"
    latency_ms: int | None
    last_checked: float
    cooldown_until: float | None = None


class ProviderHealth:
    """Per-provider health cache + fail-streak cooldown (D-10)."""

    def __init__(self) -> None:
        self._cache: dict[str, ProviderStatus] = {}
        self._fail_streak: dict[str, int] = {}
        self._cooldown_until: dict[str, float] = {}
        self._in_flight: dict[str, asyncio.Future[ProviderStatus]] = {}
        self._lock = asyncio.Lock()
        self._ttl = float(settings.AI_PROVIDER_TTL_SECONDS)
        self._cooldown_threshold = settings.AI_PROVIDER_COOLDOWN_THRESHOLD
        self._cooldown_window = settings.AI_PROVIDER_COOLDOWN_SECONDS

    # -- model-less ping endpoints per provider kind (RESEARCH Pattern 4) ----

    def _ping_request(self, info: ProviderInfo) -> tuple[str, dict[str, str]]:
        """Return (url, headers) for the health ping; secrets never logged."""
        if info.kind == "anthropic":
            return "https://api.anthropic.com/v1/models", {
                "x-api-key": getattr(settings, info.key_env) if info.key_env else "",
                "anthropic-version": "2023-06-01",
            }
        if info.kind == "ollama":
            return f"{info.base_url}/api/tags", {}
        if info.name == "deepseek":
            return "https://api.deepseek.com/models", self._bearer(info)
        if info.name == "azure":
            return (
                f"{info.base_url}/openai/deployments"
                f"?api-version={settings.AI_AZURE_OPENAI_API_VERSION}",
                {"api-key": getattr(settings, info.key_env) if info.key_env else ""},
            )
        # OpenAI-compatible (openrouter): base_url already includes /v1
        # (https://openrouter.ai/api/v1); models live at {base_url}/models.
        return f"{info.base_url}/models", self._bearer(info)

    @staticmethod
    def _bearer(info: ProviderInfo) -> dict[str, str]:
        key = getattr(settings, info.key_env) if info.key_env else ""
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def _azure_chat_ping(self, info: ProviderInfo) -> bool:
        """RESEARCH A1 fallback: 1-token chat ping when deployments list 4xxs."""
        url = (
            f"{info.base_url}/openai/deployments/{info.deployment}/chat/completions"
            f"?api-version={settings.AI_AZURE_OPENAI_API_VERSION}"
        )
        headers = {"api-key": getattr(settings, info.key_env) if info.key_env else ""}
        payload = {
            "model": info.deployment,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        async with httpx.AsyncClient(timeout=_PING_TIMEOUT_S) as client:
            resp = await client.post(url, headers=headers, json=payload)
        return resp.status_code < 400

    async def _ping(self, name: str, info: ProviderInfo) -> ProviderStatus:
        """One model-less ping; never raises (degraded, not an error — D-10)."""
        started = time.perf_counter()
        try:
            url, headers = self._ping_request(info)
            async with httpx.AsyncClient(timeout=_PING_TIMEOUT_S) as client:
                resp = await client.get(url, headers=headers)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if resp.status_code < 400:
                return ProviderStatus(name, "healthy", latency_ms, time.time())
            if info.name == "azure" and resp.status_code < 500:
                # A1: the Azure deployments list can 400 on api-version —
                # fall back to a 1-token chat ping before declaring degraded.
                if await self._azure_chat_ping(info):
                    return ProviderStatus(name, "healthy", latency_ms, time.time())
            logger.warning("provider %s ping failed (status %s)", name, resp.status_code)
            return ProviderStatus(name, "degraded", latency_ms, time.time())
        except (httpx.HTTPError, OSError) as exc:
            # status-level log only — no URL query, no headers (T-03-04-02)
            logger.warning("provider %s ping error: %s", name, type(exc).__name__)
            return ProviderStatus(name, "degraded", None, time.time())

    def _apply_result(self, name: str, status: ProviderStatus) -> ProviderStatus:
        """Update fail-streak/cooldown from a fresh ping result (D-10)."""
        if status.status == "healthy":
            self._fail_streak.pop(name, None)
            return status
        streak = self._fail_streak.get(name, 0) + 1
        self._fail_streak[name] = streak
        if streak >= self._cooldown_threshold:
            until = time.time() + self._cooldown_window
            self._cooldown_until[name] = until
            return ProviderStatus(
                name, "cooldown", status.latency_ms, status.last_checked, until
            )
        return status

    async def check(self, name: str, info: ProviderInfo) -> ProviderStatus:
        """Cached/live status for one provider; single in-flight per name."""
        # 1. Cooldown window: no network (D-10)
        until = self._cooldown_until.get(name, 0.0)
        if until > time.time():
            cached = self._cache.get(name)
            return ProviderStatus(
                name, "cooldown", None,
                cached.last_checked if cached else time.time(), until,
            )
        # 2. Fresh TTL cache (D-10) — fast path without lock contention
        cached = self._cache.get(name)
        if cached is not None and time.time() - cached.last_checked < self._ttl:
            return cached
        # 3. Single in-flight per name (T-03-04-04): a second caller awaits
        #    the same ping instead of starting a second one. The resolver
        #    never takes this lock, so awaiting here cannot deadlock.
        async with self._lock:
            cached = self._cache.get(name)
            if cached is not None and time.time() - cached.last_checked < self._ttl:
                return cached
            future = self._in_flight.get(name)
            if future is not None:
                return await future
            future = asyncio.get_running_loop().create_future()
            self._in_flight[name] = future
        # 4. Unconfigured providers report "unavailable" — never an error
        #    (RESEARCH Pitfall 5 / A3)
        if not info.configured:
            status = ProviderStatus(name, "unavailable", None, time.time())
            self._resolve(name, future, status)
            return status
        # 5. Live ping outside the lock: one slow provider never blocks others
        try:
            status = await self._ping(name, info)
        except Exception:  # defensive: never leave an awaiter hanging
            logger.exception("unexpected provider ping failure for %s", name)
            status = ProviderStatus(name, "degraded", None, time.time())
        status = self._apply_result(name, status)
        self._resolve(name, future, status)
        return status

    def _resolve(
        self, name: str, future: asyncio.Future[ProviderStatus], status: ProviderStatus
    ) -> None:
        """Publish a ping result: drop in-flight, cache, complete awaiters."""
        self._in_flight.pop(name, None)
        self._cache[name] = status
        if not future.done():
            future.set_result(status)
