"""Tests for ingestor plugins."""

import pytest

from app.plugins.ingestors import get_ingestor, RawTextIngestor, HTMLIngestor


class TestRawTextIngestor:
    @pytest.mark.asyncio
    async def test_returns_content_as_is(self):
        i = RawTextIngestor()
        result = await i.ingest("Hello world", {})
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_preserves_content(self):
        i = RawTextIngestor()
        result = await i.ingest("  hello  ", {})
        assert "hello" in result


class TestHTMLIngestor:
    @pytest.mark.asyncio
    async def test_strips_html_tags(self):
        i = HTMLIngestor()
        result = await i.ingest("<p>Hello <b>world</b></p>", {})
        assert "Hello" in result
        assert "world" in result
        assert "<p>" not in result

    @pytest.mark.asyncio
    async def test_strips_script_tags(self):
        i = HTMLIngestor()
        result = await i.ingest(
            "<div>Content</div><script>alert('xss')</script>",
            {"strip_scripts": True},
        )
        assert "Content" in result
        assert "alert" not in result

    @pytest.mark.asyncio
    async def test_strips_style_tags(self):
        i = HTMLIngestor()
        result = await i.ingest(
            "<div>Content</div><style>.foo{color:red}</style>",
            {"strip_styles": True},
        )
        assert "Content" in result
        assert "color" not in result


class TestGetIngestor:
    def test_known_types(self):
        for itype in ["raw_text", "html"]:
            i = get_ingestor(itype)
            assert hasattr(i, "ingest")

    def test_unknown_falls_back_to_raw_text(self):
        i = get_ingestor("unknown")
        assert isinstance(i, RawTextIngestor)
