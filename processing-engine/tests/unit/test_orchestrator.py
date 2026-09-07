from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.protocols import DedupResult, LLMResponse, ValidationResult
from app.services.orchestrator import Orchestrator


@pytest.fixture
def mock_conn():
    """Mock asyncpg connection."""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    # fetchrow returns None by default (no cache hit, no dedup match)
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def sample_pipeline():
    return {
        "id": uuid.uuid4(),
        "ingestor_type": "text",
        "max_content_chars": 100000,
        "dedup_strategy": "hash",
        "dedup_threshold": 0.9,
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
        "max_retries": 3,
        "retry_backoff_base": 0.01,  # fast for tests
    }


class TestOrchestratorFullPipeline:
    @pytest.mark.asyncio
    async def test_process_item_all_steps(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        mock_ingestor = AsyncMock()
        mock_ingestor.ingest = AsyncMock(return_value="ingested text")

        mock_dedup = AsyncMock()
        mock_dedup.check = AsyncMock(return_value=DedupResult(is_duplicate=False))

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            content='{"name": "test"}',
            parsed={"name": "test"},
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            model="gpt-4.1-mini",
            provider="openai",
        ))

        mock_validator = MagicMock()
        mock_validator.validate = MagicMock(return_value=ValidationResult(valid=True))

        mock_sink = AsyncMock()
        mock_sink.persist = AsyncMock()

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
                raw_content="hello world",
                source_url="https://example.com",
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        assert result["output"] == {"name": "test"}
        assert result["dedup_result"] == "new"
        assert result["prompt_tokens"] == 10
        assert result["duration_ms"] > 0
        mock_ingestor.ingest.assert_called_once()
        mock_dedup.check.assert_called_once()
        mock_llm.complete.assert_called_once()
        mock_validator.validate.assert_called_once()
        mock_sink.persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_dedup_duplicate_skips_llm(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        mock_ingestor = AsyncMock()
        mock_ingestor.ingest = AsyncMock(return_value="text")

        mock_dedup = AsyncMock()
        mock_dedup.check = AsyncMock(return_value=DedupResult(
            is_duplicate=True, matched_item_id=str(uuid.uuid4()), strategy="hash"
        ))

        mock_llm = AsyncMock()

        with patch("app.services.orchestrator.get_instance") as mock_get:
            def side_effect(ptype, name):
                return {"ingestor": mock_ingestor, "dedup": mock_dedup, "llm": mock_llm}[ptype]
            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id,
                raw_content="text",
                source_url=None,
                content_type="text/plain",
                pipeline=sample_pipeline,
                conn=mock_conn,
            )

        assert result["dedup_result"] == "duplicate"
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_retry_on_failure(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()
        sample_pipeline["max_retries"] = 2
        sample_pipeline["retry_backoff_base"] = 0.001

        mock_ingestor = AsyncMock()
        mock_ingestor.ingest = AsyncMock(return_value="text")

        mock_dedup = AsyncMock()
        mock_dedup.check = AsyncMock(return_value=DedupResult(is_duplicate=False))

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=[
            Exception("rate limit"),
            LLMResponse(content='{"name":"ok"}', parsed={"name":"ok"}, prompt_tokens=5, completion_tokens=3, total_tokens=8),
        ])

        mock_validator = MagicMock()
        mock_validator.validate = MagicMock(return_value=ValidationResult(valid=True))

        mock_sink = AsyncMock()
        mock_sink.persist = AsyncMock()

        with patch("app.services.orchestrator.get_instance") as mock_get:
            def side_effect(ptype, name):
                return {"ingestor": mock_ingestor, "dedup": mock_dedup, "llm": mock_llm, "validator": mock_validator, "sink": mock_sink}[ptype]
            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id, raw_content="text", source_url=None,
                content_type="text/plain", pipeline=sample_pipeline, conn=mock_conn,
            )

        assert result["output"] == {"name": "ok"}
        assert mock_llm.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_dry_run_skips_persist(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        mock_ingestor = AsyncMock()
        mock_ingestor.ingest = AsyncMock(return_value="text")

        mock_dedup = AsyncMock()
        mock_dedup.check = AsyncMock(return_value=DedupResult(is_duplicate=False))

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            content='{"name":"test"}', parsed={"name":"test"},
            prompt_tokens=10, completion_tokens=5, total_tokens=15,
        ))

        mock_validator = MagicMock()
        mock_validator.validate = MagicMock(return_value=ValidationResult(valid=True))

        mock_sink = AsyncMock()

        with patch("app.services.orchestrator.get_instance") as mock_get:
            def side_effect(ptype, name):
                return {"ingestor": mock_ingestor, "dedup": mock_dedup, "llm": mock_llm, "validator": mock_validator, "sink": mock_sink}[ptype]
            mock_get.side_effect = side_effect

            result = await orchestrator.process_item(
                item_id=item_id, raw_content="text", source_url=None,
                content_type="text/plain", pipeline=sample_pipeline, conn=mock_conn,
                dry_run=True,
            )

        assert result["output"] == {"name": "test"}
        mock_sink.persist.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_failure_raises(self, mock_conn, sample_pipeline):
        item_id = uuid.uuid4()
        orchestrator = Orchestrator()

        mock_ingestor = AsyncMock()
        mock_ingestor.ingest = AsyncMock(return_value="text")

        mock_dedup = AsyncMock()
        mock_dedup.check = AsyncMock(return_value=DedupResult(is_duplicate=False))

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value=LLMResponse(
            content='{"bad": 1}', parsed={"bad": 1},
            prompt_tokens=10, completion_tokens=5, total_tokens=15,
        ))

        mock_validator = MagicMock()
        mock_validator.validate = MagicMock(return_value=ValidationResult(
            valid=False, errors=["'name' is required"]
        ))

        with patch("app.services.orchestrator.get_instance") as mock_get:
            def side_effect(ptype, name):
                return {"ingestor": mock_ingestor, "dedup": mock_dedup, "llm": mock_llm, "validator": mock_validator}[ptype]
            mock_get.side_effect = side_effect

            with pytest.raises(ValueError, match="Validation failed"):
                await orchestrator.process_item(
                    item_id=item_id, raw_content="text", source_url=None,
                    content_type="text/plain", pipeline=sample_pipeline, conn=mock_conn,
                )
