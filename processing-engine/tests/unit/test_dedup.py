"""Unit tests for dedup plugins."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.plugins.dedup.hash import HashDedupStrategy, _sha256
from app.plugins.protocols import DedupResult

# ---------------------------------------------------------------------------
# _sha256 helper
# ---------------------------------------------------------------------------


class TestSha256Helper:
    def test_produces_64_char_hex(self):
        result = _sha256("hello")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        assert _sha256("test") == _sha256("test")

    def test_different_inputs_differ(self):
        assert _sha256("hello") != _sha256("world")


# ---------------------------------------------------------------------------
# HashDedupStrategy
# ---------------------------------------------------------------------------


class TestHashDedupStrategy:
    """Tests for HashDedupStrategy using a mock asyncpg connection."""

    strategy = HashDedupStrategy()
    pipeline_id = "pipe-001"

    def _make_conn(self, row=None) -> AsyncMock:
        """Create a mock asyncpg connection."""
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=row)
        return conn

    async def test_new_item_is_not_duplicate(self):
        conn = self._make_conn(row=None)  # No match found
        result = await self.strategy.check(
            content="unique content",
            url="https://example.com/unique",
            pipeline_id=self.pipeline_id,
            conn=conn,
        )
        assert isinstance(result, DedupResult)
        assert result.is_duplicate is False
        assert result.matched_item_id is None
        assert result.strategy == "hash"

    async def test_existing_url_hash_is_duplicate(self):
        # Mock: connection returns a row, simulating an existing item
        fake_row = {"id": "existing-item-id"}
        conn = self._make_conn(row=fake_row)

        result = await self.strategy.check(
            content="some content",
            url="https://example.com/already-seen",
            pipeline_id=self.pipeline_id,
            conn=conn,
        )
        assert result.is_duplicate is True
        assert result.matched_item_id == "existing-item-id"
        assert result.strategy == "hash"

    async def test_existing_content_hash_is_duplicate(self):
        fake_row = {"id": "dupe-by-content"}
        conn = self._make_conn(row=fake_row)

        result = await self.strategy.check(
            content="duplicate content",
            url=None,  # No URL — only content hash checked
            pipeline_id=self.pipeline_id,
            conn=conn,
        )
        assert result.is_duplicate is True
        assert result.matched_item_id == "dupe-by-content"

    async def test_none_url_uses_content_only_query(self):
        """When url is None, the query should only check content_hash."""
        conn = self._make_conn(row=None)

        await self.strategy.check(
            content="hello",
            url=None,
            pipeline_id=self.pipeline_id,
            conn=conn,
        )

        # fetchrow was called once
        conn.fetchrow.assert_called_once()
        # The query should NOT contain url_hash param (only 2 args: pipeline_id + content_hash)
        call_args = conn.fetchrow.call_args
        # call_args[0] is positional args: (query, pipeline_id, content_hash, current_item_id)
        assert len(call_args[0]) == 4  # query + 3 params (including current_item_id=None)

    async def test_with_url_uses_three_params(self):
        """When url is provided, the query should include url_hash param."""
        conn = self._make_conn(row=None)

        await self.strategy.check(
            content="hello",
            url="https://example.com",
            pipeline_id=self.pipeline_id,
            conn=conn,
        )

        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        # query + 4 params: pipeline_id, url_hash, content_hash, current_item_id
        assert len(call_args[0]) == 5

    async def test_similarity_is_none_for_hash_strategy(self):
        conn = self._make_conn(row=None)
        result = await self.strategy.check("content", "url", self.pipeline_id, conn)
        assert result.similarity is None

    async def test_correct_hashes_are_computed(self):
        """Verify that the correct hash values are passed to the DB query."""
        import hashlib

        content = "test content"
        url = "https://test.example.com"
        expected_content_hash = hashlib.sha256(content.encode()).hexdigest()
        expected_url_hash = hashlib.sha256(url.encode()).hexdigest()

        conn = self._make_conn(row=None)
        await self.strategy.check(content, url, self.pipeline_id, conn)

        call_args = conn.fetchrow.call_args[0]
        # call_args: (query, pipeline_id, url_hash, content_hash)
        assert call_args[1] == self.pipeline_id
        assert call_args[2] == expected_url_hash
        assert call_args[3] == expected_content_hash


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestDedupRegistryIntegration:
    def test_hash_registered(self):
        import app.plugins.dedup  # noqa: F401 — triggers registration
        from app.plugins.registry import list_available

        assert "hash" in list_available("dedup")
