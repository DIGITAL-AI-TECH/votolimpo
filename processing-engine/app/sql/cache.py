from __future__ import annotations

SELECT_CACHE_HIT = """
SELECT output, prompt_tokens, completion_tokens, cost_usd, llm_model
FROM processing_engine.cache_entries
WHERE content_hash = $1 AND pipeline_id = $2 AND expires_at > now()
ORDER BY created_at DESC
LIMIT 1
"""

UPSERT_CACHE = """
INSERT INTO processing_engine.cache_entries (
    content_hash, pipeline_id, output, prompt_tokens, completion_tokens,
    cost_usd, llm_model, expires_at
)
VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, now() + make_interval(hours => $8))
ON CONFLICT (content_hash, pipeline_id)
DO UPDATE SET
    output = EXCLUDED.output,
    prompt_tokens = EXCLUDED.prompt_tokens,
    completion_tokens = EXCLUDED.completion_tokens,
    cost_usd = EXCLUDED.cost_usd,
    llm_model = EXCLUDED.llm_model,
    hit_count = processing_engine.cache_entries.hit_count + 1,
    expires_at = EXCLUDED.expires_at
RETURNING *
"""

INCREMENT_CACHE_HIT = """
UPDATE processing_engine.cache_entries
SET hit_count = hit_count + 1
WHERE content_hash = $1 AND pipeline_id = $2
"""

DELETE_EXPIRED_CACHE = """
DELETE FROM processing_engine.cache_entries WHERE expires_at < now()
"""
