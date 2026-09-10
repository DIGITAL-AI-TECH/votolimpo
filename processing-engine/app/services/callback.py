from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CallbackService:
    """Sends POST callback to configured URL after job completion."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        api_key: str | None = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.api_key = api_key

    async def send(self, url: str, payload: dict[str, Any]) -> bool:
        """Send POST with job result. Returns True on success.

        Retries up to max_retries with exponential backoff.
        Never raises — failures are logged.
        """
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code < 400:
                        logger.info(
                            "Callback sent to %s (status=%d)", url, resp.status_code
                        )
                        return True
                    logger.warning(
                        "Callback to %s returned %d (attempt %d)",
                        url,
                        resp.status_code,
                        attempt + 1,
                    )
            except Exception as e:
                logger.warning(
                    "Callback to %s failed (attempt %d): %s", url, attempt + 1, e
                )

            if attempt < self.max_retries:
                await asyncio.sleep(self.backoff_base**attempt)

        logger.error(
            "Callback to %s failed after %d attempts", url, self.max_retries + 1
        )
        return False
