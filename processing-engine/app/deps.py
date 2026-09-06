from __future__ import annotations

from typing import AsyncIterator

import asyncpg
from fastapi import Header, HTTPException, status

from app.config import settings
from app.db import get_pool


async def get_db() -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency that yields a database connection from the pool.

    The connection is acquired at the start of the request and released
    automatically when the request completes (or raises an exception).

    Yields:
        An active asyncpg.Connection bound to the current request.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """FastAPI dependency that validates the X-Api-Key request header.

    Args:
        x_api_key: Value of the ``X-Api-Key`` HTTP header.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: 401 Unauthorized if the key does not match the
            configured :attr:`settings.API_KEY`.
    """
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
