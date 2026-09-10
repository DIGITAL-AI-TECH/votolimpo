"""Tests for pipeline config loading."""

import tempfile
from pathlib import Path

import pytest
import yaml

from app.core.pipeline_config import (
    PipelineConfig,
    load_pipelines,
    get_pipeline,
    _registry,
    _normalize_yaml,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear pipeline registry before each test."""
    _registry.clear()
    yield
    _registry.clear()


def _write_yaml(directory: Path, filename: str, data: dict):
    (directory / filename).write_text(yaml.dump(data))


class TestLoadPipelines:
    def test_loads_valid_yaml(self, tmp_path):
        _write_yaml(tmp_path, "test.yaml", {
            "id": "test-pipeline",
            "name": "Test Pipeline",
            "version": "1.0",
        })
        count = load_pipelines(str(tmp_path))
        assert count == 1
        assert get_pipeline("test-pipeline") is not None

    def test_returns_zero_for_empty_dir(self, tmp_path):
        assert load_pipelines(str(tmp_path)) == 0

    def test_returns_zero_for_nonexistent_dir(self):
        assert load_pipelines("/nonexistent/path") == 0

    def test_skips_invalid_yaml(self, tmp_path):
        (tmp_path / "bad.yaml").write_text("not: valid: yaml: [")
        _write_yaml(tmp_path, "good.yaml", {
            "id": "good",
            "name": "Good",
        })
        count = load_pipelines(str(tmp_path))
        assert count == 1

    def test_full_pipeline_config(self, tmp_path):
        _write_yaml(tmp_path, "full.yaml", {
            "id": "full-test",
            "name": "Full Test",
            "version": "2.0",
            "ingestor": {"type": "html", "config": {"strip_scripts": True}},
            "dedup": {"strategy": "composite"},
            "llm": {"provider": "openai", "model": "gpt-4.1-mini", "temperature": 0.1},
            "validators": [
                {"type": "json_schema", "config": {}},
                {"type": "grounding", "config": {"check_fields": []}},
            ],
            "sink": {"type": "postgresql", "config": {"schema": "votolimpo"}},
            "cache": {"enabled": True, "ttl_hours": 168},
        })
        load_pipelines(str(tmp_path))
        p = get_pipeline("full-test")
        assert p is not None
        assert p.version == "2.0"
        assert p.ingestor.type == "html"
        assert p.dedup.strategy == "composite"
        assert p.llm.model == "gpt-4.1-mini"
        assert len(p.validators) == 2
        assert p.sink.type == "postgresql"
        assert p.cache.ttl_hours == 168


class TestNormalizeYaml:
    """Test flat YAML → nested PipelineConfig translation."""

    def test_auto_generates_id_from_name(self):
        result = _normalize_yaml({"name": "My Pipeline"})
        assert result["id"] == "my-pipeline"

    def test_flat_ingestor(self):
        result = _normalize_yaml({"name": "t", "ingestor_type": "html"})
        assert result["ingestor"] == {"type": "html"}
        assert "ingestor_type" not in result

    def test_flat_dedup(self):
        result = _normalize_yaml({
            "name": "t",
            "dedup_strategy": "composite",
            "dedup_config": {"strategies": ["hash"]},
        })
        assert result["dedup"]["strategy"] == "composite"
        assert result["dedup"]["config"]["strategies"] == ["hash"]

    def test_flat_llm(self):
        result = _normalize_yaml({
            "name": "t",
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
            "llm_temperature": 0.1,
        })
        assert result["llm"]["provider"] == "openai"
        assert result["llm"]["model"] == "gpt-4.1-mini"

    def test_flat_sink(self):
        result = _normalize_yaml({
            "name": "t",
            "sink_type": "postgresql",
            "sink_config": {"table": "votolimpo.articles"},
        })
        assert result["sink"]["type"] == "postgresql"

    def test_string_validators_expanded(self):
        result = _normalize_yaml({
            "name": "t",
            "validators": ["schema", "grounding"],
            "validator_config": {"grounding": {"min_overlap_ratio": 0.3}},
        })
        assert result["validators"][0] == {"type": "schema", "config": {}}
        assert result["validators"][1]["type"] == "grounding"
        assert result["validators"][1]["config"]["min_overlap_ratio"] == 0.3

    def test_crons_name_handler_normalized(self):
        result = _normalize_yaml({
            "name": "t",
            "crons": [
                {"name": "recalc", "schedule": "0 3 * * *", "handler": "score.recalc"},
            ],
        })
        assert result["crons"][0]["type"] == "recalc"
        assert result["crons"][0]["config"]["handler"] == "score.recalc"

    def test_nested_format_passes_through(self):
        """Already-nested format should not be altered."""
        data = {
            "id": "my-pipe",
            "name": "test",
            "ingestor": {"type": "html"},
            "validators": [{"type": "schema", "config": {}}],
        }
        result = _normalize_yaml(data)
        assert result["ingestor"]["type"] == "html"
        assert result["validators"][0]["type"] == "schema"


class TestLoadRealYaml:
    """Integration test: load the actual pipeline YAML."""

    def test_loads_voto_limpo_yaml(self):
        yaml_dir = Path(__file__).parent.parent / "pipelines"
        if not yaml_dir.exists():
            pytest.skip("pipelines/ directory not found")

        count = load_pipelines(str(yaml_dir))
        assert count >= 1, "Should load at least the voto-limpo pipeline"

        # Verify the pipeline loaded correctly
        p = get_pipeline("voto-limpo-news-analysis")
        assert p is not None, "voto-limpo-news-analysis should be loadable"
        assert p.name == "voto-limpo-news-analysis"
        assert p.ingestor.type == "auto"
        assert p.dedup.strategy == "composite"
        assert p.llm.provider == "openai"
        assert p.llm.model == "gpt-4.1-mini"
        assert len(p.validators) == 3
        assert len(p.post_processors) == 6
        assert len(p.crons) == 5
        assert p.sink.type == "postgresql"


class TestGetPipeline:
    def test_returns_none_for_unknown(self):
        assert get_pipeline("nonexistent") is None
