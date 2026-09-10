"""Pipeline configuration loader — reads YAML configs from pipelines/ directory."""

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


class PostProcessorEntry(BaseModel):
    type: str
    config: dict[str, Any] = Field(default_factory=dict)


class SinkConfig(BaseModel):
    type: str = "postgresql"
    config: dict[str, Any] = Field(default_factory=dict)


class CronEntry(BaseModel):
    type: str
    schedule: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_hours: int = 720
    key_strategy: str = "content_hash"


class PipelineConfig(BaseModel):
    """Full pipeline configuration loaded from YAML."""
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    ingestor: IngestorConfig = Field(default_factory=IngestorConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    system_prompt: str | None = None
    user_prompt_template: str | None = None
    output_schema: dict[str, Any] | None = None
    validators: list[ValidatorEntry] = Field(default_factory=list)
    validator_config: dict[str, Any] = Field(default_factory=dict)
    post_processors: list[PostProcessorEntry] = Field(default_factory=list)
    sink: SinkConfig = Field(default_factory=SinkConfig)
    crons: list[CronEntry] = Field(default_factory=list)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    max_concurrent: int = 5
    rate_limit_rpm: int = 60
    max_retries: int = 1
    cache_ttl_hours: int = 720
    budget_limit_usd: float | None = None
    budget_period: str | None = None


# In-memory registry of loaded pipelines
_registry: dict[str, PipelineConfig] = {}


def _normalize_yaml(raw: dict) -> dict:
    """Translate flat YAML keys to nested PipelineConfig structure.

    Supports both flat (human-friendly YAML) and nested (direct PipelineConfig) formats.
    """
    data = dict(raw)

    # Auto-generate ID from name if missing
    if "id" not in data and "name" in data:
        data["id"] = data["name"].lower().replace(" ", "-")

    # Flat ingestor → nested
    if "ingestor_type" in data and "ingestor" not in data:
        data["ingestor"] = {"type": data.pop("ingestor_type")}

    # Flat dedup → nested
    if "dedup_strategy" in data and "dedup" not in data:
        dedup = {"strategy": data.pop("dedup_strategy")}
        if "dedup_config" in data:
            dedup["config"] = data.pop("dedup_config")
        data["dedup"] = dedup

    # Flat LLM → nested
    llm_flat_keys = {
        "llm_provider": "provider", "llm_model": "model",
        "llm_temperature": "temperature", "llm_max_tokens": "max_tokens",
        "llm_seed": None,  # not in LLMConfig, skip
    }
    if any(k in data for k in llm_flat_keys) and "llm" not in data:
        llm = {}
        for flat_key, nested_key in llm_flat_keys.items():
            if flat_key in data:
                val = data.pop(flat_key)
                if nested_key:
                    llm[nested_key] = val
        data["llm"] = llm

    # Flat sink → nested
    if "sink_type" in data and "sink" not in data:
        sink = {"type": data.pop("sink_type")}
        if "sink_config" in data:
            sink["config"] = data.pop("sink_config")
        data["sink"] = sink

    # Validators: list of strings → list of ValidatorEntry dicts
    if data.get("validators"):
        validator_config = data.get("validator_config", {})
        normalized = []
        for v in data["validators"]:
            if isinstance(v, str):
                normalized.append({"type": v, "config": validator_config.get(v, {})})
            elif isinstance(v, dict):
                normalized.append(v)
        data["validators"] = normalized

    # Crons: normalize name/handler format → type/schedule format
    if "crons" in data:
        normalized_crons = []
        for c in data["crons"]:
            if isinstance(c, dict):
                if "name" in c and "type" not in c:
                    c = dict(c)
                    c["type"] = c.pop("name")
                    if "handler" in c:
                        c.setdefault("config", {})["handler"] = c.pop("handler")
                normalized_crons.append(c)
        data["crons"] = normalized_crons

    return data


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
            pipeline_data = _normalize_yaml(raw.get("pipeline", raw))
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
