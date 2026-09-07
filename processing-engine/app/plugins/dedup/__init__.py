from __future__ import annotations

from app.plugins.dedup.composite import CompositeDedupStrategy
from app.plugins.dedup.hash import HashDedupStrategy
from app.plugins.dedup.semantic import SemanticDedupStrategy
from app.plugins.registry import register

register("dedup", "hash", HashDedupStrategy)
register("dedup", "semantic", SemanticDedupStrategy)
register("dedup", "composite", CompositeDedupStrategy)

__all__ = ["HashDedupStrategy", "SemanticDedupStrategy", "CompositeDedupStrategy"]
