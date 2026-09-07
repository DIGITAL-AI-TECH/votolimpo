"""Unit tests for all ingestor plugins."""
from __future__ import annotations

import json
import pytest

from app.plugins.ingestors.auto import AutoIngestor, _detect_content_type
from app.plugins.ingestors.html import HTMLIngestor
from app.plugins.ingestors.json_ingestor import JSONIngestor
from app.plugins.ingestors.pdf import PDFIngestor
from app.plugins.ingestors.text import TextIngestor, _truncate


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

CONTENT_TYPE_PLAIN = "text/plain"
CONTENT_TYPE_HTML = "text/html"
CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_PDF = "application/pdf"


# ---------------------------------------------------------------------------
# TextIngestor
# ---------------------------------------------------------------------------

class TestTextIngestor:
    ingestor = TextIngestor()

    async def test_passthrough_str(self):
        result = await self.ingestor.ingest("hello world", CONTENT_TYPE_PLAIN)
        assert result == "hello world"

    async def test_passthrough_bytes_utf8(self):
        raw = "olá mundo".encode("utf-8")
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_PLAIN)
        assert result == "olá mundo"

    async def test_passthrough_bytes_latin1(self):
        # Bytes that are invalid UTF-8 but valid latin-1
        raw = "café".encode("latin-1")
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_PLAIN)
        assert "caf" in result  # latin-1 decoded

    async def test_truncation_preserves_start_and_end(self):
        # 200 characters: first 100 chars = 'A', last 100 chars = 'B'
        content = "A" * 100 + "B" * 100
        max_chars = 50  # half=25, so 25 A's + sep + 25 B's
        result = await self.ingestor.ingest(content, CONTENT_TYPE_PLAIN, max_chars)
        assert result.startswith("A" * 25)
        assert result.endswith("B" * 25)
        assert "[...truncated...]" in result

    async def test_no_truncation_when_short(self):
        content = "short text"
        result = await self.ingestor.ingest(content, CONTENT_TYPE_PLAIN, max_chars=10000)
        assert result == "short text"

    async def test_truncation_exact_boundary(self):
        content = "x" * 100
        result = await self.ingestor.ingest(content, CONTENT_TYPE_PLAIN, max_chars=100)
        # Exactly at boundary: no truncation
        assert result == content
        assert "[...truncated...]" not in result

    async def test_truncation_over_boundary(self):
        content = "x" * 101
        result = await self.ingestor.ingest(content, CONTENT_TYPE_PLAIN, max_chars=100)
        assert "[...truncated...]" in result


# ---------------------------------------------------------------------------
# _truncate helper
# ---------------------------------------------------------------------------

class TestTruncateHelper:
    def test_short_text_unchanged(self):
        assert _truncate("abc", 10) == "abc"

    def test_truncation_separator(self):
        result = _truncate("A" * 60 + "B" * 60, 100)
        assert "[...truncated...]" in result
        assert result.startswith("A" * 50)
        assert result.endswith("B" * 50)


# ---------------------------------------------------------------------------
# HTMLIngestor
# ---------------------------------------------------------------------------

class TestHTMLIngestor:
    ingestor = HTMLIngestor()

    async def test_strips_script_tags(self):
        html = "<html><body><script>alert('xss')</script><p>Hello</p></body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "alert" not in result
        assert "Hello" in result

    async def test_strips_style_tags(self):
        html = "<html><head><style>body { color: red; }</style></head><body>Text</body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "color" not in result
        assert "Text" in result

    async def test_strips_noscript_tags(self):
        html = "<html><body><noscript>Enable JS</noscript><p>Content</p></body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "Enable JS" not in result
        assert "Content" in result

    async def test_strips_iframe_tags(self):
        html = "<html><body><iframe src='evil.com'></iframe><p>Safe</p></body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "evil.com" not in result
        assert "Safe" in result

    async def test_normalizes_whitespace(self):
        html = "<html><body><p>Hello</p><p>World</p></body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        # Should not have multiple consecutive blank lines
        assert "\n\n\n" not in result
        assert "Hello" in result
        assert "World" in result

    async def test_bytes_input(self):
        html = b"<html><body><p>Test</p></body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "Test" in result

    async def test_extracts_text_from_complex_html(self):
        html = """
        <html>
        <head><title>Page Title</title><style>.x{}</style></head>
        <body>
            <nav>Nav Link 1 | Nav Link 2</nav>
            <main>
                <h1>Main Heading</h1>
                <p>Paragraph content here.</p>
            </main>
            <script>console.log('ignored');</script>
        </body>
        </html>
        """
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML)
        assert "Main Heading" in result
        assert "Paragraph content" in result
        assert "console.log" not in result
        assert ".x{}" not in result

    async def test_truncation_applied(self):
        # Generate HTML with large body
        body = "<p>" + "word " * 10000 + "</p>"
        html = f"<html><body>{body}</body></html>"
        result = await self.ingestor.ingest(html, CONTENT_TYPE_HTML, max_chars=500)
        assert len(result) <= 500 + len("\n\n[...truncated...]\n\n")


# ---------------------------------------------------------------------------
# PDFIngestor
# ---------------------------------------------------------------------------

class TestPDFIngestor:
    ingestor = PDFIngestor()

    async def test_rejects_str_input(self):
        with pytest.raises(ValueError, match="expects bytes"):
            await self.ingestor.ingest("not bytes", CONTENT_TYPE_PDF)

    async def test_invalid_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to open PDF"):
            await self.ingestor.ingest(b"not a pdf", CONTENT_TYPE_PDF)

    async def test_valid_pdf_extraction(self):
        """Test with a minimal valid PDF if PyMuPDF is available."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        # Create a minimal in-memory PDF with one page and text
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), "Hello from PDF test")
        pdf_bytes = doc.tobytes()
        doc.close()

        result = await self.ingestor.ingest(pdf_bytes, CONTENT_TYPE_PDF)
        assert "Hello from PDF test" in result

    async def test_pdf_truncation(self):
        """Test truncation on a PDF with a lot of text."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")

        doc = fitz.open()
        page = doc.new_page()
        long_text = "word " * 5000
        page.insert_text((50, 100), long_text, fontsize=6)
        pdf_bytes = doc.tobytes()
        doc.close()

        result = await self.ingestor.ingest(pdf_bytes, CONTENT_TYPE_PDF, max_chars=500)
        assert len(result) <= 500 + len("\n\n[...truncated...]\n\n")


# ---------------------------------------------------------------------------
# JSONIngestor
# ---------------------------------------------------------------------------

class TestJSONIngestor:
    ingestor = JSONIngestor()

    async def test_valid_json_serialized(self):
        data = {"name": "Alice", "age": 30}
        raw = json.dumps(data)
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_JSON)
        parsed = json.loads(result)
        assert parsed == data

    async def test_output_is_indented(self):
        raw = '{"x":1}'
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_JSON)
        # Indented output has newlines
        assert "\n" in result

    async def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            await self.ingestor.ingest("{not valid json}", CONTENT_TYPE_JSON)

    async def test_json_list_input(self):
        raw = '[1, 2, 3]'
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_JSON)
        assert json.loads(result) == [1, 2, 3]

    async def test_bytes_input(self):
        data = {"key": "value"}
        raw = json.dumps(data).encode("utf-8")
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_JSON)
        assert json.loads(result) == data

    async def test_truncation_applied(self):
        big = {"data": "x" * 10000}
        raw = json.dumps(big)
        result = await self.ingestor.ingest(raw, CONTENT_TYPE_JSON, max_chars=500)
        assert "[...truncated...]" in result


# ---------------------------------------------------------------------------
# AutoIngestor — MIME type routing
# ---------------------------------------------------------------------------

class TestAutoIngestor:
    ingestor = AutoIngestor()

    async def test_routes_html_by_mime(self):
        html = "<html><body><p>Hello</p></body></html>"
        result = await self.ingestor.ingest(html, "text/html")
        assert "Hello" in result

    async def test_routes_json_by_mime(self):
        data = '{"key": "value"}'
        result = await self.ingestor.ingest(data, "application/json")
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    async def test_routes_text_by_mime(self):
        result = await self.ingestor.ingest("plain text", "text/plain")
        assert result == "plain text"

    async def test_routes_text_by_default(self):
        result = await self.ingestor.ingest("unknown", "application/octet-stream")
        assert result == "unknown"

    async def test_sniffs_html_from_bytes(self):
        html = b"<html><body><p>Sniffed HTML</p></body></html>"
        result = await self.ingestor.ingest(html, "")
        assert "Sniffed HTML" in result

    async def test_sniffs_pdf_magic_bytes(self):
        # PDF magic bytes followed by garbage — will fail to parse, but routing is what we test
        detected = _detect_content_type(b"%PDF-garbage", "")
        assert detected == "pdf"

    async def test_detects_html_content_type_with_charset(self):
        # MIME types often have charset parameter
        detected = _detect_content_type("<p>test</p>", "text/html; charset=utf-8")
        assert detected == "html"

    async def test_routes_pdf_by_mime(self):
        detected = _detect_content_type(b"", "application/pdf")
        assert detected == "pdf"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    def test_all_ingestors_registered(self):
        import app.plugins.ingestors  # noqa: F401 — triggers registration
        from app.plugins.registry import list_available

        available = list_available("ingestor")
        for name in ["text", "html", "pdf", "json", "auto"]:
            assert name in available, f"'{name}' not registered"
