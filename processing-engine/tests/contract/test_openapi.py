"""Contract tests — validate that the FastAPI app exposes the expected endpoints.

These tests do NOT require Docker or a real database. They validate
only the OpenAPI schema structure and route registration.
"""

from __future__ import annotations

import os

# Set env vars BEFORE any app import (Settings is instantiated at module level)
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENGINE_ROLE", "api")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def paths(client):
    return client.get("/openapi.json").json()["paths"]


class TestOpenAPIContract:
    """Verify the OpenAPI schema contains all expected routes."""

    def test_openapi_schema_available(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "Processing Engine"

    def test_health_endpoint_exists(self, paths):
        assert "/health" in paths

    def test_pipelines_endpoints_exist(self, paths):
        assert "/v1/pipelines" in paths
        assert "/v1/pipelines/{pipeline_id}" in paths

    def test_jobs_endpoints_exist(self, paths):
        assert "/v1/jobs" in paths
        assert "/v1/jobs/{job_id}" in paths

    def test_costs_endpoint_exists(self, paths):
        assert "/v1/costs" in paths

    def test_pricing_endpoint_exists(self, paths):
        assert "/v1/pricing" in paths

    def test_stats_endpoint_exists(self, paths):
        assert "/v1/stats" in paths

    def test_health_no_auth(self, client):
        """Health endpoint should NOT require auth — returns 200 or degraded, never 403."""
        resp = client.get("/health")
        assert resp.status_code != 403
