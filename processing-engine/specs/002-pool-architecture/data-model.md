# Data Model: Pool Architecture

**Feature**: 002-pool-architecture
**Created**: 2026-09-07
**Database**: PostgreSQL 16 (schema: `processing_engine`)

---

## Nova Tabela: `pool`

Buffer de ingestão desacoplada. Recebe dados brutos de N coletores independentes. O Auto-Batcher consome e cria jobs.

```sql
CREATE TABLE processing_engine.pool (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),

    -- Conteúdo bruto (pelo menos content OU source_url obrigatório)
    source_url      TEXT,
    content         TEXT,
    content_type    TEXT NOT NULL DEFAULT 'text/plain',
    metadata        JSONB DEFAULT '{}',

    -- Hashes para dedup rápido
    url_hash        TEXT,           -- SHA-256 de source_url (computado no endpoint)
    content_hash    TEXT,           -- SHA-256 de content (computado no endpoint)

    -- Controle de estado
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'claimed', 'duplicate_rejected', 'error')),
    priority        INTEGER NOT NULL DEFAULT 0,

    -- Rastreabilidade do coletor
    source_id       TEXT,           -- identificador do coletor (ex: "votolimpo-scraper")
    batch_ref       TEXT,           -- referência do batch no coletor (para debug)

    -- Referência ao job criado (preenchido pelo Auto-Batcher)
    job_id          UUID REFERENCES processing_engine.jobs(id),

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    claimed_at      TIMESTAMPTZ         -- quando o auto-batcher consumiu
);
```

---

## Indexes

```sql
-- Auto-Batcher: pegar itens pendentes por pipeline (SKIP LOCKED)
CREATE INDEX idx_pool_pending
    ON processing_engine.pool (pipeline_id, priority DESC, created_at ASC)
    WHERE status = 'pending';

-- Dedup rápido por URL na ingestão
CREATE INDEX idx_pool_url_hash
    ON processing_engine.pool (url_hash, pipeline_id)
    WHERE url_hash IS NOT NULL AND status != 'duplicate_rejected';

-- Dedup por content hash (complementar)
CREATE INDEX idx_pool_content_hash
    ON processing_engine.pool (content_hash, pipeline_id)
    WHERE content_hash IS NOT NULL AND status != 'duplicate_rejected';

-- Rastreio por coletor
CREATE INDEX idx_pool_source
    ON processing_engine.pool (source_id, created_at DESC)
    WHERE source_id IS NOT NULL;

-- Lookup por job_id (join com jobs table)
CREATE INDEX idx_pool_job_id
    ON processing_engine.pool (job_id)
    WHERE job_id IS NOT NULL;
```

---

## Ciclo de Vida do Status

```
pending ──────────────> claimed ────────> (histórico / cleanup)
    │                      │
    │                      └── job_id preenchido
    │                      └── claimed_at preenchido
    │
    └──> duplicate_rejected (url_hash já existe)
    └──> error (pipeline deletado entre ingestão e claim)
```

| Status | Quem seta | Quando |
|--------|-----------|--------|
| `pending` | Pool API | Na ingestão (POST /v1/pool/ingest) |
| `claimed` | Auto-Batcher | Ao criar job a partir do item |
| `duplicate_rejected` | Pool API | url_hash duplicado na ingestão |
| `error` | Auto-Batcher | Pipeline não encontrado no momento do claim |

---

## Relação com Tabelas Existentes

```
pool (NOVA)                    pipelines (existente)
├── pipeline_id ──────FK──────> id
├── job_id ──────────FK──────> jobs.id (existente)
│
│   Auto-Batcher cria:
│   pool.content ──────────> items.content (existente)
│   pool.source_url ───────> items.source_url (existente)
│   pool.metadata ─────────> items.metadata (existente)
│   pool.content_type ─────> items.content_type (existente)
```

**Fluxo de dados**: Pool → Auto-Batcher → Jobs + Items → Worker → Orchestrator → Sink

A pool NÃO substitui a tabela `items`. O Auto-Batcher COPIA dados da pool para `items` ao criar o job. A pool mantém o registro original para rastreabilidade.

---

## Alterações em Tabelas Existentes

**Nenhuma.** Nenhuma tabela existente é alterada. A pool é puramente aditiva.

---

## Volume Estimado

| Cenário | Items/dia na pool | Jobs criados | Retenção pool |
|---------|-------------------|--------------|---------------|
| VotoLimpo (4x/dia, 15 portais) | ~600 | ~600 | 30 dias (claimed) |
| Help Core (batch esporádico) | ~200 | ~200 | 30 dias (claimed) |
| Total | ~800 | ~800 | < 25K rows/mês |

---

## Política de Retenção (sugestão — implementação futura)

```sql
-- Cleanup de itens claimed com > 30 dias
DELETE FROM processing_engine.pool
WHERE status = 'claimed' AND created_at < now() - interval '30 days';

-- Cleanup de rejeitados com > 7 dias
DELETE FROM processing_engine.pool
WHERE status = 'duplicate_rejected' AND created_at < now() - interval '7 days';
```

Nota: Retenção é OUT-OF-SCOPE v1. Pode ser implementada via pg_cron ou script externo.
