"""Article Matcher — find related articles using 3-signal similarity."""

import logging
from typing import Any

import asyncpg

from . import validate_sql_identifier

logger = logging.getLogger(__name__)


class ArticleMatcher:
    """Match current article against recent articles by entity overlap,
    keyword overlap, and temporal proximity.

    Adds `matched_article_ids` to output.
    """

    async def process(
        self, output: dict, item_metadata: dict, pool: asyncpg.Pool, config: dict[str, Any],
    ) -> dict:
        match_table = validate_sql_identifier(
            config.get("match_table", "votolimpo.article_matches"), "match_table"
        )
        weights = config.get("weights", {
            "entity_overlap": 0.40,
            "keyword_overlap": 0.35,
            "temporal_proximity": 0.25,
        })
        persist_threshold = config.get("persist_threshold", 0.30)
        window_days = int(config.get("window_days", 30))

        article_id = output.get("article_id")
        if not article_id:
            return output

        matched_ids = []

        async with pool.acquire() as conn, conn.transaction():
            # Get current article data
            row = await conn.fetchrow("""
                SELECT a.keywords, a.published_at,
                       array_agg(pa.politician_id) as politician_ids
                FROM votolimpo.articles a
                LEFT JOIN votolimpo.politician_articles pa ON pa.article_id = a.id
                WHERE a.id = $1
                GROUP BY a.id
            """, article_id)
            if not row:
                return output

            keywords = row["keywords"] or []
            published = row["published_at"]
            pids = [x for x in (row["politician_ids"] or []) if x is not None]
            if not pids:
                output["matched_article_ids"] = []
                return output

            # Find candidates sharing politicians within window
            candidates = await conn.fetch("""
                SELECT a.id, a.keywords, a.published_at,
                       array_agg(pa.politician_id) as politician_ids
                FROM votolimpo.articles a
                JOIN votolimpo.politician_articles pa ON pa.article_id = a.id
                WHERE a.id != $1 AND a.published_at >= NOW() - ($3 * INTERVAL '1 day')
                  AND pa.politician_id = ANY($2)
                GROUP BY a.id
            """, article_id, pids, window_days)

            for cand in candidates:
                sim = _calculate_similarity(
                    {"keywords": keywords, "published_at": published, "politician_ids": pids},
                    {
                        "keywords": cand["keywords"] or [],
                        "published_at": cand["published_at"],
                        "politician_ids": [x for x in (cand["politician_ids"] or []) if x],
                    },
                    weights,
                )

                if sim["similarity"] >= persist_threshold:
                    a_id = min(article_id, cand["id"])
                    b_id = max(article_id, cand["id"])
                    await conn.execute(f"""
                        INSERT INTO {match_table}
                            (article_a_id, article_b_id, similarity,
                             entity_overlap, keyword_overlap, temporal_prox)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (article_a_id, article_b_id) DO UPDATE
                        SET similarity = EXCLUDED.similarity,
                            entity_overlap = EXCLUDED.entity_overlap,
                            keyword_overlap = EXCLUDED.keyword_overlap,
                            temporal_prox = EXCLUDED.temporal_prox
                    """, a_id, b_id, sim["similarity"],
                        sim["entity_overlap"], sim["keyword_overlap"], sim["temporal_prox"])
                    matched_ids.append(cand["id"])

        output["matched_article_ids"] = matched_ids
        return output


def _calculate_similarity(a: dict, b: dict, weights: dict) -> dict:
    """Calculate 3-signal similarity between two articles."""
    pols_a = set(a.get("politician_ids", []))
    pols_b = set(b.get("politician_ids", []))
    entity_overlap = len(pols_a & pols_b) / len(pols_a | pols_b) if pols_a | pols_b else 0.0

    kw_a = set(a.get("keywords", []) or [])
    kw_b = set(b.get("keywords", []) or [])
    keyword_overlap = len(kw_a & kw_b) / len(kw_a | kw_b) if kw_a | kw_b else 0.0

    pub_a, pub_b = a.get("published_at"), b.get("published_at")
    temporal_prox = 0.0
    if pub_a and pub_b:
        days = abs((pub_a - pub_b).days)
        temporal_prox = 1.0 if days <= 1 else 0.7 if days <= 7 else 0.3 if days <= 30 else 0.0

    similarity = (
        entity_overlap * weights.get("entity_overlap", 0.40)
        + keyword_overlap * weights.get("keyword_overlap", 0.35)
        + temporal_prox * weights.get("temporal_proximity", 0.25)
    )

    return {
        "similarity": round(similarity, 4),
        "entity_overlap": round(entity_overlap, 4),
        "keyword_overlap": round(keyword_overlap, 4),
        "temporal_prox": round(temporal_prox, 4),
    }
