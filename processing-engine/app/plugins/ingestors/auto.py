from __future__ import annotations


def _detect_content_type(raw: str | bytes, content_type: str) -> str:
    """Normalize and detect content type from MIME type or content sniffing."""
    mime = content_type.split(";")[0].strip().lower() if content_type else ""

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
        if raw[:4] == b"%PDF":
            return "pdf"
        try:
            sample = raw[:512].decode("utf-8", errors="replace").lower()
        except Exception:
            sample = ""
        if "<html" in sample or "<!doctype" in sample:
            return "html"
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
    """Auto-detecting ingestor that delegates to the appropriate registered ingestor.

    Detection priority:
    1. MIME type from config["content_type"] (if present)
    2. Content sniffing (PDF magic bytes, HTML tags, JSON brackets)
    3. Default: raw_text
    """

    async def ingest(self, content: str, config: dict) -> str:
        """Ingest content with auto-detection. Follows standard Ingestor Protocol."""
        from app.plugins.ingestors import get_ingestor

        content_type = config.get("content_type", "") if isinstance(config, dict) else ""
        detected = _detect_content_type(content, content_type)

        # Delegate to the registered ingestor (follows Protocol signature)
        ingestor = get_ingestor(detected)
        return await ingestor.ingest(content, config if isinstance(config, dict) else {})
