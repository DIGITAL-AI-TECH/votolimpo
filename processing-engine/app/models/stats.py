from __future__ import annotations

from pydantic import BaseModel


class Stats(BaseModel):
    period: str = "all"
    total_jobs: int = 0
    total_items: int = 0
    items_completed: int = 0
    items_failed: int = 0
    items_duplicate: int = 0
    success_rate: float = 0.0
    total_cost_usd: float = 0.0
    avg_duration_ms: float = 0.0
    cache_hit_rate: float = 0.0
    dedup_rate: float = 0.0
