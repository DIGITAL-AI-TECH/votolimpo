from __future__ import annotations

import json

from app.plugins.ingestors.text import _truncate


class JSONIngestor:
    """Ingestor for JSON content.

    Parses JSON and serializes to a readable indented format.
    Raises ValueError for invalid JSON.
    Applies truncation per FR-017.
    """

    async def ingest(self, content: str, config: dict) -> str:
        max_chars = config.get("max_content_chars", 100000) if isinstance(config, dict) else 100000

        if isinstance(content, bytes):
            try:
                raw_str = content.decode("utf-8")
            except UnicodeDecodeError:
                raw_str = content.decode("latin-1")
        else:
            raw_str = content

        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON content: {exc}") from exc

        text = json.dumps(data, indent=2, ensure_ascii=False)
        return _truncate(text, max_chars)
