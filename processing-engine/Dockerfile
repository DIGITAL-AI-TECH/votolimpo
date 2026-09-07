# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
# Create stub packages so hatchling can build the wheel metadata.
# Actual source code is copied in the final stage — here we only need deps.
RUN mkdir -p app db_models && \
    touch app/__init__.py db_models/__init__.py && \
    pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

WORKDIR /app

# Copy installed deps
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY db_models/ ./db_models/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY entrypoint.sh ./

RUN chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    ENGINE_ROLE=both \
    WORKER_POLL_INTERVAL_SECONDS=1.0 \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health'); exit(0 if r.status_code in (200,503) else 1)"

CMD ["./entrypoint.sh"]
