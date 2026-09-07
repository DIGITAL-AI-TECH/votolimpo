# Data Model: Core Engine

**Feature**: 001-core-engine
**Date**: 2026-09-06
**Schema**: `processing_engine`

## ENUMs

```sql
CREATE TYPE processing_engine.job_status AS ENUM (
    'queued', 'running', 'completed', 'failed', 'partial', 'cancelled'
);

CREATE TYPE processing_engine.item_status AS ENUM (
    'pending', 'ingesting', 'deduplicating', 'processing', 'validating',
    'persisting', 'completed', 'failed', 'duplicate', 'similar'
);

CREATE TYPE processing_engine.log_step AS ENUM (
    'ingest', 'dedup', 'process', 'validate', 'persist'
);

CREATE TYPE processing_engine.dedup_strategy AS ENUM (
    'hash', 'semantic', 'composite', 'none'
);

CREATE TYPE processing_engine.call_status AS ENUM (
    'success', 'error'
);
```

## Tables

### 1. pipelines

Stores pipeline configurations. Each project registers 1+ pipelines.

```sql
CREATE TABLE processing_engine.pipelines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    version         INTEGER NOT NULL DEFAULT 1,
    description     TEXT,

    -- Ingestor config
    ingestor_type   TEXT NOT NULL DEFAULT 'auto',       -- 'html', 'pdf', 'text', 'json', 'auto'
    max_content_chars INTEGER DEFAULT 100000,

    -- Dedup config
    dedup_strategy  processing_engine.dedup_strategy NOT NULL DEFAULT 'hash',
    dedup_threshold REAL DEFAULT 0.90,                  -- for semantic dedup

    -- LLM config
    llm_provider    TEXT NOT NULL DEFAULT 'openai',
    llm_model       TEXT NOT NULL DEFAULT 'gpt-4.1-mini',
    llm_temperature REAL NOT NULL DEFAULT 0.0,
    llm_seed        INTEGER DEFAULT 42,
    llm_max_tokens  INTEGER DEFAULT 16384,
    system_prompt   TEXT NOT NULL,
    output_schema   JSONB NOT NULL,                     -- JSON Schema for validation

    -- Validators (array of validator names)
    validators      TEXT[] NOT NULL DEFAULT '{"schema"}',  -- 'schema', 'grounding', 'range', 'date'

    -- Sink config
    sink_type       TEXT NOT NULL DEFAULT 'postgresql',
    sink_config     JSONB DEFAULT '{}',                 -- connection details, table name, etc.

    -- Rate limiting
    max_concurrent  INTEGER NOT NULL DEFAULT 5,
    rate_limit_rpm  INTEGER DEFAULT 60,                 -- requests per minute to LLM

    -- Budget
    budget_limit_usd REAL,                              -- NULL = no limit
    budget_period    TEXT DEFAULT 'month',               -- 'day', 'week', 'month'

    -- Retry config
    max_retries     INTEGER NOT NULL DEFAULT 3,
    retry_backoff_base REAL NOT NULL DEFAULT 2.0,       -- exponential backoff base

    -- Cache
    cache_ttl_hours INTEGER NOT NULL DEFAULT 720,       -- 30 days default

    -- Metadata
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pipelines_name ON processing_engine.pipelines (name);
CREATE INDEX idx_pipelines_active ON processing_engine.pipelines (is_active) WHERE is_active = true;
```

### 2. jobs

Processing job requests. Each job belongs to a pipeline and contains 1+ items.

```sql
CREATE TABLE processing_engine.jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),
    pipeline_version INTEGER NOT NULL,                  -- snapshot at submission time (FR-016)
    idempotency_key TEXT,                               -- FR-015: prevents reprocessing
    status          processing_engine.job_status NOT NULL DEFAULT 'queued',
    priority        INTEGER NOT NULL DEFAULT 0,         -- higher = processed first

    -- Counters (updated in real-time)
    items_total     INTEGER NOT NULL DEFAULT 0,
    items_completed INTEGER NOT NULL DEFAULT 0,
    items_failed    INTEGER NOT NULL DEFAULT 0,

    -- Overrides (FR-011)
    override_model  TEXT,                               -- override pipeline llm_model
    skip_dedup      BOOLEAN NOT NULL DEFAULT false,
    skip_cache      BOOLEAN NOT NULL DEFAULT false,
    dry_run         BOOLEAN NOT NULL DEFAULT false,

    -- Callback (FR-013)
    callback_url    TEXT,

    -- Metadata
    metadata        JSONB DEFAULT '{}',                 -- free-form project metadata
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_jobs_idempotency ON processing_engine.jobs (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_jobs_status_priority ON processing_engine.jobs (status, priority DESC, created_at)
    WHERE status = 'queued';  -- SKIP LOCKED query target
CREATE INDEX idx_jobs_pipeline ON processing_engine.jobs (pipeline_id);
CREATE INDEX idx_jobs_created ON processing_engine.jobs (created_at DESC);
```

### 3. items

Individual content items within a job. Atomic unit of processing.

```sql
CREATE TABLE processing_engine.items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES processing_engine.jobs(id) ON DELETE CASCADE,
    status          processing_engine.item_status NOT NULL DEFAULT 'pending',

    -- Input
    source_url      TEXT,
    url_hash        TEXT,                               -- SHA-256 of source_url (dedup layer 1)
    content_type    TEXT NOT NULL DEFAULT 'text/plain',  -- MIME type
    raw_content     TEXT,                               -- original content after ingest
    content_hash    TEXT,                               -- SHA-256 of raw_content (dedup layer 2)
    content_embedding VECTOR(1536),                     -- pgvector for semantic dedup

    -- Output
    output          JSONB,                              -- LLM structured output
    dedup_result    TEXT,                               -- 'new', 'duplicate', 'similar', NULL
    dedup_matched_item_id UUID,                         -- reference to matched item if duplicate/similar

    -- Metadata
    metadata        JSONB DEFAULT '{}',                 -- free-form project metadata
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    cached          BOOLEAN NOT NULL DEFAULT false,     -- true if result came from cache
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_items_job ON processing_engine.items (job_id);
CREATE INDEX idx_items_url_hash ON processing_engine.items (url_hash) WHERE url_hash IS NOT NULL;
CREATE INDEX idx_items_content_hash ON processing_engine.items (content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX idx_items_status ON processing_engine.items (job_id, status);
-- pgvector index for semantic dedup
CREATE INDEX idx_items_embedding ON processing_engine.items
    USING hnsw (content_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

### 4. processing_logs

Audit log for each step of each item's processing pipeline.

```sql
CREATE TABLE processing_engine.processing_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id         UUID NOT NULL REFERENCES processing_engine.items(id) ON DELETE CASCADE,
    job_id          UUID NOT NULL,                      -- denormalized for query performance
    pipeline_id     UUID NOT NULL,                      -- denormalized

    step            processing_engine.log_step NOT NULL,
    status          TEXT NOT NULL,                       -- 'success', 'failed', 'skipped'
    duration_ms     INTEGER,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}',                 -- step-specific data (e.g., dedup_strategy used)

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_processing_logs_item ON processing_engine.processing_logs (item_id);
CREATE INDEX idx_processing_logs_job ON processing_engine.processing_logs (job_id);
CREATE INDEX idx_processing_logs_step ON processing_engine.processing_logs (step, status);
```

### 5. cache_entries

Result cache indexed by content_hash. Avoids reprocessing identical content.

```sql
CREATE TABLE processing_engine.cache_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash    TEXT NOT NULL,
    pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),
    output          JSONB NOT NULL,                     -- cached LLM output

    -- Usage tracking
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    cost_usd        REAL,
    llm_model       TEXT,

    hit_count       INTEGER NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_cache_hash_pipeline ON processing_engine.cache_entries (content_hash, pipeline_id);
CREATE INDEX idx_cache_expires ON processing_engine.cache_entries (expires_at);
```

### 6. llm_call_log

Individual record for EVERY LLM API call — including retries and embedding calls.

```sql
CREATE TABLE processing_engine.llm_call_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id         UUID REFERENCES processing_engine.items(id) ON DELETE SET NULL,
    job_id          UUID,                               -- denormalized
    pipeline_id     UUID NOT NULL,                      -- denormalized

    -- Call details
    provider        TEXT NOT NULL,                       -- 'openai', 'anthropic', etc.
    model           TEXT NOT NULL,                       -- 'gpt-4.1-mini', 'text-embedding-3-small', etc.
    call_type       TEXT NOT NULL DEFAULT 'completion',   -- 'completion', 'embedding'
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,

    -- Cost (calculated from model_pricing)
    cost_usd        REAL NOT NULL DEFAULT 0.0,

    -- Performance
    latency_ms      INTEGER,
    status          processing_engine.call_status NOT NULL,
    error_message   TEXT,
    is_retry        BOOLEAN NOT NULL DEFAULT false,
    retry_number    INTEGER NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for cost queries (FR-021)
CREATE INDEX idx_llm_call_pipeline ON processing_engine.llm_call_log (pipeline_id, created_at DESC);
CREATE INDEX idx_llm_call_job ON processing_engine.llm_call_log (job_id) WHERE job_id IS NOT NULL;
CREATE INDEX idx_llm_call_item ON processing_engine.llm_call_log (item_id) WHERE item_id IS NOT NULL;
CREATE INDEX idx_llm_call_model ON processing_engine.llm_call_log (model, created_at DESC);
CREATE INDEX idx_llm_call_created ON processing_engine.llm_call_log (created_at DESC);
-- Partial index for budget check (fast SUM of current period)
CREATE INDEX idx_llm_call_budget ON processing_engine.llm_call_log (pipeline_id, cost_usd, created_at)
    WHERE status = 'success';
```

### 7. model_pricing

Reference table for LLM pricing. Updated without deploy.

```sql
CREATE TABLE processing_engine.model_pricing (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_price_per_million_tokens  REAL NOT NULL,       -- USD per 1M input tokens
    output_price_per_million_tokens REAL NOT NULL DEFAULT 0.0, -- USD per 1M output tokens (0 for embeddings)
    is_active       BOOLEAN NOT NULL DEFAULT true,
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_model_pricing_unique ON processing_engine.model_pricing (provider, model)
    WHERE is_active = true;

-- Seed with current OpenAI pricing (2026-09)
INSERT INTO processing_engine.model_pricing (provider, model, input_price_per_million_tokens, output_price_per_million_tokens) VALUES
    ('openai', 'gpt-4.1-mini', 0.40, 1.60),
    ('openai', 'gpt-4.1', 2.00, 8.00),
    ('openai', 'gpt-4o', 2.50, 10.00),
    ('openai', 'gpt-4o-mini', 0.15, 0.60),
    ('openai', 'text-embedding-3-small', 0.02, 0.00);
```

## State Transitions

### Job Lifecycle

```
queued ──────► running ──────► completed   (all items succeeded)
                  │
                  ├──────────► partial      (some items succeeded, some failed)
                  │
                  └──────────► failed       (all items failed or critical error)

queued ──────► cancelled                    (cancelled before processing started)
```

### Item Lifecycle

```
pending ──► ingesting ──► deduplicating ──► processing ──► validating ──► persisting ──► completed
                │              │                 │              │              │
                │              ├──► duplicate     │              │              │
                │              └──► similar        │              │              │
                │                                  │              │              │
                └──────────────────────────────────┴──────────────┴──────────────┴──► failed
```

## Cost Calculation Functions

### calculate_call_cost()

```sql
CREATE OR REPLACE FUNCTION processing_engine.calculate_call_cost(
    p_provider TEXT,
    p_model TEXT,
    p_prompt_tokens INTEGER,
    p_completion_tokens INTEGER
) RETURNS REAL AS $$
DECLARE
    v_input_price REAL;
    v_output_price REAL;
BEGIN
    SELECT input_price_per_million_tokens, output_price_per_million_tokens
    INTO v_input_price, v_output_price
    FROM processing_engine.model_pricing
    WHERE provider = p_provider AND model = p_model AND is_active = true
    LIMIT 1;

    IF v_input_price IS NULL THEN
        RAISE WARNING 'No pricing found for %/%, using 0', p_provider, p_model;
        RETURN 0.0;
    END IF;

    RETURN (p_prompt_tokens * v_input_price / 1000000.0)
         + (p_completion_tokens * v_output_price / 1000000.0);
END;
$$ LANGUAGE plpgsql STABLE;
```

### check_budget()

```sql
CREATE OR REPLACE FUNCTION processing_engine.check_budget(
    p_pipeline_id UUID
) RETURNS TABLE(current_cost REAL, budget_limit REAL, pct_used REAL, is_exceeded BOOLEAN) AS $$
DECLARE
    v_budget REAL;
    v_period TEXT;
    v_start TIMESTAMPTZ;
    v_cost REAL;
BEGIN
    SELECT p.budget_limit_usd, p.budget_period
    INTO v_budget, v_period
    FROM processing_engine.pipelines p
    WHERE p.id = p_pipeline_id;

    IF v_budget IS NULL THEN
        RETURN QUERY SELECT 0.0::REAL, NULL::REAL, 0.0::REAL, false;
        RETURN;
    END IF;

    v_start := CASE v_period
        WHEN 'day' THEN date_trunc('day', now())
        WHEN 'week' THEN date_trunc('week', now())
        WHEN 'month' THEN date_trunc('month', now())
        ELSE date_trunc('month', now())
    END;

    SELECT COALESCE(SUM(l.cost_usd), 0.0)
    INTO v_cost
    FROM processing_engine.llm_call_log l
    WHERE l.pipeline_id = p_pipeline_id
      AND l.created_at >= v_start
      AND l.status = 'success';

    RETURN QUERY SELECT v_cost, v_budget, (v_cost / v_budget * 100.0), (v_cost >= v_budget);
END;
$$ LANGUAGE plpgsql STABLE;
```

## Entity Relationship Diagram

```
pipelines 1──────N jobs 1──────N items
    │                │              │
    │                │              │── N processing_logs
    │                │              │
    │                │              │── N llm_call_log
    │                │
    │                └── N llm_call_log (denormalized)
    │
    └── N cache_entries

model_pricing (standalone reference table)
```

## Migration Strategy

All migrations managed via Alembic:
1. `001_create_schema.py` — CREATE SCHEMA processing_engine, CREATE EXTENSION pgvector
2. `002_create_enums.py` — all 5 ENUMs
3. `003_create_pipelines.py` — pipelines table + indexes
4. `004_create_jobs.py` — jobs table + indexes
5. `005_create_items.py` — items table + pgvector index
6. `006_create_processing_logs.py` — processing_logs table + indexes
7. `007_create_cache.py` — cache_entries table + indexes
8. `008_create_llm_call_log.py` — llm_call_log table + indexes
9. `009_create_model_pricing.py` — model_pricing table + seed data
10. `010_create_functions.py` — calculate_call_cost, check_budget functions
