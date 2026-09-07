from __future__ import annotations

import contextlib
import json
import time
from typing import Any

from openai import AsyncOpenAI

from app.plugins.protocols import LLMResponse


class OpenAIProvider:
    """LLM provider backed by OpenAI chat completions and embeddings APIs.

    Config dict (passed to complete()) supports:
        model       : str  — default "gpt-4.1-mini"
        temperature : float — default 0.0
        seed        : int  — default 42  (for determinism)
        max_tokens  : int  — default 4096
        api_key     : str  — overrides constructor key

    Embedding model is fixed to text-embedding-3-small (1536 dimensions).
    """

    _EMBED_MODEL = "text-embedding-3-small"
    _DEFAULT_MODEL = "gpt-4.1-mini"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    def _client(self, config: dict[str, Any]) -> AsyncOpenAI:
        key = config.get("api_key") or self._api_key
        if not key:
            # Fall back to OPENAI_API_KEY env var (AsyncOpenAI picks it up automatically)
            return AsyncOpenAI()
        return AsyncOpenAI(api_key=key)

    async def complete(
        self,
        user_content: str,
        system_prompt: str,
        output_schema: dict,
        config: dict,
    ) -> LLMResponse:
        client = self._client(config)
        model = config.get("model", self._DEFAULT_MODEL)
        temperature = config.get("temperature", 0.0)
        seed = config.get("seed", 42)
        max_tokens = config.get("max_tokens", 4096)

        # Build response_format for structured output
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": "output",
                "strict": True,
                "schema": output_schema,
            },
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        t0 = time.monotonic()
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,  # type: ignore[arg-type]
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        raw_content = response.choices[0].message.content or ""

        # Attempt to parse JSON
        parsed: dict[str, Any] | None = None
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(raw_content)

        usage = response.usage
        return LLMResponse(
            content=raw_content,
            parsed=parsed,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            latency_ms=latency_ms,
            model=model,
            provider="openai",
        )

    async def embed(self, text: str) -> list[float]:
        client = self._client({})
        response = await client.embeddings.create(
            model=self._EMBED_MODEL,
            input=text,
        )
        return response.data[0].embedding
