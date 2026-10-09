FROM python:3.12-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# App code — cache-bust: 2026-10-08
COPY app/ app/
COPY pipelines/ pipelines/
COPY prompts/ prompts/
COPY schemas/ schemas/
COPY db_models/ db_models/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY scripts/ scripts/
COPY entrypoint.sh entrypoint.sh

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

CMD ["sh", "entrypoint.sh"]
