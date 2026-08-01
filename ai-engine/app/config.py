from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All AI_* configuration for the engine (D-01/D-05/D-07/D-08/D-10).

    Keys are read from the environment ONLY (Rule B6 spirit) — defaults are
    empty strings, never hardcoded secrets (T-03-02-02). Unknown env vars are
    ignored via extra="ignore" (T-03-02-05); Settings is never logged.
    """

    # Service token (shared with Go backend)
    AI_ENGINE_TOKEN: str = ""

    # Provider API keys (D-01)
    AI_ANTHROPIC_API_KEY: str = ""
    AI_OPENAI_API_KEY: str = ""  # embeddings + canonical model
    AI_DEEPSEEK_API_KEY: str = ""
    AI_OPENROUTER_API_KEY: str = ""
    AI_AZURE_OPENAI_API_KEY: str = ""
    AI_AZURE_OPENAI_ENDPOINT: str = ""
    AI_AZURE_OPENAI_DEPLOYMENT: str = ""
    # Configurable, documented fallback (RESEARCH A1); not a secret
    AI_AZURE_OPENAI_API_VERSION: str = "2024-10-21"

    # Ollama (D-01): local default
    AI_OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Vector store (D-07): read from env ONLY, never hardcode a credential
    AI_PGVECTOR_DSN: str = ""

    # Embeddings (D-05 / Phase 2 canon PGV-04a)
    AI_EMBEDDING_DIM: int = 1536
    AI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    AI_EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    AI_EMBEDDING_BATCH_SIZE: int = 128

    # Prompt library (D-08)
    AI_PROMPTS_DIR: str = "./prompts"

    # Uploads volume root (F2 containment): document_path must resolve inside
    # this directory, else the extract/documents routes reject with 400.
    AI_UPLOADS_DIR: str = ""  # empty = containment disabled (local dev)

    # Chat caps / timeouts (DoS bounds)
    AI_MAX_TOKENS: int = 1024
    AI_LLM_TIMEOUT_SECONDS: float = 60.0
    # SSE keep-alive cadence (D-02 heartbeats <= 30s); a stalled upstream is
    # interrupted at this interval and a heartbeat is emitted instead (F4)
    AI_HEARTBEAT_INTERVAL_SECONDS: float = 25.0

    # Chunker defaults (used by 03-05)
    AI_CHUNK_SIZE: int = 1000
    AI_CHUNK_OVERLAP: int = 200

    # /v1/providers status cache + cooldown (D-10)
    AI_PROVIDER_TTL_SECONDS: int = 30
    AI_PROVIDER_COOLDOWN_THRESHOLD: int = 3
    AI_PROVIDER_COOLDOWN_SECONDS: int = 60

    # Document size gates (03-05)
    AI_MAX_DOC_PAGES: int = 200
    AI_MAX_DOC_MB: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("AI_OLLAMA_BASE_URL", "AI_EMBEDDING_BASE_URL", "AI_AZURE_OPENAI_ENDPOINT")
    @classmethod
    def _validate_http_scheme(cls, v: str) -> str:
        """Fail-fast on non-http(s) base URLs (T-03-02-03, Rule B12 spirit).

        base_urls are env-only constants that flow into outbound HTTP — a
        misconfigured scheme (or a value that is not a URL at all) would enable
        SSRF-style abuse of the engine's network position. Empty values are
        allowed (provider unconfigured).
        """
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("AI_*_BASE_URL/AI_AZURE_OPENAI_ENDPOINT must use http(s):// scheme")
        return v


settings = Settings()
