"""PDF extractor — per-page routing (D-04, ROADMAP criterion 4).

Each page is classified by its text layer: pages with more than
``DIGITAL_THRESHOLD`` chars are parsed with pypdf (fast text extraction);
pages below the threshold are treated as scanned and routed to Tesseract OCR
via pdf2image at 300 DPI with Pillow preprocessing (grayscale + autocontrast)
for quality (D-04). The page cap (AI_MAX_DOC_PAGES, default 200) bounds OCR
cost / zip-bomb DoS (T-03-05-03). Tesseract must exist in the runtime image
(Dockerfile apt layer — RESEARCH Pitfall 6); the host has no binary.
"""

import pytesseract
from pdf2image import convert_from_path
from PIL import ImageOps
from pypdf import PdfReader

from app.config import settings
from app.documents.extractors import ExtractionResult

DIGITAL_THRESHOLD = 20  # chars; below this a page is treated as scanned (D-04)
OCR_DPI = 300  # D-04: >= 300 DPI
MAX_PAGES = settings.AI_MAX_DOC_PAGES  # 200 — page cap (OCR/zip-bomb DoS bound)


async def extract_pdf(path: str) -> ExtractionResult:
    reader = PdfReader(path)
    pages = min(len(reader.pages), MAX_PAGES)
    res = ExtractionResult(pages=pages)
    # F5: convert the PDF to images ONCE (up to the page cap), then route each
    # page to pypdf (digital) or OCR (scanned). Converting per scanned page
    # re-parses the whole document O(pages^2) — instead render once at OCR DPI
    # and index the returned PIL images.
    page_images = convert_from_path(path, dpi=OCR_DPI)[:pages]
    for i in range(pages):
        page_text = (reader.pages[i].extract_text() or "").strip()
        if len(page_text) > DIGITAL_THRESHOLD:
            res.text += f"\n\n[page {i + 1}]\n{page_text}"
        else:
            img = page_images[i] if i < len(page_images) else None
            res.text += f"\n\n[page {i + 1}]\n{_ocr_image(img) if img is not None else ''}"
            res.ocr_pages += 1
    res.chars = len(res.text)
    if len(reader.pages) > MAX_PAGES:
        res.warnings.append(f"truncated at {MAX_PAGES} pages")
    return res


def _ocr_image(img) -> str:
    # Pillow preprocessing for OCR quality (D-04): grayscale + autocontrast
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    return pytesseract.image_to_string(gray).strip()
