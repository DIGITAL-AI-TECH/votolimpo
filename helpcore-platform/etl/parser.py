"""Parser for Help Bradesco .txt files exported from SharePoint."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


HEADER_FIELDS = [
    "HELP", "AREA", "LISTA", "TITULO", "SUBTITULO",
    "NIVEL3", "GROUPSTRING", "LIST_URL", "IID", "MODIFIED", "CLASSIFICACAO"
]


def parse_file(filepath: Path) -> Optional[dict]:
    """Parse a single .txt file and return structured data.

    Returns None if the file cannot be parsed (malformed/empty).
    """
    content_text = _read_file(filepath)
    if not content_text:
        return None

    lines = content_text.split("\n")
    header = {}
    links: list[str] = []
    content_lines: list[str] = []
    section = "header"

    for line in lines:
        stripped = line.strip()

        if stripped == "LINKS:":
            section = "links"
            continue
        elif stripped == "CONTEUDO:":
            section = "content"
            continue

        if section == "header":
            parsed = _parse_header_line(stripped)
            if parsed:
                key, value = parsed
                header[key] = value
        elif section == "links":
            if stripped:
                links.append(stripped)
        elif section == "content":
            content_lines.append(line)

    # Must have at minimum AREA and TITULO
    if "AREA" not in header or "TITULO" not in header:
        return None

    content = "\n".join(content_lines).strip()
    iid = header.get("IID", "")
    area = header["AREA"]

    # Generate content hash for dedup
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None

    # Parse modified date
    modified_date = _parse_date(header.get("MODIFIED"))

    return {
        "source_url": f"bradesco-help://{area}/{iid}" if iid else f"bradesco-help://{area}/{header['TITULO'][:50]}",
        "title": header["TITULO"],
        "subtitle": header.get("SUBTITULO") or None,
        "area": area,
        "lista": header.get("LISTA") or None,
        "content": content or None,
        "content_hash": content_hash,
        "classification": header.get("CLASSIFICACAO") or None,
        "iid": iid or None,
        "modified_date": modified_date,
        "links": links if links else None,
        "help_title": header.get("HELP") or None,
        "list_url": header.get("LIST_URL") or None,
        "groupstring": header.get("GROUPSTRING") or None,
    }


def _read_file(filepath: Path) -> Optional[str]:
    """Read file with encoding fallbacks: UTF-8 → latin-1 → cp1252."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return filepath.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def _parse_header_line(line: str) -> Optional[tuple[str, str]]:
    """Parse a 'KEY: VALUE' header line."""
    if not line or ":" not in line:
        return None

    colon_idx = line.index(":")
    key = line[:colon_idx].strip().upper()
    value = line[colon_idx + 1:].strip()

    if key in HEADER_FIELDS and value:
        return (key, value)
    return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Try to parse date from various formats."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
