"""Dedup plugins — detect duplicate content before LLM processing.

All strategies implement DedupStrategy (from protocols.py) and accept
``current_item_id`` to prevent self-match — the item being processed may
already exist in the table with its hashes populated by the AutoBatcher.
"""

from __future__ import annotations

from typing import Any

from app.plugins.dedup.composite import CompositeDedupStrategy
from app.plugins.dedup.hash import HashDedupStrategy
from app.plugins.dedup.semantic import SemanticDedupStrategy
from app.plugins.protocols import DedupResult, DedupStrategy


class NoneDedup:
    """No-op dedup — always returns 'new'."""

    async def check(
        self,
        content: str,
        url: str | None,
        pipeline_id: str,
        conn: Any,
        current_item_id: str | None = None,
    ) -> DedupResult:
        return DedupResult(is_duplicate=False, strategy="none")


DEDUP_STRATEGIES: dict[str, type] = {
    "hash": HashDedupStrategy,
    "composite": CompositeDedupStrategy,
    "semantic": SemanticDedupStrategy,
    "none": NoneDedup,
}

# Populate global registry
from app.plugins.registry import register as _register

for _name, _cls in DEDUP_STRATEGIES.items():
    _register("dedup", _name, _cls)


def get_dedup(strategy: str) -> DedupStrategy:
    """Get a dedup strategy by name. Defaults to HashDedupStrategy."""
    cls = DEDUP_STRATEGIES.get(strategy, HashDedupStrategy)
    return cls()
