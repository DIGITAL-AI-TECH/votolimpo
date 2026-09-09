"""Health check endpoints."""

from fastapi import APIRouter

from ...storage.database import get_pool

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 AS ok")
    return {"status": "healthy", "db": bool(row)}


@router.get("/v1/stats")
async def get_stats():
    """Processing engine statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        jobs = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'processing') AS processing,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE status = 'partial') AS partial,
                COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd,
                COUNT(*) AS total_jobs
            FROM processing_engine.jobs
        """)
        items = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE cached = true) AS cached,
                AVG(duration_ms) FILTER (WHERE status = 'completed') AS avg_duration_ms
            FROM processing_engine.job_items
        """)

    return {
        "jobs": dict(jobs) if jobs else {},
        "items": {
            "completed": items["completed"] if items else 0,
            "failed": items["failed"] if items else 0,
            "cached": items["cached"] if items else 0,
            "avg_duration_ms": round(items["avg_duration_ms"] or 0, 1) if items else 0,
        },
    }
