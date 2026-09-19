from __future__ import annotations


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, keeping first half + separator + last half."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[...truncated...]\n\n" + text[-half:]


class TextIngestor:
    """Passthrough ingestor for plain text content.

    Handles both str and bytes input. Applies truncation per FR-017.
    """

    async def ingest(self, content: str, config: dict) -> str:
        max_chars = config.get("max_content_chars", 100000) if isinstance(config, dict) else 100000

        if isinstance(content, bytes):
            # Try UTF-8 first, fall back to latin-1 (never fails)
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
        else:
            text = content

        return _truncate(text, max_chars)
