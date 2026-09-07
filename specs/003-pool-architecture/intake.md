# INTAKE: Desacoplamento Coleta-Processamento (Pool Architecture)

**Data**: 2026-09-07
**Demanda de**: Matheus Terra (owner)
**Classificacao**: Mudanca arquitetural (refactoring estrutural)
**Complexidade estimada**: L (Large)

---

## 1. Pedido Original (brief)

> "Quero que seja agnostico, a coleta dos dados nao pode estar atrelada ao servico. Quero ter N coletas que joguem os dados em uma pool, e a partir de qual pipeline inseriu a engine processe."

**Traducao tecnica**: Hoje coletores fazem `POST /v1/jobs` direto no engine, acoplando coleta ao processamento. O Matheus quer uma camada intermediaria (pool) que desacopla os dois: N coletores depositam dados na pool, e o engine consome da pool com base no pipeline associado.

---

## 2. Arquitetura Atual vs. Proposta

### HOJE (acoplado)

```
Coletor A ──POST /v1/jobs──► Engine (valida pipeline, cria job+items, processa)
Coletor B ──POST /v1/jobs──►     "
```

- O coletor precisa conhecer a API do engine
- O coletor precisa saber o `pipeline_id`
- O coletor precisa formatar o payload como `JobCreate` (items, overrides, callback)
- Se o engine esta fora, a coleta para

### PROPOSTA (desacoplado via pool)

```
Coletor A ──deposita──► POOL (tabela PostgreSQL)
Coletor B ──deposita──►   "
Coletor N ──deposita──►   "
                           │
                    Engine Pool Consumer
                           │
                    ┌──────▼──────┐
                    │  Engine     │
                    │  (pipeline) │
                    └─────────────┘
```

- Coletores depositam dados brutos na pool com metadata minima (source, pipeline_id, content, content_type)
- O engine consome da pool via SKIP LOCKED (mesmo padrao do worker atual)
- O coletor NAO precisa conhecer a API do engine — so a tabela/API da pool

---

## 3. Escopo da Mudanca

### O QUE MUDA

| Componente | Mudanca |
|-----------|---------|
| **Nova entidade: Pool** | Tabela `processing_engine.pool` para armazenar itens depositados por coletores |
| **Pool Consumer** | Novo componente no worker que consome da pool, agrupa por pipeline e cria jobs automaticamente |
| **API de Deposito** | Novo endpoint `POST /v1/pool` (ou `POST /v1/ingest`) — payload simplificado para coletores |
| **Worker** | Adicionar loop de consumo da pool alem do loop de processamento de jobs |
| **Modelo de dados** | Nova tabela + possiveis novos estados |

### O QUE FICA (nao muda)

| Componente | Por que fica |
|-----------|-------------|
| **Pipeline completo** (ingest -> dedup -> process -> validate -> persist) | O core do engine nao muda — so a forma de alimenta-lo |
| **POST /v1/jobs** (API direta) | Backwards compatible — coletores que ja usam continuam funcionando |
| **Orchestrator** | Recebe job e processa — indiferente se veio da API ou da pool |
| **Plugins** (ingestors, dedup, validators, sinks) | Nenhum plugin muda |
| **Cache, logging, stats, costs** | Funcionam identicamente |
| **Testes unitarios de plugins** | Nao sao afetados pela mudanca de entrada |

---

## 4. Riscos Identificados

| # | Risco | Severidade | Mitigacao |
|---|-------|-----------|-----------|
| R1 | **Quebra de backwards compatibility** — se `POST /v1/jobs` for removido ou alterado | ALTA | Manter `POST /v1/jobs` intacto. Pool e um CANAL ADICIONAL, nao substituto |
| R2 | **Complexidade do Pool Consumer** — agrupamento de items em jobs (quando criar job? por tempo? por quantidade? por pipeline?) | MEDIA | Definir estrategia clara: 1 item = 1 job (simples) OU batch por janela de tempo |
| R3 | **Duplicacao de dedup** — pool precisa de dedup proprio ou delega ao engine? | MEDIA | Pool faz dedup leve (url_hash) para rejeitar obvios; engine faz dedup completo |
| R4 | **Principio V (Stack Minima)** — pool NAO pode introduzir Redis/RabbitMQ/Kafka | ALTA | Pool usa tabela PostgreSQL + SKIP LOCKED (mesmo padrao do job queue) |
| R5 | **Observabilidade** — rastrear de qual coletor veio cada item | BAIXA | Campo `source_collector` na tabela pool |
| R6 | **Testes E2E e contract quebram** — se a API mudar | MEDIA | API nao muda (R1); novos testes para o endpoint /v1/pool |

---

## 5. Decisoes que o Matheus Precisa Tomar (ANTES de implementar)

### D1. Granularidade do deposito na pool

**Opcao A**: Cada item depositado vira 1 job individual no engine
- Simples, previsivel, facil de rastrear
- Menos eficiente para batches grandes

**Opcao B**: Pool Consumer agrupa items por pipeline + janela de tempo (ex: a cada 60s ou a cada 50 items, cria 1 job)
- Mais eficiente para volume alto
- Mais complexo de implementar e debugar

**Opcao C**: O coletor decide — deposita com `batch_key` opcional; items com mesmo batch_key viram 1 job
- Flexivel, mas coloca logica no coletor

**Recomendacao PM**: Opcao A para v1 (1 item = 1 job). Opcao B como melhoria futura.

### D2. API da pool — endpoint REST ou escrita direta no banco?

**Opcao A**: `POST /v1/pool` no proprio engine (API REST)
- Facil de autenticar, validar, documentar
- Coletor ainda precisa falar HTTP com o engine (menos desacoplado)

**Opcao B**: Coletores escrevem direto na tabela `pool` via SQL
- Maximo desacoplamento (coletor so precisa de conexao PostgreSQL)
- Perde validacao na entrada; qualquer servico com acesso ao banco pode inserir

**Opcao C**: Ambos — REST para coletores externos, SQL direto para servicos internos
- Maior flexibilidade, mais superficie de manutencao

**Recomendacao PM**: Opcao A (REST no engine). Mantem validacao centralizada e nao viola o principio de container unico. Se no futuro precisar de escrita direta, e uma addicao incremental.

### D3. A pool vive no mesmo banco do engine ou em banco separado?

**Recomendacao PM**: Mesmo banco, mesmo schema `processing_engine`. Principio V (Stack Minima) — zero infra nova.

### D4. O que acontece com items na pool que nao tem pipeline valido?

- Rejeitar na hora do deposito (validacao no POST /v1/pool)?
- Aceitar e marcar como `unroutable` para revisao manual?

**Recomendacao PM**: Rejeitar com 404 na hora do deposito — fail fast.

### D5. Naming — "pool" ou outro nome?

Candidatos: `pool`, `inbox`, `ingest_queue`, `data_lake`, `intake`

**Recomendacao PM**: `pool` — alinhado com a linguagem do Matheus no pedido original.

---

## 6. Acceptance Criteria Propostos

```
## Acceptance Checklist (pedido de 2026-09-07 — "Pool Architecture")

A1. N coletores independentes conseguem depositar dados na pool via API
    sem conhecer a estrutura interna do engine (JobCreate, overrides, etc.)

A2. O engine consome automaticamente da pool e cria jobs para processamento
    sem intervencao manual

A3. POST /v1/jobs continua funcionando identicamente (backwards compatible)
    — zero breaking change para integrantes existentes

A4. Cada item na pool e rastreavel ate o job/result final
    (pool_item_id -> job_id -> item_id -> result)

A5. A pool usa PostgreSQL puro (sem Redis, Kafka, RabbitMQ)
    — respeita Constitution V (Stack Minima)

A6. Items duplicados (mesmo url_hash) sao rejeitados na pool
    antes de virar job — respeita Constitution II (Anti-Reprocessamento)

A7. Metricas de custo e stats incluem items originados da pool
    (sem perder rastreabilidade de origem)

A8. Testes existentes (173 unit + contract + E2E) continuam passando
    sem modificacao (zero regressao)

A9. Novos testes cobrem: deposito na pool, consumo da pool,
    rejeicao de duplicatas na pool, rastreabilidade pool->job->result
```

---

## 7. Impacto nos Testes Existentes

### Testes que NAO quebram (se backwards compatibility for mantida)

| Suite | Qtd | Impacto | Razao |
|-------|-----|---------|-------|
| `unit/test_ingestors.py` | ~20 | Nenhum | Plugins nao mudam |
| `unit/test_dedup.py` + `test_dedup_extra.py` | ~20 | Nenhum | Logica de dedup nao muda |
| `unit/test_validators.py` + `test_validators_extra.py` | ~30 | Nenhum | Validadores nao mudam |
| `unit/test_orchestrator.py` + `test_orchestrator_cache.py` | ~30 | Nenhum | Orchestrator recebe job e processa — indiferente da origem |
| `unit/test_pipeline_models.py` | ~10 | Nenhum | Modelos de pipeline nao mudam |
| `unit/test_rate_limiter.py` | ~5 | Nenhum | Rate limiter nao muda |
| `unit/test_cost_tracker.py` | ~10 | Nenhum | Cost tracking nao muda |
| `contract/test_openapi.py` | ~15 | **PRECISA ATUALIZAR** | Novo endpoint /v1/pool precisa estar no OpenAPI |
| `contract/test_response_shapes.py` | ~16 | Nenhum | Shapes existentes nao mudam |
| `e2e/test_pipeline_flow.py` | ~5 | Nenhum | Fluxo via POST /v1/jobs continua |
| `e2e/test_batch_processing.py` | ~5 | Nenhum | Batch via POST /v1/jobs continua |
| `unit/test_worker.py` | ~10 | **PRECISA ATUALIZAR** | Worker ganha novo loop de consumo da pool |

### Testes NOVOS necessarios

| Suite | Cobertura |
|-------|-----------|
| `unit/test_pool_consumer.py` | Consumo da pool, agrupamento, criacao de job |
| `contract/test_api_pool.py` | POST /v1/pool — payload, validacao, respostas |
| `e2e/test_pool_flow.py` | Fluxo completo: deposito na pool -> consumo -> processamento -> resultado |
| `unit/test_pool_dedup.py` | Rejeicao de duplicatas na pool |

---

## 8. Estimativa de Esforco

| Fase | Trabalho | Estimativa |
|------|----------|-----------|
| Spec + Plan | Atualizar spec, data model, OpenAPI | 0.5 dia |
| Schema | Nova tabela pool + migracao Alembic | 0.5 dia |
| Pool API | POST /v1/pool endpoint | 0.5 dia |
| Pool Consumer | Loop no worker + logica de criacao de job | 1 dia |
| Testes | Unit + contract + E2E novos | 1 dia |
| Integracao | Testar com coletor real (ex: VotoLimpo scheduler) | 0.5 dia |
| **Total** | | **4 dias** |

---

## 9. Proximos Passos

1. **Matheus decide D1-D5** (decisoes pendentes acima)
2. PM gera PRD formal com base nas decisoes
3. Speckit: `specify` -> `plan` -> `tasks` -> `implement`
4. Implementacao na branch `feature/pool-architecture` (a partir de `002-processing-engine`)
5. Quality gate completo (HOMELAND -> QA + SENTINEL + DEVOPS -> PM fecho de aceite)

---

## 10. Alinhamento com Constitution

| Principio | Status | Nota |
|-----------|--------|------|
| I. Agnostico por Design | **FORTALECE** | Pool torna o engine MAIS agnostico — coletores nem conhecem a API interna |
| II. Anti-Reprocessamento | MANTIDO | Dedup na pool + dedup no engine (2 camadas) |
| III. Custo Controlado | MANTIDO | Nenhuma chamada LLM extra |
| IV. Plugin-First | MANTIDO | Nenhum plugin muda |
| V. Stack Minima | **CRITICO** | Pool DEVE ser PostgreSQL puro — zero infra nova |
| VI. Schema First | MANTIDO | Nova tabela com migracao Alembic |
| VII. Idempotencia | MANTIDO | Pool consumer respeita idempotency |
| VIII. Observabilidade | **MELHORA** | Rastreabilidade coletor -> pool -> job -> result |
| IX. Testabilidade | MANTIDO | Novos testes para pool; existentes intactos |
| X. Seguranca | MANTIDO | API key no endpoint /v1/pool |
