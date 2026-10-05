---
type: plan
title: "Plan — Frente 1: PE Help Core Instance"
created: 2026-10-05
tags: [help-core, config, plan]
---

# Plan — Frente 1: PE Help Core Instance

## Arquitetura

### Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEV LOCAL (docker-compose.helpcore.yml)       │
│                                                                  │
│  ┌────────────────────────────┐   ┌──────────────────────────┐  │
│  │       pe-helpcore           │   │       pg-helpcore         │  │
│  │  (imagem do PE existente)  │   │   (pgvector/pgvector:     │  │
│  │  PORT: 8001→8000           │◄──│    pg16)                 │  │
│  │  bind-mount: ./pipelines   │   │   PORT: 5434→5432         │  │
│  │  .env.helpcore (gitignore) │   │   DB: processing_engine   │  │
│  └────────────────────────────┘   │   DB: help_core (via      │  │
│                                   │    init-helpcore.sql)      │  │
│                                   └──────────────────────────┘  │
│                                                                  │
│  4 pipelines carregados via bind-mount (hot-reload sem rebuild)  │
│  helpcore-inventory / dedup / quality-score / rewrite            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│               PRODUÇÃO SWARM (docker-stack.helpcore.yml)         │
│                                                                  │
│  rede externa: oraculusnet ◄─── Traefik                          │
│       ↓                     pe-helpcore.digital-ai.tech          │
│  ┌──────────────┐           (router: processing-engine-helpcore) │
│  │   hc-api     │                                                │
│  │ replicas: 1  ├──────── rede interna: hc-net (overlay)        │
│  │ mem: 1G/512M │                    │                           │
│  └──────────────┘                    │                           │
│                           ┌──────────▼─────────┐                │
│                           │     hc-postgres     │                │
│                           │  replicas: 1        │                │
│                           │  mem: 2G/512M       │                │
│                           │  vol: hc-pgdata      │                │
│                           │  node: oraculus-     │                │
│                           │   server-2          │                │
│                           └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              INGESTÃO (scripts/ingest-helpcore.py)               │
│                                                                  │
│  ./pasta_txts/*.txt                                             │
│       │ parse + encoding (utf-8-sig → latin-1)                  │
│       │ batches de 200 artigos                                   │
│       ▼                                                         │
│  POST http://localhost:8001/v1/jobs                             │
│  { pipeline_id, items: [{content, source_url, metadata}] }      │
│       │                                                         │
│       ▼                                                         │
│  PE processa → sink → help_core.inventory (ou tabela do pipe)   │
└─────────────────────────────────────────────────────────────────┘
```

### Volumes e Redes (dev local)

| Recurso | Nome | Tipo | Uso |
|---------|------|------|-----|
| Volume PG | `hc-pgdata` (named) | Docker named | Persistência local dos dados |
| Bind-mount | `./pipelines:/app/pipelines:ro` | Read-only | Hot-reload dos YAMLs sem rebuild |
| Bind-mount | `./scripts/init-helpcore.sql:/docker-entrypoint-initdb.d/init.sql` | Read-only | Cria DB `help_core` no primeiro boot |
| Rede | `hc-net` | bridge (local) / overlay (Swarm) | Comunicação interna PE ↔ PG |

### Portas (evitar conflito com instância VotoLimpo)

| Serviço | Local (helpcore) | VotoLimpo (existente) | Motivo |
|---------|-----------------|----------------------|--------|
| PE API | `8001` | `8000` | Evita conflito se ambos rodarem juntos |
| PostgreSQL | `5434` | `5432` | Evita conflito de porta local |

---

## Data Model

### Schema `help_core` (criado via migrations — Frente 2)

Os pipelines desta Frente 1 fazem sink para tabelas no schema `help_core`. As migrations
são responsabilidade da Frente 2, mas o plan documenta o schema esperado para referência
e para validar o `column_mapping` dos YAMLs.

#### `help_core.inventory`
| Coluna | Tipo | Fonte |
|--------|------|-------|
| `pe_item_id` | TEXT PK | PE item ID (conflict_column) |
| `source_url` | TEXT | item_field_mapping.source_url |
| `title` | TEXT | item_field_mapping.title |
| `doc_type` | TEXT | LLM output |
| `category` | TEXT | LLM output |
| `subcategory` | TEXT | LLM output |
| `target_audience` | TEXT | LLM output |
| `quality_score` | NUMERIC | LLM output |
| `completeness_score` | NUMERIC | LLM output |
| `key_topics` | TEXT[] | LLM output (array) |
| `summary` | TEXT | LLM output |
| `requires_update` | BOOLEAN | LLM output |
| `metadata` | JSONB | jsonb_fallback (tudo que não foi mapeado) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() |

#### `help_core.dedup_results`
| Coluna | Tipo | Fonte |
|--------|------|-------|
| `pe_item_id` | TEXT PK | PE item ID |
| `source_url` | TEXT | item metadata |
| `is_duplicate` | BOOLEAN | LLM output |
| `duplicate_of` | TEXT NULL | LLM output — source_url do autoritativo |
| `similarity_score` | NUMERIC | LLM output |
| `reason` | TEXT | LLM output |
| `metadata` | JSONB | jsonb_fallback |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |

#### `help_core.quality_scores`
| Coluna | Tipo | Fonte |
|--------|------|-------|
| `pe_item_id` | TEXT PK | PE item ID (conflict_column) |
| `source_url` | TEXT | item metadata |
| `clarity` | NUMERIC | LLM output |
| `structure` | NUMERIC | LLM output |
| `completeness` | NUMERIC | LLM output |
| `accuracy_signals` | NUMERIC | LLM output |
| `readability` | NUMERIC | LLM output |
| `overall_score` | NUMERIC | LLM output |
| `improvement_suggestions` | TEXT[] | LLM output (array) |
| `metadata` | JSONB | jsonb_fallback |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() |

#### `help_core.rewrites`
| Coluna | Tipo | Fonte |
|--------|------|-------|
| `pe_item_id` | TEXT PK | PE item ID (conflict_column) |
| `source_url` | TEXT | item metadata |
| `rewritten_content` | TEXT | LLM output |
| `changes_summary` | TEXT | LLM output |
| `word_count_original` | INTEGER | LLM output |
| `word_count_rewritten` | INTEGER | LLM output |
| `metadata` | JSONB | jsonb_fallback |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() |

---

## Decisões Técnicas

### 1. Por que `docker-compose.helpcore.yml` separado (não o existente do VotoLimpo)

O `docker-compose.yml` existente usa serviços chamados `postgres` e `api`. Se sobrescrito,
derruba a instância VotoLimpo. A nova instância usa nomes completamente distintos
(`pe-helpcore`, `pg-helpcore`) e portas diferentes (`8001`, `5434`), permitindo que ambas
rodem simultaneamente no mesmo host de desenvolvimento.

Benefício adicional: permite commit do `docker-compose.helpcore.yml` sem risco de
afetar CI/CD do VotoLimpo (que usa o compose existente nos testes).

### 2. Por que porta 8001 (PE) e 5434 (PG)

Instância VotoLimpo já ocupa `8000` (PE) e `5432` (PG). Se o desenvolvedor precisar
rodar ambas ao mesmo tempo (comparar comportamento, depurar), há colisão de porta.
`8001` e `5434` são convencionalmente "instância +1" e fáceis de lembrar.

### 3. Estratégia de hot-reload dos YAMLs via bind-mount

O PE carrega pipelines no startup via `load_pipelines()` que lê `./pipelines/*.yaml`.
Com bind-mount `./pipelines:/app/pipelines:ro`, qualquer edição nos YAMLs locais fica
visível dentro do container sem rebuild.

**Caveat**: o PE carrega pipelines na inicialização — editar um YAML exige
`docker compose restart pe-helpcore` para recarregar. Não é um reload automático em
tempo real, mas evita o ciclo de `docker build` a cada ajuste de prompt.

### 4. Encoding strategy para TXTs brasileiros

Artigos da KB do Bradesco são TXTs gerados possivelmente em Windows (CP1252/latin-1)
ou exportados com BOM (utf-8-sig). O script tenta `utf-8-sig` primeiro (cobre UTF-8 com
e sem BOM), fazendo fallback para `latin-1` em caso de erro de decode. Latin-1 nunca
lança UnicodeDecodeError — cobre o pior caso de arquivos legados.

### 5. `VOTOLIMPO_DATABASE_URL` → `HELPCORE_DATABASE_URL` no helpcore-inventory.yaml

O campo `sink_config.database_url_env` indica qual env var o PE lê para conectar ao
banco de destino. A instância Help Core não define `VOTOLIMPO_DATABASE_URL` (que aponta
pro banco votolimpo do VotoLimpo). Renomear para `HELPCORE_DATABASE_URL` desacopla as
instâncias e evita que um `.env` mal configurado grave dados no banco errado.

A mudança é não-breaking: a variável só é lida em runtime pela instância que tem o
pipeline ativo. A instância VotoLimpo não registra os pipelines `helpcore-*` (eles não
estão no repertório de pipelines seeded para o VotoLimpo).

### 6. `helpcore-rewrite.yaml` com fallback OpenAI

O pipeline de reescrita idealmente usa Anthropic (Claude Sonnet) — melhor qualidade para
reescrita criativa em português. Porém, o suporte nativo Anthropic no PE é Frente 2.
O YAML será entregue já com `llm_provider: anthropic` (configuração-alvo), mas com
bloco comentado mostrando o fallback `llm_provider: openai` + `gpt-4.1` para uso
imediato. O DevOps pode trocar a linha antes do deploy até a Frente 2 estar disponível.

### 7. `init-helpcore.sql` e comportamento do PostgreSQL no Docker

O PostgreSQL oficial executa scripts em `/docker-entrypoint-initdb.d/` **apenas se o
data directory estiver vazio** (primeiro boot). Se o volume já existe, o script é
ignorado silenciosamente. Documentar no Makefile que `make -f Makefile.helpcore down -v`
(com `-v` para remover volumes) é necessário para recriar o banco do zero.

### 8. Sem `Makefile` existente no PE

O repositório não tem Makefile principal. O `Makefile.helpcore` é criado como arquivo
independente sem risco de colisão. O nome explícito `-f Makefile.helpcore` torna
intencional a invocação, evitando execução acidental.

---

## Whitelist de Arquivos

### Criar (novos — 9 arquivos)

```
processing-engine/
├── docker-compose.helpcore.yml        ← Dev local (PE + PG, portas 8001/5434)
├── docker-stack.helpcore.yml          ← Produção Swarm (hc-api + hc-postgres)
├── .env.helpcore.example              ← Template documentado (gitignored: .env.helpcore)
├── Makefile.helpcore                  ← 8 targets (up/down/logs/migrate/ingest/...)
├── scripts/
│   ├── ingest-helpcore.py             ← Script standalone (stdlib + requests)
│   └── init-helpcore.sql              ← CREATE DATABASE help_core
└── pipelines/
    ├── helpcore-dedup.yaml            ← Pipeline dedup de artigos KB
    ├── helpcore-quality-score.yaml    ← Pipeline scoring multi-dimensional
    └── helpcore-rewrite.yaml          ← Pipeline reescrita (Anthropic alvo / OpenAI fallback)
```

### Modificar (existentes — 1 arquivo)

```
processing-engine/
└── pipelines/
    └── helpcore-inventory.yaml        ← sink_config.database_url_env: HELPCORE_DATABASE_URL
                                         budget_limit_usd: 50.0 (era 100.0)
```

### Não tocar (intocáveis)

```
processing-engine/
├── app/                               ← Zero mudanças de código Python
├── docker-compose.yml                 ← Instância VotoLimpo
├── docker-stack.yml                   ← Instância VotoLimpo
├── .env / .env.example                ← VotoLimpo
└── pipelines/voto-limpo-news-analysis.yaml
```

---

## Referências

| Arquivo | Papel no Plan |
|---------|---------------|
| `docker-compose.yml` | Template base — copiar estrutura, renomear serviços, ajustar portas |
| `docker-stack.yml` | Template base — copiar labels Traefik, ajustar router/hostname/redes |
| `pipelines/helpcore-inventory.yaml` | Referência de formato; será atualizado (database_url_env + budget) |
| `pipelines/voto-limpo-news-analysis.yaml` | Referência de formato completo (dedup composite, validators, cache) |
