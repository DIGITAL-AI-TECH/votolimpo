from __future__ import annotations

import json

from app.plugins.ingestors.text import _truncate


class JSONIngestor:
    """Ingestor for JSON content.

    Parses JSON and serializes to a readable indented format.
    Raises ValueError for invalid JSON.
    Applies truncation per FR-017.
    """

    async def ingest(
        self,
        raw: str | bytes,
        content_type: str,
        max_chars: int = 100000,
    ) -> str:
        if isinstance(raw, bytes):
            try:
                raw_str = raw.decode("utf-8")
            except UnicodeDecodeError:
                raw_str = raw.decode("latin-1")
        else:
            raw_str = raw

        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON content: {exc}") from exc

        text = json.dumps(data, indent=2, ensure_ascii=False)
        return _truncate(text, max_chars)
