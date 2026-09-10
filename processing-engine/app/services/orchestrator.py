from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any

import asyncpg

from app.plugins.protocols import DedupResult, LLMResponse, ValidationResult
from app.plugins.registry import get_instance
from app.services.cost_tracker import CostTracker
from app.sql.cache import INCREMENT_CACHE_HIT, SELECT_CACHE_HIT, UPSERT_CACHE

logger = logging.getLogger(__name__)

# Inline SQL to avoid circular dependency with parallel agent
_UPDATE_ITEM_STATUS = "UPDATE processing_engine.items SET status = $2 WHERE id = $1"
_INSERT_LOG = """
INSERT INTO processing_engine.processing_logs (item_id, job_id, pipeline_id, step, status, duration_ms, error_message, metadata)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
"""


class Orchestrator:
    """Processes a single item through all pipeline stages."""

    async def process_item(
        self,
        item_id: uuid.UUID,
        raw_content: str,
        source_url: str | None,
        content_type: str,
        pipeline: dict[str, Any],
        conn: asyncpg.Connection,
        skip_dedup: bool = False,
        skip_cache: bool = False,
        dry_run: bool = False,
        override_model: str | None = None,
        job_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Execute pipeline: ingest → dedup → process → validate → persist.

        Returns dict with keys: output, dedup_result, cached, usage, duration_ms
        """
        # Store context for _log calls
        self._current_job_id = job_id
        self._current_pipeline_id = pipeline.get("id")

        total_start = time.monotonic()
        result: dict[str, Any] = {
            "output": None,
            "dedup_result": "new",
            "cached": False,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "duration_ms": 0,
        }

        # --- 1. INGEST ---
        await conn.execute(_UPDATE_ITEM_STATUS, item_id, "ingesting")
        ingested = await self._run_step(
            conn, item_id, "ingest", self._ingest, raw_content, content_type, pipeline
        )

        # --- 2. DEDUP ---
        if not skip_dedup:
            await conn.execute(_UPDATE_ITEM_STATUS, item_id, "deduplicating")
            dedup_result: DedupResult = await self._run_step(
                conn,
                item_id,
                "dedup",
                self._dedup,
                ingested,
                source_url,
                pipeline,
                conn,
                str(item_id),
            )
            if dedup_result.is_duplicate:
                result["dedup_result"] = "duplicate"
                result["duration_ms"] = int((time.monotonic() - total_start) * 1000)
                await conn.execute(_UPDATE_ITEM_STATUS, item_id, "duplicate")
                return result
        else:
            await self._log(
                conn, item_id, "dedup", "skipped", 0, meta={"reason": "skip_dedup=true"}
            )

        # --- CACHE CHECK (after dedup, before LLM) ---
        content_hash = hashlib.sha256(ingested.encode("utf-8")).hexdigest()
        if not skip_cache:
            cache_start = time.monotonic()
            cache_hit = await conn.fetchrow(
                SELECT_CACHE_HIT, content_hash, pipeline["id"]
            )
            cache_duration = int((time.monotonic() - cache_start) * 1000)
            if cache_hit:
                await conn.execute(INCREMENT_CACHE_HIT, content_hash, pipeline["id"])
                result["output"] = (
                    json.loads(cache_hit["output"])
                    if isinstance(cache_hit["output"], str)
                    else cache_hit["output"]
                )
                result["cached"] = True
                result["duration_ms"] = int((time.monotonic() - total_start) * 1000)
                await conn.execute(_UPDATE_ITEM_STATUS, item_id, "completed")
                await self._log(conn, item_id, "cache", "hit", cache_duration)
                return result
            await self._log(conn, item_id, "cache", "miss", cache_duration)
        else:
            await self._log(
                conn, item_id, "cache", "skipped", 0, meta={"reason": "skip_cache=true"}
            )

        # --- 3. PROCESS (LLM) ---
        await conn.execute(_UPDATE_ITEM_STATUS, item_id, "processing")
        llm_response: LLMResponse = await self._run_step_with_retry(
            conn,
            item_id,
            "process",
            self._process_llm,
            ingested,
            pipeline,
            override_model,
            max_retries=pipeline.get("max_retries", 3),
            backoff_base=pipeline.get("retry_backoff_base", 2.0),
        )
        result["output"] = llm_response.parsed or json.loads(llm_response.content)
        result["prompt_tokens"] = llm_response.prompt_tokens
        result["completion_tokens"] = llm_response.completion_tokens
        result["total_tokens"] = llm_response.total_tokens

        # Log LLM call cost (best-effort — never breaks the pipeline)
        try:
            cost_tracker = CostTracker()
            call_log = await cost_tracker.log_call(
                conn,
                item_id=item_id,
                job_id=job_id,
                pipeline_id=pipeline["id"],
                provider=llm_response.provider
                or pipeline.get("llm_provider", "openai"),
                model=llm_response.model or pipeline.get("llm_model", "gpt-4.1-mini"),
                call_type="completion",
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                total_tokens=llm_response.total_tokens,
                latency_ms=llm_response.latency_ms,
                status="success",
            )
            result["cost_usd"] = call_log.get("cost_usd", 0.0)
        except Exception:
            logger.debug("Cost tracking skipped (non-critical)", exc_info=True)

        # --- 4. VALIDATE ---
        await conn.execute(_UPDATE_ITEM_STATUS, item_id, "validating")
        validation: ValidationResult = await self._run_step(
            conn,
            item_id,
            "validate",
            self._validate,
            result["output"],
            ingested,
            pipeline,
        )
        if not validation.valid:
            raise ValueError(f"Validation failed: {validation.errors}")

        # --- 5. PERSIST ---
        if not dry_run:
            await conn.execute(_UPDATE_ITEM_STATUS, item_id, "persisting")
            await self._run_step(
                conn,
                item_id,
                "persist",
                self._persist,
                item_id,
                result["output"],
                pipeline,
                conn,
            )

        # Save to cache
        cache_ttl = pipeline.get("cache_ttl_hours", 720)
        if cache_ttl > 0 and result["output"]:
            try:
                await conn.execute(
                    UPSERT_CACHE,
                    content_hash,
                    pipeline["id"],
                    json.dumps(result["output"]),
                    result["prompt_tokens"],
                    result["completion_tokens"],
                    result["cost_usd"],
                    override_model or pipeline.get("llm_model", "gpt-4.1-mini"),
                    cache_ttl,
                )
            except Exception:
                logger.debug("Cache save failed", exc_info=True)

        result["duration_ms"] = int((time.monotonic() - total_start) * 1000)
        return result

    # --- Plugin delegates ---

    async def _ingest(self, raw: str, content_type: str, pipeline: dict) -> str:
        ingestor = get_instance("ingestor", pipeline.get("ingestor_type", "auto"))
        return await ingestor.ingest(
            raw, content_type, pipeline.get("max_content_chars", 100000)
        )

    async def _dedup(
        self,
        content: str,
        url: str | None,
        pipeline: dict,
        conn: asyncpg.Connection,
        current_item_id: str | None = None,
    ) -> DedupResult:
        strategy = get_instance("dedup", pipeline.get("dedup_strategy", "hash"))
        return await strategy.check(
            content, url, str(pipeline["id"]), conn, current_item_id
        )

    async def _process_llm(
        self, content: str, pipeline: dict, override_model: str | None
    ) -> LLMResponse:
        provider = get_instance("llm", pipeline.get("llm_provider", "openai"))
        config = {
            "model": override_model or pipeline.get("llm_model", "gpt-4.1-mini"),
            "temperature": pipeline.get("llm_temperature", 0.0),
            "seed": pipeline.get("llm_seed", 42),
            "max_tokens": pipeline.get("llm_max_tokens", 16384),
        }
        return await provider.complete(
            user_content=content,
            system_prompt=pipeline.get("system_prompt", ""),
            output_schema=pipeline.get("output_schema", {}),
            config=config,
        )

    async def _validate(
        self, output: dict, source: str, pipeline: dict
    ) -> ValidationResult:
        validators = pipeline.get("validators", ["schema"])
        # Run first validator (schema is the only built-in for now)
        validator = get_instance("validator", validators[0] if validators else "schema")
        return validator.validate(output, source, pipeline.get("output_schema", {}))

    async def _persist(
        self, item_id: uuid.UUID, output: dict, pipeline: dict, conn: asyncpg.Connection
    ) -> None:
        sink = get_instance("sink", pipeline.get("sink_type", "postgresql"))
        await sink.persist(str(item_id), output, pipeline.get("sink_config", {}), conn)

    # --- Step execution helpers ---

    async def _run_step(self, conn, item_id, step_name, fn, *args) -> Any:
        """Run a pipeline step, log duration and result."""
        start = time.monotonic()
        try:
            result = await fn(*args)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._log(conn, item_id, step_name, "ok", duration_ms)
            return result
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._log(conn, item_id, step_name, "error", duration_ms, str(e))
            raise

    async def _run_step_with_retry(
        self, conn, item_id, step_name, fn, *args, max_retries=3, backoff_base=2.0
    ) -> Any:
        """Run step with exponential backoff retries."""
        last_error = None
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                result = await fn(*args)
                duration_ms = int((time.monotonic() - start) * 1000)
                status = "ok" if attempt == 0 else f"ok_after_{attempt}_retries"
                await self._log(conn, item_id, step_name, status, duration_ms)
                return result
            except Exception as e:
                last_error = e
                duration_ms = int((time.monotonic() - start) * 1000)
                if attempt < max_retries:
                    await self._log(
                        conn,
                        item_id,
                        step_name,
                        "retry",
                        duration_ms,
                        str(e),
                        {"attempt": attempt + 1, "max_retries": max_retries},
                    )
                    await asyncio.sleep(backoff_base**attempt)
                else:
                    await self._log(
                        conn,
                        item_id,
                        step_name,
                        "error",
                        duration_ms,
                        str(e),
                        {"attempts_exhausted": max_retries + 1},
                    )
        raise last_error  # type: ignore[misc]

    async def _log(
        self, conn, item_id, step, status, duration_ms, error=None, meta=None
    ):
        await conn.execute(
            _INSERT_LOG,
            item_id,
            self._current_job_id,
            self._current_pipeline_id,
            step,
            status,
            duration_ms,
            error,
            json.dumps(meta) if meta else None,
        )
