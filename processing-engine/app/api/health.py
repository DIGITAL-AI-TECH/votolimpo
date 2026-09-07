from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db import get_pool

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check - no auth required. Returns 503 if DB is not connected."""
    db_connected = False
    worker_active = False
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_connected = True
    except Exception:
        pass

    # Check if worker is running (import at call time to avoid circular)
    try:
        from app.main import _worker_task

        worker_active = _worker_task is not None and not _worker_task.done()
    except Exception:
        pass

    from app.config import settings

    status_code = 200 if db_connected else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_connected else "degraded",
            "version": settings.APP_VERSION,
            "db_connected": db_connected,
            "worker_active": worker_active,
        },
    )
