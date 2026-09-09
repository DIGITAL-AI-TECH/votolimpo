"""Pipeline orchestrator — SKIP LOCKED job processing."""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..storage.database import get_pool
from ..plugins.ingestors import get_ingestor
from ..plugins.dedup import get_dedup
from ..plugins.llm import get_llm_provider, load_system_prompt, load_output_schema
from ..plugins.validators import get_validator
from ..plugins.sinks import get_sink
from .pipeline_config import get_pipeline, PipelineConfig
from .models import JobStatus

logger = logging.getLogger(__name__)


async def submit_job(job_data: dict) -> str:
    """Submit a new processing job. Returns job_id."""
    pool = await get_pool()
    job_id = job_data["job_id"]
    pipeline_id = job_data["pipeline_id"]
    items = job_data["items"]
    priority = job_data.get("priority", "normal")
    callback_url = job_data.get("callback_url")
    idempotency_key = job_data.get("idempotency_key")

    async with pool.acquire() as conn:
        # Idempotency check
        if idempotency_key:
            row = await conn.fetchrow(
                "SELECT id FROM processing_engine.jobs WHERE idempotency_key = $1",
                idempotency_key,
            )
            if row:
                return row["id"]

        await conn.execute("""
            INSERT INTO processing_engine.jobs
                (id, pipeline_id, status, priority, total_items, callback_url, idempotency_key)
            VALUES ($1, $2, 'pending', $3, $4, $5, $6)
        """, job_id, pipeline_id, priority, len(items), callback_url, idempotency_key)

        for item in items:
            await conn.execute("""
                INSERT INTO processing_engine.job_items
                    (id, job_id, content, content_type, source_url, metadata, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending')
            """, item["item_id"], job_id, item["content"],
                item.get("content_type", "text/plain"),
                item.get("source_url"),
                json.dumps(item.get("metadata", {})))

    logger.info("Job submitted: %s (%d items)", job_id, len(items))
    return job_id


async def process_next_job():
    """Pick and process the next pending job using SKIP LOCKED."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        # SKIP LOCKED: pick one pending job
        row = await conn.fetchrow("""
            UPDATE processing_engine.jobs
            SET status = 'processing', started_at = NOW(), updated_at = NOW()
            WHERE id = (
                SELECT id FROM processing_engine.jobs
                WHERE status = 'pending'
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, pipeline_id
        """)

        if not row:
            return None

        job_id = row["id"]
        pipeline_id = row["pipeline_id"]

    logger.info("Processing job: %s (pipeline: %s)", job_id, pipeline_id)

    pipeline = get_pipeline(pipeline_id)
    if not pipeline:
        await _fail_job(job_id, f"Pipeline not found: {pipeline_id}")
        return job_id

    # Process all items
    await _process_job_items(job_id, pipeline)
    return job_id


async def _process_job_items(job_id: str, pipeline: PipelineConfig):
    """Process all items in a job through the pipeline."""
    pool = await get_pool()

    async with pool.acquire() as conn:
        items = await conn.fetch(
            "SELECT * FROM processing_engine.job_items WHERE job_id = $1 ORDER BY created_at",
            job_id,
        )

    ingestor = get_ingestor(pipeline.ingestor.type)
    dedup = get_dedup(pipeline.dedup.strategy)
    llm = get_llm_provider(pipeline.llm.provider)
    validators = [(v.type, get_validator(v.type), v.config) for v in pipeline.validators]
    sink = get_sink(pipeline.sink.type)

    # Load prompts and schema
    system_prompt = ""
    output_schema = None
    if pipeline.llm.system_prompt_file:
        try:
            system_prompt = load_system_prompt(pipeline.llm.system_prompt_file)
        except FileNotFoundError:
            logger.error("System prompt not found: %s", pipeline.llm.system_prompt_file)

    if pipeline.llm.output_schema_file:
        try:
            output_schema = load_output_schema(pipeline.llm.output_schema_file)
        except FileNotFoundError:
            logger.error("Output schema not found: %s", pipeline.llm.output_schema_file)

    completed = 0
    failed = 0
    total_cost = 0.0
    total_duration = 0

    for item in items:
        t0 = time.time()
        pool = await get_pool()

        try:
            async with pool.acquire() as conn:
                # Mark item as processing
                await conn.execute(
                    "UPDATE processing_engine.job_items SET status = 'processing', updated_at = NOW() WHERE id = $1",
                    item["id"],
                )

                # Step 1: Ingest
                clean_content = await ingestor.ingest(item["content"], pipeline.ingestor.config)

                # Step 2: Cache check
                content_hash = hashlib.sha256(clean_content.encode()).hexdigest()
                if pipeline.cache.enabled:
                    cached = await conn.fetchrow(
                        "SELECT output FROM processing_engine.cache WHERE content_hash = $1 AND pipeline_id = $2 AND expires_at > NOW()",
                        content_hash, pipeline.id,
                    )
                    if cached:
                        duration_ms = int((time.time() - t0) * 1000)
                        await conn.execute("""
                            UPDATE processing_engine.job_items
                            SET status = 'completed', output = $1, cached = true,
                                duration_ms = $2, updated_at = NOW()
                            WHERE id = $3
                        """, cached["output"], duration_ms, item["id"])

                        # Still persist cached output to sink
                        metadata = json.loads(item["metadata"]) if isinstance(item["metadata"], str) else (item["metadata"] or {})
                        metadata["source_url"] = item["source_url"]
                        await sink.persist(json.loads(cached["output"]), metadata, pipeline.sink.config, conn)

                        completed += 1
                        total_duration += duration_ms
                        await _log_step(conn, job_id, item["id"], "cache_hit", "completed", duration_ms=duration_ms)
                        continue

                # Step 3: Dedup
                dedup_result = await dedup.check(
                    clean_content, item["source_url"], pipeline.dedup.config, conn,
                )
                if dedup_result == "duplicate":
                    duration_ms = int((time.time() - t0) * 1000)
                    await conn.execute("""
                        UPDATE processing_engine.job_items
                        SET status = 'completed', dedup_result = 'duplicate',
                            duration_ms = $1, updated_at = NOW()
                        WHERE id = $2
                    """, duration_ms, item["id"])
                    completed += 1
                    total_duration += duration_ms
                    await _log_step(conn, job_id, item["id"], "dedup", "skipped", metadata={"result": "duplicate"})
                    continue

                # Step 4: LLM Process
                llm_config = {
                    "model": pipeline.llm.model,
                    "temperature": pipeline.llm.temperature,
                    "max_tokens": pipeline.llm.max_tokens,
                }
                llm_result = await llm.process(clean_content, system_prompt, output_schema, llm_config)
                output = llm_result["output"]
                cost_usd = llm_result["cost_usd"]
                total_cost += cost_usd

                await _log_step(conn, job_id, item["id"], "llm", "completed",
                                model=pipeline.llm.model,
                                prompt_tokens=llm_result["usage"].get("prompt_tokens"),
                                completion_tokens=llm_result["usage"].get("completion_tokens"),
                                cost_usd=cost_usd)

                # Step 5: Validate
                all_errors = []
                for v_type, validator, v_config in validators:
                    errors = validator.validate(output, clean_content, v_config)
                    all_errors.extend(errors)

                if all_errors:
                    # Retry once
                    if pipeline.llm.max_retries > 0:
                        await _log_step(conn, job_id, item["id"], "validation", "retry",
                                        metadata={"errors": all_errors})
                        llm_result = await llm.process(clean_content, system_prompt, output_schema, llm_config)
                        output = llm_result["output"]
                        total_cost += llm_result["cost_usd"]

                        all_errors = []
                        for v_type, validator, v_config in validators:
                            errors = validator.validate(output, clean_content, v_config)
                            all_errors.extend(errors)

                    if all_errors:
                        duration_ms = int((time.time() - t0) * 1000)
                        await conn.execute("""
                            UPDATE processing_engine.job_items
                            SET status = 'failed', validation_errors = $1,
                                cost_usd = $2, duration_ms = $3, updated_at = NOW()
                            WHERE id = $4
                        """, json.dumps(all_errors), cost_usd, duration_ms, item["id"])
                        failed += 1
                        total_duration += duration_ms
                        await _log_step(conn, job_id, item["id"], "validation", "failed",
                                        metadata={"errors": all_errors})
                        continue

                # Step 6: Persist via sink
                metadata = json.loads(item["metadata"]) if isinstance(item["metadata"], str) else (item["metadata"] or {})
                metadata["source_url"] = item["source_url"]
                persist_result = await sink.persist(output, metadata, pipeline.sink.config, conn)

                # Cache the result
                if pipeline.cache.enabled:
                    expires = datetime.now(timezone.utc) + timedelta(hours=pipeline.cache.ttl_hours)
                    await conn.execute("""
                        INSERT INTO processing_engine.cache (content_hash, pipeline_id, output, expires_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (content_hash) DO UPDATE SET output = EXCLUDED.output, expires_at = EXCLUDED.expires_at
                    """, content_hash, pipeline.id, json.dumps(output), expires)

                duration_ms = int((time.time() - t0) * 1000)
                await conn.execute("""
                    UPDATE processing_engine.job_items
                    SET status = 'completed', output = $1, dedup_result = $2,
                        usage = $3, cost_usd = $4, duration_ms = $5, updated_at = NOW()
                    WHERE id = $6
                """, json.dumps(output), dedup_result,
                    json.dumps(llm_result["usage"]), cost_usd, duration_ms, item["id"])

                completed += 1
                total_duration += duration_ms
                await _log_step(conn, job_id, item["id"], "persist", "completed",
                                duration_ms=duration_ms,
                                metadata={"tables": persist_result.get("tables_written", [])})

        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            logger.exception("Failed to process item %s", item["id"])
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE processing_engine.job_items
                    SET status = 'failed', error = $1, duration_ms = $2, updated_at = NOW()
                    WHERE id = $3
                """, str(e), duration_ms, item["id"])
                await _log_step(conn, job_id, item["id"], "error", "failed",
                                error_message=str(e), duration_ms=duration_ms)
            failed += 1
            total_duration += duration_ms

    # Finalize job
    status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE processing_engine.jobs
            SET status = $1, completed_items = $2, failed_items = $3,
                total_cost_usd = $4, total_duration_ms = $5,
                completed_at = NOW(), updated_at = NOW()
            WHERE id = $6
        """, status, completed, failed, total_cost, total_duration, job_id)

    logger.info("Job %s finished: status=%s, completed=%d, failed=%d, cost=$%.4f",
                job_id, status, completed, failed, total_cost)

    # Callback if configured
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT callback_url FROM processing_engine.jobs WHERE id = $1", job_id)
        if row and row["callback_url"]:
            await _send_callback(row["callback_url"], job_id, status)


async def _fail_job(job_id: str, error: str):
    """Mark a job as failed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE processing_engine.jobs
            SET status = 'failed', completed_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """, job_id)
    logger.error("Job %s failed: %s", job_id, error)


async def _log_step(
    conn, job_id: str, item_id: str | None, step: str, status: str, *,
    model: str | None = None, prompt_tokens: int | None = None,
    completion_tokens: int | None = None, cost_usd: float | None = None,
    duration_ms: int = 0, error_message: str | None = None,
    metadata: dict | None = None,
):
    """Insert a processing log entry."""
    await conn.execute("""
        INSERT INTO processing_engine.processing_logs
            (job_id, item_id, step, status, model_used,
             prompt_tokens, completion_tokens, cost_usd,
             duration_ms, error_message, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    """, job_id, item_id, step, status, model,
        prompt_tokens, completion_tokens, cost_usd,
        duration_ms, error_message, json.dumps(metadata or {}))


async def _send_callback(url: str, job_id: str, status: str):
    """Send callback webhook when job completes."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={"job_id": job_id, "status": status})
        logger.info("Callback sent: %s → %s", job_id, url)
    except Exception as e:
        logger.warning("Callback failed for job %s: %s", job_id, e)
