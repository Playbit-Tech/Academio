"""Image OCR extractor (PYE-02): Pillow preprocessing + pytesseract.

``Image.MAX_IMAGE_PIXELS`` is a process-wide decompression-bomb guard
(T-03-05-03): Pillow's ``_decompression_bomb_check`` (Image.py) refuses to
decode images above ~80 megapixels (roughly 8k x 8k) before allocating pixel
buffers. NOTE: Pillow 12.3.0 reads this module global from ``Image`` (not
``ImageFile`` — the plan's original snippet referenced the wrong module).
OCR runs on a grayscale + autocontrast copy for quality (D-04). Tesseract
must exist in the runtime image (Dockerfile apt layer — RESEARCH Pitfall 6).
"""

import pytesseract
from PIL import Image, ImageOps

from app.documents.extractors import ExtractionResult

Image.MAX_IMAGE_PIXELS = 80_000_000  # ~8k x 8k cap — decompression-bomb guard


async def extract_image(path: str) -> ExtractionResult:
    with Image.open(path) as img:
        gray = ImageOps.autocontrast(ImageOps.grayscale(img))
        text = pytesseract.image_to_string(gray)
    return ExtractionResult(text=text, pages=1, chars=len(text), ocr_pages=1 if text.strip() else 0)
