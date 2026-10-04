"""Tests for dedup plugins — including self-match prevention.

The critical bug: AutoBatcher inserts items with url_hash/content_hash BEFORE
the worker processes them. Without current_item_id exclusion, the dedup query
finds the item itself and marks it as a duplicate (false positive).
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.plugins.dedup import DEDUP_STRATEGIES, get_dedup
from app.plugins.dedup.composite import CompositeDedupStrategy
from app.plugins.dedup.hash import HashDedupStrategy
from app.plugins.protocols import DedupResult


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestDedupRegistry:
    def test_hash_strategy_registered(self):
        assert "hash" in DEDUP_STRATEGIES
        dedup = get_dedup("hash")
        assert isinstance(dedup, HashDedupStrategy)

    def test_composite_strategy_registered(self):
        assert "composite" in DEDUP_STRATEGIES
        dedup = get_dedup("composite")
        assert isinstance(dedup, CompositeDedupStrategy)

    def test_unknown_falls_back_to_hash(self):
        dedup = get_dedup("nonexistent")
        assert isinstance(dedup, HashDedupStrategy)

    def test_none_strategy_registered(self):
        assert "none" in DEDUP_STRATEGIES

    def test_semantic_strategy_registered(self):
        assert "semantic" in DEDUP_STRATEGIES


# ---------------------------------------------------------------------------
# HashDedupStrategy tests
# ---------------------------------------------------------------------------


class TestHashDedupStrategy:
    """Tests for HashDedupStrategy with self-match prevention."""

    @pytest.fixture
    def strategy(self):
        return HashDedupStrategy()

    @pytest.fixture
    def pipeline_id(self):
        return str(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_no_duplicate_found(self, strategy, pipeline_id):
        """When no matching row exists, item is not a duplicate."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await strategy.check(
            content="Hello world",
            url="https://example.com/article-1",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=str(uuid.uuid4()),
        )

        assert isinstance(result, DedupResult)
        assert result.is_duplicate is False
        assert result.strategy == "hash"

    @pytest.mark.asyncio
    async def test_duplicate_found(self, strategy, pipeline_id):
        """When a matching row exists (different item), it IS a duplicate."""
        other_item_id = uuid.uuid4()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": other_item_id})

        result = await strategy.check(
            content="Hello world",
            url="https://example.com/article-1",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=str(uuid.uuid4()),
        )

        assert result.is_duplicate is True
        assert result.matched_item_id == str(other_item_id)
        assert result.strategy == "hash"

    @pytest.mark.asyncio
    async def test_self_match_excluded_via_query(self, strategy, pipeline_id):
        """current_item_id is passed to the SQL query to exclude self-match.

        This is the CRITICAL test: verifies that the SQL query receives the
        current_item_id parameter so the DB can exclude it via
        AND ($N::uuid IS NULL OR id != $N::uuid).
        """
        current_item_id = str(uuid.uuid4())
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        await strategy.check(
            content="Test content",
            url="https://example.com/page",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=current_item_id,
        )

        # Verify the query was called with current_item_id as last parameter
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        positional_args = call_args[0]
        # With URL: args are (query, pipeline_id, url_hash, content_hash, current_item_id)
        assert positional_args[-1] == current_item_id, (
            "current_item_id MUST be passed to the SQL query to prevent self-match"
        )

    @pytest.mark.asyncio
    async def test_self_match_excluded_no_url(self, strategy, pipeline_id):
        """current_item_id is passed even when URL is None."""
        current_item_id = str(uuid.uuid4())
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        await strategy.check(
            content="Test content",
            url=None,
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=current_item_id,
        )

        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        positional_args = call_args[0]
        # Without URL: args are (query, pipeline_id, content_hash, current_item_id)
        assert positional_args[-1] == current_item_id, (
            "current_item_id MUST be passed even when url is None"
        )

    @pytest.mark.asyncio
    async def test_current_item_id_none_does_not_exclude(self, strategy, pipeline_id):
        """When current_item_id is None, no exclusion happens (backward compat)."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        await strategy.check(
            content="Test content",
            url="https://example.com",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=None,
        )

        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        positional_args = call_args[0]
        # Last arg should be None — SQL handles it via ($N::uuid IS NULL OR ...)
        assert positional_args[-1] is None

    @pytest.mark.asyncio
    async def test_query_targets_job_items_table(self, strategy, pipeline_id):
        """SQL query MUST target processing_engine.job_items (not 'items' or 'cache')."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        await strategy.check(
            content="x", url=None, pipeline_id=pipeline_id,
            conn=conn, current_item_id=None,
        )

        query = conn.fetchrow.call_args[0][0]
        assert "processing_engine.job_items" in query, (
            "Query MUST target processing_engine.job_items"
        )
        assert "processing_engine.cache" not in query, (
            "Query must NOT target the cache table"
        )


# ---------------------------------------------------------------------------
# CompositeDedupStrategy tests
# ---------------------------------------------------------------------------


class TestCompositeDedupStrategy:
    """Tests for CompositeDedupStrategy with self-match prevention."""

    @pytest.mark.asyncio
    async def test_default_init_uses_hash_strategy(self):
        """CompositeDedupStrategy() without args defaults to HashDedupStrategy."""
        composite = CompositeDedupStrategy()
        assert len(composite.strategies) == 1
        assert isinstance(composite.strategies[0], HashDedupStrategy)

    @pytest.mark.asyncio
    async def test_passes_current_item_id_to_substrategy(self):
        """current_item_id MUST be forwarded to each sub-strategy."""
        mock_strategy = AsyncMock()
        mock_strategy.check = AsyncMock(
            return_value=DedupResult(is_duplicate=False, strategy="mock")
        )

        composite = CompositeDedupStrategy(strategies=[mock_strategy])
        current_item_id = str(uuid.uuid4())
        pipeline_id = str(uuid.uuid4())
        conn = AsyncMock()

        await composite.check(
            content="test",
            url="https://example.com",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=current_item_id,
        )

        mock_strategy.check.assert_called_once_with(
            "test", "https://example.com", pipeline_id, conn, current_item_id
        )

    @pytest.mark.asyncio
    async def test_returns_first_duplicate(self):
        """Composite returns the first strategy that finds a duplicate."""
        strategy_1 = AsyncMock()
        strategy_1.check = AsyncMock(
            return_value=DedupResult(
                is_duplicate=True, matched_item_id="abc", strategy="s1"
            )
        )
        strategy_2 = AsyncMock()

        composite = CompositeDedupStrategy(strategies=[strategy_1, strategy_2])

        result = await composite.check(
            "content", None, "pid", AsyncMock(), "item-1"
        )

        assert result.is_duplicate is True
        assert result.matched_item_id == "abc"
        strategy_2.check.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_not_duplicate_when_all_pass(self):
        """When no sub-strategy finds a duplicate, composite returns not-duplicate."""
        strategy_1 = AsyncMock()
        strategy_1.check = AsyncMock(
            return_value=DedupResult(is_duplicate=False, strategy="s1")
        )

        composite = CompositeDedupStrategy(strategies=[strategy_1])
        result = await composite.check(
            "content", None, "pid", AsyncMock(), "item-1"
        )

        assert result.is_duplicate is False
        assert result.strategy == "composite"


# ---------------------------------------------------------------------------
# NoneDedup tests
# ---------------------------------------------------------------------------


class TestNoneDedup:
    @pytest.mark.asyncio
    async def test_always_returns_not_duplicate(self):
        from app.plugins.dedup import NoneDedup
        dedup = NoneDedup()
        result = await dedup.check(
            "anything", "https://url", "pid", AsyncMock(), "item-1"
        )
        assert result.is_duplicate is False
        assert result.strategy == "none"
