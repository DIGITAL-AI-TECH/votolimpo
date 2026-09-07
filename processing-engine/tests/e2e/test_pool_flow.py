"""E2E tests for Pool flow: ingest → pool → auto-batcher → job.

Requires Docker (testcontainers) for real PostgreSQL.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import needs_docker


@needs_docker
@pytest.mark.asyncio
class TestPoolFlow:
    """E2E: Full pool flow with real PostgreSQL."""

    async def test_pool_ingest_creates_pending_items(self, client, db_conn):
        """POST /v1/pool/ingest creates items with status=pending."""
        # First create a pipeline
        pipeline_resp = await client.post(
            "/v1/pipelines",
            json={
                "name": "E2E Pool Test Pipeline",
                "ingestor_type": "text",
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "system_prompt": "Analyze this",
                "output_schema": {"type": "object"},
                "sink_type": "postgresql",
                "sink_config": {},
            },
            headers={"X-API-Key": "test-key"},
        )
        assert pipeline_resp.status_code == 201
        pipeline_id = pipeline_resp.json()["id"]

        # Ingest items
        resp = await client.post(
            "/v1/pool/ingest",
            json={
                "pipeline_id": pipeline_id,
                "source_id": "e2e-scraper",
                "batch_ref": "test-batch-001",
                "items": [
                    {"source_url": "https://e2e-test.com/page1", "content": "Content 1"},
                    {"source_url": "https://e2e-test.com/page2", "content": "Content 2"},
                    {"content": "Content without URL"},
                ],
            },
            headers={"X-API-Key": "test-key"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["accepted"] == 3
        assert data["rejected"] == 0
        assert len(data["pool_ids"]) == 3

        # Verify items are in the database with pending status
        count = await db_conn.fetchval(
            "SELECT COUNT(*) FROM processing_engine.pool WHERE status = 'pending'"
        )
        assert count >= 3

    async def test_pool_duplicate_rejected(self, client, db_conn):
        """Duplicate source_url for same pipeline is rejected."""
        pipeline_resp = await client.post(
            "/v1/pipelines",
            json={
                "name": "E2E Dedup Pipeline",
                "ingestor_type": "text",
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "system_prompt": "Test",
                "output_schema": {"type": "object"},
                "sink_type": "postgresql",
                "sink_config": {},
            },
            headers={"X-API-Key": "test-key"},
        )
        pipeline_id = pipeline_resp.json()["id"]

        # First ingest
        resp1 = await client.post(
            "/v1/pool/ingest",
            json={
                "pipeline_id": pipeline_id,
                "items": [{"source_url": "https://dedup-test.com/page1", "content": "First"}],
            },
            headers={"X-API-Key": "test-key"},
        )
        assert resp1.json()["accepted"] == 1

        # Second ingest with same URL
        resp2 = await client.post(
            "/v1/pool/ingest",
            json={
                "pipeline_id": pipeline_id,
                "items": [{"source_url": "https://dedup-test.com/page1", "content": "Duplicate"}],
            },
            headers={"X-API-Key": "test-key"},
        )

        data = resp2.json()
        assert data["accepted"] == 0
        assert data["rejected"] == 1
        assert data["rejections"][0]["reason"] == "duplicate_url"

    async def test_pool_status_reflects_pending(self, client, db_conn):
        """GET /v1/pool/status shows correct pending counts."""
        resp = await client.get("/v1/pool/status", headers={"X-API-Key": "test-key"})

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["pending_total"], int)
        assert isinstance(data["by_pipeline"], list)

    async def test_pool_single_ingest(self, client, db_conn):
        """POST /v1/pool/ingest/single works for webhooks."""
        pipeline_resp = await client.post(
            "/v1/pipelines",
            json={
                "name": "E2E Single Pipeline",
                "ingestor_type": "text",
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "system_prompt": "Test",
                "output_schema": {"type": "object"},
                "sink_type": "postgresql",
                "sink_config": {},
            },
            headers={"X-API-Key": "test-key"},
        )
        pipeline_id = pipeline_resp.json()["id"]

        resp = await client.post(
            "/v1/pool/ingest/single",
            json={
                "pipeline_id": pipeline_id,
                "source_id": "n8n-webhook",
                "source_url": "https://single-test.com/article",
                "content": "Single article content",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "accepted"
        assert data["pool_id"] is not None

    async def test_pool_ingest_nonexistent_pipeline_404(self, client):
        """Ingest to nonexistent pipeline returns 404."""
        resp = await client.post(
            "/v1/pool/ingest",
            json={
                "pipeline_id": str(uuid.uuid4()),
                "items": [{"content": "Test"}],
            },
            headers={"X-API-Key": "test-key"},
        )

        assert resp.status_code == 404
