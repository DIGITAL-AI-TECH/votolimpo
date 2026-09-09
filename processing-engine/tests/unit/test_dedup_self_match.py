"""Tests for dedup self-match fix.

Verifies that the dedup plugins do NOT flag the current item as a duplicate
of itself (false-positive bug fixed by passing current_item_id to check()).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.dedup.composite import CompositeDedupStrategy
from app.plugins.dedup.hash import HashDedupStrategy


@pytest.fixture
def item_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def pipeline_id() -> str:
    return str(uuid.uuid4())


class TestHashDedupSelfMatch:
    """HashDedupStrategy must not match the item against itself."""

    @pytest.mark.asyncio
    async def test_no_self_match_with_current_item_id(self, item_id: str, pipeline_id: str):
        """When current_item_id is passed and the only match is itself, result is NOT duplicate."""
        conn = AsyncMock()
        # Simulate: query with exclusion returns no rows (the only match was itself)
        conn.fetchrow = AsyncMock(return_value=None)

        strategy = HashDedupStrategy()
        result = await strategy.check(
            content="test content",
            url="https://example.com/test",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=item_id,
        )

        assert result.is_duplicate is False
        assert result.strategy == "hash"

        # Verify the SQL was called with 4 params (including current_item_id)
        call_args = conn.fetchrow.call_args
        assert (
            len(call_args[0]) == 5
        )  # sql + pipeline_id + url_hash + content_hash + current_item_id
        assert call_args[0][4] == item_id  # current_item_id is the 5th arg (4th param)

    @pytest.mark.asyncio
    async def test_detects_real_duplicate_with_different_id(self, item_id: str, pipeline_id: str):
        """When another item has the same hash, it IS detected as duplicate."""
        other_id = str(uuid.uuid4())
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value={"id": uuid.UUID(other_id)})

        strategy = HashDedupStrategy()
        result = await strategy.check(
            content="duplicate content",
            url="https://example.com/dup",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=item_id,
        )

        assert result.is_duplicate is True
        assert result.matched_item_id == other_id
        assert result.strategy == "hash"

    @pytest.mark.asyncio
    async def test_backward_compat_no_current_item_id(self, pipeline_id: str):
        """When current_item_id is not passed (None), query still works."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        strategy = HashDedupStrategy()
        result = await strategy.check(
            content="some content",
            url=None,
            pipeline_id=pipeline_id,
            conn=conn,
        )

        assert result.is_duplicate is False
        # Query should have 3 params: sql + pipeline_id + content_hash + None
        call_args = conn.fetchrow.call_args
        assert call_args[0][3] is None  # current_item_id defaults to None

    @pytest.mark.asyncio
    async def test_no_url_with_current_item_id(self, item_id: str, pipeline_id: str):
        """Without URL, query uses content_hash only + excludes current item."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        strategy = HashDedupStrategy()
        result = await strategy.check(
            content="content without url",
            url=None,
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=item_id,
        )

        assert result.is_duplicate is False
        call_args = conn.fetchrow.call_args
        assert call_args[0][3] == item_id


class TestCompositeDedupSelfMatch:
    """CompositeDedupStrategy must propagate current_item_id to sub-strategies."""

    @pytest.mark.asyncio
    async def test_propagates_current_item_id(self, item_id: str, pipeline_id: str):
        """current_item_id is forwarded to each sub-strategy."""
        mock_strategy = AsyncMock()
        mock_strategy.check = AsyncMock(return_value=MagicMock(is_duplicate=False))

        composite = CompositeDedupStrategy(strategies=[mock_strategy])
        conn = AsyncMock()

        await composite.check(
            content="test",
            url="https://example.com",
            pipeline_id=pipeline_id,
            conn=conn,
            current_item_id=item_id,
        )

        mock_strategy.check.assert_called_once_with(
            "test", "https://example.com", pipeline_id, conn, item_id
        )
