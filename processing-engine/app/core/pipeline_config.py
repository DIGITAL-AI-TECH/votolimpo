"""Pipeline configuration loader — reads YAML configs from pipelines/ directory."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..config import settings


class IngestorConfig(BaseModel):
    type: str = "raw_text"
    config: dict[str, Any] = Field(default_factory=dict)


class DedupConfig(BaseModel):
    strategy: str = "hash"
    config: dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    temperature: float = 0.1
    max_tokens: int = 4096
    max_retries: int = 1
    system_prompt_file: str | None = None
    output_schema_file: str | None = None


class ValidatorEntry(BaseModel):
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class SinkMapping(BaseModel):
    source_path: str
    target_table: str
    strategy: str = "insert"
    key_column: str | None = None


class SinkConfig(BaseModel):
    type: str = "postgresql"
    config: dict[str, Any] = Field(default_factory=dict)


class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_hours: int = 720
    key_strategy: str = "content_hash"


class PipelineConfig(BaseModel):
    """Full pipeline configuration loaded from YAML."""
    id: str
    name: str
    version: str = "1.0"
    ingestor: IngestorConfig = Field(default_factory=IngestorConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    validators: list[ValidatorEntry] = Field(default_factory=list)
    sink: SinkConfig = Field(default_factory=SinkConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


# In-memory registry of loaded pipelines
_registry: dict[str, PipelineConfig] = {}


def load_pipelines(directory: str | None = None) -> int:
    """Load all YAML pipeline configs from directory. Returns count loaded."""
    global _registry
    base = Path(directory or settings.pipelines_dir)
    if not base.exists():
        return 0

    loaded = 0
    for f in base.glob("*.yaml"):
        try:
            with open(f) as fp:
                raw = yaml.safe_load(fp)
            pipeline_data = raw.get("pipeline", raw)
            config = PipelineConfig(**pipeline_data)
            _registry[config.id] = config
            loaded += 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Failed to load pipeline %s: %s", f, e)

    return loaded


def get_pipeline(pipeline_id: str) -> PipelineConfig | None:
    """Get a pipeline config by ID."""
    return _registry.get(pipeline_id)


def list_pipelines() -> list[PipelineConfig]:
    """Return all loaded pipeline configs (W7: public accessor)."""
    return list(_registry.values())
