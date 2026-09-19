"""Score Persister — persist veracity scores to score_history after each article."""

import json
import logging
from typing import Any

import asyncpg

from . import acquire_votolimpo_conn, validate_sql_identifier

logger = logging.getLogger(__name__)


class ScorePersister:
    """Persist score snapshots to votolimpo.score_history for each resolved politician.

    Runs AFTER score_calculator and entity_resolver in the post-processor chain.
    Reads `resolved_politician_ids`, `veracity_score`, and `score_components` from output.
    Adds `persisted_score_history_ids` to output.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        history_table = validate_sql_identifier(
            config.get("history_table", "votolimpo.score_history"), "history_table"
        )

        politician_ids = output.get("resolved_politician_ids", [])
        veracity_score = output.get("veracity_score")
        score_components = output.get("score_components")

        if not politician_ids or veracity_score is None:
            return output

        components_json = json.dumps(score_components) if score_components else None
        persisted_ids = []

        async with acquire_votolimpo_conn(pool) as conn:
            for politician_id in politician_ids:
                try:
                    row = await conn.fetchrow(
                        f"""
                        INSERT INTO {history_table}
                            (politician_id, score, score_components, article_count, calculated_at)
                        VALUES ($1, $2, $3::jsonb, 1, NOW())
                        RETURNING id
                    """,
                        politician_id,
                        veracity_score,
                        components_json,
                    )
                    if row:
                        persisted_ids.append(row["id"])
                except Exception as e:
                    logger.warning(
                        "Failed to persist score_history for politician %s: %s",
                        politician_id,
                        e,
                    )

        output["persisted_score_history_ids"] = persisted_ids
        return output
