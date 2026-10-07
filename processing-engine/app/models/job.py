"""Pydantic response models for Job API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"
    cancelled = "cancelled"


class Job(BaseModel):
    """Job response model — serialized shape returned by the API."""

    id: uuid.UUID
    pipeline_id: uuid.UUID
    pipeline_version: int = 1
    status: str = "queued"
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    idempotency_key: str | None = None
    error_message: str | None = None
    metadata: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobListResponse(BaseModel):
    """Paginated job list response."""

    items: list[Job]
    total: int
