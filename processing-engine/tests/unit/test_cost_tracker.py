from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.cost_tracker import BudgetExceededError, CostTracker


@pytest.fixture
def mock_conn():
    return AsyncMock()


@pytest.fixture
def tracker():
    return CostTracker()


class TestCostTracker:
    @pytest.mark.asyncio
    async def test_calculate_cost_with_pricing(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value={
            "input_price_per_million_tokens": 0.40,
            "output_price_per_million_tokens": 1.60,
        })
        cost = await tracker.calculate_cost(mock_conn, "openai", "gpt-4.1-mini", 1000, 500)
        # (1000 * 0.40 / 1M) + (500 * 1.60 / 1M) = 0.0004 + 0.0008 = 0.0012
        assert abs(cost - 0.0012) < 1e-6

    @pytest.mark.asyncio
    async def test_calculate_cost_no_pricing_returns_zero(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value=None)
        cost = await tracker.calculate_cost(mock_conn, "unknown", "model", 1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_log_call_inserts_record(self, mock_conn, tracker):
        pipeline_id = uuid.uuid4()
        item_id = uuid.uuid4()

        # Mock pricing lookup
        mock_conn.fetchrow = AsyncMock(side_effect=[
            # First call: calculate_cost -> pricing lookup
            {"input_price_per_million_tokens": 0.40, "output_price_per_million_tokens": 1.60},
            # Second call: INSERT_LLM_CALL
            {"id": uuid.uuid4(), "cost_usd": 0.0012},
        ])

        result = await tracker.log_call(
            mock_conn,
            item_id=item_id,
            job_id=None,
            pipeline_id=pipeline_id,
            provider="openai",
            model="gpt-4.1-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            latency_ms=200,
        )
        assert result["cost_usd"] == 0.0012

    @pytest.mark.asyncio
    async def test_check_budget_not_exceeded(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value={
            "current_cost": 5.0,
            "budget_limit": 100.0,
            "pct_used": 5.0,
            "is_exceeded": False,
        })
        result = await tracker.check_budget(mock_conn, uuid.uuid4())
        assert result["is_exceeded"] is False
        assert result["pct_used"] == 5.0

    @pytest.mark.asyncio
    async def test_check_budget_exceeded(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value={
            "current_cost": 100.5,
            "budget_limit": 100.0,
            "pct_used": 100.5,
            "is_exceeded": True,
        })
        result = await tracker.check_budget(mock_conn, uuid.uuid4())
        assert result["is_exceeded"] is True

    @pytest.mark.asyncio
    async def test_enforce_budget_raises_when_exceeded(self, mock_conn, tracker):
        pipeline_id = uuid.uuid4()
        mock_conn.fetchrow = AsyncMock(return_value={
            "current_cost": 150.0,
            "budget_limit": 100.0,
            "pct_used": 150.0,
            "is_exceeded": True,
        })
        with pytest.raises(BudgetExceededError) as exc_info:
            await tracker.enforce_budget(mock_conn, pipeline_id)
        assert exc_info.value.pipeline_id == pipeline_id
        assert exc_info.value.current_cost == 150.0

    @pytest.mark.asyncio
    async def test_enforce_budget_passes_when_not_exceeded(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value={
            "current_cost": 50.0,
            "budget_limit": 100.0,
            "pct_used": 50.0,
            "is_exceeded": False,
        })
        # Should not raise
        await tracker.enforce_budget(mock_conn, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_check_budget_no_limit(self, mock_conn, tracker):
        mock_conn.fetchrow = AsyncMock(return_value={
            "current_cost": 0.0,
            "budget_limit": None,
            "pct_used": 0.0,
            "is_exceeded": False,
        })
        result = await tracker.check_budget(mock_conn, uuid.uuid4())
        assert result["budget_limit"] is None
        assert result["is_exceeded"] is False
