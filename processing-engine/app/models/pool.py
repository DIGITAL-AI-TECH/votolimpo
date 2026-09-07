from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PoolIngestItem(BaseModel):
    source_url: str | None = None
    content: str | None = None
    content_type: str = "text/plain"
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def check_content_or_url(self) -> PoolIngestItem:
        if not self.source_url and not self.content:
            raise ValueError("At least 'content' or 'source_url' is required")
        return self


class PoolIngestRequest(BaseModel):
    pipeline_id: uuid.UUID
    source_id: str | None = None
    batch_ref: str | None = None
    priority: int = 0
    items: list[PoolIngestItem] = Field(..., min_length=1, max_length=500)


class PoolRejection(BaseModel):
    index: int
    reason: str
    existing_pool_id: uuid.UUID | None = None


class PoolIngestResponse(BaseModel):
    accepted: int
    rejected: int
    pool_ids: list[uuid.UUID]
    rejections: list[PoolRejection]


class PoolSingleIngestRequest(BaseModel):
    pipeline_id: uuid.UUID
    source_id: str | None = None
    source_url: str | None = None
    content: str | None = None
    content_type: str = "text/plain"
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def check_content_or_url(self) -> PoolSingleIngestRequest:
        if not self.source_url and not self.content:
            raise ValueError("At least 'content' or 'source_url' is required")
        return self


class PoolSingleIngestResponse(BaseModel):
    pool_id: uuid.UUID | None = None
    status: Literal["accepted", "duplicate"]
    existing_pool_id: uuid.UUID | None = None


class PoolPipelineStatus(BaseModel):
    pipeline_id: uuid.UUID
    pipeline_name: str
    pending: int
    oldest_pending: datetime | None = None


class PoolStatusResponse(BaseModel):
    pending_total: int
    by_pipeline: list[PoolPipelineStatus]
