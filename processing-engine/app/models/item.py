"""Pydantic response models for Item/Result API endpoints."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel


class ItemStatus(str, Enum):
    pending = "pending"
    ingesting = "ingesting"
    deduplicating = "deduplicating"
    processing = "processing"
    validating = "validating"
    persisting = "persisting"
    completed = "completed"
    failed = "failed"
    duplicate = "duplicate"
    similar = "similar"


class TokenUsage(BaseModel):
    """Token usage details for a single item."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class ItemResult(BaseModel):
    """Item result response model."""

    id: uuid.UUID
    status: str = "pending"
    source_url: str | None = None
    content_type: str | None = None
    output: dict | None = None
    dedup_result: str | None = None
    cached: bool = False
    usage: TokenUsage | None = None
    duration_ms: int | None = None
    error: str | None = None
