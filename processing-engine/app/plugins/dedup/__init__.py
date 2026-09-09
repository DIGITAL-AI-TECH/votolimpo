"""Dedup plugins — detect duplicate content before LLM processing."""

import hashlib
from typing import Protocol

import asyncpg


class DedupStrategy(Protocol):
    """Protocol for dedup strategies."""

    async def check(self, content: str, source_url: str | None, config: dict, conn: asyncpg.Connection) -> str:
        """Check for duplicates. Returns: 'new' | 'duplicate' | 'similar'."""
        ...


class HashDedup:
    """Hash-based exact dedup on content + URL."""

    async def check(self, content: str, source_url: str | None, config: dict, conn: asyncpg.Connection) -> str:
        hash_fields = config.get("hash_fields", ["content"])
        parts = []
        if "source_url" in hash_fields and source_url:
            url = source_url
            if config.get("url_normalize", True):
                url = url.split("?")[0].split("#")[0].rstrip("/")
            parts.append(url)
        if "content" in hash_fields:
            parts.append(content)

        content_hash = hashlib.sha256("|".join(parts).encode()).hexdigest()

        # Check cache
        row = await conn.fetchrow(
            "SELECT 1 FROM processing_engine.cache WHERE content_hash = $1 AND expires_at > NOW()",
            content_hash,
        )
        if row:
            return "duplicate"

        return "new"


class CompositeDedup:
    """Composite: hash + optional semantic dedup."""

    async def check(self, content: str, source_url: str | None, config: dict, conn: asyncpg.Connection) -> str:
        # First do hash check
        hash_result = await HashDedup().check(content, source_url, config, conn)
        if hash_result == "duplicate":
            return "duplicate"

        # Semantic dedup disabled by default
        if not config.get("semantic_enabled", False):
            return "new"

        return "new"


DEDUP_STRATEGIES: dict[str, type] = {
    "hash": HashDedup,
    "composite": CompositeDedup,
}


def get_dedup(strategy: str) -> DedupStrategy:
    """Get a dedup strategy by name."""
    cls = DEDUP_STRATEGIES.get(strategy, HashDedup)
    return cls()
