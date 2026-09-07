from __future__ import annotations

# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

INSERT_PIPELINE = """
INSERT INTO processing_engine.pipelines (
    name,
    description,
    ingestor_type,
    max_content_chars,
    dedup_strategy,
    dedup_threshold,
    llm_provider,
    llm_model,
    llm_temperature,
    llm_seed,
    llm_max_tokens,
    system_prompt,
    output_schema,
    validators,
    sink_type,
    sink_config,
    max_concurrent,
    rate_limit_rpm,
    budget_limit_usd,
    budget_period,
    max_retries,
    retry_backoff_base,
    cache_ttl_hours
)
VALUES (
    $1,  -- name
    $2,  -- description
    $3,  -- ingestor_type
    $4,  -- max_content_chars
    $5,  -- dedup_strategy
    $6,  -- dedup_threshold
    $7,  -- llm_provider
    $8,  -- llm_model
    $9,  -- llm_temperature
    $10, -- llm_seed
    $11, -- llm_max_tokens
    $12, -- system_prompt
    $13::jsonb, -- output_schema
    $14, -- validators (TEXT[])
    $15, -- sink_type
    $16::jsonb, -- sink_config
    $17, -- max_concurrent
    $18, -- rate_limit_rpm
    $19, -- budget_limit_usd
    $20, -- budget_period
    $21, -- max_retries
    $22, -- retry_backoff_base
    $23  -- cache_ttl_hours
)
RETURNING *
"""

# ---------------------------------------------------------------------------
# SELECT
# ---------------------------------------------------------------------------

SELECT_PIPELINE_BY_ID = """
SELECT *
FROM processing_engine.pipelines
WHERE id = $1
"""

SELECT_ALL_PIPELINES = """
SELECT *
FROM processing_engine.pipelines
WHERE ($1::boolean IS NULL OR is_active = $1)
ORDER BY created_at DESC
"""

# ---------------------------------------------------------------------------
# UPDATE  (version auto-incrementa, updated_at atualizado)
# ---------------------------------------------------------------------------

UPDATE_PIPELINE = """
UPDATE processing_engine.pipelines
SET
    name               = $2,
    description        = $3,
    ingestor_type      = $4,
    max_content_chars  = $5,
    dedup_strategy     = $6,
    dedup_threshold    = $7,
    llm_provider       = $8,
    llm_model          = $9,
    llm_temperature    = $10,
    llm_seed           = $11,
    llm_max_tokens     = $12,
    system_prompt      = $13,
    output_schema      = $14::jsonb,
    validators         = $15,
    sink_type          = $16,
    sink_config        = $17::jsonb,
    max_concurrent     = $18,
    rate_limit_rpm     = $19,
    budget_limit_usd   = $20,
    budget_period      = $21,
    max_retries        = $22,
    retry_backoff_base = $23,
    cache_ttl_hours    = $24,
    version            = version + 1,
    updated_at         = now()
WHERE id = $1
RETURNING *
"""

# ---------------------------------------------------------------------------
# UNIQUENESS CHECK  (exclui o próprio registro no UPDATE)
# ---------------------------------------------------------------------------

CHECK_NAME_UNIQUE = """
SELECT EXISTS(
    SELECT 1
    FROM processing_engine.pipelines
    WHERE name = $1
      AND id != $2
)
"""
