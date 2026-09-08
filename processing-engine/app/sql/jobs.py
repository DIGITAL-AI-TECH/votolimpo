INSERT_JOB = """
INSERT INTO processing_engine.jobs (
    pipeline_id, pipeline_version, status, items_total,
    idempotency_key, priority, metadata,
    override_model, skip_dedup, skip_cache, dry_run, callback_url
)
VALUES ($1, $2, 'queued', $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11)
RETURNING *
"""

CHECK_IDEMPOTENCY = """
SELECT id FROM processing_engine.jobs
WHERE idempotency_key = $1
LIMIT 1
"""

SELECT_JOB_BY_ID = """
SELECT * FROM processing_engine.jobs WHERE id = $1
"""

SELECT_JOBS = """
SELECT * FROM processing_engine.jobs
WHERE ($1::uuid IS NULL OR pipeline_id = $1)
  AND ($2::text IS NULL OR status::text = $2)
ORDER BY priority DESC, created_at ASC
LIMIT $3 OFFSET $4
"""

COUNT_JOBS = """
SELECT COUNT(*) FROM processing_engine.jobs
WHERE ($1::uuid IS NULL OR pipeline_id = $1)
  AND ($2::text IS NULL OR status::text = $2)
"""

CLAIM_JOB = """
WITH claimed AS (
    SELECT id FROM processing_engine.jobs
    WHERE status = 'queued'
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE processing_engine.jobs j
SET status = 'running', started_at = now()
FROM claimed
WHERE j.id = claimed.id
RETURNING j.*
"""

UPDATE_JOB_STATUS = """
UPDATE processing_engine.jobs
SET status = $2, error_message = $3, completed_at = now()
WHERE id = $1
"""

INCREMENT_ITEMS_COMPLETED = """
UPDATE processing_engine.jobs SET items_completed = items_completed + 1 WHERE id = $1
"""

INCREMENT_ITEMS_FAILED = """
UPDATE processing_engine.jobs SET items_failed = items_failed + 1 WHERE id = $1
"""
