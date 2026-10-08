"""ETL script to ingest Help Bradesco files into PostgreSQL.

Supports two modes:
  --source DIR          Legacy mode: scan directory for .txt files (old behavior)
  --manifest CSV --conteudos DIR   Manifest mode: use manifest.csv as driver,
                                    load both TXT + HTML per article (recommended)
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

import asyncpg
from tqdm import tqdm

from parser import parse_file

BATCH_SIZE = 500

# Legacy mode SQL (original 14 columns)
INSERT_SQL_LEGACY = """
INSERT INTO help_core.articles (
    source_url, title, subtitle, area, lista, content, content_hash,
    classification, iid, modified_date, links, help_title, list_url, groupstring
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
ON CONFLICT (source_url) DO NOTHING
"""

# Manifest mode SQL (20 columns — includes html_content + manifest metadata)
INSERT_SQL_MANIFEST = """
INSERT INTO help_core.articles (
    source_url, title, subtitle, area, lista, content, html_content, content_hash,
    classification, iid, modified_date, links, help_title, list_url, groupstring,
    numero, view_count, image_count, attachment_count, http_status, html_hash
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
ON CONFLICT (source_url) DO UPDATE SET
    html_content = COALESCE(EXCLUDED.html_content, help_core.articles.html_content),
    numero = COALESCE(EXCLUDED.numero, help_core.articles.numero),
    view_count = COALESCE(EXCLUDED.view_count, help_core.articles.view_count),
    image_count = COALESCE(EXCLUDED.image_count, help_core.articles.image_count),
    attachment_count = COALESCE(EXCLUDED.attachment_count, help_core.articles.attachment_count),
    http_status = COALESCE(EXCLUDED.http_status, help_core.articles.http_status),
    html_hash = COALESCE(EXCLUDED.html_hash, help_core.articles.html_hash),
    content = COALESCE(EXCLUDED.content, help_core.articles.content),
    content_hash = COALESCE(EXCLUDED.content_hash, help_core.articles.content_hash)
"""

INSERT_HASH_CHECK_SQL = """
SELECT 1 FROM help_core.articles WHERE content_hash = $1 LIMIT 1
"""


async def ingest_manifest(manifest_path: str, conteudos_dir: str, database_url: str) -> dict:
    """Manifest-driven ingestion: reads CSV, loads TXT+HTML per article."""
    from manifest_parser import iter_manifest

    manifest = Path(manifest_path)
    conteudos = Path(conteudos_dir)

    if not manifest.is_file():
        print(f"ERROR: Manifest not found: {manifest_path}")
        sys.exit(1)
    if not conteudos.is_dir():
        print(f"ERROR: Conteudos directory not found: {conteudos_dir}")
        sys.exit(1)

    # Count total lines for progress bar
    with open(manifest, "r", encoding="utf-8-sig") as f:
        total = sum(1 for _ in f) - 1  # minus header
    print(f"Manifest has {total:,} entries")

    conn = await asyncpg.connect(database_url)
    print("Connected to database")

    inserted = 0
    updated = 0
    errors = 0
    batch: list[tuple] = []
    start_time = time.time()

    try:
        for record in tqdm(iter_manifest(manifest, conteudos), total=total, desc="Manifest ingest", unit="article"):
            try:
                batch.append((
                    record["source_url"],
                    record["title"],
                    record["subtitle"],
                    record["area"],
                    record["lista"],
                    record["content"],
                    record["html_content"],
                    record["content_hash"],
                    record["classification"],
                    record["iid"],
                    record["modified_date"],
                    record["links"],
                    record["help_title"],
                    record["list_url"],
                    record["groupstring"],
                    record["numero"],
                    record["view_count"],
                    record["image_count"],
                    record["attachment_count"],
                    record["http_status"],
                    record["html_hash"],
                ))

                if len(batch) >= BATCH_SIZE:
                    result = await _insert_batch_manifest(conn, batch)
                    inserted += result["inserted"]
                    updated += result["updated"]
                    batch = []

            except Exception as e:
                errors += 1
                tqdm.write(f"  ERROR: {record.get('source_url', '?')}: {e}")

        # Flush remaining batch
        if batch:
            result = await _insert_batch_manifest(conn, batch)
            inserted += result["inserted"]
            updated += result["updated"]

    finally:
        await conn.close()

    elapsed = time.time() - start_time
    report = {
        "total": total,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
        "rate_per_second": round(total / elapsed, 1) if elapsed > 0 else 0,
    }

    print("\n" + "=" * 60)
    print("MANIFEST INGEST REPORT")
    print("=" * 60)
    print(f"  Total entries: {report['total']:>10,}")
    print(f"  Inserted:      {report['inserted']:>10,}")
    print(f"  Updated:       {report['updated']:>10,}")
    print(f"  Errors:        {report['errors']:>10,}")
    print(f"  Elapsed:       {report['elapsed_seconds']:>10.1f}s")
    print(f"  Rate:          {report['rate_per_second']:>10.1f} articles/s")
    print("=" * 60)

    return report


async def _insert_batch_manifest(conn: asyncpg.Connection, batch: list[tuple]) -> dict:
    """Insert/upsert a batch of manifest records."""
    inserted = 0
    updated = 0
    for record in batch:
        try:
            result = await conn.execute(INSERT_SQL_MANIFEST, *record)
            if result == "INSERT 0 1":
                inserted += 1
            else:
                updated += 1
        except asyncpg.UniqueViolationError:
            updated += 1
    return {"inserted": inserted, "updated": updated}


async def ingest(source_dir: str, database_url: str, skip_hash_dedup: bool = False) -> dict:
    """Legacy ingestion: scan directory for .txt files."""
    source_path = Path(source_dir)
    if not source_path.is_dir():
        print(f"ERROR: Directory not found: {source_dir}")
        sys.exit(1)

    txt_files = sorted(source_path.glob("*.txt"))
    total_files = len(txt_files)
    print(f"Found {total_files:,} .txt files in {source_dir}")

    if total_files == 0:
        print("No .txt files found. Exiting.")
        return {"inserted": 0, "duplicates": 0, "errors": 0, "total": 0}

    conn = await asyncpg.connect(database_url)
    print("Connected to database")

    inserted = 0
    duplicates = 0
    errors = 0
    batch: list[tuple] = []
    start_time = time.time()

    try:
        for filepath in tqdm(txt_files, desc="Parsing & inserting", unit="file"):
            try:
                record = parse_file(filepath)
                if record is None:
                    errors += 1
                    tqdm.write(f"  SKIP (parse error): {filepath.name}")
                    continue

                # Check content_hash dedup
                if not skip_hash_dedup and record["content_hash"]:
                    existing = await conn.fetchval(
                        INSERT_HASH_CHECK_SQL, record["content_hash"]
                    )
                    if existing:
                        duplicates += 1
                        continue

                batch.append((
                    record["source_url"],
                    record["title"],
                    record["subtitle"],
                    record["area"],
                    record["lista"],
                    record["content"],
                    record["content_hash"],
                    record["classification"],
                    record["iid"],
                    record["modified_date"],
                    record["links"],
                    record["help_title"],
                    record["list_url"],
                    record["groupstring"],
                ))

                if len(batch) >= BATCH_SIZE:
                    result = await _insert_batch_legacy(conn, batch)
                    inserted += result["inserted"]
                    duplicates += result["duplicates"]
                    batch = []

            except Exception as e:
                errors += 1
                tqdm.write(f"  ERROR: {filepath.name}: {e}")

        # Flush remaining batch
        if batch:
            result = await _insert_batch_legacy(conn, batch)
            inserted += result["inserted"]
            duplicates += result["duplicates"]

    finally:
        await conn.close()

    elapsed = time.time() - start_time
    report = {
        "total": total_files,
        "inserted": inserted,
        "duplicates": duplicates,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
        "rate_per_second": round(total_files / elapsed, 1) if elapsed > 0 else 0,
    }

    print("\n" + "=" * 60)
    print("INGEST REPORT")
    print("=" * 60)
    print(f"  Total files:  {report['total']:>10,}")
    print(f"  Inserted:     {report['inserted']:>10,}")
    print(f"  Duplicates:   {report['duplicates']:>10,}")
    print(f"  Errors:       {report['errors']:>10,}")
    print(f"  Elapsed:      {report['elapsed_seconds']:>10.1f}s")
    print(f"  Rate:         {report['rate_per_second']:>10.1f} files/s")
    print("=" * 60)

    return report


async def _insert_batch_legacy(conn: asyncpg.Connection, batch: list[tuple]) -> dict:
    """Insert a batch of records (legacy mode), counting inserts vs duplicates."""
    inserted = 0
    dupes = 0
    for record in batch:
        try:
            result = await conn.execute(INSERT_SQL_LEGACY, *record)
            if result == "INSERT 0 1":
                inserted += 1
            else:
                dupes += 1
        except asyncpg.UniqueViolationError:
            dupes += 1
    return {"inserted": inserted, "duplicates": dupes}


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Help Bradesco files into PostgreSQL",
        epilog="""
Examples:
  # Manifest mode (recommended — captures TXT + HTML + metadata):
  python ingest.py --manifest manifest.csv --conteudos conteudos/

  # Legacy mode (TXT only, backward compatible):
  python ingest.py --source /path/to/txt/files/
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        help="[Legacy] Directory containing .txt files",
    )
    parser.add_argument(
        "--manifest",
        help="[Recommended] Path to manifest.csv",
    )
    parser.add_argument(
        "--conteudos",
        help="Path to conteudos/ directory (required with --manifest)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--skip-hash-dedup",
        action="store_true",
        help="[Legacy] Skip content_hash dedup check",
    )

    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: --database-url required or set DATABASE_URL env var")
        sys.exit(1)

    # asyncpg needs raw postgresql:// URL (not postgresql+asyncpg://)
    db_url = args.database_url.replace("postgresql+asyncpg://", "postgresql://")

    if args.manifest:
        if not args.conteudos:
            print("ERROR: --conteudos required when using --manifest")
            sys.exit(1)
        asyncio.run(ingest_manifest(args.manifest, args.conteudos, db_url))
    elif args.source:
        asyncio.run(ingest(args.source, db_url, args.skip_hash_dedup))
    else:
        print("ERROR: either --manifest + --conteudos or --source is required")
        sys.exit(1)


if __name__ == "__main__":
    main()
