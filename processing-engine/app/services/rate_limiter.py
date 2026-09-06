from __future__ import annotations

import asyncio
import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter for RPM (requests per minute) throttling.

    Usage:
        limiter = RateLimiter(rpm=60)
        async with limiter:
            await do_llm_call()
    """

    def __init__(self, rpm: int) -> None:
        self.rpm = max(rpm, 1)
        self.interval = 60.0 / self.rpm  # seconds between requests
        self._lock = asyncio.Lock()
        self._last_request: float = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.interval:
                wait = self.interval - elapsed
                logger.debug("Rate limiter: waiting %.2fs (rpm=%d)", wait, self.rpm)
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def __aenter__(self) -> RateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *exc) -> None:
        pass
