"""E2E tests for batch processing features (Phase 6-9).

Tests batch job submission, multi-item processing, stats, and logging.
Requires Docker (PostgreSQL container).
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import needs_docker


@needs_docker
class TestBatchJobSubmission:
    """Test submitting jobs with multiple items."""

    HEADERS = {"X-API-Key": "test-key"}

    @pytest.fixture
    async def pipeline(self, client):
        resp = await client.post(
            "/pipelines",
            json={
                "name": f"batch-test-{uuid.uuid4().hex[:8]}",
                "description": "Pipeline for batch E2E tests",
                "ingestor_type": "text",
                "dedup_strategy": "hash",
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "system_prompt": "Extract topic.",
                "output_schema": {
                    "type": "object",
                    "properties": {"topic": {"type": "string"}},
                    "required": ["topic"],
                },
                "validators": ["schema"],
                "sink_type": "postgresql",
                "max_concurrent": 3,
                "rate_limit_rpm": 60,
                "cache_ttl_hours": 720,
                "budget_limit_usd": 10.0,
                "budget_period": "month",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_submit_batch_job_multiple_items(self, client, pipeline):
        """POST /jobs accepts multiple items in a single job."""
        items = [
            {"content": f"Content number {i}", "content_type": "text/plain"}
            for i in range(5)
        ]
        resp = await client.post(
            "/jobs",
            json={"pipeline_id": pipeline["id"], "items": items},
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        job = resp.json()
        assert job["items_total"] == 5
        assert job["status"] == "queued"

    async def test_batch_job_result_has_all_items(self, client, pipeline):
        """GET /jobs/{id}/result returns all items from batch submission."""
        items = [
            {"content": f"Batch item {i}"}
            for i in range(3)
        ]
        create_resp = await client.post(
            "/jobs",
            json={"pipeline_id": pipeline["id"], "items": items},
            headers=self.HEADERS,
        )
        job_id = create_resp.json()["id"]

        resp = await client.get(f"/jobs/{job_id}/result", headers=self.HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3

    async def test_batch_with_skip_dedup(self, client, pipeline):
        """Jobs with skip_dedup=true are accepted."""
        resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": pipeline["id"],
                "items": [{"content": "skip dedup test"}],
                "skip_dedup": True,
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "queued"

    async def test_batch_with_skip_cache(self, client, pipeline):
        """Jobs with skip_cache=true are accepted."""
        resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": pipeline["id"],
                "items": [{"content": "skip cache test"}],
                "skip_cache": True,
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201

    async def test_batch_with_callback_url(self, client, pipeline):
        """Jobs with callback_url are accepted."""
        resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": pipeline["id"],
                "items": [{"content": "callback test"}],
                "callback_url": "https://example.com/webhook",
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201

    async def test_batch_with_dry_run(self, client, pipeline):
        """Jobs with dry_run=true are accepted."""
        resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": pipeline["id"],
                "items": [{"content": "dry run test"}],
                "dry_run": True,
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201


@needs_docker
class TestStatsAndCostsE2E:
    """Test stats aggregation after batch processing."""

    HEADERS = {"X-API-Key": "test-key"}

    async def test_stats_period_day(self, client):
        resp = await client.get("/stats", params={"period": "day"}, headers=self.HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "day"
        assert "cache_hit_rate" in data
        assert "dedup_rate" in data

    async def test_stats_period_week(self, client):
        resp = await client.get("/stats", params={"period": "week"}, headers=self.HEADERS)
        assert resp.status_code == 200
        assert resp.json()["period"] == "week"

    async def test_stats_period_month(self, client):
        resp = await client.get("/stats", params={"period": "month"}, headers=self.HEADERS)
        assert resp.status_code == 200
        assert resp.json()["period"] == "month"

    async def test_stats_period_all(self, client):
        resp = await client.get("/stats", params={"period": "all"}, headers=self.HEADERS)
        assert resp.status_code == 200
        assert resp.json()["period"] == "all"

    async def test_stats_filter_by_pipeline(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            "/stats", params={"pipeline_id": fake_id}, headers=self.HEADERS
        )
        assert resp.status_code == 200

    async def test_costs_group_by_pipeline(self, client):
        resp = await client.get(
            "/costs", params={"group_by": "pipeline"}, headers=self.HEADERS
        )
        assert resp.status_code == 200
        assert "breakdown" in resp.json()

    async def test_costs_group_by_model(self, client):
        resp = await client.get(
            "/costs", params={"group_by": "model"}, headers=self.HEADERS
        )
        assert resp.status_code == 200

    async def test_costs_group_by_day(self, client):
        resp = await client.get(
            "/costs", params={"group_by": "day"}, headers=self.HEADERS
        )
        assert resp.status_code == 200

    async def test_budget_status_not_found(self, client):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/costs/budget/{fake_id}", headers=self.HEADERS
        )
        # Budget endpoint should handle missing pipeline gracefully
        assert resp.status_code in (200, 404)


@needs_docker
class TestLogsE2E:
    """Test processing logs after job submission."""

    HEADERS = {"X-API-Key": "test-key"}

    async def test_logs_filter_by_step(self, client):
        """GET /jobs/{id}/logs?step=ingest filters by step."""
        # Create pipeline + job
        pipeline_resp = await client.post(
            "/pipelines",
            json={
                "name": f"logs-test-{uuid.uuid4().hex[:8]}",
                "system_prompt": "test",
                "output_schema": {"type": "object"},
            },
            headers=self.HEADERS,
        )
        pipeline_id = pipeline_resp.json()["id"]

        job_resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": pipeline_id,
                "items": [{"content": "test logs"}],
            },
            headers=self.HEADERS,
        )
        job_id = job_resp.json()["id"]

        resp = await client.get(
            f"/jobs/{job_id}/logs",
            params={"step": "ingest"},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert isinstance(logs, list)
        # All returned logs should be for the requested step
        for log in logs:
            assert log["step"] == "ingest"
