from __future__ import annotations

import json
from typing import Any


class PostgreSQLSink:
    """Sink that upserts processed output into a PostgreSQL table.

    sink_config keys:
        table            : str — fully qualified table name, e.g. "myschema.results"
        conflict_column  : str — column used in ON CONFLICT clause, e.g. "item_id"

    The sink performs an INSERT … ON CONFLICT DO UPDATE, storing the full output
    dict as a JSONB column named "output". The item_id is always stored as well.

    Example sink_config:
        {
            "table": "voto_limpo.candidates",
            "conflict_column": "item_id"
        }
    """

    async def persist(
        self,
        item_id: str,
        output: dict,
        config: dict,
        conn: Any,
    ) -> None:
        table = config.get("table")
        if not table:
            # No target table configured — output is already stored in the items table
            return
        conflict_column = config.get("conflict_column", "item_id")

        # Validate table name to avoid SQL injection (only allow schema.table format)
        _validate_table_name(table)
        _validate_identifier(conflict_column)

        output_json = json.dumps(output)

        # Dynamic upsert: insert with item_id + output, update on conflict
        query = f"""
            INSERT INTO {table} (item_id, output, updated_at)
            VALUES ($1, $2::jsonb, NOW())
            ON CONFLICT ({conflict_column}) DO UPDATE
                SET output = EXCLUDED.output,
                    updated_at = EXCLUDED.updated_at
        """

        await conn.execute(query, item_id, output_json)


def _validate_table_name(name: str) -> None:
    """Validate that table name is in schema.table format with safe characters."""
    import re

    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$"
    if not re.match(pattern, name):
        raise ValueError(
            f"Invalid table name '{name}'. "
            "Expected format: 'schema.table' with alphanumeric/underscore characters only."
        )


def _validate_identifier(name: str) -> None:
    """Validate a SQL identifier (column name)."""
    import re

    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
    if not re.match(pattern, name):
        raise ValueError(
            f"Invalid identifier '{name}'. "
            "Only alphanumeric characters and underscores are allowed."
        )
