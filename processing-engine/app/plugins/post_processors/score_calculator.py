"""Score Calculator — compute veracity score from weighted signals."""

import logging
import os
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Votolimpo DB pool for source reputation lookups.
# The main pool connects to processing_engine DB, but sources live in the
# votolimpo DB (managed by NC migrations + PE init_votolimpo_schema).
_votolimpo_pool: asyncpg.Pool | None = None
_votolimpo_dsn_resolved: str | None = None
_votolimpo_no_dsn = False  # True only when env var is absent (permanent)


async def _get_votolimpo_pool() -> asyncpg.Pool | None:
    """Get or create a pool for the votolimpo database.

    Retries on transient failures (connection refused) instead of giving up
    permanently. Only gives up permanently if the DSN env var is absent.
    """
    global _votolimpo_pool, _votolimpo_dsn_resolved, _votolimpo_no_dsn
    if _votolimpo_pool is not None:
        return _votolimpo_pool
    if _votolimpo_no_dsn:
        return None  # No DSN configured — permanent, no point retrying

    raw = os.environ.get("PE_VOTOLIMPO_DATABASE_URL") or os.environ.get(
        "VOTOLIMPO_DATABASE_URL", ""
    )
    if not raw:
        _votolimpo_no_dsn = True
        logger.warning("No VOTOLIMPO_DATABASE_URL — source reputation lookup will use engine pool")
        return None

    dsn = raw.replace("postgresql+asyncpg://", "postgresql://")
    _votolimpo_dsn_resolved = dsn
    try:
        _votolimpo_pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3, timeout=10)
        logger.info("Votolimpo pool created for source reputation lookups")
        return _votolimpo_pool
    except Exception as exc:
        # Do NOT set a permanent flag — allow retry on next call
        logger.warning("Failed to create votolimpo pool: %s — will use engine pool this time", exc)
        return None


class ScoreCalculator:
    """Calculate veracity score from 6 weighted signals.

    Pure computation — does NOT write to DB.
    Adds `veracity_score` and `score_components` to output.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        weights = config.get(
            "weights",
            {
                "source_reputation": 0.30,
                "multi_source": 0.25,
                "narrative_consistency": 0.15,
                "documental_evidence": 0.10,
                "temporality": 0.10,
                "emotional_language": 0.10,
            },
        )
        output_field = config.get("output_field", "veracity_score")
        sources_table = config.get("sources_table", "votolimpo.sources")

        signals = output.get("veracity_signals", {})

        # Use LLM-assessed source_reputation as baseline
        llm_source_reputation = _clamp(signals.get("source_reputation", 0.5))

        # Try to get source reputation from DB (overrides LLM if available)
        source_reputation = llm_source_reputation
        source_domain = item_metadata.get("source_domain") or item_metadata.get("source_name")
        if source_domain:
            try:
                from . import validate_sql_identifier

                validate_sql_identifier(sources_table, "sources_table")

                # Use votolimpo DB pool (separate from engine pool) for source lookups.
                # The engine pool connects to processing_engine DB where votolimpo
                # schema may not have seed data (migration 017 only runs in CI).
                vl_pool = await _get_votolimpo_pool()
                lookup_pool = vl_pool or pool  # fallback to engine pool
                async with lookup_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        f"SELECT reputation_score FROM {sources_table}"
                        f" WHERE domain = $1 OR $1 LIKE '%%' || domain || '%%'"
                        f" ORDER BY length(domain) DESC LIMIT 1",
                        source_domain,
                    )

                if row and row["reputation_score"] is not None:
                    source_reputation = float(row["reputation_score"])
                    logger.info(
                        "Source reputation from DB for '%s': %.2f (LLM was %.2f)",
                        source_domain,
                        source_reputation,
                        llm_source_reputation,
                    )
                else:
                    logger.info(
                        "Source '%s' not found in %s, using LLM value %.2f",
                        source_domain,
                        sources_table,
                        llm_source_reputation,
                    )
            except Exception as exc:
                logger.info(
                    "Source reputation lookup failed for '%s': %s — using LLM value %.2f",
                    source_domain,
                    exc,
                    llm_source_reputation,
                )

        # Normalize signals
        sr = source_reputation
        ms = _normalize_multi_source(signals.get("multi_source", 0))
        nc = _clamp(signals.get("narrative_consistency", 0.5))
        de = _clamp(signals.get("documental_evidence", 0.5))
        ts = _clamp(signals.get("temporality", 0.5))
        el = _clamp(signals.get("emotional_language", 0.5))

        # Weighted sum
        veracity = (
            sr * weights.get("source_reputation", 0.30)
            + ms * weights.get("multi_source", 0.25)
            + nc * weights.get("narrative_consistency", 0.15)
            + de * weights.get("documental_evidence", 0.10)
            + ts * weights.get("temporality", 0.10)
            + el * weights.get("emotional_language", 0.10)
        )

        components = {
            "source_reputation": round(sr, 4),
            "multi_source": round(ms, 4),
            "narrative_consistency": round(nc, 4),
            "documental_evidence": round(de, 4),
            "temporality": round(ts, 4),
            "emotional_language": round(el, 4),
        }

        output[output_field] = round(veracity, 4)
        output["score_components"] = components
        return output


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _normalize_multi_source(raw: float) -> float:
    """Normalize multi_source signal to [0, 1] range.

    Uses continuous clamping instead of discretization to preserve signal granularity.
    """
    return _clamp(raw, 0.0, 1.0)
