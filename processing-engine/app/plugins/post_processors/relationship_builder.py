"""Relationship Builder — build entity relationship graph with evidence."""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class RelationshipBuilder:
    """Build relationships between resolved entities with incremental weight.

    Adds `persisted_relationship_ids` to output.
    """

    async def process(
        self, output: dict, item_metadata: dict, pool: asyncpg.Pool, config: dict[str, Any],
    ) -> dict:
        relationship_table = config.get("relationship_table", "votolimpo.relationships")
        evidence_table = config.get("evidence_table", "votolimpo.relationship_evidence")

        # Build entity ID map from resolved entities
        entity_id_map: dict[str, int] = {}
        for ent in output.get("entities", []):
            if ent.get("name") and ent.get("resolved_id"):
                entity_id_map[ent["name"]] = ent["resolved_id"]
        for pol in output.get("politicians", []):
            if pol.get("name") and pol.get("resolved_id"):
                entity_id_map[pol["name"]] = pol["resolved_id"]

        article_id = output.get("article_id")
        persisted_ids = []

        async with pool.acquire() as conn:
            for rel in output.get("relationships", []):
                src_id = entity_id_map.get(rel.get("source"))
                tgt_id = entity_id_map.get(rel.get("target"))
                rel_type = rel.get("type")
                if not src_id or not tgt_id or not rel_type:
                    continue

                row = await conn.fetchrow(f"""
                    INSERT INTO {relationship_table}
                        (source_id, target_id, source_type, target_type, type, weight)
                    VALUES ($1, $2, 'entity', 'entity', $3::votolimpo.relationship_type, 1)
                    ON CONFLICT (source_id, target_id, source_type, target_type, type)
                    DO UPDATE SET weight = {relationship_table}.weight + 1,
                                  last_seen_at = NOW(), updated_at = NOW()
                    RETURNING id
                """, src_id, tgt_id, rel_type)

                if row:
                    persisted_ids.append(row["id"])
                    if rel.get("evidence") and article_id:
                        await conn.execute(f"""
                            INSERT INTO {evidence_table}
                                (relationship_id, article_id, excerpt)
                            VALUES ($1, $2, $3)
                        """, row["id"], article_id, rel["evidence"])

        output["persisted_relationship_ids"] = persisted_ids
        return output
