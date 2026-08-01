"""Cost table tests (D-03) — parity with backend/internal/ai/cost.go semantics."""

from app.providers.cost import DEFAULT_PROVIDER, DEFAULT_COSTS, calculate_cost, estimate_tokens


def test_ollama_always_free() -> None:
    assert calculate_cost(1000, 500, "ollama") == 0.0


def test_zero_tokens_zero_cost() -> None:
    assert calculate_cost(0, 0, "anthropic") == 0.0


def test_unknown_provider_falls_back_to_openai() -> None:
    # Unknown providers fall back to openai rates WITHOUT raising (Go returns 0;
    # here the fallback keeps cost reported on every response — T-03-03-07 accept).
    cost = calculate_cost(1_000_000, 0, "notreal")
    expected = 1_000_000 * DEFAULT_COSTS["openai"][0]
    assert cost == expected
    assert DEFAULT_PROVIDER == "openai"


def test_cost_strictly_increasing_in_both_counts() -> None:
    c1 = calculate_cost(100, 100, "anthropic")
    c2 = calculate_cost(200, 100, "anthropic")
    assert c2 > c1
    c3 = calculate_cost(100, 200, "anthropic")
    assert c3 > c1


def test_estimate_tokens() -> None:
    text = "hello world this is a test"
    assert estimate_tokens(text) == len(text) // 4
    assert estimate_tokens(text) >= 1


def test_estimate_tokens_min_1() -> None:
    assert estimate_tokens("a") == 1  # len//4 == 0 -> floor at 1 (Go EstimateTokens)


def test_openai_parity_spot_check() -> None:
    # $10/M prompt per Go cost.go ProviderOpenAI (0.00001/token)
    assert calculate_cost(1_000_000, 0, "openai") == 10.0
