from __future__ import annotations

import asyncio
import socket

import pytest


def _pg_reachable() -> bool:
    """Check if PostgreSQL is reachable on localhost:5432."""
    try:
        s = socket.create_connection(("127.0.0.1", 5432), timeout=1)
        s.close()
        return True
    except OSError:
        return False


_skip_no_pg = pytest.mark.skipif(
    not _pg_reachable(),
    reason="PostgreSQL not reachable on localhost:5432",
)


@_skip_no_pg
@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint returns 200 with db connected."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db_connected"] is True
    assert "version" in data


@_skip_no_pg
@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    """Health endpoint does NOT require API key."""
    response = await client.get("/health")
    assert response.status_code == 200
