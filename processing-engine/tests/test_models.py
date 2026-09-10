"""Tests for data models."""

import pytest

from app.core.models import ProcessingJob, ProcessingItem, JobStatus, JobPriority


class TestProcessingJob:
    def test_minimal_job(self):
        job = ProcessingJob(
            pipeline_id="test-pipeline",
            items=[ProcessingItem(content="test content")],
        )
        assert job.pipeline_id == "test-pipeline"
        assert len(job.items) == 1
        assert job.priority == "normal"
        assert job.callback_url is None

    def test_full_job(self):
        job = ProcessingJob(
            pipeline_id="test-pipeline",
            items=[
                ProcessingItem(
                    content="test",
                    content_type="text/html",
                    source_url="https://example.com",
                    metadata={"key": "value"},
                ),
            ],
            priority="high",
            callback_url="https://callback.example.com",
            idempotency_key="unique-key-123",
        )
        assert job.priority == "high"
        assert job.callback_url == "https://callback.example.com"
        assert job.items[0].metadata == {"key": "value"}


class TestProcessingItem:
    def test_defaults(self):
        item = ProcessingItem(content="test")
        assert item.content_type == "text/plain"
        assert item.source_url is None


class TestEnums:
    def test_job_status_values(self):
        assert "pending" in [s.value for s in JobStatus]
        assert "completed" in [s.value for s in JobStatus]
        assert "failed" in [s.value for s in JobStatus]

    def test_job_priority_values(self):
        assert "normal" in [p.value for p in JobPriority]
        assert "critical" in [p.value for p in JobPriority]
