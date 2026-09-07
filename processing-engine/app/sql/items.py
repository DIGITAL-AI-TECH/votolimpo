INSERT_ITEM = """
INSERT INTO processing_engine.items (
    job_id, pipeline_id, source_url, content, content_type,
    status, metadata, url_hash, content_hash
)
VALUES ($1, $2, $3, $4, $5, 'pending', $6::jsonb, $7, $8)
RETURNING *
"""

SELECT_ITEMS_BY_JOB = """
SELECT * FROM processing_engine.items WHERE job_id = $1 ORDER BY created_at
"""

SELECT_ITEM_BY_ID = """
SELECT * FROM processing_engine.items WHERE id = $1
"""

UPDATE_ITEM_STATUS = """
UPDATE processing_engine.items SET status = $2 WHERE id = $1
"""

UPDATE_ITEM_RESULT = """
UPDATE processing_engine.items
SET status = 'completed',
    output = $2::jsonb,
    dedup_result = $3,
    cached = $4,
    prompt_tokens = $5,
    completion_tokens = $6,
    total_tokens = $7,
    cost_usd = $8,
    duration_ms = $9
WHERE id = $1
"""

UPDATE_ITEM_FAILED = """
UPDATE processing_engine.items
SET status = 'failed', error_message = $2, duration_ms = $3
WHERE id = $1
"""

CHECK_URL_HASH = """
SELECT id FROM processing_engine.items
WHERE url_hash = $1 AND pipeline_id = $2 AND status = 'completed'
LIMIT 1
"""

CHECK_CONTENT_HASH = """
SELECT id FROM processing_engine.items
WHERE content_hash = $1 AND pipeline_id = $2 AND status = 'completed'
LIMIT 1
"""

INSERT_PROCESSING_LOG = """
INSERT INTO processing_engine.processing_logs (item_id, step, status, duration_ms, error_message, metadata)
VALUES ($1, $2, $3, $4, $5, $6::jsonb)
RETURNING *
"""

SELECT_LOGS_BY_JOB = """
SELECT pl.*
FROM processing_engine.processing_logs pl
JOIN processing_engine.items i ON pl.item_id = i.id
WHERE i.job_id = $1
ORDER BY pl.created_at
"""

SELECT_LOGS_BY_JOB_AND_STEP = """
SELECT pl.*
FROM processing_engine.processing_logs pl
JOIN processing_engine.items i ON pl.item_id = i.id
WHERE i.job_id = $1 AND pl.step = $2
ORDER BY pl.created_at
"""
