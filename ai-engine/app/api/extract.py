"""Document endpoints (PYE-04): POST /v1/extract + POST /v1/documents.

``/v1/extract`` is the Go ``ExtractRequest{DocumentPath}`` seam — pure text
extraction, NO DB access, so X-School-Schema is NOT required (matches the
existing Go client route and ExtractResponse{Status} contract; extra fields
are additive — Go ignores unknown JSON).

``/v1/documents`` is the one-call ingest (Go ``IngestDocument``) and IS
tenant-scoped (D-09): X-School-Schema is required and validated inside
``insert_chunks`` (regex + existence, no fallback) before any SQL.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.documents.extractors import extract_document
from app.documents.pipeline import ingest_document
from app.providers.embedding import EmbeddingNotConfiguredError
from app.security import require_token

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


class ExtractRequestIn(BaseModel):
    document_path: str  # absolute path inside shared uploads volume (Go ExtractRequest parity)


class DocumentsRequestIn(BaseModel):
    document_path: str
    collection: str = "default"


def _school_header(x_school_schema: str | None) -> str:
    if not x_school_schema:
        raise HTTPException(status_code=400, detail="X-School-Schema header required (D-09)")
    return x_school_schema


@router.post("/extract")
async def extract(req: ExtractRequestIn) -> dict:
    try:
        res = await extract_document(req.document_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "status": "success",
        "pages": res.pages,
        "ocr_pages": res.ocr_pages,
        "chars": res.chars,
        "warnings": res.warnings,
    }


@router.post("/documents")
async def documents(
    req: DocumentsRequestIn,
    x_school_schema: str | None = Header(default=None),
) -> dict:
    schema_name = _school_header(x_school_schema)
    try:
        return await ingest_document(req.document_path, schema_name, req.collection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except EmbeddingNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
