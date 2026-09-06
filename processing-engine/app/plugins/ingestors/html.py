from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.plugins.ingestors.text import _truncate

# Tags whose content should be completely removed (not just the tag)
_REMOVE_TAGS = {"script", "style", "noscript", "iframe"}


class HTMLIngestor:
    """Ingestor for HTML content.

    Uses BeautifulSoup4 to strip markup and extract clean text.
    Removes script/style/noscript/iframe elements entirely.
    Normalizes whitespace and applies truncation per FR-017.
    """

    async def ingest(
        self,
        raw: str | bytes,
        content_type: str,
        max_chars: int = 100000,
    ) -> str:
        if isinstance(raw, bytes):
            try:
                html = raw.decode("utf-8")
            except UnicodeDecodeError:
                html = raw.decode("latin-1")
        else:
            html = raw

        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted tags and their content
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        # Extract text with newline separator between block elements
        text = soup.get_text(separator="\n")

        # Normalize whitespace: collapse multiple blank lines into a single one
        # and strip leading/trailing spaces from each line
        lines = [line.strip() for line in text.splitlines()]
        # Remove consecutive empty lines (keep at most one blank line)
        normalized_lines: list[str] = []
        prev_blank = False
        for line in lines:
            if line == "":
                if not prev_blank:
                    normalized_lines.append(line)
                prev_blank = True
            else:
                normalized_lines.append(line)
                prev_blank = False

        text = "\n".join(normalized_lines).strip()

        # Collapse multiple spaces within a single line
        text = re.sub(r" {2,}", " ", text)

        return _truncate(text, max_chars)
