"""Cluster Updater — group related articles into news clusters."""

import logging
from typing import Any

import asyncpg

from . import validate_sql_identifier

logger = logging.getLogger(__name__)


class ClusterUpdater:
    """Group articles into clusters based on high-similarity matches.

    Adds `cluster_id` to output.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        cluster_table = validate_sql_identifier(
            config.get("cluster_table", "votolimpo.news_clusters"), "cluster_table"
        )
        cluster_articles_table = validate_sql_identifier(
            config.get("cluster_articles_table", "votolimpo.cluster_articles"),
            "cluster_articles_table",
        )
        cluster_politicians_table = validate_sql_identifier(
            config.get("cluster_politicians_table", "votolimpo.cluster_politicians"),
            "cluster_politicians_table",
        )
        similarity_threshold = config.get("similarity_threshold", 0.50)

        article_id = output.get("article_id")
        if not article_id:
            return output

        async with pool.acquire() as conn, conn.transaction():
            # Find high-similarity matches
            matches = await conn.fetch(
                """
                SELECT article_a_id, article_b_id
                FROM votolimpo.article_matches
                WHERE (article_a_id = $1 OR article_b_id = $1) AND similarity >= $2
            """,
                article_id,
                similarity_threshold,
            )

            if not matches:
                return output

            related_ids = set()
            for m in matches:
                related_ids.add(m["article_a_id"])
                related_ids.add(m["article_b_id"])

            # Find existing cluster for any related article
            row = await conn.fetchrow(
                f"""
                SELECT cluster_id FROM {cluster_articles_table}
                WHERE article_id = ANY($1) LIMIT 1
            """,
                list(related_ids),
            )

            if row:
                cluster_id = row["cluster_id"]
            else:
                row = await conn.fetchrow(f"""
                    INSERT INTO {cluster_table} (title, article_count)
                    VALUES ('Auto-generated cluster', 0) RETURNING id
                """)
                cluster_id = row["id"]

            # Add article to cluster
            await conn.execute(
                f"""
                INSERT INTO {cluster_articles_table} (cluster_id, article_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """,
                cluster_id,
                article_id,
            )

            # Update cluster stats
            await conn.execute(
                f"""
                UPDATE {cluster_table} SET
                    article_count = (SELECT COUNT(*) FROM {cluster_articles_table} WHERE cluster_id = $1),
                    first_article = (SELECT MIN(a.published_at) FROM votolimpo.articles a
                        JOIN {cluster_articles_table} ca ON ca.article_id = a.id WHERE ca.cluster_id = $1),
                    last_article = (SELECT MAX(a.published_at) FROM votolimpo.articles a
                        JOIN {cluster_articles_table} ca ON ca.article_id = a.id WHERE ca.cluster_id = $1),
                    updated_at = NOW()
                WHERE id = $1
            """,
                cluster_id,
            )

            # Update cluster_politicians
            pols = await conn.fetch(
                f"""
                SELECT pa.politician_id, COUNT(*) as cnt
                FROM votolimpo.politician_articles pa
                JOIN {cluster_articles_table} ca ON ca.article_id = pa.article_id
                WHERE ca.cluster_id = $1 GROUP BY pa.politician_id
            """,
                cluster_id,
            )
            for p in pols:
                await conn.execute(
                    f"""
                    INSERT INTO {cluster_politicians_table} (cluster_id, politician_id, article_count)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (cluster_id, politician_id) DO UPDATE SET article_count = EXCLUDED.article_count
                """,
                    cluster_id,
                    p["politician_id"],
                    p["cnt"],
                )

        output["cluster_id"] = cluster_id
        return output
