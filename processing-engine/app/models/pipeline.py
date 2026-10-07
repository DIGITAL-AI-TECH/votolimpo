"""Pydantic response models for Pipeline API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Pipeline(BaseModel):
    """Pipeline response model — serialized shape returned by the API."""

    id: uuid.UUID
    name: str
    description: str | None = None
    version: int = 1
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ingestor_type: str = "auto"
    max_content_chars: int = 500_000
    dedup_strategy: str = "hash"
    dedup_threshold: float = 0.85
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 16384
    llm_seed: int | None = None
    system_prompt: str = ""
    output_schema: dict = Field(default_factory=dict)
    validators: list = Field(default_factory=list)
    sink_type: str = "postgresql"
    sink_config: dict = Field(default_factory=dict)
    max_concurrent: int = 5
    rate_limit_rpm: int = 60
    budget_limit_usd: float | None = None
    budget_period: str = "month"
    max_retries: int = 2
    retry_backoff_base: float = 2.0
    cache_ttl_hours: int = 720
