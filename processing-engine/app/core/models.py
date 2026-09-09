"""Pydantic models for the Processing Engine."""

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class JobPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class ProcessingItem(BaseModel):
    """A single item to process."""
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    content_type: str = "text/plain"
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessingJob(BaseModel):
    """A batch job submitted for processing."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str
    items: list[ProcessingItem] = Field(min_length=1)
    priority: JobPriority = JobPriority.normal
    callback_url: str | None = None
    idempotency_key: str | None = None


class ItemResult(BaseModel):
    """Result of processing a single item."""
    item_id: str
    status: JobStatus
    output: dict[str, Any] | None = None
    validation_errors: list[str] = Field(default_factory=list)
    dedup_result: str | None = None  # "new" | "duplicate" | "similar"
    usage: dict[str, Any] | None = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    cached: bool = False


class JobResult(BaseModel):
    """Aggregate result of a processing job."""
    job_id: str
    status: JobStatus
    pipeline_id: str
    items: list[ItemResult] = Field(default_factory=list)
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
