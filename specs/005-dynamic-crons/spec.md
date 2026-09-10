# Spec 005: Dynamic Cron System

**Status:** Draft
**Priority:** HIGH
**Branch:** `feature/005-dynamic-crons`

## Objetivo

Tornar o sistema de crons do Processing Engine dinâmico — lendo definições do YAML pipeline config em vez de hardcodar funções — e implementar o cron `update_source_reputation` que está faltando.

## Acceptance Checklist

- A1. Crons são registrados dinamicamente a partir de `PipelineConfig.crons` do YAML
- A2. Os 5 crons existentes continuam funcionando com a mesma schedule
- A3. `update_source_reputation` é implementado e registrado
- A4. Crons novos podem ser adicionados via YAML sem mudar código Python
- A5. Testes cobrem registro dinâmico, execução, e fallback para crons hardcoded

## IN-SCOPE

### 1. Refactor do Scheduler (A1, A2)

**Problema:** `setup_cron_scheduler()` em `app/cron/__init__.py` hardcoda 5 funções com `_scheduler.add_job()`. O `PipelineConfig.crons` é parseado mas ignorado.

**Solução:**
1. Criar registry de cron functions: `CRON_REGISTRY: dict[str, Callable]` que mapeia `cron_id` → função
2. `setup_cron_scheduler()` itera `PipelineConfig.crons` e registra via registry lookup
3. Fallback: se não houver crons no YAML, usa os 5 hardcoded (backward compat)

```python
CRON_REGISTRY = {
    "pe_scores": cron_recalculate_scores,
    "pe_mvs": cron_refresh_mvs,
    "pe_content": cron_regenerate_content,
    "pe_cleanup": cron_cleanup_logs,
    "pe_clusters": cron_deactivate_stale_clusters,
    "pe_source_reputation": cron_update_source_reputation,
}

def setup_cron_scheduler(pipeline_configs: list[PipelineConfig]) -> AsyncIOScheduler:
    for config in pipeline_configs:
        for cron in config.crons:
            fn = CRON_REGISTRY.get(cron.id)
            if fn:
                _scheduler.add_job(fn, CronTrigger.from_crontab(cron.schedule), id=cron.id)
```

### 2. Implementar update_source_reputation (A3)

**Função:** Atualiza a reputação de fontes (RSS feeds, sites) baseado na qualidade dos artigos coletados.

```python
async def cron_update_source_reputation():
    """Recalcula reputation score de cada source baseado em:
    - Taxa de artigos válidos vs rejeitados (validator)
    - Média de scores dos artigos (score_calculator)
    - Frequência de duplicatas
    - Recência (decay factor)
    """
```

**Tabela:** `votolimpo.sources` — campo `reputation_score` (FLOAT, 0.0-1.0).

**Query:**
```sql
UPDATE {sources_table} SET reputation_score = (
    SELECT COALESCE(
        0.4 * (valid_count::float / NULLIF(total_count, 0)) +
        0.3 * avg_score +
        0.2 * (1.0 - dup_rate) +
        0.1 * recency_factor,
        0.5  -- default
    )
    FROM (
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') as valid_count,
            COUNT(*) as total_count,
            AVG(score) as avg_score,
            COUNT(*) FILTER (WHERE is_duplicate) / NULLIF(COUNT(*)::float, 0) as dup_rate,
            EXTRACT(EPOCH FROM NOW() - MAX(created_at)) / 86400.0 as days_since_last
        FROM {articles_table}
        WHERE source_id = {sources_table}.id
        AND created_at > NOW() - INTERVAL '30 days'
    ) stats
) WHERE id IN (SELECT DISTINCT source_id FROM {articles_table} WHERE created_at > NOW() - INTERVAL '30 days')
```

### 3. YAML Config Extension (A4)

Garantir que o YAML pipeline config suporta definição completa de crons:
```yaml
crons:
  - id: pe_scores
    schedule: "0 3 * * *"
    description: "Recalculate politician scores"
  - id: pe_source_reputation
    schedule: "0 5 * * *"
    description: "Update source reputation scores"
```

## OUT-OF-SCOPE

- Novos crons além de `update_source_reputation`
- UI para gerenciar crons
- Mudanças no APScheduler (continua usando AsyncIOScheduler)

## REMOVIDOS

- Hardcoded `_scheduler.add_job()` calls são removidos em favor do registry dinâmico (com fallback backward-compat)

## Arquivos Afetados (Whitelist)

| Arquivo | Mudança |
|---------|---------|
| `processing-engine/app/cron/__init__.py` | Registry + dynamic registration + update_source_reputation |
| `processing-engine/app/core/orchestrator.py` | Passar pipeline_configs para setup_cron_scheduler |
| `processing-engine/tests/test_cron_dynamic.py` | Testes do registro dinâmico |
| `processing-engine/tests/test_cron_source_reputation.py` | Testes do novo cron |
