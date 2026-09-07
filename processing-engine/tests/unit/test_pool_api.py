"""Unit tests for Pool API endpoints.

Tests use FastAPI dependency overrides with mocked connection.
No Docker or PostgreSQL required.
"""
from __future__ import annotations

import json
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENGINE_ROLE", "api")

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.pool import _compute_hash
from app.deps import get_db, verify_api_key
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline_record(pipeline_id=None):
    pid = pipeline_id or uuid.uuid4()

    class FakeRecord(dict):
        def __getitem__(self, key):
            return dict.__getitem__(self, key)
        def get(self, key, default=None):
            return dict.get(self, key, default)

    return FakeRecord(id=pid, name="Test Pipeline", version=1, is_active=True)


class FakeRecord(dict):
    """asyncpg.Record-like dict."""
    def __getitem__(self, key):
        return dict.__getitem__(self, key)
    def get(self, key, default=None):
        return dict.get(self, key, default)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    return conn


@pytest.fixture
def api_headers():
    return {"X-API-Key": "test-key"}


@pytest.fixture
async def ac(mock_conn):
    """Async test client with dependency overrides."""
    async def override_get_db():
        yield mock_conn

    async def override_verify_api_key():
        return "test-key"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_api_key] = override_verify_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /v1/pool/ingest
# ---------------------------------------------------------------------------

class TestPoolIngest:

    @pytest.mark.asyncio
    async def test_ingest_valid_items(self, ac, mock_conn, api_headers):
        pipeline_id = uuid.uuid4()
        pool_ids = [uuid.uuid4() for _ in range(3)]

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        call_count = 0

        async def mock_fetchval(*args):
            nonlocal call_count
            call_count += 1
            # Odd calls = url_hash check (None=not exists), Even calls = INSERT returning id
            if call_count % 2 == 1:
                return None
            else:
                return pool_ids[(call_count // 2) - 1]

        mock_conn.fetchval = mock_fetchval

        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(pipeline_id),
            "source_id": "test-scraper",
            "items": [
                {"source_url": f"https://example.com/page{i}", "content": f"Content {i}"}
                for i in range(3)
            ],
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["accepted"] == 3
        assert data["rejected"] == 0
        assert len(data["pool_ids"]) == 3

    @pytest.mark.asyncio
    async def test_ingest_invalid_pipeline_404(self, ac, mock_conn, api_headers):
        mock_conn.fetchrow = AsyncMock(return_value=None)

        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(uuid.uuid4()),
            "items": [{"content": "Test"}],
        }, headers=api_headers)

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_ingest_duplicate_url_rejected(self, ac, mock_conn, api_headers):
        pipeline_id = uuid.uuid4()
        existing_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        mock_conn.fetchval = AsyncMock(return_value=existing_id)  # url_hash exists

        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(pipeline_id),
            "items": [{"source_url": "https://example.com/dup", "content": "Dup"}],
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["accepted"] == 0
        assert data["rejected"] == 1
        assert data["rejections"][0]["reason"] == "duplicate_url"
        assert data["rejections"][0]["existing_pool_id"] == str(existing_id)

    @pytest.mark.asyncio
    async def test_ingest_content_only_no_url_check(self, ac, mock_conn, api_headers):
        """Items with only content (no source_url) skip URL dedup."""
        pipeline_id = uuid.uuid4()
        pool_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        mock_conn.fetchval = AsyncMock(return_value=pool_id)  # INSERT returns id

        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(pipeline_id),
            "items": [{"content": "No URL, just content"}],
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["accepted"] == 1

    @pytest.mark.asyncio
    async def test_ingest_missing_content_and_url_422(self, ac, api_headers):
        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(uuid.uuid4()),
            "items": [{"content_type": "text/plain"}],
        }, headers=api_headers)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_over_500_items_422(self, ac, api_headers):
        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(uuid.uuid4()),
            "items": [{"content": f"Item {i}"} for i in range(501)],
        }, headers=api_headers)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_empty_items_422(self, ac, api_headers):
        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(uuid.uuid4()),
            "items": [],
        }, headers=api_headers)

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_mixed_accepted_rejected(self, ac, mock_conn, api_headers):
        """Batch with mix of new and duplicate items."""
        pipeline_id = uuid.uuid4()
        existing_id = uuid.uuid4()
        new_pool_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        call_count = 0

        async def mock_fetchval(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return existing_id  # First item: duplicate
            elif call_count == 2:
                return None  # Second item: url_hash check OK
            elif call_count == 3:
                return new_pool_id  # Second item: INSERT
            return None

        mock_conn.fetchval = mock_fetchval

        resp = await ac.post("/v1/pool/ingest", json={
            "pipeline_id": str(pipeline_id),
            "items": [
                {"source_url": "https://example.com/dup", "content": "Duplicate"},
                {"source_url": "https://example.com/new", "content": "New"},
            ],
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 1


# ---------------------------------------------------------------------------
# POST /v1/pool/ingest/single
# ---------------------------------------------------------------------------

class TestPoolIngestSingle:

    @pytest.mark.asyncio
    async def test_single_ingest_accepted(self, ac, mock_conn, api_headers):
        pipeline_id = uuid.uuid4()
        pool_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        call_count = 0

        async def mock_fetchval(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # url_hash check
            return pool_id  # INSERT

        mock_conn.fetchval = mock_fetchval

        resp = await ac.post("/v1/pool/ingest/single", json={
            "pipeline_id": str(pipeline_id),
            "source_url": "https://example.com/article",
            "content": "Article content",
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["pool_id"] == str(pool_id)

    @pytest.mark.asyncio
    async def test_single_ingest_duplicate(self, ac, mock_conn, api_headers):
        pipeline_id = uuid.uuid4()
        existing_id = uuid.uuid4()

        mock_conn.fetchrow = AsyncMock(return_value=_make_pipeline_record(pipeline_id))
        mock_conn.fetchval = AsyncMock(return_value=existing_id)

        resp = await ac.post("/v1/pool/ingest/single", json={
            "pipeline_id": str(pipeline_id),
            "source_url": "https://example.com/dup",
            "content": "Dup content",
        }, headers=api_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "duplicate"
        assert data["existing_pool_id"] == str(existing_id)

    @pytest.mark.asyncio
    async def test_single_ingest_missing_content_and_url_422(self, ac, api_headers):
        resp = await ac.post("/v1/pool/ingest/single", json={
            "pipeline_id": str(uuid.uuid4()),
        }, headers=api_headers)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/pool/status
# ---------------------------------------------------------------------------

class TestPoolStatus:

    @pytest.mark.asyncio
    async def test_pool_status_with_items(self, ac, mock_conn, api_headers):
        pipeline_id = uuid.uuid4()

        mock_conn.fetchval = AsyncMock(return_value=35)
        mock_conn.fetch = AsyncMock(return_value=[
            FakeRecord(
                pipeline_id=pipeline_id,
                pipeline_name="VotoLimpo",
                pending=35,
                oldest_pending=None,
            ),
        ])

        resp = await ac.get("/v1/pool/status", headers=api_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_total"] == 35
        assert len(data["by_pipeline"]) == 1
        assert data["by_pipeline"][0]["pipeline_name"] == "VotoLimpo"
        assert data["by_pipeline"][0]["pending"] == 35

    @pytest.mark.asyncio
    async def test_pool_status_empty(self, ac, mock_conn, api_headers):
        mock_conn.fetchval = AsyncMock(return_value=0)
        mock_conn.fetch = AsyncMock(return_value=[])

        resp = await ac.get("/v1/pool/status", headers=api_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_total"] == 0
        assert data["by_pipeline"] == []


# ---------------------------------------------------------------------------
# Hash utility
# ---------------------------------------------------------------------------

class TestComputeHash:
    def test_hash_string(self):
        result = _compute_hash("https://example.com")
        assert result is not None
        assert len(result) == 64

    def test_hash_none(self):
        assert _compute_hash(None) is None

    def test_hash_deterministic(self):
        assert _compute_hash("test") == _compute_hash("test")
