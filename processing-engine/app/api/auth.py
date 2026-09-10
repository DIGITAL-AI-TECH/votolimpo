"""API key authentication dependency.

Accepts both:
  - Authorization: Bearer <token>
  - X-Api-Key: <token>
"""

import hmac

from fastapi import Header, HTTPException, Request

from ..config import settings


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None),
) -> str:
    """Validate API key from Bearer token or X-Api-Key header (timing-safe)."""
    token: str | None = None

    # Try X-Api-Key header first
    if x_api_key:
        token = x_api_key
    else:
        # Fall back to Authorization: Bearer <token>
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]

    if not token or not hmac.compare_digest(token, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return token
