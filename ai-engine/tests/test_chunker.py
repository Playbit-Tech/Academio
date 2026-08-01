"""Chunker unit tests (PYE-02): default 1000/200, overlap guards, coverage.

NOTE: the plan's example ("2500 chars -> 3 chunks") is arithmetically wrong
for the specified algorithm — stride is 800 so 2500 chars yields 4 chunks
(starts at 0/800/1600/2400). The plan's intended 3-chunk case is 2400 chars
(starts 0/800/1600, full coverage). Both cases are asserted here.
"""

import pytest

from app.documents.chunker import chunk_text


def test_chunk_empty_text() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\t ") == []


def test_chunk_defaults_three_chunks_full_coverage() -> None:
    """Default 1000/200: a 2400-char text -> exactly 3 chunks at stride 800."""
    text = "a" * 2400
    chunks = chunk_text(text)
    assert len(chunks) == 3
    assert chunks == [text[0:1000], text[800:1800], text[1600:2400]]


def test_chunk_trailing_partial_chunk() -> None:
    """2500 chars -> 4 chunks; the last chunk is the 100-char tail (2400:2500)."""
    text = "a" * 2500
    chunks = chunk_text(text)
    assert len(chunks) == 4
    assert chunks[3] == text[2400:2500]


def test_chunk_overlap_invalid() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("x" * 100, size=100, overlap=100)


def test_chunk_reconstruction_covers_text() -> None:
    """Chunks at stride 800 jointly cover the whole original text."""
    # No trailing whitespace: chunk_text strips before chunking.
    text = ("the quick brown fox jumps over the lazy dog." * 60)  # 2640 chars
    chunks = chunk_text(text)
    stride = 1000 - 200
    starts = [i * stride for i in range(len(chunks))]
    assert all(text[s : s + 1000] == chunks[i] for i, s in enumerate(starts))
    assert starts[-1] + len(chunks[-1]) == len(text)


def test_chunk_custom_size_overlap() -> None:
    text = "b" * 1000
    chunks = chunk_text(text, size=300, overlap=50)
    assert len(chunks) == 4  # starts 0/250/500/750
    assert chunks[1] == text[250:550]
