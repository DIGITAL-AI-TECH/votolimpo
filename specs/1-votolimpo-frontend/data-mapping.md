# Voto Limpo - Mapeamento Tela-a-Tela de Dados

**Created**: 2026-09-05
**Purpose**: Mapear TODOS os campos consumidos por cada tela/componente da UI,
identificar campos derivados, gaps no schema e prioridade de processamento.

---

## Legenda

- **DB**: campo existe diretamente no banco (tabela.coluna)
- **VIEW**: campo vem de uma view pre-calculada
- **DERIVADO**: campo calculado a partir de outros campos (formula descrita)
- **GAP**: campo necessario na UI que NAO existe no schema atual
- **PROC**: extraido durante processamento de artigo (GPT-4.1-mini)
- **CRON**: calculado em batch/cron (nao no processamento individual)
- **API**: calculado no momento da requisicao (query-time)

---

## TELA 1 - HOME

### 1.1 Hero + Autocomplete de Busca

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Autocomplete | nome | DB | `politicians.name` | Busca full-text, retorna apos 2 chars |
| Autocomplete | slug | DB | `politicians.slug` | Para navegar ao perfil |
| Autocomplete | partido (sigla) | DB | `parties.abbreviation` | Exibido ao lado do nome |
| Autocomplete | estado | DB | `politicians.state` | Exibido ao lado do partido |
| Autocomplete | cargo | DB | `politicians.role` | Exibido no resultado |
| Autocomplete | foto_url | DB | `politicians.photo_url` | Thumbnail no autocomplete |

**Indice necessario**: full-text index em `politicians.name` (pg_trgm ou tsvector).

### 1.2 Contadores Animados

| Componente | Campo UI | Fonte | Tabela.Coluna | Formula/Notas |
|------------|----------|-------|---------------|---------------|
| Contador | total_politicos | DERIVADO/CRON | `COUNT(*) FROM politicians` | Atualizado diariamente |
| Contador | total_noticias | DERIVADO/CRON | `COUNT(*) FROM articles` | Atualizado diariamente |
| Contador | total_condenacoes | DERIVADO/CRON | `COUNT(*) FROM milestones WHERE milestone_type = 'conviction'` | **Presente no mockup** |
| Contador | total_fontes | DERIVADO/CRON | `COUNT(*) FROM sources WHERE active = true` | Atualizado diariamente |

**GAP IDENTIFICADO**: O mockup exibe "condenacoes" como contador. O schema suporta via `milestones` mas NAO ha campo denormalizado para isso. Opcoes:
- Query-time: `COUNT(*) FROM milestones WHERE milestone_type = 'conviction'` (aceitavel, tabela pequena)
- Tabela `global_stats` (ver GAPs abaixo)

### 1.3 Ranking Top 10

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Card ranking | posicao | VIEW | `v_politician_ranking.position` | RANK() OVER |
| Card ranking | foto_url | DB | `politicians.photo_url` | |
| Card ranking | nome | DB | `politicians.name` | |
| Card ranking | partido (sigla) | DB | `parties.abbreviation` | |
| Card ranking | partido_cor | DB | `parties.color` | Cor do badge do partido |
| Card ranking | estado | DB | `politicians.state` | |
| Card ranking | cargo | DB | `politicians.role` | |
| Card ranking | score | DB | `politicians.score` | 0-100 |
| Card ranking | total_noticias | DB | `politicians.total_news` | Denormalizado |
| Card ranking | severidade_max | DB | `politicians.severity_max` | Badge de cor (low/med/high/critical) |
| Card ranking | slug | DB | `politicians.slug` | Link para perfil |

**Query**: `SELECT * FROM v_politician_ranking LIMIT 10`

### 1.4 Casos Recentes

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Card caso | titulo | DB | `articles.title` | |
| Card caso | severidade (badge) | DB | `articles.severity` | Badge colorido |
| Card caso | politicos_envolvidos[] | DB | `politician_articles` JOIN `politicians` | Lista de {nome, slug, partido} |
| Card caso | resumo | DB | `articles.summary` | Gerado por IA |
| Card caso | data | DB | `articles.published_at` | |
| Card caso | num_noticias_cluster | DERIVADO/API | `article_matches` | **Contagem de artigos no cluster** |
| Card caso | fonte | DB | `sources.name` | |

**GAP IDENTIFICADO**: O conceito de "caso" (cluster de noticias) nao tem entidade propria no schema. Atualmente, `article_matches` registra pares de artigos similares, mas nao ha:
- Tabela `clusters` com titulo consolidado do caso
- Campo `cluster_id` nos artigos para agrupar
- "Titulo do caso" consolidado (diferente do titulo individual de cada artigo)

**Workaround atual**: Usar o artigo mais recente/relevante de cada cluster como representante. O "numero de noticias relacionadas" vem de `COUNT(*) FROM article_matches WHERE article_a_id = X OR article_b_id = X`.

### 1.5 Stats Globais (Footer/Section)

Mesmo que contadores animados (1.2).

---

## TELA 2 - PERFIL DO POLITICO

### 2.1 Header do Perfil

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Header | foto_url | DB | `politicians.photo_url` | Grande, circular |
| Header | nome | DB | `politicians.name` | |
| Header | partido (sigla) | DB | `parties.abbreviation` | Badge com cor |
| Header | partido_cor | DB | `parties.color` | |
| Header | partido_logo | DB | `parties.logo_url` | |
| Header | estado | DB | `politicians.state` | |
| Header | cargo | DB | `politicians.role` | |
| Header | score | DB | `politicians.score` | Ring SVG 0-100 |
| Header | total_noticias | DB | `politicians.total_news` | |
| Header | bio | **GAP** | -- | **NAO EXISTE NO SCHEMA** |
| Header | resumo_ia | **GAP** | -- | **NAO EXISTE NO SCHEMA** |
| Header | slug | DB | `politicians.slug` | URL e compartilhamento |

**GAPS CRITICOS**:
- `bio`: Biografia curta do politico (ex: "Deputado Federal por SP desde 2018, membro da CPI X"). Fonte: TSE ou Wikipedia. Precisa de campo `politicians.bio TEXT`.
- `resumo_ia`: Resumo gerado por IA do historico do politico (ex: "Jose da Silva acumula 47 noticias negativas..."). Precisa de campo `politicians.ai_summary TEXT`. Gerado/atualizado por CRON apos cada batch de processamento.

### 2.2 Estatisticas do Perfil

| Componente | Campo UI | Fonte | Tabela.Coluna | Formula |
|------------|----------|-------|---------------|---------|
| Stat | total_noticias | DB | `politicians.total_news` | Denormalizado |
| Stat | dist_severidade | DERIVADO/API | `articles` via `politician_articles` | `GROUP BY severity` |
| Stat | fontes_frequentes | DERIVADO/API | `sources` via `articles` + `politician_articles` | `GROUP BY source_id ORDER BY COUNT(*) DESC LIMIT 5` |
| Stat | periodo_primeira | DB | `politicians.first_news_at` | |
| Stat | periodo_ultima | DB | `politicians.last_news_at` | |
| Stat | total_critical | DERIVADO/API | -- | `COUNT(*) WHERE severity = 'critical'` para este politico |

### 2.3 Tab Timeline - Noticias

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Timeline item | titulo | VIEW | `v_politician_timeline.title` | |
| Timeline item | resumo | VIEW | `v_politician_timeline.summary` | IA-generated |
| Timeline item | data | VIEW | `v_politician_timeline.published_at` | Dot colorido na linha |
| Timeline item | severidade | VIEW | `v_politician_timeline.severity` | Cor do dot e badge |
| Timeline item | veracidade_score | VIEW | `v_politician_timeline.veracity_score` | 0.0-1.0 |
| Timeline item | veracidade_label | DERIVADO/API | -- | Calculado do score (ver mapeamento abaixo) |
| Timeline item | veracidade_cor | DERIVADO/API | -- | Calculado do score |
| Timeline item | original_url | VIEW | `v_politician_timeline.original_url` | "Ler noticia completa" |
| Timeline item | fonte_nome | VIEW | `v_politician_timeline.source_name` | Clicavel |
| Timeline item | fonte_domain | VIEW | `v_politician_timeline.source_domain` | Link para fonte |
| Timeline item | noticias_relacionadas_count | DERIVADO/API | `article_matches` | `COUNT(*)` matches para este artigo |
| Timeline item | noticias_relacionadas[] | DERIVADO/API (lazy) | `article_matches` JOIN `articles` | Carregado sob demanda ao expandir |
| Timeline item | item_type | VIEW | `v_politician_timeline.item_type` | 'article' ou 'milestone' |

**Mapeamento veracidade_score -> label/cor**:

| Range | Label | Cor |
|-------|-------|-----|
| 0.8 - 1.0 | "Muito confiavel" | Verde #10B981 |
| 0.6 - 0.8 | "Confiavel" | Azul #3B82F6 |
| 0.4 - 0.6 | "Verificar fontes" | Amarelo #F59E0B |
| 0.2 - 0.4 | "Baixa confiabilidade" | Laranja #F97316 |
| 0.0 - 0.2 | "Possivel desinformacao" | Vermelho #EF4444 |

### 2.4 Tab Timeline - Milestones

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Milestone | titulo | DB | `milestones.title` | Ex: "Abertura de Inquerito" |
| Milestone | descricao | DB | `milestones.description` | |
| Milestone | tipo | DB | `milestones.milestone_type` | inquiry/complaint/conviction/etc |
| Milestone | data | DB | `milestones.occurred_at` | |
| Milestone | source_url | DB | `milestones.source_url` | Link para fonte |
| Milestone | icone | DERIVADO/API | -- | Mapeado pelo `milestone_type` (ver tabela no schema) |
| Milestone | cor | DERIVADO/API | -- | Mapeado pelo `milestone_type` |
| Milestone | artigo_associado | DB | `milestones.article_id` | Opcional |

Milestones e artigos aparecem intercalados na timeline via `v_politician_timeline` (UNION ALL), ordenados por data.

### 2.5 Tab Noticias (Listagem Compacta)

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| Lista | titulo | DB | `articles.title` | |
| Lista | data | DB | `articles.published_at` | |
| Lista | severidade | DB | `articles.severity` | Filtro |
| Lista | veracidade_score | DB | `articles.veracity_score` | |
| Lista | fonte_nome | DB | `sources.name` | |
| Lista | original_url | DB | `articles.original_url` | |
| Filtros | severidade[] | ENUM | low/medium/high/critical | Checkboxes |
| Ordenacao | campo | API | published_at, severity, veracity_score | Dropdown |

### 2.6 Tab Grafo Mini

| Componente | Campo UI | Fonte | Tabela.Coluna | Notas |
|------------|----------|-------|---------------|-------|
| No central | nome | DB | `politicians.name` | Politico do perfil |
| No central | foto_url | DB | `politicians.photo_url` | |
| No central | score | DB | `politicians.score` | Tamanho do no |
| Nos conectados | nome | DB/VIEW | `v_graph_nodes.name` | |
| Nos conectados | tipo | DB/VIEW | `v_graph_nodes.node_type` | politician/party/company/organization |
| Nos conectados | score | DB/VIEW | `v_graph_nodes.score` | |
| Nos conectados | slug | DB/VIEW | `v_graph_nodes.slug` | Para navegar (so politicos) |
| Nos conectados | foto_url | DB/VIEW | `v_graph_nodes.photo_url` | |
| Arestas | peso | DB | `relationships.weight` | Espessura da aresta |
| Arestas | tipo_relacao | DB | `relationships.relationship_type` | business/political/family/legal/financial |
| Arestas | descricao | DB | `relationships.description` | Tooltip da aresta |

**Query**: Filtrar `relationships` WHERE `source_id = :politician_id` OR `target_id = :politician_id`, JOIN com `v_graph_nodes`.

### 2.7 Compartilhamento / Open Graph

| Campo OG | Fonte | Formula |
|----------|-------|---------|
| og:title | DB | `"{nome} - Voto Limpo"` |
| og:description | DERIVADO | `"{nome} ({partido}-{estado}): score {score}/100, {total_news} noticias"` |
| og:image | DB | `politicians.photo_url` |
| og:url | DB | `"https://votolimpo.com.br/politico/{slug}"` |

---

## TELA 3 - BUSCA

### 3.1 Input de Busca

| Campo | Fonte | Notas |
|-------|-------|-------|
| query (nome) | USER INPUT | Full-text search em `politicians.name` |

### 3.2 Filtros

| Filtro | Fonte | Tabela.Coluna | Notas |
|--------|-------|---------------|-------|
| Partidos (multi-select) | DB | `parties.abbreviation` + `parties.id` | Lista de todos os partidos |
| Estados (dropdown) | ENUM | 27 UFs | Hardcoded ou `DISTINCT politicians.state` |
| Cargos (dropdown) | DB | `DISTINCT politicians.role` | |
| Severidade minima | ENUM | low/medium/high/critical | Filtra `politicians.severity_max` |

### 3.3 Ordenacao

| Opcao | Query | Notas |
|-------|-------|-------|
| Maior score | `ORDER BY score DESC` | Default |
| Mais noticias | `ORDER BY total_news DESC` | |
| Mais recente | `ORDER BY last_news_at DESC` | |
| Nome A-Z | `ORDER BY name ASC` | |

### 3.4 Cards de Resultado

| Campo UI | Fonte | Tabela.Coluna |
|----------|-------|---------------|
| foto_url | DB | `politicians.photo_url` |
| nome | DB | `politicians.name` |
| partido (sigla) | DB | `parties.abbreviation` |
| partido_cor | DB | `parties.color` |
| cargo | DB | `politicians.role` |
| estado | DB | `politicians.state` |
| score | DB | `politicians.score` |
| total_noticias | DB | `politicians.total_news` |
| severidade_max (badge) | DB | `politicians.severity_max` |
| slug | DB | `politicians.slug` |

### 3.5 Paginacao

| Campo | Fonte | Notas |
|-------|-------|-------|
| total_resultados | API | `COUNT(*)` com filtros aplicados |
| pagina_atual | USER INPUT | Query param |
| items_por_pagina | CONFIG | 20 (desktop) ou scroll infinito (mobile) |

---

## TELA 4 - GRAFO GLOBAL

### 4.1 Nos (Vertices)

| Campo UI | Fonte | Tabela.Coluna | Notas |
|----------|-------|---------------|-------|
| id | VIEW | `v_graph_nodes.id` | |
| nome | VIEW | `v_graph_nodes.name` | Label do no |
| tipo | VIEW | `v_graph_nodes.node_type` | politician/party/company/organization |
| score | VIEW | `v_graph_nodes.score` | Tamanho do no |
| estado | VIEW | `v_graph_nodes.state` | Tooltip (so politicos) |
| slug | VIEW | `v_graph_nodes.slug` | Link (so politicos) |
| foto_url | VIEW | `v_graph_nodes.photo_url` | Dentro do no |
| cor | DERIVADO/API | -- | Mapeado pelo `node_type` |

**Mapeamento tipo -> cor**:

| node_type | Cor | Label |
|-----------|-----|-------|
| politician | #10B981 (verde) | Politico |
| party | #3B82F6 (azul) | Partido |
| company | #94A3B8 (cinza) | Empresa |
| organization | #F59E0B (amarelo) | Organizacao |

### 4.2 Arestas

| Campo UI | Fonte | Tabela.Coluna | Notas |
|----------|-------|---------------|-------|
| source_type | DB | `relationships.source_type` | |
| source_id | DB | `relationships.source_id` | |
| target_type | DB | `relationships.target_type` | |
| target_id | DB | `relationships.target_id` | |
| peso | DB | `relationships.weight` | Espessura |
| tipo_relacao | DB | `relationships.relationship_type` | Cor/estilo da aresta |
| descricao | DB | `relationships.description` | Tooltip |

### 4.3 Filtros

| Filtro | Tipo | Notas |
|--------|------|-------|
| Checkboxes tipo de no | UI-only | Filtra nos por `node_type` |
| Busca de politico | API | Centraliza grafo no no encontrado |

### 4.4 Painel Lateral (ao clicar num no)

| Campo UI | Fonte | Tabela.Coluna | Notas |
|----------|-------|---------------|-------|
| nome | VIEW | `v_graph_nodes.name` | |
| tipo | VIEW | `v_graph_nodes.node_type` | |
| score | VIEW | `v_graph_nodes.score` | |
| descricao | DB | `entities.description` ou bio do politico | **GAP: bio do politico** |
| conexoes[] | DB | `relationships` filtrado | Lista de {nome, tipo, peso} |
| artigos_evidencia[] | DB | `relationship_evidence` JOIN `articles` | Noticias que fundamentam conexoes |
| link_perfil | DB | `politicians.slug` / `entities.id` | "Ver perfil" (so politicos) |

**GAP**: `entities.description` existe mas pode estar vazio. O processamento precisa extrair descricoes uteis das entidades.

### 4.5 Limite de Performance

| Parametro | Valor | Notas |
|-----------|-------|-------|
| max_nos | 200 | Limitar query a 200 nos por vez |
| paginacao_grafo | cursor-based | Carregar mais nos conforme zoom/pan |

---

## TELA 5 - RANKING

### 5.1 Top 3 com Badges

| Campo UI | Fonte | Tabela.Coluna | Notas |
|----------|-------|---------------|-------|
| posicao | VIEW | `v_politician_ranking.position` | 1=ouro, 2=prata, 3=bronze |
| foto_url | DB | `politicians.photo_url` | Grande |
| nome | DB | `politicians.name` | |
| partido (sigla) | DB | `parties.abbreviation` | |
| partido_cor | DB | `parties.color` | |
| score | DB | `politicians.score` | |
| total_noticias | DB | `politicians.total_news` | |
| badge | DERIVADO/API | -- | ouro/prata/bronze pela posicao |

### 5.2 Tabela Ordenavel

| Coluna | Fonte | Tabela.Coluna | Ordenavel |
|--------|-------|---------------|-----------|
| Posicao | VIEW | `v_politician_ranking.position` | Sim (default) |
| Foto | DB | `politicians.photo_url` | Nao |
| Nome | DB | `politicians.name` | Sim |
| Partido | DB | `parties.abbreviation` | Sim |
| Estado | DB | `politicians.state` | Sim |
| Cargo | DB | `politicians.role` | Sim |
| Score | DB | `politicians.score` | Sim |
| N. Noticias | DB | `politicians.total_news` | Sim |
| Severidade | DB | `politicians.severity_max` | Sim |
| Acao | DB | `politicians.slug` | -- (link "Ver perfil") |

### 5.3 Filtros

| Filtro | Fonte | Notas |
|--------|-------|-------|
| Partido | DB | `parties.abbreviation` |
| Estado | ENUM/DB | 27 UFs |
| Cargo | DB | `DISTINCT politicians.role` |

### 5.4 Paginacao

| Campo | Notas |
|-------|-------|
| total_resultados | COUNT com filtros |
| pagina_atual | Query param |
| items_por_pagina | 25 |

---

## CAMPOS DERIVADOS - Formulas Completas

| Campo | Formula | Quando Calcular |
|-------|---------|-----------------|
| `politicians.score` | Media ponderada: `AVG(a.severity_numeric * a.veracity_score) * weight_by_recency` | **CRON** diario |
| `politicians.total_news` | `COUNT(*) FROM politician_articles WHERE politician_id = X` | **CRON** diario |
| `politicians.severity_max` | `MAX(a.severity) FROM articles a JOIN politician_articles pa ON ...` | **CRON** diario |
| `politicians.first_news_at` | `MIN(a.published_at) FROM articles a JOIN politician_articles pa ON ...` | **CRON** diario |
| `politicians.last_news_at` | `MAX(a.published_at) FROM articles a JOIN politician_articles pa ON ...` | **CRON** diario |
| `articles.veracity_score` | `0.30*source_rep + 0.25*multi_source + 0.15*narrative + 0.10*documental + 0.10*temporal + 0.10*(1-emotional)` | **PROC** (no processamento do artigo) |
| `relationships.weight` | `COUNT(*) FROM relationship_evidence WHERE relationship_id = X` | **CRON** apos novos artigos |
| Veracidade label | Mapeamento range -> string (ver 2.3) | **API** (frontend ou API response) |
| Severidade cor | Mapeamento enum -> hex (ver schema) | **API** (frontend) |
| Milestone icone/cor | Mapeamento tipo -> icone/cor (ver schema) | **API** (frontend) |
| Node tipo cor (grafo) | Mapeamento tipo -> hex (ver 4.1) | **API** (frontend) |
| Posicao ranking | `RANK() OVER (ORDER BY score DESC)` | **API** (view) |
| Noticias relacionadas count | `COUNT(*) FROM article_matches WHERE article_a_id = X OR article_b_id = X` | **API** (query-time) |
| Contador global politicos | `COUNT(*) FROM politicians` | **CRON** |
| Contador global noticias | `COUNT(*) FROM articles` | **CRON** |
| Contador global condenacoes | `COUNT(*) FROM milestones WHERE milestone_type = 'conviction'` | **CRON** |
| Contador global fontes | `COUNT(*) FROM sources WHERE active = true` | **CRON** |
| OG description | Template string com nome/partido/estado/score/total_news | **API** (SSR) |

---

## GAPS - Campos que o Schema Atual NAO Cobre

### GAP-01: `politicians.bio` (CRITICO)

- **Onde aparece**: Tela 2 (Perfil) - Header
- **O que e**: Biografia curta do politico (1-2 frases)
- **Solucao**: Adicionar `bio TEXT` na tabela `politicians`
- **Fonte de dados**: Importacao TSE (historico de candidaturas) ou Wikipedia scraping
- **Prioridade**: ALTA - aparece no topo do perfil

### GAP-02: `politicians.ai_summary` (CRITICO)

- **Onde aparece**: Tela 2 (Perfil) - Header (resumo_ia)
- **O que e**: Resumo gerado por IA do historico completo do politico (3-5 frases)
- **Solucao**: Adicionar `ai_summary TEXT` + `ai_summary_updated_at TIMESTAMPTZ` na tabela `politicians`
- **Fonte de dados**: Gerado por GPT-4.1-mini a partir de todas as noticias do politico
- **Prioridade**: ALTA - diferencial da plataforma
- **Quando gerar**: CRON apos batch de processamento (nao a cada artigo)

### GAP-03: Conceito de "Cluster/Caso" (MEDIO)

- **Onde aparece**: Tela 1 (Home) - Casos Recentes
- **O que e**: Agrupamento de noticias sobre o mesmo assunto/caso
- **Situacao atual**: `article_matches` registra pares de artigos similares, mas nao ha conceito de "cluster" como entidade
- **Solucao proposta**: NAO criar tabela nova. Usar o artigo com maior `multi_source_count` ou mais recente do grupo como representante. O "N noticias relacionadas" vem de `article_matches`.
- **Alternativa futura**: Se necessario, criar `clusters(id, title, representative_article_id, article_count, severity, created_at)` + `cluster_articles(cluster_id, article_id)`
- **Prioridade**: MEDIA - workaround funcional existe

### GAP-04: `global_stats` (tabela cache) (BAIXO)

- **Onde aparece**: Tela 1 (Home) - Contadores
- **O que e**: Contadores globais pre-calculados
- **Situacao atual**: Requer queries `COUNT(*)` em cada request
- **Solucao**: Criar tabela `global_stats(key TEXT PK, value INT, updated_at TIMESTAMPTZ)` populada por CRON
- **Prioridade**: BAIXA - queries simples com COUNT sao rapidas em tabelas com indice

### GAP-05: `entities.description` (dados) (MEDIO)

- **Onde aparece**: Tela 4 (Grafo) - Painel lateral
- **O que e**: Descricao textual da entidade (empresa, organizacao)
- **Situacao atual**: Campo existe no schema mas provavelmente estara vazio para muitas entidades
- **Solucao**: O processamento de artigos (PROC) deve extrair uma descricao de 1-2 frases para cada entidade nova identificada
- **Prioridade**: MEDIA

### GAP-06: Full-text search index (INFRA)

- **Onde aparece**: Tela 1 (Autocomplete), Tela 3 (Busca)
- **Situacao atual**: Nao ha indice full-text definido
- **Solucao**: `CREATE INDEX idx_politicians_name_trgm ON politicians USING gin (name gin_trgm_ops);` + `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- **Prioridade**: ALTA - busca e funcionalidade central

---

## PRIORIDADE DE PROCESSAMENTO

### O que DEVE ser extraido no processamento de CADA artigo (PROC - real-time)

Estes campos sao extraidos pelo GPT-4.1-mini ao processar cada artigo coletado:

| # | Dado | Destino | Obrigatorio |
|---|------|---------|-------------|
| 1 | summary (resumo 2-3 frases) | `articles.summary` | SIM |
| 2 | severity (low/med/high/critical) | `articles.severity` | SIM |
| 3 | Politicos mencionados (nome -> id) | `politician_articles` | SIM |
| 4 | Role do politico na noticia (subject/mentioned/related) | `politician_articles.role` | SIM |
| 5 | source_reputation (reputacao da fonte) | `articles.source_reputation` | SIM (lookup tabela sources) |
| 6 | narrative_consistency | `articles.narrative_consistency` | SIM |
| 7 | documental_evidence | `articles.documental_evidence` | SIM |
| 8 | emotional_language | `articles.emotional_language` | SIM |
| 9 | veracity_score (calculado dos 6 sinais) | `articles.veracity_score` | SIM |
| 10 | Entidades extraidas (empresas, orgs) | `entities` (upsert) | SIM |
| 11 | Descricao da entidade (1-2 frases) | `entities.description` | SE NOVO |
| 12 | Relacoes entre entidades/politicos | `relationships` (upsert) | SIM |
| 13 | Evidencia da relacao | `relationship_evidence` | SIM |
| 14 | Deteccao de milestone (inquerito, condenacao, etc) | `milestones` | SE DETECTADO |
| 15 | Similaridade com artigos existentes | `article_matches` | SIM (embedding cosine) |

### O que pode ser calculado depois (CRON - batch diario/horario)

| # | Dado | Destino | Frequencia |
|---|------|---------|------------|
| 1 | Score do politico | `politicians.score` | Diario |
| 2 | Total noticias por politico | `politicians.total_news` | Diario |
| 3 | Severidade maxima por politico | `politicians.severity_max` | Diario |
| 4 | Datas primeira/ultima noticia | `politicians.first_news_at/last_news_at` | Diario |
| 5 | Weight das relacoes | `relationships.weight` | Diario |
| 6 | Resumo IA do politico | `politicians.ai_summary` **GAP-02** | Semanal ou apos N novos artigos |
| 7 | Contadores globais | `global_stats` **GAP-04** | Horario |
| 8 | multi_source_count | `articles.multi_source_count` | Apos cada batch (recalcular matches) |
| 9 | temporality_score | `articles.temporality_score` | Diario (decai com o tempo) |

### O que e calculado no frontend/API (API - query-time)

| # | Dado | Calculo |
|---|------|---------|
| 1 | Veracidade label/cor | Map score -> string/hex |
| 2 | Severidade cor | Map enum -> hex |
| 3 | Milestone icone/cor | Map tipo -> icone/hex |
| 4 | Node cor (grafo) | Map tipo -> hex |
| 5 | Posicao ranking | `RANK() OVER` na view |
| 6 | Badge posicao (ouro/prata/bronze) | posicao <= 3 |
| 7 | OG tags | Template string SSR |
| 8 | Noticias relacionadas count | COUNT nos matches (ou denormalizar) |

---

## ACCEPTANCE CRITERIA - O processamento esta completo quando...

### AC-01: Artigo Individual
- [ ] Todo artigo processado tem `summary` NAO-nulo (2-3 frases em PT-BR)
- [ ] Todo artigo processado tem `severity` classificado (low/medium/high/critical)
- [ ] Todo artigo processado tem `veracity_score` calculado (0.0-1.0) com os 6 sinais preenchidos
- [ ] Todo artigo processado tem pelo menos 1 `politician_articles` associado
- [ ] Todo artigo processado tem `original_url` valido e acessivel
- [ ] Todo artigo processado tem `source_id` vinculado a uma fonte existente

### AC-02: Entidades e Relacoes
- [ ] Toda entidade (empresa/org) mencionada em artigo esta registrada em `entities`
- [ ] Toda relacao detectada entre politico-entidade ou politico-politico esta em `relationships`
- [ ] Toda relacao tem pelo menos 1 entrada em `relationship_evidence`
- [ ] Entidades novas tem `description` preenchido (1-2 frases)

### AC-03: Milestones
- [ ] Todo artigo que descreve inquerito/denuncia/condenacao/absolvicao/prisao gera um `milestone`
- [ ] Milestones tem `milestone_type` correto e `occurred_at` preciso

### AC-04: Matches/Clusters
- [ ] Artigos sobre o mesmo caso tem `article_matches` com `similarity >= 0.7`
- [ ] `multi_source_count` reflete o numero real de fontes que cobriram o caso

### AC-05: Campos Denormalizados (CRON)
- [ ] `politicians.score` esta atualizado (diferenca < 24h)
- [ ] `politicians.total_news` bate com `COUNT(*) FROM politician_articles`
- [ ] `politicians.severity_max` bate com o MAX real dos artigos
- [ ] `politicians.first_news_at` e `last_news_at` estao corretos

### AC-06: Campos GAP Resolvidos
- [ ] `politicians.bio` preenchido para todos os politicos catalogados
- [ ] `politicians.ai_summary` gerado para todo politico com >= 3 noticias
- [ ] Full-text index (pg_trgm) ativo em `politicians.name`

### AC-07: Integridade do Grafo
- [ ] Todo no no grafo (`v_graph_nodes`) tem `name` NAO-nulo
- [ ] Todo politico com score > 0 aparece no grafo
- [ ] Toda aresta (`relationships`) tem `weight >= 1`
- [ ] Nenhum no orfao (sem arestas) no grafo, exceto politicos sem conexoes detectadas

### AC-08: Performance
- [ ] Autocomplete retorna em < 200ms para qualquer substring de 2+ chars
- [ ] Ranking top 10 (Home) retorna em < 100ms (view materializada se necessario)
- [ ] Timeline do politico carrega primeiros 20 itens em < 500ms
- [ ] Grafo global (200 nos) carrega em < 1s

---

## RESUMO DE ALTERACOES NO SCHEMA

```sql
-- GAP-01: Bio do politico
ALTER TABLE politicians ADD COLUMN bio TEXT;

-- GAP-02: Resumo IA do politico
ALTER TABLE politicians ADD COLUMN ai_summary TEXT;
ALTER TABLE politicians ADD COLUMN ai_summary_updated_at TIMESTAMPTZ;

-- GAP-06: Full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_politicians_name_trgm ON politicians USING gin (name gin_trgm_ops);

-- GAP-04 (opcional, se performance exigir):
CREATE TABLE global_stats (
  key         TEXT PRIMARY KEY,
  value       BIGINT NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ DEFAULT now()
);
```
