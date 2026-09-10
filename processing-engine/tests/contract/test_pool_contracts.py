"""Contract tests for Pool API response shapes.

Validates Pydantic model serialization matches the contract
a frontend/collector would depend on.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENGINE_ROLE", "api")

import pytest

from app.models.pool import (
    PoolIngestItem,
    PoolIngestResponse,
    PoolPipelineStatus,
    PoolRejection,
    PoolSingleIngestResponse,
    PoolStatusResponse,
)


class TestPoolIngestResponseShape:
    """Contract: PoolIngestResponse must have exact fields and types."""

    def test_accepted_response_shape(self):
        pool_id = uuid.uuid4()
        resp = PoolIngestResponse(
            accepted=3,
            rejected=1,
            pool_ids=[pool_id],
            rejections=[
                PoolRejection(
                    index=2, reason="duplicate_url", existing_pool_id=uuid.uuid4()
                )
            ],
        )
        data = resp.model_dump(mode="json")

        assert isinstance(data["accepted"], int)
        assert isinstance(data["rejected"], int)
        assert isinstance(data["pool_ids"], list)
        assert isinstance(data["pool_ids"][0], str)
        assert isinstance(data["rejections"], list)
        assert isinstance(data["rejections"][0]["index"], int)
        assert isinstance(data["rejections"][0]["reason"], str)

    def test_empty_response_shape(self):
        resp = PoolIngestResponse(accepted=0, rejected=0, pool_ids=[], rejections=[])
        data = resp.model_dump(mode="json")

        assert data["accepted"] == 0
        assert data["rejected"] == 0
        assert data["pool_ids"] == []
        assert data["rejections"] == []

    def test_required_fields_present(self):
        resp = PoolIngestResponse(
            accepted=1, rejected=0, pool_ids=[uuid.uuid4()], rejections=[]
        )
        data = resp.model_dump(mode="json")
        required = {"accepted", "rejected", "pool_ids", "rejections"}
        assert required.issubset(data.keys())


class TestPoolSingleIngestResponseShape:
    """Contract: PoolSingleIngestResponse must have exact fields."""

    def test_accepted_shape(self):
        resp = PoolSingleIngestResponse(pool_id=uuid.uuid4(), status="accepted")
        data = resp.model_dump(mode="json")

        assert isinstance(data["pool_id"], str)
        assert data["status"] == "accepted"
        assert "existing_pool_id" in data

    def test_duplicate_shape(self):
        resp = PoolSingleIngestResponse(
            pool_id=None,
            status="duplicate",
            existing_pool_id=uuid.uuid4(),
        )
        data = resp.model_dump(mode="json")

        assert data["pool_id"] is None
        assert data["status"] == "duplicate"
        assert isinstance(data["existing_pool_id"], str)


class TestPoolStatusResponseShape:
    """Contract: PoolStatusResponse must have exact fields."""

    def test_with_pipelines(self):
        resp = PoolStatusResponse(
            pending_total=47,
            by_pipeline=[
                PoolPipelineStatus(
                    pipeline_id=uuid.uuid4(),
                    pipeline_name="VotoLimpo",
                    pending=35,
                    oldest_pending=datetime(2026, 9, 7, 13, 45, tzinfo=UTC),
                ),
            ],
        )
        data = resp.model_dump(mode="json")

        assert isinstance(data["pending_total"], int)
        assert isinstance(data["by_pipeline"], list)
        bp = data["by_pipeline"][0]
        assert isinstance(bp["pipeline_id"], str)
        assert isinstance(bp["pipeline_name"], str)
        assert isinstance(bp["pending"], int)
        assert isinstance(bp["oldest_pending"], str)

    def test_empty_pool(self):
        resp = PoolStatusResponse(pending_total=0, by_pipeline=[])
        data = resp.model_dump(mode="json")

        assert data["pending_total"] == 0
        assert data["by_pipeline"] == []


class TestPoolRejectionShape:
    """Contract: PoolRejection must have exact fields."""

    def test_rejection_with_existing_id(self):
        r = PoolRejection(
            index=3, reason="duplicate_url", existing_pool_id=uuid.uuid4()
        )
        data = r.model_dump(mode="json")

        assert isinstance(data["index"], int)
        assert isinstance(data["reason"], str)
        assert isinstance(data["existing_pool_id"], str)

    def test_rejection_without_existing_id(self):
        r = PoolRejection(index=0, reason="validation_error")
        data = r.model_dump(mode="json")

        assert data["existing_pool_id"] is None


class TestPoolIngestItemValidation:
    """Contract: PoolIngestItem validation rules."""

    def test_valid_with_url_and_content(self):
        item = PoolIngestItem(source_url="https://x.com", content="Test")
        assert item.source_url == "https://x.com"

    def test_valid_with_url_only(self):
        item = PoolIngestItem(source_url="https://x.com")
        assert item.content is None

    def test_valid_with_content_only(self):
        item = PoolIngestItem(content="Test content")
        assert item.source_url is None

    def test_invalid_without_both(self):
        with pytest.raises(ValueError, match="content.*source_url"):
            PoolIngestItem()
