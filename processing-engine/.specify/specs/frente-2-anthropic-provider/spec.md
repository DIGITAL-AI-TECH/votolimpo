---
type: spec
title: "Frente 2 — Anthropic LLM Provider"
created: 2026-10-05
tags: [help-core, anthropic, llm-provider, code]
status: draft
---

# Frente 2 — Anthropic LLM Provider

## Objetivo

Implementar o Anthropic SDK como LLM provider no Processing Engine, seguindo o padrão
do `OpenAIProvider` já existente. Ao final, pipelines poderão selecionar
`llm_provider: anthropic` via YAML e o orchestrator resolverá automaticamente pelo
factory `get_llm_provider()`.

## Contexto Técnico

O PE já possui infraestrutura pronta para múltiplos providers:

- `app/plugins/llm/__init__.py` — define `LLMProvider(Protocol)`, `OpenAIProvider`,
  dict `LLM_PROVIDERS`, função factory `get_llm_provider()` e `_estimate_cost()`
- `app/plugins/llm/openai.py` — segundo OpenAIProvider com interface `complete()` diferente,
  usado diretamente pelo orchestrator via import direto
- `app/core/orchestrator.py` — usa `get_llm_provider()` para resolver o provider pelo nome
- Pipeline YAML define `llm.provider` (campo usado para selecionar o provider)

**Dois OpenAIProvider existentes (não confundir):**
1. `__init__.py` linhas 29-105 — usado via `get_llm_provider("openai")`
2. `openai.py` linhas 13+ — interface `complete()`, importado diretamente em alguns pontos

O novo `AnthropicProvider` deve seguir o padrão do provider em `__init__.py` (método
`process()`), não o de `openai.py`.

## IN-SCOPE

### 1. `app/plugins/llm/anthropic_provider.py` (arquivo NOVO)

- Classe `AnthropicProvider` implementando o Protocol `LLMProvider`
- Método `process(content, system_prompt, output_schema, config) -> dict` com mesma
  assinatura do `OpenAIProvider`
- Usa `anthropic.AsyncAnthropic` (SDK oficial assíncrono)
- Structured output via `tool_use` com schema quando `output_schema` fornecido,
  ou parse de JSON do response como fallback
- Tracking de usage: `input_tokens`, `output_tokens`, `cost_usd`
- Pricing map interno para modelos Claude:
  - `claude-sonnet-4-20250514` (default)
  - `claude-haiku-3-5-20241022`
  - `claude-opus-4-20250514`
- Respeitar headers `retry-after` da API Anthropic em rate limiting
- Default model: `claude-sonnet-4-20250514`

### 2. `app/plugins/llm/__init__.py` (MODIFICAR)

- Import e registro do `AnthropicProvider` em `LLM_PROVIDERS`:
  `LLM_PROVIDERS["anthropic"] = AnthropicProvider`
- Atualizar `MODEL_PRICING` com pricing dos modelos Anthropic

### 3. `pyproject.toml` (MODIFICAR)

- Adicionar `anthropic>=0.40.0` às dependências do projeto

### 4. `tests/plugins/llm/test_anthropic_provider.py` (arquivo NOVO)

- Testar `process()` com `output_schema` fornecido (structured output via tool_use)
- Testar `process()` sem `output_schema` (JSON parse do response)
- Testar estimativa de custo (`cost_usd`) para modelos suportados
- Testar error handling: APIError, RateLimitError, timeout
- Mock de `anthropic.AsyncAnthropic` — sem chamadas reais à API

### 5. `app/config.py` (MODIFICAR se necessário)

- Adicionar `anthropic_api_key: str = ""` ao `Settings` se ainda não existir
- Env var correspondente: `ANTHROPIC_API_KEY`

## OUT-OF-SCOPE

- Pipeline YAMLs — tratado na Frente 1
- Configuração Docker / infra — tratado na Frente 1
- Mudanças no `orchestrator.py` — `get_llm_provider()` já resolve via `LLM_PROVIDERS`
- Migração de pipelines existentes para Anthropic
- Embeddings Anthropic — API de embeddings não existe no Anthropic; manter OpenAI para embeddings
- Testes de integração com API real Anthropic

## Arquivos a Criar/Modificar (whitelist)

| Arquivo | Ação |
|---|---|
| `app/plugins/llm/anthropic_provider.py` | CRIAR |
| `app/plugins/llm/__init__.py` | MODIFICAR |
| `pyproject.toml` | MODIFICAR |
| `tests/plugins/llm/test_anthropic_provider.py` | CRIAR |
| `app/config.py` | MODIFICAR (se `ANTHROPIC_API_KEY` ausente) |

Qualquer arquivo fora desta whitelist requer justificativa explícita no commit.

## Requisitos Técnicos

- `AnthropicProvider` DEVE implementar o Protocol `LLMProvider` (método `process`)
- Structured output: usar `messages.create()` com tool_use quando `output_schema`
  presente; fallback para parse de JSON do response text
- Rate limiting: inspecionar headers `retry-after` e respeitar o delay indicado
- Default model: `claude-sonnet-4-20250514`
- Backward compatibility: pipelines sem `llm_provider` ou com `llm_provider: openai`
  continuam usando OpenAI sem nenhuma alteração de comportamento
- `ANTHROPIC_API_KEY` carregada via env var — nunca hardcoded
- Retorno de `process()` DEVE ter chaves: `output` (dict), `usage` (dict com
  `input_tokens` e `output_tokens`), `cost_usd` (float)

## Acceptance Criteria

| ID | Critério | Como verificar |
|---|---|---|
| A1 | `from app.plugins.llm import get_llm_provider; p = get_llm_provider("anthropic")` retorna `AnthropicProvider` | REPL / teste unitário |
| A2 | `p.process(content, system_prompt, output_schema, config)` retorna dict com chaves `output`, `usage`, `cost_usd` | Teste unitário com mock |
| A3 | Pipeline YAML com `llm_provider: anthropic` é processado end-to-end pelo orchestrator | Teste de integração manual ou E2E |
| A4 | Pipelines existentes sem `llm_provider` ou com `openai` continuam funcionando identicamente | Testes de regressão do suite atual |
| A5 | `pytest tests/plugins/llm/test_anthropic_provider.py` passa 100% | CI / execução local |
| A6 | `anthropic>=0.40.0` declarado no `pyproject.toml` | `grep anthropic pyproject.toml` |
| A7 | Cost tracking funcional para sonnet, haiku e opus (valores não-zero para tokens reais) | Teste unitário com mock de usage |

## REMOVIDOS

Nenhuma função, endpoint ou módulo existente é removido nesta frente.
