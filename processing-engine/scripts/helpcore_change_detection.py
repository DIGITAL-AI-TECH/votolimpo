#!/usr/bin/env python3
"""Detect content changes in Help Core articles and mark for reprocessing.

Compares current article content hash against the stored content_hash
in analysis_results. When a change is detected:
1. Records the change in help_core.article_changes
2. Sets analysis_status = 'pending' in analysis_results

Usage:
    python scripts/helpcore_change_detection.py [--batch-size N] [--dry-run]

Environment:
    HELPCORE_DATABASE_URL or DATABASE_URL
"""
import argparse
import asyncio
import hashlib
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Detect changes in Help Core articles")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dsn = os.environ.get("HELPCORE_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not dsn:
        logger.error("Set HELPCORE_DATABASE_URL or DATABASE_URL")
        sys.exit(1)
    # asyncpg does not accept the +asyncpg driver prefix
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn, timeout=15)
    try:
        # Fetch articles that already have analysis_results with a content_hash
        rows = await conn.fetch("""
            SELECT
                a.id          AS article_id,
                a.content,
                a.title,
                ar.id         AS ar_id,
                ar.content_hash AS stored_hash,
                ar.analysis_status
            FROM help_core.articles a
            JOIN help_core.analysis_results ar ON ar.article_id = a.id
            WHERE ar.content_hash IS NOT NULL
            ORDER BY a.id
        """)

        logger.info("Checking %d articles with existing analysis", len(rows))

        changes_detected = 0
        already_pending = 0
        unchanged = 0

        for batch_start in range(0, len(rows), args.batch_size):
            batch = rows[batch_start:batch_start + args.batch_size]

            if args.dry_run:
                for row in batch:
                    content = row["content"] or ""
                    current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    stored_hash = row["stored_hash"]

                    if current_hash == stored_hash:
                        unchanged += 1
                        continue

                    changes_detected += 1
                    if changes_detected <= 5:
                        logger.info(
                            "DRY RUN: article_id=%d changed "
                            "(stored=%s... current=%s...)",
                            row["article_id"],
                            stored_hash[:12],
                            current_hash[:12],
                        )
            else:
                async with conn.transaction():
                    for row in batch:
                        content = row["content"] or ""
                        current_hash = hashlib.sha256(
                            content.encode("utf-8")
                        ).hexdigest()
                        stored_hash = row["stored_hash"]

                        if current_hash == stored_hash:
                            unchanged += 1
                            continue

                        if row["analysis_status"] == "pending":
                            already_pending += 1
                            continue

                        # Record the change
                        await conn.execute(
                            """
                            INSERT INTO help_core.article_changes
                                (article_id, previous_hash, new_hash,
                                 change_type, triggered_reprocessing)
                            VALUES ($1, $2, $3, 'content_modified', true)
                            """,
                            row["article_id"],
                            stored_hash,
                            current_hash,
                        )

                        # Mark article for reprocessing and update stored hash
                        await conn.execute(
                            """
                            UPDATE help_core.analysis_results
                            SET analysis_status = 'pending',
                                content_hash    = $2,
                                updated_at      = now()
                            WHERE id = $1
                            """,
                            row["ar_id"],
                            current_hash,
                        )

                        changes_detected += 1

            checked_so_far = min(batch_start + args.batch_size, len(rows))
            logger.info("Progress: %d/%d checked", checked_so_far, len(rows))

        mode_label = "[DRY RUN] " if args.dry_run else ""
        logger.info(
            "%sDone: %d changes detected, %d unchanged, %d already pending",
            mode_label,
            changes_detected,
            unchanged,
            already_pending,
        )

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
