from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class DedupResult:
    is_duplicate: bool
    matched_item_id: str | None = None
    strategy: str = ""
    similarity: float | None = None


@dataclass
class LLMResponse:
    content: str  # raw response text
    parsed: dict[str, Any] | None = None  # parsed JSON if successful
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    model: str = ""
    provider: str = ""


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class Ingestor(Protocol):
    async def ingest(
        self, raw: str | bytes, content_type: str, max_chars: int = 100000
    ) -> str: ...


@runtime_checkable
class DedupStrategy(Protocol):
    async def check(
        self,
        content: str,
        url: str | None,
        pipeline_id: str,
        conn: Any,
        current_item_id: str | None = None,
    ) -> DedupResult: ...


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        user_content: str,
        system_prompt: str,
        output_schema: dict,
        config: dict,
    ) -> LLMResponse: ...

    async def embed(self, text: str) -> list[float]: ...


@runtime_checkable
class Validator(Protocol):
    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult: ...


@runtime_checkable
class Sink(Protocol):
    async def persist(
        self,
        item_id: str,
        output: dict,
        config: dict,
        conn: Any,
    ) -> None: ...
