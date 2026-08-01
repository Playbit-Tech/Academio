"""POST /v1/search — tenant-aware hybrid RAG (PYE-04/PYE-05, D-06/D-07/D-09).

The request body carries the query + optional metadata filters; the tenant is
passed via the ``X-School-Schema`` header (D-09) and validated
(``^school_[0-9]+$`` + existence, no fallback — D-07) inside
``hybrid_search`` BEFORE any SQL runs. Missing/invalid schema -> 400.

Response shape feeds the Go AI assistant (Phase 5): ``results[]`` with
``document_id#chunk_index`` citations + a pre-compressed ``context`` block
(T-03-06-04: retrieved text is DATA, framed by citation boundaries).
DoS bounds: query length 1..2000, top_k 1..100 (T-03-06-05).
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.providers.embedding import EmbeddingNotConfiguredError
from app.rag.hybrid import hybrid_search
from app.rag.rerank import compress_context, rank_and_cite
from app.security import require_token

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


class FilterIn(BaseModel):
    key: str  # collection | document_id | embedding_model | chunk_index (D-06 allowlist)
    value: str


class SearchRequestIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: list[FilterIn] | None = None
    top_k: int = Field(default=10, ge=1, le=100)  # capped (DoS bound, T-03-06-05)
    include_context: bool = True  # return compressed context block


@router.post("/search")
async def search(
    req: SearchRequestIn,
    x_school_schema: str | None = Header(default=None),
) -> dict:
    if not x_school_schema:
        raise HTTPException(status_code=400, detail="X-School-Schema header required (D-09)")
    try:
        merged = await hybrid_search(
            x_school_schema,
            req.query,
            [f.model_dump() for f in req.filters] if req.filters else None,
            top_k=req.top_k,
        )
    except ValueError as e:  # invalid schema, missing schema, zero-norm query embed
        raise HTTPException(status_code=400, detail=str(e)) from e
    except EmbeddingNotConfiguredError as e:
        # no AI_OPENAI_API_KEY -> fail-loud 503 (/v1/embed parity)
        raise HTTPException(status_code=503, detail=str(e)) from e
    except RuntimeError as e:  # AI_PGVECTOR_DSN not configured (get_pool fail-loud 503)
        raise HTTPException(status_code=503, detail=str(e)) from e
    ranked = rank_and_cite(merged, top_k=req.top_k)
    context, _kept = compress_context(ranked)
    return {
        "query": req.query,
        "schema": x_school_schema,
        "results": ranked,
        "context": context if req.include_context else None,
    }
