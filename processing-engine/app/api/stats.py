from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_db, verify_api_key
from app.models.stats import Stats
from app.sql.stats import SELECT_STATS

router = APIRouter(tags=["Stats"])


def _period_to_range(period: str) -> tuple[datetime, datetime]:
    """Convert period string to (start, end) datetime range."""
    now = datetime.now(timezone.utc)
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        # Monday of current week
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = start.replace(day=start.day - start.weekday())
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # "all"
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return start, now


@router.get("/stats", response_model=Stats, summary="Métricas agregadas de processamento")
async def get_stats(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    pipeline_id: Annotated[uuid.UUID | None, Query(description="Filtrar por pipeline")] = None,
    period: Annotated[str, Query(description="Período: day, week, month, all")] = "all",
) -> Stats:
    start, end = _period_to_range(period)
    record = await conn.fetchrow(SELECT_STATS, pipeline_id, start, end)

    if record is None:
        return Stats(period=period)

    return Stats(
        period=period,
        total_jobs=record["total_jobs"],
        total_items=record["total_items"],
        items_completed=record["items_completed"],
        items_failed=record["items_failed"],
        items_duplicate=record["items_duplicate"],
        success_rate=float(record["success_rate"]),
        total_cost_usd=float(record["total_cost_usd"]),
        avg_duration_ms=float(record["avg_duration_ms"]),
        cache_hit_rate=float(record["cache_hit_rate"]),
        dedup_rate=float(record["dedup_rate"]),
    )
