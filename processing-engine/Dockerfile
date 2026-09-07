# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /build

# Extract dependencies from pyproject.toml and install ONLY those.
# We do NOT install the package itself — avoids hatchling needing source
# files and eliminates stub packages shadowing real code in site-packages.
COPY pyproject.toml ./
RUN python -c "\
import tomllib, pathlib; \
data = tomllib.load(open('pyproject.toml', 'rb')); \
deps = data['project']['dependencies']; \
pathlib.Path('requirements.txt').write_text('\n'.join(deps))" && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

# Copy installed deps (NO stub packages — only third-party libraries)
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

# No HEALTHCHECK here — the docker-stack.yml defines the production health
# check with appropriate start_period and retries for Swarm. Having two
# conflicting health checks causes confusion during debugging.

CMD ["./entrypoint.sh"]
