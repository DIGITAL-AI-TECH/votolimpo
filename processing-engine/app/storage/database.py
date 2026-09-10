"""Database connection pool using asyncpg directly."""

import logging

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

# Connection pool (initialized on startup)
_pool: asyncpg.Pool | None = None


def _get_dsn() -> str:
    """Convert SQLAlchemy-style URL to asyncpg DSN."""
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_get_dsn(),
            min_size=2,
            max_size=10,
        )
        logger.info("Database pool created")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def init_engine_schema(pool: asyncpg.Pool | None = None):
    """Ensure the processing_engine schema exists.

    Only creates the schema itself — tables are managed by Alembic migrations.
    If migrations haven't run yet, creates minimal tables as fallback.
    """
    if pool is None:
        pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS processing_engine")

        # Check if tables already exist (created by Alembic)
        row = await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'processing_engine' AND table_name = 'jobs'
        """)
        if row > 0:
            logger.info("Engine schema already initialized (tables exist)")
            return

        # Fallback: create tables if Alembic hasn't run
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_engine.pipelines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0',
                config JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS processing_engine.jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pipeline_id UUID NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'normal',
                total_items INT NOT NULL DEFAULT 0,
                completed_items INT NOT NULL DEFAULT 0,
                failed_items INT NOT NULL DEFAULT 0,
                callback_url TEXT,
                idempotency_key TEXT,
                total_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
                total_duration_ms INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_priority
                ON processing_engine.jobs (status, priority DESC, created_at ASC);

            CREATE TABLE IF NOT EXISTS processing_engine.job_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_id UUID NOT NULL REFERENCES processing_engine.jobs(id),
                content TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'text/plain',
                source_url TEXT,
                metadata JSONB NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                output JSONB,
                validation_errors JSONB NOT NULL DEFAULT '[]',
                dedup_result TEXT,
                usage JSONB,
                cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
                duration_ms INT NOT NULL DEFAULT 0,
                error TEXT,
                cached BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_job_items_job_id
                ON processing_engine.job_items (job_id);

            CREATE TABLE IF NOT EXISTS processing_engine.processing_logs (
                id BIGSERIAL PRIMARY KEY,
                job_id UUID NOT NULL,
                item_id UUID,
                step TEXT NOT NULL,
                status TEXT NOT NULL,
                model_used TEXT,
                prompt_tokens INT,
                completion_tokens INT,
                cost_usd NUMERIC(10,6),
                duration_ms INT NOT NULL DEFAULT 0,
                error_message TEXT,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS processing_engine.cache (
                content_hash TEXT PRIMARY KEY,
                pipeline_id UUID NOT NULL,
                output JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON processing_engine.cache (expires_at);
        """)
    logger.info("Engine schema initialized (fallback DDL)")
