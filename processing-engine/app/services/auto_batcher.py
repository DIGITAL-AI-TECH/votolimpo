"""Auto-Batcher: background service that consumes pool items and creates jobs.

Polls the pool table for pending items, claims them with SKIP LOCKED,
and creates one job per item (v1: 1:1 granularity).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import asyncpg

from app.sql.items import INSERT_ITEM
from app.sql.jobs import INSERT_JOB
from app.sql.pipelines import SELECT_PIPELINE_BY_ID
from app.sql.pool import (
    CLAIM_PENDING_ITEMS,
    GET_PENDING_PIPELINE_IDS,
    UPDATE_POOL_JOB_ID,
    UPDATE_POOL_STATUS_ERROR,
)

logger = logging.getLogger(__name__)


class AutoBatcher:
    """Background task that converts pool items into jobs."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        poll_interval: int = 5,
        batch_size: int = 50,
    ) -> None:
        self._pool = pool
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the batcher loop as a background task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="auto-batcher")
        logger.info(
            "Auto-Batcher started (interval=%ds, batch_size=%d)",
            self._poll_interval,
            self._batch_size,
        )

    async def stop(self) -> None:
        """Stop the batcher gracefully."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Auto-Batcher stopped")

    async def _run_loop(self) -> None:
        """Main loop: batch cycle + sleep."""
        while self._running:
            try:
                await self._batch_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Auto-Batcher cycle error")
            await asyncio.sleep(self._poll_interval)

    async def _batch_cycle(self) -> None:
        """One cycle: find pipelines with pending items, claim and create jobs."""
        async with self._pool.acquire() as conn:
            pipeline_ids = await conn.fetch(GET_PENDING_PIPELINE_IDS)

        for row in pipeline_ids:
            pipeline_id = row["pipeline_id"]
            try:
                created = await self._claim_and_create_jobs(pipeline_id)
                if created > 0:
                    logger.info(
                        "Auto-Batcher: created %d jobs for pipeline %s",
                        created,
                        pipeline_id,
                    )
            except Exception:
                logger.exception(
                    "Auto-Batcher: error processing pipeline %s", pipeline_id
                )

    async def _claim_and_create_jobs(self, pipeline_id) -> int:
        """Claim pending items and create one job per item."""
        async with self._pool.acquire() as conn:
            # Get pipeline info
            pipeline = await conn.fetchrow(SELECT_PIPELINE_BY_ID, pipeline_id)
            if pipeline is None:
                logger.warning(
                    "Auto-Batcher: pipeline %s not found, marking items as error",
                    pipeline_id,
                )
                # Mark all pending items for this pipeline as error
                claimed = await conn.fetch(
                    CLAIM_PENDING_ITEMS, pipeline_id, self._batch_size
                )
                for item in claimed:
                    await conn.execute(UPDATE_POOL_STATUS_ERROR, item["id"])
                return 0

            pipeline_version = pipeline["version"]
            claimed_items = await conn.fetch(
                CLAIM_PENDING_ITEMS, pipeline_id, self._batch_size
            )

            if not claimed_items:
                return 0

            jobs_created = 0
            for pool_item in claimed_items:
                async with conn.transaction():
                    # Create job (1:1 granularity)
                    job_record = await conn.fetchrow(
                        INSERT_JOB,
                        pipeline_id,                    # $1 pipeline_id
                        pipeline_version,               # $2 pipeline_version
                        1,                              # $3 items_total
                        None,                           # $4 idempotency_key
                        pool_item["priority"],          # $5 priority
                        None,                           # $6 metadata
                        None,                           # $7 override_model
                        False,                          # $8 skip_dedup
                        False,                          # $9 skip_cache
                        False,                          # $10 dry_run
                        None,                           # $11 callback_url
                    )
                    job_id = job_record["id"]

                    # Create item in items table
                    metadata_str = pool_item["metadata"]
                    if isinstance(metadata_str, dict):
                        metadata_str = json.dumps(metadata_str)
                    elif metadata_str is None:
                        metadata_str = None

                    await conn.execute(
                        INSERT_ITEM,
                        job_id,                         # $1 job_id
                        pipeline_id,                    # $2 pipeline_id
                        pool_item["source_url"],        # $3 source_url
                        pool_item["content"],           # $4 content
                        pool_item["content_type"],      # $5 content_type
                        metadata_str,                   # $6 metadata
                        pool_item["url_hash"],          # $7 url_hash
                        pool_item["content_hash"],      # $8 content_hash
                    )

                    # Link pool item to job
                    await conn.execute(UPDATE_POOL_JOB_ID, pool_item["id"], job_id)

                    jobs_created += 1

            return jobs_created
