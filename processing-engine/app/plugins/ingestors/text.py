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

    async def ingest(
        self,
        raw: str | bytes,
        content_type: str,
        max_chars: int = 100000,
    ) -> str:
        if isinstance(raw, bytes):
            # Try UTF-8 first, fall back to latin-1 (never fails)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
        else:
            text = raw

        return _truncate(text, max_chars)
