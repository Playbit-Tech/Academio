"""Shared tenacity retry presets (D-05: 3 attempts, backoff factor 2).

Consumed by provider chat (03-03) and embeddings (03-04).
"""

import anthropic
import httpx
import openai
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

# Retry transport errors/timeouts ONLY — never 4xx. The anthropic/openai SDKs
# raise their own APIConnectionError/APITimeoutError on transport failures,
# which do NOT inherit httpx.TransportError — include them so retries actually
# fire for SDK-based providers (D-05). httpx covers Ollama.
provider_retry = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (
            httpx.TransportError,
            httpx.TimeoutException,
            anthropic.APIConnectionError,
            openai.APIConnectionError,
        )
    ),
)
embed_retry = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
