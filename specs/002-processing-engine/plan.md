# Implementation Plan: Processing Engine

**Branch**: `002-processing-engine` | **Date**: 2026-09-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-processing-engine/spec.md`

## Summary

Agnostic data processing engine that receives raw data (text, HTML, PDF, JSON), processes it through a configurable LLM pipeline (Ingest → Dedup → Process → Validate → Persist), and outputs structured results to project-specific sinks. Designed to serve VotoLimpo (article extraction), Help Core (document classification), and any future project needing AI-powered batch data processing. Built as a Python FastAPI monolith with PostgreSQL SKIP LOCKED job queue, plugin-based architecture, and YAML-driven pipeline configuration.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, asyncpg, httpx, openai, pydantic, pydantic-settings, PyMuPDF, beautifulsoup4, jsonschema, PyYAML, alembic, SQLAlchemy (models only)
**Storage**: PostgreSQL 16 with pgvector extension (schema: `processing_engine`)
**Testing**: pytest + pytest-asyncio + testcontainers-python (real PostgreSQL)
**Target Platform**: Linux server (Docker Swarm + Traefik)
**Project Type**: Single service (API + worker in one container)
**Performance Goals**: Single item < 30s (SC-001), batch of 100 < 10min (SC-002), dedup < 100ms (SC-003), cache hit < 200ms (SC-004)
**Constraints**: Docker image < 200MB (SC-011), LLM cost < $10/month for 10K articles (SC-006), success rate > 95% (SC-007)
**Scale/Scope**: ~500 items/day (VotoLimpo) + sporadic batches ~1,000 docs (Help Core)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Transparencia Radical | PASS | Engine stores source_url, content_hash, processing_logs for every item. Full audit trail. |
| II. Anti-Reprocessamento (NON-NEGOTIABLE) | PASS | 3-layer dedup: url_hash (SHA-256) before scrape, content_hash before LLM, cache by content_hash. FR-004 enforces dedup BEFORE LLM call. |
| III. Custo Controlado | PASS | Cache (FR-010) avoids redundant LLM calls. Truncation (FR-017). GPT-4.1-mini default. Processing logs track cost_usd per item (FR-008). SC-006 target: <$10/month. |
| IV. Dados > Opiniao | PASS | Engine is agnostic — processes data, doesn't editorialize. Output is structured JSON validated against schema. |
| V. Idempotencia Total | PASS | idempotency_key (FR-015) prevents duplicate jobs. Sinks use upsert (ON CONFLICT). Re-running a job returns cached results. |
| VI. Schema First | PASS | PostgreSQL with ENUMs, constraints, UNIQUE indexes. data-model.md defines all 7 tables. Alembic migrations. |
| VII. Anti-Alucinacao | PASS | 4 built-in validators: json_schema, grounding, range, date (FR-005, FR-006). Custom validators per pipeline. Validation BEFORE persist. |
| VIII. Stack Minima | PASS | Python + PostgreSQL + Docker. No Redis, no message broker, no separate vector DB. SKIP LOCKED for job queue. pgvector for semantic dedup. Single container. |
| IX. Open Source & Eleicao 2026 | PASS | Engine lives in DIGITAL-AI-TECH/votolimpo repo (public). No private data in engine code. |
| X. Testabilidade | PASS | pytest + real PostgreSQL (testcontainers). Plugin protocols enable mock injection. Contract tests for API. |

**Re-check after Phase 1**: All principles remain PASS. The data model (7 tables) and API contracts (8 endpoints) align with Constitution constraints. No violations found.

## Project Structure

### Documentation (this feature)

```text
specs/002-processing-engine/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: Technical decisions
├── data-model.md        # Phase 1: Database schema (7 tables)
├── quickstart.md        # Phase 1: Getting started guide
├── contracts/
│   └── openapi.yaml     # Phase 1: OpenAPI 3.1 spec (8 endpoints)
├── checklists/
│   └── requirements.md  # Quality validation checklist
└── tasks.md             # Phase 2: Task decomposition (created by /speckit.tasks)
```

### Source Code (repository root)

```text
processing-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + lifespan
│   ├── config.py                   # Pydantic Settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # Dependency injection (DB pool, auth)
│   │   ├── middleware.py            # API key auth
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── jobs.py             # POST /v1/jobs, GET status, GET result
│   │       ├── pipelines.py        # CRUD /v1/pipelines
│   │       └── operations.py       # GET /v1/health, GET /v1/stats
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # Pipeline coordinator
│   │   ├── worker.py               # Background job poller
│   │   └── models.py               # Pydantic domain models
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── base.py                 # Protocol definitions
│   │   ├── registry.py             # Plugin discovery
│   │   ├── ingestors/
│   │   │   ├── __init__.py
│   │   │   ├── text.py
│   │   │   ├── html.py
│   │   │   ├── pdf.py
│   │   │   ├── json_ingestor.py
│   │   │   └── auto.py
│   │   ├── dedup/
│   │   │   ├── __init__.py
│   │   │   ├── hash.py
│   │   │   ├── semantic.py
│   │   │   └── composite.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   └── openai.py
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   ├── json_schema.py
│   │   │   ├── grounding.py
│   │   │   ├── range_check.py
│   │   │   └── date_check.py
│   │   └── sinks/
│   │       ├── __init__.py
│   │       └── postgresql.py
│   └── storage/
│       ├── __init__.py
│       ├── database.py             # asyncpg pool
│       ├── queries.py              # SQL queries
│       └── migrations/
│           ├── env.py
│           └── versions/
│               └── 001_initial.py
├── pipelines/
│   └── votolimpo-article-extraction.yaml
├── prompts/
│   └── votolimpo-system.txt
├── schemas/
│   └── votolimpo-article-v1.json
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_ingestors.py
│   │   ├── test_dedup.py
│   │   ├── test_validators.py
│   │   └── test_models.py
│   ├── integration/
│   │   ├── test_orchestrator.py
│   │   └── test_worker.py
│   └── contract/
│       ├── test_api_jobs.py
│       ├── test_api_pipelines.py
│       └── test_api_operations.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
└── README.md
```

**Structure Decision**: Single project (monolith). The engine is one service with API + worker running in the same process (configurable via `ENGINE_ROLE` env var). This matches Constitution VIII (Stack Minima) and the volume requirements (~500 items/day). No frontend — API-only in v1.

## File Whitelist

Only these files/directories may be created or modified during implementation:

```
processing-engine/**        # All source code for the engine
specs/002-processing-engine/**  # Spec artifacts (if updates needed)
pipelines/**                # Pipeline YAML configs
prompts/**                  # System prompts
schemas/**                  # JSON Schemas
Dockerfile                  # Engine Dockerfile
docker-compose.yml          # Dev compose
pyproject.toml              # Python project config
alembic.ini                 # Migration config
.env.example                # Environment template
```

## Implementation Phases

### Phase A: Foundation (P1 prerequisite)

1. **Project scaffold**: pyproject.toml, Dockerfile, docker-compose.yml, alembic.ini
2. **Database**: Alembic migration with all 7 tables + ENUMs + indexes
3. **Config**: pydantic-settings (env vars) + PipelineConfig Pydantic model (YAML validation)
4. **Plugin framework**: Protocol definitions (base.py) + registry (registry.py)
5. **FastAPI app**: main.py with lifespan, dependency injection, API key middleware

### Phase B: Core Pipeline (User Story 1 — P1)

1. **Ingestors**: text + html (BeautifulSoup) + auto-detect
2. **Hash dedup**: SHA-256 of URL + content
3. **OpenAI LLM provider**: async client, structured JSON output, retry with backoff
4. **Validators**: json_schema + grounding + range + date
5. **PostgreSQL sink**: asyncpg upsert with configurable table mappings
6. **Orchestrator**: Step-by-step pipeline execution with processing logs
7. **API routes**: POST /v1/jobs, GET /v1/jobs/{id}, GET /v1/jobs/{id}/result

### Phase C: Batch & Queue (User Story 2 — P1)

1. **Worker**: Background job poller with SKIP LOCKED
2. **Batch processing**: asyncio.Semaphore for concurrency control
3. **Rate limiting**: Token bucket for LLM API calls
4. **Callback**: Webhook notification on job completion
5. **Job lifecycle**: queued → running → completed/partial/failed with counters

### Phase D: Pipeline Management (User Story 3 — P1)

1. **Pipeline CRUD**: POST/GET/PUT /v1/pipelines
2. **Versioning**: Pipeline versions stored on update; jobs reference frozen version
3. **YAML registration**: CLI tool to register pipeline from YAML file
4. **Validation**: Config validated at registration time (missing fields → 422)

### Phase E: Observability (User Stories 4+6 — P2)

1. **GET /v1/health**: DB connectivity, queue depth, uptime
2. **GET /v1/stats**: Aggregated metrics (cost, volume, success rate, by pipeline)
3. **Processing logs**: Complete audit trail per step per item

### Phase F: Cache & Optimization (User Story 5 — P2)

1. **Cache check**: Content hash lookup before LLM call
2. **Cache storage**: Result + metadata stored with TTL
3. **Cache bypass**: skip_cache=true per job
4. **Semantic dedup**: pgvector embeddings + cosine similarity (configurable threshold)

### Phase G: VotoLimpo Config

1. **Pipeline YAML**: votolimpo-article-extraction.yaml
2. **System prompt**: Port extraction prompt from specs/1-votolimpo-frontend/extraction-prompt.md
3. **JSON Schema**: Output schema for structured article extraction
4. **Integration test**: End-to-end with real VotoLimpo article

### Phase H: Docker & Deploy

1. **Dockerfile**: Multi-stage build, python:3.12-slim, target < 200MB
2. **docker-compose.yml**: Engine + PostgreSQL for dev
3. **Docker Swarm stack**: Traefik labels, health check, resource limits
4. **README.md**: Setup, usage, deployment instructions

## Complexity Tracking

> No Constitution violations found. All design decisions align with principles.

| Decision | Justification |
|----------|--------------|
| Single container (API + worker) | Volume < 1K/day doesn't justify separate processes. ENV_ROLE allows splitting later. |
| PostgreSQL SKIP LOCKED (no Redis) | Constitution VIII: Stack Minima. Volume is ~500/day. |
| pgvector (no Qdrant) | Constitution VIII: Reuses existing PostgreSQL. No separate vector DB. |
| Python Protocol (no ABC) | More Pythonic, no inheritance required, structural subtyping. |

## Key Design Decisions

Full details in [research.md](research.md). Summary:

| # | Decision | Choice | Key Rationale |
|---|----------|--------|---------------|
| 1 | Job queue | PostgreSQL SKIP LOCKED | No Redis dependency; sufficient for ~500/day |
| 2 | Async runtime | asyncio + asyncpg + httpx | FastAPI async-native; best I/O performance |
| 3 | Plugin system | typing.Protocol | Structural subtyping; no inheritance needed |
| 4 | PDF parsing | PyMuPDF + pdfplumber fallback | Fast C-based + table-heavy fallback |
| 5 | Migrations | Alembic | Standard Python; auto-generate from models |
| 6 | Config | pydantic-settings + YAML | Env vars for infra; YAML for pipeline definitions |
| 7 | Embeddings | text-embedding-3-small (1536d) | Digital AI standard; pgvector compatible |
| 8 | Testing | pytest + testcontainers | Real PostgreSQL; no mock DB (Cortex gotcha) |
| 9 | Docker | python:3.12-slim multi-stage | Target < 200MB (SC-011) |
| 10 | Rate limiting | asyncio.Semaphore + token bucket | No Redis; in-process is sufficient |

## Artifacts Generated

| Artifact | Path | Content |
|----------|------|---------|
| Research | [research.md](research.md) | 10 technical decisions with rationale |
| Data Model | [data-model.md](data-model.md) | 7 tables, 5 ENUMs, all indexes, state transitions |
| API Contract | [contracts/openapi.yaml](contracts/openapi.yaml) | OpenAPI 3.1, 8 endpoints, all schemas |
| Quickstart | [quickstart.md](quickstart.md) | Setup, usage examples, project structure |

## Next Step

Run `/speckit.tasks` to decompose the implementation phases into concrete, parallelizable tasks with dependencies.
