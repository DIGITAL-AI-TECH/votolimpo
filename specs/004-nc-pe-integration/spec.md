# Spec 004: NC↔PE Integration Fixes

**Status:** Draft
**Priority:** CRITICAL (bloqueador — sem isso o pipeline não funciona)
**Branch:** `fix/004-nc-pe-integration`

## Objetivo

Corrigir os 3 gaps de integração entre News Collector e Processing Engine que impedem o pipeline end-to-end de funcionar.

## Acceptance Checklist

- A1. PE aceita requests nos paths que o NC já usa (`/v1/pool/ingest` e `/v1/pool/ingest/single`)
- A2. `article_id` do `item_metadata` é injetado no `output` antes da PP chain, para que PP5 (article_matcher) e PP6 (cluster_updater) funcionem
- A3. Tabela `politician_articles` é populada pelo sink quando um artigo é associado a políticos
- A4. Testes unitários cobrem todos os 3 fixes
- A5. Testes de integração validam o fluxo NC→PE com payload real

## IN-SCOPE

### Fix 1: Path Alias (A1)

**Problema:** NC chama `POST /v1/pool/ingest` e `POST /v1/pool/ingest/single`. PE só registra `POST /v1/jobs`. Resultado: 404 silencioso.

**Solução:** Adicionar 2 route aliases no PE router (`app/api/routes/jobs.py`) que mapeiam:
- `POST /v1/pool/ingest` → mesma lógica de `POST /v1/jobs` (adapta payload batch NC → formato PE)
- `POST /v1/pool/ingest/single` → mesma lógica (adapta payload single NC → formato PE)

**Adaptação de payload:** O NC envia:
```json
{
  "pipeline_id": "...",
  "source_url": "...",
  "content": "...",
  "content_type": "text/plain",
  "metadata": {"article_id": 42}
}
```
O PE espera:
```json
{
  "pipeline_id": "...",
  "items": [{"source_url": "...", "content": "...", "content_type": "text/plain", "metadata": {"article_id": 42}}]
}
```
O alias `/v1/pool/ingest/single` wrapa o payload single em `items: [...]` e redireciona internamente.
O alias `/v1/pool/ingest` usa o campo `items` diretamente (já é array no NC).

### Fix 2: article_id Injection (A2)

**Problema:** PP5 (`article_matcher`) e PP6 (`cluster_updater`) chamam `output.get("article_id")` e fazem early-return quando é None. Mas `article_id` só é setado pelo sink, que roda DEPOIS da PP chain.

**Solução:** No orchestrator (`app/core/orchestrator.py`), ANTES de iterar a PP chain, injetar `item_metadata["article_id"]` no `output` dict:
```python
# Before PP chain
if "article_id" not in output and item_metadata.get("article_id"):
    output["article_id"] = item_metadata["article_id"]
```

**Arquivo:** `app/core/orchestrator.py` — na função que executa a pipeline, entre o LLM step e o PP chain loop.

### Fix 3: politician_articles Population (A3)

**Problema:** PP5 (`article_matcher`) e o cron `cron_recalculate_scores` fazem JOIN em `votolimpo.politician_articles`, mas ninguém popula essa tabela.

**Solução:** Adicionar lógica no sink (`app/plugins/sinks/__init__.py`) que, após persistir um artigo, insere associações na tabela `politician_articles` baseado nos políticos extraídos pelo LLM:
```sql
INSERT INTO {politician_articles_table} (politician_id, article_id, relevance_score, mentioned_at)
VALUES ($1, $2, $3, NOW())
ON CONFLICT (politician_id, article_id) DO NOTHING
```

**Input:** O output do LLM contém `politicians: [{name, role, resolved_id, ...}]`. Após entity_resolver (PP1), cada político tem `resolved_id`. O sink usa esses IDs + o `article_id` retornado pelo upsert.

**Tabela config:** Via `column_mapping` YAML — adicionar section `politician_articles` com target table e mapeamento.

## OUT-OF-SCOPE

- Mudanças no NC client (o NC não precisa mudar — o PE se adapta)
- Novos endpoints no PE (apenas aliases dos existentes)
- Mudanças no schema do banco (tabela `politician_articles` já existe)

## REMOVIDOS

Nenhum código existente é removido.

## Arquivos Afetados (Whitelist)

| Arquivo | Mudança |
|---------|---------|
| `processing-engine/app/api/routes/jobs.py` | Adicionar 2 route aliases + payload adapter |
| `processing-engine/app/core/orchestrator.py` | Injetar article_id no output antes da PP chain |
| `processing-engine/app/plugins/sinks/__init__.py` | Adicionar politician_articles population após persist |
| `processing-engine/tests/test_routes_ingest_alias.py` | Testes dos aliases |
| `processing-engine/tests/test_article_id_injection.py` | Testes da injeção |
| `processing-engine/tests/test_politician_articles_sink.py` | Testes da population |
