"""Processing Engine — FastAPI application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .api.auth import verify_api_key
from .config import settings
from .core.orchestrator import process_next_job
from .core.pipeline_config import load_pipelines
from .cron import setup_cron_scheduler
from .storage.database import close_pool, get_pool, init_engine_schema

logger = logging.getLogger(__name__)

# Worker task handles
_worker_tasks: list[asyncio.Task] = []


async def _worker_loop(worker_id: int):
    """Background worker that polls for pending jobs (SKIP LOCKED safe)."""
    logger.info(
        "Worker %d started (poll_interval=%ds)",
        worker_id,
        settings.worker_poll_interval,
    )
    while True:
        try:
            job_id = await process_next_job()
            if job_id:
                logger.info("Worker %d processed job: %s", worker_id, job_id)
                continue  # Immediately check for more
            await asyncio.sleep(settings.worker_poll_interval)
        except asyncio.CancelledError:
            logger.info("Worker %d cancelled", worker_id)
            break
        except Exception:
            logger.exception("Worker %d loop error", worker_id)
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

    # Start N concurrent workers (SKIP LOCKED ensures no double-processing)
    if settings.engine_role in ("worker", "both"):
        num_workers = max(1, settings.worker_concurrency)
        for i in range(num_workers):
            _worker_tasks.append(asyncio.create_task(_worker_loop(i)))
        logger.info("Started %d worker(s)", num_workers)

    # Start cron scheduler
    scheduler = setup_cron_scheduler()
    scheduler.start()
    logger.info("Cron scheduler started")

    yield

    # Shutdown all workers
    for task in _worker_tasks:
        if not task.done():
            task.cancel()
    for task in _worker_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    _worker_tasks.clear()

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
from .api.routes import health, jobs, pipelines

app.include_router(health.router, tags=["health"])
app.include_router(
    jobs.router,
    prefix="/v1",
    tags=["jobs"],
    dependencies=[Depends(verify_api_key)],
)
app.include_router(
    pipelines.router,
    prefix="/v1",
    tags=["pipelines"],
    dependencies=[Depends(verify_api_key)],
)


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
