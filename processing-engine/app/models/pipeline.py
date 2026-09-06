from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PipelineCreate(BaseModel):
    """Schema para criação de pipeline — espelha PipelineCreate do OpenAPI."""

    model_config = ConfigDict(str_strip_whitespace=True)

    # Identificação
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    # Ingestor
    ingestor_type: str = Field(default="auto")
    max_content_chars: int = Field(default=100_000)

    # Dedup
    dedup_strategy: str = Field(default="hash")
    dedup_threshold: float = Field(default=0.90, ge=0.0, le=1.0)

    # LLM
    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-4.1-mini")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_seed: int | None = Field(default=42)
    llm_max_tokens: int = Field(default=16_384)
    system_prompt: str = Field(..., min_length=1)

    # Output
    output_schema: dict[str, Any] = Field(...)

    # Validators
    validators: list[str] = Field(default_factory=lambda: ["schema"])

    # Sink
    sink_type: str = Field(default="postgresql")
    sink_config: dict[str, Any] = Field(default_factory=dict)

    # Rate limiting
    max_concurrent: int = Field(default=5, ge=1, le=50)
    rate_limit_rpm: int = Field(default=60, ge=1)

    # Budget
    budget_limit_usd: float | None = Field(default=None, ge=0.0)
    budget_period: str = Field(default="month")

    # Retry
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_backoff_base: float = Field(default=2.0)

    # Cache
    cache_ttl_hours: int = Field(default=720, ge=0)

    @field_validator("ingestor_type")
    @classmethod
    def validate_ingestor_type(cls, v: str) -> str:
        allowed = {"html", "pdf", "text", "json", "auto"}
        if v not in allowed:
            raise ValueError(f"ingestor_type deve ser um de: {sorted(allowed)}")
        return v

    @field_validator("dedup_strategy")
    @classmethod
    def validate_dedup_strategy(cls, v: str) -> str:
        allowed = {"hash", "semantic", "composite", "none"}
        if v not in allowed:
            raise ValueError(f"dedup_strategy deve ser um de: {sorted(allowed)}")
        return v

    @field_validator("budget_period")
    @classmethod
    def validate_budget_period(cls, v: str) -> str:
        allowed = {"day", "week", "month"}
        if v not in allowed:
            raise ValueError(f"budget_period deve ser um de: {sorted(allowed)}")
        return v


class Pipeline(PipelineCreate):
    """Schema de resposta — inclui campos gerados pelo banco."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
