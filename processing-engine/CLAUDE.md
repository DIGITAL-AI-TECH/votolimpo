# Processing Engine

## Project Overview

Agnostic data processing engine with LLM integration. Receives raw data (text, HTML, PDF, JSON), processes through configurable pipelines (Ingest → Dedup → Process → Validate → Persist), and outputs structured results to project-specific sinks.

Designed as a standalone, reusable service — each project (VotoLimpo, Help Core, etc.) registers a pipeline via YAML config without touching engine code.

## Stack

- **Language**: Python 3.12
- **Framework**: FastAPI + asyncpg + httpx
- **Database**: PostgreSQL 16 with pgvector extension
- **LLM**: OpenAI (gpt-4.1-mini default), extensible to Anthropic/Ollama
- **Testing**: pytest + pytest-asyncio + testcontainers
- **Deploy**: Docker Swarm + Traefik (via Digital AI infra)

## Architecture

- **Plugin-based**: Ingestors, Dedup strategies, LLM providers, Validators, Sinks — all defined as `typing.Protocol`
- **Job Queue**: PostgreSQL SKIP LOCKED (no Redis needed)
- **Single container**: API + Worker in same process (configurable via `ENGINE_ROLE` env var)
- **Config-driven**: Pipeline definitions in YAML, system prompts in text files, output schemas in JSON Schema

## Development Workflow

1. `pip install -e ".[dev]"` — install with dev dependencies
2. `docker compose up -d postgres` — start PostgreSQL
3. `alembic upgrade head` — run migrations
4. `uvicorn app.main:app --reload` — start dev server
5. `pytest` — run tests (uses testcontainers, no mock DB)

## Spec-Driven Development

This project uses SpecKit for specification-driven development:
- `/speckit.constitution` — project principles
- `/speckit.specify` — feature specifications
- `/speckit.plan` — implementation planning
- `/speckit.tasks` — task decomposition
- `/speckit.implement` — guided implementation

## Rules

- Always respond in Portuguese
- Follow coding best practices
- Run tests after making changes when possible
- Conventional Commits always
- No ORM: asyncpg with raw SQL (SQLAlchemy for models/migrations only)
- Plugin system uses `typing.Protocol` (no ABC inheritance)
- All dates in UTC with timezone info

## Active Technologies
- Python 3.12 + FastAPI, asyncpg, httpx, openai, pydantic, pydantic-settings, PyMuPDF, beautifulsoup4, jsonschema, PyYAML, alembic, SQLAlchemy (models only) (001-core-engine)
- PostgreSQL 16 with pgvector extension (schema: `processing_engine`) (001-core-engine)

## Recent Changes
- 001-core-engine: Added Python 3.12 + FastAPI, asyncpg, httpx, openai, pydantic, pydantic-settings, PyMuPDF, beautifulsoup4, jsonschema, PyYAML, alembic, SQLAlchemy (models only)
