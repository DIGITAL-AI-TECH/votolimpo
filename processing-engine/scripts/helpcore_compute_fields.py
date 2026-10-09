#!/usr/bin/env python3
"""Compute deterministic fields for Help Core analysis_results.

Reads article content from help_core.articles, calculates metrics,
and updates help_core.analysis_results. Idempotent — safe to re-run.

Usage:
    python scripts/helpcore_compute_fields.py [--batch-size N] [--dry-run] [--force]

Environment:
    DATABASE_URL or HELPCORE_DATABASE_URL — PostgreSQL connection string
"""
import argparse
import asyncio
import hashlib
import logging
import os
import re
import sys
from decimal import Decimal

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def compute_fields(content: str, title: str | None) -> dict:
    """Compute all deterministic fields from article content."""
    if not content:
        content = ""

    words = content.split()
    word_count = len(words)
    sentences = [s for s in re.split(r'[.!?]+', content) if s.strip()]
    sentence_count = len(sentences)
    paragraphs = [p for p in content.split('\n\n') if p.strip()]
    paragraph_count = len(paragraphs)
    lines = content.splitlines()
    line_count = len(lines)
    char_count = len(content)

    return {
        "char_count": char_count,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "line_count": line_count,
        "avg_sentence_length": round(word_count / max(sentence_count, 1), 2),
        "reading_time_seconds": int(word_count / 200 * 60),
        "has_numbered_steps": bool(re.search(r'^\d+[.)]\s', content, re.MULTILINE)),
        "has_bullet_points": bool(re.search(r'^[-*\u2022]\s', content, re.MULTILINE)),
        "has_headers": bool(re.search(r'^#+\s', content, re.MULTILINE)),
        "has_tables": bool(re.search(r'\|.*\|.*\|', content) or '<table' in content.lower()),
        "has_images": bool(re.search(r'<img|!\[', content)),
        "uppercase_ratio": round(sum(1 for c in content if c.isupper()) / max(char_count, 1), 4),
        "content_hash": hashlib.sha256(content.encode('utf-8')).hexdigest(),
        "link_count": len(re.findall(r'https?://', content)),
        "title_word_count": len(title.split()) if title else 0,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute deterministic fields for Help Core articles"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for updates (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate but don't write to DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recalculate even if word_count already set",
    )
    args = parser.parse_args()

    dsn = os.environ.get("HELPCORE_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not dsn:
        logger.error("Set HELPCORE_DATABASE_URL or DATABASE_URL")
        sys.exit(1)

    # asyncpg uses postgresql:// not postgresql+asyncpg://
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn, timeout=15)

    try:
        where_clause = "" if args.force else "AND ar.word_count IS NULL"
        rows = await conn.fetch(f"""
            SELECT ar.id, ar.article_id, a.content, a.title
            FROM help_core.analysis_results ar
            JOIN help_core.articles a ON a.id = ar.article_id
            WHERE ar.article_id IS NOT NULL {where_clause}
            ORDER BY ar.id
        """)

        logger.info("Found %d rows to process (force=%s)", len(rows), args.force)

        if not rows:
            logger.info("Nothing to do")
            return

        updated = 0

        for i in range(0, len(rows), args.batch_size):
            batch = rows[i : i + args.batch_size]

            if not args.dry_run:
                async with conn.transaction():
                    for row in batch:
                        fields = compute_fields(row["content"] or "", row["title"])

                        await conn.execute(
                            """
                            UPDATE help_core.analysis_results SET
                                char_count           = $2,
                                word_count           = $3,
                                sentence_count       = $4,
                                paragraph_count      = $5,
                                line_count           = $6,
                                avg_sentence_length  = $7,
                                reading_time_seconds = $8,
                                has_numbered_steps   = $9,
                                has_bullet_points    = $10,
                                has_headers          = $11,
                                has_tables           = $12,
                                has_images           = $13,
                                uppercase_ratio      = $14,
                                content_hash         = $15,
                                link_count           = $16,
                                title_word_count     = $17,
                                updated_at           = now()
                            WHERE id = $1
                            """,
                            row["id"],
                            fields["char_count"],
                            fields["word_count"],
                            fields["sentence_count"],
                            fields["paragraph_count"],
                            fields["line_count"],
                            Decimal(str(fields["avg_sentence_length"])),
                            fields["reading_time_seconds"],
                            fields["has_numbered_steps"],
                            fields["has_bullet_points"],
                            fields["has_headers"],
                            fields["has_tables"],
                            fields["has_images"],
                            Decimal(str(fields["uppercase_ratio"])),
                            fields["content_hash"],
                            fields["link_count"],
                            fields["title_word_count"],
                        )
                        updated += 1
            else:
                for row in batch:
                    fields = compute_fields(row["content"] or "", row["title"])
                    updated += 1
                    if updated <= 3:
                        logger.info(
                            "DRY RUN sample (article_id=%s): %s",
                            row["article_id"],
                            fields,
                        )

            logger.info(
                "Progress: %d/%d processed",
                min(i + args.batch_size, len(rows)),
                len(rows),
            )

        logger.info("Done: %d updated", updated)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
