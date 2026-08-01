"""SSE envelope tests (D-02) — byte-for-byte Go-scanner compatibility."""

import json

from app.sse import done_event, format_event, heartbeat, usage_event


def go_scan_stream(stream: str) -> list[dict]:
    """Simulates backend/internal/ai/engine/sse.go scanSSEEvents + parseSSEBlock.

    - splits on blank lines (event boundary)
    - tolerates comment-only blocks (": ping") -> skipped (nil)
    - collects "data:" fields, joining multi-line with \n
    - callback unmarshals the raw envelope JSON (EngineEvent{type, data})
    """
    events: list[dict] = []
    for block in stream.split("\n\n"):
        lines = [l.rstrip("\r") for l in block.split("\n")]
        data_parts: list[str] = []
        for line in lines:
            if line.startswith(":"):
                continue  # comment
            if line.startswith("data:"):
                data_parts.append(line[len("data:"):].strip())
        if not data_parts:
            continue  # comment-only or empty block -> nil per Go
        events.append(json.loads("\n".join(data_parts)))
    return events


def test_format_event_exact_bytes() -> None:
    """(a) exact byte equality with the Go contract wire format."""
    assert format_event("delta", {"content": "Hello"}) == 'data: {"type":"delta","data":{"content":"Hello"}}\n\n'


def test_format_event_no_literal_newlines_in_json() -> None:
    """(b) the data: payload contains no literal newline (Pitfall 3)."""
    payload = format_event("delta", {"content": "line1\nline2\n"})
    data_line = payload.removeprefix("data: ").rstrip("\n\n")
    assert "\n" not in data_line


def test_heartbeat() -> None:
    """(c) heartbeat is the exact Go-tolerated comment line."""
    assert heartbeat() == ": ping\n\n"


def test_usage_event_embeds_five_fields() -> None:
    """(d) usage_event embeds all five normalized usage fields."""
    evt = usage_event("deepseek", "deepseek-chat", 12, 3, 0.000012)
    parsed = json.loads(evt.removeprefix("data: ").rstrip("\n\n"))
    assert parsed["type"] == "usage"
    assert parsed["data"] == {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "input_tokens": 12,
        "output_tokens": 3,
        "cost": 0.000012,
    }


def test_done_event() -> None:
    """(e) done_event emits data: {"type":"done","data":{}}."""
    assert done_event() == 'data: {"type":"done","data":{}}\n\n'


def test_round_trip_through_go_scanner_equivalent() -> None:
    """Full stream round-trips through a Go-scanner-equivalent parse.

    Mirrors the RESEARCH live probe: heartbeat + deltas + usage + done all
    survive with type and data intact, comments tolerated, no garbage events.
    """
    stream = (
        heartbeat()
        + format_event("delta", {"content": "Hello"})
        + format_event("delta", {"content": " world"})
        + usage_event("anthropic", "claude-3-5-sonnet-latest", 12, 3, 0.000081)
        + done_event()
    )
    events = go_scan_stream(stream)
    assert [e["type"] for e in events] == ["delta", "delta", "usage", "done"]
    assert events[0]["data"] == {"content": "Hello"}
    assert events[1]["data"] == {"content": " world"}
    assert events[2]["data"] == {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
        "input_tokens": 12,
        "output_tokens": 3,
        "cost": 0.000081,
    }
    assert events[3]["data"] == {}
