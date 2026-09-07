# Arquitetura: Pool de Ingestao Desacoplada

**Autor**: HOMELAND (review arquitetural)
**Data**: 2026-09-07
**Status**: PROPOSTA — aguardando validacao do Matheus antes de implementar
**Branch futura**: `002-pool-architecture`

---

## 1. Diagnostico do Estado Atual

Hoje, o acoplamento entre coleta e processamento acontece em um unico ponto:
`POST /v1/jobs`. O coletor (quem quer que seja) precisa:

1. Conhecer a API do engine
2. Montar o payload completo com `pipeline_id` + array de `items` (content, source_url, content_type, metadata)
3. Chamar POST /v1/jobs — que cria job + items atomicamente
4. O worker pega o job via SKIP LOCKED e processa

O problema: o coletor esta OBRIGADO a criar jobs. Ele define quantos itens vao em cada job, qual a prioridade, se pula cache. Isso mistura responsabilidades — o coletor deveria apenas dizer "aqui tem dado novo, processa isso".

Alem disso, se o coletor falhar no meio do envio de um batch de 200 itens, nao tem como "retomar de onde parou" — precisa reenviar tudo.

---

## 2. Arquitetura Proposta: Pool + Auto-Batching

```
                                                    PROCESSING ENGINE
                                                    (container unico)
                                                    +-----------------+
+------------------+                                |                 |
|  VotoLimpo       |---+                            |   API (FastAPI) |
|  Scraper         |   |                            |                 |
|  (Firecrawl 4x)  |   |    POST /v1/pool/ingest   |   +----------+  |
+------------------+   +---------------------------->|   | pool     |  |
                       |                            |   | (tabela) |  |
+------------------+   |                            |   +----+-----+  |
|  Help Core       |---+                            |        |        |
|  File Importer   |                                |   Auto-Batcher  |
|  (batch upload)  |                                |   (cria jobs    |
+------------------+                                |    da pool)     |
                                                    |        |        |
+------------------+                                |   +----v-----+  |
|  Futuro Coletor  |---+                            |   | jobs     |  |
|  (qualquer)      |   |                            |   | (tabela) |  |
+------------------+   |                            |   +----+-----+  |
                       |   POST /v1/pool/ingest     |        |        |
                       +---------------------------->|   Worker        |
                                                    |   (SKIP LOCKED) |
+------------------+                                |        |        |
|  Webhook externo |---+                            |   +----v-----+  |
|  (n8n, Zapier)   |   |   POST /v1/pool/ingest    |   | Pipeline |  |
+------------------+   +---------------------------->|   | Executor |  |
                                                    |   +----+-----+  |
                                                    |        |        |
                                                    |   Sink (persist)|
                                                    +-----------------+
```

### Principio fundamental

**O coletor NAO cria jobs. O coletor deposita itens na pool. O engine decide como agrupar e processar.**

---

## 3. Schema SQL da Pool

```sql
-- Nova tabela: pool de ingestao
CREATE TABLE processing_engine.pool (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),

    -- Conteudo bruto
    source_url      TEXT,
    content         TEXT,
    content_type    TEXT NOT NULL DEFAULT 'text/plain',
    metadata        JSONB DEFAULT '{}',

    -- Hashes pre-computados pelo coletor OU pelo endpoint de ingestao
    url_hash        TEXT,
    content_hash    TEXT,

    -- Controle
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'claimed', 'duplicate_rejected')),
    priority        INTEGER NOT NULL DEFAULT 0,

    -- Rastreabilidade: quem enviou
    source_id       TEXT,          -- identificador do coletor (ex: "votolimpo-scraper", "helpcore-importer")
    batch_ref       TEXT,          -- referencia do batch do coletor (para debug/rastreio)

    -- Depois de claimed, referencia ao job criado
    job_id          UUID REFERENCES processing_engine.jobs(id),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index para o auto-batcher pegar itens pendentes por pipeline
CREATE INDEX idx_pool_pending
    ON processing_engine.pool (pipeline_id, priority DESC, created_at)
    WHERE status = 'pending';

-- Index para dedup rapido na pool (rejeitar duplicatas antes de processar)
CREATE INDEX idx_pool_url_hash
    ON processing_engine.pool (url_hash, pipeline_id)
    WHERE url_hash IS NOT NULL AND status != 'duplicate_rejected';

CREATE INDEX idx_pool_content_hash
    ON processing_engine.pool (content_hash, pipeline_id)
    WHERE content_hash IS NOT NULL AND status != 'duplicate_rejected';

-- Index para rastreio por source
CREATE INDEX idx_pool_source
    ON processing_engine.pool (source_id, created_at DESC)
    WHERE source_id IS NOT NULL;
```

---

## 4. Contrato de Entrada (API de Ingestao na Pool)

### 4.1 Endpoint: `POST /v1/pool/ingest`

Deposita 1 ou mais itens na pool para processamento futuro.

**Request:**
```json
{
  "pipeline_id": "uuid-do-pipeline",
  "source_id": "votolimpo-scraper",
  "batch_ref": "scrape-2026-09-07-14h",
  "priority": 0,
  "items": [
    {
      "source_url": "https://example.com/page1",
      "content": "<html>...</html>",
      "content_type": "text/html",
      "metadata": {
        "scraped_at": "2026-09-07T14:00:00Z",
        "depth": 1
      }
    },
    {
      "source_url": "https://example.com/page2",
      "content": "Texto extraido do PDF...",
      "content_type": "text/plain",
      "metadata": {}
    }
  ]
}
```

**Campos obrigatorios:**
| Campo | Tipo | Descricao |
|-------|------|-----------|
| `pipeline_id` | UUID | Pipeline que vai processar esses itens |
| `items` | array | 1 a 500 itens por request |
| `items[].content` | string | Conteudo bruto (texto, HTML, JSON). Pelo menos `content` OU `source_url` obrigatorio |

**Campos opcionais:**
| Campo | Tipo | Default | Descricao |
|-------|------|---------|-----------|
| `source_id` | string | null | Identificador do coletor (para rastreio) |
| `batch_ref` | string | null | Referencia do batch no coletor (para debug) |
| `priority` | int | 0 | Prioridade (maior = processa antes) |
| `items[].source_url` | string | null | URL de origem |
| `items[].content_type` | string | "text/plain" | MIME type |
| `items[].metadata` | object | {} | Metadados livres do coletor |

**Response (201 Created):**
```json
{
  "accepted": 8,
  "rejected": 2,
  "pool_ids": [
    "uuid-1", "uuid-2", "uuid-3", "uuid-4",
    "uuid-5", "uuid-6", "uuid-7", "uuid-8"
  ],
  "rejections": [
    {
      "index": 3,
      "reason": "duplicate_url",
      "existing_pool_id": "uuid-existente"
    },
    {
      "index": 7,
      "reason": "duplicate_url",
      "existing_pool_id": "uuid-existente-2"
    }
  ]
}
```

**Comportamento:**
- O endpoint faz dedup IMEDIATO na pool: se `url_hash` ja existe para o mesmo `pipeline_id` com status != `duplicate_rejected`, rejeita o item com `duplicate_url`.
- Itens aceitos entram com status `pending`.
- NAO cria job. O auto-batcher cuida disso.
- Operacao atomica: ou todos os aceitos entram, ou nenhum (transacao).

### 4.2 Endpoint: `POST /v1/pool/ingest/single`

Atalho para depositar 1 item (sem wrapper de array). Util para webhooks.

**Request:**
```json
{
  "pipeline_id": "uuid-do-pipeline",
  "source_id": "n8n-webhook",
  "source_url": "https://example.com/page",
  "content": "Conteudo...",
  "content_type": "text/html",
  "metadata": {}
}
```

**Response (201):**
```json
{
  "pool_id": "uuid-do-item-na-pool",
  "status": "accepted"
}
```

**Response (409 Conflict) se duplicata:**
```json
{
  "pool_id": null,
  "status": "duplicate",
  "existing_pool_id": "uuid-existente",
  "reason": "duplicate_url"
}
```

### 4.3 Endpoint: `GET /v1/pool/status`

Consulta o estado da pool (para dashboards/monitoring).

**Response:**
```json
{
  "pending_total": 47,
  "by_pipeline": [
    {
      "pipeline_id": "uuid-votolimpo",
      "pipeline_name": "VotoLimpo Analyzer",
      "pending": 35,
      "oldest_pending": "2026-09-07T13:45:00Z"
    },
    {
      "pipeline_id": "uuid-helpcore",
      "pipeline_name": "Help Core Processor",
      "pending": 12,
      "oldest_pending": "2026-09-07T14:10:00Z"
    }
  ]
}
```

---

## 5. Mecanismo de Consumo: Auto-Batcher

O Auto-Batcher e um background task (igual ao Worker atual) que:

1. **Poll periodico** (ex: a cada 5s)
2. Para cada pipeline com itens `pending` na pool:
   - Pega ate N itens (configuravel por pipeline, default 50)
   - Usa `FOR UPDATE SKIP LOCKED` para evitar concorrencia
   - Cria um job automaticamente com esses itens
   - Move os itens da pool para a tabela `items` (vinculados ao job)
   - Marca os itens da pool como `claimed` com referencia ao `job_id`
3. O Worker existente (SKIP LOCKED em jobs) pega o job e processa normalmente

```
Pool (pending)
    |
    | Auto-Batcher (poll 5s)
    |   - FOR UPDATE SKIP LOCKED
    |   - Agrupa por pipeline_id
    |   - Cria job + items
    v
Jobs (queued)
    |
    | Worker (poll 1s) — INALTERADO
    |   - FOR UPDATE SKIP LOCKED
    v
Pipeline Executor — INALTERADO
    |
    v
Sink (persist)
```

### SQL do Auto-Batcher

```sql
-- Claim N itens pendentes de um pipeline (atomico)
WITH claimed AS (
    SELECT id FROM processing_engine.pool
    WHERE pipeline_id = $1 AND status = 'pending'
    ORDER BY priority DESC, created_at ASC
    LIMIT $2
    FOR UPDATE SKIP LOCKED
)
UPDATE processing_engine.pool p
SET status = 'claimed', job_id = $3
FROM claimed
WHERE p.id = claimed.id
RETURNING p.*
```

### Configuracao por pipeline (no YAML)

```yaml
# Novo campo no pipeline config
pool:
  batch_size: 50           # quantos itens por job (default 50)
  batch_interval_seconds: 5 # frequencia do auto-batcher (default 5)
  auto_batch: true          # habilitar auto-batching (default true)
```

Se `auto_batch: false`, o pipeline so processa via `POST /v1/jobs` (comportamento atual preservado).

---

## 6. Fluxo Detalhado por Coletor

### 6.1 VotoLimpo Scraper (Firecrawl, 4x/dia)

```
Scheduler (cron 4x/dia)
    |
    v
Firecrawl crawl (TSE, portais, diarios)
    |
    | Para cada pagina coletada:
    v
POST /v1/pool/ingest
    pipeline_id: "votolimpo-analyzer"
    source_id: "votolimpo-scraper"
    batch_ref: "crawl-2026-09-07-06h"
    items: [
      { source_url: "https://tse.jus.br/...", content: "<html>...", content_type: "text/html" },
      { source_url: "https://diario.gov.br/...", content: "<html>...", content_type: "text/html" },
      ...
    ]
    |
    v
Pool recebe 150 itens → rejeita 12 duplicatas → aceita 138
    |
    | Auto-Batcher (a cada 5s)
    | Cria 3 jobs de 50 itens cada (50 + 50 + 38)
    v
Worker processa os 3 jobs normalmente
```

**O scraper NAO precisa saber sobre jobs, batching, concorrencia ou rate limits. Ele so deposita dados.**

### 6.2 Help Core File Importer (batch upload)

```
Operador humano no Help Core
    |
    | Upload de 500 PDFs via interface
    v
Help Core Backend
    |
    | Para cada PDF: extrai texto (PyMuPDF)
    v
POST /v1/pool/ingest
    pipeline_id: "helpcore-sharepoint"
    source_id: "helpcore-importer"
    batch_ref: "import-batch-42"
    items: [
      { content: "texto do PDF 1...", content_type: "text/plain", metadata: { filename: "doc1.pdf" } },
      { content: "texto do PDF 2...", content_type: "text/plain", metadata: { filename: "doc2.pdf" } },
      ...
    ]
    |
    v
Pool recebe 500 itens
    |
    | Auto-Batcher cria 10 jobs de 50
    v
Worker processa 10 jobs (5 simultaneos, rate limited)
```

### 6.3 Futuro Coletor Generico (webhook via n8n)

```
n8n Workflow (trigger: webhook, RSS, email, etc.)
    |
    | Para cada item detectado:
    v
POST /v1/pool/ingest/single
    pipeline_id: "projeto-x-analyzer"
    source_id: "n8n-rss-monitor"
    source_url: "https://feed.example.com/article-123"
    content: "Texto do artigo..."
    content_type: "text/plain"
    |
    v
Pool recebe 1 item por vez
    |
    | Auto-Batcher agrupa quando acumular o suficiente
    | OU processa individual apos batch_interval_seconds
    v
Worker processa
```

---

## 7. O que MUDA no Engine Atual

### 7.1 Novas adicoes (codigo novo)

| Componente | Descricao | Arquivo |
|------------|-----------|---------|
| **Pool table** | Migration nova | `alembic/versions/012_create_pool.py` |
| **Pool models** | Pydantic models para ingestao | `app/models/pool.py` |
| **Pool SQL** | Queries da pool (insert, claim, status) | `app/sql/pool.py` |
| **Pool API** | Endpoints `/v1/pool/*` | `app/api/pool.py` |
| **Auto-Batcher** | Background task que cria jobs da pool | `app/services/auto_batcher.py` |
| **Config** | Novos settings para o batcher | `app/config.py` (edit) |

### 7.2 Modificacoes em codigo existente

| Arquivo | Mudanca | Impacto |
|---------|---------|---------|
| `app/main.py` | Registrar router da pool + iniciar auto-batcher no lifespan | Minimo — 10 linhas |
| `app/config.py` | Adicionar `BATCHER_POLL_INTERVAL_SECONDS`, `BATCHER_DEFAULT_BATCH_SIZE` | Minimo — 2 campos |
| `alembic/versions/003_create_pipelines.py` | NAO ALTERA — campo `pool` vai no JSONB de config | Zero |

### 7.3 O que pode ser adicionado ao pipeline YAML

```yaml
# Campos novos no pipeline config (opcionais, com defaults)
pool:
  auto_batch: true
  batch_size: 50
  batch_interval_seconds: 5
```

Esses campos ficam dentro do JSONB `config` do pipeline — NAO requer alteracao de schema da tabela `pipelines`.

---

## 8. O que NAO MUDA

| Componente | Motivo |
|------------|--------|
| **Worker** (`app/worker.py`) | Continua pegando jobs via SKIP LOCKED. Zero mudanca. |
| **Orchestrator** (`app/services/orchestrator.py`) | Pipeline de 5 etapas inalterado. |
| **Plugins/Protocols** (`app/plugins/`) | Ingestor, Dedup, LLM, Validator, Sink — tudo igual. |
| **API de Jobs** (`app/api/jobs.py`) | POST /v1/jobs continua funcionando normalmente (backward compatible). |
| **SQL de Items** (`app/sql/items.py`) | Inalterado. |
| **SQL de Jobs** (`app/sql/jobs.py`) | Inalterado. |
| **Cost Tracker** (`app/services/cost_tracker.py`) | Inalterado. |
| **Rate Limiter** (`app/services/rate_limiter.py`) | Inalterado. |
| **Callback** (`app/services/callback.py`) | Inalterado. |
| **Models existentes** (`app/models/`) | Inalterados. |
| **Migrations existentes** | Nenhuma alterada. |
| **Dockerfile/docker-compose** | Container unico, mesma imagem. |

**Nao se quebra NADA do que existe.** A pool e uma camada ADICIONAL na frente dos jobs. Coletores novos usam a pool. Quem quiser continuar criando jobs direto via POST /v1/jobs pode.

---

## 9. Diagrama de Sequencia: Ciclo Completo

```
Coletor                  Pool API              Pool (tabela)         Auto-Batcher           Jobs (tabela)          Worker
  |                        |                      |                      |                      |                    |
  |-- POST /v1/pool/ingest -->                    |                      |                      |                    |
  |                        |-- dedup check ------->|                      |                      |                    |
  |                        |<--- ok/dup ----------|                      |                      |                    |
  |                        |-- INSERT pending ---->|                      |                      |                    |
  |<-- 201 accepted ------|                      |                      |                      |                    |
  |                        |                      |                      |                      |                    |
  |                        |                      |  (poll 5s)           |                      |                    |
  |                        |                      |<-- SELECT pending ---|                      |                    |
  |                        |                      |     SKIP LOCKED      |                      |                    |
  |                        |                      |--- N items --------->|                      |                    |
  |                        |                      |                      |-- INSERT job -------->|                    |
  |                        |                      |                      |-- INSERT items ------>|                    |
  |                        |                      |<-- UPDATE claimed ---|                      |                    |
  |                        |                      |                      |                      |                    |
  |                        |                      |                      |                      |  (poll 1s)         |
  |                        |                      |                      |                      |<-- SKIP LOCKED ----|
  |                        |                      |                      |                      |--- job record ---->|
  |                        |                      |                      |                      |                    |
  |                        |                      |                      |                      |         Orchestrator
  |                        |                      |                      |                      |         (inalterado)
```

---

## 10. Dedup na Pool vs Dedup no Pipeline

Ha DOIS niveis de dedup, cada um com responsabilidade distinta:

| Nivel | Onde | Quando | O que faz | Custo |
|-------|------|--------|-----------|-------|
| **Pool Dedup** | `POST /v1/pool/ingest` | Na ingestao | Rejeita url_hash duplicado na pool (mesmo pipeline) | ~0 (index lookup) |
| **Pipeline Dedup** | `Orchestrator._dedup()` | Durante processamento | Hash + semantico contra itens JA PROCESSADOS | ~0 (hash) ou ~$0.0001 (embedding) |

Pool Dedup e uma primeira barreira rapida: se o mesmo URL ja esta na pool (pendente ou ja processado), nao aceita de novo. Isso evita que um coletor envie o mesmo conteudo repetidamente.

Pipeline Dedup continua existindo como barreira final contra reprocessamento — inclusive pegando conteudo identico vindo de URLs diferentes (content_hash match).

---

## 11. Retencao e Limpeza da Pool

Itens `claimed` na pool sao referencia historica. Sugestao de politica:

```sql
-- Cron job (pg_cron ou script externo): limpar pool items > 30 dias que ja foram claimed
DELETE FROM processing_engine.pool
WHERE status = 'claimed' AND created_at < now() - interval '30 days';

-- Itens rejeitados por dedup: limpar apos 7 dias
DELETE FROM processing_engine.pool
WHERE status = 'duplicate_rejected' AND created_at < now() - interval '7 days';
```

---

## 12. Seguranca

- O endpoint `/v1/pool/ingest` usa a mesma API key do engine (`verify_api_key`).
- O `source_id` e declarativo — o coletor informa quem e. NAO e autenticacao (a API key ja cumpre esse papel).
- Coletores diferentes podem usar a mesma API key ou API keys diferentes (se implementarmos multi-key no futuro).
- Rate limiting no endpoint de ingestao: limitar a 100 requests/minuto por IP ou API key (previne abuse).
- `content` e armazenado como TEXT — nao ha execucao de codigo. O ingestor do pipeline trata sanitizacao.

---

## 13. Impacto na Constitution

Todas as validacoes contra a Constitution:

| Principio | Status | Justificativa |
|-----------|--------|---------------|
| I. Agnostico por Design | OK | Pool recebe dados de QUALQUER coletor. Engine continua 100% agnostico. |
| II. Anti-Reprocessamento | OK | Pool Dedup (url_hash) + Pipeline Dedup (content_hash + semantico). Duas camadas. |
| III. Custo Controlado | OK | Nenhuma chamada LLM na pool. Budget limits inalterados. |
| IV. Plugin-First | OK | Pool nao altera o sistema de plugins. Auto-Batcher e service interno. |
| V. Stack Minima | OK | Pool e tabela PostgreSQL. Sem Redis, sem fila externa. SKIP LOCKED reaproveitado. |
| VI. Schema First | OK | Migration Alembic para a pool. Pydantic models para a API. |
| VII. Idempotencia Total | OK | Pool Dedup garante idempotencia na ingestao. Jobs continuam com idempotency_key. |
| VIII. Observabilidade | OK | `source_id` + `batch_ref` permitem rastreio. GET /v1/pool/status para monitoring. |
| IX. Testabilidade | OK | Pool API testavel com PostgreSQL real (testcontainers). |
| X. Seguranca | OK | Mesma API key. Queries parametrizadas. Sem execucao de codigo. |

---

## 14. Decisoes Arquiteturais Explicitas

### D1: Pool como tabela PostgreSQL, nao como fila externa
**Alternativas consideradas**: Redis streams, RabbitMQ, tabela temporaria.
**Decisao**: Tabela permanente com SKIP LOCKED. Consistente com principio V (Stack Minima).
**Trade-off**: Menor throughput que fila dedicada, mas suficiente para 10K items/dia e zero complexidade operacional.

### D2: Auto-Batcher como background task, nao como trigger PostgreSQL
**Alternativas consideradas**: LISTEN/NOTIFY, pg_cron trigger, webhook interno.
**Decisao**: Poll periodico (igual ao Worker). Simples, testavel, sem dependencia de extensao.
**Trade-off**: Latencia de ate batch_interval_seconds entre ingestao e criacao do job. Aceitavel para o caso de uso.

### D3: POST /v1/jobs preservado (backward compatible)
**Alternativas consideradas**: Deprecar POST /v1/jobs e forcar tudo via pool.
**Decisao**: Manter ambos. Pool para coletores. Jobs direto para uso programatico avancado.
**Trade-off**: Duas formas de submeter dados. Mas backward compatibility e mais importante que pureza.

### D4: Dedup na pool SOMENTE por url_hash, nao por content_hash
**Alternativas consideradas**: Dedup por content_hash na pool tambem.
**Decisao**: Apenas url_hash na pool. Content_hash e responsabilidade do Pipeline Dedup.
**Motivo**: Na pool, o coletor pode enviar conteudo diferente para a mesma URL (pagina atualizada). O url_hash na pool evita duplicatas obvias. O content_hash fino fica para o pipeline que ja tem toda a infraestrutura de dedup.

### D5: Pool item carrega conteudo completo, nao referencia
**Alternativas consideradas**: Pool so com URL, engine busca conteudo depois.
**Decisao**: Pool carrega o conteudo bruto. Coletor ja fez o trabalho de buscar.
**Motivo**: Engine 100% agnostico de coleta. Se a pool so guardasse URL, o engine precisaria saber como buscar — violaria principio I.

---

## 15. Estimativa de Esforco

| Item | Estimativa |
|------|-----------|
| Migration (pool table + indexes) | 1h |
| Pydantic models (PoolIngest, PoolItem, PoolStatus) | 1h |
| SQL queries (insert, claim, status) | 1h |
| Pool API (3 endpoints) | 2h |
| Auto-Batcher service | 3h |
| Integracao main.py (router + lifespan) | 30min |
| Testes unitarios + integracao | 4h |
| Testes E2E (coletor → pool → job → resultado) | 2h |
| **TOTAL** | **~15h** |

---

## 16. Proximos Passos

1. **Matheus valida esta proposta** — sem validacao, nao se implementa nada
2. Se aprovado: criar spec formal via `/speckit.specify` com base neste documento
3. Implementar seguindo o pipeline: spec → plan → tasks → implement → gates
4. Primeiro coletor de teste: VotoLimpo scraper adaptado para usar a pool

---

**HOMELAND — Este documento e proposta arquitetural. Nao e codigo. Nao e spec. E a fundacao sobre a qual a spec sera construida. Cada decisao esta justificada. Cada trade-off esta explicito. Se tem algo que nao faz sentido, agora e a hora de questionar.**
