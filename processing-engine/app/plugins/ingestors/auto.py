from __future__ import annotations

from app.plugins.ingestors.html import HTMLIngestor
from app.plugins.ingestors.json_ingestor import JSONIngestor
from app.plugins.ingestors.pdf import PDFIngestor
from app.plugins.ingestors.text import TextIngestor


def _detect_content_type(raw: str | bytes, content_type: str) -> str:
    """Normalize and detect content type from MIME type or content sniffing."""
    # Normalize the provided content_type (strip params like charset)
    mime = content_type.split(";")[0].strip().lower()

    if mime:
        if "html" in mime:
            return "html"
        if mime == "application/pdf":
            return "pdf"
        if mime in ("application/json", "text/json"):
            return "json"
        if mime.startswith("text/"):
            return "text"

    # Content sniffing fallback
    if isinstance(raw, bytes):
        # PDF magic bytes
        if raw[:4] == b"%PDF":
            return "pdf"
        # Try to detect HTML by looking for common tags
        try:
            sample = raw[:512].decode("utf-8", errors="replace").lower()
        except Exception:
            sample = ""
        if "<html" in sample or "<!doctype" in sample:
            return "html"
        # Try to detect JSON
        stripped = raw[:1].decode("utf-8", errors="replace").strip()
        if stripped in ("{", "["):
            return "json"
    else:
        sample = raw[:512].lower()
        if "<html" in sample or "<!doctype" in sample:
            return "html"
        stripped = raw[:1].strip()
        if stripped in ("{", "["):
            return "json"

    return "text"


class AutoIngestor:
    """Auto-detecting ingestor that delegates to the appropriate ingestor.

    Detection priority:
    1. MIME type from content_type header
    2. Content sniffing (PDF magic bytes, HTML tags, JSON brackets)
    3. Default: TextIngestor
    """

    def __init__(self) -> None:
        self._html = HTMLIngestor()
        self._pdf = PDFIngestor()
        self._json = JSONIngestor()
        self._text = TextIngestor()

    async def ingest(
        self,
        raw: str | bytes,
        content_type: str,
        max_chars: int = 100000,
    ) -> str:
        detected = _detect_content_type(raw, content_type)

        if detected == "html":
            return await self._html.ingest(raw, content_type, max_chars)
        if detected == "pdf":
            return await self._pdf.ingest(raw, content_type, max_chars)
        if detected == "json":
            return await self._json.ingest(raw, content_type, max_chars)
        # Default: text
        return await self._text.ingest(raw, content_type, max_chars)
