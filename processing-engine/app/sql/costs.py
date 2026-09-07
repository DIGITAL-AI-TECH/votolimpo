from __future__ import annotations

# ---------------------------------------------------------------------------
# LLM Call Log
# ---------------------------------------------------------------------------

INSERT_LLM_CALL = """
INSERT INTO processing_engine.llm_call_log (
    item_id, job_id, pipeline_id,
    provider, model, call_type,
    prompt_tokens, completion_tokens, total_tokens,
    cost_usd, latency_ms, status, error_message,
    is_retry, retry_number
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
RETURNING *
"""

# ---------------------------------------------------------------------------
# Cost Aggregation Queries
# ---------------------------------------------------------------------------

SELECT_COSTS_BY_PIPELINE = """
SELECT
    p.name AS label,
    COUNT(*) AS total_calls,
    COALESCE(SUM(l.prompt_tokens), 0) AS prompt_tokens,
    COALESCE(SUM(l.completion_tokens), 0) AS completion_tokens,
    COALESCE(SUM(l.total_tokens), 0) AS total_tokens,
    COALESCE(SUM(l.cost_usd), 0) AS total_cost_usd
FROM processing_engine.llm_call_log l
JOIN processing_engine.pipelines p ON l.pipeline_id = p.id
WHERE ($1::uuid IS NULL OR l.pipeline_id = $1)
  AND ($2::uuid IS NULL OR l.job_id = $2)
  AND l.created_at >= $3
  AND l.created_at < $4
  AND l.status = 'success'
GROUP BY p.name
ORDER BY total_cost_usd DESC
"""

SELECT_COSTS_BY_MODEL = """
SELECT
    l.model AS label,
    COUNT(*) AS total_calls,
    COALESCE(SUM(l.prompt_tokens), 0) AS prompt_tokens,
    COALESCE(SUM(l.completion_tokens), 0) AS completion_tokens,
    COALESCE(SUM(l.total_tokens), 0) AS total_tokens,
    COALESCE(SUM(l.cost_usd), 0) AS total_cost_usd
FROM processing_engine.llm_call_log l
WHERE ($1::uuid IS NULL OR l.pipeline_id = $1)
  AND ($2::uuid IS NULL OR l.job_id = $2)
  AND l.created_at >= $3
  AND l.created_at < $4
  AND l.status = 'success'
GROUP BY l.model
ORDER BY total_cost_usd DESC
"""

SELECT_COSTS_BY_DAY = """
SELECT
    TO_CHAR(date_trunc('day', l.created_at), 'YYYY-MM-DD') AS label,
    COUNT(*) AS total_calls,
    COALESCE(SUM(l.prompt_tokens), 0) AS prompt_tokens,
    COALESCE(SUM(l.completion_tokens), 0) AS completion_tokens,
    COALESCE(SUM(l.total_tokens), 0) AS total_tokens,
    COALESCE(SUM(l.cost_usd), 0) AS total_cost_usd
FROM processing_engine.llm_call_log l
WHERE ($1::uuid IS NULL OR l.pipeline_id = $1)
  AND ($2::uuid IS NULL OR l.job_id = $2)
  AND l.created_at >= $3
  AND l.created_at < $4
  AND l.status = 'success'
GROUP BY date_trunc('day', l.created_at)
ORDER BY label
"""

SELECT_COSTS_TOTAL = """
SELECT
    COUNT(*) AS total_calls,
    COALESCE(SUM(l.prompt_tokens), 0) AS prompt_tokens,
    COALESCE(SUM(l.completion_tokens), 0) AS completion_tokens,
    COALESCE(SUM(l.total_tokens), 0) AS total_tokens,
    COALESCE(SUM(l.cost_usd), 0) AS total_cost_usd
FROM processing_engine.llm_call_log l
WHERE ($1::uuid IS NULL OR l.pipeline_id = $1)
  AND ($2::uuid IS NULL OR l.job_id = $2)
  AND l.created_at >= $3
  AND l.created_at < $4
  AND l.status = 'success'
"""

# ---------------------------------------------------------------------------
# Budget Check (uses DB function)
# ---------------------------------------------------------------------------

CHECK_BUDGET = """
SELECT * FROM processing_engine.check_budget($1)
"""

# ---------------------------------------------------------------------------
# Model Pricing
# ---------------------------------------------------------------------------

SELECT_ALL_PRICING = """
SELECT * FROM processing_engine.model_pricing
WHERE ($1::boolean IS NULL OR is_active = $1)
ORDER BY provider, model
"""

SELECT_PRICING_BY_PROVIDER_MODEL = """
SELECT * FROM processing_engine.model_pricing
WHERE provider = $1 AND model = $2 AND is_active = true
LIMIT 1
"""

UPSERT_PRICING = """
INSERT INTO processing_engine.model_pricing (
    provider, model, input_price_per_million_tokens,
    output_price_per_million_tokens, is_active, effective_from
)
VALUES ($1, $2, $3, $4, $5, COALESCE($6, CURRENT_DATE))
ON CONFLICT (provider, model) WHERE is_active = true
DO UPDATE SET
    input_price_per_million_tokens = EXCLUDED.input_price_per_million_tokens,
    output_price_per_million_tokens = EXCLUDED.output_price_per_million_tokens,
    effective_from = EXCLUDED.effective_from,
    updated_at = now()
RETURNING *
"""
