"""Entity Resolver — resolve politician/entity names to DB IDs via pg_trgm fuzzy matching."""

import logging
from typing import Any

import asyncpg

from . import (
    generate_slug,
    normalize_entity_name,
    normalize_for_search,
    validate_sql_identifier,
)

logger = logging.getLogger(__name__)


class EntityResolver:
    """Resolve named entities from LLM output to database IDs.

    Cascade: exact match → fuzzy(threshold) → fuzzy+party → create new.
    Adds `resolved_politician_ids` and `resolved_entity_ids` to output.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        politician_table = validate_sql_identifier(
            config.get("politician_table", "voto_limpo.politicians"), "politician_table"
        )
        entity_table = validate_sql_identifier(
            config.get("entity_table", "voto_limpo.entities"), "entity_table"
        )
        fuzzy_threshold = config.get("fuzzy_threshold", 0.80)
        fuzzy_party_threshold = config.get("fuzzy_party_threshold", 0.70)
        entity_fuzzy_threshold = config.get("entity_fuzzy_threshold", 0.85)

        resolved_politician_ids = []
        resolved_entity_ids = []

        async with pool.acquire() as conn, conn.transaction():
            # Resolve politicians
            for pol in output.get("politicians", []):
                name = pol.get("name")
                if not name:
                    continue
                politician_id = await self._resolve_politician(
                    conn,
                    name,
                    pol.get("party"),
                    pol.get("state"),
                    politician_table,
                    fuzzy_threshold,
                    fuzzy_party_threshold,
                )
                pol["resolved_id"] = politician_id
                resolved_politician_ids.append(politician_id)

                # Update metadata if available
                if pol.get("role"):
                    await conn.execute(
                        f"""
                        UPDATE {politician_table}
                        SET role = COALESCE($1, role), updated_at = NOW()
                        WHERE id = $2 AND role IS NULL
                    """,
                        pol.get("role"),
                        politician_id,
                    )

            # Resolve entities
            for ent in output.get("entities", []):
                name = ent.get("name")
                ent_type = ent.get("type")
                if not name or not ent_type:
                    continue
                entity_id = await self._resolve_entity(
                    conn,
                    name,
                    ent_type,
                    entity_table,
                    entity_fuzzy_threshold,
                )
                ent["resolved_id"] = entity_id
                resolved_entity_ids.append(entity_id)

        output["resolved_politician_ids"] = resolved_politician_ids
        output["resolved_entity_ids"] = resolved_entity_ids
        return output

    async def _resolve_politician(
        self,
        conn: asyncpg.Connection,
        name: str,
        party: str | None,
        state: str | None,
        table: str,
        fuzzy_threshold: float,
        fuzzy_party_threshold: float,
    ) -> int:
        """Resolve politician: exact → fuzzy → fuzzy+party → create."""
        normalized = normalize_for_search(name)

        # Exact match
        row = await conn.fetchrow(
            f"SELECT id FROM {table} WHERE lower(name) = lower($1)",
            name.strip(),
        )
        if row:
            return row["id"]

        # Fuzzy match
        row = await conn.fetchrow(
            f"""
            SELECT id, similarity(lower(name), $1) as sim
            FROM {table}
            WHERE similarity(lower(name), $1) > $2
            ORDER BY sim DESC LIMIT 1
        """,
            normalized,
            fuzzy_threshold,
        )
        if row:
            return row["id"]

        # Fuzzy + party
        if party:
            row = await conn.fetchrow(
                f"""
                SELECT id FROM {table}
                WHERE similarity(lower(name), $1) > $2
                  AND lower(party) = lower($3)
                ORDER BY similarity(lower(name), $1) DESC LIMIT 1
            """,
                normalized,
                fuzzy_party_threshold,
                party,
            )
            if row:
                return row["id"]

        # Create new
        slug = generate_slug(name)
        row = await conn.fetchrow(
            f"""
            INSERT INTO {table} (name, slug, party, state)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """,
            name.strip(),
            slug,
            party,
            state,
        )
        return row["id"]

    async def _resolve_entity(
        self,
        conn: asyncpg.Connection,
        name: str,
        ent_type: str,
        table: str,
        fuzzy_threshold: float,
    ) -> int:
        """Resolve entity: exact normalized → fuzzy → create."""
        norm = normalize_for_search(name)

        # Exact normalized match
        row = await conn.fetchrow(
            f"""
            SELECT id FROM {table}
            WHERE normalized_name = $1 AND type = $2::voto_limpo.entity_type
        """,
            norm,
            ent_type,
        )
        if row:
            await conn.execute(
                f"""
                UPDATE {table}
                SET last_seen_at = NOW(), article_count = article_count + 1
                WHERE id = $1
            """,
                row["id"],
            )
            return row["id"]

        # Fuzzy match
        row = await conn.fetchrow(
            f"""
            SELECT id FROM {table}
            WHERE similarity(normalized_name, $1) > $2
              AND type = $3::voto_limpo.entity_type
            ORDER BY similarity(normalized_name, $1) DESC LIMIT 1
        """,
            norm,
            fuzzy_threshold,
            ent_type,
        )
        if row:
            await conn.execute(
                f"""
                UPDATE {table}
                SET last_seen_at = NOW(), article_count = article_count + 1
                WHERE id = $1
            """,
                row["id"],
            )
            return row["id"]

        # Create new
        clean_name = normalize_entity_name(name)
        row = await conn.fetchrow(
            f"""
            INSERT INTO {table} (name, normalized_name, type, article_count)
            VALUES ($1, $2, $3::voto_limpo.entity_type, 1)
            RETURNING id
        """,
            clean_name,
            norm,
            ent_type,
        )
        return row["id"]
