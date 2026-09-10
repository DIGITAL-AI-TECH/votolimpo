"""Cron jobs for the Processing Engine."""

import json
import logging
from math import exp, log2

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from openai import AsyncOpenAI

from ..config import settings
from ..storage.database import get_pool

logger = logging.getLogger(__name__)

# Politician score weights
SEVERITY_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 4.0, "critical": 8.0}
ROLE_WEIGHT = {"protagonist": 1.0, "investigated": 0.9, "mentioned": 0.5,
               "witness": 0.3, "victim": 0.2, "other": 0.1}


def _calculate_politician_score(articles: list[dict]) -> dict:
    """Sigmoid-normalized politician score."""
    if not articles:
        return {"score": 0.0, "components": {}}

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    weighted_sum = 0.0

    for a in articles:
        severity_w = SEVERITY_WEIGHT.get(a.get("severity", "low"), 1.0)
        role_w = ROLE_WEIGHT.get(a.get("role", "mentioned"), 0.5)
        veracity = a.get("veracity_score") or 0.5

        published = a.get("published_at")
        days_since = 30
        if published:
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            days_since = (now - published).days

        recency_decay = exp(-0.02 * max(0, days_since))
        weighted_sum += severity_w * role_w * veracity * recency_decay

    volume_bonus = log2(1 + len(articles))
    raw = weighted_sum + volume_bonus
    score = 100.0 / (1.0 + exp(-0.15 * (raw - 20)))

    return {
        "score": round(score, 2),
        "components": {
            "weighted_sum": round(weighted_sum, 4),
            "volume_bonus": round(volume_bonus, 4),
            "raw_score": round(raw, 4),
            "article_count": len(articles),
        },
    }


# H5 fix: batch query with JOIN+GROUP BY instead of N+1
async def cron_recalculate_scores():
    """Recalculate politician scores. Daily at 03:00 UTC."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Single query: fetch all articles grouped by politician
        rows = await conn.fetch("""
            SELECT pa.politician_id,
                   array_agg(json_build_object(
                       'severity', a.severity::text,
                       'role', pa.role::text,
                       'veracity_score', a.veracity_score,
                       'published_at', a.published_at
                   )::text) as articles_json
            FROM votolimpo.politician_articles pa
            JOIN votolimpo.articles a ON a.id = pa.article_id
            WHERE a.processing_status = 'completed'
            GROUP BY pa.politician_id
        """)

        updated = 0
        for row in rows:
            articles = [json.loads(a) for a in row["articles_json"]]
            # Convert published_at strings back to datetime
            from datetime import datetime, timezone
            for a in articles:
                if a.get("published_at"):
                    try:
                        a["published_at"] = datetime.fromisoformat(a["published_at"])
                    except (ValueError, TypeError):
                        a["published_at"] = None

            result = _calculate_politician_score(articles)

            await conn.execute("""
                UPDATE votolimpo.politicians
                SET score = $1, score_components = $2, total_articles = $3, updated_at = NOW()
                WHERE id = $4
            """, result["score"], json.dumps(result["components"]), len(articles), row["politician_id"])

            await conn.execute("""
                INSERT INTO votolimpo.score_history (politician_id, score, components)
                VALUES ($1, $2, $3)
            """, row["politician_id"], result["score"], json.dumps(result["components"]))
            updated += 1

    logger.info("Recalculated scores for %d politicians", updated)


async def cron_refresh_mvs():
    """Refresh materialized views. Every 6 hours."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY votolimpo.mv_article_relations")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY votolimpo.mv_global_stats")
    logger.info("Materialized views refreshed")


async def cron_regenerate_content():
    """Regenerate bios and AI summaries. Weekly Sunday 05:00 UTC."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Bios
        politicians = await conn.fetch("""
            SELECT id, name, party, state, role FROM votolimpo.politicians
            WHERE bio IS NULL OR updated_at < NOW() - INTERVAL '30 days'
        """)

    # Process OUTSIDE pool.acquire (LLM calls)
    bio_count = 0
    for p in politicians:
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "Você é um redator de enciclopédia política brasileira. "
                     "Gere uma biografia OBJETIVA e FACTUAL em 1-2 frases (máximo 200 caracteres). "
                     "Inclua: nome completo, partido atual, cargo atual ou mais relevante, estado. "
                     "NÃO inclua opinião, juízo de valor ou informações não confirmadas. "
                     "Responda APENAS com o texto da bio, sem aspas ou formatação."},
                    {"role": "user", "content": f"Nome: {p['name']}\nPartido: {p['party'] or 'N/I'}\n"
                     f"Estado: {p['state'] or 'N/I'}\nCargo: {p['role'] or 'N/I'}"},
                ],
                temperature=0.3, max_tokens=100,
            )
            bio = response.choices[0].message.content.strip()[:200]
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE votolimpo.politicians SET bio = $1, updated_at = NOW() WHERE id = $2",
                    bio, p["id"])
            bio_count += 1
        except Exception:
            logger.exception("Failed bio for politician %d", p["id"])

    # Summaries
    async with pool.acquire() as conn:
        pols_need_summary = await conn.fetch("""
            SELECT id FROM votolimpo.politicians
            WHERE total_articles >= 5
              AND (ai_summary IS NULL OR updated_at < NOW() - INTERVAL '7 days')
        """)

    summary_count = 0
    for p in pols_need_summary:
        try:
            async with pool.acquire() as conn:
                articles = await conn.fetch("""
                    SELECT a.title, a.summary, a.severity::text, a.published_at, pa.role::text
                    FROM votolimpo.articles a
                    JOIN votolimpo.politician_articles pa ON pa.article_id = a.id
                    WHERE pa.politician_id = $1 AND a.processing_status = 'completed'
                    ORDER BY CASE a.severity
                        WHEN 'critical' THEN 4 WHEN 'high' THEN 3
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 1 END DESC,
                        a.published_at DESC
                    LIMIT 20
                """, p["id"])

                if len(articles) < 5:
                    continue

                pol = await conn.fetchrow(
                    "SELECT name, party, state FROM votolimpo.politicians WHERE id = $1", p["id"])
                if not pol:
                    continue

            articles_text = "\n".join([
                f"- [{a['published_at'].strftime('%d/%m/%Y') if a['published_at'] else '?'}] "
                f"({a['severity']}) {a['title']}" + (f" — {a['summary']}" if a["summary"] else "")
                for a in articles
            ])

            response = await client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": "Você é um analista político imparcial. "
                     "Resuma a atuação recente do político em 3-5 frases (máximo 600 caracteres). "
                     "Base-se EXCLUSIVAMENTE nos títulos e resumos dos artigos fornecidos. "
                     "NÃO invente fatos. Responda APENAS com o texto do resumo."},
                    {"role": "user", "content": f"Resuma {pol['name']} ({pol['party'] or '?'}/{pol['state'] or '?'}).\n\n{articles_text}"},
                ],
                temperature=0.3, max_tokens=300,
            )
            summary = response.choices[0].message.content.strip()[:600]
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE votolimpo.politicians SET ai_summary = $1, updated_at = NOW() WHERE id = $2",
                    summary, p["id"])
            summary_count += 1
        except Exception:
            logger.exception("Failed summary for politician %d", p["id"])

    logger.info("Content regeneration: %d bios, %d summaries", bio_count, summary_count)


# H7 fix: correct schema from votolimpo → processing_engine
async def cron_cleanup_logs():
    """Delete processing logs older than 90 days. Monthly."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM processing_engine.processing_logs WHERE created_at < NOW() - INTERVAL '90 days'")
    logger.info("Cleaned up old processing logs")


async def cron_deactivate_stale_clusters():
    """Deactivate clusters with no activity in 30 days. Daily."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE votolimpo.news_clusters SET is_active = false, updated_at = NOW()
            WHERE is_active = true AND last_article < NOW() - INTERVAL '30 days'
        """)
    logger.info("Deactivated stale clusters")


# H4 fix: create new scheduler instance each time, protect against double-start
_scheduler: AsyncIOScheduler | None = None


def setup_cron_scheduler() -> AsyncIOScheduler:
    """Configure all cron jobs and return a NEW scheduler instance."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(cron_recalculate_scores,
                       CronTrigger(hour=3, minute=0, timezone="UTC"),
                       id="pe_scores", replace_existing=True)
    _scheduler.add_job(cron_refresh_mvs,
                       CronTrigger(hour="*/6", minute=15, timezone="UTC"),
                       id="pe_mvs", replace_existing=True)
    _scheduler.add_job(cron_regenerate_content,
                       CronTrigger(day_of_week="sun", hour=5, minute=0, timezone="UTC"),
                       id="pe_content", replace_existing=True)
    _scheduler.add_job(cron_cleanup_logs,
                       CronTrigger(day=1, hour=2, minute=0, timezone="UTC"),
                       id="pe_cleanup", replace_existing=True)
    _scheduler.add_job(cron_deactivate_stale_clusters,
                       CronTrigger(hour=4, minute=0, timezone="UTC"),
                       id="pe_clusters", replace_existing=True)
    logger.info("Cron scheduler configured (5 jobs)")
    return _scheduler
