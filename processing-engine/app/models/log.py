"""Pydantic response models for Processing Log API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class LogStep(str, Enum):
    ingest = "ingest"
    dedup = "dedup"
    cache = "cache"
    process = "process"
    validate = "validate"
    persist = "persist"


class ProcessingLog(BaseModel):
    """Processing log entry response model."""

    id: uuid.UUID
    item_id: uuid.UUID
    step: str
    status: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int | None = None
    error_message: str | None = None
    metadata: dict | None = None
