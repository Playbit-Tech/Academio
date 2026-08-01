from dataclasses import dataclass, field
from typing import Literal, Protocol

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
    """Implemented by each provider client in plan 03-03."""

    def chat(self, model: str, messages: list[dict], max_tokens: int) -> tuple[str, int, int]: ...
    def stream(self, model: str, messages: list[dict], max_tokens: int): ...
