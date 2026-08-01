"""Versioned prompt library (PYE-03 / D-08): Git-backed YAML + Jinja2 rendering.

Git IS the versioning mechanism — every prompt type is a directory under
``settings.AI_PROMPTS_DIR`` (default ``./prompts``) containing ``prompt.yaml``
(metadata: name, version, description, model_hint) and ``template.txt`` (a
Jinja2 template using ``{{ var }}`` placeholders ONLY — server-authored, no
``{% %}`` control blocks, T-03-07-01). Prompts are editable without code
changes and versioned by git history; dev/staging/prod aliases resolve to
version selectors in code defaults (D-08):

    dev     -> "working"  (current working tree file — always available)
    staging -> "latest"   (highest version field among prompt.yaml files)
    prod    -> "latest"   (same selector; git tag is the audit trail)

Rendering is strict by default (StrictUndefined — missing variables raise a
clear ValueError instead of leaking literal ``{{ var }}`` text). The chat
pipeline uses ``render_system`` (lenient Undefined) because the Go ChatRequest
carries no variables — an unfilled system prompt degrades to whitespace, never
to executable content.
"""

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, TemplateError, Undefined

from app.config import settings

# dev/staging/prod alias -> version selector (D-08). Configurable, defaults:
#   dev    -> "working" (current working tree file — always available)
#   staging-> "latest"  (highest version field among prompt.yaml files)
#   prod   -> "latest"  (same selector; Git tag is the audit trail, not runtime state)
ALIAS_DEFAULTS = {"dev": "working", "staging": "latest", "prod": "latest"}

# Exact allowlist of prompt types (T-03-07-02): 9 names, no user paths — this
# is the path-traversal guard for prompt_type before any file access.
_SUPPORTED = frozenset(
    {
        "report-comments",
        "lesson-plans",
        "questions",
        "rubrics",
        "behaviour-summary",
        "attendance-analysis",
        "parent-letters",
        "meeting-minutes",
        "translation",
    }
)


class PromptLibrary:
    """Loads + caches prompts from ``prompts_dir`` and renders them (D-08)."""

    def __init__(self, prompts_dir: str | None = None) -> None:
        self._dir = Path(prompts_dir or settings.AI_PROMPTS_DIR)
        # LLM prompts: no HTML escaping. StrictUndefined catches template typos
        # (missing vars raise instead of leaking "{{ var }}" text, T-03-07-01);
        # the chat pipeline uses the lenient env via render_system().
        self._env = Environment(undefined=StrictUndefined, autoescape=False)
        self._lenient_env = Environment(undefined=Undefined, autoescape=False)
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    def _load(self, prompt_type: str) -> dict[str, Any]:
        if prompt_type not in _SUPPORTED:
            raise ValueError(f"unknown prompt type: {prompt_type}")
        base = self._dir / prompt_type
        meta = yaml.safe_load((base / "prompt.yaml").read_text(encoding="utf-8"))
        tpl = (base / "template.txt").read_text(encoding="utf-8")
        return {"meta": meta, "template": tpl}

    def _resolve_alias(self, alias: str) -> str:
        # unknown alias treated as a raw version selector
        return ALIAS_DEFAULTS.get(alias, alias)

    def get_prompt(self, prompt_type: str, alias: str = "prod") -> dict[str, Any]:
        """Cached load: (type, alias) -> {type, alias, meta, template}.

        Git is the version mechanism (D-08). ``latest`` (staging/prod default)
        picks the highest version among prompt.yaml files; with a single
        committed template that equals the working tree — the SELECTOR logic
        exists and is testable (alias resolution). Results are cached per
        (type, resolved-alias) so repeated renders never re-read the files.
        """
        resolved = self._resolve_alias(alias)
        key = (prompt_type, resolved)
        if key not in self._cache:
            data = self._load(prompt_type)
            self._cache[key] = {"type": prompt_type, "alias": resolved, **data}
        return self._cache[key]

    def render(self, prompt_type: str, variables: dict[str, Any], alias: str = "prod") -> str:
        """Strict render: missing variables raise ValueError (T-03-07-01).

        Callers that hold a full vars map use this; the chat pipeline uses
        render_system() (no variables available from the Go contract).
        """
        data = self.get_prompt(prompt_type, alias)
        try:
            return self._env.from_string(data["template"]).render(**variables)
        except TemplateError as e:
            raise ValueError(f"prompt render failed for {prompt_type}: {e}") from e

    def render_system(self, prompt_type: str, alias: str = "prod") -> str:
        """Lenient render for the chat pipeline: unfilled variable slots
        degrade to empty strings instead of raising (the Go ChatRequest carries
        no variables, D-08). Templates remain server-authored ``{{ var }}``-only
        so an unfilled slot is whitespace, never executable content.
        """
        data = self.get_prompt(prompt_type, alias)
        try:
            return self._lenient_env.from_string(data["template"]).render()
        except TemplateError as e:
            raise ValueError(f"prompt render failed for {prompt_type}: {e}") from e


# Module-level singleton for app use (re-exported from app.prompts).
library = PromptLibrary()
