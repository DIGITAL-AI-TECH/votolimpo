---
type: spec
title: "Frente 1 — PE Help Core Instance (Config)"
created: 2026-10-05
tags: [help-core, bradesco, config, docker, pipelines]
status: draft
---

# Frente 1 — PE Help Core Instance

## Objetivo

Criar toda a infraestrutura de **configuração** para rodar o Processing Engine como
instância dedicada do projeto Help Core (Bradesco). Zero mudanças no código do PE —
apenas arquivos de configuração, YAMLs de pipeline, scripts auxiliares e Makefile.

O resultado esperado: uma instância PE funcional rodando localmente via docker-compose,
com 4 pipelines registrados, script de ingestão de artigos TXT e stack Swarm pronto
para o DevOps fazer deploy em `pe-helpcore.digital-ai.tech`.

---

## IN-SCOPE

### 1. `docker-compose.helpcore.yml` — Dev local
- Serviços: `pe-helpcore` (imagem do PE) + `pg-helpcore` (pgvector/pg16)
- Porta PE: `8001:8000` (evita conflito com instância VotoLimpo em 8000)
- Porta PostgreSQL: `5434:5432` (evita conflito com pg VotoLimpo em 5432)
- Env vars lidas de `.env.helpcore` (gitignored)
- Volume bind-mount de `./pipelines` para hot-reload dos YAMLs sem rebuild
- Healthcheck: `curl -sf http://localhost:8000/health`
- Banco: cria databases `processing_engine` e `help_core` via `POSTGRES_DB` + init SQL

### 2. `docker-stack.helpcore.yml` — Produção Swarm
- Serviços: `hc-postgres` + `hc-api`
- Hostname Traefik: `pe-helpcore.digital-ai.tech`
- Rede: `oraculusnet` (externa) + `hc-net` (overlay interna)
- Resource limits: PE 1G / 512M reservation; PostgreSQL 2G / 512M reservation
- `PE_API_KEY`, `HC_DATABASE_URL`, `HC_OPENAI_API_KEY` via secrets de Swarm (env vars)
- Placement: `node.hostname == oraculus-server-2` (mesmo nó do PE VotoLimpo)
- `HELPCORE_DATABASE_URL` apontando para `hc-postgres:5432/help_core`
- Labels Traefik idênticos ao PE VotoLimpo, com router `processing-engine-helpcore`
- `start_period: 120s` no healthcheck (gotcha: node:alpine não tem wget, usar curl)

### 3. `.env.helpcore.example` — Template de variáveis
Todas as variáveis necessárias documentadas com descrição inline:

```
# --- Engine ---
DATABASE_URL=postgresql://postgres:postgres@pg-helpcore:5432/processing_engine
HELPCORE_DATABASE_URL=postgresql://postgres:postgres@pg-helpcore:5432/help_core
API_KEY=hc-dev-api-key-change-in-prod
ENGINE_ROLE=both
LOG_LEVEL=debug

# --- Worker ---
WORKER_CONCURRENCY=4
WORKER_POLL_INTERVAL=2
BATCHER_ENABLED=true
BATCHER_POLL_INTERVAL_SECONDS=5
BATCHER_DEFAULT_BATCH_SIZE=50

# --- LLM ---
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...   # obrigatorio para pipeline helpcore-rewrite

# --- Sink Help Core ---
# Aponta para o banco help_core no mesmo PostgreSQL dedicado
VOTOLIMPO_DATABASE_URL=postgresql://postgres:postgres@pg-helpcore:5432/help_core
```

### 4. Pipeline YAMLs completos (em `pipelines/`)

#### 4a. `helpcore-inventory.yaml`
- ID e nome: `helpcore-inventory`
- Já existe como rascunho — **atualizar** para spec completa:
  - `sink_config.database_url_env: HELPCORE_DATABASE_URL` (renomear de VOTOLIMPO_DATABASE_URL)
  - `sink_config.table: help_core.inventory`
  - `conflict_column: pe_item_id`
  - `budget_limit_usd: 50.0` (piloto conservador)
- 19 categorias e 103 subcategorias completas (já no YAML atual, preservar)
- Campos output: `doc_type`, `category`, `subcategory`, `target_audience`,
  `quality_score`, `completeness_score`, `key_topics`, `summary`, `requires_update`

#### 4b. `helpcore-dedup.yaml`
- ID e nome: `helpcore-dedup`
- Modelo: `gpt-4.1-mini`, temperatura 0.0
- `dedup_strategy: composite` com `hash_fields: [content]`
- Objetivo: identificar artigos duplicados ou quasi-duplicados na base de conhecimento
- Output schema: `{ is_duplicate: bool, duplicate_of: string|null, similarity_score: float,
  reason: string }` — `duplicate_of` é o `source_url` do artigo mais autoritativo
- `sink_type: postgresql`, `table: help_core.dedup_results`
- Validator: apenas `schema`
- Cache: `enabled: true`, `ttl_hours: 720`

#### 4c. `helpcore-quality-score.yaml`
- ID e nome: `helpcore-quality-score`
- Modelo: `gpt-4.1-mini`, temperatura 0.0
- Scoring multi-dimensional (0-100 cada):
  - `clarity`: clareza e objetividade do texto
  - `structure`: organização (títulos, passos numerados, listas)
  - `completeness`: se todos os passos/informações estão presentes
  - `accuracy_signals`: sinais de precisão (referências a sistemas reais, datas, versões)
  - `readability`: facilidade de leitura para o público-alvo
  - `overall_score`: média ponderada (clarity 30%, structure 25%, completeness 25%,
    accuracy_signals 10%, readability 10%)
- Output schema: os 6 campos numéricos + `improvement_suggestions: string[]` (até 3)
- `sink_type: postgresql`, `table: help_core.quality_scores`
- `conflict_column: pe_item_id`
- Validators: `[schema, range]` — range valida todos os scores em [0, 100]
- Cache: `enabled: true`, `ttl_hours: 720`

#### 4d. `helpcore-rewrite.yaml`
- ID e nome: `helpcore-rewrite`
- **`llm_provider: anthropic`** — depende da Frente 2 para funcionar (suporte a Anthropic no PE)
- Modelo: `claude-sonnet-4-5` (ou `claude-3-5-sonnet-20241022`)
- Temperatura: 0.3 (leve criatividade para reescrita fluente)
- System prompt: reescrita de artigos da KB em linguagem clara, estruturada e
  padronizada para operadores de atendimento Bradesco
- Output schema: `{ rewritten_content: string, changes_summary: string,
  word_count_original: int, word_count_rewritten: int }`
- `sink_type: postgresql`, `table: help_core.rewrites`
- `conflict_column: pe_item_id`
- Validator: apenas `schema`
- Cache: `enabled: false` (reescrita é criativa, não deve ser cacheada)
- **Nota no YAML**: comentário explícito que este pipeline requer `ANTHROPIC_API_KEY`
  e suporte Anthropic no PE (Frente 2). Fallback: `llm_provider: openai` + `gpt-4.1`
  para uso imediato sem aguardar Frente 2.

### 5. `scripts/ingest-helpcore.py`
Script Python standalone (sem dependências além de `requests` e `pathlib`) para
ingerir artigos TXT no PE Help Core via `POST /v1/jobs`.

Funcionalidades obrigatórias:
- **Encoding**: tenta `utf-8-sig` primeiro, fallback para `latin-1`
- **Batches**: agrupa arquivos em lotes de 200 (configurável via `--batch-size`)
- **Pipeline selecionável**: `--pipeline helpcore-inventory` (default)
- **Retry**: até 3 tentativas com backoff exponencial (2s, 4s, 8s) em caso de 5xx
- **Relatório final**: imprime tabela `total | enviados | erros | custo_estimado`
- **Progress**: barra de progresso simples (`[=====>    ] 150/500 artigos`)
- **Dry run**: `--dry-run` lista arquivos sem ingerir
- **Filtro por extensão**: apenas `.txt` (configurável via `--ext`)
- **Source URL**: derivado do nome do arquivo (`file://<nome_sem_ext>`)
- **Auth**: lê `HC_API_KEY` do env ou `--api-key` CLI arg

Assinatura:
```
python scripts/ingest-helpcore.py <pasta_txts> \
  [--pipeline helpcore-inventory] \
  [--batch-size 200] \
  [--pe-url http://localhost:8001] \
  [--api-key hc-dev-api-key] \
  [--dry-run]
```

### 6. `Makefile.helpcore`
Makefile separado para não interferir com o Makefile principal do PE VotoLimpo.

Targets obrigatórios:

| Target | Ação |
|--------|------|
| `make -f Makefile.helpcore up` | `docker compose -f docker-compose.helpcore.yml up -d` |
| `make -f Makefile.helpcore down` | `docker compose -f docker-compose.helpcore.yml down` |
| `make -f Makefile.helpcore logs` | Tail dos logs do container `pe-helpcore` |
| `make -f Makefile.helpcore migrate` | Roda `alembic upgrade head` dentro do container |
| `make -f Makefile.helpcore ingest` | Chama `scripts/ingest-helpcore.py` com vars do `.env.helpcore` |
| `make -f Makefile.helpcore test-pilot` | Ingere 100 primeiros arquivos de `HC_SAMPLE_DIR` como piloto |
| `make -f Makefile.helpcore pipelines` | Copia YAMLs helpcore para o container e valida `GET /v1/pipelines` |
| `make -f Makefile.helpcore status` | `curl localhost:8001/health && curl localhost:8001/v1/stats` |

---

## OUT-OF-SCOPE

- **Zero mudanças no código Python do PE** — nenhum arquivo em `app/` é tocado
- Frontend ou dashboard para Help Core
- Integração com SharePoint (fase posterior)
- Autenticação SSO / OAuth para Help Core
- Migrations de schema `help_core.*` (são responsabilidade da Frente 2)
- Deploy real em produção (responsabilidade do DevOps após gate completo)
- Suporte nativo Anthropic no PE (Frente 2)

---

## REMOVIDOS

Nenhuma funcionalidade existente é removida. O `helpcore-inventory.yaml` existente é
**atualizado** (não substituído) — a variável de sink muda de `VOTOLIMPO_DATABASE_URL`
para `HELPCORE_DATABASE_URL`. Esse ajuste é não-breaking pois a variável só importa
quando o pipeline está ativo em uma instância que a tenha definida.

---

## Requisitos Técnicos

### docker-compose.helpcore.yml
- Baseado no `docker-compose.yml` existente mas com nomes de serviços distintos
  (`pe-helpcore`, `pg-helpcore`) para não colidir com instância VotoLimpo
- Portas mapeadas: `8001:8000` (PE) e `5434:5432` (PG)
- Volume de pipelines: `./pipelines:/app/pipelines:ro`
- O PE precisa de `init.sql` para criar o database `help_core` se não existir:
  ```sql
  CREATE DATABASE help_core;
  ```
  Montar via `./scripts/init-helpcore.sql:/docker-entrypoint-initdb.d/init.sql`

### docker-stack.helpcore.yml
- Espelha estrutura do `docker-stack.yml` existente
- Nomes dos serviços com prefixo `hc-` para evitar conflitos no Swarm
- Stack name recomendado: `helpcore` (Portainer mostrará `helpcore_hc-api` etc.)
- Volume persistente: `hc-pgdata` (não compartilha com o volume `pgdata` do VotoLimpo)

### Pipeline YAMLs
- Formato idêntico ao `helpcore-inventory.yaml` e `voto-limpo-news-analysis.yaml` existentes
- IDs em kebab-case, únicos globalmente no PE
- `sink_config.database_url_env` deve apontar para `HELPCORE_DATABASE_URL` em todos
- `budget_limit_usd: 50.0` em todos (conservador para piloto)
- `max_concurrent: 5` em todos

### Script de ingestão
- Python 3.12, apenas stdlib + `requests` (já disponível no ambiente)
- Não depende de nenhum módulo interno do PE
- Compatível com `python scripts/ingest-helpcore.py` sem instalação

### Makefile
- Targets devem funcionar com GNU Make 4.x
- Usa `$(shell ...)` para carregar vars do `.env.helpcore` quando necessário
- O target `test-pilot` deve sair com código não-zero se houver erros de ingestão

---

## Arquivos a Criar/Modificar

### Criar (novos)
```
processing-engine/
├── docker-compose.helpcore.yml
├── docker-stack.helpcore.yml
├── .env.helpcore.example
├── Makefile.helpcore
├── scripts/
│   ├── ingest-helpcore.py
│   └── init-helpcore.sql          ← CREATE DATABASE help_core
└── pipelines/
    ├── helpcore-dedup.yaml         (novo)
    ├── helpcore-quality-score.yaml (novo)
    └── helpcore-rewrite.yaml       (novo)
```

### Modificar (existentes)
```
processing-engine/
└── pipelines/
    └── helpcore-inventory.yaml    ← sink_config.database_url_env: HELPCORE_DATABASE_URL
```

### Não tocar
- `app/` — zero mudanças de código
- `docker-compose.yml` — instância VotoLimpo intacta
- `docker-stack.yml` — instância VotoLimpo intacta
- `.env` / `.env.example` — VotoLimpo intactos
- `Makefile` (se existir) — VotoLimpo intacto

---

## Acceptance Criteria

```
A1. docker-compose up sobe instância local
    - Comando: make -f Makefile.helpcore up
    - Evidência: curl http://localhost:8001/health retorna HTTP 200 {"status": "ok"}

A2. 4 pipelines registrados e listáveis
    - Comando: curl -H "x-api-key: hc-dev-api-key" http://localhost:8001/v1/pipelines
    - Evidência: JSON com helpcore-inventory, helpcore-dedup, helpcore-quality-score,
      helpcore-rewrite listados

A3. Script de ingestão processa piloto sem erros
    - Comando: python scripts/ingest-helpcore.py <pasta> --dry-run (valida sem enviar)
    - Evidência: relatório final com "0 erros" para sample de 100 arquivos TXT

A4. .env.helpcore.example documenta todas as variáveis
    - Evidência: todas as variáveis usadas em docker-compose.helpcore.yml e
      docker-stack.helpcore.yml têm linha correspondente no example com comentário

A5. Makefile com todos os targets funcionando
    - Evidência: make -f Makefile.helpcore help lista os 8 targets; cada um executa
      sem erro de sintaxe (make --dry-run)

A6. docker-stack.helpcore.yml pronto para deploy Swarm
    - Evidência: docker stack deploy --prune --resolve-image=always
      -c docker-stack.helpcore.yml helpcore --resolve-image never
      não retorna erro de sintaxe (validação offline com docker stack config)
```

---

## Dependências e Blockers

| Dependência | Tipo | Impacto |
|-------------|------|---------|
| Frente 2 — suporte Anthropic no PE | Blocker parcial | Pipeline `helpcore-rewrite` funciona com fallback OpenAI; modo Anthropic aguarda Frente 2 |
| Migrations `help_core.*` (tabelas sink) | Blocker para ingestão real | A3 (dry-run) passa sem as tabelas; ingestão efetiva requer schema `help_core.inventory` etc. |
| Arquivos TXT do Bradesco disponíveis | Blocker para A3 real | Dry-run valida sem TXTs; ingestão efetiva requer os 100k+ artigos |

---

## Notas de Implementação

1. **Portas**: usar `8001` e `5434` no local para não conflitar com VotoLimpo (`8000`/`5432`)
2. **Nome dos serviços Swarm**: prefixo `hc-` evita colisão com serviços `pe-postgres` e `api` do VotoLimpo
3. **`helpcore-rewrite.yaml`**: adicionar comentário YAML proeminente que o pipeline requer
   Frente 2. Incluir fallback comentado com `llm_provider: openai` + `gpt-4.1` para uso imediato.
4. **`init-helpcore.sql`**: o PostgreSQL oficial ignora scripts de init se o volume já existir —
   documentar no Makefile que `make down -v` (com volumes) é necessário para re-criar.
5. **`.env.helpcore`**: deve constar no `.gitignore` da raiz do PE. Verificar e adicionar se necessário.
