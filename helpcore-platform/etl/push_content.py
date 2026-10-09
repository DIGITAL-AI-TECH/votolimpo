#!/usr/bin/env python3
"""Push article content to Help Core platform via admin bulk-content API.

Reads manifest.csv + conteudos/ directory and sends batched updates
to populate the content field for all articles.

Usage:
    python push_content.py \
        --manifest /path/to/manifest.csv \
        --conteudos /path/to/conteudos/ \
        --url https://helpcore.digital-ai.tech \
        --api-key <HELPCORE_AUTH_SECRET>

    # Dry-run (no actual requests):
    python push_content.py --manifest ... --conteudos ... --dry-run
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BATCH_SIZE = 100


def load_file_content(row: dict, field: str, conteudos_dir: Path) -> str | None:
    raw_path = row.get(field, "").strip()
    if not raw_path:
        return None
    normalized = raw_path.replace("\\", "/")
    marker = "conteudos/"
    idx = normalized.find(marker)
    if idx == -1:
        return None
    relative = normalized[idx + len(marker):]
    filepath = conteudos_dir / relative
    if not filepath.exists():
        return None
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return filepath.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def parse_txt_content(txt_content: str) -> dict:
    lines = txt_content.split("\n")
    links = []
    content_lines = []
    section = "header"
    for line in lines:
        stripped = line.strip()
        if stripped in ("LINKS:", "===== LINKS ====="):
            section = "links"
            continue
        elif stripped in ("CONTEUDO:", "===== CONTEUDO ====="):
            section = "content"
            continue
        if section == "links":
            if stripped:
                links.append(stripped)
        elif section == "content":
            content_lines.append(line)
    return {"content": "\n".join(content_lines).strip()}


def iter_manifest(manifest_path: Path, conteudos_dir: Path):
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            area = row.get("AREA", "").strip()
            titulo = row.get("TITULO", "").strip()
            if not area or not titulo:
                continue

            iid = row.get("IID", "").strip() or None
            if iid:
                source_url = f"bradesco-help://{area}/{iid}"
            else:
                source_url = f"bradesco-help://{area}/{titulo[:50]}"

            txt_content = load_file_content(row, "TXT_FILE", conteudos_dir)
            html_content = load_file_content(row, "HTML_FILE", conteudos_dir)

            parsed = parse_txt_content(txt_content) if txt_content else {}
            body = parsed.get("content", "")
            content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None

            if not body and not html_content:
                continue

            yield {
                "source_url": source_url,
                "content": body or None,
                "html_content": html_content,
                "content_hash": content_hash,
            }


def send_batch(batch: list[dict], url: str, api_key: str) -> dict:
    endpoint = f"{url.rstrip('/')}/api/admin/bulk-content"
    payload = json.dumps({"articles": batch}).encode("utf-8")

    req = Request(endpoint, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    for attempt in range(3):
        try:
            with urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"  HTTP {e.code}: {body}")
            if e.code >= 500 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
        except URLError as e:
            if attempt < 2:
                print(f"  Connection error: {e.reason}, retrying...")
                time.sleep(2 ** attempt)
                continue
            raise


def main():
    parser = argparse.ArgumentParser(description="Push article content to Help Core")
    parser.add_argument("--manifest", required=True, help="Path to manifest.csv")
    parser.add_argument("--conteudos", required=True, help="Path to conteudos/ directory")
    parser.add_argument("--url", default="https://helpcore.digital-ai.tech",
                        help="Help Core platform URL")
    parser.add_argument("--api-key", required=True, help="HELPCORE_AUTH_SECRET value")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no requests")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    conteudos_dir = Path(args.conteudos)

    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}")
        sys.exit(1)
    if not conteudos_dir.exists():
        print(f"ERROR: conteudos dir not found: {conteudos_dir}")
        sys.exit(1)

    print(f"Reading manifest: {manifest_path}")
    print(f"Conteudos dir: {conteudos_dir}")
    print(f"Target: {args.url}")
    print(f"Batch size: {args.batch_size}")
    print()

    batch: list[dict] = []
    total_sent = 0
    total_updated = 0
    total_not_found = 0
    total_with_content = 0
    batch_num = 0

    for record in iter_manifest(manifest_path, conteudos_dir):
        total_with_content += 1
        batch.append(record)

        if len(batch) >= args.batch_size:
            batch_num += 1
            if args.dry_run:
                print(f"  [DRY-RUN] Batch {batch_num}: {len(batch)} articles")
                total_sent += len(batch)
            else:
                print(f"  Sending batch {batch_num} ({len(batch)} articles)...", end=" ")
                result = send_batch(batch, args.url, args.api_key)
                total_sent += len(batch)
                total_updated += result.get("updated", 0)
                total_not_found += result.get("not_found", 0)
                print(f"updated={result.get('updated', 0)}, not_found={result.get('not_found', 0)}")
            batch = []

    # Send remaining
    if batch:
        batch_num += 1
        if args.dry_run:
            print(f"  [DRY-RUN] Batch {batch_num}: {len(batch)} articles")
            total_sent += len(batch)
        else:
            print(f"  Sending batch {batch_num} ({len(batch)} articles)...", end=" ")
            result = send_batch(batch, args.url, args.api_key)
            total_sent += len(batch)
            total_updated += result.get("updated", 0)
            total_not_found += result.get("not_found", 0)
            print(f"updated={result.get('updated', 0)}, not_found={result.get('not_found', 0)}")

    print()
    print("=" * 50)
    print(f"Articles with content found: {total_with_content}")
    print(f"Articles sent:               {total_sent}")
    if not args.dry_run:
        print(f"Articles updated in DB:      {total_updated}")
        print(f"Articles not found in DB:    {total_not_found}")
    print("Done!")


if __name__ == "__main__":
    main()
