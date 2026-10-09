# 004 — Migrar pipeline helpcore-analysis para Anthropic SDK (subscription)

## Objetivo

Trocar o LLM provider do pipeline `helpcore-analysis` de OpenAI (gpt-4.1-mini) para Anthropic Claude (claude-sonnet-4-20250514) usando token do pool de subscription do Claude Code Server.

## Motivacao

- Usar a subscription Anthropic ja contratada (token "conta 20x" do pool do Claude Code Server)
- Custo efetivo zero adicional (ja pago na subscription)
- Qualidade superior do Claude Sonnet 4 para classificacao estruturada

## IN-SCOPE

1. Alterar `helpcore-analysis.yaml`: `llm_provider: anthropic`, `llm_model: claude-sonnet-4-20250514`
2. Descomentar `ANTHROPIC_API_KEY` no `docker-stack.helpcore.yml`
3. Adicionar `HC_ANTHROPIC_API_KEY` nas env vars do Portainer (stack ID 362, endpoint 4)
4. Deploy da stack atualizada
5. Testar classificacao de 10 artigos

## OUT-OF-SCOPE

- Alteracao do Anthropic provider (`anthropic_provider.py`) — ja implementado e funcional
- Alteracao do pipeline `helpcore-rewrite.yaml` — ja usa Anthropic
- Mudanca de modelo (usar Sonnet 4, nao Opus/Haiku)
- Alteracao do output schema ou system prompt

## Token

- Fonte: `TOKEN_POOL` da stack `claude-code-server` (Portainer ID 160)
- Label: "conta 20x" (subscription)
- Formato: `sk-ant-oat01-...`

## Aceite

- A1. Pipeline YAML aponta para `llm_provider: anthropic`
- A2. Stack deployada com `ANTHROPIC_API_KEY` configurada
- A3. 10 artigos classificados com sucesso via Anthropic
- A4. Campos `inventory` e `quality` preenchidos corretamente
