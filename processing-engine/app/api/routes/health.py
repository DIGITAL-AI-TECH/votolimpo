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
