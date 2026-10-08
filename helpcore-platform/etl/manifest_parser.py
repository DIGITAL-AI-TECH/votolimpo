"""Manifest-driven parser for Help Bradesco SNAPSHOT data.

Reads the manifest.csv as the single source of truth and loads both
TXT (structured text) and HTML (rich content) for each article.
"""

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


def parse_manifest(manifest_path: Path, conteudos_dir: Path) -> list[dict]:
    """Parse manifest.csv and load TXT+HTML content for each entry.

    Args:
        manifest_path: Path to manifest.csv
        conteudos_dir: Path to the conteudos/ directory containing area subdirs

    Returns:
        List of article dicts ready for database insertion.
    """
    records = []
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = _parse_row(row, conteudos_dir)
            if record:
                records.append(record)
    return records


def iter_manifest(manifest_path: Path, conteudos_dir: Path):
    """Iterate manifest.csv yielding one article dict at a time (memory-efficient).

    Args:
        manifest_path: Path to manifest.csv
        conteudos_dir: Path to the conteudos/ directory

    Yields:
        Article dicts ready for database insertion.
    """
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = _parse_row(row, conteudos_dir)
            if record:
                yield record


def _parse_row(row: dict, conteudos_dir: Path) -> Optional[dict]:
    """Parse a single manifest CSV row into an article dict."""
    area = row.get("AREA", "").strip()
    titulo = row.get("TITULO", "").strip()
    if not area or not titulo:
        return None

    numero = _safe_int(row.get("NUMERO"))
    iid = row.get("IID", "").strip() or None
    lista = row.get("LISTA", "").strip() or None

    # Build source_url (unique key)
    if iid:
        source_url = f"bradesco-help://{area}/{iid}"
    else:
        source_url = f"bradesco-help://{area}/{titulo[:50]}"

    # Resolve file paths from manifest
    txt_content = _load_file_content(row, "TXT_FILE", conteudos_dir)
    html_content = _load_file_content(row, "HTML_FILE", conteudos_dir)

    # Parse TXT to extract structured content (links + body)
    parsed_txt = _parse_txt_content(txt_content) if txt_content else {}

    # Content hash from TXT body (for dedup compatibility with old ETL)
    body = parsed_txt.get("content", "")
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest() if body else None

    return {
        "source_url": source_url,
        "title": titulo,
        "subtitle": row.get("SUBTITULO", "").strip() or None,
        "area": area,
        "lista": lista,
        "content": body or None,
        "html_content": html_content,
        "content_hash": content_hash,
        "classification": row.get("CLASSIFICACAO", "").strip() or None,
        "iid": iid,
        "modified_date": _parse_date(row.get("MODIFIED")),
        "links": parsed_txt.get("links", []) or None,
        "help_title": row.get("HELP", "").strip() or None,
        "list_url": row.get("LIST_URL", "").strip() or None,
        "groupstring": row.get("GROUPSTRING", "").strip() or None,
        "numero": numero,
        "view_count": _safe_int(row.get("VIEWCOUNT")),
        "image_count": _safe_int(row.get("IMAGENS")),
        "attachment_count": _safe_int(row.get("ANEXOS")),
        "http_status": _safe_int(row.get("HTTP")),
        "html_hash": row.get("SHA256_HTML", "").strip() or None,
    }


def _load_file_content(row: dict, field: str, conteudos_dir: Path) -> Optional[str]:
    """Load file content by resolving the manifest path to a local path.

    The manifest stores Windows absolute paths like:
    C:\\Users\\...\\SNAPSHOT-FINAL-AOC-CARTOES\\conteudos\\Alto Valor\\2 Via de Senha\\000001_00. CONCEITO.html

    We extract the relative path after 'conteudos\\' and resolve against conteudos_dir.
    """
    raw_path = row.get(field, "").strip()
    if not raw_path:
        return None

    # Extract relative path after "conteudos\\" or "conteudos/"
    normalized = raw_path.replace("\\", "/")
    marker = "conteudos/"
    idx = normalized.find(marker)
    if idx == -1:
        return None

    relative = normalized[idx + len(marker):]
    filepath = conteudos_dir / relative

    if not filepath.exists():
        return None

    return _read_file(filepath)


def _read_file(filepath: Path) -> Optional[str]:
    """Read file with encoding fallbacks: UTF-8 → latin-1 → cp1252."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return filepath.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    return None


def _parse_txt_content(txt_content: str) -> dict:
    """Extract links and body content from TXT file content.

    TXT files have structure:
    HEADER: value
    ...
    ===== LINKS =====
    link1
    link2
    ===== CONTEUDO =====
    body text...
    """
    lines = txt_content.split("\n")
    links: list[str] = []
    content_lines: list[str] = []
    section = "header"

    for line in lines:
        stripped = line.strip()

        # Handle both old format (LINKS:) and new format (===== LINKS =====)
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

    content = "\n".join(content_lines).strip()
    return {"links": links, "content": content}


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Try to parse date from various formats."""
    if not date_str:
        return None
    date_str = date_str.strip()
    if not date_str:
        return None

    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _safe_int(value: Optional[str]) -> Optional[int]:
    """Safely convert string to int, returning None on failure."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
