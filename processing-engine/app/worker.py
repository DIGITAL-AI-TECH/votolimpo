from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg

from app.db import get_pool
from app.services.callback import CallbackService
from app.services.orchestrator import Orchestrator
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Inline SQL — keeps worker self-contained
_CLAIM_JOB = """
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

_SELECT_PIPELINE = "SELECT * FROM processing_engine.pipelines WHERE id = $1"

_SELECT_PENDING_ITEMS = """
SELECT * FROM processing_engine.items
WHERE job_id = $1 AND status = 'pending'
ORDER BY created_at
"""

_UPDATE_ITEM_RESULT = """
UPDATE processing_engine.items
SET status = 'completed', output = $2::jsonb, dedup_result = $3, cached = $4,
    prompt_tokens = $5, completion_tokens = $6, total_tokens = $7, cost_usd = $8, duration_ms = $9
WHERE id = $1
"""

_UPDATE_ITEM_FAILED = """
UPDATE processing_engine.items
SET status = 'failed', error_message = $2, duration_ms = $3
WHERE id = $1
"""

_INCREMENT_COMPLETED = (
    "UPDATE processing_engine.jobs SET items_completed = items_completed + 1 WHERE id = $1"
)
_INCREMENT_FAILED = (
    "UPDATE processing_engine.jobs SET items_failed = items_failed + 1 WHERE id = $1"
)

_FINALIZE_JOB = """
UPDATE processing_engine.jobs
SET status = $2, completed_at = now()
WHERE id = $1
"""

_SELECT_JOB = "SELECT * FROM processing_engine.jobs WHERE id = $1"


class Worker:
    """Background worker that claims queued jobs via SKIP LOCKED."""

    def __init__(self, poll_interval: float = 1.0) -> None:
        self.poll_interval = poll_interval
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("Worker started (poll_interval=%.1fs)", self.poll_interval)
        while self._running:
            try:
                claimed = await self._claim_and_process()
                if not claimed:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Worker cancelled — shutting down")
                break
            except Exception:
                logger.exception("Worker loop error")
                await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False

    async def _claim_and_process(self) -> bool:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Claim inside transaction
            job_record = await conn.fetchrow(_CLAIM_JOB)
            if job_record is None:
                return False

            job = dict(job_record)
            logger.info(
                "Claimed job %s (pipeline=%s, items=%d)",
                job["id"],
                job["pipeline_id"],
                job["items_total"],
            )

            try:
                await self._process_job(job, pool)
            except Exception:
                logger.exception("Failed to process job %s", job["id"])
                await conn.execute(_FINALIZE_JOB, job["id"], "failed")
            return True

    async def _process_job(self, job: dict[str, Any], pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            pipeline_record = await conn.fetchrow(_SELECT_PIPELINE, job["pipeline_id"])
            if pipeline_record is None:
                raise ValueError(f"Pipeline {job['pipeline_id']} not found")
            pipeline = dict(pipeline_record)

            items = await conn.fetch(_SELECT_PENDING_ITEMS, job["id"])

        if not items:
            async with pool.acquire() as conn:
                await conn.execute(_FINALIZE_JOB, job["id"], "completed")
            return

        orchestrator = Orchestrator()
        semaphore = asyncio.Semaphore(pipeline.get("max_concurrent", 5))
        rate_limiter = RateLimiter(rpm=pipeline.get("rate_limit_rpm", 60))

        async def process_one(item_record: asyncpg.Record) -> None:
            item = dict(item_record)
            async with semaphore:
                await rate_limiter.acquire()
                async with pool.acquire() as item_conn:
                    try:
                        result = await orchestrator.process_item(
                            item_id=item["id"],
                            raw_content=item.get("content") or item.get("raw_content") or "",
                            source_url=item.get("source_url"),
                            content_type=item.get("content_type", "text/plain"),
                            pipeline=pipeline,
                            conn=item_conn,
                            skip_dedup=job.get("skip_dedup", False),
                            skip_cache=job.get("skip_cache", False),
                            dry_run=job.get("dry_run", False),
                            override_model=job.get("override_model"),
                            job_id=job["id"],
                        )
                        await item_conn.execute(
                            _UPDATE_ITEM_RESULT,
                            item["id"],
                            json.dumps(result.get("output")),
                            result.get("dedup_result", "new"),
                            result.get("cached", False),
                            result.get("prompt_tokens", 0),
                            result.get("completion_tokens", 0),
                            result.get("total_tokens", 0),
                            result.get("cost_usd", 0.0),
                            result.get("duration_ms", 0),
                        )
                    except Exception as e:
                        logger.error("Item %s failed: %s", item["id"], e)
                        await item_conn.execute(
                            _UPDATE_ITEM_FAILED,
                            item["id"],
                            str(e)[:1000],
                            0,
                        )

                # Update job counters outside item_conn context
                async with pool.acquire() as counter_conn:
                    if item.get("status_after") == "failed":
                        pass  # handled below
                    # Check item final status
                    updated_item = await counter_conn.fetchrow(
                        "SELECT status FROM processing_engine.items WHERE id = $1", item["id"]
                    )
                    if updated_item and updated_item["status"] in ("completed", "duplicate"):
                        await counter_conn.execute(_INCREMENT_COMPLETED, job["id"])
                    else:
                        await counter_conn.execute(_INCREMENT_FAILED, job["id"])

        await asyncio.gather(*[process_one(item) for item in items], return_exceptions=True)

        # Determine final job status
        async with pool.acquire() as conn:
            updated_job = await conn.fetchrow(_SELECT_JOB, job["id"])
            if updated_job is None:
                return
            uj = dict(updated_job)
            if uj["items_failed"] == 0:
                final_status = "completed"
            elif uj["items_completed"] == 0:
                final_status = "failed"
            else:
                final_status = "partial"
            await conn.execute(_FINALIZE_JOB, job["id"], final_status)
            logger.info(
                "Job %s finished: %s (completed=%d, failed=%d)",
                job["id"],
                final_status,
                uj["items_completed"],
                uj["items_failed"],
            )

        # Send callback if configured
        callback_url = job.get("callback_url")
        if callback_url:
            callback = CallbackService()
            await callback.send(
                callback_url,
                {
                    "job_id": str(job["id"]),
                    "status": final_status,
                    "items_completed": uj["items_completed"],
                    "items_failed": uj["items_failed"],
                    "items_total": uj["items_total"],
                },
            )
