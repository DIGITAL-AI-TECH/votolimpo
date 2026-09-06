from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class LogStep(str, Enum):
    ingest = "ingest"
    dedup = "dedup"
    process = "process"
    validate = "validate"
    persist = "persist"


class ProcessingLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    step: LogStep
    status: str
    duration_ms: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
