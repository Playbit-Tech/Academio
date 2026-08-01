"""Tests for the Settings surface (plan 03-02 Task 2)."""

from app.config import Settings

# The 25 AI_* fields (D-01 provider keys + embedding/vector/prompt/doc gates).
# Keep in sync with app/config.py — the count assertion below enforces an
# exact match; update both together if the surface grows.
ALL_AI_FIELDS = [
    "AI_ENGINE_TOKEN",
    "AI_ANTHROPIC_API_KEY",
    "AI_OPENAI_API_KEY",
    "AI_DEEPSEEK_API_KEY",
    "AI_OPENROUTER_API_KEY",
    "AI_AZURE_OPENAI_API_KEY",
    "AI_AZURE_OPENAI_ENDPOINT",
    "AI_AZURE_OPENAI_DEPLOYMENT",
    "AI_AZURE_OPENAI_API_VERSION",
    "AI_OLLAMA_BASE_URL",
    "AI_PGVECTOR_DSN",
    "AI_EMBEDDING_DIM",
    "AI_EMBEDDING_MODEL",
    "AI_EMBEDDING_BASE_URL",
    "AI_EMBEDDING_BATCH_SIZE",
    "AI_PROMPTS_DIR",
    "AI_MAX_TOKENS",
    "AI_LLM_TIMEOUT_SECONDS",
    "AI_CHUNK_SIZE",
    "AI_CHUNK_OVERLAP",
    "AI_PROVIDER_TTL_SECONDS",
    "AI_PROVIDER_COOLDOWN_THRESHOLD",
    "AI_PROVIDER_COOLDOWN_SECONDS",
    "AI_MAX_DOC_PAGES",
    "AI_MAX_DOC_MB",
]


def test_defaults_locked() -> None:
    """The plan's locked defaults hold on a fresh Settings (no env)."""
    # _env_file=None isolates from any local dotenv; pyright does not model
    # pydantic-settings' init-only kwarg in its synthesized BaseModel.__init__.
    s = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert s.AI_EMBEDDING_DIM == 1536
    assert s.AI_OLLAMA_BASE_URL == "http://localhost:11434"
    assert s.AI_EMBEDDING_BATCH_SIZE == 128
    assert s.AI_PROMPTS_DIR == "./prompts"


def test_env_override_reads_back() -> None:
    """Explicit values (the env path) read back exactly."""
    # _env_file=None isolates from any local dotenv; pyright does not model
    # pydantic-settings' init-only kwarg in its synthesized BaseModel.__init__.
    s = Settings(
        AI_ANTHROPIC_API_KEY="k-test",
        AI_PGVECTOR_DSN="postgres://x",
        _env_file=None,  # pyright: ignore[reportCallIssue]
    )
    assert s.AI_ANTHROPIC_API_KEY == "k-test"
    assert s.AI_PGVECTOR_DSN == "postgres://x"


def test_all_ai_fields_present_and_exact_count() -> None:
    """Every field from the plan's action list exists; count matches exactly."""
    missing = [f for f in ALL_AI_FIELDS if f not in Settings.model_fields]
    assert missing == [], f"fields missing from Settings: {missing}"
    assert len(Settings.model_fields) == len(ALL_AI_FIELDS), (
        f"expected {len(ALL_AI_FIELDS)} AI_* fields, got {len(Settings.model_fields)}: "
        f"{sorted(set(Settings.model_fields) - set(ALL_AI_FIELDS))}"
    )
