"""Pipeline orchestrator — SKIP LOCKED job processing."""

import asyncio
import hashlib
import json
import logging
import time
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from urllib.parse import urlparse

from ..config import settings
from ..plugins.dedup import get_dedup
from ..plugins.ingestors import get_ingestor
from ..plugins.llm import get_llm_provider, load_output_schema, load_system_prompt
from ..plugins.post_processors import get_post_processor
from ..plugins.sinks import get_sink
from ..plugins.validators import get_validator
from ..storage.database import get_pool
from .pipeline_config import PipelineConfig, get_pipeline

logger = logging.getLogger(__name__)


async def submit_job(job_data: dict) -> str:
    """Submit a new processing job. Returns job_id."""
    pool = await get_pool()
    job_id = _uuid.UUID(job_data["job_id"])
    pipeline_id = _uuid.UUID(job_data["pipeline_id"])
    items = job_data["items"]
    raw_priority = job_data.get("priority", "normal")
    priority = (
        raw_priority.value if hasattr(raw_priority, "value") else str(raw_priority)
    )
    callback_url = job_data.get("callback_url")
    idempotency_key = job_data.get("idempotency_key")

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Idempotency check
            if idempotency_key:
                row = await conn.fetchrow(
                    "SELECT id FROM processing_engine.jobs WHERE idempotency_key = $1",
                    idempotency_key,
                )
                if row:
                    return str(row["id"])

            await conn.execute(
                """
                INSERT INTO processing_engine.jobs
                    (id, pipeline_id, status, priority, total_items, callback_url, idempotency_key)
                VALUES ($1, $2, 'pending', $3, $4, $5, $6)
            """,
                job_id,
                pipeline_id,
                priority,
                len(items),
                callback_url,
                idempotency_key,
            )

            for item in items:
                await conn.execute(
                    """
                    INSERT INTO processing_engine.job_items
                        (id, job_id, content, content_type, source_url, metadata, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                """,
                    _uuid.UUID(item["item_id"]),
                    job_id,
                    item["content"],
                    item.get("content_type", "text/plain"),
                    item.get("source_url"),
                    json.dumps(item.get("metadata", {})),
                )

    logger.info("Job submitted: %s (%d items)", job_id, len(items))
    return str(job_id)


async def process_next_job():
    """Pick and process the next pending job using SKIP LOCKED (C3 fix)."""
    pool = await get_pool()

    # Proper SKIP LOCKED: SELECT FOR UPDATE inside transaction, then UPDATE
    async with pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow("""
                SELECT id, pipeline_id FROM processing_engine.jobs
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
            """)

        if not row:
            return None

        await conn.execute(
            """
                UPDATE processing_engine.jobs
                SET status = 'processing', started_at = NOW(), updated_at = NOW()
                WHERE id = $1
            """,
            row["id"],
        )

    job_id = row["id"]  # UUID from DB
    pipeline_id = str(row["pipeline_id"])  # str for get_pipeline lookup

    logger.info("Processing job: %s (pipeline: %s)", job_id, pipeline_id)

    pipeline = get_pipeline(pipeline_id)
    if not pipeline:
        await _fail_job(job_id, f"Pipeline not found: {pipeline_id}")
        return job_id

    await _process_job_items(job_id, pipeline)
    return job_id


async def _process_job_items(job_id: str, pipeline: PipelineConfig):
    """Process all items through the pipeline (C2 fix: LLM outside pool.acquire)."""
    pool = await get_pool()

    # Fetch items (short acquire)
    async with pool.acquire() as conn:
        items = await conn.fetch(
            "SELECT * FROM processing_engine.job_items WHERE job_id = $1 ORDER BY created_at",
            job_id,
        )

    ingestor = get_ingestor(pipeline.ingestor.type)
    dedup = get_dedup(pipeline.dedup.strategy)
    llm = get_llm_provider(pipeline.llm.provider)
    validators = [
        (v.type, get_validator(v.type), v.config) for v in pipeline.validators
    ]
    post_processors = [
        (pp.type, get_post_processor(pp.type), pp.config)
        for pp in pipeline.post_processors
    ]
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

    # H3 fix: process items concurrently with semaphore
    sem = asyncio.Semaphore(settings.worker_concurrency)

    async def _process_one(item):
        async with sem:
            return await _process_single_item(
                item,
                job_id,
                pipeline,
                ingestor,
                dedup,
                llm,
                validators,
                post_processors,
                sink,
                system_prompt,
                output_schema,
                pool,
            )

    results = await asyncio.gather(*[_process_one(item) for item in items])
    for r in results:
        completed += r["completed"]
        failed += r["failed"]
        total_cost += r["cost"]
        total_duration += r["duration"]

    # Finalize job
    status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE processing_engine.jobs
            SET status = $1, completed_items = $2, failed_items = $3,
                total_cost_usd = $4, total_duration_ms = $5,
                completed_at = NOW(), updated_at = NOW()
            WHERE id = $6
        """,
            status,
            completed,
            failed,
            total_cost,
            total_duration,
            job_id,
        )

    logger.info(
        "Job %s finished: status=%s, completed=%d, failed=%d, cost=$%.4f",
        job_id,
        status,
        completed,
        failed,
        total_cost,
    )

    # Callback if configured
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT callback_url FROM processing_engine.jobs WHERE id = $1", job_id
        )
        if row and row["callback_url"]:
            await _send_callback(row["callback_url"], job_id, status)


async def _process_single_item(
    item,
    job_id,
    pipeline,
    ingestor,
    dedup,
    llm,
    validators,
    post_processors,
    sink,
    system_prompt,
    output_schema,
    pool,
) -> dict:
    """Process a single item through the pipeline. Returns stats dict.

    C2 fix: Each DB operation uses short-lived acquire/release.
    LLM call happens WITHOUT holding a connection.
    """
    t0 = time.time()
    item_id = item["id"]
    cost = 0.0

    try:
        # Mark as processing (short acquire)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE processing_engine.job_items SET status = 'processing', updated_at = NOW() WHERE id = $1",
                item_id,
            )

        # Step 1: Ingest (no DB needed)
        clean_content = await ingestor.ingest(item["content"], pipeline.ingestor.config)
        content_hash = hashlib.sha256(clean_content.encode()).hexdigest()

        # Step 2: Cache check (short acquire)
        if pipeline.cache.enabled:
            async with pool.acquire() as conn:
                cached = await conn.fetchrow(
                    "SELECT output FROM processing_engine.cache WHERE content_hash = $1 AND pipeline_id = $2 AND expires_at > NOW()",
                    content_hash,
                    pipeline.id,
                )
            if cached:
                duration_ms = int((time.time() - t0) * 1000)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE processing_engine.job_items
                        SET status = 'completed', output = $1, cached = true,
                            duration_ms = $2, updated_at = NOW()
                        WHERE id = $3
                    """,
                        cached["output"],
                        duration_ms,
                        item_id,
                    )
                    metadata = (
                        json.loads(item["metadata"])
                        if isinstance(item["metadata"], str)
                        else (item["metadata"] or {})
                    )
                    metadata["source_url"] = item["source_url"]
                    await sink.persist(
                        json.loads(cached["output"]),
                        metadata,
                        pipeline.sink.config,
                        conn,
                    )
                    await _log_step(
                        conn,
                        job_id,
                        item_id,
                        "cache_hit",
                        "completed",
                        duration_ms=duration_ms,
                    )
                return {
                    "completed": 1,
                    "failed": 0,
                    "cost": 0.0,
                    "duration": duration_ms,
                }

        # Step 3: Dedup (short acquire for DB check)
        async with pool.acquire() as conn:
            dedup_result = await dedup.check(
                clean_content,
                item["source_url"],
                pipeline.dedup.config,
                conn,
            )
        if dedup_result == "duplicate":
            duration_ms = int((time.time() - t0) * 1000)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE processing_engine.job_items
                    SET status = 'completed', dedup_result = 'duplicate',
                        duration_ms = $1, updated_at = NOW()
                    WHERE id = $2
                """,
                    duration_ms,
                    item_id,
                )
                await _log_step(
                    conn,
                    job_id,
                    item_id,
                    "dedup",
                    "skipped",
                    metadata={"result": "duplicate"},
                )
            return {"completed": 1, "failed": 0, "cost": 0.0, "duration": duration_ms}

        # Step 4: LLM Process (NO DB connection held — C2 fix)
        llm_config = {
            "model": pipeline.llm.model,
            "temperature": pipeline.llm.temperature,
            "max_tokens": pipeline.llm.max_tokens,
        }
        llm_result = await llm.process(
            clean_content, system_prompt, output_schema, llm_config
        )
        output = llm_result["output"]
        cost += llm_result["cost_usd"]

        # Log LLM step (short acquire)
        async with pool.acquire() as conn:
            await _log_step(
                conn,
                job_id,
                item_id,
                "llm",
                "completed",
                model=pipeline.llm.model,
                prompt_tokens=llm_result["usage"].get("prompt_tokens"),
                completion_tokens=llm_result["usage"].get("completion_tokens"),
                cost_usd=llm_result["cost_usd"],
            )

        # Step 5: Validate
        all_errors = []
        for v_type, validator, v_config in validators:
            errors = validator.validate(output, clean_content, v_config)
            all_errors.extend(errors)

        # H1 fix: proper retry loop
        if all_errors:
            for attempt in range(pipeline.llm.max_retries):
                async with pool.acquire() as conn:
                    await _log_step(
                        conn,
                        job_id,
                        item_id,
                        "validation",
                        "retry",
                        metadata={"errors": all_errors, "attempt": attempt + 1},
                    )
                # Retry LLM (NO DB connection held)
                llm_result = await llm.process(
                    clean_content, system_prompt, output_schema, llm_config
                )
                output = llm_result["output"]
                cost += llm_result["cost_usd"]
                all_errors = []
                for v_type, validator, v_config in validators:
                    errors = validator.validate(output, clean_content, v_config)
                    all_errors.extend(errors)
                if not all_errors:
                    break

            if all_errors:
                duration_ms = int((time.time() - t0) * 1000)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE processing_engine.job_items
                        SET status = 'failed', validation_errors = $1,
                            cost_usd = $2, duration_ms = $3, updated_at = NOW()
                        WHERE id = $4
                    """,
                        json.dumps(all_errors),
                        cost,
                        duration_ms,
                        item_id,
                    )
                    await _log_step(
                        conn,
                        job_id,
                        item_id,
                        "validation",
                        "failed",
                        metadata={"errors": all_errors},
                    )
                return {
                    "completed": 0,
                    "failed": 1,
                    "cost": cost,
                    "duration": duration_ms,
                }

        # Step 5.5: Post-process (sequential chain — output flows between processors)
        metadata = (
            json.loads(item["metadata"])
            if isinstance(item["metadata"], str)
            else (item["metadata"] or {})
        )
        metadata["source_url"] = item["source_url"]
        for pp_type, processor, pp_config in post_processors:
            try:
                output = await processor.process(output, metadata, pool, pp_config)
            except Exception as pp_err:
                logger.error(
                    "Post-processor %s failed for item %s: %s", pp_type, item_id, pp_err
                )
                duration_ms = int((time.time() - t0) * 1000)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE processing_engine.job_items
                        SET status = 'failed', error = $1, duration_ms = $2, updated_at = NOW()
                        WHERE id = $3
                    """,
                        f"PostProcessor {pp_type}: {pp_err}",
                        duration_ms,
                        item_id,
                    )
                    await _log_step(
                        conn,
                        job_id,
                        item_id,
                        "post_process",
                        "failed",
                        error_message=str(pp_err),
                        duration_ms=duration_ms,
                        metadata={"processor": pp_type},
                    )
                return {
                    "completed": 0,
                    "failed": 1,
                    "cost": cost,
                    "duration": duration_ms,
                }

        # Log post-processing completion
        async with pool.acquire() as conn:
            await _log_step(
                conn,
                job_id,
                item_id,
                "post_process",
                "completed",
                metadata={"processors": [pp[0] for pp in post_processors]},
            )

        # Step 6: Persist via sink (short acquire)
        async with pool.acquire() as conn:
            persist_result = await sink.persist(
                output, metadata, pipeline.sink.config, conn
            )

        # Cache the result
        if pipeline.cache.enabled:
            expires = datetime.now(UTC) + timedelta(hours=pipeline.cache.ttl_hours)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO processing_engine.cache (content_hash, pipeline_id, output, expires_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (content_hash) DO UPDATE SET output = EXCLUDED.output, expires_at = EXCLUDED.expires_at
                """,
                    content_hash,
                    pipeline.id,
                    json.dumps(output),
                    expires,
                )

        duration_ms = int((time.time() - t0) * 1000)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE processing_engine.job_items
                SET status = 'completed', output = $1, dedup_result = $2,
                    usage = $3, cost_usd = $4, duration_ms = $5, updated_at = NOW()
                WHERE id = $6
            """,
                json.dumps(output),
                dedup_result,
                json.dumps(llm_result["usage"]),
                cost,
                duration_ms,
                item_id,
            )
            await _log_step(
                conn,
                job_id,
                item_id,
                "persist",
                "completed",
                duration_ms=duration_ms,
                metadata={"tables": persist_result.get("tables_written", [])},
            )

        return {"completed": 1, "failed": 0, "cost": cost, "duration": duration_ms}

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        logger.exception("Failed to process item %s", item_id)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE processing_engine.job_items
                SET status = 'failed', error = $1, duration_ms = $2, updated_at = NOW()
                WHERE id = $3
            """,
                str(e),
                duration_ms,
                item_id,
            )
            await _log_step(
                conn,
                job_id,
                item_id,
                "error",
                "failed",
                error_message=str(e),
                duration_ms=duration_ms,
            )
        return {"completed": 0, "failed": 1, "cost": cost, "duration": duration_ms}


async def _fail_job(job_id, error: str):
    """Mark a job as failed."""
    pool = await get_pool()
    jid = _uuid.UUID(str(job_id)) if not isinstance(job_id, _uuid.UUID) else job_id
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE processing_engine.jobs
            SET status = 'failed', error_message = $2, completed_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """,
            jid,
            error,
        )
    logger.error("Job %s failed: %s", job_id, error)


async def _log_step(
    conn,
    job_id: str,
    item_id: str | None,
    step: str,
    status: str,
    *,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    cost_usd: float | None = None,
    duration_ms: int = 0,
    error_message: str | None = None,
    metadata: dict | None = None,
):
    """Insert a processing log entry."""
    await conn.execute(
        """
        INSERT INTO processing_engine.processing_logs
            (job_id, item_id, step, status, model_used,
             prompt_tokens, completion_tokens, cost_usd,
             duration_ms, error_message, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    """,
        job_id,
        item_id,
        step,
        status,
        model,
        prompt_tokens,
        completion_tokens,
        cost_usd,
        duration_ms,
        error_message,
        json.dumps(metadata or {}),
    )


def _validate_callback_url(url: str) -> bool:
    """Validate callback URL is safe (no SSRF to internal networks)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        try:
            addr = ip_address(host)
            return addr.is_global
        except ValueError:
            # It's a hostname, block obvious internal patterns
            blocked = ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "[::1]")
            return host.lower() not in blocked
    except Exception:
        return False


async def _send_callback(url: str, job_id: str, status: str):
    """Send callback webhook when job completes."""
    if not _validate_callback_url(url):
        logger.warning("Callback URL blocked (SSRF protection): %s", url)
        return
    import socket

    import httpx

    # DNS rebinding protection: resolve hostname and validate IP
    try:
        parsed_host = urlparse(url).hostname
        addrs = socket.getaddrinfo(parsed_host, None)
        for _, _, _, _, sockaddr in addrs:
            addr = ip_address(sockaddr[0])
            if not addr.is_global:
                logger.warning(
                    "Callback blocked (resolved to non-global IP %s): %s", addr, url
                )
                return
    except Exception as e:
        logger.warning("Callback DNS resolution failed for %s: %s", url, e)
        return
    try:
        headers = {"x-api-key": settings.api_key}
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            await client.post(
                url, json={"job_id": str(job_id), "status": status}, headers=headers
            )
        logger.info("Callback sent: %s → %s", job_id, url)
    except Exception as e:
        logger.warning("Callback failed for job %s: %s", job_id, e)
