"""Provider price tables + cost calculation — mirror of backend/internal/ai/cost.go (D-03).

Values are USD per token (input, output). The Go `defaultCosts` map only
carried Gemini/OpenAI; this module extends it to the five Phase 3 providers
plus the "openai" fallback, keeping the Go parity spot-check exact
(calculate_cost(1_000_000, 0, "openai") == 10.0, $10/M prompt).
"""

# USD per token price tables — mirror of backend/internal/ai/cost.go defaultCosts.
# Anthropic/DeepSeek/OpenRouter/Azure rates are published list prices as of 2026-08-01;
# Ollama is local/free. Keep in sync with Go cost.go.
DEFAULT_COSTS: dict[str, tuple[float, float]] = {
    "anthropic":  (0.000003, 0.000015),   # $3/M prompt, $15/M completion (Claude Sonnet-class)
    "deepseek":   (0.00000027, 0.0000011), # $0.27/M, $1.10/M (DeepSeek-V3)
    "openrouter": (0.00000015, 0.0000006), # conservative default (model-dependent routing)
    "azure":      (0.000005, 0.000015),    # Azure OpenAI GPT-4o-class
    "openai":     (0.00001, 0.00003),      # parity with Go cost.go ProviderOpenAI
    "ollama":     (0.0, 0.0),              # local — free
}
DEFAULT_PROVIDER = "openai"


def calculate_cost(input_tokens: int, output_tokens: int, provider: str) -> float:
    prompt_rate, completion_rate = DEFAULT_COSTS.get(provider, DEFAULT_COSTS[DEFAULT_PROVIDER])
    return input_tokens * prompt_rate + output_tokens * completion_rate


def estimate_tokens(text: str) -> int:
    tokens = len(text) // 4  # common approximation, mirrors Go EstimateTokens
    return max(tokens, 1)
