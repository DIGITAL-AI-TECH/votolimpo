---
type: tasks
title: "Tasks — Frente 2: Anthropic LLM Provider"
created: 2026-10-05
tags: [help-core, anthropic, code, tasks]
---

# Tasks — Frente 2: Anthropic LLM Provider

## Fase 1: Scaffolding (preparar o terreno)

### T1.1 — Adicionar `anthropic>=0.40.0` ao pyproject.toml

**Arquivo**: `pyproject.toml`

**Mudança**:
```toml
# Bloco [project] → dependencies — adicionar após "openai>=1.30.0":
"anthropic>=0.40.0",
```

**Critério de done**: `grep 'anthropic' pyproject.toml` retorna a linha adicionada.

**blockedBy**: nenhuma
**[P]**: pode rodar em paralelo com T1.2

---

### T1.2 — Adicionar `anthropic_api_key` ao config.py

**Arquivo**: `app/config.py`

**Mudança**: inserir campo após `openai_api_key: str = ""` (linha 28):
```python
# Anthropic (opcional — necessário somente para pipelines com llm_provider: anthropic)
anthropic_api_key: str = ""
```

O pydantic-settings lê automaticamente `ANTHROPIC_API_KEY` do ambiente.

**Critério de done**: `from app.config import settings; settings.anthropic_api_key` não
lança `AttributeError`.

**blockedBy**: nenhuma
**[P]**: pode rodar em paralelo com T1.1

---

## Fase 2: Implementação do Provider

### T2.1 — Criar `app/plugins/llm/anthropic_provider.py`

**Arquivo**: `app/plugins/llm/anthropic_provider.py` (NOVO)

**Estrutura completa esperada**:

```python
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
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-3-5-20241022": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def _estimate_anthropic_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = ANTHROPIC_MODEL_PRICING.get(model, (3.00, 15.00))
    return round(
        (input_tokens / 1_000_000) * input_rate
        + (output_tokens / 1_000_000) * output_rate,
        6,
    )


class AnthropicProvider:
    """Anthropic Claude provider com structured output via tool_use."""

    def __init__(self):
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def process(
        self,
        content: str,
        system_prompt: str,
        output_schema: dict | None,
        config: dict,
    ) -> dict[str, Any]:
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
                wait = float(
                    getattr(exc, "response", None)
                    and exc.response.headers.get("retry-after")
                    or 2 ** attempt
                )
                logger.warning("Anthropic rate limit, retry %d in %.1fs", attempt + 1, wait)
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
        cost_usd = _estimate_anthropic_cost(model, usage_raw.input_tokens, usage_raw.output_tokens)

        return {"output": output, "usage": usage, "cost_usd": cost_usd}

    async def _call_with_tool(self, content, system_prompt, output_schema, model, max_tokens):
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
                output = block.input  # já é dict
                break
        if output is None:
            raise ValueError("Anthropic tool_use: nenhum bloco tool_use na resposta")
        return output, response.usage

    async def _call_plain_json(self, content, system_prompt, model, max_tokens):
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
            raise ValueError(f"LLM returned invalid JSON: {e}. Raw: {raw[:200]}") from e
        return output, response.usage
```

**Critério de done**:
- `python -c "from app.plugins.llm.anthropic_provider import AnthropicProvider"` não lança erros
- Classe possui método `process()` com assinatura idêntica ao `LLMProvider` Protocol

**blockedBy**: T1.2 (precisa de `settings.anthropic_api_key`)

---

### T2.2 — Registrar AnthropicProvider em `__init__.py`

**Arquivo**: `app/plugins/llm/__init__.py`

**Mudanças cirúrgicas (3 pontos)**:

1. Adicionar import no topo do arquivo (após `from openai import AsyncOpenAI`):
```python
from .anthropic_provider import AnthropicProvider
```

2. Adicionar pricing dos modelos Anthropic ao `MODEL_PRICING` (após linha com `"gpt-4o-mini"`):
```python
# Anthropic Claude
"claude-sonnet-4-20250514": (3.00, 15.00),
"claude-haiku-3-5-20241022": (0.80, 4.00),
"claude-opus-4-20250514": (15.00, 75.00),
```

3. Registrar no dict `LLM_PROVIDERS` (após `"openai": OpenAIProvider`):
```python
"anthropic": AnthropicProvider,
```

**Critério de done**:
```python
from app.plugins.llm import get_llm_provider, LLM_PROVIDERS
assert "anthropic" in LLM_PROVIDERS
p = get_llm_provider("anthropic")
assert type(p).__name__ == "AnthropicProvider"
p2 = get_llm_provider("openai")
assert type(p2).__name__ == "OpenAIProvider"
p3 = get_llm_provider("unknown_provider")
assert type(p3).__name__ == "OpenAIProvider"  # fallback
```

**blockedBy**: T2.1 (arquivo anthropic_provider.py deve existir antes do import)

---

## Fase 3: Testes

### T3.1 — Criar `tests/plugins/llm/test_anthropic_provider.py`

**Arquivo**: `tests/plugins/llm/test_anthropic_provider.py` (NOVO)

**Cobertura obrigatória**:

```python
"""Testes do AnthropicProvider — sem chamadas reais à API."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

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


# ── factory e registro ───────────────────────────────────────────────────────

def test_get_llm_provider_returns_anthropic():
    from app.plugins.llm import LLM_PROVIDERS, get_llm_provider
    assert "anthropic" in LLM_PROVIDERS
    p = get_llm_provider("anthropic")
    assert isinstance(p, AnthropicProvider)

def test_get_llm_provider_fallback_openai():
    from app.plugins.llm import get_llm_provider
    p = get_llm_provider("nao_existe")
    from app.plugins.llm import OpenAIProvider
    assert isinstance(p, OpenAIProvider)


# ── process() com output_schema (tool_use) ───────────────────────────────────

@pytest.mark.asyncio
async def test_process_with_schema_returns_correct_shape():
    provider = AnthropicProvider()
    expected_output = {"name": "João", "score": 0.9}
    mock_resp = _mock_tool_response(expected_output, _mock_usage(200, 100))

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        result = await provider.process(
            content="texto",
            system_prompt="Extraia dados.",
            output_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            config={"model": "claude-sonnet-4-20250514"},
        )

    assert result["output"] == expected_output
    assert result["usage"]["prompt_tokens"] == 200
    assert result["usage"]["completion_tokens"] == 100
    assert result["usage"]["total_tokens"] == 300
    assert result["usage"]["model"] == "claude-sonnet-4-20250514"
    assert result["cost_usd"] > 0

@pytest.mark.asyncio
async def test_process_with_schema_uses_tool_use():
    """Confirma que messages.create é chamado com tools e tool_choice."""
    provider = AnthropicProvider()
    mock_resp = _mock_tool_response({"x": 1})

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        await provider.process("c", "s", {"type": "object"}, {})
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tool_choice"]["type"] == "tool"
        assert call_kwargs["tool_choice"]["name"] == "extraction_output"


# ── process() sem output_schema (JSON livre) ─────────────────────────────────

@pytest.mark.asyncio
async def test_process_without_schema_parses_json():
    provider = AnthropicProvider()
    mock_resp = _mock_text_response(json.dumps({"key": "value"}))

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        result = await provider.process("content", "prompt", None, {})

    assert result["output"] == {"key": "value"}

@pytest.mark.asyncio
async def test_process_without_schema_raises_on_invalid_json():
    provider = AnthropicProvider()
    mock_resp = _mock_text_response("isso nao e json")

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        with pytest.raises(ValueError, match="LLM returned invalid JSON"):
            await provider.process("content", "prompt", None, {})


# ── custo ────────────────────────────────────────────────────────────────────

def test_estimate_cost_sonnet():
    cost = _estimate_anthropic_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0, rel=1e-3)  # 3.00 + 15.00

def test_estimate_cost_haiku():
    cost = _estimate_anthropic_cost("claude-haiku-3-5-20241022", 1_000_000, 1_000_000)
    assert cost == pytest.approx(4.80, rel=1e-3)  # 0.80 + 4.00

def test_estimate_cost_opus():
    cost = _estimate_anthropic_cost("claude-opus-4-20250514", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0, rel=1e-3)  # 15.00 + 75.00

def test_estimate_cost_unknown_model_uses_sonnet_default():
    cost_unknown = _estimate_anthropic_cost("claude-unknown", 1_000_000, 1_000_000)
    cost_default = _estimate_anthropic_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
    assert cost_unknown == cost_default

def test_cost_appears_in_process_result():
    """cost_usd no retorno de process() deve ser > 0 para tokens reais."""
    cost = _estimate_anthropic_cost("claude-sonnet-4-20250514", 500, 300)
    assert cost > 0


# ── error handling ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_retries_and_raises_after_max():
    from anthropic import RateLimitError as AnthropicRateLimitError

    provider = AnthropicProvider()
    exc = MagicMock(spec=AnthropicRateLimitError)
    exc.response = MagicMock()
    exc.response.headers = {"retry-after": "0"}  # sem espera no teste

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(side_effect=exc)
        with pytest.raises(Exception):
            await provider.process("c", "s", None, {})
        assert mock_client.messages.create.call_count == 3  # MAX_RETRIES

@pytest.mark.asyncio
async def test_api_error_propagates_immediately():
    from anthropic import APIError as AnthropicAPIError

    provider = AnthropicProvider()
    exc = MagicMock(spec=AnthropicAPIError)

    with patch.object(provider, "client") as mock_client:
        mock_client.messages.create = AsyncMock(side_effect=exc)
        with pytest.raises(Exception):
            await provider.process("c", "s", None, {})
        # APIError não deve ser retentada
        assert mock_client.messages.create.call_count == 1
```

**Critério de done**: `pytest tests/plugins/llm/test_anthropic_provider.py -v` passa 100%.

**blockedBy**: T2.1, T2.2

---

## Fase 4: Validação final

### T4.1 — Rodar suite completa e confirmar sem regressão

```bash
cd /workspace/votolimpo/processing-engine
pytest tests/ -v --tb=short
```

**Critério de done**:
- Zero falhas novas (baseline: todos os testes que passavam antes continuam passando)
- `tests/plugins/llm/test_anthropic_provider.py` 100% verde
- Nenhum teste existente de OpenAI foi alterado

**blockedBy**: T3.1

---

### T4.2 — Verificar backward-compat via assert de importação

```bash
python -c "
from app.plugins.llm import get_llm_provider, LLM_PROVIDERS
p = get_llm_provider('anthropic')
print('AnthropicProvider OK:', type(p).__name__)
p2 = get_llm_provider('openai')
print('OpenAIProvider OK:', type(p2).__name__)
p3 = get_llm_provider('nao_existe')
print('Fallback OK:', type(p3).__name__)
assert 'anthropic' in LLM_PROVIDERS
assert type(p).__name__ == 'AnthropicProvider'
assert type(p2).__name__ == 'OpenAIProvider'
assert type(p3).__name__ == 'OpenAIProvider'
print('Todos os asserts passaram.')
"
```

**Critério de done**: script roda sem exceção e imprime "Todos os asserts passaram."

**blockedBy**: T2.2

---

## Resumo de Dependências

```
T1.1 ────────────────────────────────────────────────────┐
                                                          ├─ T4.1
T1.2 ──── T2.1 ──── T2.2 ──── T3.1 ─────────────────────┤
                 └─────────── T4.2 ─────────────────────┘
```

Fases 1 (T1.1 + T1.2) podem rodar em paralelo entre si.
T2.1 depende de T1.2. T2.2 depende de T2.1. T3.1 depende de T2.2.
T4.1 e T4.2 dependem de T3.1 e T2.2 respectivamente.
