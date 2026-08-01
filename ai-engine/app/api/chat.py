"""POST /v1/chat + /v1/chat/stream routes (PYE-04) — provider:model routing (D-03).

The stream route emits the D-02 SSE envelope byte-compatible with the Go
scanner (backend/internal/ai/engine/sse.go): one compact-JSON ``data:`` line
per event, blank-line boundaries, ``: ping`` heartbeats <= 30s, in-band error
events AFTER HTTP 200, and no gzip (RESEARCH Pitfall 3). Usage is normalized
on every response: {provider, model, input_tokens, output_tokens, cost}.

require_token comes from app.security (03-04 extracted it there to break the
main <-> api circular import — see the 03-04 SUMMARY deviation note).
"""

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.providers.cost import calculate_cost
from app.providers.registry import build_provider_registry, parse_model_composite
from app.security import require_token
from app.sse import done_event, format_event, heartbeat, usage_event

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])

_REDACTED = "[REDACTED]"
# Header/query fragments that may carry credentials inside SDK error strings
# (T-03-03-03): redact the value, keep the attribute name for debuggability.
_HEADER_SECRET_RE = re.compile(r"(?i)(authorization|api[-_]?key|x-api-key)\s*[:=]\s*\S+")
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9._~+/\-=]+")


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequestIn(BaseModel):
    model: str | None = None  # optional; model_hint fallback when prompt_type set (D-08)
    messages: list[ChatMessageIn]
    stream: bool = False
    max_tokens: int | None = None  # optional; capped by settings.AI_MAX_TOKENS (T-03-03-02)
    # Optional prompt library wiring (D-08 / PYE-03): additive fields — Go
    # never sends them, so the ChatRequest{model, messages, stream} shape
    # stays 1:1 (Go's decoder ignores unknown JSON fields).
    prompt_type: str | None = None
    prompt_alias: str = "prod"  # dev/staging/prod version alias (D-08)


class ChatResponseOut(BaseModel):
    message: dict[str, str]
    usage: dict  # {provider, model, input_tokens, output_tokens, cost} — additive, Go ignores


def _clients() -> dict[str, Any]:  # build per-request; configured-only (D-01)
    reg = build_provider_registry()
    clients: dict[str, Any] = {}
    # import provider classes inside to avoid import cycles
    from app.providers.anthropic_provider import AnthropicProvider
    from app.providers.ollama_provider import OllamaProvider
    from app.providers.openai_compat import OpenAICompatProvider

    for name, info in reg.items():
        if not info.configured:
            continue
        if info.kind == "anthropic":
            clients[name] = AnthropicProvider()
        elif info.kind == "ollama":
            clients[name] = OllamaProvider()
        else:
            clients[name] = OpenAICompatProvider(info)
    return clients


def _sanitize_error_message(message: str) -> str:
    """Redact credentials before echoing SDK errors into SSE events (T-03-03-03).

    ``str(e)`` of provider SDK errors may embed the request URL or headers
    (e.g. ``Authorization: Bearer sk-...`` or ``?api_key=...``). Strip every
    configured secret value plus common header/query key fragments so an
    in-band error event never leaks a credential (Rule B6 spirit).
    """
    cleaned = message
    for secret in (
        settings.AI_ENGINE_TOKEN,
        settings.AI_ANTHROPIC_API_KEY,
        settings.AI_OPENAI_API_KEY,
        settings.AI_DEEPSEEK_API_KEY,
        settings.AI_OPENROUTER_API_KEY,
        settings.AI_AZURE_OPENAI_API_KEY,
        settings.AI_PGVECTOR_DSN,
    ):
        if secret:
            cleaned = cleaned.replace(secret, _REDACTED)
    cleaned = _HEADER_SECRET_RE.sub(lambda m: f"{m.group(1)}: {_REDACTED}", cleaned)
    cleaned = _BEARER_RE.sub("Bearer " + _REDACTED, cleaned)
    return cleaned


def _resolve_messages(req: ChatRequestIn) -> tuple[list[dict[str, Any]], str]:
    """Optional D-08 prompt_type wiring: render a library prompt as the first
    system message; model_hint fallback when model is not provided.

    Returns (messages, model_composite). ``prompt_type`` is additive — Go never
    sends it, so behavior is unchanged when absent (ChatRequest shape 1:1).
    """
    from app.prompts.prompt_library import library

    messages = [m.model_dump() for m in req.messages]
    model = req.model
    if req.prompt_type:
        try:
            system_msg = library.render_system(req.prompt_type, alias=req.prompt_alias)
            meta = library.get_prompt(req.prompt_type, req.prompt_alias)["meta"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None  # T-03-07-05: sanitized
        messages = [{"role": "system", "content": system_msg}, *messages]
        if model is None:
            # documented convenience: explicit model always wins; model_hint
            # only fills the gap (03-07 Task 3)
            hint = meta.get("model_hint") if isinstance(meta, dict) else None
            if isinstance(hint, str):
                model = hint
    if not model:
        raise HTTPException(
            status_code=400,
            detail="model is required (or set prompt_type with a model_hint)",
        )
    return messages, model


@router.post("/chat")
async def chat(req: ChatRequestIn) -> ChatResponseOut:
    messages, model = _resolve_messages(req)
    provider_name, model = parse_model_composite(model)
    clients = _clients()
    if provider_name not in clients:
        raise HTTPException(status_code=503, detail=f"provider not configured: {provider_name}")
    max_tokens = min(req.max_tokens or settings.AI_MAX_TOKENS, settings.AI_MAX_TOKENS)
    text, itok, otok = await clients[provider_name].chat(
        model, messages, max_tokens
    )
    return ChatResponseOut(
        message={"role": "assistant", "content": text},
        usage={
            "provider": provider_name,
            "model": model,
            "input_tokens": itok,
            "output_tokens": otok,
            "cost": calculate_cost(itok, otok, provider_name),
        },
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequestIn, request: Request) -> StreamingResponse:
    messages, model = _resolve_messages(req)
    provider_name, model = parse_model_composite(model)
    clients = _clients()
    if provider_name not in clients:
        raise HTTPException(status_code=503, detail=f"provider not configured: {provider_name}")
    max_tokens = min(req.max_tokens or settings.AI_MAX_TOKENS, settings.AI_MAX_TOKENS)

    async def gen() -> AsyncIterator[str]:
        yield heartbeat()  # immediate keep-alive (D-02; heartbeats <= 30s)
        try:
            stream = clients[provider_name].stream(model, messages, max_tokens)
            while True:
                # F4: bound each upstream wait so a stalled provider cannot
                # violate the D-02 heartbeat guarantee — emit a keep-alive on
                # timeout and keep the stream alive.
                try:
                    evt = await asyncio.wait_for(
                        anext(stream), timeout=settings.AI_HEARTBEAT_INTERVAL_SECONDS
                    )
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield heartbeat()
                    continue
                except StopAsyncIteration:
                    break
                if await request.is_disconnected():  # context-bound stream (T-03-03-06)
                    return
                if "delta" in evt:
                    yield format_event("delta", {"content": evt["delta"]})
                elif "usage" in evt:
                    itok, otok = evt["usage"]
                    yield usage_event(
                        provider_name, model, itok, otok,
                        calculate_cost(itok, otok, provider_name),
                    )
            yield done_event()
        except Exception as e:  # in-band error AFTER HTTP 200 (D-02/ROADMAP: in-band errors)
            yield format_event("error", {"message": _sanitize_error_message(str(e))})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
