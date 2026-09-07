# Feature Specification: Pool Architecture — Ingestão Desacoplada

**Feature Branch**: `002-processing-engine`
**Created**: 2026-09-07
**Status**: Approved
**Input**: Desacoplar coleta de dados do processamento — N coletores independentes depositam dados em uma pool centralizada, e o engine consome e processa conforme o pipeline configurado
**Architecture**: [architecture.md](architecture.md)

## Decisões Validadas pelo Owner (2026-09-07)

| # | Decisão | Resultado |
|---|---------|-----------|
| D1 | Granularidade pool→job | **1 item = 1 job** na v1 (batch grouping como evolução futura) |
| D2 | API da pool | **REST** (`POST /v1/pool`) no engine |
| D3 | Banco | **Mesmo banco** do engine (Stack Mínima) |
| D4 | Pipeline inválido | **Rejeitar** na hora (fail fast) |
| D5 | Naming | **pool** |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Depositar Itens na Pool via Coletor (Priority: P1)

Um coletor externo (scraper, file importer, webhook n8n, ou qualquer sistema) deposita dados brutos na pool do Processing Engine via REST API. O coletor NÃO cria jobs — apenas informa o `pipeline_id` e o conteúdo. A pool faz dedup imediato por `url_hash` e rejeita duplicatas.

**Why this priority**: É o contrato fundamental da pool — sem ele, não existe desacoplamento entre coleta e processamento.

**Independent Test**: Pode ser testado enviando itens via POST /v1/pool/ingest e verificando que entram na pool com status `pending`.

**Acceptance Scenarios**:

1. **Given** um pipeline "votolimpo-analyzer" registrado, **When** um coletor envia POST /v1/pool/ingest com 5 itens HTML, **Then** a API retorna 201 com `accepted: 5` e todos os itens ficam com status `pending` na pool.
2. **Given** um item com `source_url` que já existe na pool (mesmo `pipeline_id`, status != `duplicate_rejected`), **When** o coletor tenta enviar novamente, **Then** a API retorna o item como `rejected` com `reason: "duplicate_url"` e `existing_pool_id`.
3. **Given** um `pipeline_id` inexistente, **When** o coletor envia POST /v1/pool/ingest, **Then** a API retorna 404 com mensagem "Pipeline not found" (fail fast).
4. **Given** um batch de 10 itens onde 3 são duplicatas, **When** enviados via POST /v1/pool/ingest, **Then** a API retorna `accepted: 7, rejected: 3` com detalhes de cada rejeição.
5. **Given** nenhum campo `content` nem `source_url` em um item, **When** enviado, **Then** a API retorna 422 com erro de validação (pelo menos um é obrigatório).

---

### User Story 2 - Auto-Batcher Cria Jobs a partir da Pool (Priority: P1)

Um background task (Auto-Batcher) consome itens `pending` da pool periodicamente e cria jobs automaticamente no engine. O batcher usa `FOR UPDATE SKIP LOCKED` para evitar concorrência. Na v1, cada item da pool gera 1 job individual.

**Why this priority**: Sem o auto-batcher, os itens ficam parados na pool. É o segundo elo essencial do desacoplamento.

**Independent Test**: Pode ser testado depositando itens na pool e verificando que jobs são criados automaticamente após o intervalo configurado.

**Acceptance Scenarios**:

1. **Given** 10 itens `pending` na pool para o pipeline "votolimpo-analyzer", **When** o auto-batcher executa um ciclo, **Then** 10 jobs são criados (1:1), cada item da pool é marcado como `claimed` com referência ao `job_id`, e cada job tem status `queued`.
2. **Given** itens pendentes de 3 pipelines diferentes, **When** o auto-batcher executa, **Then** cria jobs separados por `pipeline_id` (nunca mistura pipelines em um job).
3. **Given** um pipeline com `pool.auto_batch: false`, **When** itens são depositados na pool para esse pipeline, **Then** o auto-batcher os ignora (processamento somente via POST /v1/jobs direto).
4. **Given** zero itens pendentes na pool, **When** o auto-batcher executa, **Then** nenhum job é criado e nenhum erro ocorre (idle gracioso).
5. **Given** dois auto-batchers rodando simultaneamente (horizontal scaling futuro), **When** ambos executam, **Then** SKIP LOCKED garante que cada item é processado por apenas um batcher (sem duplicação de jobs).

---

### User Story 3 - Consultar Status da Pool (Priority: P2)

Um operador ou dashboard consulta o status da pool para monitorar filas pendentes, volume por pipeline, e saúde geral da ingestão.

**Why this priority**: Observabilidade é essencial para operações, mas não bloqueia o fluxo core.

**Independent Test**: Pode ser testado depositando itens na pool e consultando GET /v1/pool/status.

**Acceptance Scenarios**:

1. **Given** 35 itens pendentes do pipeline A e 12 do pipeline B, **When** GET /v1/pool/status é chamado, **Then** retorna `pending_total: 47` com breakdown por pipeline incluindo nome, contagem e timestamp do item mais antigo.
2. **Given** pool vazia, **When** GET /v1/pool/status é chamado, **Then** retorna `pending_total: 0` e `by_pipeline: []`.

---

### User Story 4 - Depositar Item Único via Webhook (Priority: P2)

Um webhook (n8n, Zapier, ou sistema externo) deposita um único item na pool via endpoint simplificado (`/v1/pool/ingest/single`). Útil para integrações que enviam um item por vez.

**Why this priority**: Facilita integrações simples sem exigir payload com array. Complementar à US1.

**Independent Test**: Pode ser testado enviando POST /v1/pool/ingest/single e verificando que o item entra na pool.

**Acceptance Scenarios**:

1. **Given** um pipeline válido, **When** POST /v1/pool/ingest/single com `pipeline_id`, `content` e `source_url`, **Then** retorna 201 com `pool_id` e `status: "accepted"`.
2. **Given** um `source_url` duplicado, **When** POST /v1/pool/ingest/single, **Then** retorna 409 com `status: "duplicate"` e `existing_pool_id`.

---

### User Story 5 - Backward Compatibility com POST /v1/jobs (Priority: P1)

Sistemas que já usam POST /v1/jobs continuam funcionando sem alteração. A pool é um canal ADICIONAL de entrada — não substitui a API de jobs existente.

**Why this priority**: Não pode quebrar integrações existentes. Backward compatibility é inegociável.

**Independent Test**: Executar a suíte de testes existente (173 testes) e verificar que todos passam sem alteração.

**Acceptance Scenarios**:

1. **Given** um sistema usando POST /v1/jobs diretamente, **When** a pool é adicionada ao engine, **Then** POST /v1/jobs continua criando jobs normalmente, sem mudança no payload ou na resposta.
2. **Given** a suíte de testes existente (173 testes), **When** executada após implementação da pool, **Then** todos os 173 testes passam sem modificação.

---

## Functional Requirements

### Pool Ingest (FR-101 a FR-107)

| ID | Requirement |
|----|-------------|
| FR-101 | `POST /v1/pool/ingest` aceita 1 a 500 itens por request com `pipeline_id` obrigatório |
| FR-102 | Cada item requer pelo menos `content` OU `source_url` (pelo menos um) |
| FR-103 | Dedup imediato na pool por `url_hash` (mesmo `pipeline_id`) — rejeita duplicatas com detalhes |
| FR-104 | Pipeline inexistente retorna 404 (fail fast, não aceita como "unroutable") |
| FR-105 | `source_id` e `batch_ref` opcionais para rastreabilidade do coletor |
| FR-106 | `priority` (int, default 0) controla ordem de consumo (maior = primeiro) |
| FR-107 | Operação atômica: todos os itens aceitos entram em uma transação ou nenhum |

### Auto-Batcher (FR-111 a FR-116)

| ID | Requirement |
|----|-------------|
| FR-111 | Background task com poll periódico configurável (`BATCHER_POLL_INTERVAL_SECONDS`, default 5s) |
| FR-112 | Consome itens `pending` por pipeline usando `FOR UPDATE SKIP LOCKED` |
| FR-113 | Na v1: 1 item da pool = 1 job individual (granularidade 1:1) |
| FR-114 | Cria job com `pipeline_id` do item e move conteúdo para tabela `items` existente |
| FR-115 | Marca item da pool como `claimed` com referência ao `job_id` criado |
| FR-116 | Configurável por pipeline: `pool.auto_batch` (default true), `pool.batch_size`, `pool.batch_interval_seconds` |

### Pool Status (FR-121 a FR-122)

| ID | Requirement |
|----|-------------|
| FR-121 | `GET /v1/pool/status` retorna total de pendentes e breakdown por pipeline |
| FR-122 | Inclui `oldest_pending` timestamp por pipeline para detectar backlogs |

### Pool Single Ingest (FR-131)

| ID | Requirement |
|----|-------------|
| FR-131 | `POST /v1/pool/ingest/single` — atalho para 1 item sem wrapper de array, retorna 409 em duplicata |

### Backward Compatibility (FR-141)

| ID | Requirement |
|----|-------------|
| FR-141 | `POST /v1/jobs` continua funcionando sem alteração — pool é canal adicional, não substituto |

---

## IN-SCOPE

- Tabela `pool` no PostgreSQL com indexes para SKIP LOCKED e dedup
- 3 endpoints REST: `POST /v1/pool/ingest`, `POST /v1/pool/ingest/single`, `GET /v1/pool/status`
- Auto-Batcher como background task (asyncio, igual padrão do Worker)
- Dedup na pool por url_hash (barreira rápida pré-processamento)
- Configuração de pool por pipeline via YAML (auto_batch, batch_size, interval)
- Migration Alembic para tabela pool + indexes
- Testes: unitários, E2E, contract (3 camadas obrigatórias)
- Mesma API key auth dos endpoints existentes

## OUT-OF-SCOPE (v1)

- Batch grouping (N itens = 1 job) — evolução futura, v1 é 1:1
- Multi-API-key por coletor — mesma API key para todos
- UI/dashboard para a pool — apenas API REST
- Pool em banco separado — fica no mesmo PostgreSQL
- Rate limiting específico no endpoint de ingestão — usa rate limit global
- Cleanup automático de itens claimed (manual/cron externo)
- Cross-pipeline dedup (dedup entre pipelines diferentes)

## REMOVIDOS

Nenhum — esta feature é aditiva. Nada do engine existente é removido.

---

## Success Criteria

| ID | Criterion | Target |
|----|-----------|--------|
| SC-101 | Pool ingest aceita 500 itens em < 2s | < 2s |
| SC-102 | Auto-Batcher cria job em < batch_interval após ingestão | < 5s (default) |
| SC-103 | Dedup na pool rejeita duplicata em < 10ms | < 10ms |
| SC-104 | Zero testes existentes quebrados | 173/173 passando |
| SC-105 | Pool status retorna em < 200ms | < 200ms |
| SC-106 | Container size não aumenta > 5MB | < 205MB |

---

## Edge Cases

1. **Coletor envia batch de 500 itens onde todos são duplicatas**: Pool retorna `accepted: 0, rejected: 500` sem erro — operação legítima.
2. **Auto-Batcher encontra item cujo pipeline foi deletado entre ingestão e claim**: Marcar item como erro, não travar o batcher.
3. **Content muito grande (> 1MB por item)**: Aceitar na pool (TEXT sem limite), truncation é responsabilidade do pipeline (já existe no orchestrator).
4. **Dois coletores enviam o mesmo URL quase simultaneamente**: O primeiro ganha (INSERT), o segundo recebe `duplicate_url` (UNIQUE index + ON CONFLICT).
5. **Pool com milhões de itens pendentes**: Indexes com WHERE clause parcial + SKIP LOCKED impedem degradação de performance.

---

## Assumptions

1. PostgreSQL 16 com pgvector já está rodando (setup existente)
2. A API key auth já está implementada (verify_api_key middleware)
3. O Worker existente continua consumindo jobs normalmente
4. Coletores são responsáveis por extrair o conteúdo antes de enviar (engine é agnóstico de coleta)
5. Volume esperado: < 10K itens/dia na pool (suficiente para VotoLimpo + Help Core)
