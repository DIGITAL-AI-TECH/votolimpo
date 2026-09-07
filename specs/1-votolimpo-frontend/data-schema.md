# Voto Limpo - Estrutura de Dados

**Baseado nos mockups refinados de 2026-09-05**
**Banco**: PostgreSQL 16

---

## Entidades Principais

### 1. politicians (Políticos)

```sql
CREATE TABLE politicians (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,        -- "jose-da-silva-pt-sp"
  name          TEXT NOT NULL,                -- "José da Silva"
  party_id      UUID REFERENCES parties(id),
  state         CHAR(2) NOT NULL,             -- "SP"
  role          TEXT NOT NULL,                -- "Deputado Federal"
  photo_url     TEXT,                         -- CDN URL (foto TSE)
  score         DECIMAL(5,2) DEFAULT 0,       -- 0.00 a 100.00
  total_news    INT DEFAULT 0,                -- contagem denormalizada
  severity_max  TEXT DEFAULT 'low',           -- low/medium/high/critical
  first_news_at DATE,                         -- data da primeira notícia
  last_news_at  DATE,                         -- data da última notícia
  tse_id        TEXT,                         -- ID no TSE (importação)
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_politicians_score ON politicians(score DESC);
CREATE INDEX idx_politicians_slug ON politicians(slug);
CREATE INDEX idx_politicians_party ON politicians(party_id);
CREATE INDEX idx_politicians_state ON politicians(state);
CREATE INDEX idx_politicians_role ON politicians(role);
```

### 2. parties (Partidos)

```sql
CREATE TABLE parties (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,                -- "Partido dos Trabalhadores"
  abbreviation  TEXT UNIQUE NOT NULL,          -- "PT"
  logo_url      TEXT,                         -- CDN URL
  color         TEXT,                         -- hex cor do partido "#FF0000"
  created_at    TIMESTAMPTZ DEFAULT now()
);
```

### 3. articles (Notícias/Artigos)

```sql
CREATE TABLE articles (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  summary         TEXT,                       -- resumo gerado por IA (2-3 frases)
  original_url    TEXT NOT NULL,               -- link para notícia na íntegra
  source_id       UUID REFERENCES sources(id),
  published_at    DATE NOT NULL,
  collected_at    TIMESTAMPTZ DEFAULT now(),

  -- Score de veracidade (0.0 a 1.0)
  veracity_score  DECIMAL(3,2),               -- score final calculado

  -- 6 sinais do score
  source_reputation   DECIMAL(3,2),           -- reputação da fonte (peso 30%)
  multi_source_count  INT DEFAULT 1,          -- nº de fontes que cobriram (peso 25%)
  narrative_consistency DECIMAL(3,2),          -- consistência narrativa (peso 15%)
  documental_evidence DECIMAL(3,2),           -- evidência documental (peso 10%)
  temporality_score   DECIMAL(3,2),           -- temporalidade (peso 10%)
  emotional_language  DECIMAL(3,2),           -- linguagem emocional invertida (peso 10%)

  severity        TEXT NOT NULL DEFAULT 'low', -- low/medium/high/critical
  raw_content     TEXT,                        -- conteúdo bruto coletado
  ai_processed    BOOLEAN DEFAULT false,

  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_severity ON articles(severity);
CREATE INDEX idx_articles_veracity ON articles(veracity_score);
CREATE INDEX idx_articles_source ON articles(source_id);
```

### 4. sources (Fontes de Notícias)

```sql
CREATE TABLE sources (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,              -- "G1", "Folha de S.Paulo"
  domain          TEXT UNIQUE NOT NULL,        -- "g1.globo.com"
  reputation      DECIMAL(3,2) DEFAULT 0.5,   -- 0.0 a 1.0
  category        TEXT,                        -- "portal", "jornal", "revista", "blog"
  logo_url        TEXT,
  active          BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 5. politician_articles (Relação N:N Político-Notícia)

```sql
CREATE TABLE politician_articles (
  politician_id   UUID REFERENCES politicians(id) ON DELETE CASCADE,
  article_id      UUID REFERENCES articles(id) ON DELETE CASCADE,
  role            TEXT DEFAULT 'subject',      -- subject/mentioned/related
  PRIMARY KEY (politician_id, article_id)
);

CREATE INDEX idx_pa_politician ON politician_articles(politician_id);
CREATE INDEX idx_pa_article ON politician_articles(article_id);
```

### 6. article_matches (Match entre Notícias Relacionadas)

```sql
CREATE TABLE article_matches (
  article_a_id    UUID REFERENCES articles(id) ON DELETE CASCADE,
  article_b_id    UUID REFERENCES articles(id) ON DELETE CASCADE,
  similarity      DECIMAL(3,2) NOT NULL,      -- 0.0 a 1.0 (cosine similarity)
  match_type      TEXT DEFAULT 'content',      -- content/entity/temporal
  created_at      TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (article_a_id, article_b_id),
  CHECK (article_a_id < article_b_id)         -- evitar duplicatas
);

CREATE INDEX idx_matches_a ON article_matches(article_a_id);
CREATE INDEX idx_matches_b ON article_matches(article_b_id);
```

### 7. milestones (Marcos na Timeline)

```sql
CREATE TABLE milestones (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  politician_id   UUID REFERENCES politicians(id) ON DELETE CASCADE,
  title           TEXT NOT NULL,               -- "Abertura de Inquérito"
  description     TEXT,                        -- descrição do milestone
  milestone_type  TEXT NOT NULL,               -- inquiry/complaint/conviction/acquittal/arrest/impeachment
  occurred_at     DATE NOT NULL,
  source_url      TEXT,                        -- link para fonte
  article_id      UUID REFERENCES articles(id), -- artigo associado (opcional)
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_milestones_politician ON milestones(politician_id);
CREATE INDEX idx_milestones_date ON milestones(occurred_at DESC);
```

### 8. entities (Entidades do Grafo - não-políticos)

```sql
CREATE TABLE entities (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  entity_type     TEXT NOT NULL,               -- company/organization/lobby/ngo
  description     TEXT,
  score           DECIMAL(5,2) DEFAULT 0,      -- score de envolvimento
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_entities_type ON entities(entity_type);
```

### 9. relationships (Arestas do Grafo)

```sql
CREATE TABLE relationships (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Nós (polimórfico: politician ou entity)
  source_type     TEXT NOT NULL,               -- politician/entity/party
  source_id       UUID NOT NULL,
  target_type     TEXT NOT NULL,               -- politician/entity/party
  target_id       UUID NOT NULL,

  relationship_type TEXT NOT NULL,             -- business/political/family/legal/financial
  weight          INT DEFAULT 1,               -- peso (nº de notícias que fundamentam)
  description     TEXT,                        -- descrição da relação

  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rel_source ON relationships(source_type, source_id);
CREATE INDEX idx_rel_target ON relationships(target_type, target_id);
CREATE INDEX idx_rel_weight ON relationships(weight DESC);
```

### 10. relationship_evidence (Evidências das Relações)

```sql
CREATE TABLE relationship_evidence (
  relationship_id UUID REFERENCES relationships(id) ON DELETE CASCADE,
  article_id      UUID REFERENCES articles(id) ON DELETE CASCADE,
  PRIMARY KEY (relationship_id, article_id)
);
```

---

## Views Úteis

### v_politician_ranking (Ranking com dados completos)

```sql
CREATE VIEW v_politician_ranking AS
SELECT
  p.id, p.slug, p.name, p.score, p.total_news,
  p.state, p.role, p.photo_url, p.severity_max,
  pa.abbreviation AS party, pa.color AS party_color,
  RANK() OVER (ORDER BY p.score DESC) AS position,
  p.first_news_at, p.last_news_at
FROM politicians p
JOIN parties pa ON pa.id = p.party_id
ORDER BY p.score DESC;
```

### v_politician_timeline (Timeline do político)

```sql
CREATE VIEW v_politician_timeline AS
SELECT
  pa2.politician_id,
  a.id AS article_id,
  a.title, a.summary, a.published_at,
  a.veracity_score, a.severity, a.original_url,
  s.name AS source_name, s.domain AS source_domain,
  NULL AS milestone_type, NULL AS milestone_description,
  'article' AS item_type
FROM articles a
JOIN politician_articles pa2 ON pa2.article_id = a.id
JOIN sources s ON s.id = a.source_id

UNION ALL

SELECT
  m.politician_id,
  m.article_id,
  m.title, m.description AS summary, m.occurred_at AS published_at,
  NULL AS veracity_score, NULL AS severity, m.source_url AS original_url,
  NULL AS source_name, NULL AS source_domain,
  m.milestone_type, m.description AS milestone_description,
  'milestone' AS item_type
FROM milestones m

ORDER BY published_at DESC;
```

### v_graph_nodes (Nós do grafo)

```sql
CREATE VIEW v_graph_nodes AS
SELECT id, name, 'politician' AS node_type, score, state, slug, photo_url
FROM politicians
UNION ALL
SELECT id, name, entity_type AS node_type, score, NULL, NULL, NULL
FROM entities
UNION ALL
SELECT id, name, 'party' AS node_type, NULL, NULL, NULL, logo_url
FROM parties;
```

---

## Fluxo de Dados

```
TSE (importação) → politicians + parties
                ↓
Firecrawl (coleta) → articles (raw_content)
                ↓
GPT-4.1-mini (processamento) → articles (summary, veracity_score, severity)
                              → politician_articles (relação N:N)
                              → article_matches (similaridade)
                              → milestones (detecção de marcos)
                              → entities + relationships (extração de entidades)
                ↓
Cron (recálculo) → politicians.score (atualização diária)
                 → politicians.total_news
                 → politicians.severity_max
```

---

## Tipos de Milestone

| Tipo | Ícone | Cor | Descrição |
|------|-------|-----|-----------|
| `inquiry` | Lupa | Azul | Abertura de inquérito |
| `complaint` | Documento | Laranja | Denúncia do MPF/MP |
| `conviction` | Balança | Vermelho | Condenação judicial |
| `acquittal` | Check | Verde | Absolvição |
| `arrest` | Algemas | Vermelho escuro | Prisão |
| `impeachment` | Martelo | Roxo | Impeachment/Cassação |
| `plea_deal` | Aperto de mão | Amarelo | Delação premiada |
| `fine` | Cifrão | Laranja | Multa/Penalidade |

---

## Tipos de Severidade

| Nível | Cor | Score Range | Descrição |
|-------|-----|-------------|-----------|
| `critical` | #EF4444 | 80-100 | Condenação, prisão, desvio milionário |
| `high` | #F97316 | 60-79 | Denúncia formal, inquérito |
| `medium` | #F59E0B | 40-59 | Irregularidade, uso indevido |
| `low` | #3B82F6 | 0-39 | Votação polêmica, declaração controversa |

---

## Score de Veracidade - Pesos

| Sinal | Peso | Fonte |
|-------|------|-------|
| Reputação da fonte | 30% | `sources.reputation` |
| Multi-fonte | 25% | `articles.multi_source_count` |
| Consistência narrativa | 15% | GPT-4.1-mini análise |
| Evidência documental | 10% | GPT-4.1-mini análise |
| Temporalidade | 10% | Cálculo por data |
| Linguagem emocional | 10% | GPT-4.1-mini análise (invertido) |

**Fórmula**: `veracity_score = 0.30*rep + 0.25*multi + 0.15*narrative + 0.10*documental + 0.10*temporal + 0.10*(1-emotional)`
