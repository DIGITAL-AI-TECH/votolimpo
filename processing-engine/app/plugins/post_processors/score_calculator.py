"""Score Calculator — compute veracity score from weighted signals."""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


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
        sources_table = config.get("sources_table", "voto_limpo.sources")

        signals = output.get("veracity_signals", {})

        # Get source reputation from DB (best-effort — table may not exist in PE's DB)
        source_reputation = 0.50
        source_name = item_metadata.get("source_name")
        if source_name:
            try:
                from . import validate_sql_identifier

                validate_sql_identifier(sources_table, "sources_table")
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        f"SELECT reputation_score FROM {sources_table} WHERE name = $1",
                        source_name,
                    )
                    if row:
                        source_reputation = float(row["reputation_score"])
            except Exception:
                logger.debug("Source reputation table not available, using default 0.5")

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
