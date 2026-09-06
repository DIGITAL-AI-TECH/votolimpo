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

## Governance

- Constitution supersede todas as decisões de design
- Princípio II (Anti-Reprocessamento) é NON-NEGOTIABLE — não pode ser relaxado
- Princípio V (Stack Mínima) só pode ser violado com justificativa escrita aprovada pelo owner
- Amendments requerem: documentação, justificativa, migração

**Version**: 1.0.0 | **Ratified**: 2026-09-06 | **Last Amended**: 2026-09-06
