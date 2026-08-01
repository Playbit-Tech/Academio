"""Anthropic provider client — direct `anthropic` SDK (D-01, PYE-01).

Implements chat() + stream() with the normalized contract consumed by
app/api/chat.py: chat returns (text, input_tokens, output_tokens); stream
yields {"delta": text} events then a final {"usage": (itok, otok)}.
"""

from typing import Any

from anthropic import AsyncAnthropic
from tenacity import retry

from app.config import settings
from app.util.retry import provider_retry


class AnthropicProvider:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.AI_ANTHROPIC_API_KEY,
                                      timeout=settings.AI_LLM_TIMEOUT_SECONDS)

    def _system(self, messages: list[Any]) -> tuple[str | None, list[Any]]:
        # anthropic SDK separates system from messages
        sys = [m["content"] for m in messages if m["role"] == "system"]
        msgs = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] != "system"
        ]
        return ("\n".join(sys) or None, msgs)

    @retry(**provider_retry)  # pyright: ignore[reportArgumentType]  # tenacity typing vs pyright (see 03-02 pattern)
    async def chat(
        self, model: str, messages: list[Any], max_tokens: int | None = None
    ) -> tuple[str, int, int]:
        system, msgs = self._system(messages)
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "messages": msgs,
        }
        if system:
            body["system"] = system
        resp = await self._client.messages.create(**body)
        text = "".join(b.text for b in resp.content if b.type == "text")
        usage = resp.usage
        return text, usage.input_tokens, usage.output_tokens

    async def stream(self, model: str, messages: list[Any], max_tokens: int | None = None) -> Any:
        system, msgs = self._system(messages)
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "messages": msgs,
        }
        if system:
            body["system"] = system
        async with self._client.messages.stream(**body) as s:
            async for event in s:
                if event.type == "text":
                    yield {"delta": event.text}
            final = await s.get_final_message()
            u = final.usage
            yield {"usage": (u.input_tokens, u.output_tokens)}
