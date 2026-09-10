from __future__ import annotations

SELECT_STATS = """
WITH job_stats AS (
    SELECT
        COUNT(*) AS total_jobs,
        COALESCE(SUM(total_items), 0) AS total_items,
        COALESCE(SUM(completed_items), 0) AS completed_items,
        COALESCE(SUM(failed_items), 0) AS failed_items
    FROM processing_engine.jobs
    WHERE ($1::uuid IS NULL OR pipeline_id = $1)
      AND created_at >= $2
      AND created_at < $3
),
item_stats AS (
    SELECT
        COUNT(*) FILTER (WHERE status = 'duplicate') AS items_duplicate,
        COUNT(*) FILTER (WHERE cached = true) AS items_cached,
        COALESCE(AVG(duration_ms) FILTER (WHERE status = 'completed'), 0) AS avg_duration_ms
    FROM processing_engine.job_items
    WHERE ($1::uuid IS NULL OR pipeline_id = $1)
      AND created_at >= $2
      AND created_at < $3
),
cost_stats AS (
    SELECT COALESCE(SUM(cost_usd), 0) AS total_cost_usd
    FROM processing_engine.llm_call_log
    WHERE ($1::uuid IS NULL OR pipeline_id = $1)
      AND created_at >= $2
      AND created_at < $3
      AND status = 'success'
)
SELECT
    js.total_jobs,
    js.total_items,
    js.completed_items,
    js.failed_items,
    ist.items_duplicate,
    ist.items_cached,
    ist.avg_duration_ms,
    cs.total_cost_usd,
    CASE WHEN js.total_items > 0
        THEN (js.completed_items::float / js.total_items * 100)
        ELSE 0.0
    END AS success_rate,
    CASE WHEN js.completed_items > 0
        THEN (ist.items_cached::float / js.completed_items * 100)
        ELSE 0.0
    END AS cache_hit_rate,
    CASE WHEN js.total_items > 0
        THEN (ist.items_duplicate::float / js.total_items * 100)
        ELSE 0.0
    END AS dedup_rate
FROM job_stats js, item_stats ist, cost_stats cs
"""
