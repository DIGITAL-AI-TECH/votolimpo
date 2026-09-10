# Spec 008: News Collector Frontend

**Status:** Draft
**Priority:** MEDIUM
**Branch:** `feature/008-frontend`

## Objetivo

Implementar o frontend do News Collector para visualização e gerenciamento de artigos coletados, pipelines e status do Processing Engine.

## Acceptance Checklist

- A1. Dashboard com métricas resumidas (artigos coletados hoje, processados, pendentes, erros)
- A2. Lista de artigos com filtros (data, fonte, status, pipeline)
- A3. Detalhe de artigo com output do LLM, post-processors e scores
- A4. Lista de pipelines com status e configuração
- A5. Lista de jobs do PE com status e progresso
- A6. Página de sources (fontes RSS) com reputation score
- A7. Design responsivo, tema escuro
- A8. Autenticação básica (API key ou session)

## IN-SCOPE

### 1. Stack

- **Framework:** React 18 + Vite (já existe base no NC — `news-collector/ui/`)
- **Styling:** Tailwind CSS
- **HTTP Client:** fetch nativo (NC API + PE API)
- **State:** React Query (TanStack Query) para caching e refetch

### 2. Páginas

#### Dashboard (A1)
- Cards: artigos hoje, processados, pendentes, erros
- Gráfico: artigos por dia (últimos 30 dias)
- Timeline: últimas atividades

#### Artigos (A2, A3)
- Tabela paginada com filtros
- Detalhe expandível com JSON viewer para LLM output
- Status badges (raw, processing, completed, failed)

#### Pipelines (A4)
- Lista de pipelines registrados
- Config viewer (YAML renderizado)
- Post-processors chain visualization

#### Jobs (A5)
- Lista de jobs com status em tempo real
- Progresso por item
- Retry button para jobs falhados

#### Sources (A6)
- Lista de fontes RSS/sites
- Reputation score com progress bar
- Último artigo coletado
- Botão para forçar coleta

### 3. APIs Consumidas

**NC API** (`/api/v1/`):
- `GET /articles` — lista artigos
- `GET /articles/:id` — detalhe
- `GET /sources` — lista fontes
- `GET /stats` — métricas

**PE API** (`/v1/`):
- `GET /jobs` — lista jobs
- `GET /jobs/:id` — status do job
- `GET /pipelines` — lista pipelines
- `GET /stats` — métricas PE

### 4. Auth (A8)

Autenticação via header `x-api-key` nas chamadas à API. Token armazenado em localStorage após login simples.

## OUT-OF-SCOPE

- CRUD de pipelines via UI (read-only)
- CRUD de sources via UI (exceto trigger manual de coleta)
- Real-time WebSocket updates
- i18n
- PWA

## REMOVIDOS

Nenhum.

## Arquivos Afetados (Whitelist)

| Diretório | Mudança |
|-----------|---------|
| `news-collector/ui/src/` | Toda a implementação do frontend |
| `news-collector/ui/package.json` | Dependências |
| `news-collector/ui/vite.config.ts` | Configuração Vite |
| `news-collector/ui/tailwind.config.ts` | Configuração Tailwind |
