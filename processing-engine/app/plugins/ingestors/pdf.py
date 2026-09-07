from __future__ import annotations

from app.plugins.ingestors.text import _truncate


class PDFIngestor:
    """Ingestor for PDF binary content.

    Uses PyMuPDF (fitz) to extract text page by page.
    Handles corrupted PDFs with a descriptive ValueError.
    Applies truncation per FR-017.

    Note: raw input MUST be bytes (PDF binary).
    """

    async def ingest(
        self,
        raw: str | bytes,
        content_type: str,
        max_chars: int = 100000,
    ) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ImportError(
                "PyMuPDF is required for PDF ingestion. Install with: pip install PyMuPDF"
            ) from exc

        if isinstance(raw, str):
            raise ValueError("PDFIngestor expects bytes input, not str.")

        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Failed to open PDF: {exc}") from exc

        pages: list[str] = []
        try:
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    page_text = page.get_text()
                    if page_text.strip():
                        pages.append(page_text)
                except Exception as exc:
                    # Skip unreadable pages but log what happened
                    pages.append(f"[Page {page_num + 1} could not be read: {exc}]")
        finally:
            doc.close()

        text = "\n\n".join(pages)
        return _truncate(text, max_chars)
