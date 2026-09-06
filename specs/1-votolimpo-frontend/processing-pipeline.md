# VotoLimpo - Processing Pipeline Specification

**Versao**: 1.0
**Data**: 2026-09-05
**Escopo**: Definicao completa do processamento de artigos coletados via Firecrawl, processados via GPT-4.1-mini, e persistidos no PostgreSQL 16.

---

## Indice

1. [Processing Output Schema (GPT-4.1-mini)](#1-processing-output-schema)
2. [Metricas Extraidas](#2-metricas-extraidas)
3. [Algoritmo de Score do Politico](#3-algoritmo-de-score-do-politico)
4. [Matching de Noticias Relacionadas](#4-matching-de-noticias-relacionadas)
5. [Deteccao de Milestones](#5-deteccao-de-milestones)
6. [Extracao de Entidades e Relacoes](#6-extracao-de-entidades-e-relacoes)
7. [Geracao de Bio e Resumo IA](#7-geracao-de-bio-e-resumo-ia)
8. [Score de Severidade](#8-score-de-severidade)
9. [Validacao Anti-Alucinacao](#9-validacao-anti-alucinacao)
10. [Fluxo Completo do Pipeline](#10-fluxo-completo-do-pipeline)

---

## 1. Processing Output Schema

### 1.1. JSON de Saida do GPT-4.1-mini (por artigo)

Cada artigo coletado pelo Firecrawl e enviado ao GPT-4.1-mini com structured output (`response_format: json_schema`). O modelo retorna EXATAMENTE este schema — nenhum campo opcional, nenhum campo inventado.

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
      "reasoning": "string (1 frase justificando)"
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
    "reasoning": "string (1 frase justificando)"
  },

  "politicians": [
    {
      "name": "string (nome completo como citado no texto)",
      "role_in_article": "subject | mentioned | related",
      "current_role": "string | null (cargo atual se mencionado)",
      "party": "string | null (sigla do partido se mencionado)",
      "state": "string | null (UF se mencionado)",
      "context": "string (1 frase: o que o artigo diz sobre este politico)"
    }
  ],

  "entities": [
    {
      "name": "string",
      "entity_type": "company | organization | lobby | ngo | government_body | court",
      "role_in_article": "string (1 frase: papel da entidade no contexto)"
    }
  ],

  "relationships": [
    {
      "source_name": "string (nome do politico ou entidade)",
      "source_type": "politician | entity",
      "target_name": "string",
      "target_type": "politician | entity | party",
      "relationship_type": "business | political | family | legal | financial",
      "description": "string (1 frase descrevendo a relacao)"
    }
  ],

  "milestones": [
    {
      "title": "string (max 100 chars)",
      "milestone_type": "inquiry | complaint | conviction | acquittal | arrest | impeachment | plea_deal | fine",
      "occurred_at": "YYYY-MM-DD",
      "description": "string (1-2 frases)",
      "politician_name": "string (nome do politico associado)"
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

### 1.2. Regras de Preenchimento

| Campo | Regra | Validacao |
|-------|-------|-----------|
| `title_normalized` | Titulo limpo sem clickbait, max 200 chars | `len(title) <= 200`, nao vazio |
| `summary` | Resumo factual em 2-3 frases. SEM opiniao. SEM adjetivos de valor. | `len(summary) <= 500`, nao vazio |
| `published_at` | Data de publicacao extraida do artigo. `null` se nao encontrada. | ISO 8601 ou null. Nao pode ser data futura. |
| `language` | Idioma detectado do texto | Enum fixo |
| `category` | Categoria principal do artigo | Enum fixo |
| `politicians[]` | Lista de politicos mencionados. Minimo 0 (artigo pode nao citar nenhum). | Cada item tem `name` nao vazio |
| `entities[]` | Entidades nao-politicas mencionadas | Cada item tem `name` e `entity_type` |
| `relationships[]` | Relacoes extraidas SOMENTE se explicitadas no texto | Cada item tem source + target |
| `milestones[]` | Eventos juridicos/politicos importantes. SOMENTE se explicitamente descritos no texto. | `milestone_type` deve ser do enum |
| `veracity_signals.*` | Scores de 0.0 a 1.0 com reasoning obrigatorio | `0.0 <= score <= 1.0` |
| `severity.level` | Classificacao de gravidade | Enum fixo |
| `extraction_confidence.*` | Autoavaliacao de confianca do modelo | `0.0 <= score <= 1.0` |
| `keywords[]` | Max 10 palavras-chave para indexacao | `len(keywords) <= 10` |

### 1.3. System Prompt para GPT-4.1-mini

```
Voce e um analista de inteligencia politica brasileira. Sua tarefa e extrair informacoes
estruturadas de artigos de noticias sobre politicos brasileiros.

REGRAS ABSOLUTAS:
1. Extraia SOMENTE informacoes EXPLICITAMENTE presentes no texto. NAO infira, NAO invente,
   NAO complete com conhecimento externo.
2. Se uma informacao nao esta no texto, use null ou lista vazia. NUNCA alucine dados.
3. O resumo deve ser FACTUAL — sem opiniao, sem adjetivos de valor ("controverso",
   "polemico"). Descreva FATOS.
4. Para milestones: so crie se o texto descreve EXPLICITAMENTE um evento juridico/politico
   (inquerito aberto, denuncia oferecida, condenacao proferida). "Acusacoes" genericas
   NAO sao milestones.
5. Para relationships: so crie se o texto EXPLICITA uma relacao (ex: "empresa X doou para
   campanha de Y"). Coocorrencia no mesmo artigo NAO e relacao.
6. extraction_confidence: seja HONESTO. Se o texto e ambiguo, score baixo. Se esta claro,
   score alto.
7. Nomes de politicos: use o nome completo como aparece no texto. NAO normalize para
   nomes oficiais que voce conhece de treino.
8. severity: baseie-se SOMENTE no conteudo do artigo, nao no historico do politico.

FORMATO: Retorne EXCLUSIVAMENTE o JSON no schema especificado. Sem texto adicional.
```

### 1.4. User Prompt Template

```
Analise o artigo abaixo e extraia as informacoes no formato JSON especificado.

FONTE: {source_name} ({source_domain})
REPUTACAO DA FONTE: {source_reputation}/1.0
URL: {original_url}
DATA DE COLETA: {collected_at}

--- INICIO DO ARTIGO ---
{raw_content}
--- FIM DO ARTIGO ---
```

---

## 2. Metricas Extraidas

### 2.1. Metricas por Artigo (calculadas no momento do processamento)

| Metrica | Campo DB | Formula | Origem |
|---------|----------|---------|--------|
| Score de veracidade | `articles.veracity_score` | Formula ponderada (secao 2.3) | Calculado |
| Reputacao da fonte | `articles.source_reputation` | `sources.reputation` da fonte | Copiado |
| Contagem multi-fonte | `articles.multi_source_count` | Contagem de artigos com `similarity >= 0.7` no `article_matches` | Calculado pos-matching |
| Consistencia narrativa | `articles.narrative_consistency` | `veracity_signals.narrative_consistency.score` | GPT |
| Evidencia documental | `articles.documental_evidence` | `veracity_signals.documental_evidence.score` | GPT |
| Temporalidade | `articles.temporality_score` | Decay baseado em idade do evento (secao 2.4) | Calculado |
| Linguagem emocional | `articles.emotional_language` | `veracity_signals.emotional_language.score` | GPT |
| Severidade | `articles.severity` | `severity.level` | GPT |

### 2.2. Metricas por Politico (recalculadas em batch diario)

| Metrica | Campo DB | Formula |
|---------|----------|---------|
| Score consolidado | `politicians.score` | Algoritmo completo (secao 3) |
| Total de noticias | `politicians.total_news` | `COUNT(politician_articles WHERE politician_id = X)` |
| Severidade maxima | `politicians.severity_max` | `MAX(severity)` de todos os artigos associados (critical > high > medium > low) |
| Primeira noticia | `politicians.first_news_at` | `MIN(articles.published_at)` dos artigos associados |
| Ultima noticia | `politicians.last_news_at` | `MAX(articles.published_at)` dos artigos associados |

### 2.3. Formula do Score de Veracidade (por artigo)

```
veracity_score = (
    0.30 * source_reputation
  + 0.25 * multi_source_normalized
  + 0.15 * narrative_consistency
  + 0.10 * documental_evidence
  + 0.10 * temporality_score
  + 0.10 * (1.0 - emotional_language)
)
```

**Normalizacao de multi_source_count:**

```python
def normalize_multi_source(count: int) -> float:
    """
    1 fonte  = 0.0 (sem corroboracao)
    2 fontes = 0.5
    3 fontes = 0.75
    4+ fontes = 1.0 (saturacao — mais fontes nao melhoram o score)
    """
    if count <= 1:
        return 0.0
    elif count == 2:
        return 0.5
    elif count == 3:
        return 0.75
    else:
        return 1.0
```

**Justificativa dos pesos:**
- Reputacao da fonte (30%): o sinal mais forte e quem publicou. Fontes com historico de acuracia elevam a confianca.
- Multi-fonte (25%): corroboracao independente e o segundo sinal mais forte. Se 3+ fontes cobrem o mesmo fato, a probabilidade de ser verdadeiro aumenta significativamente.
- Consistencia narrativa (15%): artigos com narrativa coerente, sem contradicoes internas, sao mais confiaveis.
- Evidencia documental (10%): referencias a documentos oficiais, numeros de processo, leis citadas elevam a confianca.
- Temporalidade (10%): noticias recentes sobre eventos recentes sao mais confiaveis que noticias tardias.
- Linguagem emocional invertida (10%): textos neutros e factuais sao mais confiaveis que textos carregados de emocao.

### 2.4. Score de Temporalidade

```python
from datetime import date, timedelta

def calculate_temporality_score(published_at: date, event_date: date | None) -> float:
    """
    Mede o quao proximo temporalmente o artigo esta do evento que descreve.

    - Se event_date nao disponivel: usa published_at vs data de coleta.
    - Artigo publicado no mesmo dia do evento = 1.0
    - Artigo publicado 30+ dias apos o evento = 0.2 (floor)

    Decay linear: score = max(0.2, 1.0 - (delta_days / 30) * 0.8)
    """
    if event_date is None:
        # Fallback: artigos mais recentes recebem score mais alto
        # Usa a data de coleta como referencia
        today = date.today()
        delta = (today - published_at).days
    else:
        delta = abs((published_at - event_date).days)

    if delta <= 0:
        return 1.0
    elif delta >= 30:
        return 0.2
    else:
        return round(max(0.2, 1.0 - (delta / 30) * 0.8), 2)
```

### 2.5. Metricas Agregadas (dashboard global)

| Metrica | Formula | Uso na UI |
|---------|---------|-----------|
| Total de politicos catalogados | `COUNT(politicians)` | Contador na home |
| Total de noticias processadas | `COUNT(articles WHERE ai_processed = true)` | Contador na home |
| Total de fontes monitoradas | `COUNT(sources WHERE active = true)` | Contador na home |
| Media de veracidade por fonte | `AVG(veracity_score) GROUP BY source_id` | Ranking de fontes |
| Distribuicao de severidade | `COUNT(*) GROUP BY severity` | Grafico do perfil |

---

## 3. Algoritmo de Score do Politico

### 3.1. Conceito

O score do politico (0-100) representa a "carga de polemicas" acumulada. Score MAIS ALTO = MAIS polemicas/corrupcao. NAO e um score de "reputacao positiva" — e um score de "exposicao negativa verificada".

### 3.2. Formula Completa

```python
import math
from datetime import date, timedelta
from typing import List, NamedTuple

class ArticleData(NamedTuple):
    veracity_score: float      # 0.0 a 1.0
    severity: str              # critical/high/medium/low
    published_at: date
    role: str                  # subject/mentioned/related

# Pesos de severidade
SEVERITY_WEIGHT = {
    'critical': 10.0,
    'high': 6.0,
    'medium': 3.0,
    'low': 1.0,
}

# Pesos de role (papel do politico no artigo)
ROLE_WEIGHT = {
    'subject': 1.0,       # protagonista da noticia
    'mentioned': 0.5,     # mencionado mas nao e o foco
    'related': 0.25,      # citado tangencialmente
}

def calculate_politician_score(articles: List[ArticleData]) -> float:
    """
    Calcula o score consolidado do politico (0-100).

    Componentes:
    1. Soma ponderada de artigos (severity * veracity * role * recency_decay)
    2. Bonus de volume (log-scale para nao explodir com muitas noticias)
    3. Bonus de recencia (noticias recentes pesam mais)
    4. Normalizacao sigmoid para escala 0-100
    """
    if not articles:
        return 0.0

    today = date.today()

    # --- Componente 1: Soma ponderada ---
    weighted_sum = 0.0
    for art in articles:
        severity_w = SEVERITY_WEIGHT.get(art.severity, 1.0)
        role_w = ROLE_WEIGHT.get(art.role, 0.25)
        veracity_w = art.veracity_score  # so conta se a noticia e verificada

        # Recency decay: artigos dos ultimos 180 dias pesam mais
        days_old = (today - art.published_at).days
        recency_decay = max(0.1, 1.0 - (days_old / 365) * 0.5)
        # 0 dias = 1.0, 365 dias = 0.5, 730+ dias = 0.1

        weighted_sum += severity_w * role_w * veracity_w * recency_decay

    # --- Componente 2: Bonus de volume (log-scale) ---
    # log2(n) garante que 1 artigo = 0, 2 = 1, 4 = 2, 8 = 3, etc.
    volume_bonus = math.log2(max(1, len(articles)))

    # --- Componente 3: Bonus de recencia ---
    # Ultimos 30 dias: multiplier 1.5x
    recent_count = sum(1 for a in articles if (today - a.published_at).days <= 30)
    recency_bonus = min(recent_count * 0.5, 3.0)  # cap em 3.0

    # --- Score bruto ---
    raw_score = weighted_sum + volume_bonus + recency_bonus

    # --- Normalizacao sigmoid para 0-100 ---
    # sigmoid(x) = 100 / (1 + e^(-k*(x - midpoint)))
    # midpoint = 20 (politico com ~5 noticias high = ~50 pontos)
    # k = 0.15 (controla inclinacao)
    normalized = 100.0 / (1.0 + math.exp(-0.15 * (raw_score - 20)))

    return round(normalized, 2)
```

### 3.3. Propriedades do Algoritmo

| Propriedade | Comportamento |
|-------------|---------------|
| Politico sem noticias | Score = 0.0 |
| 1 noticia low, veracidade 0.5 | Score ~ 2-5 (quase zero) |
| 5 noticias high, veracidade 0.8 | Score ~ 40-55 |
| 10 noticias critical, veracidade 0.9 | Score ~ 85-95 |
| 50 noticias medium, veracidade 0.6 | Score ~ 60-70 |
| Noticias antigas (>1 ano) | Peso reduzido via recency_decay (0.5x) |
| Noticias recentes (<30 dias) | Bonus de recencia (ate +3.0) |
| Politico "mentioned" em muitas noticias | Cada noticia pesa 0.5x vs "subject" |
| Noticia com veracidade 0.1 | Peso quase nulo (nao penaliza se desinformacao) |

### 3.4. Recalculo

- **Frequencia**: Cron diario as 03:00 UTC
- **Escopo**: Todos os politicos com `last_news_at >= now() - interval '1 year'` OU `total_news > 0`
- **Query de recalculo**:

```sql
-- Buscar dados para recalculo
SELECT
    pa.politician_id,
    pa.role,
    a.veracity_score,
    a.severity,
    a.published_at
FROM politician_articles pa
JOIN articles a ON a.id = pa.article_id
WHERE a.ai_processed = true
  AND a.veracity_score IS NOT NULL
ORDER BY pa.politician_id;
```

```sql
-- Atualizar scores (apos calculo em Python)
UPDATE politicians SET
    score = $1,
    total_news = $2,
    severity_max = $3,
    first_news_at = $4,
    last_news_at = $5,
    updated_at = now()
WHERE id = $6;
```

### 3.5. Calibracao e Benchmarks

Para calibrar o midpoint (20) e o k (0.15) da sigmoid, usar estes cenarios de referencia:

| Cenario | raw_score esperado | Score final esperado |
|---------|-------------------|---------------------|
| Politico limpo (0 noticias) | 0 | 0 |
| Politico com 1 noticia low | ~1.5 | ~5 |
| Politico com 3 noticias medium | ~10 | ~20 |
| Politico com 5 noticias high | ~30 | ~65 |
| Politico "mensalao" (20+ noticias critical) | ~100+ | ~95+ |

Se os scores nao baterem com estes benchmarks apos implementacao, ajustar `midpoint` e `k`.

---

## 4. Matching de Noticias Relacionadas

### 4.1. Estrategia

Tres sinais para identificar noticias relacionadas, avaliados em camadas:

| Sinal | Peso | Descricao |
|-------|------|-----------|
| **Entity overlap** | 0.40 | Politicos e entidades em comum |
| **Keyword overlap** | 0.35 | Keywords em comum (extraidas pelo GPT) |
| **Temporal proximity** | 0.25 | Publicadas em janela temporal proxima |

NAO usar embedding semantico no MVP. Custo alto (embedding de 15k+ artigos) e o entity/keyword overlap ja captura 80%+ dos casos relevantes.

### 4.2. Algoritmo

```python
from datetime import date, timedelta
from typing import Set

def calculate_article_similarity(
    article_a_politicians: Set[str],    # UUIDs dos politicos
    article_b_politicians: Set[str],
    article_a_entities: Set[str],       # UUIDs das entidades
    article_b_entities: Set[str],
    article_a_keywords: Set[str],       # keywords normalizadas (lowercase, sem acento)
    article_b_keywords: Set[str],
    article_a_date: date,
    article_b_date: date,
) -> tuple[float, str]:
    """
    Retorna (similarity: 0.0-1.0, match_type: content|entity|temporal)
    """
    # --- Entity overlap (Jaccard) ---
    all_entities_a = article_a_politicians | article_a_entities
    all_entities_b = article_b_politicians | article_b_entities

    if all_entities_a and all_entities_b:
        entity_jaccard = len(all_entities_a & all_entities_b) / len(all_entities_a | all_entities_b)
    else:
        entity_jaccard = 0.0

    # --- Keyword overlap (Jaccard) ---
    if article_a_keywords and article_b_keywords:
        keyword_jaccard = len(article_a_keywords & article_b_keywords) / len(article_a_keywords | article_b_keywords)
    else:
        keyword_jaccard = 0.0

    # --- Temporal proximity ---
    delta_days = abs((article_a_date - article_b_date).days)
    if delta_days <= 3:
        temporal_score = 1.0
    elif delta_days <= 7:
        temporal_score = 0.8
    elif delta_days <= 14:
        temporal_score = 0.5
    elif delta_days <= 30:
        temporal_score = 0.2
    else:
        temporal_score = 0.0

    # --- Score composto ---
    similarity = (
        0.40 * entity_jaccard
      + 0.35 * keyword_jaccard
      + 0.25 * temporal_score
    )

    # --- Match type (baseado no sinal dominante) ---
    if entity_jaccard >= keyword_jaccard and entity_jaccard >= temporal_score:
        match_type = 'entity'
    elif keyword_jaccard >= temporal_score:
        match_type = 'content'
    else:
        match_type = 'temporal'

    return round(similarity, 2), match_type
```

### 4.3. Threshold e Persistencia

- **Threshold para persistir**: `similarity >= 0.30`
- **Threshold para "noticias relacionadas" na UI**: `similarity >= 0.50`
- **Threshold para contagem multi_source**: `similarity >= 0.70` (mesmo caso, fontes diferentes)

### 4.4. Janela de Comparacao

Para evitar comparacao O(n^2) com todo o banco:
- Novo artigo: comparar apenas com artigos dos ultimos **90 dias**
- Batch semanal: recalcular matches de artigos dos ultimos **30 dias** (captura late-arrivals)

### 4.5. Atualizacao de multi_source_count

```sql
-- Apos calcular matches, atualizar multi_source_count
UPDATE articles a SET
    multi_source_count = (
        SELECT COUNT(DISTINCT a2.source_id) + 1
        FROM article_matches am
        JOIN articles a2 ON (
            (am.article_a_id = a.id AND am.article_b_id = a2.id) OR
            (am.article_b_id = a.id AND am.article_a_id = a2.id)
        )
        WHERE am.similarity >= 0.70
          AND a2.source_id != a.source_id
    )
WHERE a.id = $1;
```

---

## 5. Deteccao de Milestones

### 5.1. Tipos e Criterios de Deteccao

Milestones sao eventos juridicos/politicos discretos e verificaveis. O GPT-4.1-mini so deve gerar um milestone se o texto contem **evidencia explicita** do evento.

| Tipo | Evidencia Necessaria | Exemplos de Trigger Textual |
|------|---------------------|----------------------------|
| `inquiry` | Mencao explicita a abertura de inquerito | "PF abre inquerito", "inquerito instaurado", "STF autoriza investigacao" |
| `complaint` | Denuncia formal oferecida | "MPF denuncia", "denuncia aceita pelo", "PGR oferece denuncia" |
| `conviction` | Condenacao judicial proferida | "condenado a", "TRF condena", "juiz sentenciou", "condenacao em segunda instancia" |
| `acquittal` | Absolvicao judicial | "absolvido de", "tribunal absolve", "arquivamento do processo" |
| `arrest` | Prisao efetiva | "preso pela PF", "mandado de prisao", "detido na operacao" |
| `impeachment` | Cassacao ou processo de impeachment | "cassacao aprovada", "processo de impeachment", "perda do mandato" |
| `plea_deal` | Delacao premiada | "delacao premiada", "acordo de colaboracao", "delatou" |
| `fine` | Multa ou penalidade financeira | "multa de R$", "TSE multa", "condenado ao pagamento de" |

### 5.2. Regras de Validacao

1. **Obrigatorio `occurred_at`**: Todo milestone deve ter data. Se o texto nao menciona data explicita, o modelo deve usar a data de publicacao do artigo como fallback.
2. **Obrigatorio `politician_name`**: Todo milestone deve estar associado a um politico nomeado.
3. **Deduplicacao**: Antes de inserir, verificar se ja existe milestone do mesmo tipo, para o mesmo politico, na mesma data (+-7 dias). Se existir, nao duplicar.
4. **Confianca minima**: So persistir milestones onde `extraction_confidence.milestones_confidence >= 0.7`.

### 5.3. Query de Deduplicacao

```sql
SELECT EXISTS (
    SELECT 1 FROM milestones m
    JOIN politicians p ON p.id = m.politician_id
    WHERE p.name ILIKE $1           -- nome do politico (fuzzy)
      AND m.milestone_type = $2     -- mesmo tipo
      AND ABS(m.occurred_at - $3::date) <= 7  -- janela de 7 dias
) AS already_exists;
```

---

## 6. Extracao de Entidades e Relacoes

### 6.1. Pipeline de Entidades

```
Artigo (raw_content)
  → GPT extrai entities[] e relationships[]
  → Normalizar nomes (trim, title case)
  → Buscar entidade existente no DB (fuzzy match: trigram similarity >= 0.85)
    → Encontrou: reusar ID existente
    → Nao encontrou: INSERT nova entidade
  → Persistir relacoes com evidencia (relationship_evidence)
```

### 6.2. Normalizacao de Nomes

```python
import unicodedata
import re

def normalize_entity_name(name: str) -> str:
    """
    Normaliza nome de entidade para matching.
    'PETROBRAS S.A.' → 'Petrobras SA'
    'Empresa XYZ Ltda.' → 'Empresa Xyz'
    """
    # Remove acentos para matching
    name = name.strip()
    # Remove sufixos corporativos comuns
    suffixes = [' S.A.', ' SA', ' S/A', ' Ltda.', ' Ltda', ' LTDA',
                ' Eireli', ' ME', ' EPP', ' Inc.', ' Corp.']
    for suffix in suffixes:
        if name.upper().endswith(suffix.upper()):
            name = name[:len(name) - len(suffix)]
    return name.strip().title()

def normalize_for_search(name: str) -> str:
    """Remove acentos e lowercase para busca fuzzy."""
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
```

### 6.3. Fuzzy Match no PostgreSQL

```sql
-- Requer extensao pg_trgm
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Buscar entidade similar
SELECT id, name, entity_type,
       similarity(name, $1) AS sim
FROM entities
WHERE similarity(name, $1) >= 0.85
ORDER BY sim DESC
LIMIT 1;
```

### 6.4. Resolucao de Politicos

Politicos extraidos pelo GPT precisam ser resolvidos contra a tabela `politicians`:

```python
def resolve_politician(extracted_name: str, party: str | None, state: str | None) -> str | None:
    """
    Tenta resolver o nome extraido para um politician.id existente.

    Estrategia em cascata:
    1. Match exato por nome
    2. Match fuzzy por nome (trigram >= 0.80)
    3. Match fuzzy por nome + partido (se disponivel)
    4. None (nao resolvido — log para revisao manual)
    """
    pass  # implementacao usa queries SQL com pg_trgm
```

```sql
-- Resolucao com multiplos sinais
SELECT id, name, slug,
       similarity(name, $1) AS name_sim
FROM politicians p
LEFT JOIN parties pa ON pa.id = p.party_id
WHERE similarity(p.name, $1) >= 0.80
  AND ($2 IS NULL OR pa.abbreviation = $2)  -- partido como filtro opcional
  AND ($3 IS NULL OR p.state = $3)           -- estado como filtro opcional
ORDER BY name_sim DESC
LIMIT 1;
```

### 6.5. Persistencia de Relacoes

```sql
-- Inserir relacao (ou incrementar peso se ja existe)
INSERT INTO relationships (source_type, source_id, target_type, target_id, relationship_type, weight, description)
VALUES ($1, $2, $3, $4, $5, 1, $6)
ON CONFLICT ON (
    -- Precisa de unique constraint ou busca manual
    -- Constraint sugerida:
    -- UNIQUE(source_type, source_id, target_type, target_id, relationship_type)
)
DO UPDATE SET
    weight = relationships.weight + 1,
    updated_at = now();

-- Inserir evidencia
INSERT INTO relationship_evidence (relationship_id, article_id)
VALUES ($1, $2)
ON CONFLICT DO NOTHING;
```

**NOTA**: Adicionar unique constraint na tabela `relationships`:

```sql
ALTER TABLE relationships
ADD CONSTRAINT uq_relationship_pair
UNIQUE (source_type, source_id, target_type, target_id, relationship_type);
```

---

## 7. Geracao de Bio e Resumo IA

### 7.1. Campos Adicionais Necessarios

O schema atual de `politicians` NAO possui campos para bio e resumo_ia. Adicionar:

```sql
ALTER TABLE politicians ADD COLUMN bio TEXT;          -- bio curta (1-2 frases)
ALTER TABLE politicians ADD COLUMN ai_summary TEXT;   -- resumo IA (3-5 frases)
ALTER TABLE politicians ADD COLUMN ai_summary_at TIMESTAMPTZ; -- quando foi gerado
```

### 7.2. Geracao de Bio

A bio e uma descricao factual curta do politico. NAO menciona polemicas — apenas dados publicos.

**Template de prompt:**

```
Com base nos dados abaixo, gere uma bio curta (1-2 frases) FACTUAL do politico.
NAO mencione polemicas ou investigacoes. Apenas dados publicos: cargo, partido, estado,
historico politico basico.

Nome: {name}
Partido: {party}
Cargo: {role}
Estado: {state}
Periodo de noticias: {first_news_at} a {last_news_at}

Formato: 1-2 frases factuais, max 200 caracteres.
```

**Exemplo de saida:**
```
"Deputado Federal por SP pelo PT desde 2019. Ex-vereador de Sao Paulo (2013-2018)."
```

### 7.3. Geracao de Resumo IA

O resumo_ia sintetiza os PRINCIPAIS casos/polemicas do politico baseado nos artigos processados.

**Quando gerar**: A cada recalculo diario, para politicos com `total_news >= 3`.

**Template de prompt:**

```
Voce e um analista de transparencia politica. Com base nos resumos das noticias abaixo,
gere um paragrafo de sintese (3-5 frases) sobre os principais casos envolvendo este politico.

REGRAS:
1. Seja FACTUAL — descreva fatos, nao opinioes.
2. Priorize noticias de alta severidade (critical > high > medium > low).
3. Mencione datas quando relevante.
4. NAO use adjetivos de valor ("controverso", "polemico", "corrupto").
5. Use linguagem neutra de relatorio.

POLITICO: {name} ({party}-{state}), {role}
SCORE: {score}/100

NOTICIAS (ordenadas por severidade e data):
{for each article, top 20 by severity then recency:}
- [{published_at}] [{severity}] {title}
  {summary}
{end for}

Formato: 3-5 frases factuais, max 600 caracteres.
```

**Exemplo de saida:**
```
"Jose da Silva e alvo de tres investigacoes na Policia Federal desde 2024,
envolvendo desvio de emendas parlamentares no valor de R$ 12 milhoes.
Em janeiro de 2026, o MPF ofereceu denuncia por peculato e lavagem de dinheiro.
O deputado teve o sigilo bancario quebrado por decisao do STF em marco de 2026.
Nao ha condenacao ate o momento."
```

### 7.4. Frequencia e Cache

- **Bio**: Gerada uma vez, atualizada somente se o cargo ou partido mudar.
- **Resumo IA**: Regenerado no cron diario para politicos com noticias nos ultimos 30 dias.
- **Cache**: `ai_summary_at` permite saber quando foi gerado. Skip se `ai_summary_at > last_news_at`.

---

## 8. Score de Severidade

### 8.1. Criterios Objetivos

O GPT-4.1-mini classifica a severidade de cada artigo. Os criterios devem estar NO system prompt para consistencia:

| Nivel | Criterios (TODOS devem ser avaliados) | Exemplos |
|-------|--------------------------------------|----------|
| `critical` | Condenacao criminal transitada em julgado, prisao, desvio de recursos publicos > R$1M, envolvimento com crime organizado, trafego de influencia comprovado | "Condenado a 12 anos por corrupcao passiva", "Preso na Operacao Lava Jato" |
| `high` | Denuncia formal aceita pelo judiciario, inquerito policial instaurado, quebra de sigilo, afastamento do cargo, desvio < R$1M | "MPF denuncia por improbidade", "STF aceita denuncia", "Afastado pelo TRE" |
| `medium` | Irregularidade administrativa, uso indevido de verba publica, nepotismo, conflito de interesse documentado, multa | "TCU aponta irregularidades", "Nomeou parente para cargo", "Multado pelo TSE" |
| `low` | Votacao polemica, declaracao controversa, processo administrativo, acusacao sem fundamento documental | "Votou contra projeto X", "Declaracao sobre Y gera criticas" |

### 8.2. Escala Numerica (para ordenacao interna)

```python
SEVERITY_NUMERIC = {
    'critical': 4,
    'high': 3,
    'medium': 2,
    'low': 1,
}

# Para o campo severity_max do politico:
def calculate_severity_max(article_severities: list[str]) -> str:
    if not article_severities:
        return 'low'
    return max(article_severities, key=lambda s: SEVERITY_NUMERIC.get(s, 0))
```

### 8.3. Instrucao no System Prompt

Adicionar ao system prompt do GPT-4.1-mini:

```
CLASSIFICACAO DE SEVERIDADE (use SOMENTE estes criterios):

CRITICAL: Condenacao criminal, prisao, desvio > R$1M, crime organizado, trafego de
influencia COMPROVADO em decisao judicial.
HIGH: Denuncia formal ACEITA pelo judiciario, inquerito instaurado, quebra de sigilo
judicial, afastamento do cargo.
MEDIUM: Irregularidade administrativa documentada por orgao oficial (TCU, CGU, MP),
nepotismo, conflito de interesse, multa.
LOW: Votacao polemica, declaracao controversa, processo administrativo, acusacoes
sem evidencia documental.

NA DUVIDA ENTRE DOIS NIVEIS: escolha o MENOR. Nao infle severidade.
```

---

## 9. Validacao Anti-Alucinacao

### 9.1. Checks Automaticos (pos-processamento)

Cada resposta do GPT-4.1-mini passa por validacao automatica ANTES de persistir:

```python
from dataclasses import dataclass
from typing import List

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

def validate_processing_output(output: dict, raw_content: str, source_domain: str) -> ValidationResult:
    errors = []
    warnings = []

    # --- CHECK 1: Schema compliance ---
    required_fields = ['article', 'veracity_signals', 'severity', 'politicians',
                       'entities', 'relationships', 'milestones', 'keywords',
                       'extraction_confidence']
    for field in required_fields:
        if field not in output:
            errors.append(f"Campo obrigatorio ausente: {field}")

    # --- CHECK 2: Score ranges ---
    for signal_name in ['narrative_consistency', 'documental_evidence', 'emotional_language']:
        signal = output.get('veracity_signals', {}).get(signal_name, {})
        score = signal.get('score')
        if score is not None and not (0.0 <= score <= 1.0):
            errors.append(f"Score fora do range [0,1]: {signal_name}={score}")

    # --- CHECK 3: Datas nao futuras ---
    pub_date = output.get('article', {}).get('published_at')
    if pub_date:
        from datetime import date
        try:
            parsed = date.fromisoformat(pub_date)
            if parsed > date.today():
                errors.append(f"Data futura detectada: {pub_date}")
        except ValueError:
            errors.append(f"Data invalida: {pub_date}")

    for ms in output.get('milestones', []):
        ms_date = ms.get('occurred_at')
        if ms_date:
            try:
                parsed = date.fromisoformat(ms_date)
                if parsed > date.today():
                    errors.append(f"Milestone com data futura: {ms_date}")
            except ValueError:
                errors.append(f"Milestone com data invalida: {ms_date}")

    # --- CHECK 4: Nomes de politicos existem no texto ---
    raw_lower = raw_content.lower() if raw_content else ""
    for pol in output.get('politicians', []):
        name = pol.get('name', '')
        # Verificar se pelo menos o sobrenome aparece no texto
        parts = name.split()
        if parts:
            last_name = parts[-1].lower()
            if len(last_name) > 3 and last_name not in raw_lower:
                warnings.append(f"Sobrenome '{last_name}' nao encontrado no texto (politico: {name})")

    # --- CHECK 5: Entidades existem no texto ---
    for ent in output.get('entities', []):
        name = ent.get('name', '')
        # Pelo menos parte do nome deve aparecer no texto
        name_parts = name.split()
        found = any(part.lower() in raw_lower for part in name_parts if len(part) > 3)
        if not found and name:
            warnings.append(f"Entidade '{name}' nao encontrada no texto")

    # --- CHECK 6: Severity coherence ---
    severity = output.get('severity', {}).get('level', 'low')
    has_milestone = len(output.get('milestones', [])) > 0
    if severity == 'low' and has_milestone:
        warnings.append("Severidade 'low' mas contem milestones — verificar se a severidade esta correta")

    # --- CHECK 7: Confidence thresholds ---
    confidence = output.get('extraction_confidence', {})
    overall = confidence.get('overall_confidence', 0)
    if overall < 0.3:
        warnings.append(f"Confianca geral muito baixa ({overall}) — considerar reprocessamento")

    # --- CHECK 8: Milestones sem politician_name ---
    for ms in output.get('milestones', []):
        if not ms.get('politician_name'):
            errors.append(f"Milestone sem politico associado: {ms.get('title')}")

    # --- CHECK 9: Titulo normalizado vs original ---
    title = output.get('article', {}).get('title_normalized', '')
    if len(title) > 200:
        errors.append(f"Titulo excede 200 chars: {len(title)}")
    if not title:
        errors.append("Titulo vazio")

    # --- CHECK 10: Summary length ---
    summary = output.get('article', {}).get('summary', '')
    if len(summary) > 500:
        errors.append(f"Summary excede 500 chars: {len(summary)}")

    # --- CHECK 11: Enum validation ---
    valid_severities = {'critical', 'high', 'medium', 'low'}
    if severity not in valid_severities:
        errors.append(f"Severity invalida: {severity}")

    valid_categories = {'corruption', 'investigation', 'trial', 'legislation',
                        'scandal', 'misconduct', 'acquittal', 'other'}
    category = output.get('article', {}).get('category')
    if category and category not in valid_categories:
        errors.append(f"Category invalida: {category}")

    valid_roles = {'subject', 'mentioned', 'related'}
    for pol in output.get('politicians', []):
        role = pol.get('role_in_article')
        if role and role not in valid_roles:
            errors.append(f"Role invalida para politico {pol.get('name')}: {role}")

    valid_milestone_types = {'inquiry', 'complaint', 'conviction', 'acquittal',
                             'arrest', 'impeachment', 'plea_deal', 'fine'}
    for ms in output.get('milestones', []):
        ms_type = ms.get('milestone_type')
        if ms_type and ms_type not in valid_milestone_types:
            errors.append(f"Milestone type invalido: {ms_type}")

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
```

### 9.2. Politica de Reprocessamento

| Resultado da Validacao | Acao |
|------------------------|------|
| 0 errors, 0 warnings | Persistir normalmente |
| 0 errors, 1+ warnings | Persistir + log warnings para revisao manual semanal |
| 1+ errors | NAO persistir. Reprocessar com prompt refinado (max 1 retry) |
| Retry tambem falha | Marcar artigo como `ai_processed = false` + log para revisao manual |

### 9.3. Metricas de Qualidade do Pipeline

Monitorar semanalmente:

| Metrica | Calculo | Alerta se |
|---------|---------|-----------|
| Taxa de validacao | `artigos_validos / artigos_processados` | < 90% |
| Taxa de warnings | `artigos_com_warnings / artigos_validos` | > 30% |
| Taxa de retry | `artigos_reprocessados / artigos_processados` | > 10% |
| Confianca media | `AVG(extraction_confidence.overall_confidence)` | < 0.6 |
| Politicos nao resolvidos | `COUNT(politician_name sem match no DB)` | > 20% |
| Entidades fantasma | `COUNT(warnings de "entidade nao encontrada no texto")` | > 15% |

### 9.4. Amostragem para Revisao Manual

- **Frequencia**: Semanal
- **Tamanho**: 5% dos artigos processados na semana (minimo 10, maximo 50)
- **Criterio de selecao**: Priorizar artigos com `extraction_confidence.overall_confidence < 0.5` e artigos com warnings
- **Checklist de revisao**:
  - [ ] Politicos extraidos realmente aparecem no texto?
  - [ ] Entidades extraidas existem no texto?
  - [ ] Milestones sao justificados pelo texto?
  - [ ] Severidade coerente com o conteudo?
  - [ ] Resumo e factual e sem opiniao?
  - [ ] Relacoes sao explicitas no texto (nao inferidas)?

---

## 10. Fluxo Completo do Pipeline

### 10.1. Diagrama

```
                    ┌─────────────────┐
                    │   Firecrawl     │
                    │  (coleta web)   │
                    └────────┬────────┘
                             │ raw_content + original_url + source_domain
                             ▼
                    ┌─────────────────┐
                    │  Source Lookup   │
                    │  (buscar/criar  │
                    │   fonte no DB)  │
                    └────────┬────────┘
                             │ source_id + source_reputation
                             ▼
                    ┌─────────────────┐
                    │  Deduplicacao   │
                    │  (URL unica?)   │
                    └────────┬────────┘
                             │ artigo novo confirmado
                             ▼
                    ┌─────────────────┐
                    │  INSERT article │
                    │  (raw_content,  │
                    │  ai_processed   │
                    │  = false)       │
                    └────────┬────────┘
                             │ article_id
                             ▼
                    ┌─────────────────┐
                    │  GPT-4.1-mini   │
                    │  (structured    │
                    │   output)       │
                    └────────┬────────┘
                             │ JSON de saida (secao 1)
                             ▼
                    ┌─────────────────┐
                    │  Validacao      │
                    │  Anti-Alucinacao│
                    │  (secao 9)      │
                    └────────┬────────┘
                        ┌────┴────┐
                   VALIDO      INVALIDO
                     │            │
                     │            ▼
                     │     Retry (1x)
                     │     ou skip + log
                     ▼
              ┌──────────────┐
              │ Persistencia │
              │ (transacao)  │
              └──────┬───────┘
                     │
         ┌───────────┼───────────┬───────────────┐
         ▼           ▼           ▼               ▼
   ┌──────────┐ ┌────────┐ ┌─────────┐   ┌────────────┐
   │ UPDATE   │ │ Resolve│ │ Resolve │   │ INSERT     │
   │ article  │ │ politi-│ │ entida- │   │ milestones │
   │ (scores, │ │ cians  │ │ des     │   │ (dedupli-  │
   │ summary) │ │ → pol_ │ │ → rela- │   │  cados)    │
   └──────────┘ │ arti-  │ │ tions + │   └────────────┘
                │ cles   │ │ evidence│
                └────────┘ └─────────┘
                     │
                     ▼
              ┌──────────────┐
              │ Matching     │
              │ (comparar    │
              │ com artigos  │
              │ recentes)    │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ UPDATE       │
              │ multi_source │
              │ _count       │
              └──────┬───────┘
                     │
                     ▼
              ┌──────────────┐
              │ Recalcular   │
              │ veracity_    │
              │ score (com   │
              │ multi_source)│
              └──────────────┘
```

### 10.2. Transacao de Persistencia

```sql
BEGIN;

-- 1. Atualizar artigo com dados processados
UPDATE articles SET
    title = $title_normalized,
    summary = $summary,
    published_at = COALESCE($published_at, published_at),
    source_reputation = $source_reputation,
    narrative_consistency = $narrative_consistency,
    documental_evidence = $documental_evidence,
    emotional_language = $emotional_language,
    severity = $severity,
    ai_processed = true,
    updated_at = now()
WHERE id = $article_id;

-- 2. Inserir politician_articles (para cada politico resolvido)
INSERT INTO politician_articles (politician_id, article_id, role)
VALUES ($politician_id, $article_id, $role)
ON CONFLICT DO NOTHING;

-- 3. Inserir/atualizar entidades
INSERT INTO entities (name, entity_type, description)
VALUES ($name, $entity_type, $role_in_article)
ON CONFLICT (name, entity_type) DO UPDATE SET
    description = COALESCE(EXCLUDED.description, entities.description);

-- 4. Inserir/atualizar relacoes
INSERT INTO relationships (source_type, source_id, target_type, target_id, relationship_type, weight, description)
VALUES ($source_type, $source_id, $target_type, $target_id, $rel_type, 1, $description)
ON CONFLICT ON CONSTRAINT uq_relationship_pair DO UPDATE SET
    weight = relationships.weight + 1,
    updated_at = now();

-- 5. Inserir evidencia de relacao
INSERT INTO relationship_evidence (relationship_id, article_id)
VALUES ($relationship_id, $article_id)
ON CONFLICT DO NOTHING;

-- 6. Inserir milestones (deduplicados)
INSERT INTO milestones (politician_id, title, description, milestone_type, occurred_at, source_url, article_id)
SELECT $politician_id, $title, $description, $milestone_type, $occurred_at, $source_url, $article_id
WHERE NOT EXISTS (
    SELECT 1 FROM milestones
    WHERE politician_id = $politician_id
      AND milestone_type = $milestone_type
      AND ABS(occurred_at - $occurred_at) <= 7
);

COMMIT;
```

### 10.3. Cron Jobs

| Job | Frequencia | Descricao |
|-----|------------|-----------|
| **article_processor** | A cada 15min | Processa artigos com `ai_processed = false` (batch de 20) |
| **article_matcher** | A cada 1h | Calcula matches para artigos processados na ultima hora |
| **politician_score** | Diario 03:00 UTC | Recalcula score de todos os politicos ativos |
| **ai_summary** | Diario 04:00 UTC | Regenera resumo IA para politicos com noticias nos ultimos 30 dias |
| **quality_report** | Semanal (dom 06:00 UTC) | Gera metricas de qualidade do pipeline (secao 9.3) |

### 10.4. Indices Adicionais Recomendados

```sql
-- Para deduplicacao de URLs
CREATE UNIQUE INDEX idx_articles_url ON articles(original_url);

-- Para busca fuzzy de nomes (requer pg_trgm)
CREATE INDEX idx_politicians_name_trgm ON politicians USING gin(name gin_trgm_ops);
CREATE INDEX idx_entities_name_trgm ON entities USING gin(name gin_trgm_ops);

-- Para entity deduplication
ALTER TABLE entities ADD CONSTRAINT uq_entity_name_type UNIQUE (name, entity_type);

-- Para matching eficiente
CREATE INDEX idx_articles_processed_date ON articles(published_at DESC) WHERE ai_processed = true;

-- Para keywords (futuro: full-text search)
-- ALTER TABLE articles ADD COLUMN keywords TEXT[];
-- CREATE INDEX idx_articles_keywords ON articles USING gin(keywords);
```

### 10.5. Estimativa de Custos GPT-4.1-mini

| Etapa | Input tokens (est.) | Output tokens (est.) | Custo por artigo |
|-------|--------------------|--------------------|-----------------|
| Processamento de artigo | ~2000 (raw_content medio) | ~800 (JSON de saida) | ~$0.0005 |
| Geracao de resumo IA | ~3000 (top 20 noticias) | ~200 (resumo) | ~$0.0004 |
| Geracao de bio | ~200 (dados basicos) | ~100 (bio) | ~$0.00005 |

**Projecao mensal** (10.000 artigos/mes): ~$5-7 USD em API costs.

---

## Apendice A: Exemplo Completo de Processing Output

```json
{
  "$schema": "article_processing_v1",

  "article": {
    "title_normalized": "PF indicia deputado Jose da Silva por desvio de emendas parlamentares",
    "summary": "A Policia Federal indiciou o deputado federal Jose da Silva (PT-SP) por suposto desvio de R$ 12 milhoes em emendas parlamentares entre 2022 e 2025. O inquerito aponta que os recursos foram direcionados a empresas ligadas a familiares do parlamentar.",
    "published_at": "2026-08-15",
    "language": "pt-BR",
    "category": "investigation"
  },

  "veracity_signals": {
    "narrative_consistency": {
      "score": 0.85,
      "reasoning": "Narrativa coerente com datas, valores e fontes oficiais citadas consistentemente."
    },
    "documental_evidence": {
      "score": 0.90,
      "reasoning": "Cita numero do inquerito (INQ 5432/2026-STF), valores especificos e nome da operacao."
    },
    "emotional_language": {
      "score": 0.15,
      "reasoning": "Texto predominantemente factual com linguagem neutra. Minimo de adjetivos de valor."
    }
  },

  "severity": {
    "level": "high",
    "reasoning": "Indiciamento pela PF com inquerito formalizado, mas ainda sem denuncia aceita pelo judiciario."
  },

  "politicians": [
    {
      "name": "Jose da Silva",
      "role_in_article": "subject",
      "current_role": "Deputado Federal",
      "party": "PT",
      "state": "SP",
      "context": "Indiciado pela PF por desvio de R$ 12 milhoes em emendas parlamentares entre 2022 e 2025."
    },
    {
      "name": "Maria Oliveira",
      "role_in_article": "mentioned",
      "current_role": "Senadora",
      "party": "MDB",
      "state": "SP",
      "context": "Citada como relatora da CPI que investiga desvio de emendas."
    }
  ],

  "entities": [
    {
      "name": "Construtora ABC",
      "entity_type": "company",
      "role_in_article": "Empresa que recebeu os recursos desviados das emendas parlamentares."
    },
    {
      "name": "Policia Federal",
      "entity_type": "government_body",
      "role_in_article": "Orgao que conduziu o inquerito e realizou o indiciamento."
    }
  ],

  "relationships": [
    {
      "source_name": "Jose da Silva",
      "source_type": "politician",
      "target_name": "Construtora ABC",
      "target_type": "entity",
      "relationship_type": "financial",
      "description": "Emendas parlamentares de Jose da Silva foram direcionadas a Construtora ABC, empresa ligada a familiares."
    }
  ],

  "milestones": [
    {
      "title": "Indiciamento pela PF por desvio de emendas",
      "milestone_type": "inquiry",
      "occurred_at": "2026-08-14",
      "description": "PF indiciou Jose da Silva no inquerito INQ 5432/2026-STF por desvio de R$ 12 milhoes em emendas parlamentares.",
      "politician_name": "Jose da Silva"
    }
  ],

  "keywords": ["emendas parlamentares", "desvio", "policia federal", "indiciamento", "construtora", "PT", "Sao Paulo"],

  "extraction_confidence": {
    "politicians_confidence": 0.95,
    "entities_confidence": 0.85,
    "milestones_confidence": 0.90,
    "overall_confidence": 0.90
  }
}
```

---

## Apendice B: Tabela de Reputacao de Fontes (seed)

| Fonte | Dominio | Reputacao | Categoria |
|-------|---------|-----------|-----------|
| G1 | g1.globo.com | 0.85 | portal |
| Folha de S.Paulo | folha.uol.com.br | 0.90 | jornal |
| Estadao | estadao.com.br | 0.88 | jornal |
| UOL | uol.com.br | 0.75 | portal |
| CNN Brasil | cnnbrasil.com.br | 0.80 | tv |
| Band | band.uol.com.br | 0.75 | tv |
| Agencia Brasil | agenciabrasil.ebc.com.br | 0.85 | agencia |
| Poder360 | poder360.com.br | 0.82 | portal |
| Metropoles | metropoles.com | 0.78 | portal |
| Congresso em Foco | congressoemfoco.uol.com.br | 0.80 | portal |
| The Intercept Brasil | theintercept.com/brasil | 0.70 | investigativo |
| Revista Forum | revistaforum.com.br | 0.45 | blog-opinion |
| Brasil 247 | brasil247.com | 0.35 | blog-opinion |
| Jovem Pan News | jovempan.com.br | 0.55 | tv-opinion |
| Terça Livre | — | 0.20 | blog-partisan |

**Criterios de reputacao:**
- 0.80-1.00: Veiculo com equipe editorial, fact-checking interno, historico de correcoes publicas
- 0.60-0.79: Veiculo estabelecido com mix de noticias e opiniao
- 0.40-0.59: Veiculo com viés editorial forte mas com base factual
- 0.20-0.39: Blog/portal com forte viés partidario e historico de desinformacao
- 0.00-0.19: Fonte conhecida por desinformacao sistematica

---

## Apendice C: Migracoes SQL Necessarias

```sql
-- Migracao 001: Campos adicionais para politicians
ALTER TABLE politicians ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE politicians ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE politicians ADD COLUMN IF NOT EXISTS ai_summary_at TIMESTAMPTZ;

-- Migracao 002: Unique constraint para relationships
ALTER TABLE relationships
ADD CONSTRAINT uq_relationship_pair
UNIQUE (source_type, source_id, target_type, target_id, relationship_type);

-- Migracao 003: Unique constraint para entities
ALTER TABLE entities
ADD CONSTRAINT uq_entity_name_type UNIQUE (name, entity_type);

-- Migracao 004: Unique index para articles URL
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_url ON articles(original_url);

-- Migracao 005: Extensao pg_trgm
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Migracao 006: Indices fuzzy
CREATE INDEX IF NOT EXISTS idx_politicians_name_trgm ON politicians USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm ON entities USING gin(name gin_trgm_ops);

-- Migracao 007: Indice para processamento pendente
CREATE INDEX IF NOT EXISTS idx_articles_pending ON articles(created_at ASC) WHERE ai_processed = false;

-- Migracao 008: Keywords array
ALTER TABLE articles ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_articles_keywords ON articles USING gin(keywords);
```
