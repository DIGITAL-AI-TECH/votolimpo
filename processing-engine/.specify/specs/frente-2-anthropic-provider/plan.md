---
type: plan
title: "Plan — Frente 2: Anthropic LLM Provider"
created: 2026-10-05
tags: [help-core, anthropic, code, plan]
---

# Plan — Frente 2: Anthropic LLM Provider

## Arquitetura

```
Pipeline YAML
  llm:
    provider: anthropic        ← campo lido pelo orchestrator
    model: claude-sonnet-4-20250514
    temperature: 0.1
    max_tokens: 8096
        │
        ▼
orchestrator.py
  from ..plugins.llm import get_llm_provider
  provider = get_llm_provider(pipeline.llm.provider)
  # "anthropic" → LLM_PROVIDERS["anthropic"]() → AnthropicProvider()
        │
        ▼
app/plugins/llm/__init__.py
  LLM_PROVIDERS = {
    "openai":    OpenAIProvider,   ← existente, não alterado
    "anthropic": AnthropicProvider ← NOVO (T1.4)
  }

  def get_llm_provider(provider: str) -> LLMProvider:
    cls = LLM_PROVIDERS.get(provider, OpenAIProvider)  ← fallback openai
    return cls()
        │
        ▼
app/plugins/llm/anthropic_provider.py   ← NOVO (T1.3)
  class AnthropicProvider:
    async def process(content, system_prompt, output_schema, config) -> dict
```

**Dois OpenAIProvider existentes — não confundir:**
- `__init__.py` L29-105: método `process()`, usado via `get_llm_provider("openai")` — padrão a seguir
- `openai.py` L13+: método `complete()`, importado diretamente pelo orchestrator para embeddings —
  não é afetado por esta frente

O `AnthropicProvider` segue o padrão do `__init__.py`, não o de `openai.py`.

## Decisões Técnicas

### 1. Structured Output: tool_use

A Anthropic não tem `json_schema` nativo como OpenAI. A estratégia da spec é `tool_use`:

```python
# Quando output_schema está presente
tool = {
    "name": "extraction_output",
    "description": "Structured extraction output",
    "input_schema": output_schema,  # JSON Schema passado como-está
}

response = await client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=system_prompt,
    messages=[{"role": "user", "content": content}],
    tools=[tool],
    tool_choice={"type": "tool", "name": "extraction_output"},
)

# Extrair input do bloco tool_use
for block in response.content:
    if block.type == "tool_use":
        output = block.input  # já é dict — sem json.loads necessário
        break
```

**Sem output_schema**: usar `response_format` não existe na Anthropic. Instruir via system prompt:

```python
if not output_schema:
    effective_system = system_prompt
    if "json" not in system_prompt.lower():
        effective_system += "\n\nRespond with valid JSON only, no markdown."

response = await client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=effective_system,
    messages=[{"role": "user", "content": content}],
)
raw = response.content[0].text
output = json.loads(raw)  # pode lançar JSONDecodeError → propagar como ValueError
```

### 2. Pricing Map

Modelos suportados com pricing público ($/1M tokens: [input, output]):

```python
ANTHROPIC_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-3-5-20241022": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}
```

Os valores são adicionados ao `MODEL_PRICING` global em `__init__.py` para que
`_estimate_cost()` já existente funcione sem modificação — ela é agnóstica ao provider.

### 3. Usage: tokens Anthropic → formato interno

```python
# Anthropic retorna:
response.usage.input_tokens   # prompt
response.usage.output_tokens  # completion

# Formato interno (compatível com OpenAIProvider):
usage = {
    "prompt_tokens":     response.usage.input_tokens,
    "completion_tokens": response.usage.output_tokens,
    "total_tokens":      response.usage.input_tokens + response.usage.output_tokens,
    "model":             model,
}
```

### 4. Rate Limiting com retry-after

A Anthropic retorna `anthropic.RateLimitError` quando rate limit é atingido.
O header `retry-after` (segundos) está em `exc.response.headers.get("retry-after")`.

```python
import asyncio
from anthropic import RateLimitError, APIError

MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        response = await client.messages.create(...)
        break
    except RateLimitError as exc:
        if attempt == MAX_RETRIES - 1:
            raise
        wait = float(exc.response.headers.get("retry-after", 2 ** attempt))
        await asyncio.sleep(wait)
    except APIError:
        raise  # outros erros não são retentáveis
```

### 5. Client lazy initialization

Mesmo padrão do `OpenAIProvider` em `__init__.py` — client criado sob demanda via property:

```python
class AnthropicProvider:
    def __init__(self):
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client
```

### 6. `anthropic_api_key` no Settings

`app/config.py` não possui `anthropic_api_key`. Deve ser adicionado como campo opcional
(string vazia como default — compatível com deploys que não usam Anthropic):

```python
# app/config.py — adicionar após openai_api_key
anthropic_api_key: str = ""
# Env var: ANTHROPIC_API_KEY (lida automaticamente pelo pydantic-settings)
```

### 7. Dependência

`pyproject.toml` atualmente lista apenas `openai>=1.30.0`. Adicionar ao bloco `[project]`:

```toml
"anthropic>=0.40.0",
```

### 8. Backward compatibility

`get_llm_provider()` atual:
```python
def get_llm_provider(provider: str) -> LLMProvider:
    cls = LLM_PROVIDERS.get(provider, OpenAIProvider)
    return cls()
```

O fallback para `OpenAIProvider` quando `provider` não está no dict já garante que:
- Pipelines sem campo `llm_provider` (valor None/vazio) → OpenAI
- Pipelines com `llm_provider: openai` → OpenAI
- Pipelines com `llm_provider: anthropic` → Anthropic

Nenhuma alteração no `get_llm_provider()` é necessária.

## Contratos

### `AnthropicProvider.process()` — retorno obrigatório

```python
{
    "output": dict,          # JSON estruturado extraído pelo LLM
    "usage": {
        "prompt_tokens":     int,
        "completion_tokens": int,
        "total_tokens":      int,
        "model":             str,
    },
    "cost_usd": float,       # arredondado a 6 casas decimais
}
```

Idêntico ao `OpenAIProvider.process()` em `__init__.py` L101-105.

### Erros propagados

| Condição | Exceção levantada |
|---|---|
| JSON inválido sem output_schema | `ValueError("LLM returned invalid JSON: ...")` |
| APIError não-retentável | `anthropic.APIError` (propagar) |
| RateLimitError após MAX_RETRIES | `anthropic.RateLimitError` (propagar) |

## Whitelist de Arquivos

| Arquivo | Ação | Mudança exata |
|---|---|---|
| `app/plugins/llm/anthropic_provider.py` | CRIAR | Novo arquivo com `AnthropicProvider` |
| `app/plugins/llm/__init__.py` | MODIFICAR | Import + registro em LLM_PROVIDERS + pricing map |
| `pyproject.toml` | MODIFICAR | `"anthropic>=0.40.0"` na lista de dependências |
| `app/config.py` | MODIFICAR | Campo `anthropic_api_key: str = ""` após `openai_api_key` |
| `tests/plugins/llm/test_anthropic_provider.py` | CRIAR | Suite de testes com mocks |

Qualquer arquivo fora desta whitelist requer justificativa explícita no commit.
