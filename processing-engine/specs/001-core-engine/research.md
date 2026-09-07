# Research: Core Engine

**Feature**: 001-core-engine
**Date**: 2026-09-06

## Prior Knowledge from Cortex

### Python Gotchas (applicable)
- `datetime.now(timezone.utc)` — never use `datetime.utcnow()` (deprecated, no timezone info)
- OpenAI max output tokens: 16384 for gpt-4o — engine must respect model limits
- Content preservation: 100% content — NO summarization in pipelines
- YAML colon in title breaks parsing — use `_yaml_quote()` helper

### Docker Gotchas (applicable)
- Alpine image target: <100MB — use multi-stage builds
- Swarm bind mount: use long-form syntax only
- `python:3.12-slim` over Alpine for Python (avoids musl/glibc issues with asyncpg and psycopg)

### Cross-project Patterns
- `streaming-pipeline.md`: io.Pipe streaming — applicable for large PDF/HTML ingest
- `docker-swarm-deployment.md`: Traefik + Swarm patterns — reuse for deploy phase
- `webhook-bridge.md`: n8n webhook integration — relevant for callback_url (FR-013)

---

## Decision 1: Job Queue — PostgreSQL SKIP LOCKED

**Decision**: Use PostgreSQL `FOR UPDATE SKIP LOCKED` for job queue instead of Redis/RabbitMQ.

**Rationale**: Constitution Principle V (Stack Mínima) mandates PostgreSQL as the only infra dependency. SKIP LOCKED provides lightweight, transactional job claiming with no external service. For expected volume (500-1000 items/day per project), PostgreSQL is more than sufficient — LinkedIn processes 120k+ jobs/sec with this pattern.

**Alternatives considered**:
- Redis (Bull/Celery): adds infra dependency, violates Constitution V
- RabbitMQ: overkill for volume, adds operational complexity
- arq (Python + Redis): same Redis dependency issue

**Implementation**: Worker loop polls `SELECT ... FROM jobs WHERE status = 'queued' ORDER BY priority DESC, created_at FOR UPDATE SKIP LOCKED LIMIT 1`, transitions to 'running', processes, and commits. Polling interval: 1 second (configurable via `WORKER_POLL_INTERVAL_SECONDS`).

---

## Decision 2: Async Runtime — asyncio (native)

**Decision**: Use Python's built-in asyncio with async/await throughout (FastAPI, asyncpg, httpx, openai).

**Rationale**: All key dependencies (FastAPI, asyncpg, httpx, openai SDK) are natively async. No need for threading or multiprocessing for I/O-bound workloads. asyncio.Semaphore provides natural concurrency control for batch processing (max_concurrent).

**Alternatives considered**:
- Threading: GIL limits, harder to reason about DB connections
- multiprocessing: Overhead for I/O-bound work, complicates DB pool sharing
- Celery: adds Redis/RabbitMQ dependency (Constitution V violation)

---

## Decision 3: Plugin System — typing.Protocol (structural subtyping)

**Decision**: Use `typing.Protocol` for all plugin interfaces (Ingestor, DedupStrategy, LLMProvider, Validator, Sink).

**Rationale**: Constitution Principle IV (Plugin-First) mandates zero inheritance and zero ABC. Protocol classes enable structural subtyping — any class that implements the right methods satisfies the protocol, without inheriting from it. This is the most Pythonic approach for plugin architectures since Python 3.8.

**Implementation**:
```python
class Ingestor(Protocol):
    async def ingest(self, raw: bytes, mime_type: str, config: dict) -> IngestResult: ...

class DedupStrategy(Protocol):
    async def check(self, item: Item, pipeline_id: str) -> DedupResult: ...

class LLMProvider(Protocol):
    async def process(self, content: str, prompt: str, config: LLMConfig) -> LLMResult: ...

class Validator(Protocol):
    def validate(self, output: dict, schema: dict, source_text: str) -> ValidationResult: ...

class Sink(Protocol):
    async def persist(self, item: Item, result: ProcessResult, config: dict) -> PersistResult: ...
```

**Alternatives considered**:
- ABC (Abstract Base Class): requires explicit inheritance, couples plugins to engine
- Zope Interface: heavy, enterprise-ish, unnecessary complexity
- Duck typing without Protocol: works but no IDE support or type checking

---

## Decision 4: PDF Extraction — PyMuPDF (fitz)

**Decision**: Use PyMuPDF for PDF text extraction.

**Rationale**: Fastest Python PDF library (~10x faster than pdfplumber, ~5x faster than PyPDF2). Pure C extension with no Java dependency (unlike Tika). Handles tables, images, and metadata. Supports incremental rendering for large PDFs.

**Alternatives considered**:
- pdfplumber: slower, better for table extraction specifically
- PyPDF2: slower, less accurate text extraction
- Apache Tika: requires JVM, adds heavy dependency
- unstructured: too heavy, includes ML models we don't need

---

## Decision 5: Database Migrations — Alembic + SQLAlchemy models

**Decision**: Use Alembic for migrations with SQLAlchemy models as schema source of truth. Runtime queries use asyncpg with raw SQL.

**Rationale**: Constitution Principle VI (Schema First) requires versioned schema. Alembic provides reliable migration management. SQLAlchemy models serve as documentation and migration source. Runtime uses asyncpg for performance (no ORM overhead) — this is the same pattern used successfully in database-backup-processor at Digital AI.

**Alternatives considered**:
- Raw SQL migrations: error-prone, no autogenerate
- Django ORM: wrong framework, heavyweight
- Tortoise ORM: full ORM, violates "no ORM" preference
- yoyo-migrations: less ecosystem support than Alembic

---

## Decision 6: Testing — pytest + testcontainers (real PostgreSQL)

**Decision**: All integration tests run against real PostgreSQL via testcontainers. No database mocking.

**Rationale**: Constitution Principle IX (Testabilidade) explicitly mandates "zero mock de banco de dados." testcontainers spins up a real PostgreSQL container per test session, applies migrations, and destroys after. This catches real SQL errors, constraint violations, and migration issues that mocks would miss.

**Implementation**:
```python
@pytest.fixture(scope="session")
async def db():
    with PostgresContainer("postgres:16") as pg:
        pool = await asyncpg.create_pool(pg.get_connection_url())
        await run_migrations(pool)
        yield pool
```

**Alternatives considered**:
- SQLite in-memory: missing features (pgvector, SKIP LOCKED, JSONB operators)
- Mocking asyncpg: violates Constitution IX, masks real SQL issues

---

## Decision 7: Cost Calculation — model_pricing lookup table

**Decision**: Maintain a `model_pricing` table in PostgreSQL with per-model input/output token costs. Each LLM call calculates `cost_usd = (prompt_tokens * input_price_per_token) + (completion_tokens * output_price_per_token)`.

**Rationale**: Token prices change frequently (OpenAI updates pricing ~quarterly). Storing prices in a database table (vs. hardcoded constants) allows updates without redeployment (FR-020). The table is seeded with current OpenAI prices and updated via API or YAML config.

**Pricing data** (as of 2026-09):
| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|-------|---------------------|----------------------|
| gpt-4.1-mini | $0.40 | $1.60 |
| gpt-4.1 | $2.00 | $8.00 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |
| text-embedding-3-small | $0.02 | N/A |

**Budget enforcement** (FR-022): A PostgreSQL function `check_budget(pipeline_id)` sums `cost_usd` from `llm_call_log` for the current billing period (month by default). Called before each LLM invocation. Returns `(current_cost, budget_limit, pct_used)`.

**Alternatives considered**:
- Hardcoded constants: requires deploy for price updates
- External pricing API: adds dependency, latency
- Environment variables: awkward for multi-model configs

---

## Decision 8: Embedding Storage — pgvector

**Decision**: Use pgvector extension for storing and querying embeddings (dedup semântico).

**Rationale**: Constitution V mandates PostgreSQL as the only infra dependency. pgvector provides efficient vector similarity search (<=> operator for cosine distance) within the same database. No need for Qdrant, Pinecone, or Weaviate.

**Implementation**: `content_embedding vector(1536)` column on items table, indexed with `ivfflat` or `hnsw`. Dedup query: `SELECT id FROM items WHERE pipeline_id = $1 AND content_embedding <=> $2 < $3` (threshold configurable per pipeline).

**Alternatives considered**:
- Qdrant: violates Constitution V (adds external service)
- FAISS: in-memory only, doesn't persist across restarts
- No semantic dedup: loses ~15-30% cost savings on similar content

---

## Decision 9: Container Strategy — Single process, dual mode

**Decision**: Single Docker container runs both API and Worker. Configurable via `ENGINE_ROLE` env var: `api`, `worker`, or `both` (default).

**Rationale**: For expected volume (<1000 items/day), running separate containers is unnecessary overhead. The `both` mode starts FastAPI + worker loop in the same asyncio event loop. For higher scale, deploy separate containers with `ENGINE_ROLE=api` and `ENGINE_ROLE=worker` pointing to the same PostgreSQL.

**Implementation**:
```python
# main.py
role = settings.engine_role  # "api" | "worker" | "both"
if role in ("api", "both"):
    # start FastAPI
if role in ("worker", "both"):
    # start worker loop as background task
```

**Alternatives considered**:
- Always separate containers: operational overhead for small deployments
- Celery workers: adds Redis dependency (Constitution V violation)

---

## Decision 10: API Authentication — API Key header

**Decision**: Simple API key authentication via `X-API-Key` header. Single key per instance (v1).

**Rationale**: Constitution X mandates API key on all endpoints (except /health). For v1, a single key (set via `API_KEY` env var) is sufficient. Multi-tenant with per-client keys is explicitly OUT OF SCOPE for v1.

**Alternatives considered**:
- JWT: overkill for service-to-service auth
- OAuth2: unnecessary complexity for v1
- No auth: violates Constitution X
