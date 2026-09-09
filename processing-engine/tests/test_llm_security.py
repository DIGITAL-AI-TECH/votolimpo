"""Tests for LLM plugin security (path traversal, cost estimation)."""

import json
import os
import tempfile

import pytest

from app.plugins.llm import _safe_resolve, _estimate_cost, load_system_prompt, load_output_schema


class TestSafeResolve:
    def test_simple_filename(self, tmp_path):
        (tmp_path / "prompt.txt").write_text("hello")
        result = _safe_resolve("prompt.txt", str(tmp_path))
        assert result == tmp_path / "prompt.txt"

    def test_path_traversal_stripped_to_filename(self, tmp_path):
        """Path traversal attempts are neutralized — .name extracts only filename."""
        result = _safe_resolve("../../etc/passwd", str(tmp_path))
        assert result.name == "passwd"
        assert str(result).startswith(str(tmp_path))

    def test_absolute_path_stripped_to_filename(self, tmp_path):
        """Absolute paths are reduced to just the filename."""
        result = _safe_resolve("/etc/passwd", str(tmp_path))
        assert result.name == "passwd"
        assert str(result).startswith(str(tmp_path))

    def test_nested_traversal_stripped(self, tmp_path):
        """Nested traversal attempts result in just the filename."""
        result = _safe_resolve("foo/../../bar", str(tmp_path))
        assert result.name == "bar"
        assert str(result).startswith(str(tmp_path))


class TestLoadSystemPrompt:
    def test_loads_from_prompts_dir(self, tmp_path, monkeypatch):
        (tmp_path / "test.txt").write_text("system prompt content")
        monkeypatch.setattr("app.plugins.llm.settings.prompts_dir", str(tmp_path))
        result = load_system_prompt("test.txt")
        assert result == "system prompt content"

    def test_blocks_traversal(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.plugins.llm.settings.prompts_dir", str(tmp_path))
        with pytest.raises((ValueError, FileNotFoundError)):
            load_system_prompt("../../etc/passwd")


class TestLoadOutputSchema:
    def test_loads_json_schema(self, tmp_path, monkeypatch):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        (tmp_path / "test.json").write_text(json.dumps(schema))
        monkeypatch.setattr("app.plugins.llm.settings.schemas_dir", str(tmp_path))
        result = load_output_schema("test.json")
        assert result == schema


class TestCostEstimation:
    def test_known_model(self):
        cost = _estimate_cost("gpt-4.1-mini", 1000, 500)
        expected = (1000 / 1_000_000) * 0.40 + (500 / 1_000_000) * 1.60
        assert cost == round(expected, 6)

    def test_unknown_model_uses_default(self):
        cost = _estimate_cost("unknown-model", 1000, 500)
        # Default is same as gpt-4.1-mini pricing
        expected = (1000 / 1_000_000) * 0.40 + (500 / 1_000_000) * 1.60
        assert cost == round(expected, 6)

    def test_zero_tokens(self):
        assert _estimate_cost("gpt-4.1-mini", 0, 0) == 0.0

    def test_gpt4o_pricing(self):
        cost = _estimate_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost == round(2.50 + 10.00, 6)
