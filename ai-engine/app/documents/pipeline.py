"""One-call document pipeline (PYE-02/PYE-04, PIP-01-ready).

``ingest_document`` is the single call the Go asynq worker makes: extract ->
chunk -> embed -> store. Schema validation happens INSIDE ``insert_chunks``
via ``validate_schema_name`` with the pooled connection (D-07/D-09) — the
pipeline passes ``schema_name`` through unchanged; zero-vector rejection from
``embed_texts`` (03-04) propagates as ValueError -> 400 at the route.
"""

import uuid

from app.config import settings
from app.db.vectors import insert_chunks
from app.documents.chunker import chunk_text
from app.documents.extractors import extract_document
from app.providers.embedding import EmbeddingClient


async def ingest_document(
    path: str,
    schema_name: str,
    collection: str = "default",
    document_id: str | None = None,
) -> dict:
    """One-call ingest: extract -> chunk -> embed -> store.

    ``document_id`` (D-02) is the stable id the Go worker supplies
    (``ai_documents.id``); when provided it is used INSTEAD of a fresh uuid4 so
    worker retries hit ``ON CONFLICT (document_id, chunk_index) DO NOTHING`` and
    no duplicate vectors appear after restarts. Default ``None`` preserves the
    original uuid4 behavior for callers that do not supply one.
    """
    extraction = await extract_document(path)  # size/page/type gates inside
    chunks = chunk_text(extraction.text)
    if not chunks:
        return {
            "status": "success",
            "document_id": document_id,  # D-02: echo caller id even with 0 chunks
            "chunks": 0,
            "pages": extraction.pages,
            "ocr_pages": extraction.ocr_pages,
            "warnings": ["no text extracted"],
        }
    vectors = await EmbeddingClient().embed_texts(chunks)  # 1536-dim asserted (03-04)
    doc_id = document_id or str(uuid.uuid4())  # D-02: caller wins, uuid4 fallback
    chunk_rows = [
        {"index": i, "text": t, "embedding": v}
        for i, (t, v) in enumerate(zip(chunks, vectors, strict=True))
    ]
    inserted = await insert_chunks(
        schema_name,
        collection,
        doc_id,
        chunk_rows,
        settings.AI_EMBEDDING_MODEL,
    )
    return {
        "status": "success",
        "document_id": doc_id,
        "chunks": inserted,
        "pages": extraction.pages,
        "ocr_pages": extraction.ocr_pages,
        "chars": extraction.chars,
    }
