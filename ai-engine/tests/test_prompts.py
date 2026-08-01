"""Prompt library tests (PYE-03 / D-08): load, cache, render, aliases.

Hermetic — no network, no DB (D-12). The nine Git-backed prompts under
``ai-engine/prompts/`` are the fixtures; tests prove PYE-03 coverage (all nine
render with canonical vars), StrictUndefined fail-loud behavior (missing vars
raise instead of leaking ``{{ var }}``), alias resolution (dev/staging/prod),
file-read caching, the AI_PROMPTS_DIR override, and zero ``{% %}`` control
blocks in any template (T-03-07-01).
"""

import shutil
from pathlib import Path
from typing import Any

import pytest

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
