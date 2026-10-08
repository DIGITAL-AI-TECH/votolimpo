# Data Model: Help Core Platform

## Entities

### Article (help_core.articles)
Artigo original do Help Bradesco, inserido pelo ETL.

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| id | SERIAL PK | N | ID auto-increment |
| source_url | TEXT UNIQUE | N | `bradesco-help://<AREA>/<IID>` |
| title | TEXT | N | Titulo do artigo (campo TITULO do .txt) |
| subtitle | TEXT | Y | Subtitulo (campo SUBTITULO) |
| area | TEXT | N | Area operacional (campo AREA, ex: "Alto Valor") |
| lista | TEXT | Y | Lista/subcategoria (campo LISTA) |
| content | TEXT | Y | Conteudo completo do artigo (secao CONTEUDO) |
| content_hash | TEXT | Y | SHA-256 do conteudo para dedup |
| classification | TEXT | Y | TEXTUAL, LINK_ONLY, SHORT_TEXT |
| iid | TEXT | Y | ID interno SharePoint |
| modified_date | TIMESTAMPTZ | Y | Data de modificacao (campo MODIFIED) |
| links | TEXT[] | Y | Links internos extraidos (secao LINKS) |
| help_title | TEXT | Y | Titulo do Help (campo HELP) |
| list_url | TEXT | Y | URL do SharePoint (campo LIST_URL) |
| groupstring | TEXT | Y | GroupString do SharePoint |
| created_at | TIMESTAMPTZ | N | DEFAULT NOW() |

**Indices**:
- `UNIQUE (source_url)` — chave de negocio
- `UNIQUE (content_hash)` WHERE content_hash IS NOT NULL — dedup
- `GIN (to_tsvector('portuguese', COALESCE(title,'') || ' ' || COALESCE(content,'')))` — busca full-text
- `BTREE (area)` — navegacao por area
- `BTREE (classification)` — filtro por tipo

### AnalysisResult (help_core.analysis_results)
Resultado do processamento LLM. Ja existe — criada pela migration 019 do PE.

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| id | SERIAL PK | N | ID auto-increment |
| pe_item_id | UUID UNIQUE | N | ID do item no PE (chave de upsert) |
| article_id | INTEGER FK | Y | FK para articles.id (via source_url match) |
| source_url | TEXT | Y | URL do artigo processado |
| doc_type | TEXT | Y | Tipo de documento (manual, procedimento, faq, etc.) |
| category | TEXT | Y | Categoria principal |
| subcategory | TEXT | Y | Subcategoria |
| target_audience | TEXT | Y | Publico-alvo |
| inv_quality_score | NUMERIC | Y | Score de qualidade inventario |
| completeness_score | NUMERIC | Y | Score de completude |
| key_topics | JSONB | Y | Topicos-chave (array) |
| summary | TEXT | Y | Resumo |
| requires_update | BOOLEAN | Y | Precisa de atualizacao? |
| has_mandatory_fields | BOOLEAN | Y | Tem campos obrigatorios? |
| missing_mandatory_fields | JSONB | Y | Campos obrigatorios faltantes |
| mentions_systems | JSONB | Y | Sistemas mencionados |
| escalation_present | BOOLEAN | Y | Tem escalacao? |
| has_internal_conflicts | BOOLEAN | Y | Tem conflitos internos? |
| internal_conflict_details | TEXT | Y | Detalhes do conflito |
| area_operacional | TEXT | Y | Area operacional identificada pelo LLM |
| confidence | NUMERIC | Y | Confianca da classificacao (0-1) |
| clarity | NUMERIC | Y | Score clareza (0-100) |
| structure | NUMERIC | Y | Score estrutura (0-100) |
| readability | NUMERIC | Y | Score legibilidade (0-100) |
| completeness | NUMERIC | Y | Score completude qualidade (0-100) |
| accuracy_signals | NUMERIC | Y | Score sinais de precisao (0-100) |
| overall_score | NUMERIC | Y | Score geral ponderado (0-100) |
| priority_level | TEXT | Y | critical, high, medium, low |
| estimated_effort | TEXT | Y | minor, moderate, major |
| improvement_suggestions | JSONB | Y | Sugestoes de melhoria (array) |
| language_issues | JSONB | Y | Problemas de linguagem (array) |
| steps | JSONB | Y | Passos extraidos (array de objetos) |
| markdown_content | TEXT | Y | Conteudo em markdown processado |
| prompt_version | TEXT | Y | Versao do prompt |
| processed_at | TIMESTAMPTZ | Y | Data de processamento |

### ReviewAction (help_core.review_actions) — NOVA
Historico de acoes de revisao humana.

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| id | SERIAL PK | N | ID auto-increment |
| analysis_result_id | INTEGER FK | N | FK para analysis_results.id |
| action | TEXT | N | 'approved', 'rejected', 'revision_requested' |
| notes | TEXT | Y | Notas do revisor (obrigatorio em reject/revision) |
| created_at | TIMESTAMPTZ | N | DEFAULT NOW() |

**CHECK**: `action IN ('approved', 'rejected', 'revision_requested')`
**CHECK**: `(action = 'approved') OR (notes IS NOT NULL AND notes != '')`

### ArticleRelationship (help_core.article_relationships) — Ja existe
Relacionamentos entre artigos (duplicatas, referencias).

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| id | SERIAL PK | N | |
| source_article_id | INTEGER FK | N | FK articles.id |
| target_article_id | INTEGER FK | N | FK articles.id |
| relationship_type | TEXT | N | 'duplicate', 'reference', 'related' |
| similarity_score | NUMERIC | Y | Score de similaridade (0-1) |
| created_at | TIMESTAMPTZ | N | DEFAULT NOW() |

## Relationships

```
Article 1 ←──── N AnalysisResult (via source_url match ou article_id FK)
AnalysisResult 1 ←──── N ReviewAction (via analysis_result_id FK)
Article N ←──── N Article (via ArticleRelationship, bidirecional)
```

## State Transitions

### Article Processing Status
Derivado da existencia de AnalysisResult:
- **Nao processado**: Nenhum AnalysisResult com source_url correspondente
- **Processado**: AnalysisResult existe com overall_score preenchido

### Review Status
Derivado da ultima ReviewAction:
- **Pendente**: Nenhuma ReviewAction, ou ultima = 'revision_requested'
- **Aprovado**: Ultima ReviewAction.action = 'approved'
- **Rejeitado**: Ultima ReviewAction.action = 'rejected'
