from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI

from app.config import settings
from app.db import close_pool, create_pool

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_worker_task: asyncio.Task | None = None


async def _run_worker() -> None:
    """Background worker loop that polls for pending jobs."""
    from app.worker import Worker

    worker = Worker(poll_interval=settings.WORKER_POLL_INTERVAL_SECONDS)
    await worker.run()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan context manager.

    Startup:
      - Creates the asyncpg connection pool.
      - Starts the background worker if ENGINE_ROLE is 'worker' or 'both'.

    Shutdown:
      - Cancels the worker task (if running).
      - Closes the connection pool.
    """
    global _worker_task

    # --- Startup ---
    logger.info("Starting Processing Engine (role=%s)", settings.ENGINE_ROLE)
    await create_pool(settings.DATABASE_URL)

    if settings.ENGINE_ROLE in ("worker", "both"):
        _worker_task = asyncio.create_task(_run_worker(), name="processing-worker")
        logger.info("Background worker task created")

    yield

    # --- Shutdown ---
    logger.info("Shutting down Processing Engine")

    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None

    await close_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Processing Engine",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers — imported here so that circular imports are avoided while keeping
# each router in its own module.
# ---------------------------------------------------------------------------
from app.api import health  # noqa: E402 — must come after app is defined
from app.api.pipelines import router as pipelines_router  # noqa: E402
from app.api.jobs import router as jobs_router  # noqa: E402
from app.api.costs import router as costs_router  # noqa: E402
from app.api.pricing import router as pricing_router  # noqa: E402
from app.api.stats import router as stats_router  # noqa: E402
from app.deps import verify_api_key  # noqa: E402

app.include_router(health.router)
app.include_router(
    pipelines_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    jobs_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    costs_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    pricing_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    stats_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
