import contextvars
import json
import logging
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Request

from app.api.chat import router as chat_router
from app.api.embed import router as embed_router
from app.api.extract import router as extract_router
from app.api.providers import router as providers_router
from app.api.search import router as search_router
from app.security import require_token

# ──────────────────────────────────────────────────────────────
# Structured JSON logging with per-request correlation (OBS-01 D-02).
#
# `request_id` is the correlation key shared with the Go backend via the
# X-Request-ID header. It lives in a contextvar so every log record emitted
# while a request is in flight carries the same ID, matching the Go side's
# JSON logs. PII-safe (D-04): only record metadata + message are emitted —
# raw document/prompt bodies are never added to log records.
# ──────────────────────────────────────────────────────────────

current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log record, including the request_id."""

    converter = time.gmtime  # UTC timestamps for cross-service correlation

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    root = logging.getLogger()
    # Only install the JSON handler when nothing is configured yet — test
    # runners (pytest log_cli/caplog) install their handlers before app
    # import, and they must keep working.
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # uvicorn keeps its own loggers; stop them propagating to the root so
    # access/error lines are not double-logged.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).propagate = False


_configure_logging()

app = FastAPI(title="Academio AI Engine")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Any) -> Any:
    """Correlate every request's logs via X-Request-ID (OBS-01 D-02).

    Reads the incoming X-Request-ID (sent by the Go backend through the
    EngineClient seam), generates a uuid4 hex when absent, publishes it on
    the logging contextvar for the duration of the request and echoes it back
    on the response header so the caller can trace the full Go → Python path.
    """
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = current_request_id.set(request_id)
    try:
        response = await call_next(request)
    finally:
        current_request_id.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-engine"}


@app.get("/v1/health", dependencies=[Depends(require_token)])
async def v1_health() -> dict:
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(embed_router)
app.include_router(extract_router)
app.include_router(providers_router)
app.include_router(search_router)
