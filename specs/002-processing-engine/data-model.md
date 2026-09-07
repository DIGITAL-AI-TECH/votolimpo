# Data Model: Processing Engine

**Feature**: Processing Engine (002-processing-engine)
**Date**: 2026-09-06
**Schema**: `processing_engine` (isolated from project schemas)

---

## Entity Relationship Diagram

```
pipelines 1──N jobs 1──N job_items 1──N processing_logs
    │                      │
    │                      │ 1──0..1 cache_entries
    │                      │
    └── pipeline_versions ─┘ (job references version)
```

---

## Entities

### 1. pipelines

Registered pipeline configurations. Each project defines 1+ pipelines.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PK | Slug identifier (e.g., "votolimpo-article-extraction") |
| name | TEXT | NOT NULL | Human-readable name |
| description | TEXT | | Optional description |
| current_version | INT | NOT NULL DEFAULT 1 | Latest version number |
| config | JSONB | NOT NULL | Full pipeline configuration (validated Pydantic model) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Last update timestamp |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | Soft-disable without deleting |

**Indexes**: PK on `id`

---

### 2. pipeline_versions

Versioned snapshots of pipeline config. Jobs reference the version active at submission time (FR-016).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Unique version ID |
| pipeline_id | TEXT | FK → pipelines.id, NOT NULL | Parent pipeline |
| version | INT | NOT NULL | Version number |
| config | JSONB | NOT NULL | Frozen config snapshot |
| system_prompt | TEXT | | Resolved system prompt content |
| output_schema | JSONB | | Resolved JSON Schema for LLM output |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | When this version was created |

**Indexes**: UNIQUE on `(pipeline_id, version)`

---

### 3. jobs

Processing jobs submitted via API. Lifecycle: queued → running → completed/failed/partial.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Job ID returned to caller |
| pipeline_id | TEXT | FK → pipelines.id, NOT NULL | Which pipeline to use |
| pipeline_version_id | UUID | FK → pipeline_versions.id, NOT NULL | Frozen version at submission |
| status | job_status ENUM | NOT NULL DEFAULT 'queued' | queued/running/completed/failed/partial |
| priority | job_priority ENUM | NOT NULL DEFAULT 'normal' | low/normal/high/critical |
| items_total | INT | NOT NULL DEFAULT 0 | Total items in job |
| items_completed | INT | NOT NULL DEFAULT 0 | Successfully processed |
| items_failed | INT | NOT NULL DEFAULT 0 | Failed items |
| callback_url | TEXT | | Webhook URL for completion notification |
| idempotency_key | TEXT | UNIQUE | Prevents duplicate job submission (FR-015) |
| llm_override | JSONB | | Per-job LLM overrides (model, temperature) |
| skip_dedup | BOOLEAN | NOT NULL DEFAULT FALSE | Bypass dedup for this job |
| skip_cache | BOOLEAN | NOT NULL DEFAULT FALSE | Bypass cache for this job |
| dry_run | BOOLEAN | NOT NULL DEFAULT FALSE | Validate without persisting |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | Submission time |
| started_at | TIMESTAMPTZ | | When processing began |
| completed_at | TIMESTAMPTZ | | When processing finished |
| claimed_at | TIMESTAMPTZ | | When worker claimed the job (SKIP LOCKED) |
| error_message | TEXT | | Top-level error if job failed |
| metadata | JSONB | NOT NULL DEFAULT '{}' | Free-form metadata from caller |

**Indexes**:
- PK on `id`
- UNIQUE on `idempotency_key` (WHERE idempotency_key IS NOT NULL)
- `idx_jobs_status_priority` on `(status, priority DESC, created_at)` — for SKIP LOCKED polling
- `idx_jobs_pipeline` on `(pipeline_id)`

**ENUMs**:
```sql
CREATE TYPE job_status AS ENUM ('queued', 'running', 'completed', 'failed', 'partial');
CREATE TYPE job_priority AS ENUM ('low', 'normal', 'high', 'critical');
```

---

### 4. job_items

Individual items within a job. Atomic processing unit.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Item ID |
| job_id | UUID | FK → jobs.id ON DELETE CASCADE, NOT NULL | Parent job |
| status | item_status ENUM | NOT NULL DEFAULT 'pending' | pending/processing/completed/failed/skipped |
| content | TEXT | NOT NULL | Raw content (text, HTML, etc.) |
| content_type | TEXT | NOT NULL DEFAULT 'text/plain' | MIME type |
| content_hash | TEXT | | SHA-256 of normalized content |
| source_url | TEXT | | Origin URL |
| url_hash | TEXT | | SHA-256 of canonical URL |
| output | JSONB | | Structured LLM output (after validation) |
| validation_result | JSONB | | Validation details (pass/fail per validator) |
| dedup_result | dedup_result ENUM | | new/duplicate/similar/cached |
| dedup_matched_id | UUID | | ID of the matched duplicate item |
| usage | JSONB | | Token usage: {prompt_tokens, completion_tokens, total_tokens} |
| cost_usd | NUMERIC(10,6) | NOT NULL DEFAULT 0 | Estimated cost for this item |
| duration_ms | INT | NOT NULL DEFAULT 0 | Total processing time |
| error_message | TEXT | | Error details if failed |
| retry_count | INT | NOT NULL DEFAULT 0 | Number of retries attempted |
| cached | BOOLEAN | NOT NULL DEFAULT FALSE | Whether result came from cache |
| metadata | JSONB | NOT NULL DEFAULT '{}' | Free-form metadata from caller |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| processed_at | TIMESTAMPTZ | | When processing completed |

**Indexes**:
- PK on `id`
- `idx_job_items_job` on `(job_id)`
- `idx_job_items_content_hash` on `(content_hash)` — for cache/dedup lookup
- `idx_job_items_url_hash` on `(url_hash)` — for URL dedup
- `idx_job_items_status` on `(job_id, status)` — for progress counting

**ENUMs**:
```sql
CREATE TYPE item_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'skipped');
CREATE TYPE dedup_result AS ENUM ('new', 'duplicate', 'similar', 'cached');
```

---

### 5. processing_logs

Audit trail for every step of every item. One row per (item, step).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Log entry ID |
| job_id | UUID | FK → jobs.id ON DELETE CASCADE, NOT NULL | Parent job |
| item_id | UUID | FK → job_items.id ON DELETE CASCADE, NOT NULL | Parent item |
| step | processing_step ENUM | NOT NULL | ingest/dedup/cache_check/process/validate/persist |
| status | TEXT | NOT NULL | success/failed/skipped |
| duration_ms | INT | NOT NULL DEFAULT 0 | Step duration |
| model_used | TEXT | | LLM model (only for 'process' step) |
| prompt_tokens | INT | | Input tokens (only for 'process' step) |
| completion_tokens | INT | | Output tokens (only for 'process' step) |
| cost_usd | NUMERIC(10,6) | NOT NULL DEFAULT 0 | Step cost |
| error_message | TEXT | | Error details if failed |
| metadata | JSONB | NOT NULL DEFAULT '{}' | Step-specific metadata |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Indexes**:
- PK on `id`
- `idx_logs_job_item` on `(job_id, item_id)`
- `idx_logs_step` on `(step, created_at)` — for stats queries

**ENUMs**:
```sql
CREATE TYPE processing_step AS ENUM ('ingest', 'dedup', 'cache_check', 'process', 'validate', 'persist');
```

---

### 6. cache_entries

Cached LLM results indexed by content_hash. Avoids reprocessing identical content (FR-010).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | Cache entry ID |
| pipeline_id | TEXT | FK → pipelines.id, NOT NULL | Scoped to pipeline |
| content_hash | TEXT | NOT NULL | SHA-256 of normalized content |
| output | JSONB | NOT NULL | Cached LLM output |
| model_used | TEXT | NOT NULL | Model that generated this output |
| prompt_tokens | INT | | Original token count |
| completion_tokens | INT | | Original token count |
| original_cost_usd | NUMERIC(10,6) | NOT NULL DEFAULT 0 | Cost of original processing |
| hit_count | INT | NOT NULL DEFAULT 0 | Times this cache entry was used |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| expires_at | TIMESTAMPTZ | NOT NULL | created_at + TTL from pipeline config |

**Indexes**:
- PK on `id`
- UNIQUE on `(pipeline_id, content_hash)`
- `idx_cache_expires` on `(expires_at)` — for cleanup job

---

### 7. embeddings (for semantic dedup)

Vector embeddings for semantic dedup via pgvector. Only populated when pipeline uses semantic dedup strategy.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| pipeline_id | TEXT | FK → pipelines.id, NOT NULL | Scoped to pipeline |
| content_hash | TEXT | NOT NULL | Links to source content |
| embedding | vector(1536) | NOT NULL | text-embedding-3-small output |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Indexes**:
- PK on `id`
- UNIQUE on `(pipeline_id, content_hash)`
- `idx_embeddings_ivfflat` on `embedding` using ivfflat (lists = 100) with cosine distance — for semantic similarity search

---

## State Transitions

### Job Status

```
queued ──(worker claims)──→ running ──→ completed (all items OK)
                                   ──→ partial   (some items failed)
                                   ──→ failed    (all items failed OR critical error)
```

### Item Status

```
pending ──(processing starts)──→ processing ──→ completed (output valid + persisted)
                                             ──→ failed    (max retries exceeded)
                                             ──→ skipped   (dedup hit: duplicate/similar/cached)
```

---

## SQL Migration (initial)

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";      -- pgvector

-- Schema
CREATE SCHEMA IF NOT EXISTS processing_engine;
SET search_path TO processing_engine, public;

-- ENUMs
CREATE TYPE job_status AS ENUM ('queued', 'running', 'completed', 'failed', 'partial');
CREATE TYPE job_priority AS ENUM ('low', 'normal', 'high', 'critical');
CREATE TYPE item_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'skipped');
CREATE TYPE dedup_result AS ENUM ('new', 'duplicate', 'similar', 'cached');
CREATE TYPE processing_step AS ENUM ('ingest', 'dedup', 'cache_check', 'process', 'validate', 'persist');

-- Tables created in order above (pipelines → pipeline_versions → jobs → job_items → processing_logs → cache_entries → embeddings)
```

---

## Validation Rules (from spec)

| Entity | Rule | Source |
|--------|------|--------|
| jobs | idempotency_key must be unique when present | FR-015 |
| jobs | callback_url must be valid HTTP(S) URL when present | FR-013 |
| job_items | content must not be empty | FR-001 |
| job_items | content_type must be valid MIME type | FR-001 |
| job_items | cost_usd >= 0 | Implicit |
| cache_entries | expires_at > created_at | FR-010 |
| processing_logs | cost_usd >= 0 | FR-008 |
| pipelines | config must validate against PipelineConfig Pydantic model | FR-003 |
