"""LLM provider plugins — send content to LLMs and get structured output."""

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from openai import AsyncOpenAI

from ...config import settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol for LLM provider plugins."""

    async def process(
        self,
        content: str,
        system_prompt: str,
        output_schema: dict | None,
        config: dict,
    ) -> dict[str, Any]:
        """Process content through LLM. Returns parsed output + usage info."""
        ...


class OpenAIProvider:
    """OpenAI GPT provider with structured output support."""

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def process(
        self,
        content: str,
        system_prompt: str,
        output_schema: dict | None,
        config: dict,
    ) -> dict[str, Any]:
        model = config.get("model", "gpt-4.1-mini")
        temperature = config.get("temperature", 0.1)
        max_tokens = config.get("max_tokens", 4096)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if output_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_output",
                    "strict": True,
                    "schema": output_schema,
                },
            }

        response = await self.client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content
        output = json.loads(raw)

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
            "model": model,
        }

        # Estimate cost (GPT-4.1-mini pricing)
        prompt_cost = (usage["prompt_tokens"] / 1_000_000) * 0.40
        completion_cost = (usage["completion_tokens"] / 1_000_000) * 1.60
        cost_usd = prompt_cost + completion_cost

        return {
            "output": output,
            "usage": usage,
            "cost_usd": round(cost_usd, 6),
        }


LLM_PROVIDERS: dict[str, type] = {
    "openai": OpenAIProvider,
}


def get_llm_provider(provider: str) -> LLMProvider:
    """Get an LLM provider by name."""
    cls = LLM_PROVIDERS.get(provider, OpenAIProvider)
    return cls()


def load_system_prompt(file_path: str) -> str:
    """Load system prompt from file, resolving relative to prompts_dir."""
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(settings.prompts_dir) / p.name
    return p.read_text()


def load_output_schema(file_path: str) -> dict:
    """Load JSON schema from file, resolving relative to schemas_dir."""
    p = Path(file_path)
    if not p.is_absolute():
        p = Path(settings.schemas_dir) / p.name
    return json.loads(p.read_text())
