from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def _init_pool_with_extensions(conn: asyncpg.Connection) -> None:
    """Callback executed for each new connection in the pool.

    Ensures the pgvector extension is available on every connection.
    """
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")


async def create_pool(
    *,
    dsn: str | None = None,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> asyncpg.Pool:
    """Create and store the global asyncpg connection pool.

    Accepts EITHER a ``dsn`` string OR individual connection parameters.
    Individual parameters are preferred because they avoid URL-encoding
    issues when the password contains special characters (``$``, ``@``,
    ``:``, etc.).

    Returns:
        The newly created pool.
    """
    global _pool

    logger.info("Creating asyncpg connection pool")
    if dsn:
        _pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=10,
            init=_init_pool_with_extensions,
        )
    else:
        _pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            min_size=2,
            max_size=10,
            init=_init_pool_with_extensions,
        )
    logger.info("Connection pool created successfully")
    return _pool


def get_pool() -> asyncpg.Pool:
    """Return the global connection pool.

    Raises:
        RuntimeError: If the pool has not been initialized yet.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool has not been initialized. Call create_pool() before using get_pool()."
        )
    return _pool


async def close_pool() -> None:
    """Close the global connection pool gracefully."""
    global _pool

    if _pool is not None:
        logger.info("Closing asyncpg connection pool")
        await _pool.close()
        _pool = None
        logger.info("Connection pool closed")
