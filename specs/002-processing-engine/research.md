# Research: Processing Engine

**Feature**: Processing Engine (002-processing-engine)
**Date**: 2026-09-06
**Status**: Complete

---

## Prior Knowledge from Cortex

### Relevant Patterns
- **docker-swarm-deployment.md**: Traefik + Swarm, bind mounts long-form, Alpine < 100MB
- **webhook-bridge.md**: FastAPI as middleware between platforms and internal services
- **multi-tenant-isolation.md**: API key + tenant header per request
- **tool-design.md**: Plugin interfaces should be atomic, single-responsibility, composable

### Relevant Decisions
- **ARQ over Celery** (2026-06-01): For Python async pipelines, ARQ (Redis queue) preferred over Celery. However, this engine's spec explicitly requires PostgreSQL SKIP LOCKED (no Redis) — volume is ~500 items/day, not enough to justify Redis dependency.
- **Redis Sliding Window Rate Limit** (2026-06-15): Lua-based rate limiting. Not applicable for v1 (no Redis), but the engine implements its own concurrency limiter via asyncio.Semaphore + token bucket.

### Relevant Gotchas
- **Python**: `datetime.now(timezone.utc)` not `datetime.utcnow()`; gpt-4o max output 16384 tokens; content preservation 100% in AI pipelines
- **Docker**: Alpine bind mount long-form syntax; registry layer < 200 MiB; CapDrop ALL prevents chown

---

## Decision 1: Job Queue — PostgreSQL SKIP LOCKED vs Redis/ARQ

**Decision**: PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`

**Rationale**:
- Volume is ~500 items/day (VotoLimpo) + sporadic batches of ~1,000 docs (Help Core)
- At this scale, PostgreSQL advisory locks are more than sufficient
- Eliminates Redis as infrastructure dependency (Constitution VIII: Stack Minima)
- Jobs table with status enum (queued/running/completed/failed/partial) + claimed_at timestamp
- Worker polls every 2 seconds with `SKIP LOCKED` to avoid contention
- Batch claim: `LIMIT {max_concurrent}` in a single transaction

**Alternatives considered**:
- ARQ (Redis): Better for high-throughput (10K+ jobs/min), but overkill here and adds dependency
- Celery: Heavy, complex, not async-native
- pg_notify: Could supplement polling for lower latency, but polling at 2s is fine for v1

---

## Decision 2: Async Runtime

**Decision**: asyncio + asyncpg + httpx (async OpenAI client)

**Rationale**:
- FastAPI is async-native — all I/O (DB, LLM API, HTTP callbacks) benefits from async
- asyncpg is the fastest PostgreSQL driver for Python (connection pool built-in)
- httpx for async HTTP (callbacks, webhook delivery)
- OpenAI Python SDK supports async natively (`AsyncOpenAI`)
- Concurrency control via `asyncio.Semaphore(max_concurrent)` per job

**Alternatives considered**:
- sync + threading: Worse performance for I/O-bound workloads
- trio: Less ecosystem support than asyncio

---

## Decision 3: Plugin System Architecture

**Decision**: Python `typing.Protocol` (structural subtyping) + entry-point registry

**Rationale**:
- Each plugin type defines a Protocol (interface): `Ingestor`, `DedupStrategy`, `LLMProvider`, `Validator`, `Sink`
- Built-in plugins live in `app/plugins/{type}/` — auto-discovered via `__init__.py` registry
- Custom plugins (e.g., Help Core SharePoint sink) are Python modules referenced in YAML config
- No dynamic code loading from YAML — plugin module paths are validated at pipeline registration
- Protocol-based means no inheritance required — any class matching the signature works

**Alternatives considered**:
- ABC (Abstract Base Classes): Requires inheritance, more rigid
- importlib + dynamic import: Security risk if YAML specifies arbitrary module paths
- Stevedore/pluggy: External dependency for simple use case

---

## Decision 4: PDF Ingestion

**Decision**: PyMuPDF (fitz) as primary, pdfplumber as fallback

**Rationale**:
- PyMuPDF is fastest for text extraction (C-based, ~10x faster than pdfplumber)
- pdfplumber handles table-heavy PDFs better
- Auto-detect: try PyMuPDF first; if text extraction yields < 100 chars, retry with pdfplumber
- Both are pure-Python installable (no system deps beyond what Alpine provides)
- Image-based PDFs (scanned): out of scope for v1 (would need Tesseract OCR)

**Alternatives considered**:
- pdfplumber only: Slower for simple text PDFs
- PyPDF2: Less reliable text extraction
- Tesseract OCR: Adds ~80MB to image, not needed for v1 use cases

---

## Decision 5: Database Migrations

**Decision**: Alembic with async support (alembic + asyncpg)

**Rationale**:
- Standard Python migration tool, integrates with SQLAlchemy models
- Engine uses its own schema (`processing_engine`) separate from project schemas
- Auto-generate migrations from SQLAlchemy model changes
- `alembic upgrade head` in Docker entrypoint ensures schema is current on deploy

**Alternatives considered**:
- Raw SQL files: No auto-generation, error-prone for model changes
- yoyo-migrations: Less ecosystem support
- dbmate: Go-based, would add dependency

---

## Decision 6: Configuration Management

**Decision**: Pydantic Settings (env vars) + YAML pipeline configs (pydantic model validation)

**Rationale**:
- App-level config (DB URL, API keys, worker count) via env vars → `pydantic-settings`
- Pipeline configs via YAML files → validated against Pydantic models at registration time
- YAML supports `${ENV_VAR}` interpolation for secrets (connection strings, API keys)
- Pipeline configs are versioned — stored in DB after validation, YAML is just the input format
- Schema files (JSON Schema for LLM output) are loaded and stored alongside pipeline config

**Alternatives considered**:
- TOML: Less readable for nested config (pipeline definitions are deeply nested)
- JSON: No comments, less human-friendly for operators
- Database-only config: Harder to version control and review in PRs

---

## Decision 7: Embedding Model for Semantic Dedup

**Decision**: OpenAI `text-embedding-3-small` (1536 dimensions) via pgvector

**Rationale**:
- Consistent with Digital AI standards (identity/preferences.md: "Embedding model: OpenAI text-embedding-3-small (1536d) for n8n compatibility")
- pgvector extension in PostgreSQL 16 — no separate vector DB needed
- Cosine similarity with configurable threshold (default 0.90)
- Embeddings stored in `cache` table alongside content_hash for dual-layer dedup
- Cost: ~$0.00002 per embedding (negligible)

**Alternatives considered**:
- Qdrant: Already used in Cortex, but adds infrastructure dependency
- FAISS: In-memory only, doesn't survive restart
- text-embedding-3-large: 3072d, more accurate but 2x cost and storage

---

## Decision 8: Testing Strategy

**Decision**: pytest + pytest-asyncio + testcontainers-python (PostgreSQL)

**Rationale**:
- pytest is the standard Python test framework
- pytest-asyncio for async test functions (matches async codebase)
- testcontainers-python spins up real PostgreSQL in Docker for integration tests
- No mocking of database — real SQL against real PostgreSQL (Constitution X: Testabilidade)
- Unit tests for plugins (mock LLM responses), integration tests for orchestrator pipeline
- Contract tests for API endpoints (httpx TestClient)

**Alternatives considered**:
- unittest: Less ergonomic, no async support built-in
- SQLite for tests: Different SQL dialect, pgvector not available
- Mocked DB: Cortex gotcha — "got burned when mocked tests passed but prod migration failed"

---

## Decision 9: Docker Image Strategy

**Decision**: Multi-stage build, Python 3.12-slim base, target < 200MB

**Rationale**:
- SC-011 requires image < 200MB
- python:3.12-slim-bookworm as base (~150MB with dependencies)
- Multi-stage: builder stage installs deps, runtime stage copies only needed files
- System deps: libpq (for asyncpg), libmupdf (for PyMuPDF) — both available via apt
- Single container runs both API + worker (configurable via `ROLE=api|worker|both`)

**Alternatives considered**:
- Alpine: Smaller base but musl libc causes issues with some Python C extensions
- Separate API/worker images: Unnecessary for v1 volume, single image is simpler
- Distroless: No shell for debugging in production

---

## Decision 10: Concurrency & Rate Limiting

**Decision**: asyncio.Semaphore per job + token bucket for LLM API

**Rationale**:
- Per-job concurrency: `asyncio.Semaphore(pipeline.max_concurrent)` limits parallel item processing
- LLM rate limiting: Simple token bucket (configurable requests_per_minute in pipeline config)
- Backoff: Exponential backoff on 429/5xx from LLM API (FR-018), starting at 1s, max 60s
- No Redis needed — all state in-memory per worker process (fine for single-container v1)

**Alternatives considered**:
- Redis-based rate limiter: Overkill for single-process architecture
- Fixed delay between requests: Wastes capacity when under limit
- Circuit breaker: Could add in v2 if needed
