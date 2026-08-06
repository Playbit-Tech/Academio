from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ProviderKind = Literal["anthropic", "deepseek", "openrouter", "azure", "ollama"]


@dataclass(frozen=True)
class ProviderInfo:
    name: str  # "anthropic" | "deepseek" | ...
    kind: ProviderKind
    key_env: str | None  # env var name holding the API key, None for Ollama
    base_url: str | None = None  # openai-compat base_url; None for anthropic/ollama
    deployment: str | None = None  # Azure deployment name
    configured: bool = field(default=False)  # key present (or Ollama base URL set)


class Provider(Protocol):
    """Implemented by each provider client in plan 03-03.

    messages is ``list[Any]``: chat.py passes pydantic ``model_dump()`` dicts
    whose keys/values are checked at runtime by the SDK TypedDict parsers.
    stream() yields ``{"delta": str}`` events and a final ``{"usage": (in, out)}``.
    """

    def chat(
        self, model: str, messages: list[Any], max_tokens: int, temperature: float | None = None
    ) -> tuple[str, int, int]: ...
    def stream(
        self, model: str, messages: list[Any], max_tokens: int, temperature: float | None = None
    ) -> AsyncIterator[dict]: ...
