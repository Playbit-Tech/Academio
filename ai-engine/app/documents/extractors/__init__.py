"""Extractor dispatcher + shared ExtractionResult (PYE-02, D-04).

``extract_document`` enforces the DoS bounds BEFORE any parsing (T-03-05-03):
file existence, file size cap (AI_MAX_DOC_MB), and type allowlist. Page caps
are enforced inside the PDF extractor (AI_MAX_DOC_PAGES). Unknown types are
rejected with ValueError -> 400 at the route.
"""

import os
from dataclasses import dataclass, field

from app.config import settings

_OFFICE_EXTS = {".docx", ".pptx", ".xlsx", ".xls", ".csv", ".txt"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


@dataclass
class ExtractionResult:
    """Normalized extraction output consumed by the chunker/pipeline."""

    text: str = ""
    pages: int = 0
    ocr_pages: int = 0
    chars: int = 0
    warnings: list[str] = field(default_factory=list)


async def extract_document(path: str) -> ExtractionResult:
    """Route a file by extension to the right extractor (size/type gated)."""
    if not os.path.isfile(path):
        raise ValueError(f"file not found: {path}")
    size_bytes = settings.AI_MAX_DOC_MB * 1024 * 1024
    if os.path.getsize(path) > size_bytes:
        raise ValueError(f"document exceeds {settings.AI_MAX_DOC_MB}MB size limit")
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        from app.documents.extractors.pdf import extract_pdf

        return await extract_pdf(path)
    if ext in _OFFICE_EXTS:
        from app.documents.extractors.office import extract_office

        return await extract_office(path, ext)
    if ext in _IMAGE_EXTS:
        from app.documents.extractors.image import extract_image

        return await extract_image(path)
    raise ValueError(f"unsupported document type: {ext!r}")
