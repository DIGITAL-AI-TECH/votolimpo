from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

try:
    from testcontainers.postgres import PostgresContainer

    _HAS_DOCKER = True
except ImportError:
    _HAS_DOCKER = False


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    if not _HAS_DOCKER:
        return False
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


_DOCKER_OK = _docker_available()

needs_docker = pytest.mark.skipif(not _DOCKER_OK, reason="Docker not available")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL 16 container with pgvector for the test session."""
    if not _DOCKER_OK:
        pytest.skip("Docker not available")
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="test",
        password="test",
        dbname="test_processing_engine",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    """Get the database URL from the running container."""
    return postgres_container.get_connection_url().replace("psycopg2", "postgresql")


@pytest.fixture(scope="session")
def run_migrations(database_url):
    """Run Alembic migrations against the test database."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="/workspace/processing-engine",
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stderr}")


@pytest.fixture(scope="session")
async def db_pool(database_url) -> AsyncGenerator[asyncpg.Pool, None]:
    """Create an asyncpg pool connected to the test database."""
    pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=2,
        max_size=5,
    )
    yield pool
    await pool.close()


@pytest.fixture
async def db_conn(db_pool) -> AsyncGenerator[asyncpg.Connection, None]:
    """Get a connection from the test pool. Rolls back after each test."""
    async with db_pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        yield conn
        await tr.rollback()


@pytest.fixture
async def client(database_url, db_pool) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with the real database."""
    os.environ["DATABASE_URL"] = database_url
    os.environ["API_KEY"] = "test-key"
    os.environ["ENGINE_ROLE"] = "api"  # Don't start worker in tests by default

    # Reset the pool to use test database
    from app import db as db_module
    db_module._pool = db_pool

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    db_module._pool = None
