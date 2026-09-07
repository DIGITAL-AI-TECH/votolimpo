from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"
    cancelled = "cancelled"


class ItemCreate(BaseModel):
    source_url: str | None = None
    content: str | None = None
    content_type: str = "text/plain"
    metadata: dict[str, Any] | None = None


class JobCreate(BaseModel):
    pipeline_id: uuid.UUID
    idempotency_key: str | None = None
    priority: int = 0
    items: list[ItemCreate] = Field(..., min_length=1, max_length=1000)
    override_model: str | None = None
    skip_dedup: bool = False
    skip_cache: bool = False
    dry_run: bool = False
    callback_url: str | None = None
    metadata: dict[str, Any] | None = None


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pipeline_id: uuid.UUID
    pipeline_version: int
    status: JobStatus
    items_total: int
    items_completed: int
    items_failed: int
    idempotency_key: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class JobListResponse(BaseModel):
    items: list[Job]
    total: int
