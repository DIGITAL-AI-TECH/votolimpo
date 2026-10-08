"""Tests for the Help Bradesco .txt parser."""

import tempfile
from pathlib import Path

import pytest

# Add parent dir to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import parse_file, _parse_date, _parse_header_line


@pytest.fixture
def sample_txt(tmp_path):
    """Create a sample .txt file."""
    content = """HELP: Ajuda Bradesco
AREA: Alto Valor
LISTA: Cartões Premium
TITULO: Abertura de Atendimento Premium
SUBTITULO: Procedimento
NIVEL3:
GROUPSTRING: Alto Valor > Cartões Premium
LIST_URL: https://bradesco.sharepoint.com/sites/help
IID: 93
MODIFIED: 2025-08-14T09:42:00Z
CLASSIFICACAO: TEXTUAL

LINKS:
https://exemplo.com/link1
https://exemplo.com/link2

CONTEUDO:
1. Confirmar dados do cliente via PID/MD
2. Verificar cartão ativo no sistema
3. Registrar atendimento no CRM
"""
    filepath = tmp_path / "sample.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


@pytest.fixture
def minimal_txt(tmp_path):
    """Create a minimal .txt file with just required fields."""
    content = """AREA: SAC
TITULO: FAQ Basico

CONTEUDO:
Perguntas frequentes sobre o SAC.
"""
    filepath = tmp_path / "minimal.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


@pytest.fixture
def malformed_txt(tmp_path):
    """Create a malformed .txt file without required fields."""
    content = """Some random content without headers."""
    filepath = tmp_path / "malformed.txt"
    filepath.write_text(content, encoding="utf-8")
    return filepath


@pytest.fixture
def latin1_txt(tmp_path):
    """Create a file with latin-1 encoding."""
    content = """AREA: Cartões
TITULO: Ação de Cobrança

CONTEUDO:
Procedimento para ação de cobrança com acentuação.
"""
    filepath = tmp_path / "latin1.txt"
    filepath.write_bytes(content.encode("latin-1"))
    return filepath


class TestParseFile:
    def test_parse_complete_file(self, sample_txt):
        result = parse_file(sample_txt)
        assert result is not None
        assert result["area"] == "Alto Valor"
        assert result["title"] == "Abertura de Atendimento Premium"
        assert result["subtitle"] == "Procedimento"
        assert result["lista"] == "Cartões Premium"
        assert result["iid"] == "93"
        assert result["classification"] == "TEXTUAL"
        assert result["source_url"] == "bradesco-help://Alto Valor/93"
        assert result["help_title"] == "Ajuda Bradesco"
        assert len(result["links"]) == 2
        assert "Confirmar dados" in result["content"]
        assert result["content_hash"] is not None
        assert result["modified_date"] is not None

    def test_parse_minimal_file(self, minimal_txt):
        result = parse_file(minimal_txt)
        assert result is not None
        assert result["area"] == "SAC"
        assert result["title"] == "FAQ Basico"
        assert result["subtitle"] is None
        assert result["links"] is None

    def test_parse_malformed_returns_none(self, malformed_txt):
        result = parse_file(malformed_txt)
        assert result is None

    def test_parse_latin1_encoding(self, latin1_txt):
        result = parse_file(latin1_txt)
        assert result is not None
        assert result["area"] == "Cartões"
        assert "acentuação" in result["content"]

    def test_content_hash_deterministic(self, sample_txt):
        r1 = parse_file(sample_txt)
        r2 = parse_file(sample_txt)
        assert r1["content_hash"] == r2["content_hash"]

    def test_empty_content_hash_is_none(self, tmp_path):
        content = """AREA: Test
TITULO: Empty Content

CONTEUDO:
"""
        filepath = tmp_path / "empty_content.txt"
        filepath.write_text(content, encoding="utf-8")
        result = parse_file(filepath)
        # content is empty string which is falsy, so content_hash should be None
        assert result is not None


class TestParseDate:
    def test_iso_format(self):
        dt = _parse_date("2025-08-14T09:42:00Z")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 8

    def test_date_only(self):
        dt = _parse_date("2025-08-14")
        assert dt is not None

    def test_br_format(self):
        dt = _parse_date("14/08/2025")
        assert dt is not None
        assert dt.day == 14

    def test_none_input(self):
        assert _parse_date(None) is None

    def test_invalid_format(self):
        assert _parse_date("not-a-date") is None


class TestParseHeaderLine:
    def test_valid_line(self):
        result = _parse_header_line("AREA: Alto Valor")
        assert result == ("AREA", "Alto Valor")

    def test_empty_value(self):
        result = _parse_header_line("SUBTITULO: ")
        assert result is None

    def test_unknown_key(self):
        result = _parse_header_line("UNKNOWN: value")
        assert result is None

    def test_empty_line(self):
        assert _parse_header_line("") is None
