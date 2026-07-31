from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import settings

app = FastAPI(title="Academio AI Engine")


def require_token(x_ai_engine_token: str | None = Header(default=None)) -> None:
    if not settings.AI_ENGINE_TOKEN or x_ai_engine_token != settings.AI_ENGINE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-engine"}


@app.get("/v1/health", dependencies=[Depends(require_token)])
async def v1_health() -> dict:
    return {"status": "ok"}
