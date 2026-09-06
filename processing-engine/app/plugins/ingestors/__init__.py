from __future__ import annotations

from app.plugins.ingestors.auto import AutoIngestor
from app.plugins.ingestors.html import HTMLIngestor
from app.plugins.ingestors.json_ingestor import JSONIngestor
from app.plugins.ingestors.pdf import PDFIngestor
from app.plugins.ingestors.text import TextIngestor
from app.plugins.registry import register

register("ingestor", "text", TextIngestor)
register("ingestor", "html", HTMLIngestor)
register("ingestor", "pdf", PDFIngestor)
register("ingestor", "json", JSONIngestor)
register("ingestor", "auto", AutoIngestor)

__all__ = [
    "TextIngestor",
    "HTMLIngestor",
    "PDFIngestor",
    "JSONIngestor",
    "AutoIngestor",
]
