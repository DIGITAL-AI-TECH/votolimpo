FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# App code
COPY app/ app/
COPY pipelines/ pipelines/
COPY prompts/ prompts/
COPY schemas/ schemas/

# Non-root user
RUN adduser --disabled-password --no-create-home appuser
USER appuser

ENV PE_PIPELINES_DIR=/app/pipelines \
    PE_PROMPTS_DIR=/app/prompts \
    PE_SCHEMAS_DIR=/app/schemas \
    PE_LOG_LEVEL=info

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
