"""Shared tenacity retry presets (D-05: 3 attempts, backoff factor 2).

Consumed by provider chat (03-03) and embeddings (03-04).
"""

import httpx
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

provider_retry = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
embed_retry = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
