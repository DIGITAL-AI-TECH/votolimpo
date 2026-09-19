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

    async def ingest(self, content: str, config: dict) -> str:
        max_chars = config.get("max_content_chars", 100000) if isinstance(config, dict) else 100000

        if isinstance(content, bytes):
            try:
                html = content.decode("utf-8")
            except UnicodeDecodeError:
                html = content.decode("latin-1")
        else:
            html = content

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
