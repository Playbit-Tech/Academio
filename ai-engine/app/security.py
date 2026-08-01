"""Service-token security (D-01 / PYE-05): X-AI-Engine-Token only, never user JWT.

Defined here (not app.main) so the api route modules can import the dependency
without a main <-> api circular import. See the 03-04 SUMMARY deviation note.
"""

from fastapi import Header, HTTPException

from app.config import settings


def require_token(x_ai_engine_token: str | None = Header(default=None)) -> None:
    if not settings.AI_ENGINE_TOKEN or x_ai_engine_token != settings.AI_ENGINE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")
