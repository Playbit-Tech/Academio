"""Tests for the provider registry (plan 03-02 Task 3).

Deterministic without API keys — they read the Settings singleton defaults.
"""

import pytest

from app.config import settings
from app.providers.registry import build_provider_registry, get_provider, parse_model_composite


def test_parse_splits_provider_model() -> None:
    assert parse_model_composite("anthropic:claude-3-5-sonnet-latest") == (
        "anthropic",
        "claude-3-5-sonnet-latest",
    )


def test_parse_preserves_slash_in_model() -> None:
    # The '/' in the model must survive (openrouter:openai/gpt-4o-mini)
    assert parse_model_composite("openrouter:openai/gpt-4o-mini") == (
        "openrouter",
        "openai/gpt-4o-mini",
    )


def test_parse_unprefixed_defaults_to_openai() -> None:
    assert parse_model_composite("gpt-4o-mini") == ("openai", "gpt-4o-mini")


def test_parse_splits_on_first_colon() -> None:
    assert parse_model_composite("a:b:c") == ("a", "b:c")


def test_registry_keys_and_ollama_default() -> None:
    reg = build_provider_registry()
    assert set(reg) == {"anthropic", "deepseek", "openrouter", "azure", "ollama"}
    assert get_provider("ollama").base_url == settings.AI_OLLAMA_BASE_URL


def test_get_provider_unknown_raises() -> None:
    with pytest.raises(ValueError):
        get_provider("nope")
