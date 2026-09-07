"""Unit tests for Auto-Batcher service.

Tests use mocks — no Docker or PostgreSQL required.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENGINE_ROLE", "api")

import pytest

from app.services.auto_batcher import AutoBatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool_item(pipeline_id=None, pool_id=None, source_url="https://example.com"):
    pool_id = pool_id or uuid.uuid4()
    pipeline_id = pipeline_id or uuid.uuid4()

    class FakeRecord(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)
        def get(self, key, default=None):
            return dict.get(self, key, default)

    return FakeRecord(
        id=pool_id,
        pipeline_id=pipeline_id,
        source_url=source_url,
        content="Test content",
        content_type="text/plain",
        metadata={"source": "test"},
        url_hash="abc123",
        content_hash="def456",
        status="claimed",
        priority=0,
        source_id="test-scraper",
        batch_ref=None,
        job_id=None,
    )


def _make_pipeline_record(pipeline_id=None, version=1):
    pid = pipeline_id or uuid.uuid4()

    class FakeRecord(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)
        def get(self, key, default=None):
            return dict.get(self, key, default)

    return FakeRecord(id=pid, name="Test Pipeline", version=version, is_active=True)


def _make_job_record(job_id=None):
    jid = job_id or uuid.uuid4()

    class FakeRecord(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)
        def get(self, key, default=None):
            return dict.get(self, key, default)

    return FakeRecord(id=jid, status="queued")


def _make_mock_pool():
    """Create a mock asyncpg pool with connection context manager."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Make pool.acquire() return an async context manager that yields mock_conn
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=mock_conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = acq

    # Transaction context manager — transaction() must be a regular call, not async
    txn = MagicMock()
    txn.__aenter__ = AsyncMock()
    txn.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=txn)

    return mock_pool, mock_conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutoBatcher:

    @pytest.mark.asyncio
    async def test_claim_and_create_jobs_creates_job(self):
        """Items claimed from pool should become jobs."""
        mock_pool, mock_conn = _make_mock_pool()
        pipeline_id = uuid.uuid4()
        pool_item = _make_pool_item(pipeline_id=pipeline_id)
        job_record = _make_job_record()

        # fetchrow calls: 1) pipeline lookup, 2) INSERT job
        mock_conn.fetchrow = AsyncMock(side_effect=[
            _make_pipeline_record(pipeline_id),  # pipeline lookup
            job_record,                          # INSERT job
        ])
        # fetch calls: 1) CLAIM_PENDING_ITEMS
        mock_conn.fetch = AsyncMock(return_value=[pool_item])
        mock_conn.execute = AsyncMock()

        batcher = AutoBatcher(pool=mock_pool, poll_interval=1, batch_size=10)
        created = await batcher._claim_and_create_jobs(pipeline_id)

        assert created == 1
        # Verify INSERT_ITEM was called
        assert mock_conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_batch_cycle_no_pending(self):
        """Batch cycle with no pending items should be idle."""
        mock_pool, mock_conn = _make_mock_pool()
        mock_conn.fetch = AsyncMock(return_value=[])  # No pending pipelines

        batcher = AutoBatcher(pool=mock_pool, poll_interval=1, batch_size=10)
        await batcher._batch_cycle()

        # Should have called GET_PENDING_PIPELINE_IDS
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_cycle_multiple_pipelines(self):
        """Batch cycle should process multiple pipelines."""
        mock_pool, mock_conn = _make_mock_pool()
        pid1 = uuid.uuid4()
        pid2 = uuid.uuid4()

        class FakeRow(dict):
            def __getitem__(self, key):
                return dict.__getitem__(self, key)

        # First fetch: GET_PENDING_PIPELINE_IDS
        mock_conn.fetch = AsyncMock(return_value=[
            FakeRow(pipeline_id=pid1),
            FakeRow(pipeline_id=pid2),
        ])

        batcher = AutoBatcher(pool=mock_pool, poll_interval=1, batch_size=10)

        with patch.object(batcher, '_claim_and_create_jobs', new_callable=AsyncMock) as mock_claim:
            mock_claim.return_value = 0
            await batcher._batch_cycle()

            assert mock_claim.call_count == 2
            mock_claim.assert_any_call(pid1)
            mock_claim.assert_any_call(pid2)

    @pytest.mark.asyncio
    async def test_pipeline_not_found_marks_error(self):
        """If pipeline doesn't exist, items should be marked as error."""
        mock_pool, mock_conn = _make_mock_pool()
        pipeline_id = uuid.uuid4()
        pool_item = _make_pool_item(pipeline_id=pipeline_id)

        # fetchrow: pipeline not found
        mock_conn.fetchrow = AsyncMock(return_value=None)
        # fetch: claimed items
        mock_conn.fetch = AsyncMock(return_value=[pool_item])
        mock_conn.execute = AsyncMock()

        batcher = AutoBatcher(pool=mock_pool, poll_interval=1, batch_size=10)
        created = await batcher._claim_and_create_jobs(pipeline_id)

        assert created == 0
        # Should have called UPDATE_POOL_STATUS_ERROR
        mock_conn.execute.assert_called()

    @pytest.mark.asyncio
    async def test_stop_graceful(self):
        """Stop should cancel the running task gracefully."""
        mock_pool, _ = _make_mock_pool()
        batcher = AutoBatcher(pool=mock_pool, poll_interval=60, batch_size=10)

        await batcher.start()
        assert batcher._task is not None
        assert not batcher._task.done()

        await batcher.stop()
        assert batcher._task is None
        assert not batcher._running

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """Start should create a background task."""
        mock_pool, _ = _make_mock_pool()
        batcher = AutoBatcher(pool=mock_pool, poll_interval=60, batch_size=10)

        await batcher.start()
        assert batcher._running is True
        assert batcher._task is not None

        # Cleanup
        await batcher.stop()
