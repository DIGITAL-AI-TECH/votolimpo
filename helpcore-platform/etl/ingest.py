"""ETL script to ingest Help Bradesco .txt files into PostgreSQL."""

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

INSERT_SQL = """
INSERT INTO help_core.articles (
    source_url, title, subtitle, area, lista, content, content_hash,
    classification, iid, modified_date, links, help_title, list_url, groupstring
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
ON CONFLICT (source_url) DO NOTHING
"""

INSERT_HASH_CHECK_SQL = """
SELECT 1 FROM help_core.articles WHERE content_hash = $1 LIMIT 1
"""


async def ingest(source_dir: str, database_url: str, skip_hash_dedup: bool = False) -> dict:
    """Main ingestion function."""
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
    print(f"Connected to database")

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
                    result = await _insert_batch(conn, batch)
                    inserted += result["inserted"]
                    duplicates += result["duplicates"]
                    batch = []

            except Exception as e:
                errors += 1
                tqdm.write(f"  ERROR: {filepath.name}: {e}")

        # Flush remaining batch
        if batch:
            result = await _insert_batch(conn, batch)
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


async def _insert_batch(conn: asyncpg.Connection, batch: list[tuple]) -> dict:
    """Insert a batch of records, counting inserts vs duplicates."""
    inserted = 0
    dupes = 0
    for record in batch:
        try:
            result = await conn.execute(INSERT_SQL, *record)
            if result == "INSERT 0 1":
                inserted += 1
            else:
                dupes += 1
        except asyncpg.UniqueViolationError:
            dupes += 1
    return {"inserted": inserted, "duplicates": dupes}


def main():
    parser = argparse.ArgumentParser(description="Ingest Help Bradesco .txt files into PostgreSQL")
    parser.add_argument(
        "--source",
        required=True,
        help="Directory containing .txt files",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--skip-hash-dedup",
        action="store_true",
        help="Skip content_hash dedup check (faster but may insert dupes)",
    )

    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: --database-url required or set DATABASE_URL env var")
        sys.exit(1)

    # asyncpg needs raw postgresql:// URL (not postgresql+asyncpg://)
    db_url = args.database_url.replace("postgresql+asyncpg://", "postgresql://")

    asyncio.run(ingest(args.source, db_url, args.skip_hash_dedup))


if __name__ == "__main__":
    main()
