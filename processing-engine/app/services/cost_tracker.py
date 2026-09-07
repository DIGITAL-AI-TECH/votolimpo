from __future__ import annotations

import logging
import uuid
from typing import Any

import asyncpg

from app.sql.costs import CHECK_BUDGET, INSERT_LLM_CALL, SELECT_PRICING_BY_PROVIDER_MODEL

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when pipeline budget limit is exceeded."""

    def __init__(self, pipeline_id: uuid.UUID, current_cost: float, budget_limit: float):
        self.pipeline_id = pipeline_id
        self.current_cost = current_cost
        self.budget_limit = budget_limit
        super().__init__(
            f"Budget exceeded for pipeline {pipeline_id}: ${current_cost:.4f} / ${budget_limit:.2f}"
        )


class CostTracker:
    """Tracks LLM API call costs and enforces budget limits."""

    async def log_call(
        self,
        conn: asyncpg.Connection,
        *,
        item_id: uuid.UUID | None,
        job_id: uuid.UUID | None,
        pipeline_id: uuid.UUID,
        provider: str,
        model: str,
        call_type: str = "completion",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        status: str = "success",
        error_message: str | None = None,
        is_retry: bool = False,
        retry_number: int = 0,
    ) -> dict[str, Any]:
        """Log an LLM call and calculate cost from model_pricing."""
        cost = await self.calculate_cost(conn, provider, model, prompt_tokens, completion_tokens)

        record = await conn.fetchrow(
            INSERT_LLM_CALL,
            item_id,
            job_id,
            pipeline_id,
            provider,
            model,
            call_type,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost,
            latency_ms,
            status,
            error_message,
            is_retry,
            retry_number,
        )
        return dict(record) if record else {"cost_usd": cost}

    async def calculate_cost(
        self,
        conn: asyncpg.Connection,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Calculate cost using model_pricing table."""
        pricing = await conn.fetchrow(SELECT_PRICING_BY_PROVIDER_MODEL, provider, model)
        if pricing is None:
            logger.warning("No pricing found for %s/%s, using 0", provider, model)
            return 0.0
        input_price = pricing["input_price_per_million_tokens"]
        output_price = pricing["output_price_per_million_tokens"]
        return (prompt_tokens * input_price / 1_000_000) + (
            completion_tokens * output_price / 1_000_000
        )

    async def check_budget(
        self,
        conn: asyncpg.Connection,
        pipeline_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Check budget status for a pipeline.

        Returns dict with: current_cost, budget_limit, pct_used, is_exceeded
        """
        record = await conn.fetchrow(CHECK_BUDGET, pipeline_id)
        if record is None:
            return {
                "current_cost": 0.0,
                "budget_limit": None,
                "pct_used": 0.0,
                "is_exceeded": False,
            }
        result = dict(record)
        # Warn at 80%
        if result.get("pct_used", 0) >= 80 and not result.get("is_exceeded", False):
            logger.warning(
                "Pipeline %s budget at %.1f%% ($%.4f / $%.2f)",
                pipeline_id,
                result["pct_used"],
                result["current_cost"],
                result["budget_limit"],
            )
        return result

    async def enforce_budget(
        self,
        conn: asyncpg.Connection,
        pipeline_id: uuid.UUID,
    ) -> None:
        """Raise BudgetExceededError if pipeline budget is exceeded."""
        status = await self.check_budget(conn, pipeline_id)
        if status.get("is_exceeded"):
            raise BudgetExceededError(
                pipeline_id=pipeline_id,
                current_cost=status["current_cost"],
                budget_limit=status["budget_limit"],
            )
