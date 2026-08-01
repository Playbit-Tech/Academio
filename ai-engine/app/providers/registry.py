from app.config import settings
from app.providers.base import ProviderInfo


def parse_model_composite(model: str) -> tuple[str, str]:
    """Split 'provider:model' on the FIRST ':' (D-03).

    Model IDs may contain '/' (openrouter:openai/gpt-4o-mini) but never ':'.
    Unprefixed models default to provider 'openai' for backward compat.
    """
    if ":" in model:
        provider, _, rest = model.partition(":")
        return provider, rest
    return "openai", model


def build_provider_registry() -> dict[str, ProviderInfo]:
    """Returns name -> ProviderInfo for all five providers (D-01)."""
    s = settings
    return {
        "anthropic": ProviderInfo(
            "anthropic",
            "anthropic",
            "AI_ANTHROPIC_API_KEY",
            configured=bool(s.AI_ANTHROPIC_API_KEY),
        ),
        "deepseek": ProviderInfo(
            "deepseek",
            "deepseek",
            "AI_DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com",
            configured=bool(s.AI_DEEPSEEK_API_KEY),
        ),
        "openrouter": ProviderInfo(
            "openrouter",
            "openrouter",
            "AI_OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            configured=bool(s.AI_OPENROUTER_API_KEY),
        ),
        "azure": ProviderInfo(
            "azure",
            "azure",
            "AI_AZURE_OPENAI_API_KEY",
            base_url=s.AI_AZURE_OPENAI_ENDPOINT or None,
            deployment=s.AI_AZURE_OPENAI_DEPLOYMENT or None,
            configured=bool(
                s.AI_AZURE_OPENAI_API_KEY
                and s.AI_AZURE_OPENAI_ENDPOINT
                and s.AI_AZURE_OPENAI_DEPLOYMENT
            ),
        ),
        "ollama": ProviderInfo(
            "ollama",
            "ollama",
            None,
            base_url=s.AI_OLLAMA_BASE_URL,
            configured=bool(s.AI_OLLAMA_BASE_URL),
        ),
    }


def get_provider(name: str) -> ProviderInfo:
    reg = build_provider_registry()
    if name not in reg:
        raise ValueError(f"unknown provider: {name}")
    return reg[name]
