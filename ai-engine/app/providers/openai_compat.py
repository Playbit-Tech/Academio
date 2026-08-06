"""OpenAI-compat provider client — deepseek / openrouter / azure (D-01).

One class, `openai` SDK with base_url from ProviderInfo. Azure uses
`AsyncAzureOpenAI` (openai 2.52.0): the base `AsyncOpenAI` class does NOT
accept azure_deployment/api_version kwargs — `AsyncAzureOpenAI` builds the
`{endpoint}/openai/deployments/{deployment}` base_url itself. Non-azure
providers (deepseek, openrouter) use plain `AsyncOpenAI(base_url=...)`.
"""

from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI
from tenacity import retry

from app.config import settings
from app.providers.base import ProviderInfo
from app.util.retry import provider_retry

# Azure endpoints are conventionally configured as
# https://{resource}.openai.azure.com/openai/v1 (D-01); AsyncAzureOpenAI
# expects the bare resource root and appends /openai/deployments/{name}.
_AZURE_SUFFIXES = ("/openai/v1", "/openai")


class OpenAICompatProvider:
    def __init__(self, info: ProviderInfo) -> None:  # ProviderInfo from registry
        if not info.key_env:
            raise ValueError(f"provider {info.name}: key_env is required")
        api_key = getattr(settings, info.key_env, "")
        if not api_key:
            # F6: fail fast (Rule B6 spirit) — never construct with a literal
            # placeholder key; the route maps this to 503 like
            # EmbeddingNotConfiguredError.
            raise ValueError(f"provider {info.name}: {info.key_env} is not set")
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": settings.AI_LLM_TIMEOUT_SECONDS,
        }
        if info.name == "azure":
            endpoint = (info.base_url or "").rstrip("/")
            for suffix in _AZURE_SUFFIXES:
                if endpoint.endswith(suffix):
                    endpoint = endpoint[: -len(suffix)]
            self._client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                azure_deployment=info.deployment,
                api_version=settings.AI_AZURE_OPENAI_API_VERSION,
                api_key=kwargs["api_key"],
                timeout=kwargs["timeout"],
            )
        else:
            kwargs["base_url"] = info.base_url
            self._client = AsyncOpenAI(**kwargs)

    @retry(**provider_retry)  # pyright: ignore[reportArgumentType]  # tenacity typing vs pyright (see 03-02 pattern)
    async def chat(
        self,
        model: str,
        messages: list[Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> tuple[str, int, int]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = await self._client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content or ""
        if resp.usage is None:
            return content, 0, 0
        return content, resp.usage.prompt_tokens, resp.usage.completion_tokens

    async def stream(
        self,
        model: str,
        messages: list[Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or settings.AI_MAX_TOKENS,
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        stream = await self._client.chat.completions.create(**kwargs)
        usage: tuple[int, int] | None = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield {"delta": chunk.choices[0].delta.content}
            if chunk.usage:
                usage = (chunk.usage.prompt_tokens or 0, chunk.usage.completion_tokens or 0)
        # usage arrives on the final chunk for streamed OpenAI-compat responses
        if usage is not None:
            yield {"usage": usage}
