"""Processing Engine — FastAPI application."""

import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .storage.database import get_pool, close_pool, init_engine_schema
from .core.pipeline_config import load_pipelines
from .core.orchestrator import process_next_job
from .cron import setup_cron_scheduler

logger = logging.getLogger(__name__)

# Worker task handle
_worker_task: asyncio.Task | None = None


async def _worker_loop():
    """Background worker that polls for pending jobs."""
    logger.info("Worker loop started (poll_interval=%ds)", settings.worker_poll_interval)
    while True:
        try:
            job_id = await process_next_job()
            if job_id:
                logger.info("Processed job: %s", job_id)
                continue  # Immediately check for more
            await asyncio.sleep(settings.worker_poll_interval)
        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception:
            logger.exception("Worker loop error")
            await asyncio.sleep(settings.worker_poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB, load pipelines, start worker + cron."""
    global _worker_task

    # Init DB pool + schema
    pool = await get_pool()
    await init_engine_schema(pool)
    logger.info("Database pool initialized")

    # Load pipeline configs
    count = load_pipelines(settings.pipelines_dir)
    logger.info("Loaded %d pipeline(s)", count)

    # Start worker if role includes it
    if settings.engine_role in ("worker", "both"):
        _worker_task = asyncio.create_task(_worker_loop())

    # Start cron scheduler
    scheduler = setup_cron_scheduler()
    scheduler.start()
    logger.info("Cron scheduler started")

    yield

    # Shutdown
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    scheduler.shutdown(wait=False)
    await close_pool()
    logger.info("Processing Engine shut down")


app = FastAPI(
    title="Processing Engine",
    description="Agnostic, plugin-based processing engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Import and register routes
from .api.routes import jobs, pipelines, health  # noqa: E402

app.include_router(health.router, tags=["health"])
app.include_router(jobs.router, prefix="/v1", tags=["jobs"])
app.include_router(pipelines.router, prefix="/v1", tags=["pipelines"])


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
