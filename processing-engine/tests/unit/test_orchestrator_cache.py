from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.protocols import DedupResult, LLMResponse, ValidationResult
from app.services.orchestrator import Orchestrator


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def sample_pipeline():
    return {
        "id": uuid.uuid4(),
        "ingestor_type": "text",
        "max_content_chars": 100000,
        "dedup_strategy": "hash",
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "llm_temperature": 0.0,
        "llm_seed": 42,
        "llm_max_tokens": 16384,
        "system_prompt": "Extract data",
        "output_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        "validators": ["schema"],
        "sink_type": "postgresql",
        "sink_config": {},
        "max_retries": 1,
        "retry_backoff_base": 0.001,
        "cache_ttl_hours": 720,
    }


def _setup_mocks():
    mock_ingestor = AsyncMock()
    mock_ingestor.ingest = AsyncMock(return_value="ingested text")
    mock_dedup = AsyncMock()
    mock_dedup.check = AsyncMock(return_value=DedupResult(is_duplicate=False))
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=LLMResponse(
            content='{"name":"test"}',
            parsed={"name": "test"},
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            model="gpt-4.1-mini",
            provider="openai",
        )
    )
    mock_validator = MagicMock()
    mock_validator.validate = MagicMock(return_value=ValidationResult(valid=True))
    mock_sink = AsyncMock()
    mock_sink.persist = AsyncMock()
    return mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink


class TestCacheIntegration:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        # First call: fetchrow for dedup returns None, fetchrow for cache returns a hit
        cache_hit_record = {
            "output": json.dumps({"name": "cached"}),
            "prompt_tokens": 8,
            "completion_tokens": 4,
            "cost_usd": 0.0005,
            "llm_model": "gpt-4.1-mini",
        }
        # fetchrow calls: dedup check (None), cache check (hit)
        mock_conn.fetchrow = AsyncMock(return_value=cache_hit_record)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        assert result["cached"] is True
        assert result["output"] == {"name": "cached"}
        # LLM should NOT be called on cache hit
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        # All fetchrow return None (no cache, no dedup)
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        assert result["cached"] is False
        assert result["output"] == {"name": "test"}
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_cache_bypasses_check(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
                skip_cache=True,
            )

        assert result["cached"] is False
        mock_llm.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_saved_after_successful_processing(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        # Verify UPSERT_CACHE was called (it's the execute with 8 params)
        [
            c
            for c in mock_conn.execute.call_args_list
            if len(c.args) == 9 and "make_interval" not in str(c.args[0])
            # UPSERT_CACHE has 8 params ($1-$8)
        ]
        # The cache upsert should have been attempted
        # We check that execute was called with the cache SQL
        execute_sqls = [str(c.args[0]) for c in mock_conn.execute.call_args_list]
        assert any("cache_entries" in sql for sql in execute_sqls)


class TestLoggingSkippedSteps:
    @pytest.mark.asyncio
    async def test_skip_dedup_logs_skipped(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
                skip_dedup=True,
            )

        # Check that a "dedup" / "skipped" log was inserted
        # _log signature: (sql, item_id, job_id, pipeline_id, step, status, duration_ms, error, meta)
        log_calls = [
            c
            for c in mock_conn.execute.call_args_list
            if len(c.args) >= 5 and c.args[1] == item_id and c.args[4] == "dedup"
        ]
        assert len(log_calls) >= 1
        # The status should be "skipped"
        assert log_calls[0].args[5] == "skipped"

    @pytest.mark.asyncio
    async def test_skip_cache_logs_skipped(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
                skip_cache=True,
            )

        # Check that a "cache" / "skipped" log was inserted
        # _log signature: (sql, item_id, job_id, pipeline_id, step, status, duration_ms, error, meta)
        log_calls = [
            c
            for c in mock_conn.execute.call_args_list
            if len(c.args) >= 5 and c.args[1] == item_id and c.args[4] == "cache"
        ]
        assert len(log_calls) >= 1
        assert log_calls[0].args[5] == "skipped"

    @pytest.mark.asyncio
    async def test_cache_miss_logs_miss(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_ingestor, mock_dedup, mock_llm, mock_validator, mock_sink = _setup_mocks()

        with patch("app.services.orchestrator.get_instance") as mock_get:

            def side_effect(ptype, name):
                return {
                    "ingestor": mock_ingestor,
                    "dedup": mock_dedup,
                    "llm": mock_llm,
                    "validator": mock_validator,
                    "sink": mock_sink,
                }[ptype]

            mock_get.side_effect = side_effect

            await orchestrator.process_item(
                item_id=item_id,
                raw_content="hello",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        # Check that a "cache" / "miss" log was inserted
        # _log signature: (sql, item_id, job_id, pipeline_id, step, status, duration_ms, error, meta)
        log_calls = [
            c
            for c in mock_conn.execute.call_args_list
            if len(c.args) >= 5 and c.args[1] == item_id and c.args[4] == "cache"
        ]
        assert len(log_calls) >= 1
        assert log_calls[0].args[5] == "miss"
