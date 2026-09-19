"""Ingestor plugins — transform raw content into clean text."""

from typing import Protocol


class Ingestor(Protocol):
    """Protocol for ingestor plugins."""

    async def ingest(self, content: str, config: dict) -> str:
        """Transform raw content into clean text for LLM processing."""
        ...


class RawTextIngestor:
    """Pass-through ingestor for plain text."""

    async def ingest(self, content: str, config: dict) -> str:
        max_chars = config.get("max_content_chars", 15000)
        return content[:max_chars]


class HTMLIngestor:
    """Strip HTML tags and extract text content."""

    async def ingest(self, content: str, config: dict) -> str:
        import re

        max_chars = config.get("max_content_chars", 15000)

        if config.get("strip_tags", True):
            # Remove script and style elements
            text = re.sub(
                r"<(script|style)[^>]*>.*?</\1>",
                "",
                content,
                flags=re.DOTALL | re.IGNORECASE,
            )
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()
        else:
            text = content

        return text[:max_chars]


# Registry — import full-featured ingestors from their modules
from app.plugins.ingestors.auto import AutoIngestor
from app.plugins.ingestors.html import HTMLIngestor as _HTMLIngestorFull
from app.plugins.ingestors.json_ingestor import JSONIngestor
from app.plugins.ingestors.pdf import PDFIngestor
from app.plugins.ingestors.text import TextIngestor

INGESTORS: dict[str, type] = {
    "raw_text": RawTextIngestor,
    "text": TextIngestor,
    "html": _HTMLIngestorFull,
    "pdf": PDFIngestor,
    "json": JSONIngestor,
    "auto": AutoIngestor,
}

# Populate global registry
from app.plugins.registry import register as _register

for _name, _cls in INGESTORS.items():
    _register("ingestor", _name, _cls)


def get_ingestor(ingestor_type: str) -> Ingestor:
    """Get an ingestor by type name."""
    cls = INGESTORS.get(ingestor_type, RawTextIngestor)
    return cls()
