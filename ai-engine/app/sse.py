"""SSE envelope writer matching the Go EngineEvent contract (D-02).

Wire format (byte-compatible with backend/internal/ai/engine/sse.go):
- one compact-JSON ``data:`` line per event, blank-line boundaries
  (``\\n\\n``) — the Go scanner splits on blank lines and joins multi-line
  ``data:`` fields, so literal newlines inside the JSON would corrupt events
  (RESEARCH Pitfall 3). ``separators=(",", ":")`` + ``ensure_ascii=True`` are
  MANDATORY.
- heartbeats as ``: ping`` comment lines (Go ``parseSSEBlock`` ignores
  comment-only blocks).
- NO ``event:`` field — ``type`` lives INSIDE the JSON payload
  (EngineEvent{type, data}, engine.go lines 20-23).
"""

import json
from typing import Any

# EngineEvent envelope: {type: "delta"|"citation"|"usage"|"error"|"done", data: <object>}
# Wire format: one compact JSON "data:" line per event, blank-line boundaries,
# heartbeats as ": ping" comment lines (Go sse.go tolerates). NO "event:" field.


def format_event(event_type: str, data: dict[str, Any]) -> str:
    payload = json.dumps({"type": event_type, "data": data}, separators=(",", ":"), ensure_ascii=True)
    return f"data: {payload}\n\n"


def heartbeat() -> str:
    return ": ping\n\n"


def done_event() -> str:
    return format_event("done", {})


def usage_event(provider: str, model: str, input_tokens: int, output_tokens: int, cost: float) -> str:
    return format_event("usage", {"provider": provider, "model": model,
                                  "input_tokens": input_tokens, "output_tokens": output_tokens, "cost": cost})
