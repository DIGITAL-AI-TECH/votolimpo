# Quickstart: Processing Engine

**Feature**: Processing Engine (002-processing-engine)
**Date**: 2026-09-06

---

## Prerequisites

- Docker & Docker Compose
- PostgreSQL 16 with pgvector extension
- OpenAI API key (for LLM processing + embeddings)

---

## 1. Clone & Setup

```bash
git clone https://github.com/DIGITAL-AI-TECH/votolimpo.git
cd votolimpo
git checkout 002-processing-engine
```

## 2. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```env
# Database
DATABASE_URL=postgresql+asyncpg://processing:secret@localhost:5432/processing_engine

# OpenAI
OPENAI_API_KEY=sk-...

# Engine config
ENGINE_ROLE=both          # api | worker | both
ENGINE_WORKERS=2          # Number of concurrent worker tasks
ENGINE_POLL_INTERVAL=2    # Seconds between job queue polls
ENGINE_API_KEY=my-api-key # API key for authentication

# Optional
LOG_LEVEL=INFO
```

## 3. Start with Docker Compose

```bash
docker compose up -d
```

This starts:
- **processing-engine**: FastAPI API + worker (port 8000)
- **postgres**: PostgreSQL 16 with pgvector (port 5432)

## 4. Register a Pipeline

```bash
curl -X POST http://localhost:8000/v1/pipelines \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: my-api-key" \
  -d '{
    "id": "demo-text-extraction",
    "name": "Demo - Text Extraction",
    "config": {
      "ingestor": {"type": "text"},
      "dedup": {"strategy": "hash"},
      "llm": {
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "temperature": 0.1,
        "max_tokens": 2048,
        "system_prompt": "Extract key entities and a one-paragraph summary from the following text. Return JSON with fields: entities (array of {name, type}), summary (string)."
      },
      "validators": [{"type": "json_schema"}],
      "sink": {"type": "postgresql", "config": {"target_table": "demo_results", "strategy": "upsert", "key_column": "content_hash"}},
      "cache": {"enabled": true, "ttl_hours": 720}
    }
  }'
```

## 5. Submit a Job

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: my-api-key" \
  -d '{
    "pipeline_id": "demo-text-extraction",
    "items": [
      {
        "content": "The Brazilian Supreme Court ruled today that former President Jair Bolsonaro is ineligible to run for office until 2030. The decision was unanimous among the 11 justices.",
        "content_type": "text/plain",
        "source_url": "https://example.com/article-1"
      }
    ]
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline_id": "demo-text-extraction",
  "status": "queued",
  "items_total": 1,
  "items_completed": 0,
  "items_failed": 0,
  "created_at": "2026-09-06T10:00:00Z"
}
```

## 6. Check Results

```bash
# Poll status
curl http://localhost:8000/v1/jobs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-Api-Key: my-api-key"

# Get results (when status = completed)
curl http://localhost:8000/v1/jobs/550e8400-e29b-41d4-a716-446655440000/result \
  -H "X-Api-Key: my-api-key"
```

## 7. Check Health & Stats

```bash
# Health (no auth required)
curl http://localhost:8000/v1/health

# Stats
curl http://localhost:8000/v1/stats -H "X-Api-Key: my-api-key"
```

---

## VotoLimpo Pipeline (Production)

To register the VotoLimpo pipeline, use the YAML config in `pipelines/votolimpo-article-extraction.yaml`:

```bash
# The CLI tool converts YAML to JSON and registers via API
python -m app.cli register-pipeline pipelines/votolimpo-article-extraction.yaml
```

---

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with auto-reload
uvicorn app.main:app --reload --port 8000

# Type check
mypy app/

# Lint
ruff check app/ tests/
```

---

## Project Structure

```
processing-engine/
  app/
    main.py                     # FastAPI app + lifespan (startup/shutdown)
    config.py                   # Settings (pydantic-settings)
    api/
      routes/
        jobs.py                 # POST /v1/jobs, GET /v1/jobs/{id}, GET /v1/jobs/{id}/result
        pipelines.py            # POST/GET/PUT /v1/pipelines
        operations.py           # GET /v1/health, GET /v1/stats
      deps.py                   # Dependency injection (DB pool, auth)
      middleware.py              # API key auth middleware
    core/
      orchestrator.py           # Pipeline coordinator (claim job, run steps)
      worker.py                 # Background worker (poll queue, process jobs)
      models.py                 # Pydantic models (Job, Item, Result, PipelineConfig)
    plugins/
      base.py                   # Protocol definitions (Ingestor, DedupStrategy, etc.)
      registry.py               # Plugin discovery and instantiation
      ingestors/
        text.py                 # Plain text passthrough
        html.py                 # HTML → clean text (BeautifulSoup)
        pdf.py                  # PDF → text (PyMuPDF + pdfplumber fallback)
        json_ingestor.py        # JSON field extraction
        auto.py                 # Auto-detect by content_type
      dedup/
        hash.py                 # SHA-256 dedup (url_hash + content_hash)
        semantic.py             # pgvector cosine similarity
        composite.py            # Hash first, semantic fallback
      llm/
        openai.py               # OpenAI provider (gpt-4.1-mini default)
      validators/
        json_schema.py          # JSON Schema validation
        grounding.py            # Entity grounding check
        range_check.py          # Numeric range validation
        date_check.py           # Date validation (no future dates)
      sinks/
        postgresql.py           # PostgreSQL upsert sink
    storage/
      database.py               # asyncpg connection pool
      queries.py                # SQL queries (jobs, items, logs, cache)
      migrations/               # Alembic migrations
  pipelines/                    # YAML configs per project
    votolimpo-article-extraction.yaml
  prompts/                      # System prompts per project
    votolimpo-system.txt
  schemas/                      # JSON Schemas per project
    votolimpo-article-v1.json
  tests/
    conftest.py                 # Fixtures (DB, test client, mock LLM)
    unit/
      test_ingestors.py
      test_dedup.py
      test_validators.py
    integration/
      test_orchestrator.py
      test_api_jobs.py
      test_api_pipelines.py
    contract/
      test_api_contracts.py     # Validates API responses match OpenAPI spec
  Dockerfile
  docker-compose.yml
  pyproject.toml
  alembic.ini
```
