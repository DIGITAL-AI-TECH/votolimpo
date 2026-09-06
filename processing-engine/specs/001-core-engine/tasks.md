# Tasks: Core Engine

**Input**: Design documents from `/specs/001-core-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Included — spec requires pytest + testcontainers with real PostgreSQL, zero DB mocks.

**Organization**: Tasks grouped by user story. P1 stories (US1, US2, US3, US7) first, then P2 (US4, US5, US6).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project — `app/`, `tests/`, `alembic/`, `db_models/` at repository root
- SQL queries in `app/sql/` as constant strings
- Pydantic models in `app/models/`, SQLAlchemy models in `db_models/` (migration only)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, Docker dev environment

- [ ] T001 Create `pyproject.toml` with all dependencies (fastapi, asyncpg, httpx, openai, pydantic, pydantic-settings, PyMuPDF, beautifulsoup4, jsonschema, PyYAML, alembic, sqlalchemy, pytest, pytest-asyncio, testcontainers, uvicorn, httpx[http2]) and project metadata
- [ ] T002 Create `.env.example` with all environment variables (DATABASE_URL, OPENAI_API_KEY, API_KEY, ENGINE_ROLE, WORKER_POLL_INTERVAL_SECONDS, LOG_LEVEL)
- [ ] T003 [P] Create `docker-compose.yml` with postgres:16 service (pgvector extension enabled via init script), port 5432, volume for data persistence
- [ ] T004 [P] Create `app/__init__.py` and `app/config.py` with pydantic-settings Settings class for all env vars (DATABASE_URL, OPENAI_API_KEY, API_KEY, ENGINE_ROLE enum api|worker|both, WORKER_POLL_INTERVAL_SECONDS=1.0, LOG_LEVEL=INFO)
- [ ] T005 Create `app/db.py` with asyncpg pool lifecycle (create_pool, get_pool, close_pool) — pool created on app startup, closed on shutdown
- [ ] T006 Create `app/main.py` with FastAPI app, lifespan handler (DB pool + optional worker start), version from pyproject.toml, CORS middleware
- [ ] T007 [P] Create `app/deps.py` with FastAPI dependencies: `get_db()` (asyncpg connection from pool), `verify_api_key()` (X-API-Key header validation)
- [ ] T008 Create all `__init__.py` files for package structure: `app/api/`, `app/models/`, `app/services/`, `app/plugins/`, `app/plugins/ingestors/`, `app/plugins/dedup/`, `app/plugins/llm/`, `app/plugins/validators/`, `app/plugins/sinks/`, `app/sql/`, `db_models/`, `tests/`, `tests/unit/`, `tests/integration/`, `tests/contract/`

---

## Phase 2: Foundational (Database + Migrations + Health)

**Purpose**: PostgreSQL schema, all 10 Alembic migrations, health endpoint, test fixtures

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 Create `alembic.ini` at project root with `sqlalchemy.url` pointing to DATABASE_URL, script_location = alembic
- [ ] T010 Create `alembic/env.py` with async migration support (asyncpg), target_metadata from db_models, schema `processing_engine`
- [ ] T011 [P] Create SQLAlchemy models in `db_models/pipeline.py` — Pipeline model matching data-model.md table 1 (pipelines)
- [ ] T012 [P] Create SQLAlchemy models in `db_models/job.py` — Job model matching data-model.md table 2 (jobs)
- [ ] T013 [P] Create SQLAlchemy models in `db_models/item.py` — Item model matching data-model.md table 3 (items) with pgvector column
- [ ] T014 [P] Create SQLAlchemy models in `db_models/processing_log.py` — ProcessingLog model matching data-model.md table 4
- [ ] T015 [P] Create SQLAlchemy models in `db_models/cache_entry.py` — CacheEntry model matching data-model.md table 5
- [ ] T016 [P] Create SQLAlchemy models in `db_models/llm_call_log.py` — LLMCallLog model matching data-model.md table 6
- [ ] T017 [P] Create SQLAlchemy models in `db_models/model_pricing.py` — ModelPricing model matching data-model.md table 7
- [ ] T018 [P] Create `db_models/__init__.py` importing all models for Alembic autogenerate discovery
- [ ] T019 Create `alembic/versions/001_create_schema.py` — CREATE SCHEMA processing_engine + CREATE EXTENSION IF NOT EXISTS vector
- [ ] T020 Create `alembic/versions/002_create_enums.py` — all 5 ENUMs (job_status, item_status, log_step, dedup_strategy, call_status)
- [ ] T021 Create `alembic/versions/003_create_pipelines.py` — pipelines table with all columns and indexes per data-model.md
- [ ] T022 Create `alembic/versions/004_create_jobs.py` — jobs table with SKIP LOCKED index, idempotency unique index
- [ ] T023 Create `alembic/versions/005_create_items.py` — items table with pgvector HNSW index, hash indexes
- [ ] T024 Create `alembic/versions/006_create_processing_logs.py` — processing_logs table with composite indexes
- [ ] T025 Create `alembic/versions/007_create_cache.py` — cache_entries table with unique hash+pipeline index
- [ ] T026 Create `alembic/versions/008_create_llm_call_log.py` — llm_call_log table with budget partial index
- [ ] T027 Create `alembic/versions/009_create_model_pricing.py` — model_pricing table with seed data (OpenAI pricing 2026-09)
- [ ] T028 Create `alembic/versions/010_create_functions.py` — calculate_call_cost() and check_budget() PostgreSQL functions
- [ ] T029 Create `app/api/health.py` — GET /health endpoint (no auth): returns status, version, db_connected (pool check), worker_active
- [ ] T030 Register health router in `app/main.py`
- [ ] T031 Create `tests/conftest.py` with testcontainers PostgreSQL fixture (session-scoped): starts postgres:16 container, runs alembic migrations, provides async connection pool, cleanup after session
- [ ] T032 Create test `tests/integration/test_health.py` — verify health endpoint returns 200 with db_connected=true, migrations apply cleanly

**Checkpoint**: Database schema running, health endpoint live, test infrastructure ready

---

## Phase 3: User Story 3 — Registrar Pipeline via Configuração (Priority: P1)

**Goal**: Register, update, list pipelines via API and CLI. Version snapshots on update.

**Independent Test**: POST pipeline config → GET returns it → PUT updates version → jobs use correct config.

**Why first**: All other stories depend on having a pipeline registered.

### Tests for US3

- [ ] T033 [P] [US3] Create unit test `tests/unit/test_pipeline_models.py` — validate PipelineCreate pydantic model: required fields (name, system_prompt, output_schema), defaults, validators enum validation
- [ ] T034 [P] [US3] Create integration test `tests/integration/test_pipelines_api.py` — POST create pipeline (201), GET list (200), GET by id (200), PUT update bumps version, POST duplicate name (409), POST missing required field (422), GET nonexistent (404)

### Implementation for US3

- [ ] T035 [P] [US3] Create Pydantic models in `app/models/pipeline.py` — PipelineCreate (request), Pipeline (response), PipelineUpdate per openapi.yaml schemas
- [ ] T036 [US3] Create SQL queries in `app/sql/pipelines.sql` — INSERT pipeline, SELECT by id, SELECT all active, UPDATE pipeline (version bump), check name uniqueness
- [ ] T037 [US3] Create `app/api/pipelines.py` — POST /v1/pipelines (create), GET /v1/pipelines (list with active_only filter), GET /v1/pipelines/{id} (detail), PUT /v1/pipelines/{id} (update with version increment). All endpoints require X-API-Key via verify_api_key dependency
- [ ] T038 [US3] Create `app/cli.py` — `register-pipeline` CLI command: reads YAML file, validates against PipelineCreate model, inserts into DB
- [ ] T039 [US3] Create `pipelines/example.yaml` — example pipeline config for VotoLimpo use case (html ingestor, hash dedup, openai LLM, schema validator, postgresql sink)
- [ ] T040 [US3] Register pipelines router in `app/main.py` with prefix /v1 and api_key dependency

**Checkpoint**: Pipelines CRUD working. Can register pipeline via API or YAML CLI.

---

## Phase 4: User Story 1 — Submeter Item para Processamento (Priority: P1) 🎯 MVP

**Goal**: Submit single item job, process through full pipeline (ingest → dedup → process → validate → persist), return structured result.

**Independent Test**: POST job with 1 item → worker processes → GET result returns structured output.

### Plugin System (prerequisite for US1)

- [ ] T041 [P] [US1] Create `app/plugins/protocols.py` — 5 Protocol classes: Ingestor (ingest(raw, content_type) → str), DedupStrategy (check(content, pipeline_id, conn) → DedupResult), LLMProvider (complete(prompt, system_prompt, schema, config) → LLMResponse + embed(text) → list[float]), Validator (validate(output, source, schema) → ValidationResult), Sink (persist(item_id, output, config, conn) → None)
- [ ] T042 [P] [US1] Create `app/plugins/registry.py` — PluginRegistry with register(type, name, cls), get(type, name), list_available(type). Auto-registers built-in plugins on import.
- [ ] T043 [P] [US1] Create `app/plugins/ingestors/text.py` — TextIngestor: passthrough with encoding detection, respects max_content_chars truncation (preserve start+end per FR-017)
- [ ] T044 [P] [US1] Create `app/plugins/ingestors/html.py` — HTMLIngestor: BeautifulSoup4 extract text, strip tags/scripts/styles, normalize whitespace, truncate
- [ ] T045 [P] [US1] Create `app/plugins/ingestors/pdf.py` — PDFIngestor: PyMuPDF extract text page by page, handle corrupted PDFs gracefully (error message, not crash), truncate
- [ ] T046 [P] [US1] Create `app/plugins/ingestors/json_ingestor.py` — JSONIngestor: parse JSON, serialize to readable text for LLM consumption, truncate
- [ ] T047 [P] [US1] Create `app/plugins/ingestors/auto.py` — AutoIngestor: detect content_type from MIME or content sniffing, delegate to appropriate ingestor
- [ ] T048 [P] [US1] Create `app/plugins/ingestors/__init__.py` — register all ingestors in registry
- [ ] T049 [P] [US1] Create `app/plugins/dedup/hash.py` — HashDedupStrategy: SHA-256 of url and/or content, check against items table (url_hash, content_hash columns), return DedupResult(is_duplicate, matched_item_id, strategy)
- [ ] T050 [P] [US1] Create `app/plugins/dedup/__init__.py` — register hash dedup in registry
- [ ] T051 [P] [US1] Create `app/plugins/llm/openai.py` — OpenAIProvider: chat completions (structured output via response_format json_schema), embeddings (text-embedding-3-small). Returns tokens used, latency. Uses httpx async client.
- [ ] T052 [P] [US1] Create `app/plugins/llm/__init__.py` — register openai provider in registry
- [ ] T053 [P] [US1] Create `app/plugins/validators/schema.py` — SchemaValidator: validate output against JSON Schema (jsonschema library), return ValidationResult(valid, errors[])
- [ ] T054 [P] [US1] Create `app/plugins/validators/__init__.py` — register schema validator in registry
- [ ] T055 [P] [US1] Create `app/plugins/sinks/postgresql.py` — PostgreSQLSink: upsert results to configured table (ON CONFLICT DO UPDATE), uses sink_config for table/schema/columns mapping
- [ ] T056 [P] [US1] Create `app/plugins/sinks/__init__.py` — register postgresql sink in registry
- [ ] T057 [P] [US1] Create `app/plugins/__init__.py` — import all sub-packages to trigger auto-registration

### Tests for US1

- [ ] T058 [P] [US1] Create `tests/unit/test_ingestors.py` — test TextIngestor (passthrough, truncation), HTMLIngestor (tag stripping, script removal), PDFIngestor (text extraction, corrupted file handling), JSONIngestor (serialization), AutoIngestor (mime detection)
- [ ] T059 [P] [US1] Create `tests/unit/test_dedup.py` — test HashDedupStrategy: new item returns not duplicate, same url_hash returns duplicate with matched_item_id, same content_hash returns duplicate
- [ ] T060 [P] [US1] Create `tests/unit/test_validators.py` — test SchemaValidator: valid output passes, missing required field fails, wrong type fails, extra fields pass (additionalProperties)

### Core Implementation for US1

- [ ] T061 [P] [US1] Create Pydantic models in `app/models/job.py` — JobCreate (request with items array), Job (response), JobStatus enum per openapi.yaml
- [ ] T062 [P] [US1] Create Pydantic models in `app/models/item.py` — ItemCreate (request), ItemResult (response with output, usage, dedup_result, cached, duration_ms)
- [ ] T063 [US1] Create SQL queries in `app/sql/items.sql` — INSERT item, UPDATE item status/output/dedup, SELECT items by job_id, check url_hash exists, check content_hash exists
- [ ] T064 [US1] Create SQL queries in `app/sql/jobs.sql` — INSERT job (with idempotency_key check), UPDATE job status/counters, SELECT job by id, SELECT FOR UPDATE SKIP LOCKED (worker claim)
- [ ] T065 [US1] Create `app/services/orchestrator.py` — Orchestrator class with process_item(item, pipeline, conn) method: step-by-step execution (ingest → dedup → process → validate → persist), writes processing_log per step, handles retries with exponential backoff (FR-018), respects max_retries from pipeline config
- [ ] T066 [US1] Create `app/api/jobs.py` — POST /v1/jobs (create job, insert items, return job with status queued), GET /v1/jobs/{id} (status + counters), GET /v1/jobs/{id}/result (all item results), GET /v1/jobs/{id}/logs (processing logs with optional step filter). Check idempotency_key (409 if duplicate). All endpoints require X-API-Key.
- [ ] T067 [US1] Create `app/worker.py` — SKIP LOCKED polling loop: claim_job() selects queued job with FOR UPDATE SKIP LOCKED, process_job() iterates items through orchestrator, update_counters() increments items_completed/items_failed in real-time, set job status (completed/failed/partial) on finish. asyncio.Semaphore for max_concurrent. Configurable poll interval.
- [ ] T068 [US1] Register jobs router in `app/main.py`, start worker in lifespan if ENGINE_ROLE includes worker

### Integration Test for US1

- [ ] T069 [US1] Create `tests/integration/test_jobs_api.py` — full integration test: create pipeline, POST job with 1 text item, wait for worker to process, GET job status = completed, GET result has valid output. Test idempotency_key duplicate returns 409.
- [ ] T070 [US1] Create `tests/unit/test_orchestrator.py` — test orchestrator with mock LLM provider: verify all 5 steps execute in order, processing_logs created for each step, retry logic works on LLM failure

**Checkpoint**: MVP complete — can submit single-item job, process end-to-end, retrieve structured result.

---

## Phase 5: User Story 7 — Metrificação de Custos (Priority: P1)

**Goal**: Track every LLM call with cost, expose cost breakdown API, enforce budget limits per pipeline.

**Independent Test**: Process items in 2 pipelines → GET /v1/costs returns correct breakdown by pipeline → set budget limit → exceed → job rejected with 429.

### Tests for US7

- [ ] T071 [P] [US7] Create `tests/unit/test_cost_tracker.py` — test CostTracker.log_call() inserts into llm_call_log, calculate_cost() uses model_pricing correctly, check_budget() returns correct pct_used and is_exceeded
- [ ] T072 [P] [US7] Create `tests/integration/test_costs_api.py` — test GET /v1/costs with pipeline_id filter, group_by=pipeline, group_by=model, period=month. Test budget enforcement: set budget_limit_usd on pipeline, process items until 80% (warning in log), process until 100% (POST job returns 429)

### Implementation for US7

- [ ] T073 [P] [US7] Create Pydantic models in `app/models/cost.py` — CostReport, CostBreakdownItem, ModelPricing, ModelPricingCreate per openapi.yaml schemas
- [ ] T074 [US7] Create SQL queries in `app/sql/costs.sql` — SELECT aggregated costs with GROUP BY (pipeline_id, job_id, model, date_trunc), SUM tokens/cost, JOIN pipeline name for labels. SELECT budget check (current period cost vs limit). INSERT llm_call_log. SELECT/UPSERT model_pricing.
- [ ] T075 [US7] Create `app/services/cost_tracker.py` — CostTracker class: log_call(provider, model, tokens_in, tokens_out, latency, status, item_id, job_id, pipeline_id, is_retry) inserts into llm_call_log with calculated cost. check_budget(pipeline_id) calls check_budget() SQL function. get_pricing(provider, model) looks up model_pricing.
- [ ] T076 [US7] Integrate CostTracker into `app/services/orchestrator.py` — call cost_tracker.log_call() after every LLM call (completions AND embeddings), including retries (is_retry=true). Call check_budget() before processing item — if exceeded, raise BudgetExceededError.
- [ ] T077 [US7] Create `app/api/costs.py` — GET /v1/costs with all filters (pipeline_id, job_id, period, start_date, end_date, group_by) per openapi.yaml. Returns CostReport with breakdown.
- [ ] T078 [US7] Create `app/api/pricing.py` — GET /v1/pricing (list active pricing), POST /v1/pricing (upsert model pricing). Requires X-API-Key.
- [ ] T079 [US7] Add budget check in `app/api/jobs.py` POST /v1/jobs — before creating job, call check_budget(pipeline_id). If exceeded, return 429 with "Budget limit reached for pipeline {name}".
- [ ] T080 [US7] Register costs and pricing routers in `app/main.py`

**Checkpoint**: Full cost tracking operational. Every LLM call logged, costs queryable, budgets enforced.

---

## Phase 6: User Story 2 — Processar Batch de Documentos (Priority: P1)

**Goal**: Submit batch of 10-1000 items, process in parallel with concurrency control, detect duplicates between items, callback on completion.

**Independent Test**: POST job with 20 items (2 duplicates) → worker processes max 5 concurrent → result has 18 completed + 2 duplicate → callback_url receives POST.

### Tests for US2

- [ ] T081 [P] [US2] Create `tests/integration/test_worker.py` — test batch processing: submit 10 items, verify all processed. Test concurrency: max_concurrent=2, verify no more than 2 run simultaneously. Test partial failure: 1 item fails, job status = partial with correct counters.

### Implementation for US2

- [ ] T082 [US2] Create `app/services/callback.py` — CallbackService: send POST to callback_url with job result (httpx async, timeout 30s, 3 retries with backoff). Log callback attempts. Handle failures gracefully (log error, don't crash job).
- [ ] T083 [US2] Enhance `app/worker.py` — process_job() processes items with asyncio.Semaphore(max_concurrent) from pipeline config. After all items processed, determine final status (completed/partial/failed based on counters). Call callback_url if configured. Rate limiting via asyncio.sleep between LLM calls based on rate_limit_rpm.
- [ ] T084 [US2] Integrate callback into worker — after job completes (any status), if callback_url is set, call CallbackService.send().

**Checkpoint**: Batch processing with concurrency control, dedup between batch items, callback on completion.

---

## Phase 7: User Story 5 — Cache de Resultados (Priority: P2)

**Goal**: Cache processed results by content_hash; return cached result without LLM call on cache hit; TTL expiration; skip_cache override.

**Independent Test**: Process item A → process item B with same content (different URL) → B returns cached=true with cost_usd=0 → wait TTL → reprocess → new result.

### Tests for US5

- [ ] T085 [P] [US5] Create `tests/integration/test_cache.py` — test cache hit: process item, submit same content with different URL, verify cached=true and cost=0. Test cache miss: different content, verify cached=false. Test skip_cache: same content but skip_cache=true, verify reprocessed. Test TTL expiry (mock time or short TTL).

### Implementation for US5

- [ ] T086 [US5] Add cache SQL to `app/sql/items.sql` — SELECT from cache_entries by content_hash+pipeline_id WHERE expires_at > now(). INSERT/UPDATE cache entry on successful processing. DELETE expired entries.
- [ ] T087 [US5] Integrate cache into `app/services/orchestrator.py` — after dedup step (if not duplicate), check cache by content_hash+pipeline_id. If cache hit and not skip_cache: return cached output, set item.cached=true, skip LLM call. If cache miss or skip_cache: process normally, save result to cache with TTL.

**Checkpoint**: Cache operational. Identical content returns cached result with zero LLM cost.

---

## Phase 8: User Story 6 — Logging e Auditoria Completa (Priority: P2)

**Goal**: Detailed processing_logs for every step of every item, queryable via API.

**Independent Test**: Process item → GET /v1/jobs/{id}/logs → 5 log entries (ingest, dedup, process, validate, persist) with duration_ms and metadata.

### Implementation for US6

- [ ] T088 [US6] Enhance `app/services/orchestrator.py` — ensure every step (ingest, dedup, process, validate, persist) writes a processing_log entry with: step enum, status (success/failed/skipped), duration_ms (measured via time.monotonic), error_message, metadata (e.g., dedup_strategy used, tokens consumed, validator names). Already partially done in US1; this task completes metadata and ensures skipped steps are logged.
- [ ] T089 [US6] Ensure GET /v1/jobs/{id}/logs in `app/api/jobs.py` returns ProcessingLog list with step filter support — already created in US1 but verify completeness against openapi.yaml schema.

**Checkpoint**: Full audit trail for every processing step. Every step logged with timing and metadata.

---

## Phase 9: User Story 4 — Consultar Status e Métricas (Priority: P2)

**Goal**: Real-time job status with counters, aggregated stats endpoint across all jobs/pipelines.

**Independent Test**: Submit jobs → GET /v1/stats → returns total_jobs, total_items, success_rate, total_cost_usd, cache_hit_rate.

### Tests for US4

- [ ] T090 [P] [US4] Create `tests/integration/test_stats_api.py` — test GET /v1/stats: process 3 jobs (2 success, 1 partial), verify total_jobs=3, items counts correct, success_rate calculated, total_cost_usd matches sum of costs. Test pipeline_id filter. Test period filter.

### Implementation for US4

- [ ] T091 [P] [US4] Create Pydantic models in `app/models/stats.py` — Stats response model per openapi.yaml: period, total_jobs, total_items, items_completed, items_failed, success_rate, total_cost_usd, avg_duration_ms, cache_hit_rate, dedup_rate
- [ ] T092 [US4] Create SQL queries in `app/sql/stats.sql` — aggregation query: COUNT jobs, SUM items (total/completed/failed), AVG duration, SUM cost from llm_call_log, COUNT cached items / total for cache_hit_rate, COUNT duplicate items / total for dedup_rate. Support pipeline_id and period filters.
- [ ] T093 [US4] Create `app/api/stats.py` — GET /v1/stats with pipeline_id and period (day/week/month/all) query params. Returns Stats model. Requires X-API-Key.
- [ ] T094 [US4] Register stats router in `app/main.py`
- [ ] T095 [US4] Add GET /v1/jobs (list jobs) to `app/api/jobs.py` — with pipeline_id, status, limit, offset filters per openapi.yaml. Returns paginated list with total count.

**Checkpoint**: Operational visibility. Stats endpoint shows health of processing across all pipelines.

---

## Phase 10: Additional Plugins (Dedup + Validators)

**Purpose**: Complete plugin coverage — semantic dedup, composite dedup, grounding/range/date validators.

- [ ] T096 [P] Create `app/plugins/dedup/semantic.py` — SemanticDedupStrategy: generate embedding via LLMProvider.embed(), query pgvector for cosine similarity above threshold, return DedupResult. Requires CostTracker integration (embedding calls are billable).
- [ ] T097 [P] Create `app/plugins/dedup/composite.py` — CompositeDedupStrategy: run hash first, if not duplicate run semantic as fallback. Combines both strategies.
- [ ] T098 [P] Create `app/plugins/validators/grounding.py` — GroundingValidator: check that extracted entities/names/dates in LLM output actually appear in the source text (prevent hallucination)
- [ ] T099 [P] Create `app/plugins/validators/range_val.py` — RangeValidator: check numeric fields (scores, ratings) are within configured range (0.0-1.0 default)
- [ ] T100 [P] Create `app/plugins/validators/date_val.py` — DateValidator: check date fields are not in the future (anti-hallucination for temporal data)
- [ ] T101 Register all new plugins in respective `__init__.py` files
- [ ] T102 [P] Add tests in `tests/unit/test_dedup.py` — semantic dedup: mock embedding, verify cosine query. Composite: hash hit skips semantic, hash miss falls through to semantic.
- [ ] T103 [P] Add tests in `tests/unit/test_validators.py` — grounding: entity exists in source → pass, entity missing → fail. Range: value in range → pass, out of range → fail. Date: past date → pass, future date → fail.

**Checkpoint**: All plugin types fully implemented and tested.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Docker production image, CI/CD, contract tests, example config

- [ ] T104 Create `Dockerfile` — multi-stage build: python:3.12-slim base, install deps from pyproject.toml, copy app code, target <200MB image. CMD configurable via ENGINE_ROLE env var.
- [ ] T105 [P] Create `docker-stack.yml` — Docker Swarm production config with Traefik labels, healthcheck, deploy replicas, resource limits, secrets for API keys
- [ ] T106 [P] Create `.github/workflows/ci.yml` — GitHub Actions: lint (ruff), typecheck (mypy or pyright), test (pytest with testcontainers), build Docker image, push to registry. Include n8n Discord notification matrix per deployment-governance.
- [ ] T107 Create `tests/contract/test_openapi.py` — load openapi.yaml, validate all defined endpoints exist and return correct status codes and response schemas. Verify API matches contract.
- [ ] T108 Final validation: run full test suite (`pytest -v`), verify all tests pass, check Docker image builds and is <200MB, verify quickstart.md steps work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US3 Pipelines)**: Depends on Phase 2 — BLOCKS US1, US2, US7 (they need pipelines)
- **Phase 4 (US1 Single Item)**: Depends on Phase 3 — core MVP
- **Phase 5 (US7 Costs)**: Depends on Phase 4 (needs orchestrator + LLM calls to track)
- **Phase 6 (US2 Batch)**: Depends on Phase 4 (extends worker with concurrency + callback)
- **Phase 7 (US5 Cache)**: Depends on Phase 4 (extends orchestrator with cache layer)
- **Phase 8 (US6 Logging)**: Depends on Phase 4 (enhances orchestrator logging)
- **Phase 9 (US4 Stats)**: Depends on Phase 5 (needs cost data for stats)
- **Phase 10 (Plugins)**: Depends on Phase 4 (extends plugin system)
- **Phase 11 (Polish)**: Depends on all previous phases

### User Story Dependencies

```
Phase 2 (Foundation) ──► Phase 3 (US3: Pipelines) ──► Phase 4 (US1: Single Item MVP)
                                                            │
                                              ┌─────────────┼─────────────┬──────────────┐
                                              ▼             ▼             ▼              ▼
                                        Phase 5        Phase 6       Phase 7        Phase 8
                                       (US7: Costs)   (US2: Batch)  (US5: Cache)   (US6: Logs)
                                              │
                                              ▼
                                        Phase 9
                                       (US4: Stats)
                                              │
                                              ▼
                                        Phase 10 (Plugins) ──► Phase 11 (Polish)
```

### Within Each User Story

- Tests written FIRST, verify they FAIL
- Models/SQL before services
- Services before API endpoints
- Core implementation before integration enhancements
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T003, T004 can run in parallel
- **Phase 2**: All db_models (T011-T018) can run in parallel. Then all migrations sequential.
- **Phase 3**: T033, T034 (tests) in parallel. T035 (models) in parallel with tests.
- **Phase 4**: All plugins (T041-T057) can run in parallel. All plugin tests (T058-T060) in parallel. Models T061-T062 in parallel.
- **Phase 5**: T071-T072 (tests) in parallel. T073 (models) in parallel.
- **Phase 6**: T081 (test) independent.
- **Phase 10**: All plugins (T096-T100) can run in parallel. All tests (T102-T103) in parallel.
- **Phase 11**: T105, T106 can run in parallel.

---

## Parallel Example: Phase 4 (US1 MVP)

```bash
# Wave 1 — All plugins in parallel (different files, zero dependencies):
T041: app/plugins/protocols.py
T042: app/plugins/registry.py
T043-T048: app/plugins/ingestors/*.py (6 files in parallel)
T049-T050: app/plugins/dedup/hash.py + __init__.py
T051-T052: app/plugins/llm/openai.py + __init__.py
T053-T054: app/plugins/validators/schema.py + __init__.py
T055-T057: app/plugins/sinks/postgresql.py + __init__.py + plugins/__init__.py

# Wave 2 — Tests + Models in parallel (after plugins):
T058-T060: tests/unit/test_ingestors.py, test_dedup.py, test_validators.py
T061-T062: app/models/job.py, app/models/item.py

# Wave 3 — SQL queries (after models):
T063: app/sql/items.sql
T064: app/sql/jobs.sql

# Wave 4 — Services + API (sequential, depends on SQL):
T065: app/services/orchestrator.py
T066: app/api/jobs.py
T067: app/worker.py
T068: app/main.py (register + worker start)

# Wave 5 — Integration tests (after everything):
T069-T070: tests/integration/ + tests/unit/test_orchestrator.py
```

---

## Implementation Strategy

### MVP First (Phases 1-4: Setup + Foundation + Pipelines + Single Item)

1. Complete Phase 1: Setup (pyproject.toml, docker-compose, config)
2. Complete Phase 2: Foundational (migrations, health, test fixtures)
3. Complete Phase 3: US3 Pipelines (CRUD + CLI)
4. Complete Phase 4: US1 Single Item (full pipeline, MVP!)
5. **STOP and VALIDATE**: Submit test item, verify end-to-end processing
6. Deploy as usable service

### Incremental Delivery

1. **MVP** (Phases 1-4): Submit item → get result ✅
2. **+Costs** (Phase 5): Track every LLM call, budget enforcement ✅
3. **+Batch** (Phase 6): Process 100+ items with concurrency ✅
4. **+Cache** (Phase 7): Save ~30% on duplicate content ✅
5. **+Logging** (Phase 8): Full audit trail per step ✅
6. **+Stats** (Phase 9): Operational metrics dashboard ✅
7. **+Plugins** (Phase 10): Semantic dedup, advanced validators ✅
8. **+Production** (Phase 11): Docker, CI/CD, contract tests ✅

---

## Summary

| Metric | Value |
|--------|-------|
| **Total tasks** | 108 |
| **Phase 1 (Setup)** | 8 tasks |
| **Phase 2 (Foundation)** | 24 tasks |
| **Phase 3 (US3 Pipelines)** | 8 tasks |
| **Phase 4 (US1 Single Item)** | 30 tasks |
| **Phase 5 (US7 Costs)** | 10 tasks |
| **Phase 6 (US2 Batch)** | 4 tasks |
| **Phase 7 (US5 Cache)** | 3 tasks |
| **Phase 8 (US6 Logging)** | 2 tasks |
| **Phase 9 (US4 Stats)** | 6 tasks |
| **Phase 10 (Plugins)** | 8 tasks |
| **Phase 11 (Polish)** | 5 tasks |
| **Parallel opportunities** | 67 tasks marked [P] |
| **MVP scope** | Phases 1-4 (70 tasks) |

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All SQL in `app/sql/*.sql` as raw query strings — no ORM at runtime
- SQLAlchemy models in `db_models/` used ONLY for Alembic migration generation
