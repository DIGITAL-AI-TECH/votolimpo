"""Tests for configurable PostgreSQL sink with column_mapping mode."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.sinks import SINKS, PostgreSQLSink, get_sink

# ─── Helpers ───


class _AsyncCtx:
    """Proper async context manager."""

    def __init__(self, value=None):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        return False


def _make_conn():
    """Create a mock asyncpg.Connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncCtx())
    return conn


# ─── Registry ───


class TestSinkRegistry:
    def test_postgresql_in_registry(self):
        assert "postgresql" in SINKS

    def test_get_sink_returns_postgresql(self):
        sink = get_sink("postgresql")
        assert isinstance(sink, PostgreSQLSink)

    def test_get_sink_unknown_defaults_postgresql(self):
        sink = get_sink("unknown_sink_type")
        assert isinstance(sink, PostgreSQLSink)


# ─── column_mapping mode ───


class TestColumnMappingMode:
    async def test_basic_insert(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test Article", "summary": "A summary"}
        config = {
            "table": "test_table",
            "column_mapping": {
                "title": "title",
                "summary": "summary_text",
            },
        }

        result = await sink._do_persist(conn, output, {}, config)
        assert "test_table" in result["tables_written"]
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args
        assert "INSERT INTO test_table" in call_args[0][0]

    async def test_upsert_with_conflict_column(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"url_hash": "abc123", "title": "Updated"}
        config = {
            "table": "articles",
            "column_mapping": {"url_hash": "url_hash", "title": "title"},
            "conflict_column": "url_hash",
        }

        result = await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "ON CONFLICT (url_hash)" in call_sql
        assert "DO UPDATE SET" in call_sql
        assert result["article_id"] == 1

    async def test_static_columns(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test"}
        config = {
            "table": "articles",
            "column_mapping": {"title": "title"},
            "static_columns": {"processing_status": "completed", "source": "pe"},
        }

        await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "processing_status" in call_sql
        assert "source" in call_sql

    async def test_item_field_mapping(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test"}
        metadata = {"source_url": "https://example.com", "nc_article_id": 42}
        config = {
            "table": "articles",
            "column_mapping": {"title": "title"},
            "item_field_mapping": {
                "source_url": "url",
                "nc_article_id": "nc_article_id",
            },
        }

        await sink._do_persist(conn, output, metadata, config)
        call_args = conn.fetchrow.call_args
        # Should have title + source_url + nc_article_id as params
        assert len(call_args[0]) >= 4  # sql + 3 params

    async def test_jsonb_fallback_column(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test", "nested": {"key": "value"}}
        config = {
            "table": "articles",
            "column_mapping": {"title": "title"},
            "jsonb_fallback": "raw_extraction",
        }

        await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "raw_extraction" in call_sql
        assert "::jsonb" in call_sql

    async def test_skips_none_values_in_mapping(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test", "optional_field": None}
        config = {
            "table": "articles",
            "column_mapping": {"title": "title", "optional_field": "optional_col"},
        }

        await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "optional_col" not in call_sql

    async def test_auto_generates_url_hash_for_conflict(self):
        """When conflict_column is url_hash but not in mapping, auto-generate from source_url."""
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test"}
        metadata = {"source_url": "https://example.com/article"}
        config = {
            "table": "votolimpo.articles",
            "column_mapping": {"title": "title"},
            "conflict_column": "url_hash",
        }

        await sink._do_persist(conn, output, metadata, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "url_hash" in call_sql
        assert "ON CONFLICT (url_hash)" in call_sql
        # url and url_hash should both be in the INSERT
        assert "url" in call_sql

    async def test_type_casts_applied(self):
        """type_casts config adds SQL casts to parameter placeholders."""
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"severity": "high"}
        config = {
            "table": "articles",
            "column_mapping": {"severity": "severity"},
            "type_casts": {"severity": "votolimpo.severity_level"},
        }

        await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "::votolimpo.severity_level" in call_sql

    async def test_type_casts_on_static_columns(self):
        """type_casts also work for static columns."""
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"title": "Test"}
        config = {
            "table": "articles",
            "column_mapping": {"title": "title"},
            "static_columns": {"processing_status": "completed"},
            "type_casts": {"processing_status": "votolimpo.processing_status"},
        }

        await sink._do_persist(conn, output, {}, config)
        call_sql = conn.fetchrow.call_args[0][0]
        assert "::votolimpo.processing_status" in call_sql

    async def test_requires_table(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        with pytest.raises(ValueError, match="requires 'table'"):
            await sink._do_persist(conn, {}, {}, {"column_mapping": {"x": "y"}})

    async def test_empty_mapping_does_nothing(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"unmapped": "value"}
        config = {
            "table": "articles",
            "column_mapping": {"nonexistent_key": "col"},
        }

        result = await sink._do_persist(conn, output, {}, config)
        assert result["tables_written"] == []
        conn.fetchrow.assert_not_called()

    async def test_json_serializes_dicts_and_lists(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"data": {"nested": True}, "tags": ["a", "b"]}
        config = {
            "table": "test",
            "column_mapping": {"data": "data_col", "tags": "tags_col"},
        }

        await sink._do_persist(conn, output, {}, config)
        call_args = conn.fetchrow.call_args[0]
        # Params should be JSON strings for dict and list
        assert call_args[1] == json.dumps({"nested": True})
        assert call_args[2] == json.dumps(["a", "b"])


# ─── Legacy mappings mode ───


class TestLegacyMappingsMode:
    async def test_upsert_article(self):
        conn = _make_conn()
        # Setup transaction context manager
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock()
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value = tx

        # fetchrow for source upsert, then article upsert
        conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": 5},  # source upsert
                {"id": 100},  # article upsert
            ]
        )

        sink = PostgreSQLSink()
        output = {"severity": "high", "summary": "Test", "keywords": ["test"]}
        metadata = {
            "source_url": "https://example.com/article",
            "source_name": "Example News",
            "source_domain": "example.com",
            "title": "Test Article",
            "published_at": None,
            "nc_article_id": 42,
        }
        config = {
            "mappings": [{"target_table": "articles", "strategy": "upsert"}],
        }

        result = await sink._do_persist(conn, output, metadata, config)
        assert result["article_id"] == 100
        assert "articles" in result["tables_written"]


# ─── JSONB fallback mode ───


class TestJsonbFallbackMode:
    async def test_simple_jsonb_insert(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        output = {"key": "value", "nested": [1, 2, 3]}
        metadata = {"item_id": "test-item-123"}

        result = await sink._do_persist(conn, output, metadata, {})
        conn.execute.assert_called_once()
        call_sql = conn.execute.call_args[0][0]
        assert "ON CONFLICT (item_id)" in call_sql
        assert result["tables_written"] == ["processing_engine.results"]

    async def test_custom_fallback_table(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        await sink._do_persist(conn, {}, {"item_id": "x"}, {"table": "custom.results"})
        call_sql = conn.execute.call_args[0][0]
        assert "custom.results" in call_sql


# ─── Mode routing ───


class TestModeRouting:
    async def test_column_mapping_takes_priority(self):
        conn = _make_conn()
        sink = PostgreSQLSink()

        config = {
            "column_mapping": {"title": "title"},
            "mappings": [{"target_table": "articles", "strategy": "upsert"}],
            "table": "test_table",
        }
        output = {"title": "Test"}

        result = await sink._do_persist(conn, output, {}, config)
        # Should use column_mapping (INSERT), not legacy mappings
        assert "test_table" in result["tables_written"]

    async def test_mappings_over_fallback(self):
        conn = _make_conn()
        # Transaction mock
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock()
        tx.__aexit__ = AsyncMock(return_value=False)
        conn.transaction.return_value = tx
        conn.fetchrow = AsyncMock(side_effect=[{"id": 1}, {"id": 2}])

        sink = PostgreSQLSink()
        config = {"mappings": [{"target_table": "articles", "strategy": "upsert"}]}
        output = {"severity": "low", "summary": "t"}
        metadata = {"source_url": "http://x.com", "source_name": "x"}

        result = await sink._do_persist(conn, output, metadata, config)
        assert "articles" in result["tables_written"]


# ─── Connection routing (database_url_env) ───


class TestConnectionRouting:
    async def test_uses_own_connection_for_env(self):
        sink = PostgreSQLSink()
        output = {"title": "Test"}
        metadata = {}
        config = {
            "database_url_env": "PE_VOTOLIMPO_DATABASE_URL",
            "table": "test_table",
            "column_mapping": {"title": "title"},
        }

        mock_conn = _make_conn()
        default_conn = _make_conn()

        with (
            patch(
                "asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn
            ) as mock_connect,
            patch.dict("os.environ", {"PE_VOTOLIMPO_DATABASE_URL": "postgres://test"}),
        ):
            await sink.persist(output, metadata, config, default_conn)

        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()

    async def test_rejects_unlisted_env(self):
        sink = PostgreSQLSink()

        with pytest.raises(ValueError, match="not in whitelist"):
            await sink.persist(
                {}, {}, {"database_url_env": "EVIL_DB_URL"}, _make_conn()
            )
