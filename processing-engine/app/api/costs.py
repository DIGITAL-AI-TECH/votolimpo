from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_db, verify_api_key
from app.models.cost import BudgetStatus, CostBreakdownItem, CostReport
from app.sql.costs import (
    CHECK_BUDGET,
    SELECT_COSTS_BY_DAY,
    SELECT_COSTS_BY_MODEL,
    SELECT_COSTS_BY_PIPELINE,
    SELECT_COSTS_TOTAL,
)

router = APIRouter(tags=["Costs"])


def _default_start() -> datetime:
    """Default start: beginning of current month."""
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _default_end() -> datetime:
    """Default end: now."""
    return datetime.now(UTC)


@router.get("/costs", response_model=CostReport, summary="Relatório de custos LLM")
async def get_costs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    pipeline_id: Annotated[uuid.UUID | None, Query(description="Filtrar por pipeline")] = None,
    job_id: Annotated[uuid.UUID | None, Query(description="Filtrar por job")] = None,
    group_by: Annotated[str, Query(description="Agrupar por: pipeline, model, day")] = "pipeline",
    start_date: Annotated[datetime | None, Query(description="Data início (ISO 8601)")] = None,
    end_date: Annotated[datetime | None, Query(description="Data fim (ISO 8601)")] = None,
) -> CostReport:
    start = start_date or _default_start()
    end = end_date or _default_end()

    # Choose query based on group_by
    query_map = {
        "pipeline": SELECT_COSTS_BY_PIPELINE,
        "model": SELECT_COSTS_BY_MODEL,
        "day": SELECT_COSTS_BY_DAY,
    }
    query = query_map.get(group_by, SELECT_COSTS_BY_PIPELINE)

    # Fetch breakdown
    records = await conn.fetch(query, pipeline_id, job_id, start, end)
    breakdown = [
        CostBreakdownItem(
            label=str(r["label"]),
            total_calls=r["total_calls"],
            prompt_tokens=r["prompt_tokens"],
            completion_tokens=r["completion_tokens"],
            total_tokens=r["total_tokens"],
            total_cost_usd=float(r["total_cost_usd"]),
        )
        for r in records
    ]

    # Fetch totals
    totals = await conn.fetchrow(SELECT_COSTS_TOTAL, pipeline_id, job_id, start, end)

    return CostReport(
        total_cost_usd=float(totals["total_cost_usd"]) if totals else 0.0,
        total_calls=totals["total_calls"] if totals else 0,
        total_tokens=totals["total_tokens"] if totals else 0,
        breakdown=breakdown,
        period=group_by,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )


@router.get(
    "/costs/budget/{pipeline_id}",
    response_model=BudgetStatus,
    summary="Status do orçamento do pipeline",
)
async def get_budget_status(
    pipeline_id: uuid.UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> BudgetStatus:
    record = await conn.fetchrow(CHECK_BUDGET, pipeline_id)
    if record is None:
        return BudgetStatus(pipeline_id=pipeline_id)
    return BudgetStatus(
        pipeline_id=pipeline_id,
        current_cost=float(record["current_cost"] or 0),
        budget_limit=float(record["budget_limit"]) if record["budget_limit"] is not None else None,
        pct_used=float(record["pct_used"] or 0),
        is_exceeded=bool(record["is_exceeded"]),
    )
