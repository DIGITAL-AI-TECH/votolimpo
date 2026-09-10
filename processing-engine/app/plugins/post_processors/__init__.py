"""Post-processor plugins — execute after LLM validation, before sink persistence."""

import logging
import re
import unicodedata
from typing import Any, Protocol, runtime_checkable

import asyncpg

logger = logging.getLogger(__name__)


@runtime_checkable
class PostProcessor(Protocol):
    """Protocol for post-processor plugins.

    Post-processors execute in sequence after LLM output is validated and
    before the sink persists data. Each processor can enrich the output
    (add keys) but MUST NOT remove existing keys.

    Args:
        output: Validated LLM output dict (may have keys added by prior processors)
        item_metadata: Item metadata (source_url, content_hash, etc.)
        pool: asyncpg connection pool (acquire/release short connections)
        config: Post-processor config from pipeline YAML
    Returns:
        Enriched output dict
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict: ...


# ─── SQL safety ───

_SQL_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]*$')


def validate_sql_identifier(name: str, context: str = "identifier") -> str:
    """Validate that a string is a safe SQL identifier (table/column name).

    Allows: letters, digits, underscores, dots (for schema.table).
    Raises ValueError if the name contains dangerous characters.
    """
    if not name or not _SQL_IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL {context}: {name!r}")
    return name


# ─── Shared helper functions (used by multiple post-processors) ───


def normalize_for_search(name: str) -> str:
    """Normalize name for fuzzy search: remove accents, lowercase, collapse spaces."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", ascii_only.lower().strip())


def normalize_entity_name(name: str) -> str:
    """Remove political title prefixes from entity names."""
    name = name.strip()
    prefixes = [
        "ex-", "ex ", "deputado ", "deputada ", "senador ", "senadora ",
        "ministro ", "ministra ", "governador ", "governadora ",
        "prefeito ", "prefeita ", "vereador ", "vereadora ",
    ]
    lower = name.lower()
    for p in prefixes:
        if lower.startswith(p):
            name = name[len(p):]
            break
    return name.strip()


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from name."""
    normalized = normalize_for_search(name)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")


# ─── Registry ───


# Lazy imports to avoid circular dependencies — registered at module load
POST_PROCESSORS: dict[str, type] = {}


def _register_all():
    """Register all built-in post-processors."""
    from .article_matcher import ArticleMatcher
    from .cluster_updater import ClusterUpdater
    from .entity_resolver import EntityResolver
    from .milestone_detector import MilestoneDetector
    from .relationship_builder import RelationshipBuilder
    from .score_calculator import ScoreCalculator

    POST_PROCESSORS.update({
        "entity_resolver": EntityResolver,
        "score_calculator": ScoreCalculator,
        "relationship_builder": RelationshipBuilder,
        "milestone_detector": MilestoneDetector,
        "article_matcher": ArticleMatcher,
        "cluster_updater": ClusterUpdater,
    })


def get_post_processor(pp_type: str) -> PostProcessor:
    """Get a post-processor instance by type name."""
    if not POST_PROCESSORS:
        _register_all()
    cls = POST_PROCESSORS.get(pp_type)
    if cls is None:
        raise ValueError(f"Unknown post-processor type: {pp_type}")
    return cls()
