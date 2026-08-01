# Stage 1: build deps with uv
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: runtime
FROM python:3.13-slim
# OCR tooling (D-04): python:3.13-slim ships NO tesseract; pytesseract/pdf2image
# resolve the binaries at runtime. poppler-utils provides pdftoppm for pdf2image.
# Verified apt candidates in trixie: tesseract-ocr 5.5.0, poppler-utils 25.03.0
# (RESEARCH Pitfall 6). Builder stage needs no apt — wrappers are pure Python.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8000
COPY app ./app
COPY prompts ./prompts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
