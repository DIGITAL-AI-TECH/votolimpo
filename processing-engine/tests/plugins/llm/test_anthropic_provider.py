"""Testes do AnthropicProvider — sem chamadas reais à API."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.llm.anthropic_provider import (
    AnthropicProvider,
    _estimate_anthropic_cost,
)


# ── helpers de mock ─────────────────────────────────────────────────────────

def _mock_usage(input_tokens=100, output_tokens=50):
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


def _mock_tool_response(output_dict: dict, usage=None):
    """Simula resposta tool_use da Anthropic."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = output_dict
    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage or _mock_usage()
    return resp


def _mock_text_response(text: str, usage=None):
    """Simula resposta de texto livre da Anthropic."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = usage or _mock_usage()
    return resp


def _make_provider_with_mock_client(mock_create_return=None, mock_create_side_effect=None):
    """Cria AnthropicProvider com _client mockado — evita property sem setter."""
    provider = AnthropicProvider()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(
        return_value=mock_create_return,
        side_effect=mock_create_side_effect,
    )
    provider._client = mock_client  # injeta diretamente (bypass da property lazy)
    return provider, mock_client


# ── factory e registro ───────────────────────────────────────────────────────

def test_get_llm_provider_returns_anthropic():
    from app.plugins.llm import LLM_PROVIDERS, get_llm_provider
    assert "anthropic" in LLM_PROVIDERS
    p = get_llm_provider("anthropic")
    assert isinstance(p, AnthropicProvider)


def test_get_llm_provider_fallback_openai():
    from app.plugins.llm import get_llm_provider, OpenAIProvider
    p = get_llm_provider("nao_existe")
    assert isinstance(p, OpenAIProvider)


# ── process() com output_schema (tool_use) ───────────────────────────────────

@pytest.mark.asyncio
async def test_process_with_schema_returns_correct_shape():
    expected_output = {"name": "João", "score": 0.9}
    mock_resp = _mock_tool_response(expected_output, _mock_usage(200, 100))
    provider, _ = _make_provider_with_mock_client(mock_create_return=mock_resp)

    result = await provider.process(
        content="texto",
        system_prompt="Extraia dados.",
        output_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        config={"model": "claude-sonnet-4-5-20250929"},
    )

    assert result["output"] == expected_output
    assert result["usage"]["prompt_tokens"] == 200
    assert result["usage"]["completion_tokens"] == 100
    assert result["usage"]["total_tokens"] == 300
    assert result["usage"]["model"] == "claude-sonnet-4-5-20250929"
    assert result["cost_usd"] > 0


@pytest.mark.asyncio
async def test_process_with_schema_uses_tool_use():
    """Confirma que messages.create é chamado com tools e tool_choice."""
    mock_resp = _mock_tool_response({"x": 1})
    provider, mock_client = _make_provider_with_mock_client(mock_create_return=mock_resp)

    await provider.process("c", "s", {"type": "object"}, {})
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" in call_kwargs
    assert call_kwargs["tool_choice"]["type"] == "tool"
    assert call_kwargs["tool_choice"]["name"] == "extraction_output"


# ── process() sem output_schema (JSON livre) ─────────────────────────────────

@pytest.mark.asyncio
async def test_process_without_schema_parses_json():
    mock_resp = _mock_text_response(json.dumps({"key": "value"}))
    provider, _ = _make_provider_with_mock_client(mock_create_return=mock_resp)

    result = await provider.process("content", "prompt", None, {})
    assert result["output"] == {"key": "value"}


@pytest.mark.asyncio
async def test_process_without_schema_raises_on_invalid_json():
    mock_resp = _mock_text_response("isso nao e json")
    provider, _ = _make_provider_with_mock_client(mock_create_return=mock_resp)

    with pytest.raises(ValueError, match="LLM returned invalid JSON"):
        await provider.process("content", "prompt", None, {})


# ── custo ────────────────────────────────────────────────────────────────────

def test_estimate_cost_sonnet():
    cost = _estimate_anthropic_cost("claude-sonnet-4-5-20250929", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0, rel=1e-3)  # 3.00 + 15.00


def test_estimate_cost_haiku():
    cost = _estimate_anthropic_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    assert cost == pytest.approx(4.80, rel=1e-3)  # 0.80 + 4.00


def test_estimate_cost_opus():
    cost = _estimate_anthropic_cost("claude-opus-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0, rel=1e-3)  # 15.00 + 75.00


def test_estimate_cost_unknown_model_uses_sonnet_default():
    cost_unknown = _estimate_anthropic_cost("claude-unknown", 1_000_000, 1_000_000)
    cost_default = _estimate_anthropic_cost("claude-sonnet-4-5-20250929", 1_000_000, 1_000_000)
    assert cost_unknown == cost_default


def test_cost_appears_in_process_result():
    """cost_usd calculado deve ser > 0 para tokens reais."""
    cost = _estimate_anthropic_cost("claude-sonnet-4-5-20250929", 500, 300)
    assert cost > 0


# ── error handling ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_retries_and_raises_after_max():
    from anthropic import RateLimitError as AnthropicRateLimitError

    # Cria subclasse real de RateLimitError para que isinstance() funcione
    # no except do provider (MagicMock(spec=...) não passa isinstance check)
    class FakeRateLimitError(AnthropicRateLimitError):
        def __init__(self):
            self.response = MagicMock()
            self.response.headers = {"retry-after": "0"}  # sem espera no teste

        def __str__(self):
            return "rate limit"

    exc = FakeRateLimitError()

    provider, mock_client = _make_provider_with_mock_client(mock_create_side_effect=exc)

    with pytest.raises(AnthropicRateLimitError):
        await provider.process("c", "s", None, {})
    assert mock_client.messages.create.call_count == 3  # MAX_RETRIES


@pytest.mark.asyncio
async def test_api_error_propagates_immediately():
    from anthropic import APIError as AnthropicAPIError

    exc = MagicMock(spec=AnthropicAPIError)

    provider, mock_client = _make_provider_with_mock_client(mock_create_side_effect=exc)

    with pytest.raises(Exception):
        await provider.process("c", "s", None, {})
    # APIError nao deve ser retentada
    assert mock_client.messages.create.call_count == 1
