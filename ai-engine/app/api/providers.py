"""GET /v1/providers (PYE-04): provider health status (D-10 data source).

Consumed by Go INT-02 in Phase 5 — field names are the stable contract:
{provider, status, latency_ms, last_checked, cooldown_until}. A provider
without a key reports status "unavailable" INSIDE the 200 list — the endpoint
never 500s because of missing keys (RESEARCH Pitfall 5 / A3); only unexpected
internal errors 500.
"""

from fastapi import APIRouter, Depends

from app.providers.healthcheck import ProviderHealth
from app.providers.registry import build_provider_registry
from app.security import require_token

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])

# Module-level singleton: TTL cache + cooldown state shared across requests (D-10)
_health = ProviderHealth()


@router.get("/providers")
async def providers() -> dict:
    reg = build_provider_registry()
    results = []
    for name, info in reg.items():
        status = await _health.check(name, info)
        results.append(
            {
                "provider": name,
                "status": status.status,
                "latency_ms": status.latency_ms,
                "last_checked": status.last_checked,
                "cooldown_until": status.cooldown_until,
            }
        )
    return {"providers": results}
