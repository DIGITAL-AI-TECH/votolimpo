# Quickstart: Processing Engine

## Prerequisites

- Python 3.12+
- Docker + Docker Compose (for PostgreSQL)
- OpenAI API key

## 1. Setup

```bash
# Clone the repo
git clone https://github.com/DIGITAL-AI-TECH/processing-engine.git
cd processing-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Start PostgreSQL (with pgvector)
docker compose up -d postgres

# Run migrations
alembic upgrade head
```

## 2. Configure

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
# Required:
#   DATABASE_URL=postgresql://engine:engine@localhost:5432/processing_engine
#   OPENAI_API_KEY=sk-...
#   API_KEY=your-secret-api-key
```

## 3. Start the Engine

```bash
# Development (API + Worker in single process)
uvicorn app.main:app --reload

# Production (separate processes)
ENGINE_ROLE=api uvicorn app.main:app --host 0.0.0.0 --port 8000
ENGINE_ROLE=worker python -m app.worker
```

## 4. Register a Pipeline

```bash
# Via cURL
curl -X POST http://localhost:8000/v1/pipelines \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "system_prompt": "Extract the following fields from the document...",
    "output_schema": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["title", "summary"]
    },
    "llm_model": "gpt-4.1-mini",
    "dedup_strategy": "hash",
    "max_concurrent": 5,
    "budget_limit_usd": 10.0,
    "budget_period": "month"
  }'
```

Or via YAML file:
```yaml
# pipelines/my-project.yaml
name: my-project
system_prompt: |
  Extract the following fields from the document...
output_schema:
  type: object
  properties:
    title: { type: string }
    summary: { type: string }
    entities: { type: array, items: { type: string } }
  required: [title, summary]
llm_model: gpt-4.1-mini
dedup_strategy: hash
max_concurrent: 5
budget_limit_usd: 10.0
budget_period: month
```

```bash
# Register via CLI
python -m app.cli register-pipeline pipelines/my-project.yaml
```

## 5. Submit a Job

```bash
# Single item
curl -X POST http://localhost:8000/v1/jobs \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "PIPELINE_UUID_HERE",
    "items": [
      {
        "source_url": "https://example.com/document",
        "content_type": "text/html"
      }
    ]
  }'

# Batch (multiple items)
curl -X POST http://localhost:8000/v1/jobs \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "PIPELINE_UUID_HERE",
    "items": [
      {"source_url": "https://example.com/doc1", "content_type": "text/html"},
      {"source_url": "https://example.com/doc2", "content_type": "text/html"},
      {"content": "Raw text content to process", "content_type": "text/plain"}
    ],
    "callback_url": "https://my-service.com/webhook/processing-done"
  }'
```

## 6. Check Status & Results

```bash
# Job status
curl http://localhost:8000/v1/jobs/JOB_UUID \
  -H "X-API-Key: your-secret-api-key"

# Job results
curl http://localhost:8000/v1/jobs/JOB_UUID/result \
  -H "X-API-Key: your-secret-api-key"

# Processing logs
curl http://localhost:8000/v1/jobs/JOB_UUID/logs \
  -H "X-API-Key: your-secret-api-key"
```

## 7. Monitor Costs

```bash
# Cost breakdown by pipeline (current month)
curl "http://localhost:8000/v1/costs?group_by=pipeline&period=month" \
  -H "X-API-Key: your-secret-api-key"

# Cost breakdown by model
curl "http://localhost:8000/v1/costs?group_by=model&period=month" \
  -H "X-API-Key: your-secret-api-key"

# Costs for specific pipeline
curl "http://localhost:8000/v1/costs?pipeline_id=PIPELINE_UUID&group_by=job" \
  -H "X-API-Key: your-secret-api-key"

# Aggregated stats
curl "http://localhost:8000/v1/stats?pipeline_id=PIPELINE_UUID" \
  -H "X-API-Key: your-secret-api-key"
```

## 8. Run Tests

```bash
# All tests (requires Docker for testcontainers)
pytest

# Unit tests only (fast, no Docker)
pytest tests/unit/

# Integration tests (starts PostgreSQL container)
pytest tests/integration/

# With coverage
pytest --cov=app --cov-report=term-missing
```

## Project Structure

```
processing-engine/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # pydantic-settings
│   ├── db.py                 # asyncpg pool management
│   ├── deps.py               # FastAPI dependencies
│   ├── worker.py             # SKIP LOCKED job worker
│   ├── cli.py                # CLI commands
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── pipelines.py
│   │   ├── jobs.py
│   │   ├── stats.py
│   │   ├── costs.py
│   │   └── pricing.py
│   ├── models/               # Pydantic models (request/response)
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── job.py
│   │   ├── item.py
│   │   ├── cost.py
│   │   └── stats.py
│   ├── services/             # Business logic
│   │   ├── __init__.py
│   │   ├── orchestrator.py   # Pipeline orchestration
│   │   ├── cost_tracker.py   # LLM call logging + budget check
│   │   └── callback.py       # Webhook callbacks
│   ├── plugins/              # Plugin implementations
│   │   ├── __init__.py
│   │   ├── protocols.py      # typing.Protocol definitions
│   │   ├── registry.py       # Plugin registry
│   │   ├── ingestors/
│   │   │   ├── html.py
│   │   │   ├── pdf.py
│   │   │   ├── text.py
│   │   │   ├── json_ingestor.py
│   │   │   └── auto.py
│   │   ├── dedup/
│   │   │   ├── hash.py
│   │   │   ├── semantic.py
│   │   │   └── composite.py
│   │   ├── llm/
│   │   │   └── openai.py
│   │   ├── validators/
│   │   │   ├── schema.py
│   │   │   ├── grounding.py
│   │   │   ├── range.py
│   │   │   └── date.py
│   │   └── sinks/
│   │       └── postgresql.py
│   └── sql/                  # Raw SQL queries
│       ├── jobs.sql
│       ├── items.sql
│       ├── costs.sql
│       └── stats.sql
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       ├── 001_create_schema.py
│       ├── ...
│       └── 010_create_functions.py
├── db_models/                # SQLAlchemy models (migration source only)
│   ├── __init__.py
│   ├── pipeline.py
│   ├── job.py
│   ├── item.py
│   ├── processing_log.py
│   ├── cache_entry.py
│   ├── llm_call_log.py
│   └── model_pricing.py
├── tests/
│   ├── conftest.py           # testcontainers fixtures
│   ├── unit/
│   │   ├── test_ingestors.py
│   │   ├── test_dedup.py
│   │   ├── test_validators.py
│   │   ├── test_cost_tracker.py
│   │   └── test_orchestrator.py
│   ├── integration/
│   │   ├── test_jobs_api.py
│   │   ├── test_pipelines_api.py
│   │   ├── test_costs_api.py
│   │   ├── test_worker.py
│   │   └── test_cache.py
│   └── contract/
│       └── test_openapi.py
├── pipelines/                # Example pipeline configs
│   └── example.yaml
├── specs/                    # SpecKit artifacts
├── .specify/                 # SpecKit templates & memory
├── CLAUDE.md
├── CONSTITUTION.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
└── .env.example
```

## Docker Deployment

```bash
# Build image
docker build -t processing-engine:latest .

# Run with Docker Compose
docker compose up -d

# Deploy to Docker Swarm (production)
docker stack deploy -c docker-stack.yml processing-engine
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `API_KEY` | Yes | — | API authentication key |
| `ENGINE_ROLE` | No | `both` | `api`, `worker`, or `both` |
| `WORKER_POLL_INTERVAL_SECONDS` | No | `1.0` | Worker polling interval |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `HOST` | No | `0.0.0.0` | API host |
| `PORT` | No | `8000` | API port |
