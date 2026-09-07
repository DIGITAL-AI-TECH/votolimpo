# Implementation Plan: Pool Architecture

**Branch**: `002-processing-engine` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)
**Input**: Desacoplar coleta de dados do processamento via pool centralizada
**Architecture**: [architecture.md](architecture.md) | **Data Model**: [data-model.md](data-model.md)

## Summary

Adicionar camada de ingestão desacoplada (pool) ao Processing Engine. N coletores independentes depositam dados via REST API, um Auto-Batcher consome da pool e cria jobs automaticamente. O engine existente (worker, orchestrator, plugins) permanece inalterado. Backward compatible — POST /v1/jobs continua funcionando.

## Technical Context

**Language/Version**: Python 3.12
**Framework**: FastAPI + asyncpg (existente)
**Database**: PostgreSQL 16 (schema `processing_engine`, existente)
**New table**: `pool` (buffer de ingestão)
**New service**: Auto-Batcher (background task asyncio)
**New endpoints**: 3 (pool ingest, pool ingest/single, pool status)
**Existing code modified**: main.py (~10 linhas), config.py (~2 campos)
**Existing code NOT modified**: worker.py, orchestrator.py, plugins/*, api/jobs.py, sql/*, models/*

## Constitution Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Agnóstico por Design | PASS | Pool recebe dados de qualquer coletor. Engine continua 100% agnóstico de coleta. |
| II. Anti-Reprocessamento | PASS | Pool Dedup (url_hash barreira rápida) + Pipeline Dedup existente (content_hash + semântico). |
| III. Custo Controlado | PASS | Zero chamadas LLM na pool. Budget limits inalterados. |
| IV. Plugin-First | PASS | Pool não altera sistema de plugins. Auto-Batcher é service interno. |
| V. Stack Mínima | PASS | Pool é tabela PostgreSQL. Sem Redis, sem fila externa. SKIP LOCKED reaproveitado. |
| VI. Schema First | PASS | Migration Alembic. Pydantic models. OpenAPI contract. |
| VII. Idempotência Total | PASS | Pool Dedup garante idempotência na ingestão. Jobs continuam com idempotency_key. |
| VIII. Observabilidade | PASS | source_id + batch_ref para rastreio. GET /v1/pool/status para monitoring. |
| IX. Testabilidade | PASS | 3 camadas: unit + E2E + contract. testcontainers com PostgreSQL real. |
| X. Segurança | PASS | Mesma API key. Queries parametrizadas. Sem execução de código. |

## File Whitelist

### Novos arquivos (criar)

```
processing-engine/
├── alembic/versions/
│   └── 012_create_pool.py              # Migration: tabela pool + indexes
├── app/
│   ├── api/
│   │   └── pool.py                     # Endpoints: ingest, ingest/single, status
│   ├── models/
│   │   └── pool.py                     # Pydantic models: PoolIngestRequest, PoolItem, PoolStatus
│   ├── services/
│   │   └── auto_batcher.py             # Background task: consome pool → cria jobs
│   └── sql/
│       └── pool.py                     # SQL queries: insert, claim, status, dedup check
├── db_models/
│   └── pool.py                         # SQLAlchemy model (para migrations)
└── tests/
    ├── unit/
    │   ├── test_pool_api.py            # Unit tests da Pool API
    │   └── test_auto_batcher.py        # Unit tests do Auto-Batcher
    ├── e2e/
    │   └── test_pool_flow.py           # E2E: coletor → pool → job → resultado
    └── contract/
        └── test_pool_contracts.py      # Contract tests: shapes dos endpoints da pool
```

### Arquivos existentes modificados (editar)

```
processing-engine/
├── app/
│   ├── main.py                         # + registrar router da pool + iniciar auto-batcher no lifespan
│   └── config.py                       # + BATCHER_POLL_INTERVAL_SECONDS, BATCHER_DEFAULT_BATCH_SIZE
└── specs/002-pool-architecture/
    └── contracts/openapi.yaml          # + 3 endpoints da pool
```

### Arquivos NÃO tocados

```
app/worker.py, app/services/orchestrator.py, app/services/cost_tracker.py,
app/services/rate_limiter.py, app/services/callback.py, app/api/jobs.py,
app/api/pipelines.py, app/api/costs.py, app/api/stats.py, app/api/health.py,
app/sql/jobs.py, app/sql/items.py, app/sql/cache.py, app/sql/costs.py,
app/sql/pipelines.py, app/sql/stats.py, app/models/job.py, app/models/item.py,
app/models/pipeline.py, app/models/cost.py, app/models/stats.py, app/models/log.py,
app/plugins/*, db_models/job.py, db_models/item.py, db_models/pipeline.py,
db_models/processing_log.py, db_models/llm_call_log.py, db_models/cache_entry.py,
db_models/model_pricing.py, alembic/versions/001-011_*.py,
Dockerfile, docker-compose.yml, docker-stack.yml
```

---

## Implementation Phases

### Phase A — Database & Models (Foundation)

**Objetivo**: Tabela pool no banco + models Pydantic + SQLAlchemy

**Arquivos**:
- `alembic/versions/012_create_pool.py` — Migration completa (tabela + 5 indexes)
- `db_models/pool.py` — SQLAlchemy model para Alembic
- `app/models/pool.py` — Pydantic models (PoolIngestRequest, PoolIngestItem, PoolIngestResponse, PoolStatusResponse, PoolSingleIngestRequest, PoolSingleIngestResponse)
- `app/sql/pool.py` — SQL queries (insert_pool_items, check_url_hash_exists, claim_pending_items, get_pool_status)

**Validação**: Migration aplica sem erro. Models importam sem erro.

### Phase B — Pool API (3 endpoints)

**Objetivo**: Endpoints REST para ingestão e consulta

**Arquivos**:
- `app/api/pool.py` — Router com 3 endpoints:
  - `POST /v1/pool/ingest` (FR-101 a FR-107)
  - `POST /v1/pool/ingest/single` (FR-131)
  - `GET /v1/pool/status` (FR-121, FR-122)
- `app/main.py` — Registrar router da pool

**Lógica do ingest**:
1. Validar pipeline_id existe (404 se não)
2. Computar url_hash (SHA-256) para cada item com source_url
3. Check dedup: url_hash já existe para mesmo pipeline_id?
4. INSERT itens aceitos com status=pending (transação atômica)
5. Retornar accepted/rejected com detalhes

**Validação**: Endpoints respondem. Pipeline inexistente retorna 404. Duplicatas são rejeitadas.

### Phase C — Auto-Batcher (Background Service)

**Objetivo**: Background task que consome pool e cria jobs

**Arquivos**:
- `app/services/auto_batcher.py` — Classe AutoBatcher com:
  - `start()` — inicia loop asyncio
  - `stop()` — para graciosamente
  - `_batch_cycle()` — um ciclo de claim + criação de jobs
  - `_claim_items()` — SELECT FOR UPDATE SKIP LOCKED
  - `_create_job_from_pool_item()` — INSERT em jobs + items
- `app/main.py` — Iniciar auto-batcher no lifespan (startup/shutdown)
- `app/config.py` — `BATCHER_POLL_INTERVAL_SECONDS` (default 5), `BATCHER_DEFAULT_BATCH_SIZE` (default 50)

**Lógica do batch_cycle**:
1. Listar pipelines com itens pending (SELECT DISTINCT pipeline_id)
2. Para cada pipeline: claim N itens com SKIP LOCKED
3. Para cada item claimed: criar 1 job + 1 item (v1: granularidade 1:1)
4. Marcar item da pool como claimed com job_id e claimed_at
5. Log: "Created N jobs for pipeline X"

**Validação**: Itens pending são consumidos. Jobs são criados. Worker processa normalmente.

### Phase D — Testes (3 camadas)

**Objetivo**: Cobertura completa conforme política de testes

**Arquivos**:
- `tests/unit/test_pool_api.py` — Unit tests:
  - Ingest com items válidos
  - Ingest com pipeline inexistente (404)
  - Dedup por url_hash (rejeição)
  - Batch misto (aceitos + rejeitados)
  - Validação de campos obrigatórios
  - Single ingest (aceito + duplicado)
  - Pool status (com e sem itens)
- `tests/unit/test_auto_batcher.py` — Unit tests:
  - Claim de itens pending
  - Criação de jobs 1:1
  - Pipeline com auto_batch=false ignorado
  - Ciclo idle (zero pendentes)
  - SKIP LOCKED (simulação de concorrência)
- `tests/e2e/test_pool_flow.py` — E2E:
  - Coletor → pool → auto-batcher → job → worker → resultado no sink
  - Batch de 10 itens → 10 jobs → todos completados
  - Duplicata rejeitada na pool → não gera job
- `tests/contract/test_pool_contracts.py` — Contract tests:
  - Shape de PoolIngestResponse (accepted, rejected, pool_ids, rejections)
  - Shape de PoolSingleIngestResponse (pool_id, status)
  - Shape de PoolStatusResponse (pending_total, by_pipeline)
  - Todos os campos obrigatórios presentes e com tipos corretos

**Validação**: `pytest -v` — todos passam. 173 testes existentes continuam passando.

### Phase E — OpenAPI Contract & Documentation

**Objetivo**: Atualizar contratos e documentação

**Arquivos**:
- `specs/002-pool-architecture/contracts/openapi.yaml` — 3 novos endpoints + schemas
- `specs/002-pool-architecture/quickstart.md` — Guia de uso da pool para coletores

**Validação**: OpenAPI válido. Exemplos de curl funcionam.

---

## Diagrama de Sequência

```
Coletor              Pool API           Pool (tabela)      Auto-Batcher        Jobs          Worker
  |                    |                    |                   |                 |              |
  |-- POST /ingest --->|                    |                   |                 |              |
  |                    |-- check pipeline ->|                   |                 |              |
  |                    |-- check url_hash ->|                   |                 |              |
  |                    |-- INSERT pending ->|                   |                 |              |
  |<-- 201 accepted --|                    |                   |                 |              |
  |                    |                    |                   |                 |              |
  |                    |                    |  (poll 5s)        |                 |              |
  |                    |                    |<- SKIP LOCKED ----|                 |              |
  |                    |                    |-- items --------->|                 |              |
  |                    |                    |                   |-- INSERT job -->|              |
  |                    |                    |                   |-- INSERT item ->|              |
  |                    |                    |<- UPDATE claimed -|                 |              |
  |                    |                    |                   |                 |              |
  |                    |                    |                   |                 | (poll 1s)    |
  |                    |                    |                   |                 |<- SKIP LOCK -|
  |                    |                    |                   |                 |-- job ------>|
  |                    |                    |                   |                 |         Orchestrator
  |                    |                    |                   |                 |         (inalterado)
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-Batcher crash perde itens | Baixo — itens ficam pending, próximo ciclo recupera | SKIP LOCKED + status transition atômica |
| Pool table cresce indefinidamente | Médio — performance degrada com milhões de rows | Indexes parciais (WHERE status='pending') + cleanup futuro |
| Dedup por url_hash falha (URL muda) | Baixo — Pipeline Dedup por content_hash pega na segunda camada | Duas camadas complementares |
| Auto-Batcher muito lento para volume alto | Baixo — 10K items/dia é trivial para PostgreSQL | Configurável batch_size + interval |
| Backward compatibility quebra | Alto — integrações existentes param de funcionar | Zero mudança em endpoints existentes + 173 testes como rede de segurança |
