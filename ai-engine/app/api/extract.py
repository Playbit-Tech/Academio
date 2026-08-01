"""Document endpoints (PYE-04): POST /v1/extract + POST /v1/documents.

``/v1/extract`` is the Go ``ExtractRequest{DocumentPath}`` seam — pure text
extraction, NO DB access, so X-School-Schema is NOT required (matches the
existing Go client route and ExtractResponse{Status} contract; extra fields
are additive — Go ignores unknown JSON).

``/v1/documents`` is the one-call ingest (Go ``IngestDocument``) and IS
tenant-scoped (D-09): X-School-Schema is required and validated inside
``insert_chunks`` (regex + existence, no fallback) before any SQL.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.documents.extractors import extract_document
from app.documents.pipeline import ingest_document
from app.providers.embedding import EmbeddingNotConfiguredError
from app.security import require_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


class ExtractRequestIn(BaseModel):
    document_path: str  # absolute path inside shared uploads volume (Go ExtractRequest parity)


class DocumentsRequestIn(BaseModel):
    document_path: str
    collection: str = "default"
    # D-02: stable id supplied by the Go worker (ai_documents.id). Retries reuse it
    # so ON CONFLICT (document_id, chunk_index) DO NOTHING makes ingest idempotent.
    document_id: str | None = None


def _assert_within_uploads(document_path: str) -> None:
    """Containment check (review F2): reject paths outside the uploads volume.

    The caller supplies document_path; with AI_UPLOADS_DIR configured we
    require the resolved path to be inside it so any allowlisted file on the
    container FS cannot be extracted (path traversal / arbitrary-read guard).
    AI_UPLOADS_DIR defaults to empty (containment off) for local dev.
    """
    root = settings.AI_UPLOADS_DIR
    if not root:
        return
    try:
        resolved = Path(document_path).resolve()
        root_resolved = Path(root).resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=f"invalid document path: {e}") from e
    if not resolved.is_relative_to(root_resolved):
        raise HTTPException(
            status_code=400,
            detail=f"document_path must be inside AI_UPLOADS_DIR ({root_resolved})",
        )


def _school_header(x_school_schema: str | None) -> str:
    if not x_school_schema:
        raise HTTPException(status_code=400, detail="X-School-Schema header required (D-09)")
    return x_school_schema


@router.post("/extract")
async def extract(req: ExtractRequestIn) -> dict:
    _assert_within_uploads(req.document_path)
    try:
        res = await extract_document(req.document_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # F8: pdftoppm/tesseract/permission failures -> 502 + log
        logger.exception("extract failed for %s", req.document_path)
        raise HTTPException(status_code=502, detail=f"extract failed: {e}") from e
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
    _assert_within_uploads(req.document_path)
    try:
        return await ingest_document(
            req.document_path, schema_name, req.collection, req.document_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except EmbeddingNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # F8: unexpected pipeline failure -> 502 + log
        logger.exception("document ingest failed for %s", req.document_path)
        raise HTTPException(status_code=502, detail=f"ingest failed: {e}") from e
