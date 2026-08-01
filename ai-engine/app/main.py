from fastapi import Depends, FastAPI

from app.api.chat import router as chat_router
from app.api.embed import router as embed_router
from app.api.extract import router as extract_router
from app.api.providers import router as providers_router
from app.api.search import router as search_router
from app.security import require_token

app = FastAPI(title="Academio AI Engine")


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
