from __future__ import annotations

import hashlib
from typing import Any

from app.plugins.protocols import DedupResult


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class HashDedupStrategy:
    """Deduplication via SHA-256 hashes of URL and content.

    Checks the processing_engine.items table for existing records with the
    same url_hash or content_hash within the same pipeline.

    Returns DedupResult(is_duplicate=True, matched_item_id=...) if a duplicate
    is found, otherwise DedupResult(is_duplicate=False).
    """

    async def check(
        self,
        content: str,
        url: str | None,
        pipeline_id: str,
        conn: Any,
        current_item_id: str | None = None,
    ) -> DedupResult:
        content_hash = _sha256(content)
        url_hash = _sha256(url) if url else None

        # Build query dynamically based on whether we have a URL
        # Exclude current_item_id to prevent self-match (the item being
        # processed already exists in the table with its hashes populated)
        if url_hash:
            row = await conn.fetchrow(
                """
                SELECT id
                FROM processing_engine.items
                WHERE pipeline_id = $1
                  AND (url_hash = $2 OR content_hash = $3)
                  AND status != 'failed'
                  AND ($4::uuid IS NULL OR id != $4::uuid)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                pipeline_id,
                url_hash,
                content_hash,
                current_item_id,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT id
                FROM processing_engine.items
                WHERE pipeline_id = $1
                  AND content_hash = $2
                  AND status != 'failed'
                  AND ($3::uuid IS NULL OR id != $3::uuid)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                pipeline_id,
                content_hash,
                current_item_id,
            )

        if row:
            return DedupResult(
                is_duplicate=True,
                matched_item_id=str(row["id"]),
                strategy="hash",
            )

        return DedupResult(
            is_duplicate=False,
            strategy="hash",
        )
