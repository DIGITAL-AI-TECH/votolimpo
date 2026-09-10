# Implementation Plan: 003 — Post-Processing Hooks

**Branch**: `feature/003-post-processing-hooks` | **Date**: 2026-09-09 | **Spec**: `specs/003-post-processing-hooks/spec.md`

## Summary

Extrair a logica de pos-processamento (entity resolution, scoring, relationships,
milestones, article matching, clustering) que HOJE vive monolitica dentro do
`PostgreSQLSink` para um sistema de **PostProcessor plugins** generico e configuravel
via pipeline YAML. Adicionar suporte a `column_mapping` no Sink e sistema de crons
configuraveis.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, asyncpg, httpx, openai, pydantic, pydantic-settings, PyYAML
**Storage**: PostgreSQL 16 (pgvector, pg_trgm)
**Testing**: pytest + pytest-asyncio + testcontainers
**Target Platform**: Linux Docker Swarm
**Project Type**: Single service (API + Worker)
**Performance Goals**: <2s per item processing, 500 items/day budget
**Constraints**: <$10/month LLM, PostgreSQL-only (no Redis/Rabbit)

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Transparencia Radical | OK | Post-processors preservam source_url e proveniencia |
| II. Anti-Reprocessamento | OK | Sem mudanca — dedup permanece no orchestrator |
| III. Custo Controlado | OK | Nenhum post-processor chama LLM (exceto cron content_gen) |
| IV. Dados > Opiniao | OK | Score calculator usa pesos explicitos, nao editorial |
| V. Idempotencia Total | OK | Todos os post-processors usam ON CONFLICT/UPSERT |
| VI. Schema First | OK | ENUMs e constraints mantidos, column_mapping mapeia para colunas tipadas |
| VII. Anti-Alucinacao | OK | Validators permanecem ANTES dos post-processors |
| VIII. Stack Minima | OK | Nenhuma dependencia nova. Mesmo PostgreSQL |
| IX. Open Source | OK | Tudo generico, nada proprietario |
| X. Testabilidade | OK | Cada post-processor testavel isoladamente com fixture |

**GATE: PASSED** — nenhuma violacao.

## Research Findings

### R1. Decisao: Extrair vs Reescrever o Sink

**Decision**: EXTRAIR — mover metodos do PostgreSQLSink para PostProcessors individuais.
**Rationale**: O sink atual (`app/plugins/sinks/__init__.py`, 536 linhas) ja implementa
toda a logica de entity resolution, scoring, milestones, matching, clustering. O codigo
esta funcional e testado. Extrair metodo por metodo para plugins separados minimiza risco.
**Alternative rejected**: Reescrever do zero — risco de regressao, trabalho duplicado.

### R2. Decisao: PostProcessor recebe `conn` da mesma transacao ou separada?

**Decision**: SEPARADA — cada post-processor recebe `pool` (nao `conn`), adquire sua
propria conexao. Post-processors que fazem writes usam suas proprias transacoes.
**Rationale**: O pattern atual do orchestrator (C2 fix) ja usa acquire/release curtos.
Post-processors que fazem writes pesados (entity_resolver, relationship_builder)
precisam de transacao propria para nao segurar a conexao da pipeline inteira.
**Alternative rejected**: Mesma transacao — risco de deadlock com semaforo de concurrencia.

### R3. Decisao: column_mapping OU manter mappings existentes?

**Decision**: Manter AMBOS — column_mapping e novo, mappings e backward-compat.
**Rationale**: O sink atual usa `mappings: [{source_path, target_table, strategy}]` e
funciona. Adicionar `column_mapping` como alternativa permite pipelines novos usarem o
formato mais simples sem quebrar pipelines existentes.

### R4. Decisao: Crons como plugin ou modulo separado?

**Decision**: Modulo separado em `app/crons/` com registry proprio, registrado no startup.
**Rationale**: Crons nao fazem parte do pipeline de processamento (nao sao hooks).
Executam em schedule fixo (APScheduler ou asyncio loop). Configuracao no YAML e opcional.

### R5. Ordenacao dos Post-Processors

A ordem definida no YAML e a ordem de execucao. Isso e critico:
1. entity_resolver PRIMEIRO (resolve IDs que os outros usam)
2. score_calculator SEGUNDO (precisa de IDs resolvidos para source lookup)
3. relationship_builder (precisa de resolved IDs)
4. milestone_detector (precisa de resolved politician IDs)
5. article_matcher (precisa de resolved IDs + keywords)
6. cluster_updater (precisa de matched articles)

## Project Structure

### Documentation (this feature)

```text
specs/003-post-processing-hooks/
├── plan.md              # This file
├── spec.md              # Feature specification
└── tasks.md             # Task decomposition (next step)
```

### Source Code — Files to CREATE

```text
app/plugins/post_processors/
├── __init__.py          # PostProcessor Protocol + registry + get_post_processor()
├── entity_resolver.py   # Extract from sink._resolve_politicians + _upsert_entities
├── score_calculator.py  # Extract from sink._update_veracity
├── relationship_builder.py  # Extract from sink._upsert_entities (relationship part)
├── milestone_detector.py    # Extract from sink._detect_milestones
├── article_matcher.py       # Extract from sink._match_article
└── cluster_updater.py       # Extract from sink._update_clusters

app/crons/
├── __init__.py          # CronRegistry + scheduling
├── score_recalculator.py    # Sigmoid politician scores
├── mv_refresher.py          # REFRESH MATERIALIZED VIEW
├── source_reputation.py     # Source reputation recalc
├── content_generator.py     # Bio + AI Summary via LLM
└── cluster_cleanup.py       # Deactivate stale clusters

tests/
├── test_post_processors.py  # Unit tests for all 6 post-processors
├── test_configurable_sink.py # Tests for column_mapping
└── test_crons.py            # Tests for cron jobs
```

### Source Code — Files to MODIFY

```text
app/core/pipeline_config.py  # Add PostProcessorEntry, CronEntry to PipelineConfig
app/core/orchestrator.py     # Add post-processing step between validate and sink
app/plugins/sinks/__init__.py # Slim down: remove extracted logic, add column_mapping
app/main.py                  # Register crons on startup
```

### Files NOT touched (whitelist boundary)

```text
app/config.py                # env_prefix already OK
app/api/                     # No API changes
app/plugins/dedup/           # No changes
app/plugins/ingestors/       # No changes
app/plugins/llm/             # No changes
app/plugins/validators/      # No changes
app/storage/                 # No changes
migrations/                  # No new migrations (votolimpo schema managed externally)
```

## Architecture: Post-Processing Flow

```
orchestrator._process_single_item():
  1. ingest → clean_content
  2. dedup check
  3. LLM process → output
  4. validate
  5. NEW: post-process (sequencial)
     │  for pp in pipeline.post_processors:
     │    processor = get_post_processor(pp.type)
     │    output = await processor.process(output, item_metadata, pool, pp.config)
  6. sink.persist(output, ...) — agora slim (column_mapping ou legacy mappings)
```

Post-processors recebem `pool` (nao `conn`) e adquirem conexoes curtas internamente.
Output e passado em cadeia: cada post-processor pode ADICIONAR chaves mas NAO remover.

## Architecture: Configurable Sink

```python
# Se tem column_mapping → INSERT dinamico com colunas mapeadas
# Se tem mappings (legacy) → comportamento atual (strategy-based)
# Se nenhum → fallback JSONB generico (item_id + output)
```

Prioridade: `column_mapping` > `mappings` > fallback JSONB.

## Architecture: Crons

```python
# app/crons/__init__.py
CRON_REGISTRY = {
    "recalculate_scores": ScoreRecalculator,
    "refresh_mvs": MVRefresher,
    "update_source_reputation": SourceReputation,
    "regenerate_content": ContentGenerator,
    "deactivate_clusters": ClusterCleanup,
}

# Registrado no startup via app/main.py
# Execucao: asyncio.create_task com sleep loop (sem APScheduler — stack minima)
```

## Complexity Tracking

Nenhuma violacao de constitution. Nenhuma tecnologia nova adicionada.
