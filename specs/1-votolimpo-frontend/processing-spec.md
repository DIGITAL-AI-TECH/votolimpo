# VotoLimpo - Especificação Completa de Processamento de Dados

**Versão**: 1.0
**Data**: 2026-09-05
**Autores**: Data Scientist (SIGMA) + Homeland + PM
**Escopo**: Estrutura completa dos dados extraídos, schema corrigido, pipeline de processamento

---

## Índice

1. [Visão Geral do Pipeline](#1-visão-geral)
2. [Schema Corrigido (PostgreSQL 16)](#2-schema-corrigido)
3. [JSON de Saída do Processamento (GPT-4.1-mini)](#3-json-de-saída)
4. [Algoritmos e Fórmulas](#4-algoritmos)
5. [Mapeamento Tela → Dados](#5-mapeamento-tela-dados)
6. [Validação Anti-Alucinação](#6-validação)
7. [Cron Jobs e Batch Processing](#7-cron-jobs)
8. [Acceptance Criteria](#8-acceptance-criteria)

---

## 1. Visão Geral do Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        COLETA (Firecrawl)                       │
│  sources → crawl → raw_content → dedup (url_hash + content_hash)│
│  → collection_runs (audit trail)                                │
└───────────────────────┬─────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROCESSAMENTO (GPT-4.1-mini)                  │
│  raw_content → structured JSON → validação anti-alucinação      │
│  → processing_logs (custo, tokens, erros)                       │
│                                                                 │
│  EXTRAI POR ARTIGO:                                             │
│  • título normalizado + resumo (2-3 frases)                     │
│  • 3 sinais de veracidade (narrative, documental, emotional)    │
│  • severidade (critical/high/medium/low)                        │
│  • políticos mencionados[] (nome, papel, partido, estado)       │
│  • entidades[] (empresas, órgãos, organizações)                 │
│  • relações[] (source → target, tipo, descrição)                │
│  • milestones[] (inquérito, denúncia, condenação...)            │
│  • keywords[] (max 10)                                          │
│  • confidence scores (autoavaliação)                            │
└───────────────────────┬─────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PERSISTÊNCIA (PostgreSQL)                     │
│  1. Resolver políticos (fuzzy match pg_trgm)                    │
│  2. Resolver entidades (fuzzy match + normalização)             │
│  3. Inserir article + politician_articles                       │
│  4. Inserir milestones (com dedup ±7 dias)                      │
│  5. Upsert relationships + evidências                           │
│  6. Calcular article_matches (entity + keyword + temporal)      │
│  7. Atualizar multi_source_count                                │
│  8. Calcular veracity_score final                               │
└───────────────────────┬─────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CRON DIÁRIO (03:00 UTC)                       │
│  1. Recalcular politician.score (sigmoid, 0-100)                │
│  2. Atualizar total_news, severity_max, first/last_news_at      │
│  3. Regenerar ai_summary (políticos com notícias <30 dias)      │
│  4. Refresh materialized views (stats, ranking)                 │
│  5. Registrar score_history                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Schema Corrigido (PostgreSQL 16)

### 2.1. Tipos ENUM (substituem TEXT livre)

```sql
CREATE TYPE severity_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE article_role AS ENUM ('subject', 'mentioned', 'related');
CREATE TYPE entity_type AS ENUM ('company', 'organization', 'lobby', 'ngo', 'government_body', 'court');
CREATE TYPE milestone_type AS ENUM ('inquiry', 'complaint', 'conviction', 'acquittal', 'arrest', 'impeachment', 'plea_deal', 'fine');
CREATE TYPE relationship_type AS ENUM ('business', 'political', 'family', 'legal', 'financial');
CREATE TYPE source_category AS ENUM ('portal', 'jornal', 'revista', 'blog', 'agencia');
CREATE TYPE match_type AS ENUM ('content', 'entity', 'temporal');
CREATE TYPE processing_status AS ENUM ('running', 'completed', 'failed', 'partial');
```

### 2.2. Tabelas Corrigidas (campos adicionados marcados com ✚)

```sql
-- ═══════════════════════════════════════════════
-- TABELAS EXISTENTES (com correções do Homeland)
-- ═══════════════════════════════════════════════

CREATE TABLE politicians (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  party_id      UUID REFERENCES parties(id),
  state         CHAR(2) NOT NULL,
  role          TEXT NOT NULL,
  photo_url     TEXT,
  score         DECIMAL(5,2) DEFAULT 0,
  total_news    INT DEFAULT 0,
  severity_max  severity_level DEFAULT 'low',     -- ✚ ENUM em vez de TEXT
  first_news_at TIMESTAMPTZ,                      -- ✚ TIMESTAMPTZ em vez de DATE
  last_news_at  TIMESTAMPTZ,                      -- ✚ TIMESTAMPTZ em vez de DATE
  tse_id        TEXT,
  bio           TEXT,                              -- ✚ NOVO (Homeland C1)
  ai_summary    TEXT,                              -- ✚ NOVO (Homeland C1)
  ai_summary_at TIMESTAMPTZ,                      -- ✚ NOVO (cache de regeneração)
  initials      CHAR(2) GENERATED ALWAYS AS (      -- ✚ NOVO (Homeland C1)
    upper(left(name, 1)) || upper(left(split_part(name, ' ', -1), 1))
  ) STORED,
  search_vector tsvector GENERATED ALWAYS AS (     -- ✚ NOVO (Homeland W5)
    setweight(to_tsvector('portuguese', coalesce(name, '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(bio, '')), 'B')
  ) STORED,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_politicians_score ON politicians(score DESC);
CREATE INDEX idx_politicians_slug ON politicians(slug);
CREATE INDEX idx_politicians_party ON politicians(party_id);
CREATE INDEX idx_politicians_search ON politicians(state, role, party_id, score DESC); -- ✚ composto (H6)
CREATE INDEX idx_politicians_fts ON politicians USING gin(search_vector);              -- ✚ full-text (W5)

CREATE TABLE articles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  summary         TEXT,
  original_url    TEXT NOT NULL UNIQUE,              -- ✚ UNIQUE (Homeland H1)
  source_id       UUID REFERENCES sources(id),
  published_at    TIMESTAMPTZ NOT NULL,              -- ✚ TIMESTAMPTZ em vez de DATE
  collected_at    TIMESTAMPTZ DEFAULT now(),
  veracity_score  DECIMAL(3,2),
  source_reputation   DECIMAL(3,2),
  multi_source_count  INT DEFAULT 1,
  narrative_consistency DECIMAL(3,2),
  documental_evidence DECIMAL(3,2),
  temporality_score   DECIMAL(3,2),
  emotional_language  DECIMAL(3,2),
  severity        severity_level NOT NULL DEFAULT 'low', -- ✚ ENUM
  category        TEXT,                              -- ✚ NOVO (corruption/investigation/trial/etc)
  keywords        TEXT[],                            -- ✚ NOVO (array de keywords)
  ai_processed    BOOLEAN DEFAULT false,
  url_hash        TEXT GENERATED ALWAYS AS (          -- ✚ NOVO dedup (Homeland C8)
    md5(regexp_replace(original_url, '[?#].*$', ''))
  ) STORED,
  content_hash    TEXT,                              -- ✚ NOVO dedup por conteúdo
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT chk_veracity CHECK (veracity_score BETWEEN 0.00 AND 1.00) -- ✚ (Homeland C2)
);

CREATE UNIQUE INDEX idx_articles_url_dedup ON articles(url_hash);       -- ✚ dedup
CREATE INDEX idx_articles_content_hash ON articles(content_hash);
CREATE INDEX idx_articles_timeline ON articles(published_at DESC, severity)
  INCLUDE (title, summary, veracity_score, original_url, source_id);   -- ✚ covering index (H6)

-- raw_content separado para performance (Homeland H10)
CREATE TABLE article_raw_content (
  article_id  UUID PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  raw_content TEXT NOT NULL,
  content_hash TEXT NOT NULL
);

CREATE TABLE sources (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  domain          TEXT UNIQUE NOT NULL,
  reputation      DECIMAL(3,2) DEFAULT 0.5,
  category        source_category,                   -- ✚ ENUM
  logo_url        TEXT,
  active          BOOLEAN DEFAULT true,
  last_crawled_at TIMESTAMPTZ,                       -- ✚ NOVO (Homeland H8)
  crawl_frequency_hours INT DEFAULT 24,              -- ✚ NOVO
  crawl_config    JSONB DEFAULT '{}',                -- ✚ NOVO
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE politician_articles (
  politician_id   UUID REFERENCES politicians(id) ON DELETE CASCADE,
  article_id      UUID REFERENCES articles(id) ON DELETE CASCADE,
  role            article_role DEFAULT 'subject',    -- ✚ ENUM
  PRIMARY KEY (politician_id, article_id)
);

CREATE TABLE article_matches (
  article_a_id    UUID REFERENCES articles(id) ON DELETE CASCADE,
  article_b_id    UUID REFERENCES articles(id) ON DELETE CASCADE,
  similarity      DECIMAL(3,2) NOT NULL,
  match_type      match_type DEFAULT 'content',      -- ✚ ENUM
  created_at      TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (article_a_id, article_b_id),
  CHECK (article_a_id < article_b_id)
);

CREATE TABLE milestones (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  politician_id   UUID REFERENCES politicians(id) ON DELETE CASCADE,
  title           TEXT NOT NULL,
  description     TEXT,
  milestone_type  milestone_type NOT NULL,            -- ✚ ENUM
  occurred_at     DATE NOT NULL,
  source_url      TEXT,
  article_id      UUID REFERENCES articles(id),
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE entities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  slug            TEXT UNIQUE,                        -- ✚ NOVO dedup (Homeland H4)
  entity_type     entity_type NOT NULL,               -- ✚ ENUM
  description     TEXT,
  aliases         TEXT[],                             -- ✚ NOVO (nomes alternativos)
  score           DECIMAL(5,2) DEFAULT 0,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_entities_name_trgm ON entities USING gin (name gin_trgm_ops); -- ✚ fuzzy match
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE relationships (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_politician_id UUID REFERENCES politicians(id) ON DELETE CASCADE,  -- ✚ FKs separadas (C7)
  source_entity_id     UUID REFERENCES entities(id) ON DELETE CASCADE,
  source_party_id      UUID REFERENCES parties(id) ON DELETE CASCADE,
  target_politician_id UUID REFERENCES politicians(id) ON DELETE CASCADE,
  target_entity_id     UUID REFERENCES entities(id) ON DELETE CASCADE,
  target_party_id      UUID REFERENCES parties(id) ON DELETE CASCADE,
  relationship_type    relationship_type NOT NULL,     -- ✚ ENUM
  weight               INT DEFAULT 1,
  description          TEXT,
  created_at           TIMESTAMPTZ DEFAULT now(),
  updated_at           TIMESTAMPTZ DEFAULT now(),
  CONSTRAINT chk_source_one CHECK (
    (source_politician_id IS NOT NULL)::int +
    (source_entity_id IS NOT NULL)::int +
    (source_party_id IS NOT NULL)::int = 1
  ),
  CONSTRAINT chk_target_one CHECK (
    (target_politician_id IS NOT NULL)::int +
    (target_entity_id IS NOT NULL)::int +
    (target_party_id IS NOT NULL)::int = 1
  )
);

CREATE TABLE relationship_evidence (
  relationship_id UUID REFERENCES relationships(id) ON DELETE CASCADE,
  article_id      UUID REFERENCES articles(id) ON DELETE CASCADE,
  PRIMARY KEY (relationship_id, article_id)
);

-- ═══════════════════════════════════════════════
-- TABELAS NOVAS (gaps identificados)
-- ═══════════════════════════════════════════════

-- Clusters de notícias / "Casos" (Homeland C3)
CREATE TABLE news_clusters (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title         TEXT NOT NULL,
  summary       TEXT NOT NULL,
  severity      severity_level NOT NULL,
  article_count INT DEFAULT 0,
  first_seen_at DATE NOT NULL,
  last_seen_at  DATE NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cluster_articles (
  cluster_id  UUID REFERENCES news_clusters(id) ON DELETE CASCADE,
  article_id  UUID REFERENCES articles(id) ON DELETE CASCADE,
  PRIMARY KEY (cluster_id, article_id)
);

CREATE TABLE cluster_politicians (
  cluster_id    UUID REFERENCES news_clusters(id) ON DELETE CASCADE,
  politician_id UUID REFERENCES politicians(id) ON DELETE CASCADE,
  PRIMARY KEY (cluster_id, politician_id)
);

-- Audit trail de coleta (Homeland C4)
CREATE TABLE collection_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id     UUID REFERENCES sources(id),
  status        processing_status NOT NULL DEFAULT 'running',
  articles_found INT DEFAULT 0,
  articles_new   INT DEFAULT 0,
  articles_dup   INT DEFAULT 0,
  error_message  TEXT,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ,
  metadata      JSONB DEFAULT '{}'
);

-- Audit trail de processamento (Homeland C4)
CREATE TABLE processing_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id    UUID REFERENCES articles(id),
  collection_run_id UUID REFERENCES collection_runs(id),
  step          TEXT NOT NULL,
  status        processing_status NOT NULL,
  model_used    TEXT,
  prompt_tokens INT,
  completion_tokens INT,
  cost_usd      DECIMAL(10,6),
  input_hash    TEXT,
  output_json   JSONB,
  error_message TEXT,
  duration_ms   INT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Histórico de score (Homeland C5)
CREATE TABLE score_history (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  politician_id UUID NOT NULL REFERENCES politicians(id) ON DELETE CASCADE,
  score         DECIMAL(5,2) NOT NULL,
  total_news    INT NOT NULL,
  severity_max  severity_level NOT NULL,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata      JSONB DEFAULT '{}'
);

CREATE INDEX idx_score_hist ON score_history(politician_id, calculated_at DESC);

-- Histórico de partidos (Homeland H3)
CREATE TABLE politician_parties (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  politician_id UUID NOT NULL REFERENCES politicians(id) ON DELETE CASCADE,
  party_id      UUID NOT NULL REFERENCES parties(id),
  started_at    DATE NOT NULL,
  ended_at      DATE
);
```

### 2.3. Views e Materialized Views

```sql
-- Ranking (corrigido: LEFT JOIN - Homeland H5)
CREATE VIEW v_politician_ranking AS
SELECT
  p.id, p.slug, p.name, p.score, p.total_news,
  p.state, p.role, p.photo_url, p.severity_max,
  p.bio, p.ai_summary, p.initials,
  pa.abbreviation AS party, pa.color AS party_color, pa.logo_url AS party_logo,
  RANK() OVER (ORDER BY p.score DESC) AS position,
  p.first_news_at, p.last_news_at
FROM politicians p
LEFT JOIN parties pa ON pa.id = p.party_id
ORDER BY p.score DESC;

-- Relações bidirecionais para matches (Homeland H7)
CREATE MATERIALIZED VIEW mv_article_relations AS
SELECT article_a_id AS article_id, article_b_id AS related_id, similarity, match_type FROM article_matches
UNION ALL
SELECT article_b_id, article_a_id, similarity, match_type FROM article_matches;

CREATE UNIQUE INDEX idx_mv_rel ON mv_article_relations(article_id, related_id);

-- Stats globais (Homeland H9)
CREATE MATERIALIZED VIEW mv_global_stats AS
SELECT
  (SELECT count(*) FROM politicians) AS total_politicians,
  (SELECT count(*) FROM articles WHERE ai_processed = true) AS total_articles,
  (SELECT count(*) FROM sources WHERE active = true) AS total_sources,
  (SELECT count(*) FROM milestones WHERE milestone_type = 'conviction') AS total_convictions;

CREATE UNIQUE INDEX idx_mv_stats ON mv_global_stats((1));
```

---

## 3. JSON de Saída do Processamento (GPT-4.1-mini)

Cada artigo coletado pelo Firecrawl é processado com `response_format: json_schema`. O modelo retorna EXATAMENTE este schema:

```json
{
  "$schema": "article_processing_v1",

  "article": {
    "title_normalized": "string (max 200 chars)",
    "summary": "string (2-3 frases, max 500 chars)",
    "published_at": "YYYY-MM-DD | null",
    "language": "pt-BR | pt | es | en",
    "category": "corruption | investigation | trial | legislation | scandal | misconduct | acquittal | other"
  },

  "veracity_signals": {
    "narrative_consistency": {
      "score": 0.0,
      "reasoning": "string (1 frase)"
    },
    "documental_evidence": {
      "score": 0.0,
      "evidence_types": ["document_number", "law_reference", "court_ruling", "official_statement", "financial_record", "none"],
      "reasoning": "string"
    },
    "emotional_language": {
      "score": 0.0,
      "reasoning": "string"
    }
  },

  "severity": {
    "level": "critical | high | medium | low",
    "reasoning": "string (1 frase)"
  },

  "politicians": [
    {
      "name": "string (nome completo como no texto)",
      "role_in_article": "subject | mentioned | related",
      "current_role": "string | null",
      "party": "string | null (sigla)",
      "state": "string | null (UF)",
      "context": "string (1 frase: o que o artigo diz sobre este político)"
    }
  ],

  "entities": [
    {
      "name": "string",
      "entity_type": "company | organization | lobby | ngo | government_body | court",
      "role_in_article": "string (1 frase)"
    }
  ],

  "relationships": [
    {
      "source_name": "string",
      "source_type": "politician | entity",
      "target_name": "string",
      "target_type": "politician | entity | party",
      "relationship_type": "business | political | family | legal | financial",
      "description": "string (1 frase)"
    }
  ],

  "milestones": [
    {
      "title": "string (max 100 chars)",
      "milestone_type": "inquiry | complaint | conviction | acquittal | arrest | impeachment | plea_deal | fine",
      "occurred_at": "YYYY-MM-DD",
      "description": "string (1-2 frases)",
      "politician_name": "string"
    }
  ],

  "keywords": ["string (max 10 keywords)"],

  "extraction_confidence": {
    "politicians_confidence": 0.0,
    "entities_confidence": 0.0,
    "milestones_confidence": 0.0,
    "overall_confidence": 0.0
  }
}
```

### Regras de Extração

| Campo | Regra |
|-------|-------|
| `title_normalized` | Título limpo sem clickbait, max 200 chars |
| `summary` | Resumo FACTUAL em 2-3 frases. SEM opinião, SEM adjetivos de valor |
| `politicians[]` | SOMENTE políticos EXPLICITAMENTE citados no texto. Nome completo como aparece |
| `entities[]` | Empresas, órgãos, organizações mencionados. NÃO incluir partidos (são tabela separada) |
| `relationships[]` | SOMENTE relações EXPLÍCITAS no texto. Coocorrência NÃO é relação |
| `milestones[]` | SOMENTE eventos jurídicos/políticos com evidência explícita. Confiança mínima 0.7 |
| `severity` | Baseado SOMENTE no conteúdo do artigo, não no histórico do político |
| `extraction_confidence` | Autoavaliação honesta. Texto ambíguo = score baixo |

---

## 4. Algoritmos e Fórmulas

### 4.1. Score de Veracidade (por artigo)

```
veracity_score = 0.30 × source_reputation
               + 0.25 × multi_source_normalized
               + 0.15 × narrative_consistency
               + 0.10 × documental_evidence
               + 0.10 × temporality_score
               + 0.10 × (1.0 - emotional_language)
```

- Armazenado como 0.00-1.00 no banco
- Exibido como 0-100 na UI (multiplicar por 100)
- multi_source: 1 fonte=0.0, 2=0.5, 3=0.75, 4+=1.0

| Score | Label UI | Cor |
|-------|----------|-----|
| 0.80-1.00 | Muito confiável | Verde #10B981 |
| 0.60-0.79 | Confiável | Azul #3B82F6 |
| 0.40-0.59 | Verificar fontes | Amarelo #F59E0B |
| 0.20-0.39 | Pouco confiável | Laranja #F97316 |
| 0.00-0.19 | Não verificado | Vermelho #EF4444 |

### 4.2. Score do Político (0-100, sigmoid)

```python
# Componente 1: Soma ponderada
SEVERITY_WEIGHT = {'critical': 10.0, 'high': 6.0, 'medium': 3.0, 'low': 1.0}
ROLE_WEIGHT = {'subject': 1.0, 'mentioned': 0.5, 'related': 0.25}

for artigo in artigos_do_politico:
    recency_decay = max(0.1, 1.0 - (dias_desde_publicacao / 365) * 0.5)
    weighted_sum += SEVERITY_WEIGHT[severity] * ROLE_WEIGHT[role] * veracity * recency_decay

# Componente 2: Bônus de volume (log-scale)
volume_bonus = log2(max(1, total_artigos))

# Componente 3: Bônus de recência
recency_bonus = min(artigos_ultimos_30_dias * 0.5, 3.0)

# Normalização sigmoid
raw_score = weighted_sum + volume_bonus + recency_bonus
score = 100.0 / (1 + e^(-0.15 * (raw_score - 20)))
```

| Cenário | Score esperado |
|---------|---------------|
| 0 notícias | 0 |
| 1 notícia low | ~5 |
| 5 notícias high, veracidade 0.8 | ~50 |
| 10 notícias critical, veracidade 0.9 | ~90 |

### 4.3. Matching de Notícias Relacionadas

3 sinais combinados (sem embeddings no MVP):

| Sinal | Peso | Métrica |
|-------|------|---------|
| Entity overlap | 0.40 | Jaccard (políticos + entidades em comum) |
| Keyword overlap | 0.35 | Jaccard (keywords normalizadas) |
| Temporal proximity | 0.25 | ≤3 dias=1.0, ≤7=0.8, ≤14=0.5, ≤30=0.2, >30=0.0 |

Thresholds:
- ≥0.30: persistir no banco
- ≥0.50: exibir como "notícias relacionadas" na UI
- ≥0.70: contar como multi_source (mesma história, fontes diferentes)
- Janela: comparar com artigos dos últimos 90 dias

### 4.4. Detecção de Milestones

| Tipo | Trigger textual | Dedup |
|------|----------------|-------|
| `inquiry` | "inquérito instaurado", "PF abre inquérito" | mesmo político + tipo + ±7 dias |
| `complaint` | "MPF denuncia", "denúncia aceita" | idem |
| `conviction` | "condenado a", "tribunal condena" | idem |
| `acquittal` | "absolvido", "arquivamento" | idem |
| `arrest` | "preso pela PF", "mandado de prisão" | idem |
| `impeachment` | "cassação aprovada", "perda do mandato" | idem |
| `plea_deal` | "delação premiada", "acordo de colaboração" | idem |
| `fine` | "multa de R$", "TSE multa" | idem |

Confiança mínima: 0.70 para persistir.

### 4.5. Severidade

| Nível | Critérios |
|-------|-----------|
| `critical` | Condenação criminal, prisão, desvio >R$1M, crime organizado |
| `high` | Denúncia formal aceita, inquérito instaurado, quebra de sigilo |
| `medium` | Irregularidade administrativa (TCU/CGU/MP), nepotismo, multa |
| `low` | Votação polêmica, declaração controversa, processo administrativo |

Na dúvida entre dois níveis: escolher o MENOR.

### 4.6. Resolução de Entidades (fuzzy match)

```sql
-- Requer: CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Político
SELECT id, name, similarity(name, $1) AS sim
FROM politicians
WHERE similarity(name, $1) >= 0.80
  AND ($2 IS NULL OR party_abbreviation = $2)
ORDER BY sim DESC LIMIT 1;

-- Entidade
SELECT id, name, entity_type, similarity(name, $1) AS sim
FROM entities
WHERE similarity(name, $1) >= 0.85
ORDER BY sim DESC LIMIT 1;
```

Não encontrou → INSERT nova entidade. Normalizar nome (remover LTDA/SA/S.A./etc).

---

## 5. Mapeamento Tela → Dados

### TELA 1 — HOME

| Componente | Campos consumidos | Fonte |
|------------|-------------------|-------|
| Autocomplete busca | name, slug, party, state, role, photo_url | `politicians` + FTS index |
| Contadores | total_politicians, total_articles, total_convictions, total_sources | `mv_global_stats` |
| Ranking top 10 | position, name, party, party_color, state, role, score, total_news, severity_max, slug, photo_url | `v_politician_ranking LIMIT 10` |
| Casos recentes | title, severity, politicians[], summary, date | `news_clusters` + `cluster_politicians` |

### TELA 2 — PERFIL DO POLÍTICO

| Componente | Campos consumidos | Fonte |
|------------|-------------------|-------|
| Header | name, party, party_color, party_logo, state, role, score, total_news, bio, ai_summary, initials, photo_url | `v_politician_ranking WHERE slug=$1` |
| Tab Timeline | title, summary, published_at, severity, veracity_score, original_url, source_name, milestone_type, item_type | `v_politician_timeline WHERE politician_id=$1` |
| Notícias relacionadas (expand) | related article title, summary, source, date | `mv_article_relations WHERE article_id=$1` |
| Tab Notícias | title, summary, published_at, severity, veracity_score, source_name | `articles JOIN politician_articles` |
| Tab Grafo mini | entities, relationships, parties | `relationships WHERE source/target = politician` |

### TELA 3 — BUSCA

| Componente | Campos consumidos | Fonte |
|------------|-------------------|-------|
| Busca por nome | name (full-text) | `search_vector` GIN index |
| Filtros | party, state, role, severity_min | `idx_politicians_search` composto |
| Cards resultado | photo_url, name, party, role, state, score, total_news, severity_max, slug | `politicians + parties` |

### TELA 4 — GRAFO GLOBAL

| Componente | Campos consumidos | Fonte |
|------------|-------------------|-------|
| Nós | id, name, type (politician/party/company/org), score, slug | `v_graph_nodes` |
| Arestas | source, target, weight, relationship_type | `relationships` |
| Painel lateral | name, type, score, connections[] | `relationships WHERE source/target = node` |

### TELA 5 — RANKING

| Componente | Campos consumidos | Fonte |
|------------|-------------------|-------|
| Top 3 badges | position, name, party, score, photo_url | `v_politician_ranking LIMIT 3` |
| Tabela ordenável | position, name, party, state, role, score, total_news, slug | `v_politician_ranking` |
| Filtros | party, state, role | índice composto |

---

## 6. Validação Anti-Alucinação

### Checks automáticos pós-processamento (ANTES de persistir)

| # | Check | Ação se falhar |
|---|-------|---------------|
| 1 | JSON válido e conforme schema | Retry 1x, depois skip |
| 2 | `veracity_signals.*.score` entre 0.0 e 1.0 | Rejeitar |
| 3 | `published_at` não é data futura | Rejeitar |
| 4 | `politicians[].name` aparece no `raw_content` | Remover político alucinado |
| 5 | `entities[].name` aparece no `raw_content` | Remover entidade alucinada |
| 6 | `severity.level` é enum válido | Rejeitar |
| 7 | `milestones[].milestone_type` é enum válido | Remover milestone inválido |
| 8 | `extraction_confidence.overall_confidence >= 0.3` | Marcar para revisão manual |
| 9 | `len(summary) <= 500` | Truncar |
| 10 | `len(keywords) <= 10` | Truncar |
| 11 | Coerência severidade vs conteúdo (critical sem evidence = warning) | Log warning |

### Métricas de qualidade (monitorar semanalmente)

| Métrica | Target |
|---------|--------|
| Taxa de rejeição por validação | < 5% |
| % de políticos não-resolvidos | < 10% |
| % de milestones com confidence < 0.7 | < 15% |
| Custo médio por artigo (GPT-4.1-mini) | < $0.001 |
| Taxa de retry | < 3% |
| Amostragem manual (accuracy) | > 90% |

---

## 7. Cron Jobs

| Job | Frequência | O que faz |
|-----|-----------|-----------|
| `recalculate_scores` | Diário 03:00 UTC | Recalcula score de todos os políticos + insere score_history |
| `regenerate_summaries` | Diário 04:00 UTC | Regenera ai_summary para políticos com notícias <30 dias |
| `refresh_views` | Horário | `REFRESH MATERIALIZED VIEW CONCURRENTLY` em mv_global_stats, mv_article_relations |
| `cluster_articles` | Diário 05:00 UTC | Agrupa artigos em news_clusters baseado em article_matches |
| `cleanup_logs` | Semanal | Remove processing_logs > 90 dias |

---

## 8. Acceptance Criteria

O processamento está **COMPLETO** quando:

- [ ] AC-01: Artigo processado gera JSON válido conforme schema §3
- [ ] AC-02: Todos os políticos mencionados são resolvidos (fuzzy match) ou logados como não-resolvidos
- [ ] AC-03: Score de veracidade calculado com 6 sinais, armazenado como 0.00-1.00
- [ ] AC-04: Milestones detectados e deduplicados (±7 dias, mesmo tipo, mesmo político)
- [ ] AC-05: Entidades normalizadas e sem duplicatas (pg_trgm ≥0.85)
- [ ] AC-06: article_matches calculados para artigos dos últimos 90 dias
- [ ] AC-07: Cron diário recalcula score + total_news + severity_max + ai_summary
- [ ] AC-08: processing_logs registra TODA chamada ao GPT (tokens, custo, status)
- [ ] AC-09: score_history preserva snapshot diário para cada político
- [ ] AC-10: Validação anti-alucinação rejeita < 5% dos artigos
- [ ] AC-11: news_clusters agrupam notícias relacionadas para "Casos Recentes" na home
- [ ] AC-12: Full-text search funciona em < 500ms para busca por nome de político

---

## Fontes de Reputação (seed inicial)

| Fonte | Domínio | Reputação | Categoria |
|-------|---------|-----------|-----------|
| Folha de S.Paulo | folha.uol.com.br | 0.92 | jornal |
| Estadão | estadao.com.br | 0.90 | jornal |
| G1 | g1.globo.com | 0.88 | portal |
| UOL | noticias.uol.com.br | 0.82 | portal |
| O Globo | oglobo.globo.com | 0.88 | jornal |
| Poder360 | poder360.com.br | 0.85 | portal |
| The Intercept Brasil | theintercept.com/brasil | 0.78 | portal |
| Agência Brasil | agenciabrasil.ebc.com.br | 0.90 | agencia |
| Agência Pública | apublica.org | 0.82 | agencia |
| Correio Braziliense | correiobraziliense.com.br | 0.80 | jornal |
| Gazeta do Povo | gazetadopovo.com.br | 0.78 | jornal |
| Jornal do Commercio | jc.ne10.uol.com.br | 0.75 | jornal |
| Diário do Nordeste | diariodonordeste.verdesmares.com.br | 0.72 | jornal |
| Transparência Brasil | transparencia.org.br | 0.95 | agencia |
| Congresso em Foco | congressoemfoco.uol.com.br | 0.83 | portal |

---

## Estimativa de Custo (GPT-4.1-mini)

| Componente | Custo |
|-----------|-------|
| Processamento de artigo (~3K tokens input + ~800 output) | ~$0.0005/artigo |
| Bio do político (~200 tokens) | ~$0.00005/político |
| Resumo IA do político (~500 tokens) | ~$0.0002/político |
| **10.000 artigos/mês** | **~$5-7/mês** |

---

*Documento gerado pela consolidação de: Data Scientist (SIGMA), Homeland Review, PM Data Mapping*
*Referências detalhadas: `processing-pipeline.md`, `data-mapping.md`*
