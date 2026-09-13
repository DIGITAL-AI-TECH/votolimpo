# Processing Engine Constitution

## Core Principles

### I. Agnóstico por Design
O engine NÃO conhece o domínio dos dados que processa. Cada projeto registra um pipeline via YAML config (ingestor, dedup, LLM, validators, sink). Nenhum código específico de projeto vive no engine — prompts, schemas e configs vivem fora do core. Novo projeto = novo YAML, zero código.

### II. Anti-Reprocessamento (NON-NEGOTIABLE)
Nenhum item já processado com sucesso pode ser reprocessado sem flag explícito (`skip_cache=true`). Três camadas obrigatórias: (1) URL hash antes do scrape, (2) content hash antes do LLM, (3) cache de resultado por content hash. Violação deste princípio é blocker — o item deve ser rejeitado com `dedup_result: duplicate`.

### III. Custo Controlado e Metrificado
Todo processamento LLM gera registro de custo granular (prompt_tokens, completion_tokens, cost_usd) em `llm_call_log` — incluindo retries e embeddings. Preços por modelo vivem em `model_pricing` (atualizável sem deploy). Custos são consultáveis por execução, por chamada, por pipeline (projeto) e por período via API. Budget limits por pipeline previnem gastos não-autorizados. Cache evita chamadas redundantes. Rate limiting protege contra burst. Target: <$10/mês para 10K itens com gpt-4.1-mini.

### IV. Plugin-First
Cada estágio do pipeline (ingestor, dedup, llm, validator, sink) é um plugin que implementa um `typing.Protocol`. Adicionar novo tipo = criar classe que satisfaz o protocolo e registrar no registry. Zero herança, zero ABC.

### V. Stack Mínima
PostgreSQL é a única dependência de infraestrutura (além do próprio Python). Job queue via SKIP LOCKED, embeddings via pgvector, cache em tabela, métricas em tabela. Sem Redis, sem RabbitMQ, sem Qdrant, sem serviço externo. Container único.

### VI. Schema First
Todo schema de banco é versionado via Alembic. Todo output de pipeline é validado contra JSON Schema ANTES de persistir. API contracts definidos em OpenAPI 3.1. Sem dado não-tipado.

### VII. Idempotência Total
Jobs com mesmo `idempotency_key` retornam resultado existente, nunca reprocessam. Sinks usam upsert (`ON CONFLICT`). Re-executar um pipeline no mesmo dataset produz resultado idêntico (determinismo via temperature=0 + seed).

### VIII. Observabilidade
Cada item processado gera um `processing_log` com: step executado, duração, tokens usados, custo, resultado. Jobs expõem contadores em tempo real (items_completed, items_failed). Endpoint `/v1/stats` agrega métricas por pipeline.

### IX. Testabilidade
Testes rodam contra PostgreSQL real (testcontainers). Protocols permitem injeção de mocks para LLM em testes unitários. Zero mock de banco de dados. Contract tests validam API contra OpenAPI spec.

### X. Segurança
API key obrigatória em todos os endpoints (exceto /health). Sem injeção SQL — queries parametrizadas via asyncpg. Sem execução de código arbitrário nos plugins. Prompts e schemas são read-only — carregados no registro do pipeline, não em runtime.

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.12 |
| API | FastAPI |
| Database | PostgreSQL 16 + pgvector |
| DB Driver | asyncpg (async) |
| HTTP Client | httpx (async) |
| LLM SDK | openai (async) |
| Models | Pydantic v2 |
| Config | pydantic-settings |
| PDF | PyMuPDF (fitz) |
| HTML | BeautifulSoup4 |
| Schema | jsonschema |
| Config files | PyYAML |
| Migrations | Alembic + SQLAlchemy (models only) |
| Testing | pytest + pytest-asyncio + testcontainers |
| Deploy | Docker (python:3.12-slim) + Docker Swarm + Traefik |

## Development Workflow

1. Constitution (este arquivo) — princípios invioláveis
2. `/speckit.specify` — spec por feature
3. `/speckit.plan` — plano técnico + data model + contracts
4. `/speckit.tasks` — decomposição em tasks
5. `/speckit.implement` — execução guiada
6. QA Gate — code-reviewer + sentinel + devops + PM

## Pipeline VotoLimpo — Arquitetura E2E

### Fluxo Completo

```
News Collector (NC)                    Processing Engine (PE)
───────────────────                    ────────────────────
1. Coleta artigos (Crawl4/RSS)
2. Armazena em news_collector.articles
3. Envia batch ao PE via HTTP ──────►  4. Recebe items no pipeline
                                       5. Dedup (content hash)
                                       6. LLM Analysis (gpt-4.1-mini):
                                          - veracity_score (0.0-1.0)
                                          - veracity_signals (6 componentes)
                                          - politicians (name, party, role)
                                          - keywords, summary, severity
                                       7. Validate (JSON Schema)
                                       8. Sink PostgreSQL:
                                          - votolimpo.articles (upsert)
                                          - votolimpo.article_matches
                                          - votolimpo.news_clusters
9. NC lê processing_output ◄────────  (webhook callback ou polling)
10. Backend extrai campos PE:
    - score = veracity_score × 10
    - score_breakdown = signals × 10
    - politicians = lista de nomes
    - llm_output = processing_output
11. Frontend consome via API REST
```

### Bancos de Dados

| Banco | Usado por | Schema | Conteúdo |
|-------|-----------|--------|----------|
| `processing_engine` | PE | `processing_engine` | Jobs, items, costs, pipelines, cache, llm_call_log |
| `news_collector` | NC | `news_collector` | Sources, articles, entities, schedules, pe_jobs |
| `votolimpo` | PE (sink) | `votolimpo` | Artigos analisados, article_matches, news_clusters |

**Host compartilhado**: `pe-postgres:5432` (Docker Swarm overlay network `pe-net`)

### Schema Naming (REGRA CRÍTICA)

O schema do sink VotoLimpo é `votolimpo` (SEM underscore). O nome antigo `voto_limpo` (com underscore) estava incorreto e foi corrigido em 2026-09-13. NUNCA usar `voto_limpo` em código novo.

### Conversão de Scores (REGRA CRÍTICA)

PE produz scores no range **0.0 a 1.0**. O frontend espera range **0 a 10**. A conversão acontece no backend do NC (`populate_from_processing_output()`), multiplicando por 10 e arredondando para 1 casa decimal. NUNCA alterar o range do PE.

### Pipeline ID

O pipeline VotoLimpo está registrado como `voto-limpo-news-analysis` com ID `a09099b0-147e-42ab-831b-7b3c1e46bdc1`. Este ID é configurado no NC via env var `PROCESSING_ENGINE_PIPELINE_ID`.

## Dependências Externas e Credenciais

### OpenAI API Key (CRÍTICA)

O PE depende de uma OpenAI API key válida para processar items via LLM. Sem ela, TODOS os jobs falham com HTTP 401.

| Item | Valor |
|------|-------|
| Env var no PE | `OPENAI_API_KEY` |
| Fonte de verdade | `/cortex/secrets/projects/processing-engine.env` |
| Onde configurar | Portainer → Stack 345 → Environment variables |
| Modelo default | `gpt-4.1-mini` |

**Regra**: Ao atualizar a key no Cortex, SEMPRE atualizar também no Portainer (stack 345). Key expirada = pipeline 100% parado.

### Infraestrutura (Docker Swarm)

| Componente | Stack ID | Endpoint | URL Pública |
|------------|----------|----------|-------------|
| Processing Engine | 345 | 4 (Contabo) | `https://processing-engine.digital-ai.tech` |
| News Collector | 347 | 4 (Contabo) | `https://api.news-collector.digital-ai.tech` |
| pe-postgres | (dentro do stack 345) | — | Interno via `pe-net` |

### Autenticação entre serviços

| De → Para | Header | Env var (origem) |
|-----------|--------|------------------|
| Cliente → PE | `x-api-key` | `PE_API_KEY` |
| Cliente → NC | `Authorization: Bearer` | `NC_API_TOKEN` |
| NC → PE | `x-api-key` | `PROCESSING_ENGINE_TOKEN` (no NC) |

## CI/CD

- **Repo**: `DIGITAL-AI-TECH/votolimpo` (path: `processing-engine/`)
- **Trigger**: Push to `main` com mudanças em `processing-engine/**`
- **Steps**: Notify → Lint (ruff) → Test (pytest) → Build (Docker) → Deploy (Portainer API)
- **Registry**: `registry.digital-ai.tech/processing-engine`
- **Notificações**: Discord via n8n webhook

## Governance

- Constitution supersede todas as decisões de design
- Princípio II (Anti-Reprocessamento) é NON-NEGOTIABLE — não pode ser relaxado
- Princípio V (Stack Mínima) só pode ser violado com justificativa escrita aprovada pelo owner
- Amendments requerem: documentação, justificativa, migração

**Version**: 1.1.0 | **Ratified**: 2026-09-06 | **Last Amended**: 2026-09-13
