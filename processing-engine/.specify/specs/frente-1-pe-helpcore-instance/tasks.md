---
type: tasks
title: "Tasks — Frente 1: PE Help Core Instance"
created: 2026-10-05
tags: [help-core, config, tasks]
---

# Tasks — Frente 1: PE Help Core Instance

> Todas as tasks são de **configuração pura** — zero mudanças em `app/`.
> Cada task lista arquivos envolvidos, critério de done e dependências (`blockedBy`).
> `[P]` = pode rodar em paralelo com outras tasks marcadas `[P]` na mesma fase.

---

## Fase 1: Infraestrutura Docker

### T1.1 — Criar `scripts/init-helpcore.sql`
**Arquivos:** `scripts/init-helpcore.sql` (novo)

**O que fazer:**
- Criar arquivo SQL com comando `CREATE DATABASE IF NOT EXISTS help_core;`
- Adicionar comentário explicando que este script é montado em
  `/docker-entrypoint-initdb.d/init.sql` e executado apenas no primeiro boot do PG
- Adicionar nota sobre comportamento: se volume já existe, o script é ignorado

**Critério de done:**
- Arquivo existe em `scripts/init-helpcore.sql`
- Sintaxe SQL válida (verificar com `psql --command="\i init-helpcore.sql" --dry-run` ou inspeção manual)
- Comentário documenta o comportamento do Docker entrypoint

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T1.2, T1.3

---

### T1.2 — Criar `.env.helpcore.example` [P]
**Arquivos:** `.env.helpcore.example` (novo); `.gitignore` (verificar/adicionar entrada)

**O que fazer:**
- Criar arquivo com todas as variáveis necessárias para `docker-compose.helpcore.yml` e
  `docker-stack.helpcore.yml`, cada uma com comentário inline explicando o propósito
- Variáveis obrigatórias (ver spec §3):
  ```
  DATABASE_URL           ← URL do banco processing_engine no pg-helpcore
  HELPCORE_DATABASE_URL  ← URL do banco help_core no pg-helpcore
  API_KEY                ← Chave de autenticação da API do PE Help Core
  ENGINE_ROLE            ← "both" para API + Worker no mesmo processo
  LOG_LEVEL              ← "debug" para dev, "info" para prod
  WORKER_CONCURRENCY     ← 4 (dev), 8 (prod)
  WORKER_POLL_INTERVAL   ← 2 (segundos)
  BATCHER_ENABLED        ← true
  BATCHER_POLL_INTERVAL_SECONDS ← 5
  BATCHER_DEFAULT_BATCH_SIZE    ← 50
  OPENAI_API_KEY         ← Obrigatório para inventory/dedup/quality-score
  ANTHROPIC_API_KEY      ← Obrigatório para helpcore-rewrite (Frente 2)
  VOTOLIMPO_DATABASE_URL ← Mapeado para help_core (PE usa esta env var como sink alternativo)
  ```
- Verificar `.gitignore` na raiz do PE: adicionar `.env.helpcore` se não estiver listado
- Valores de exemplo devem ser plausíveis mas claramente de dev (ex: `hc-dev-api-key-change-in-prod`)

**Critério de done:**
- `.env.helpcore.example` existe com todas as variáveis da spec §3
- Todo valor tem comentário de uma linha acima (formato `# descrição`)
- `.gitignore` contém `.env.helpcore` (e não `.env.helpcore.example`)

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T1.1, T1.3

---

### T1.3 — Criar `docker-compose.helpcore.yml` [P]
**Arquivos:** `docker-compose.helpcore.yml` (novo); referência: `docker-compose.yml`

**O que fazer:**
- Copiar estrutura do `docker-compose.yml` existente como base
- Renomear serviços: `postgres` → `pg-helpcore`, `api` → `pe-helpcore`
- Ajustar portas: `8001:8000` (PE), `5434:5432` (PG)
- Configurar env vars do PE lidas do `.env.helpcore` (usar `env_file: .env.helpcore`)
- Adicionar volume bind-mount para pipelines (read-only): `./pipelines:/app/pipelines:ro`
- Adicionar bind-mount do init SQL: `./scripts/init-helpcore.sql:/docker-entrypoint-initdb.d/init.sql:ro`
- **Remover** bind-mounts de `./app` e `./db_models` do `docker-compose.yml` existente (esses
  são para hot-reload de código; Help Core usa a imagem buildada)
- Volume nomeado para PG: `hc-pgdata` (não compartilha com `pgdata` do VotoLimpo)
- Healthcheck PE: `curl -sf http://localhost:8000/health` (gotcha: não tem wget no Alpine)
- Healthcheck PG: `pg_isready -U postgres` (já estava no original)
- `depends_on` com `condition: service_healthy`

**Critério de done:**
- `docker-compose.helpcore.yml` existe e é YAML válido
- Serviços usam nomes `pe-helpcore` e `pg-helpcore`
- Portas `8001` e `5434` (nenhuma colisão com VotoLimpo em `8000`/`5432`)
- Bind-mount `./pipelines:/app/pipelines:ro` presente
- Init SQL montado em `/docker-entrypoint-initdb.d/`
- Volume `hc-pgdata` definido na seção `volumes:`

**blockedBy:** T1.1 (precisa do init SQL para referenciar no bind-mount), T1.2 (para env_file)
*(na prática pode ser escrito antes — o arquivo pode referenciar `.env.helpcore` mesmo se ainda não existe; a validação de boot exige os dois)*

---

### T1.4 — Criar `docker-stack.helpcore.yml`
**Arquivos:** `docker-stack.helpcore.yml` (novo); referência: `docker-stack.yml`

**O que fazer:**
- Copiar estrutura do `docker-stack.yml` existente como base
- Renomear serviços: `pe-postgres` → `hc-postgres`, `api` → `hc-api`
- Usar prefixo `hc-` em todos os recursos para evitar colisões no Swarm
- Imagem do PE: mesma que VotoLimpo (`registry.digital-ai.tech/processing-engine:${IMAGE_TAG:-latest}`)
- Env vars do PE: `API_KEY`, `DATABASE_URL`, `HELPCORE_DATABASE_URL`, `OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`, `ENGINE_ROLE: both`, `WORKER_CONCURRENCY: 4`
- Volume bind-mount dos pipelines: `./pipelines:/app/pipelines:ro` (Swarm suporta bind mounts
  com path relativo ao nó — documentar que os YAMLs devem estar no host)
- Healthcheck: usar `curl` (não wget — gotcha: Alpine não tem wget)
  `start_period: 120s` (conforme gotcha documentado)
- Labels Traefik:
  - Router HTTPS: `processing-engine-helpcore` (regra: `Host("pe-helpcore.digital-ai.tech")`)
  - Router HTTP: `processing-engine-helpcore-http` com middleware `redirect-to-https`
  - Serviço: `processing-engine-helpcore` na porta `8000`
  - `traefik.docker.network=oraculusnet`
- Redes: `oraculusnet` (external) + `hc-net` (overlay interna)
- Resource limits: PE `1G` / `512M` reservation; PG `2G` / `512M` reservation
- Placement ambos: `node.hostname == oraculus-server-2`
- Volume persistente: `hc-pgdata` (named, não é `external: true` — será criado pelo Swarm)
- Stack name recomendado: `helpcore` (Portainer mostrará `helpcore_hc-api`, `helpcore_hc-postgres`)

**Critério de done:**
- `docker-stack.helpcore.yml` existe e é YAML válido
- `docker stack config -c docker-stack.helpcore.yml` não retorna erro de sintaxe
- Nenhum nome de serviço ou volume colide com `docker-stack.yml` do VotoLimpo
- Labels Traefik com hostname `pe-helpcore.digital-ai.tech` e router `processing-engine-helpcore`
- `start_period: 120s` no healthcheck do `hc-api`

**blockedBy:** T1.2 (para ter clareza das env vars a declarar)

---

### T1.5 — Criar `Makefile.helpcore`
**Arquivos:** `Makefile.helpcore` (novo)

**O que fazer:**
- Criar Makefile com `COMPOSE_FILE = docker-compose.helpcore.yml` no topo
- Carregar vars do `.env.helpcore` via `$(shell ...)` para os targets que precisam (ingest, test-pilot)
- Implementar os 8 targets obrigatórios da spec §6:

| Target | Comando |
|--------|---------|
| `up` | `docker compose -f docker-compose.helpcore.yml up -d` |
| `down` | `docker compose -f docker-compose.helpcore.yml down` |
| `logs` | `docker compose -f docker-compose.helpcore.yml logs -f pe-helpcore` |
| `migrate` | `docker compose -f docker-compose.helpcore.yml exec pe-helpcore alembic upgrade head` |
| `ingest` | `python scripts/ingest-helpcore.py $${HC_INGEST_DIR} --pe-url http://localhost:8001 --api-key $${API_KEY}` |
| `test-pilot` | `python scripts/ingest-helpcore.py $${HC_SAMPLE_DIR} --batch-size 100 --pe-url http://localhost:8001 --api-key $${API_KEY}`; exit com código não-zero se houver erros |
| `pipelines` | `curl -s -H "x-api-key: $${API_KEY}" http://localhost:8001/v1/pipelines \| python3 -m json.tool` |
| `status` | `curl -s http://localhost:8001/health && curl -s -H "x-api-key: $${API_KEY}" http://localhost:8001/v1/stats` |

- Adicionar target `help` que lista todos os targets com uma linha de descrição (target padrão `.DEFAULT_GOAL := help`)
- Comentário no topo: "Usar com: make -f Makefile.helpcore <target>"
- Nota sobre `down -v` para remover volumes (necessário para recriar banco do zero)

**Critério de done:**
- `make -f Makefile.helpcore help` lista os 8 targets sem erro de sintaxe
- `make -f Makefile.helpcore --dry-run up` mostra o comando correto sem executar
- Sintaxe GNU Make 4.x válida (sem tabs vs espaços misturados)

**blockedBy:** T1.3 (referencia docker-compose.helpcore.yml)

---

## Fase 2: Pipeline YAMLs

> Todos os YAMLs da Fase 2 podem ser escritos em paralelo. A leitura do `helpcore-inventory.yaml`
> e `voto-limpo-news-analysis.yaml` existentes como referência de formato é obrigatória antes de
> iniciar qualquer YAML.

### T2.1 — Atualizar `helpcore-inventory.yaml` [P]
**Arquivos:** `pipelines/helpcore-inventory.yaml` (modificar)

**O que fazer:**
- Localizar campo `sink_config.database_url_env` e alterar de `VOTOLIMPO_DATABASE_URL`
  para `HELPCORE_DATABASE_URL`
- Alterar `budget_limit_usd` de `100.0` para `50.0` (piloto conservador conforme spec)
- Alterar `dedup_strategy` de `hash` para `composite` para alinhamento com spec:
  `dedup_config: { hash_fields: [content], url_normalize: true }`
- Preservar integralmente: `id`, `name`, `description`, `system_prompt` completo com
  19 categorias e 103 subcategorias, `output_schema`, `validators`, `sink_config.table`,
  `sink_config.conflict_column`, `column_mapping`, `item_field_mapping`, `jsonb_fallback`,
  `max_concurrent`, `rate_limit_rpm`, `max_retries`, `cache`

**Critério de done:**
- `sink_config.database_url_env: HELPCORE_DATABASE_URL` (não mais `VOTOLIMPO_DATABASE_URL`)
- `budget_limit_usd: 50.0`
- `dedup_strategy: composite` com `hash_fields: [content]`
- Nenhum campo do system_prompt original foi removido ou alterado
- YAML válido (verificar com `python -c "import yaml; yaml.safe_load(open('pipelines/helpcore-inventory.yaml'))"`)

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T2.2, T2.3, T2.4

---

### T2.2 — Criar `helpcore-dedup.yaml` [P]
**Arquivos:** `pipelines/helpcore-dedup.yaml` (novo)

**O que fazer:**
- Criar YAML com os campos obrigatórios (spec §4b):
  - `id: helpcore-dedup`, `name: helpcore-dedup`
  - `ingestor_type: auto`
  - `dedup_strategy: composite` com `hash_fields: [content]`
  - `llm_provider: openai`, `llm_model: gpt-4.1-mini`, `llm_temperature: 0.0`
  - `llm_max_tokens: 4096` (respostas de dedup são curtas)
  - System prompt: identifica artigos duplicados ou quasi-duplicados na KB Bradesco.
    Instruir o modelo a comparar o artigo recebido com o contexto disponível e retornar
    `is_duplicate`, `duplicate_of` (source_url do autoritativo ou null), `similarity_score`
    (0.0-1.0), `reason` (explicação em PT-BR)
  - `output_schema` com os 4 campos: `is_duplicate` (bool), `duplicate_of` (string|null),
    `similarity_score` (number, 0.0-1.0), `reason` (string)
  - `validators: [schema]`
  - `sink_type: postgresql`, `sink_config.database_url_env: HELPCORE_DATABASE_URL`,
    `sink_config.table: help_core.dedup_results`
  - `cache: { enabled: true, ttl_hours: 720 }`
  - `budget_limit_usd: 50.0`, `max_concurrent: 5`

**Critério de done:**
- `pipelines/helpcore-dedup.yaml` existe e é YAML válido
- `id: helpcore-dedup` único (não conflita com outros IDs no diretório)
- `sink_config.database_url_env: HELPCORE_DATABASE_URL`
- `output_schema` cobre os 4 campos com tipos corretos (incluindo `null` em `duplicate_of`)
- `cache.enabled: true`

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T2.1, T2.3, T2.4

---

### T2.3 — Criar `helpcore-quality-score.yaml` [P]
**Arquivos:** `pipelines/helpcore-quality-score.yaml` (novo)

**O que fazer:**
- Criar YAML com os campos obrigatórios (spec §4c):
  - `id: helpcore-quality-score`, `name: helpcore-quality-score`
  - `ingestor_type: auto`
  - `dedup_strategy: composite` com `hash_fields: [content]`
  - `llm_provider: openai`, `llm_model: gpt-4.1-mini`, `llm_temperature: 0.0`
  - System prompt: avaliação multi-dimensional de qualidade de artigos da KB Bradesco.
    Detalhar os 5 critérios com pesos para o `overall_score`:
    - `clarity` (30%): clareza e objetividade para operadores de atendimento
    - `structure` (25%): organização com títulos, passos numerados, listas
    - `completeness` (25%): todos os passos e informações necessárias presentes
    - `accuracy_signals` (10%): referências a sistemas reais, datas, versões, números de tela
    - `readability` (10%): facilidade de leitura para o público-alvo
    - `overall_score`: média ponderada dos 5 critérios
    - `improvement_suggestions`: lista de até 3 sugestões concretas de melhoria em PT-BR
  - `output_schema` com os 6 campos numéricos (0-100) + `improvement_suggestions` (array de string)
  - `validators: [schema, range]`
  - `validator_config.range.ranges`: mapear todos os 6 campos numéricos para `[0, 100]`
    (usar notação `"clarity": [0, 100]`, etc.)
  - `sink_type: postgresql`, `sink_config.database_url_env: HELPCORE_DATABASE_URL`,
    `sink_config.table: help_core.quality_scores`, `conflict_column: pe_item_id`
  - `cache: { enabled: true, ttl_hours: 720 }`
  - `budget_limit_usd: 50.0`, `max_concurrent: 5`

**Critério de done:**
- `pipelines/helpcore-quality-score.yaml` existe e é YAML válido
- `output_schema` tem os 6 campos numéricos + `improvement_suggestions` array
- `validators: [schema, range]` e `validator_config` presente com ranges para todos os 6 scores
- `sink_config.conflict_column: pe_item_id`

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T2.1, T2.2, T2.4

---

### T2.4 — Criar `helpcore-rewrite.yaml` [P]
**Arquivos:** `pipelines/helpcore-rewrite.yaml` (novo)

**O que fazer:**
- Criar YAML com os campos obrigatórios (spec §4d):
  - `id: helpcore-rewrite`, `name: helpcore-rewrite`
  - `ingestor_type: auto`
  - `dedup_strategy: none` (reescrita é criativa, dedup não se aplica)
  - **`llm_provider: anthropic`** (configuração-alvo)
  - **`llm_model: claude-sonnet-4-5`** (ou `claude-3-5-sonnet-20241022`)
  - `llm_temperature: 0.3`
  - Sistema de comentários proeminente no topo do arquivo:
    ```yaml
    # ATENÇÃO: Este pipeline requer:
    #   1. ANTHROPIC_API_KEY definida no ambiente
    #   2. Suporte nativo Anthropic no PE (Frente 2 do Help Core)
    #
    # FALLBACK (para uso imediato sem aguardar Frente 2):
    #   Comentar as linhas llm_provider/llm_model acima e descomentar:
    #   # llm_provider: openai
    #   # llm_model: gpt-4.1
    ```
  - System prompt em PT-BR: reescrita de artigos da KB do Bradesco em linguagem clara,
    estruturada e padronizada para operadores de atendimento. Instruções: manter todas
    as informações técnicas, adicionar estrutura com títulos e passos numerados quando
    ausente, adaptar para linguagem direta e objetiva (voz ativa), corrigir erros
    ortográficos e gramaticais, preservar termos técnicos do sistema Bradesco
  - `output_schema` com 4 campos: `rewritten_content` (string), `changes_summary` (string),
    `word_count_original` (int), `word_count_rewritten` (int)
  - `validators: [schema]`
  - `sink_type: postgresql`, `sink_config.database_url_env: HELPCORE_DATABASE_URL`,
    `sink_config.table: help_core.rewrites`, `conflict_column: pe_item_id`
  - `cache: { enabled: false }` (reescrita é criativa, não deve ser cacheada)
  - `budget_limit_usd: 50.0`, `max_concurrent: 5`

**Critério de done:**
- `pipelines/helpcore-rewrite.yaml` existe e é YAML válido
- Comentário de aviso Anthropic/Frente 2 presente e proeminente (antes das configurações)
- Fallback OpenAI documentado em bloco comentado
- `cache.enabled: false`
- `llm_provider: anthropic` na configuração ativa

**blockedBy:** nenhum
**[P]** — pode rodar em paralelo com T2.1, T2.2, T2.3

---

## Fase 3: Script de Ingestão

### T3.1 — Criar `scripts/ingest-helpcore.py`
**Arquivos:** `scripts/ingest-helpcore.py` (novo)

**O que fazer:**
- Criar script Python standalone (apenas stdlib + `requests`):
  - `#!/usr/bin/env python3` no topo
  - `argparse` para CLI com argumentos da spec §5:
    - `pasta_txts` (posicional): diretório com arquivos TXT
    - `--pipeline` (default: `helpcore-inventory`)
    - `--batch-size` (default: 200)
    - `--pe-url` (default: `http://localhost:8001`)
    - `--api-key` (default: lê `HC_API_KEY` do env)
    - `--dry-run` (flag booleana)
    - `--ext` (default: `.txt`)
  - Função `read_file_safe(path)`: tenta `utf-8-sig`, fallback `latin-1`
  - Função `ingest_batch(items, pipeline_id, pe_url, api_key)`:
    - `POST /v1/jobs` com `{ pipeline_id, items, skip_cache: false, skip_dedup: false }`
    - Headers: `x-api-key: <api_key>`, `Content-Type: application/json`
    - Retry: até 3 tentativas com backoff exponencial (2s, 4s, 8s) apenas em 5xx
    - Retorna `(success: bool, job_id: str | None, error: str | None)`
  - Função `progress_bar(current, total, width=40)`: imprime barra ASCII
    ex: `[========>           ] 100/500 artigos`
  - Lógica principal:
    - Escanear diretório recursivamente por `*.txt` (ou `--ext`)
    - Construir `source_url = "file://" + path.stem` para cada arquivo
    - `--dry-run`: listar arquivos encontrados e sair sem ingerir
    - Agrupar em batches de `--batch-size`
    - Para cada batch: chamar `ingest_batch()`, atualizar progresso
    - Coletar contadores: `total`, `enviados`, `erros`
  - Relatório final (tabela ASCII):
    ```
    ┌─────────────────────────────────────────┐
    │ RELATÓRIO DE INGESTÃO                    │
    ├──────────────┬──────────────────────────┤
    │ Total        │ 500                      │
    │ Enviados     │ 498                      │
    │ Erros        │ 2                        │
    │ Custo est.   │ ~$0.30 (500 × $0.0006)  │
    └──────────────┴──────────────────────────┘
    ```
  - Exit code: `0` se sem erros, `1` se houver qualquer erro de ingestão

**Critério de done:**
- `python scripts/ingest-helpcore.py --help` mostra todos os argumentos sem erro
- `python scripts/ingest-helpcore.py /tmp --dry-run` roda sem dependências externas
  (além de `requests` que é stdlib-adjacent e disponível no env)
- Encoding fallback implementado: `utf-8-sig` → `latin-1`
- Retry com backoff presente para erros 5xx
- Relatório final impresso após cada execução

**blockedBy:** nenhum (script independente do Docker)

---

## Fase 4: Validação

### T4.1 — Testar `docker-compose up` local (health check)
**Arquivos:** nenhum modificado — validação de runtime

**O que fazer:**
- Copiar `.env.helpcore.example` para `.env.helpcore` e preencher com valores de dev
- Executar: `make -f Makefile.helpcore up`
- Aguardar container saudável (até 60s)
- Validar: `curl -s http://localhost:8001/health` → `{"status": "ok"}` (HTTP 200)
- Validar banco `help_core` criado: `docker compose -f docker-compose.helpcore.yml exec pg-helpcore psql -U postgres -c "\l"` → mostra `help_core` na lista

**Critério de done (A1 da spec):**
- `curl http://localhost:8001/health` retorna HTTP 200
- Banco `help_core` existe no PostgreSQL
- Sem erros de startup nos logs (`make -f Makefile.helpcore logs`)

**blockedBy:** T1.1, T1.2, T1.3, T1.4, T1.5 (toda a Fase 1 deve estar concluída)

---

### T4.2 — Verificar 4 pipelines registrados (A2)
**Arquivos:** nenhum modificado — validação de runtime

**O que fazer:**
- Com instância rodando (T4.1 concluído)
- Executar: `make -f Makefile.helpcore pipelines`
- Verificar que os 4 IDs aparecem na resposta:
  `helpcore-inventory`, `helpcore-dedup`, `helpcore-quality-score`, `helpcore-rewrite`

**Critério de done (A2 da spec):**
- `GET /v1/pipelines` retorna array com 4 itens helpcore
- Nenhum erro 500 no response

**blockedBy:** T4.1, T2.1, T2.2, T2.3, T2.4

---

### T4.3 — Piloto dry-run do script de ingestão (A3)
**Arquivos:** nenhum modificado — validação funcional

**O que fazer:**
- Criar pasta de teste com 5-10 arquivos `.txt` de exemplo (conteúdo dummy mas em PT-BR)
  em `/tmp/hc-sample/` ou usar arquivos TXT reais se disponíveis
- Executar: `python scripts/ingest-helpcore.py /tmp/hc-sample --dry-run`
- Confirmar que lista os arquivos e imprime "0 erros" no relatório final
- (Opcional, se TXTs reais disponíveis) Executar ingestão real com 5 arquivos:
  `python scripts/ingest-helpcore.py /tmp/hc-sample --batch-size 5 --api-key hc-dev-api-key`
  e verificar job criado via `curl http://localhost:8001/v1/jobs`

**Critério de done (A3 da spec):**
- `--dry-run` executa sem erros Python
- Relatório final impresso com `0 erros`
- (Opcional) Job ID retornado se ingestão real executada

**blockedBy:** T3.1, T4.1

---

### T4.4 — Validar sintaxe `docker-stack.helpcore.yml` (A6)
**Arquivos:** nenhum modificado — validação offline

**O que fazer:**
- Executar validação offline do Swarm compose:
  `docker stack config -c docker-stack.helpcore.yml` (ou `docker compose -f docker-stack.helpcore.yml config`)
- Confirmar que nenhum erro de sintaxe ou campo desconhecido é retornado
- Verificar que nomes de serviços, redes e volumes são distintos do `docker-stack.yml` existente
  (grep por `hc-postgres`, `hc-api`, `hc-pgdata`, `hc-net`)

**Critério de done (A6 da spec):**
- `docker stack config` não retorna erro
- Zero colisões de nome com `docker-stack.yml` do VotoLimpo

**blockedBy:** T1.4

---

### T4.5 — Verificar `.env.helpcore.example` documenta todas as variáveis (A4)
**Arquivos:** nenhum modificado — validação de completude

**O que fazer:**
- Extrair todas as variáveis referenciadas em `docker-compose.helpcore.yml` e
  `docker-stack.helpcore.yml` (grepar por `${` e `$_`)
- Comparar com as variáveis documentadas em `.env.helpcore.example`
- Confirmar que nenhuma variável usada nos composes está ausente do example

**Critério de done (A4 da spec):**
- 100% das variáveis usadas nos composes têm entrada no `.env.helpcore.example`
- Todas têm comentário de descrição

**blockedBy:** T1.2, T1.3, T1.4

---

### T4.6 — Verificar Makefile com todos os targets (A5)
**Arquivos:** nenhum modificado — validação de sintaxe

**O que fazer:**
- Executar: `make -f Makefile.helpcore help` → deve listar 8 targets com descrições
- Executar `make -f Makefile.helpcore --dry-run <target>` para cada target:
  `up`, `down`, `logs`, `migrate`, `ingest`, `test-pilot`, `pipelines`, `status`
- Confirmar que nenhum target retorna erro de sintaxe GNU Make

**Critério de done (A5 da spec):**
- `make -f Makefile.helpcore help` lista ≥ 8 targets
- `make --dry-run` de cada target passa sem erro de sintaxe

**blockedBy:** T1.5

---

## Resumo de Dependências

```
T1.1 ──────────────────────────────────────────► T1.3
T1.2 ──────────────────────────────────────────► T1.3
T1.2 ──────────────────────────────────────────► T1.4
T1.3 ──────────────────────────────────────────► T1.5
T1.1 ──┐
T1.2 ──┤
T1.3 ──┤──────────────────────────────────────► T4.1
T1.4 ──┤
T1.5 ──┘
T2.1, T2.2, T2.3, T2.4 (paralelo) ──────────── T4.2 (precisa de T4.1 e todos os YAMLs)
T3.1 (independente) ─────────────────────────── T4.3 (precisa de T3.1 e T4.1)
T1.4 ────────────────────────────────────────── T4.4
T1.2 + T1.3 + T1.4 ──────────────────────────── T4.5
T1.5 ────────────────────────────────────────── T4.6
```

### Ordem sugerida de execução

1. **Em paralelo** (sem dependências entre si): T1.1, T1.2, T2.1, T2.2, T2.3, T2.4, T3.1
2. **Sequencial** (aguardam T1.1 e T1.2): T1.3, T1.4
3. **Sequencial** (aguarda T1.3): T1.5
4. **Validações** (aguardam Fase 1 + Fase 2): T4.1 → T4.2 → T4.3; T4.4, T4.5, T4.6 (paralelo)
