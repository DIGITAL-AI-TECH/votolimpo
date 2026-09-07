"""E2E tests — full pipeline lifecycle through the HTTP API.

These tests require Docker (PostgreSQL container) and exercise
the complete flow: create pipeline → submit job → poll result.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import needs_docker


@needs_docker
class TestPipelineLifecycle:
    """Full lifecycle: CRUD pipeline + submit job + check status."""

    HEADERS = {"X-API-Key": "test-key"}
    PIPELINE_PAYLOAD = {
        "name": f"e2e-test-{uuid.uuid4().hex[:8]}",
        "description": "Pipeline criado pelo teste E2E",
        "ingestor_type": "text",
        "dedup_strategy": "hash",
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "system_prompt": "Extract the main topic from the text.",
        "output_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
        "validators": ["schema"],
        "sink_type": "postgresql",
        "sink_config": {},
        "max_concurrent": 1,
        "budget_limit_usd": 1.0,
        "budget_period": "month",
        "cache_ttl_hours": 0,
    }

    @pytest.fixture
    async def created_pipeline(self, client):
        """Create a pipeline and return its response dict."""
        resp = await client.post(
            "/pipelines",
            json=self.PIPELINE_PAYLOAD,
            headers=self.HEADERS,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_create_pipeline(self, client):
        """POST /pipelines returns 201 with all expected fields."""
        resp = await client.post(
            "/pipelines",
            json=self.PIPELINE_PAYLOAD,
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == self.PIPELINE_PAYLOAD["name"]
        assert "id" in data
        assert data["version"] == 1
        assert data["is_active"] is True

    async def test_get_pipeline(self, client, created_pipeline):
        """GET /pipelines/{id} returns the pipeline we just created."""
        pid = created_pipeline["id"]
        resp = await client.get(f"/pipelines/{pid}", headers=self.HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    async def test_list_pipelines_includes_created(self, client, created_pipeline):
        """GET /pipelines lists the pipeline we created."""
        resp = await client.get("/pipelines", headers=self.HEADERS)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert created_pipeline["id"] in ids

    async def test_update_pipeline_bumps_version(self, client, created_pipeline):
        """PUT /pipelines/{id} bumps version and updates fields."""
        pid = created_pipeline["id"]
        updated = {**self.PIPELINE_PAYLOAD, "name": f"updated-{uuid.uuid4().hex[:8]}"}
        resp = await client.put(
            f"/pipelines/{pid}",
            json=updated,
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2
        assert data["name"] == updated["name"]

    async def test_submit_job(self, client, created_pipeline):
        """POST /jobs creates a job with status 'queued'."""
        resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": created_pipeline["id"],
                "items": [{"content": "Python is great", "content_type": "text/plain"}],
            },
            headers=self.HEADERS,
        )
        assert resp.status_code == 201
        job = resp.json()
        assert job["status"] == "queued"
        assert job["items_total"] == 1
        assert job["pipeline_id"] == created_pipeline["id"]

    async def test_get_job_details(self, client, created_pipeline):
        """GET /jobs/{id} returns the job we submitted."""
        # Create job first
        create_resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": created_pipeline["id"],
                "items": [{"content": "hello"}],
            },
            headers=self.HEADERS,
        )
        job_id = create_resp.json()["id"]

        resp = await client.get(f"/jobs/{job_id}", headers=self.HEADERS)
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    async def test_list_jobs_with_filters(self, client, created_pipeline):
        """GET /jobs returns paginated list with filters."""
        # Create a job
        await client.post(
            "/jobs",
            json={
                "pipeline_id": created_pipeline["id"],
                "items": [{"content": "test"}],
            },
            headers=self.HEADERS,
        )
        resp = await client.get(
            "/jobs",
            params={"pipeline_id": created_pipeline["id"], "limit": 10},
            headers=self.HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["total"], int)

    async def test_idempotency_key_prevents_duplicate(self, client, created_pipeline):
        """POST /jobs with same idempotency_key returns 409."""
        idem_key = f"idem-{uuid.uuid4().hex[:8]}"
        payload = {
            "pipeline_id": created_pipeline["id"],
            "items": [{"content": "test"}],
            "idempotency_key": idem_key,
        }
        resp1 = await client.post("/jobs", json=payload, headers=self.HEADERS)
        assert resp1.status_code == 201

        resp2 = await client.post("/jobs", json=payload, headers=self.HEADERS)
        assert resp2.status_code == 409

    async def test_job_result_endpoint(self, client, created_pipeline):
        """GET /jobs/{id}/result returns structured result."""
        create_resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": created_pipeline["id"],
                "items": [{"content": "test"}],
            },
            headers=self.HEADERS,
        )
        job_id = create_resp.json()["id"]

        resp = await client.get(f"/jobs/{job_id}/result", headers=self.HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    async def test_job_logs_endpoint(self, client, created_pipeline):
        """GET /jobs/{id}/logs returns list (empty for fresh job)."""
        create_resp = await client.post(
            "/jobs",
            json={
                "pipeline_id": created_pipeline["id"],
                "items": [{"content": "test"}],
            },
            headers=self.HEADERS,
        )
        job_id = create_resp.json()["id"]

        resp = await client.get(f"/jobs/{job_id}/logs", headers=self.HEADERS)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@needs_docker
class TestAuthE2E:
    """Auth / security E2E tests."""

    async def test_no_api_key_returns_403(self, client):
        """All protected endpoints require X-API-Key."""
        resp = await client.get("/pipelines")
        assert resp.status_code == 403

    async def test_wrong_api_key_returns_403(self, client):
        """Invalid API key is rejected."""
        resp = await client.get("/pipelines", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 403

    async def test_health_no_auth_required(self, client):
        """GET /health works without API key."""
        resp = await client.get("/health")
        assert resp.status_code == 200


@needs_docker
class TestCostsE2E:
    """Costs and budget E2E tests."""

    HEADERS = {"X-API-Key": "test-key"}

    async def test_costs_endpoint(self, client):
        """GET /costs returns structured report."""
        resp = await client.get("/costs", headers=self.HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost_usd" in data
        assert "breakdown" in data

    async def test_stats_endpoint(self, client):
        """GET /stats returns aggregated metrics."""
        resp = await client.get("/stats", headers=self.HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_jobs" in data
        assert "success_rate" in data
