# Spec: Post-Processing Hooks — Pipeline Extensível Pós-LLM

## Objetivo

Adicionar ao Processing Engine um sistema de **post-processing hooks** — plugins
executados APÓS o LLM retornar output validado e ANTES do Sink persistir. Hooks permitem
que cada pipeline defina operações projeto-específicas (score calculation, entity resolution,
graph building, clustering, content generation) sem alterar o engine core.

## IN-SCOPE

1. Novo tipo de plugin `PostProcessor` (Protocol) com interface `process(output, item, conn, config) -> output`
2. Pipeline YAML ganha seção `post_processors: [...]` (lista ordenada de hooks)
3. Hooks são executados em SEQUÊNCIA (output de um é input do próximo)
4. Registry de post-processors (mesmo padrão do registry de plugins existente)
5. 6 post-processors concretos para o pipeline Voto Limpo (implementados como plugins genéricos):
   - `entity_resolver` — resolve nomes de políticos/entidades para IDs via pg_trgm
   - `score_calculator` — calcula veracity score (6 sinais ponderados)
   - `relationship_builder` — constrói grafo de relacionamentos com evidências
   - `milestone_detector` — detecta e dedup marcos jurídicos/políticos
   - `article_matcher` — encontra artigos relacionados (3 sinais)
   - `cluster_updater` — agrupa artigos em "casos" (news clusters)
6. Hook de `content_generator` como cron separado (não inline no pipeline)

## OUT-OF-SCOPE

- Execução paralela de hooks (YAGNI — sequencial é suficiente para MVP)
- Hooks assíncronos com retry independente (retry é do pipeline inteiro)
- Hooks que modificam o output schema (hooks operam sobre o output JÁ validado)
- Content generation inline (bio + AI summary são cron, não hook)

## REMOVIDOS

Nenhum — spec nova.

---

## Arquitetura

### Fluxo atualizado do Orchestrator

```
ingest → dedup → LLM → validate → POST-PROCESS (novo) → sink → log
                                       │
                                       ├─ entity_resolver
                                       ├─ score_calculator
                                       ├─ relationship_builder
                                       ├─ milestone_detector
                                       ├─ article_matcher
                                       └─ cluster_updater
```

### Protocol

```python
@runtime_checkable
class PostProcessor(Protocol):
    async def process(
        self,
        output: dict,           # Output validado do LLM
        item: dict,             # Item original (id, raw_content, source_url, metadata)
        conn: asyncpg.Connection,  # DB connection (mesma transação)
        config: dict,           # Config do hook (vem do pipeline YAML)
    ) -> dict:
        """Processa output e retorna output (possivelmente enriquecido).

        REGRAS:
        - DEVE retornar o output (modificado ou não)
        - PODE adicionar chaves ao output (ex: resolved_politician_ids)
        - NÃO PODE remover chaves existentes
        - PODE fazer writes no DB (INSERT/UPDATE) via conn
        - Exceção = abort do pipeline inteiro (mesmo comportamento de validator)
        """
        ...
```

### Pipeline YAML (seção nova)

```yaml
name: voto-limpo-news-analysis
# ... (ingestor, dedup, llm, validators como antes)

post_processors:
  - type: entity_resolver
    config:
      schema: votolimpo
      politician_table: votolimpo.politicians
      entity_table: votolimpo.entities
      fuzzy_threshold: 0.80
      fuzzy_party_threshold: 0.70
      entity_fuzzy_threshold: 0.85

  - type: score_calculator
    config:
      weights:
        source_reputation: 0.30
        multi_source: 0.25
        narrative_consistency: 0.15
        documental_evidence: 0.10
        temporality: 0.10
        emotional_language: 0.10
      output_field: veracity_score

  - type: relationship_builder
    config:
      relationship_table: votolimpo.relationships
      evidence_table: votolimpo.relationship_evidence

  - type: milestone_detector
    config:
      milestone_table: votolimpo.milestones
      confidence_threshold: 0.70
      dedup_window_days: 7

  - type: article_matcher
    config:
      match_table: votolimpo.article_matches
      weights:
        entity_overlap: 0.40
        keyword_overlap: 0.35
        temporal_proximity: 0.25
      persist_threshold: 0.30
      ui_threshold: 0.50
      multi_source_threshold: 0.70
      window_days: 30

  - type: cluster_updater
    config:
      cluster_table: votolimpo.news_clusters
      cluster_articles_table: votolimpo.cluster_articles
      cluster_politicians_table: votolimpo.cluster_politicians
      similarity_threshold: 0.50
```

---

## Post-Processors Detalhados

### 1. `entity_resolver`

Resolve nomes extraídos pelo LLM para IDs no banco. Usa cascade:
exact match → trigram fuzzy (threshold) → fuzzy + party → create new.

**Input** (do LLM output):
```json
{
  "politicians": [{"name": "Lula", "party": "PT", "state": "SP", ...}],
  "entities": [{"name": "STF", "type": "organization", ...}]
}
```

**Output** (enriquecido):
```json
{
  "politicians": [{"name": "Lula", ..., "resolved_id": 42}],
  "entities": [{"name": "STF", ..., "resolved_id": 108}],
  "resolved_politician_ids": [42],
  "resolved_entity_ids": [108]
}
```

**DB writes**: UPSERT em `politicians` (novo político), UPDATE `search_vector`.

### 2. `score_calculator`

Calcula `veracity_score` a partir dos 6 sinais retornados pelo LLM + source_reputation do banco.

**Input**: `output.veracity_signals` (6 floats do LLM)
**Output**: adiciona `output.veracity_score` (float) e `output.score_components` (dict)
**DB writes**: nenhum (score é persistido pelo Sink junto com o artigo)

### 3. `relationship_builder`

Para cada relationship no output, upsert no grafo com weight incremental + evidência.

**Input**: `output.relationships` + `output.resolved_*_ids`
**Output**: adiciona `output.persisted_relationship_ids`
**DB writes**: UPSERT `relationships` (weight + 1), INSERT `relationship_evidence`

### 4. `milestone_detector`

Para cada milestone com confidence >= threshold, dedup por (politician + type + ±N dias).

**Input**: `output.milestones` + `output.resolved_politician_ids`
**Output**: adiciona `output.persisted_milestone_ids`
**DB writes**: INSERT `milestones` (se não duplicado)

### 5. `article_matcher`

Compara artigo novo contra artigos dos últimos N dias que compartilham políticos.
3 sinais: entity overlap, keyword overlap, temporal proximity.

**Input**: `output.resolved_politician_ids` + `output.keywords` + item metadata
**Output**: adiciona `output.matched_article_ids`
**DB writes**: INSERT/UPDATE `article_matches`

### 6. `cluster_updater`

Agrupa artigos em clusters baseado nos matches de alta similaridade.

**Input**: `output.matched_article_ids`
**Output**: adiciona `output.cluster_id`
**DB writes**: UPSERT `news_clusters`, INSERT `cluster_articles`, UPSERT `cluster_politicians`

---

## Configurable Sink (evolução)

O Sink PostgreSQL atual faz `INSERT (item_id, output)` em JSONB genérico. Para o Voto Limpo,
precisa mapear campos do output para colunas reais.

### Novo `sink_config` com `column_mapping`

```yaml
sink_type: postgresql
sink_config:
  table: votolimpo.articles
  conflict_column: url_hash
  column_mapping:
    # output_field -> db_column
    title: title
    summary: summary
    severity: severity
    veracity_score: veracity_score
    score_components: score_components
    keywords: keywords
    language: language
    is_political: is_political
  static_columns:
    processing_status: completed
  item_field_mapping:
    # item metadata -> db_column
    source_url: source_url
    content_hash: url_hash
  jsonb_fallback: raw_output  # coluna para output completo como JSONB
```

### Lógica do Sink atualizado

```python
async def persist(self, item_id, output, config, conn):
    mapping = config.get("column_mapping")
    if not mapping:
        # Fallback: comportamento atual (item_id + output JSONB)
        return await self._persist_jsonb(item_id, output, config, conn)

    # Build dynamic INSERT com colunas mapeadas
    columns = []
    values = []
    params = []

    for output_key, db_col in mapping.items():
        if output_key in output:
            columns.append(db_col)
            params.append(output[output_key])
            values.append(f"${len(params)}")

    # static_columns (valores fixos)
    for col, val in config.get("static_columns", {}).items():
        columns.append(col)
        params.append(val)
        values.append(f"${len(params)}")

    # item_field_mapping (campos do item, não do output)
    # ... similar

    # jsonb_fallback (output completo)
    if fallback := config.get("jsonb_fallback"):
        columns.append(fallback)
        params.append(json.dumps(output))
        values.append(f"${len(params)}::jsonb")

    # UPSERT
    conflict = config.get("conflict_column", "item_id")
    query = f"""
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({', '.join(values)})
        ON CONFLICT ({conflict}) DO UPDATE SET
            {', '.join(f'{c} = EXCLUDED.{c}' for c in columns if c != conflict)}
    """
    await conn.execute(query, *params)
```

**Backward compatible**: sem `column_mapping`, comportamento atual (JSONB).

---

## Env Prefix Fix

O `config.py` atual NÃO tem `env_prefix`. O docker-stack.yml usa `PE_*`. Fix:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,      # PE_API_KEY → API_KEY
        extra="ignore",
        env_prefix="PE_",          # <-- FIX
    )
```

Com `env_prefix="PE_"`, `PE_API_KEY` → lido como `API_KEY`, `PE_DATABASE_URL` → `DATABASE_URL`.

---

## Cron Jobs (fora do pipeline, mas configurados no PE)

| Cron | Frequência | O que faz |
|------|-----------|-----------|
| `recalculate_scores` | Diário 03:00 UTC | Sigmoid score de todos os políticos |
| `refresh_mvs` | Cada 6h | REFRESH MATERIALIZED VIEW CONCURRENTLY |
| `update_source_reputation` | Semanal dom 04:00 | Recalcula reputation de sources |
| `regenerate_content` | Semanal dom 05:00 | Bio + AI Summary via GPT-4.1-mini |
| `deactivate_clusters` | Diário 04:00 | Marca clusters inativos (>30d sem artigo) |

Crons vivem em `app/crons/` e são registrados no startup do worker. Cada cron é
também configurável via pipeline YAML (seção `crons:`), permitindo que diferentes
projetos definam seus próprios crons.

---

## Aceite

### Post-Processing Hooks
- [ ] A1. Protocol `PostProcessor` definido em `app/plugins/protocols.py`
- [ ] A2. Orchestrator executa hooks em sequência APÓS validate e ANTES de sink
- [ ] A3. Pipeline YAML com `post_processors` é carregado e hooks instanciados
- [ ] A4. Hook que lança exceção aborta o pipeline (mesmo que validator)
- [ ] A5. Output é passado entre hooks em cadeia (output_1 → input_2)

### Entity Resolver
- [ ] A6. Cascade resolve: exact → fuzzy(0.80) → fuzzy+party(0.70) → create
- [ ] A7. Normalização remove acentos e prefixos
- [ ] A8. Entity upsert com fuzzy match (0.85)

### Score Calculator
- [ ] A9. Veracity calculada com 6 sinais ponderados conforme spec
- [ ] A10. Score components JSONB para auditabilidade

### Relationship Builder
- [ ] A11. Relationships com weight incremental em co-ocorrência
- [ ] A12. Evidence linkada ao artigo

### Milestone Detector
- [ ] A13. Milestones com confidence >= threshold detectados
- [ ] A14. Dedup ±7 dias funciona

### Article Matcher
- [ ] A15. 3 sinais calculados corretamente
- [ ] A16. Matches persistidos conforme thresholds

### Cluster Updater
- [ ] A17. Artigos agrupados automaticamente
- [ ] A18. cluster_politicians atualizado

### Configurable Sink
- [ ] A19. column_mapping persiste em colunas individuais (não JSONB genérico)
- [ ] A20. Sem column_mapping: comportamento atual (backward compatible)
- [ ] A21. static_columns e item_field_mapping funcionam

### Env Prefix
- [ ] A22. `PE_API_KEY`, `PE_DATABASE_URL` etc. são lidos corretamente pelo Settings

### Crons
- [ ] A23. 5 crons registrados e executam nos horários definidos
- [ ] A24. Politician score sigmoid produz valores coerentes com calibração
