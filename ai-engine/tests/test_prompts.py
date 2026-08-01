"""Prompt library tests (PYE-03 / D-08): load, cache, render, aliases.

Hermetic — no network, no DB (D-12). The nine Git-backed prompts under
``ai-engine/prompts/`` are the fixtures; tests prove PYE-03 coverage (all nine
render with canonical vars), StrictUndefined fail-loud behavior (missing vars
raise instead of leaking ``{{ var }}``), alias resolution (dev/staging/prod),
file-read caching, the AI_PROMPTS_DIR override, and zero ``{% %}`` control
blocks in any template (T-03-07-01).
"""

import shutil
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.chat as chat_api
from app.config import Settings
from app.config import settings as app_settings
from app.main import app
from app.prompts import PROMPT_TYPES, PromptLibrary

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

# Canonical vars map per prompt type (Task 1 template placeholders). This is
# the PYE-03 coverage fixture: every type must render with exactly these.
VARS_FIXTURE: dict[str, dict[str, Any]] = {
    "report-comments": {
        "student_name": "Ada",
        "level": "JSS2",
        "observations": "Works hard, participates well",
    },
    "lesson-plans": {
        "subject": "Mathematics",
        "level": "JSS2",
        "topic": "Quadratic equations",
        "duration_minutes": 40,
    },
    "questions": {
        "question_count": 5,
        "subject": "Mathematics",
        "level": "JSS2",
        "topic": "Algebra",
    },
    "rubrics": {
        "criteria_count": 4,
        "assignment": "Essay",
        "subject": "English",
        "level": "SS1",
    },
    "behaviour-summary": {
        "student_name": "Ada",
        "period": "Term 1",
        "notes": "Attentive, kind to classmates",
    },
    "attendance-analysis": {
        "student_name": "Ada",
        "period": "Term 1",
        "attendance_summary": "95% present, 3 unexplained absences",
    },
    "parent-letters": {
        "tone": "formal",
        "parent_name": "Mrs Okafor",
        "student_name": "Ada",
        "topic": "academic progress",
    },
    "meeting-minutes": {"notes": "Discuss budget, decide on new lab, follow up on hire"},
    "translation": {
        "source_language": "English",
        "target_language": "Yoruba",
        "text": "Good morning, how are you?",
    },
}


def test_render_report_comments_with_vars() -> None:
    """(a) render() with full vars: substitutes values, no literal '{{' leak."""
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    out = lib.render("report-comments", VARS_FIXTURE["report-comments"])
    assert "Ada" in out
    assert "JSS2" in out
    assert "{{" not in out


def test_render_missing_variable_raises_value_error() -> None:
    """(b) Missing variable -> ValueError (StrictUndefined), never a silent
    '{{ var }}' leak (T-03-07-01)."""
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    with pytest.raises(ValueError, match="prompt render failed"):
        lib.render("report-comments", {"student_name": "Ada"})  # level/observations missing


def test_unknown_prompt_type_raises_value_error() -> None:
    """(c) Unknown prompt type -> ValueError before any file access (T-03-07-02)."""
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    with pytest.raises(ValueError, match="unknown prompt type"):
        lib.render("not-a-type", {})


def test_all_nine_types_render_with_canonical_vars() -> None:
    """(d) PYE-03 coverage: all nine prompt types render with their vars map."""
    assert set(VARS_FIXTURE) == set(PROMPT_TYPES)
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    for prompt_type, vars_map in VARS_FIXTURE.items():
        out = lib.render(prompt_type, vars_map)
        assert isinstance(out, str) and out.strip()
        assert "{{" not in out


def test_alias_resolution() -> None:
    """(e) dev/staging/prod alias resolution (D-08): prod->latest, dev->working;
    unknown alias treated as a raw version selector."""
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    assert lib.get_prompt("questions", "prod")["alias"] == "latest"
    assert lib.get_prompt("questions", "staging")["alias"] == "latest"
    assert lib.get_prompt("questions", "dev")["alias"] == "working"
    assert lib.get_prompt("questions", "1.0")["alias"] == "1.0"  # raw selector


def test_get_prompt_caches_file_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(f) Second call with same (type, alias) does not re-read the files."""
    reads = {"count": 0}
    original_read_text = Path.read_text

    def counting_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        reads["count"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    lib = PromptLibrary(prompts_dir=str(PROMPTS_DIR))
    first = lib.get_prompt("report-comments", "prod")
    second = lib.get_prompt("report-comments", "prod")
    assert first is second  # cache hit returns the SAME dict
    assert reads["count"] == 2  # prompt.yaml + template.txt read exactly once


def test_prompts_dir_override(tmp_path: Path) -> None:
    """(g) AI_PROMPTS_DIR override: a library pointed at a temp copy of one
    prompt type loads and renders from there."""
    src = PROMPTS_DIR / "report-comments"
    dst = tmp_path / "prompts" / "report-comments"
    dst.mkdir(parents=True)
    shutil.copy2(src / "prompt.yaml", dst / "prompt.yaml")
    shutil.copy2(src / "template.txt", dst / "template.txt")
    lib = PromptLibrary(prompts_dir=str(tmp_path / "prompts"))
    out = lib.render("report-comments", VARS_FIXTURE["report-comments"])
    assert "Ada" in out


def test_no_control_blocks_in_templates() -> None:
    """(h) No '{% ... %}' control flow in any of the 9 templates (T-03-07-01):
    server-authored templates must not embed executable logic."""
    for prompt_type in PROMPT_TYPES:
        tpl = (PROMPTS_DIR / prompt_type / "template.txt").read_text(encoding="utf-8")
        assert "{%" not in tpl, f"{prompt_type}/template.txt contains a control block"


# ---------------------------------------------------------------------------
# Chat wiring tests (03-07 Task 3): optional prompt_type on /v1/chat and
# /v1/chat/stream is additive — no prompt_type => byte-identical behavior.
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    s = Settings(AI_ENGINE_TOKEN="test-token-123")
    # The app's require_token dependency reads the module-level singleton;
    # share the test token with that same instance (mirrors test_chat.py).
    app_settings.AI_ENGINE_TOKEN = s.AI_ENGINE_TOKEN
    return s


@pytest.fixture
async def client(settings: Settings) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-AI-Engine-Token": settings.AI_ENGINE_TOKEN}


class RecordingProvider:
    """Records the (model, messages) it was asked to serve — no network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    async def chat(self, model: str, messages: list[Any], max_tokens: int | None = None):
        self.calls.append((model, messages))
        return "assistant reply", 5, 3


class RecordingStreamProvider(RecordingProvider):
    async def stream(self, model: str, messages: list[Any], max_tokens: int | None = None):
        self.calls.append((model, messages))
        yield {"delta": "assistant reply"}


async def test_chat_without_prompt_type_unchanged(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(i) No prompt_type: request passes through untouched (additive wiring)."""
    provider = RecordingProvider()
    monkeypatch.setattr(chat_api, "_clients", lambda: {"anthropic": provider})
    resp = await client.post(
        "/v1/chat",
        json={
            "model": "anthropic:claude-3-5-sonnet-latest",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert provider.calls == [("claude-3-5-sonnet-latest", [{"role": "user", "content": "hi"}])]


async def test_chat_with_prompt_type_prepends_system_and_falls_back_to_model_hint(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(j) prompt_type: system message rendered (lenient — no vars from the Go
    contract, D-08) prepended; model omitted -> model_hint
    (anthropic:claude-3-5-sonnet-latest) used."""
    provider = RecordingProvider()
    monkeypatch.setattr(chat_api, "_clients", lambda: {"anthropic": provider})
    resp = await client.post(
        "/v1/chat",
        json={
            "prompt_type": "report-comments",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    model, messages = provider.calls[0]
    assert model == "claude-3-5-sonnet-latest"  # model_hint fallback (D-08)
    assert messages[0]["role"] == "system"
    assert "report card comments" in messages[0]["content"].lower()
    assert "{{" not in messages[0]["content"]  # lenient render: no literal slot leak
    assert messages[1] == {"role": "user", "content": "hi"}


async def test_chat_unknown_prompt_type_is_400_without_provider_call(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(k) Unknown prompt_type -> 400 BEFORE any provider call (T-03-07-05)."""
    provider = RecordingProvider()
    monkeypatch.setattr(chat_api, "_clients", lambda: {"anthropic": provider})
    resp = await client.post(
        "/v1/chat",
        json={
            "prompt_type": "not-a-real-type",
            "model": "anthropic:claude-3-5-sonnet-latest",
            "messages": [{"role": "user", "content": "hi"}],
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 400
    assert "unknown prompt type" in resp.json()["detail"]
    assert provider.calls == []


async def test_stream_with_prompt_type_prepends_system(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(l) /chat/stream with prompt_type: same system-message wiring, SSE
    envelope intact (delta + done events, no gzip)."""
    provider = RecordingStreamProvider()
    monkeypatch.setattr(chat_api, "_clients", lambda: {"anthropic": provider})
    resp = await client.post(
        "/v1/chat/stream",
        json={
            "prompt_type": "questions",
            "model": "anthropic:claude-3-5-sonnet-latest",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
        headers=_headers(settings),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    model, messages = provider.calls[0]
    assert model == "claude-3-5-sonnet-latest"
    assert messages[0]["role"] == "system"
    assert "questions" in messages[0]["content"].lower()  # lenient-rendered template
    assert "{{" not in messages[0]["content"]
    assert 'data: {"type":"delta"' in resp.text
    assert 'data: {"type":"done"' in resp.text
