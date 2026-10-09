"""Post-processor: HelpCoreScoreRecalculator

Deterministically recalculates overall_score and priority_level from the
5 quality sub-scores returned by the LLM. This ensures consistency —
the LLM may round or apply slightly different weights.

MUST run BEFORE markdown_generator (which may use these values).
"""

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Weights matching the system prompt definition
WEIGHTS = {
    "clarity": 0.30,
    "structure": 0.25,
    "completeness": 0.25,
    "accuracy_signals": 0.10,
    "readability": 0.10,
}

PRIORITY_THRESHOLDS = [
    (30, "critical"),
    (50, "high"),
    (70, "medium"),
]


class HelpCoreScoreRecalculator:
    """Recalculate overall_score and priority_level from LLM sub-scores."""

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        quality = output.get("quality")
        if not quality:
            logger.warning("No quality block in output — skipping score recalculation")
            return output

        # Calculate weighted average
        score = sum(
            quality.get(dim, 0) * weight
            for dim, weight in WEIGHTS.items()
        )
        score = round(score, 2)

        # Determine priority level
        priority = "low"
        for threshold, level in PRIORITY_THRESHOLDS:
            if score < threshold:
                priority = level
                break

        # Log if LLM values differ
        llm_score = quality.get("overall_score")
        llm_priority = quality.get("priority_level")
        if llm_score is not None and abs(llm_score - score) > 0.5:
            logger.info(
                "Score recalculated: LLM=%.2f → deterministic=%.2f (delta=%.2f)",
                llm_score, score, abs(llm_score - score),
            )
        if llm_priority and llm_priority != priority:
            logger.info(
                "Priority recalculated: LLM=%s → deterministic=%s (score=%.2f)",
                llm_priority, priority, score,
            )

        # Overwrite with deterministic values
        quality["overall_score"] = score
        quality["priority_level"] = priority

        return output
