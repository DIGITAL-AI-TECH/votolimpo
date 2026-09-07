from __future__ import annotations

import asyncio
import time

import pytest

from app.services.rate_limiter import RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_request_no_wait(self):
        limiter = RateLimiter(rpm=60)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.05  # Should be instant

    @pytest.mark.asyncio
    async def test_respects_rpm_interval(self):
        # 600 RPM = 0.1s interval
        limiter = RateLimiter(rpm=600)
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.08  # ~0.1s with tolerance

    @pytest.mark.asyncio
    async def test_context_manager(self):
        limiter = RateLimiter(rpm=6000)  # 0.01s interval
        async with limiter:
            pass  # Should not raise
        async with limiter:
            pass  # Second call should wait briefly

    @pytest.mark.asyncio
    async def test_min_rpm_is_one(self):
        limiter = RateLimiter(rpm=0)
        assert limiter.rpm == 1

    @pytest.mark.asyncio
    async def test_concurrent_requests_serialized(self):
        # 1200 RPM = 0.05s interval, 3 concurrent requests
        limiter = RateLimiter(rpm=1200)
        timestamps: list[float] = []

        async def req():
            await limiter.acquire()
            timestamps.append(time.monotonic())

        await asyncio.gather(req(), req(), req())
        # At least 2 intervals between first and last
        assert len(timestamps) == 3
        total_span = timestamps[-1] - timestamps[0]
        assert total_span >= 0.08  # 2 * 0.05s intervals


class TestRateLimiterEdgeCases:
    @pytest.mark.asyncio
    async def test_high_rpm_fast(self):
        limiter = RateLimiter(rpm=60000)  # 1ms interval
        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be very fast

    @pytest.mark.asyncio
    async def test_low_rpm_slow(self):
        limiter = RateLimiter(rpm=120)  # 0.5s interval
        await limiter.acquire()
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.4  # ~0.5s with tolerance
