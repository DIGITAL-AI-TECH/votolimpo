from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI

from app.config import settings
from app.db import close_pool, create_pool

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_worker_task: asyncio.Task | None = None
_auto_batcher = None


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
    global _worker_task, _auto_batcher

    # --- Startup ---
    logger.info("Starting Processing Engine (role=%s)", settings.ENGINE_ROLE)
    if settings.DATABASE_URL:
        db_pool = await create_pool(dsn=settings.DATABASE_URL)
    else:
        db_pool = await create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
        )

    if settings.ENGINE_ROLE in ("worker", "both"):
        _worker_task = asyncio.create_task(_run_worker(), name="processing-worker")
        logger.info("Background worker task created")

    # Start Auto-Batcher if enabled and not API-only
    if settings.BATCHER_ENABLED and settings.ENGINE_ROLE != "api":
        from app.services.auto_batcher import AutoBatcher

        _auto_batcher = AutoBatcher(
            pool=db_pool,
            poll_interval=settings.BATCHER_POLL_INTERVAL_SECONDS,
            batch_size=settings.BATCHER_DEFAULT_BATCH_SIZE,
        )
        await _auto_batcher.start()

    yield

    # --- Shutdown ---
    logger.info("Shutting down Processing Engine")

    if _auto_batcher is not None:
        await _auto_batcher.stop()
        _auto_batcher = None

    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await _worker_task
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
from app.api.costs import router as costs_router  # noqa: E402
from app.api.jobs import router as jobs_router  # noqa: E402
from app.api.pipelines import router as pipelines_router  # noqa: E402
from app.api.pool import router as pool_router  # noqa: E402
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
app.include_router(
    pool_router,
    prefix="/v1",
    dependencies=[Depends(verify_api_key)],
)
