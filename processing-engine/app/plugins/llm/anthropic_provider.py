"""Anthropic Claude LLM provider — implementa o Protocol LLMProvider."""

import asyncio
import json
import logging
from typing import Any

from anthropic import AsyncAnthropic, RateLimitError, APIError

from ...config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

# Pricing ($/1M tokens: [input, output])
ANTHROPIC_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-6": (15.00, 75.00),
}

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _is_oauth_token(key: str) -> bool:
    """Detect OAuth tokens (sk-ant-oat*) vs regular API keys (sk-ant-api*)."""
    return key.startswith("sk-ant-oat")


def _estimate_anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estima custo em USD baseado no pricing map do modelo."""
    input_rate, output_rate = ANTHROPIC_MODEL_PRICING.get(model, (3.00, 15.00))
    return round(
        (input_tokens / 1_000_000) * input_rate
        + (output_tokens / 1_000_000) * output_rate,
        6,
    )


class AnthropicProvider:
    """Anthropic Claude provider com structured output via tool_use.

    Supports both regular API keys (sk-ant-api*) and OAuth tokens
    (sk-ant-oat*) from Anthropic subscriptions. OAuth tokens use
    Authorization: Bearer header + anthropic-beta: oauth-2025-04-20.
    """

    def __init__(self):
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            key = settings.anthropic_api_key
            if _is_oauth_token(key):
                logger.info("Using OAuth token auth (Authorization: Bearer)")
                self._client = AsyncAnthropic(
                    auth_token=key,
                    default_headers={"anthropic-beta": "oauth-2025-04-20"},
                )
            else:
                logger.info("Using API key auth (x-api-key)")
                self._client = AsyncAnthropic(api_key=key)
        return self._client

    async def process(
        self,
        content: str,
        system_prompt: str,
        output_schema: dict | None,
        config: dict,
    ) -> dict[str, Any]:
        """Process content through Anthropic Claude. Returns parsed output + usage info."""
        model = config.get("model", DEFAULT_MODEL)
        max_tokens = config.get("max_tokens", 8096)

        for attempt in range(MAX_RETRIES):
            try:
                if output_schema:
                    response = await self._call_with_tool(
                        content, system_prompt, output_schema, model, max_tokens
                    )
                else:
                    response = await self._call_plain_json(
                        content, system_prompt, model, max_tokens
                    )
                break
            except RateLimitError as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                retry_after = None
                if hasattr(exc, "response") and exc.response is not None:
                    retry_after = exc.response.headers.get("retry-after")
                wait = float(retry_after) if retry_after is not None else float(2 ** attempt)
                logger.warning(
                    "Anthropic rate limit, retry %d in %.1fs", attempt + 1, wait
                )
                await asyncio.sleep(wait)
            except APIError:
                raise

        output, usage_raw = response

        usage = {
            "prompt_tokens": usage_raw.input_tokens,
            "completion_tokens": usage_raw.output_tokens,
            "total_tokens": usage_raw.input_tokens + usage_raw.output_tokens,
            "model": model,
        }
        cost_usd = _estimate_anthropic_cost(
            model, usage_raw.input_tokens, usage_raw.output_tokens
        )

        return {"output": output, "usage": usage, "cost_usd": cost_usd}

    async def _call_with_tool(
        self,
        content: str,
        system_prompt: str,
        output_schema: dict,
        model: str,
        max_tokens: int,
    ):
        """Structured output via tool_use — garante JSON válido conforme schema."""
        tool = {
            "name": "extraction_output",
            "description": "Structured extraction output",
            "input_schema": output_schema,
        }
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
            tools=[tool],
            tool_choice={"type": "tool", "name": "extraction_output"},
        )
        output = None
        for block in response.content:
            if block.type == "tool_use":
                output = block.input  # ja e dict — sem json.loads necessario
                break
        if output is None:
            raise ValueError("Anthropic tool_use: nenhum bloco tool_use na resposta")
        return output, response.usage

    async def _call_plain_json(
        self,
        content: str,
        system_prompt: str,
        model: str,
        max_tokens: int,
    ):
        """JSON livre via instrução no system prompt."""
        effective_system = system_prompt
        if "json" not in system_prompt.lower():
            effective_system += "\n\nRespond with valid JSON only, no markdown fences."
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=effective_system,
            messages=[{"role": "user", "content": content}],
        )
        raw = response.content[0].text
        try:
            output = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON: {e}. Raw: {raw[:200]}"
            ) from e
        return output, response.usage
