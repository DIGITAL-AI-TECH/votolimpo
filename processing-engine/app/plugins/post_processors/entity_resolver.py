"""Entity Resolver — resolve politician/entity names to DB IDs via pg_trgm fuzzy matching."""

import logging
from typing import Any

import asyncpg

from . import (
    acquire_votolimpo_conn,
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
            config.get("politician_table", "votolimpo.politicians"), "politician_table"
        )
        entity_table = validate_sql_identifier(
            config.get("entity_table", "votolimpo.entities"), "entity_table"
        )
        fuzzy_threshold = config.get("fuzzy_threshold", 0.80)
        fuzzy_party_threshold = config.get("fuzzy_party_threshold", 0.70)
        entity_fuzzy_threshold = config.get("entity_fuzzy_threshold", 0.85)

        resolved_politician_ids = []
        resolved_entity_ids = []

        async with acquire_votolimpo_conn(pool) as conn, conn.transaction():
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

            # Link politicians to article via politician_articles (post-sink: article_id available)
            article_id = output.get("article_id")
            if article_id and resolved_politician_ids:
                # Map article_role from LLM output to NC enum values
                role_map = {
                    "protagonist": "protagonist",
                    "mentioned": "mentioned",
                    "investigated": "investigated",
                    "witness": "witness",
                    "victim": "victim",
                    "other": "other",
                    "subject": "protagonist",  # legacy PE mapping
                    "related": "mentioned",  # legacy PE mapping
                }
                for pol in output.get("politicians", []):
                    pid = pol.get("resolved_id")
                    if not pid:
                        continue
                    raw_role = pol.get("article_role", "mentioned")
                    nc_role = role_map.get(raw_role, "mentioned")
                    relevance = pol.get("relevance_score")
                    try:
                        await conn.execute(
                            """
                            INSERT INTO votolimpo.politician_articles
                                (politician_id, article_id, role, relevance_score)
                            VALUES ($1, $2, $3::votolimpo.article_role, $4)
                            ON CONFLICT (politician_id, article_id) DO UPDATE
                            SET role = EXCLUDED.role, relevance_score = EXCLUDED.relevance_score
                        """,
                            pid,
                            article_id,
                            nc_role,
                            relevance,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to link politician %s to article %s: %s",
                            pid,
                            article_id,
                            e,
                        )

            # Resolve entities — supports both formats:
            #   1. "entities": [{name, type}]  (structured, preferred)
            #   2. "entity_names": ["str"]     (LLM output schema returns this)
            entities_list = output.get("entities", [])
            if not entities_list:
                # Fallback: convert entity_names (strings) to entity objects
                entity_names = output.get("entity_names", [])
                # Build set of resolved politician names to avoid duplicating them as entities
                resolved_politician_names = {
                    normalize_for_search(pol.get("name", ""))
                    for pol in output.get("politicians", [])
                    if pol.get("name")
                }
                for raw_name in entity_names:
                    if not raw_name or not isinstance(raw_name, str):
                        continue
                    # Skip names that are already resolved politicians
                    if normalize_for_search(raw_name) in resolved_politician_names:
                        continue
                    entities_list.append({"name": raw_name, "type": "organization"})

            for ent in entities_list:
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
        """Resolve entity: exact normalized → fuzzy → create.

        NC schema (002_create_tables.sql): entities uses 'type' column (not 'entity_type')
        with enum values: person, organization, location, event, concept.
        """
        norm = normalize_for_search(name)

        # Map PE entity types to NC enum values if needed
        nc_type = _map_entity_type(ent_type)

        # Exact normalized match
        row = await conn.fetchrow(
            f"""
            SELECT id FROM {table}
            WHERE normalized_name = $1 AND type = $2::votolimpo.entity_type
        """,
            norm,
            nc_type,
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
              AND type = $3::votolimpo.entity_type
            ORDER BY similarity(normalized_name, $1) DESC LIMIT 1
        """,
            norm,
            fuzzy_threshold,
            nc_type,
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
            VALUES ($1, $2, $3::votolimpo.entity_type, 1)
            RETURNING id
        """,
            clean_name,
            norm,
            nc_type,
        )
        return row["id"]


# NC entity_type enum: person, organization, location, event, concept
# Map any non-NC values to the closest NC equivalent
_ENTITY_TYPE_MAP = {
    "company": "organization",
    "lobby": "organization",
    "ngo": "organization",
    "person": "person",
    "organization": "organization",
    "location": "location",
    "event": "event",
    "concept": "concept",
}


def _map_entity_type(ent_type: str) -> str:
    """Map entity type to NC-compatible enum value."""
    return _ENTITY_TYPE_MAP.get(ent_type.lower(), "organization")
