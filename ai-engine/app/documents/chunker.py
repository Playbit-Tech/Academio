"""Fixed-size text chunker with overlap (PYE-02).

Default size 1000 / overlap 200 (AI_CHUNK_SIZE / AI_CHUNK_OVERLAP). Chunks
start at ``size - overlap`` stride so adjacent chunks share an overlap
window. Reconstruction guarantee: consecutive chunk starts advance by the
stride, and the last chunk reaches the end of the text. Overlap >= size is
rejected (a degenerate overlap would stall the stride loop).
"""

from app.config import settings


def chunk_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size or settings.AI_CHUNK_SIZE  # 1000 chars
    overlap = overlap or settings.AI_CHUNK_OVERLAP  # 200 chars
    if overlap >= size:
        raise ValueError("chunk overlap must be < chunk size")
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks
