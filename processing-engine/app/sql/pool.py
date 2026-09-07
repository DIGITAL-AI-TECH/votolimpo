"""SQL queries for the Pool ingestion buffer."""

INSERT_POOL_ITEM = """
INSERT INTO processing_engine.pool (
    pipeline_id, source_url, content, content_type, metadata,
    url_hash, content_hash, status, priority, source_id, batch_ref
)
VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11)
RETURNING id
"""

CHECK_URL_HASH_EXISTS = """
SELECT id FROM processing_engine.pool
WHERE url_hash = $1 AND pipeline_id = $2 AND status != 'duplicate_rejected'
LIMIT 1
"""

CHECK_CONTENT_HASH_EXISTS = """
SELECT id FROM processing_engine.pool
WHERE content_hash = $1 AND pipeline_id = $2 AND status != 'duplicate_rejected'
LIMIT 1
"""

CLAIM_PENDING_ITEMS = """
WITH claimed AS (
    SELECT id FROM processing_engine.pool
    WHERE pipeline_id = $1 AND status = 'pending'
    ORDER BY priority DESC, created_at ASC
    LIMIT $2
    FOR UPDATE SKIP LOCKED
)
UPDATE processing_engine.pool p
SET status = 'claimed', claimed_at = now()
FROM claimed
WHERE p.id = claimed.id
RETURNING p.*
"""

UPDATE_POOL_JOB_ID = """
UPDATE processing_engine.pool
SET job_id = $2
WHERE id = $1
"""

UPDATE_POOL_STATUS_ERROR = """
UPDATE processing_engine.pool
SET status = 'error'
WHERE id = $1
"""

GET_POOL_STATUS = """
SELECT
    p.pipeline_id,
    pl.name AS pipeline_name,
    COUNT(*) AS pending,
    MIN(p.created_at) AS oldest_pending
FROM processing_engine.pool p
JOIN processing_engine.pipelines pl ON pl.id = p.pipeline_id
WHERE p.status = 'pending'
GROUP BY p.pipeline_id, pl.name
ORDER BY pending DESC
"""

GET_PENDING_PIPELINE_IDS = """
SELECT DISTINCT pipeline_id
FROM processing_engine.pool
WHERE status = 'pending'
"""

COUNT_PENDING_TOTAL = """
SELECT COUNT(*) FROM processing_engine.pool WHERE status = 'pending'
"""
