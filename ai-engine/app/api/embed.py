"""POST /v1/embed (PYE-04): canonical 1536-dim embeddings (D-05)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.providers.embedding import (
    EmbeddingClient,
    EmbeddingNotConfiguredError,
    validate_vector,
)
from app.security import require_token

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


class EmbedRequestIn(BaseModel):
    # Per-call text count cap (T-03-04-07). The X-School-Schema header is
    # ACCEPTED but not required here — /v1/embed performs no DB access; the
    # header is honored for symmetry with tenant-scoped routes (D-09).
    texts: list[str] = Field(min_length=1, max_length=256)


class EmbedResponseOut(BaseModel):
    model: str
    dimension: int
    embeddings: list[list[float]]


@router.post("/embed")
async def embed(req: EmbedRequestIn) -> EmbedResponseOut:
    try:
        vecs = await EmbeddingClient().embed_texts(req.texts)
    except EmbeddingNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Provider/SDK failures (network, auth, upstream 5xx) map to a clean
        # 502 — never an unhandled traceback (T-03-04-03 fail-loud).
        raise HTTPException(status_code=502, detail="embedding provider error") from e
    if not vecs:  # no embedding survived the pipeline
        raise HTTPException(status_code=500, detail="embedding pipeline returned no vectors")
    # Boundary assert: every vector must match the Phase-2-locked 1536
    # dimension and have non-zero norm before crossing to the caller (D-05,
    # D-14 parity; RESEARCH Pitfall 2 — NaN cosine poisoning downstream).
    for v in vecs:
        try:
            validate_vector(v, settings.AI_EMBEDDING_DIM)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return EmbedResponseOut(
        model=settings.AI_EMBEDDING_MODEL,
        dimension=len(vecs[0]),
        embeddings=vecs,
    )
