"""Pydantic response models for Cost/Budget API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CostBreakdownItem(BaseModel):
    """Single pipeline cost breakdown entry."""

    label: str
    total_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class CostReport(BaseModel):
    """Cost report response model."""

    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_tokens: int = 0
    breakdown: list[CostBreakdownItem] = Field(default_factory=list)
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class BudgetStatus(BaseModel):
    """Budget status for a pipeline."""

    pipeline_id: uuid.UUID
    current_cost: float = 0.0
    budget_limit: float = 0.0
    pct_used: float = 0.0
    is_exceeded: bool = False


class ModelPricing(BaseModel):
    """Model pricing entry."""

    id: uuid.UUID
    provider: str
    model: str
    input_price_per_million_tokens: float = 0.0
    output_price_per_million_tokens: float = 0.0
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
