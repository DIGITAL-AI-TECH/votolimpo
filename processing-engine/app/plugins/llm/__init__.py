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
        else:
            # Force JSON output even without explicit schema to prevent plain text.
            # OpenAI requires the word "json" in messages when using json_object mode.
            kwargs["response_format"] = {"type": "json_object"}
            if "json" not in system_prompt.lower():
                kwargs["messages"][0]["content"] += "\n\nRespond with valid JSON."

        response = await self.client.chat.completions.create(**kwargs)
        raw = response.choices[0].message.content

        # W4 fix: explicit JSONDecodeError handling
        try:
            output = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}. Raw: {raw[:200]}") from e

        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens
            if response.usage
            else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
            "model": model,
        }

        # W3 fix: pricing map per model ($/1M tokens)
        cost_usd = _estimate_cost(
            model, usage["prompt_tokens"], usage["completion_tokens"]
        )

        return {
            "output": output,
            "usage": usage,
            "cost_usd": round(cost_usd, 6),
        }


# W3 fix: pricing per model ($/1M tokens: [input, output])
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost based on model pricing map."""
    input_rate, output_rate = MODEL_PRICING.get(model, (0.40, 1.60))
    prompt_cost = (prompt_tokens / 1_000_000) * input_rate
    completion_cost = (completion_tokens / 1_000_000) * output_rate
    return round(prompt_cost + completion_cost, 6)


LLM_PROVIDERS: dict[str, type] = {
    "openai": OpenAIProvider,
}


def get_llm_provider(provider: str) -> LLMProvider:
    """Get an LLM provider by name."""
    cls = LLM_PROVIDERS.get(provider, OpenAIProvider)
    return cls()


def _safe_resolve(file_path: str, base_dir: str) -> Path:
    """Resolve file path safely within base_dir (prevent path traversal)."""
    base = Path(base_dir).resolve()
    p = (base / Path(file_path).name).resolve()
    if not str(p).startswith(str(base)):
        raise ValueError(f"Path traversal blocked: {file_path}")
    return p


def load_system_prompt(file_path: str) -> str:
    """Load system prompt from file, resolving relative to prompts_dir."""
    p = _safe_resolve(file_path, settings.prompts_dir)
    return p.read_text()


def load_output_schema(file_path: str) -> dict:
    """Load JSON schema from file, resolving relative to schemas_dir."""
    p = _safe_resolve(file_path, settings.schemas_dir)
    return json.loads(p.read_text())
