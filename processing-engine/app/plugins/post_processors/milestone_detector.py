"""Milestone Detector — detect and dedup political/legal milestones."""

import logging
from typing import Any

import asyncpg

from . import validate_sql_identifier

logger = logging.getLogger(__name__)


class MilestoneDetector:
    """Detect milestones from LLM output with confidence threshold and dedup window.

    Adds `persisted_milestone_ids` to output.
    """

    async def process(
        self, output: dict, item_metadata: dict, pool: asyncpg.Pool, config: dict[str, Any],
    ) -> dict:
        milestone_table = validate_sql_identifier(
            config.get("milestone_table", "votolimpo.milestones"), "milestone_table"
        )
        confidence_threshold = config.get("confidence_threshold", 0.70)
        dedup_window_days = int(config.get("dedup_window_days", 7))

        # Map politician names to resolved IDs
        politician_id_map: dict[str, int] = {}
        for pol in output.get("politicians", []):
            if pol.get("name") and pol.get("resolved_id"):
                politician_id_map[pol["name"]] = pol["resolved_id"]

        article_id = output.get("article_id")
        persisted_ids = []

        async with pool.acquire() as conn, conn.transaction():
            for m in output.get("milestones", []):
                confidence = m.get("confidence", 0)
                if confidence < confidence_threshold:
                    continue

                politician_name = m.get("politician_name")
                if not politician_name:
                    continue

                politician_id = politician_id_map.get(politician_name)
                if not politician_id:
                    # Try to find from resolved_politician_ids (fallback)
                    continue

                milestone_type = m.get("type")
                milestone_date = m.get("date")
                if not milestone_type or not milestone_date:
                    continue

                # Dedup: same politician + type within window
                existing = await conn.fetchrow(f"""
                    SELECT id FROM {milestone_table}
                    WHERE politician_id = $1 AND type = $2::votolimpo.milestone_type
                      AND ABS(date - $3::date) <= $4
                """, politician_id, milestone_type, milestone_date, dedup_window_days)

                if existing:
                    continue

                row = await conn.fetchrow(f"""
                    INSERT INTO {milestone_table}
                        (politician_id, article_id, type, title, description, date, confidence)
                    VALUES ($1, $2, $3::votolimpo.milestone_type, $4, $5, $6, $7)
                    RETURNING id
                """, politician_id, article_id, milestone_type,
                    m.get("title"), m.get("description"), milestone_date, confidence)

                if row:
                    persisted_ids.append(row["id"])

        output["persisted_milestone_ids"] = persisted_ids
        return output
