"""Milestone Detector — detect and dedup political/legal milestones.

NC schema (002_create_tables.sql):
    milestones.politician_id INTEGER REFERENCES politicians(id)
    milestones.article_id    INTEGER REFERENCES articles(id)
    milestones.type          milestone_type NOT NULL  (column name is 'type')
    milestones.date          DATE NOT NULL
    milestones.confidence    DECIMAL(3,2) NOT NULL
"""

import logging
from datetime import date as date_type
from typing import Any

import asyncpg

from . import acquire_votolimpo_conn, normalize_for_search, validate_sql_identifier

logger = logging.getLogger(__name__)


class MilestoneDetector:
    """Detect milestones from LLM output with confidence threshold and dedup window.

    Adds `persisted_milestone_ids` to output.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        milestone_table = validate_sql_identifier(
            config.get("milestone_table", "votolimpo.milestones"), "milestone_table"
        )
        confidence_threshold = config.get("confidence_threshold", 0.70)
        dedup_window_days = int(config.get("dedup_window_days", 7))

        # Map politician names to resolved IDs (case-insensitive normalized)
        politician_id_map: dict[str, int] = {}
        for pol in output.get("politicians", []):
            if pol.get("name") and pol.get("resolved_id"):
                politician_id_map[pol["name"]] = pol["resolved_id"]
                # Also index by normalized name for fuzzy matching
                politician_id_map[normalize_for_search(pol["name"])] = pol[
                    "resolved_id"
                ]

        article_id = output.get("article_id")
        milestones = output.get("milestones", [])
        if not milestones:
            output["persisted_milestone_ids"] = []
            return output

        persisted_ids = []

        async with acquire_votolimpo_conn(pool) as conn, conn.transaction():
            for m in milestones:
                confidence = m.get("confidence", 0)
                if confidence < confidence_threshold:
                    logger.debug(
                        "Milestone skipped (confidence %.2f < %.2f): %s",
                        confidence,
                        confidence_threshold,
                        m.get("title", "?"),
                    )
                    continue

                politician_name = m.get("politician_name")
                if not politician_name:
                    continue

                # Look up politician ID by exact name or normalized name
                politician_id = politician_id_map.get(
                    politician_name
                ) or politician_id_map.get(normalize_for_search(politician_name))
                if not politician_id:
                    logger.debug(
                        "Milestone skipped (politician '%s' not resolved): %s",
                        politician_name,
                        m.get("title", "?"),
                    )
                    continue

                milestone_type = m.get("type")
                milestone_date = m.get("date")
                if not milestone_type or not milestone_date:
                    continue

                # Parse date string to date object if needed
                if isinstance(milestone_date, str):
                    try:
                        milestone_date = date_type.fromisoformat(milestone_date)
                    except ValueError:
                        logger.warning(
                            "Invalid milestone date '%s', skipping", milestone_date
                        )
                        continue

                # Dedup: same politician + type within window
                # NC schema: column is 'date' and 'type' (not 'milestone_type' / 'occurred_at')
                existing = await conn.fetchrow(
                    f"""
                    SELECT id FROM {milestone_table}
                    WHERE politician_id = $1
                      AND type = $2::votolimpo.milestone_type
                      AND "date" BETWEEN ($3::date - $4 * INTERVAL '1 day')::date
                                      AND ($3::date + $4 * INTERVAL '1 day')::date
                """,
                    politician_id,
                    milestone_type,
                    milestone_date,
                    dedup_window_days,
                )

                if existing:
                    logger.debug(
                        "Milestone deduped (existing %s): %s",
                        existing["id"],
                        m.get("title", "?"),
                    )
                    continue

                try:
                    row = await conn.fetchrow(
                        f"""
                        INSERT INTO {milestone_table}
                            (politician_id, article_id, type, title, description, "date", confidence)
                        VALUES ($1, $2, $3::votolimpo.milestone_type, $4, $5, $6, $7)
                        RETURNING id
                    """,
                        politician_id,
                        article_id,
                        milestone_type,
                        m.get("title"),
                        m.get("description"),
                        milestone_date,
                        confidence,
                    )

                    if row:
                        persisted_ids.append(row["id"])
                        logger.info(
                            "Milestone persisted: id=%s type=%s politician=%s",
                            row["id"],
                            milestone_type,
                            politician_name,
                        )
                except Exception as e:
                    logger.error(
                        "Failed to insert milestone for %s: %s", politician_name, e
                    )

        output["persisted_milestone_ids"] = persisted_ids
        return output
