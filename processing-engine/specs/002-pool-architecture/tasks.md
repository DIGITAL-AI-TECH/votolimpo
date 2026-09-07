# Tasks: Pool Architecture

**Feature**: 002-pool-architecture | **Plan**: [plan.md](plan.md) | **Date**: 2026-09-07

---

## Phase A — Database & Models (Foundation)

### Task A1: Migration 012 — Tabela pool + indexes
- **Phase**: A
- **Priority**: P1
- **blockedBy**: —
- **File**: `alembic/versions/012_create_pool.py`
- **Description**: Criar migration Alembic com:
  - Tabela `processing_engine.pool` (id, pipeline_id FK, source_url, content, content_type, metadata, url_hash, content_hash, status CHECK, priority, source_id, batch_ref, job_id FK, created_at, claimed_at)
  - Enum/CHECK para status: pending, claimed, duplicate_rejected, error
  - 5 indexes: idx_pool_pending, idx_pool_url_hash, idx_pool_content_hash, idx_pool_source, idx_pool_job_id
  - Downgrade: DROP TABLE
- **Acceptance**: `alembic upgrade head` sem erro. Tabela existe com todos os campos e indexes.

### Task A2: SQLAlchemy model — Pool
- **Phase**: A
- **Priority**: P1
- **blockedBy**: —
- **File**: `db_models/pool.py`
- **Description**: Criar modelo SQLAlchemy para a tabela pool. Incluir no `db_models/__init__.py`.
- **Acceptance**: Importa sem erro. Alembic reconhece o model.

### Task A3: Pydantic models — Pool
- **Phase**: A
- **Priority**: P1
- **blockedBy**: —
- **File**: `app/models/pool.py`
- **Description**: Criar modelos Pydantic:
  - `PoolIngestItem` — source_url (optional), content (optional), content_type (default "text/plain"), metadata (default {})
  - `PoolIngestRequest` — pipeline_id (UUID), source_id (optional), batch_ref (optional), priority (default 0), items (list[PoolIngestItem], min 1, max 500)
  - `PoolIngestResponse` — accepted (int), rejected (int), pool_ids (list[UUID]), rejections (list[PoolRejection])
  - `PoolRejection` — index (int), reason (str), existing_pool_id (UUID optional)
  - `PoolSingleIngestRequest` — pipeline_id, source_id, source_url, content, content_type, metadata
  - `PoolSingleIngestResponse` — pool_id (UUID optional), status ("accepted" | "duplicate"), existing_pool_id (UUID optional)
  - `PoolStatusResponse` — pending_total (int), by_pipeline (list[PoolPipelineStatus])
  - `PoolPipelineStatus` — pipeline_id, pipeline_name, pending (int), oldest_pending (datetime optional)
  - Validator: pelo menos `content` ou `source_url` obrigatório em cada item
- **Acceptance**: Models importam. Validator rejeita item sem content nem source_url.

### Task A4: SQL queries — Pool
- **Phase**: A
- **Priority**: P1
- **blockedBy**: —
- **File**: `app/sql/pool.py`
- **Description**: Criar módulo SQL com funções assíncronas:
  - `insert_pool_items(conn, pipeline_id, items, source_id, batch_ref, priority)` — INSERT com ON CONFLICT para dedup, retorna aceitos e rejeitados
  - `check_url_hash_exists(conn, url_hash, pipeline_id)` — EXISTS check
  - `claim_pending_items(conn, pipeline_id, limit)` — SELECT FOR UPDATE SKIP LOCKED + UPDATE status=claimed
  - `get_pool_status(conn)` — Aggregate por pipeline com COUNT e MIN(created_at)
  - `get_pending_pipeline_ids(conn)` — DISTINCT pipeline_id com itens pending
- **Acceptance**: Queries executam sem erro contra PostgreSQL de teste.

---

## Phase B — Pool API (3 endpoints)

### Task B1: Pool router — POST /v1/pool/ingest
- **Phase**: B
- **Priority**: P1
- **blockedBy**: A1, A3, A4
- **File**: `app/api/pool.py`
- **Description**: Endpoint principal:
  1. Validar pipeline_id existe (SELECT em pipelines, 404 se não)
  2. Computar url_hash (hashlib.sha256) para itens com source_url
  3. Computar content_hash para itens com content
  4. Check dedup em batch: url_hash já existe para mesmo pipeline_id
  5. INSERT itens aceitos em transação atômica
  6. Retornar PoolIngestResponse com accepted/rejected/pool_ids/rejections
- **Acceptance**: 201 com itens válidos. 404 com pipeline inexistente. Duplicatas rejeitadas com detalhes.

### Task B2: Pool router — POST /v1/pool/ingest/single
- **Phase**: B
- **Priority**: P2
- **blockedBy**: B1
- **File**: `app/api/pool.py` (mesmo arquivo)
- **Description**: Atalho para 1 item:
  1. Reutilizar lógica de B1 internamente
  2. Retornar 201 (accepted) ou 409 (duplicate)
- **Acceptance**: 201 para item novo. 409 para duplicata com existing_pool_id.

### Task B3: Pool router — GET /v1/pool/status
- **Phase**: B
- **Priority**: P2
- **blockedBy**: A1, A4
- **File**: `app/api/pool.py` (mesmo arquivo)
- **Description**: Status da pool:
  1. Query aggregate por pipeline
  2. Retornar PoolStatusResponse
- **Acceptance**: Retorna contagens corretas. Pool vazia retorna pending_total: 0.

### Task B4: Registrar router no main.py
- **Phase**: B
- **Priority**: P1
- **blockedBy**: B1
- **File**: `app/main.py`
- **Description**: Adicionar `app.include_router(pool_router, prefix="/v1")` no FastAPI app.
- **Acceptance**: Endpoints acessíveis. Swagger mostra os 3 novos endpoints.

---

## Phase C — Auto-Batcher (Background Service)

### Task C1: Auto-Batcher service
- **Phase**: C
- **Priority**: P1
- **blockedBy**: A4
- **File**: `app/services/auto_batcher.py`
- **Description**: Classe `AutoBatcher` com:
  - `__init__(pool, config)` — recebe connection pool e settings
  - `start()` — inicia loop asyncio.create_task
  - `stop()` — seta flag + cancela task
  - `_run_loop()` — while running: await _batch_cycle() + sleep(interval)
  - `_batch_cycle()` — para cada pipeline com itens pending: claim + criar jobs
  - `_claim_and_create_jobs(pipeline_id)` — SKIP LOCKED + INSERT job + INSERT item + UPDATE pool claimed
  - Logging: itens claimed, jobs criados, erros
- **Acceptance**: Itens pending são consumidos. Jobs aparecem na tabela jobs. Worker processa normalmente.

### Task C2: Config settings do Batcher
- **Phase**: C
- **Priority**: P1
- **blockedBy**: —
- **File**: `app/config.py`
- **Description**: Adicionar campos:
  - `BATCHER_POLL_INTERVAL_SECONDS: int = 5`
  - `BATCHER_DEFAULT_BATCH_SIZE: int = 50`
  - `BATCHER_ENABLED: bool = True` (para desabilitar em testes se necessário)
- **Acceptance**: Settings carregam de env vars.

### Task C3: Integrar Auto-Batcher no lifespan
- **Phase**: C
- **Priority**: P1
- **blockedBy**: C1, C2
- **File**: `app/main.py`
- **Description**: No lifespan do FastAPI:
  - `startup`: criar AutoBatcher e chamar `start()` (se BATCHER_ENABLED e ENGINE_ROLE != "api")
  - `shutdown`: chamar `stop()` e aguardar graceful shutdown
- **Acceptance**: Auto-Batcher inicia com o app. Para graciosamente no shutdown.

---

## Phase D — Testes (3 camadas)

### Task D1: Unit tests — Pool API
- **Phase**: D
- **Priority**: P1
- **blockedBy**: B1, B2, B3
- **File**: `tests/unit/test_pool_api.py`
- **Description**: Testes com mocks:
  - test_ingest_valid_items — 5 itens aceitos
  - test_ingest_invalid_pipeline — 404
  - test_ingest_duplicate_url — rejeitado com detalhes
  - test_ingest_mixed_accepted_rejected — batch misto
  - test_ingest_missing_content_and_url — 422
  - test_ingest_max_500_items — 500 aceitos
  - test_ingest_over_500_items — 422
  - test_single_ingest_accepted — 201
  - test_single_ingest_duplicate — 409
  - test_pool_status_with_items — contagens corretas
  - test_pool_status_empty — pending_total: 0
- **Acceptance**: Todos passam.

### Task D2: Unit tests — Auto-Batcher
- **Phase**: D
- **Priority**: P1
- **blockedBy**: C1
- **File**: `tests/unit/test_auto_batcher.py`
- **Description**: Testes com mocks:
  - test_claim_pending_items — SKIP LOCKED retorna itens
  - test_create_job_from_pool_item — job criado com dados corretos
  - test_batch_cycle_multiple_pipelines — jobs separados por pipeline
  - test_batch_cycle_no_pending — idle sem erro
  - test_auto_batch_false_ignored — pipeline com auto_batch=false ignorado
  - test_stop_graceful — shutdown sem perder itens
- **Acceptance**: Todos passam.

### Task D3: E2E tests — Pool flow completo
- **Phase**: D
- **Priority**: P1
- **blockedBy**: B4, C3
- **File**: `tests/e2e/test_pool_flow.py`
- **Description**: Testes com PostgreSQL real (testcontainers):
  - test_pool_to_job_complete_flow — ingest → pool → batcher → job → worker → resultado
  - test_pool_batch_10_items — 10 itens → 10 jobs → todos completed
  - test_pool_duplicate_rejected — duplicata na pool não gera job
  - test_pool_status_reflects_pending — status mostra itens corretos
- **Acceptance**: Todos passam com testcontainers.

### Task D4: Contract tests — Pool response shapes
- **Phase**: D
- **Priority**: P1
- **blockedBy**: A3
- **File**: `tests/contract/test_pool_contracts.py`
- **Description**: Validar shapes Pydantic:
  - test_pool_ingest_response_shape — accepted, rejected, pool_ids são tipos corretos
  - test_pool_single_response_shape — pool_id, status presentes
  - test_pool_status_response_shape — pending_total int, by_pipeline é lista
  - test_pool_rejection_shape — index int, reason str
- **Acceptance**: Todos passam.

### Task D5: Verificar testes existentes (regressão)
- **Phase**: D
- **Priority**: P1
- **blockedBy**: B4, C3
- **File**: (nenhum novo — roda suite existente)
- **Description**: Executar `pytest tests/unit/ tests/contract/` e verificar que os 173 testes existentes continuam passando sem modificação.
- **Acceptance**: 173/173 passando + novos testes da pool.

---

## Phase E — Contracts & Documentation

### Task E1: OpenAPI contract
- **Phase**: E
- **Priority**: P2
- **blockedBy**: B1, B2, B3
- **File**: `specs/002-pool-architecture/contracts/openapi.yaml`
- **Description**: Adicionar schemas e endpoints da pool ao OpenAPI 3.1:
  - POST /v1/pool/ingest + request/response schemas
  - POST /v1/pool/ingest/single + request/response schemas
  - GET /v1/pool/status + response schema
- **Acceptance**: YAML válido. Schemas correspondem aos Pydantic models.

### Task E2: Quickstart guide
- **Phase**: E
- **Priority**: P2
- **blockedBy**: B1
- **File**: `specs/002-pool-architecture/quickstart.md`
- **Description**: Guia prático para coletores:
  - Como enviar dados para a pool (curl examples)
  - Como consultar status
  - Exemplos por tipo de coletor (scraper, file importer, webhook)
- **Acceptance**: Exemplos de curl funcionam contra o engine rodando.

---

## Summary

| Phase | Tasks | Arquivos novos | Arquivos editados |
|-------|-------|----------------|-------------------|
| A — Foundation | A1-A4 | 4 | 0 |
| B — Pool API | B1-B4 | 1 | 1 (main.py) |
| C — Auto-Batcher | C1-C3 | 1 | 2 (main.py, config.py) |
| D — Testes | D1-D5 | 4 | 0 |
| E — Docs | E1-E2 | 2 | 0 |
| **Total** | **18** | **12** | **2** |

## Dependency Graph

```
A1 (migration) ──────> B1 (ingest) ──────> B4 (main.py) ──> D3 (E2E)
A2 (sqlalchemy)        B2 (single) ──┘                      D5 (regressão)
A3 (pydantic) ───────> B3 (status) ──┘
A4 (sql) ────────────> C1 (batcher) ──> C3 (lifespan) ──> D3 (E2E)
                       C2 (config) ──┘                     D5 (regressão)
A3 (pydantic) ──────────────────────────────────> D4 (contract)
B1 ──────────> D1 (unit pool api)
C1 ──────────> D2 (unit batcher)
B1, B2, B3 ──> E1 (openapi)
B1 ──────────> E2 (quickstart)
```

## Critical Path

```
A1 → A4 → B1 → B4 → C1 → C3 → D3 → D5
```

Tempo estimado no critical path: ~12h de implementação.
