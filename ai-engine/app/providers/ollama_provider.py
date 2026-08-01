"""Ollama provider client — httpx direct, OpenAI-compat API (D-01).

Local/free provider; no API key. `stream()` yields {"delta": ...} events
and a final {"usage": (itok, otok)} when Ollama includes usage on the last
content chunk (OpenAI-compat streaming).
"""

import json
from typing import Any

import httpx
from tenacity import retry

from app.config import settings
from app.util.retry import provider_retry


class OllamaProvider:
    def __init__(self) -> None:
        self._base = settings.AI_OLLAMA_BASE_URL

    @retry(**provider_retry)  # pyright: ignore[reportArgumentType]  # tenacity typing vs pyright (see 03-02 pattern)
    async def chat(
        self, model: str, messages: list[Any], max_tokens: int | None = None
    ) -> tuple[str, int, int]:
        async with httpx.AsyncClient(timeout=settings.AI_LLM_TIMEOUT_SECONDS) as c:
            r = await c.post(
                f"{self._base}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    **(dict(max_tokens=max_tokens) if max_tokens else {}),
                },
            )
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage", {})
        return text, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)

    async def stream(self, model: str, messages: list[Any], max_tokens: int | None = None) -> Any:
        async with httpx.AsyncClient(timeout=settings.AI_LLM_TIMEOUT_SECONDS) as c:
            async with c.stream(
                "POST",
                f"{self._base}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    **(dict(max_tokens=max_tokens) if max_tokens else {}),
                },
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):  # includes ": ping"-style keepalives
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    d = chunk["choices"][0].get("delta", {})
                    if d.get("content"):
                        yield {"delta": d["content"]}
                    if chunk.get("usage"):
                        u = chunk["usage"]
                        yield {"usage": (u.get("prompt_tokens", 0), u.get("completion_tokens", 0))}
