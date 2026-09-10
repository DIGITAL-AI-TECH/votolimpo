from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ItemStatus(StrEnum):
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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class ItemResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ItemStatus
    source_url: str | None = None
    content_type: str | None = None
    output: dict[str, Any] | None = None
    dedup_result: str | None = None  # "new", "duplicate", "similar"
    cached: bool = False
    usage: TokenUsage | None = None
    duration_ms: int | None = None
    error: str | None = None
