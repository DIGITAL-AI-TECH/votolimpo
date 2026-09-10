"""Sink plugins — persist processed output to target systems."""

import hashlib
import json
import logging
import os
from typing import Protocol

import asyncpg

from app.plugins.post_processors import validate_sql_identifier

logger = logging.getLogger(__name__)


class Sink(Protocol):
    """Protocol for sink plugins."""

    async def persist(
        self, output: dict, item_metadata: dict, config: dict, conn: asyncpg.Connection
    ) -> dict:
        """Persist processed output. Returns persistence details."""
        ...


class PostgreSQLSink:
    """Persist to PostgreSQL — supports column_mapping (new) and legacy mappings mode.

    Modes (checked in priority order):
    1. column_mapping: output fields → DB columns via dynamic INSERT/UPSERT
    2. mappings (legacy): strategy-based persistence per table
    3. fallback: simple JSONB insert (item_id + output)
    """

    async def persist(
        self, output: dict, item_metadata: dict, config: dict, conn: asyncpg.Connection
    ) -> dict:
        """Persist output. Handles connection routing for separate target DBs."""
        # C4 fix: allow separate target DB (whitelist of allowed env vars)
        ALLOWED_DB_ENVS = {"PE_VOTOLIMPO_DATABASE_URL", "PE_DATABASE_URL"}
        db_env = config.get("database_url_env")
        own_conn = None
        if db_env:
            if db_env not in ALLOWED_DB_ENVS:
                raise ValueError(
                    f"database_url_env '{db_env}' not in whitelist: {ALLOWED_DB_ENVS}"
                )
            target_url = os.environ.get(db_env)
            if target_url:
                own_conn = await asyncpg.connect(target_url, timeout=10)
                conn = own_conn

        try:
            result = await self._do_persist(conn, output, item_metadata, config)
        finally:
            if own_conn:
                await own_conn.close()

        return result

    async def _do_persist(self, conn, output, item_metadata, config) -> dict:
        """Route to the appropriate persistence mode."""
        result = {"tables_written": [], "article_id": None}

        if "column_mapping" in config:
            await self._persist_column_mapping(
                conn, output, item_metadata, config, result
            )
        elif "mappings" in config:
            await self._persist_legacy_mappings(
                conn, output, item_metadata, config, result
            )
        else:
            await self._persist_jsonb_fallback(
                conn, output, item_metadata, config, result
            )

        return result

    async def _persist_column_mapping(
        self, conn, output, item_metadata, config, result
    ):
        """Dynamic INSERT/UPSERT based on column_mapping config."""
        table = config.get("table")
        if not table:
            raise ValueError("column_mapping mode requires 'table' in sink config")
        validate_sql_identifier(table, "table")

        mapping = config["column_mapping"]
        conflict_column = config.get("conflict_column")
        if conflict_column:
            validate_sql_identifier(conflict_column, "conflict_column")

        columns = []
        values = []
        params = []

        # Validate all column names from config
        for db_col in mapping.values():
            validate_sql_identifier(db_col, "column")
        for col in config.get("static_columns", {}):
            validate_sql_identifier(col, "static_column")
        for db_col in config.get("item_field_mapping", {}).values():
            validate_sql_identifier(db_col, "item_field_column")
        if config.get("jsonb_fallback"):
            validate_sql_identifier(config["jsonb_fallback"], "jsonb_fallback_column")

        # Auto-generate url_hash from source_url when conflict_column is url_hash
        # (required for ON CONFLICT to work — url_hash must be in the INSERT)
        if conflict_column == "url_hash" and "url_hash" not in [
            v for v in mapping.values()
        ]:
            source_url = item_metadata.get("source_url", "")
            url_hash = hashlib.sha256(source_url.encode()).hexdigest()
            columns.append("url_hash")
            params.append(url_hash)
            values.append(f"${len(params)}")
            # Also ensure 'url' column is populated if not mapped
            if (
                "url" not in [v for v in mapping.values()]
                and "url" not in config.get("item_field_mapping", {}).values()
            ):
                columns.append("url")
                params.append(source_url)
                values.append(f"${len(params)}")

        # Type casts for enum/custom PostgreSQL types (e.g. {"severity": "votolimpo.severity_level"})
        type_casts = config.get("type_casts", {})

        # Map output fields → DB columns
        for output_key, db_col in mapping.items():
            val = output.get(output_key)
            if val is not None:
                columns.append(db_col)
                params.append(json.dumps(val) if isinstance(val, (dict, list)) else val)
                cast = type_casts.get(db_col, "")
                cast_suffix = f"::{cast}" if cast else ""
                values.append(f"${len(params)}{cast_suffix}")

        # Static columns (fixed values per row)
        for col, val in config.get("static_columns", {}).items():
            columns.append(col)
            params.append(val)
            cast = type_casts.get(col, "")
            cast_suffix = f"::{cast}" if cast else ""
            values.append(f"${len(params)}{cast_suffix}")

        # Item field mapping (item metadata → DB columns)
        for item_key, db_col in config.get("item_field_mapping", {}).items():
            val = item_metadata.get(item_key)
            if val is not None:
                columns.append(db_col)
                params.append(val)
                values.append(f"${len(params)}")

        # JSONB fallback column (full output as JSON)
        fallback_col = config.get("jsonb_fallback")
        if fallback_col:
            columns.append(fallback_col)
            params.append(json.dumps(output))
            values.append(f"${len(params)}::jsonb")

        if not columns:
            return

        if conflict_column:
            # UPSERT
            update_cols = [c for c in columns if c != conflict_column]
            update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            query = f"""
                INSERT INTO {table} ({", ".join(columns)})
                VALUES ({", ".join(values)})
                ON CONFLICT ({conflict_column}) DO UPDATE SET {update_clause}
                RETURNING id
            """
        else:
            query = f"""
                INSERT INTO {table} ({", ".join(columns)})
                VALUES ({", ".join(values)})
                RETURNING id
            """

        row = await conn.fetchrow(query, *params)
        if row:
            result["article_id"] = row["id"]
        result["tables_written"].append(table)

    async def _persist_legacy_mappings(
        self, conn, output, item_metadata, config, result
    ):
        """Legacy strategy-based persistence (backward compat with existing pipelines)."""
        mappings = config["mappings"]

        async with conn.transaction():
            for mapping in mappings:
                target_table = mapping.get("target_table", "")
                strategy = mapping.get("strategy", "insert")

                if target_table == "articles" and strategy == "upsert":
                    article_id = await self._upsert_article(conn, output, item_metadata)
                    result["article_id"] = article_id
                    result["tables_written"].append("articles")

        return result

    async def _upsert_article(
        self, conn: asyncpg.Connection, output: dict, metadata: dict
    ) -> int:
        """Upsert article into votolimpo.articles (legacy mode)."""
        url = metadata.get("source_url", "")
        url_hash = hashlib.sha256(url.encode()).hexdigest()

        # Upsert source
        source_name = metadata.get("source_name")
        source_id = None
        if source_name:
            row = await conn.fetchrow(
                """
                INSERT INTO votolimpo.sources (name, domain)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET
                    article_count = votolimpo.sources.article_count + 1,
                    updated_at = NOW()
                RETURNING id
            """,
                source_name,
                metadata.get("source_domain"),
            )
            if row:
                source_id = row["id"]

        article = output.get("article", output)
        keywords = output.get("keywords", article.get("keywords", []))
        if not isinstance(keywords, list):
            keywords = []

        row = await conn.fetchrow(
            """
            INSERT INTO votolimpo.articles
                (title, url, url_hash, source_id, published_at,
                 severity, summary, keywords, processing_status,
                 nc_article_id, raw_extraction, processed_at)
            VALUES ($1, $2, $3, $4, $5,
                    $6::votolimpo.severity_level, $7, $8,
                    'completed'::votolimpo.processing_status,
                    $9, $10, NOW())
            ON CONFLICT (url_hash) DO UPDATE SET
                processing_status = 'completed'::votolimpo.processing_status,
                severity = EXCLUDED.severity,
                summary = EXCLUDED.summary,
                keywords = EXCLUDED.keywords,
                raw_extraction = EXCLUDED.raw_extraction,
                processed_at = NOW(),
                updated_at = NOW()
            RETURNING id
        """,
            metadata.get("title", article.get("title", "")),
            url,
            url_hash,
            source_id,
            metadata.get("published_at"),
            output.get("severity", "low"),
            output.get("summary", ""),
            keywords,
            metadata.get("nc_article_id"),
            json.dumps(output),
        )
        return row["id"]

    async def _persist_jsonb_fallback(
        self, conn, output, item_metadata, config, result
    ):
        """Fallback: persist as simple JSONB (item_id + output)."""
        table = config.get("table", "processing_engine.results")
        validate_sql_identifier(table, "table")
        item_id = item_metadata.get("item_id", "unknown")
        await conn.execute(
            f"""
            INSERT INTO {table} (item_id, output)
            VALUES ($1, $2::jsonb)
            ON CONFLICT (item_id) DO UPDATE SET output = EXCLUDED.output
        """,
            item_id,
            json.dumps(output),
        )
        result["tables_written"].append(table)


# Registry
SINKS: dict[str, type] = {
    "postgresql": PostgreSQLSink,
}


def get_sink(sink_type: str) -> Sink:
    cls = SINKS.get(sink_type, PostgreSQLSink)
    return cls()
