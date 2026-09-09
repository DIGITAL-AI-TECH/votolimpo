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


class TestGetPipeline:
    def test_returns_none_for_unknown(self):
        assert get_pipeline("nonexistent") is None
