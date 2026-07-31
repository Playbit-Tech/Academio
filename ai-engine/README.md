# ai-engine

Additive Python AI engine for Academio. The Go backend is the brain (agents, routing,
failover, orchestration); this service is the engine — Python-side document intelligence,
multi-provider LLM breadth, and compute that belongs outside the Go monolith.

Authentication is service-to-service via the `X-AI-Engine-Token` header (never a user JWT,
never a URL parameter). `GET /health` is intentionally unauthenticated — it is the container
healthcheck target.

**Status: Phase 1 skeleton** — pinned FastAPI project, `/health` + token-protected `/v1/health`,
smoke tests, and a multi-stage container image. Document intelligence, providers, and pgvector
integration land in later phases.

## Bootstrap

```bash
uv sync
uv run uvicorn app.main:app --port 8000
uv run pytest
```

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13 is pinned in `.python-version`).

## Repository note

This directory is submodule-ready — extract it to `Playbits/Academio-AI` when the remote
exists, matching the `backend/`, `frontend/`, and `mobile/` submodule pattern.
