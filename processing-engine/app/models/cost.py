from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelPricingCreate(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    input_price_per_million_tokens: float = Field(..., ge=0.0)
    output_price_per_million_tokens: float = Field(default=0.0, ge=0.0)
    is_active: bool = True
    effective_from: date | None = None


class ModelPricing(ModelPricingCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CostBreakdownItem(BaseModel):
    label: str  # pipeline name, model name, date, etc.
    total_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class CostReport(BaseModel):
    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_tokens: int = 0
    breakdown: list[CostBreakdownItem] = Field(default_factory=list)
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class BudgetStatus(BaseModel):
    pipeline_id: uuid.UUID
    current_cost: float = 0.0
    budget_limit: float | None = None
    pct_used: float = 0.0
    is_exceeded: bool = False
