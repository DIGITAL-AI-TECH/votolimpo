from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint returns 200 with db connected."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db_connected"] is True
    assert "version" in data


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health endpoint does NOT require API key."""
    response = await client.get("/health")
    assert response.status_code == 200
