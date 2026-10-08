# Research: Help Core Platform

## R1: Formato dos Arquivos .txt do Help Bradesco

**Decision**: Parser com regex para header padrao (10 campos fixos) + separacao por `===== CONTEUDO =====`.

**Rationale**: Analise de amostra real confirmou formato consistente:
```
HELP: <titulo_help>
AREA: <area_operacional>
LISTA: <lista/subcategoria>
TITULO: <titulo>
SUBTITULO: <subtitulo>
NIVEL3: <nivel3>
GROUPSTRING: <groupstring>
LIST_URL: <url_sharepoint>
IID: <id_numerico>
MODIFIED: <dd/MM/yyyy HH:mm>
CLASSIFICACAO: <TEXTUAL|LINK_ONLY|SHORT_TEXT>

===== LINKS =====
<links separados por newline>

===== CONTEUDO =====
<conteudo do artigo>
```

- Encoding: UTF-8 com BOM (byte `\xef\xbb\xbf`) em alguns arquivos
- Estrutura de diretorios: `conteudos/<AREA>/<SUBCATEGORIA>/<arquivo>.txt`
- 26 areas operacionais, cada uma com subdiretorios por lista/subcategoria

**Alternatives considered**: JSON intermediario (rejeitado — os .txt sao a fonte canonica), CSV export (rejeitado — perde formatacao do conteudo).

## R2: Autenticacao — Middleware vs NextAuth

**Decision**: Middleware nativo do Next.js com cookie httpOnly + token fixo.

**Rationale**: NextAuth adiciona ~15 arquivos de boilerplate para uma necessidade trivial (1 senha fixa). O middleware nativo resolve em ~30 linhas:
- `POST /api/auth/login`: valida senha contra `HELPCORE_AUTH_PASSWORD` env var, seta cookie `hc_session` com token HMAC
- `middleware.ts`: verifica cookie em toda rota exceto `/login` e `/api/auth/*`
- Cookie: `httpOnly=true, Secure=true, SameSite=Strict, maxAge=7d`

**Alternatives considered**: NextAuth Credentials (rejeitado — overengineering), Basic Auth HTTP (rejeitado — UX ruim, sem logout).

## R3: Busca Full-Text — ts_vector vs pg_trgm

**Decision**: `ts_vector` com config `portuguese` + GIN index no MVP. `pg_trgm` como complemento futuro para autocomplete.

**Rationale**:
- `ts_vector('portuguese', ...)` faz stemming (procedimento → procediment) e stop words
- GIN index suporta 108K documentos com busca <100ms
- `pg_trgm` e melhor para fuzzy/typo tolerance mas nao e necessario no MVP
- Index: `CREATE INDEX idx_articles_fts ON help_core.articles USING GIN (to_tsvector('portuguese', COALESCE(title,'') || ' ' || COALESCE(content,'')))`

**Alternatives considered**: Elasticsearch (rejeitado — infra adicional desnecessaria para 108K docs), LIKE/ILIKE (rejeitado — O(n) sem index).

## R4: Charts — Recharts vs Chart.js

**Decision**: Recharts.

**Rationale**: React-native (componentes declarativos), sem refs/canvas, `ResponsiveContainer` built-in. Suporta radar, donut, barras empilhadas, treemap. Chart.js requer refs manuais e luta contra o DOM virtual do React.

## R5: Diff Visual — Lib

**Decision**: `react-diff-viewer-continued` (fork mantido do react-diff-viewer).

**Rationale**: Fork ativo (ultimo commit 2024), compativel com React 18+. Suporta side-by-side e inline, syntax highlighting, word-level diff. O `react-diff-viewer` original esta abandonado (2022).

## R6: Prisma multiSchema

**Decision**: Prisma com `previewFeatures = ["multiSchema"]` e `schemas = ["help_core"]`.

**Rationale**: O banco `processing_engine` ja existe com schemas separados. Prisma suporta multiSchema via preview feature. A plataforma precisa ler de `help_core` (articles, analysis_results) e `processing_engine` (jobs, items para metricas de progresso).

**Nota**: `DATABASE_URL` aponta para o database `processing_engine` (que contem ambos os schemas). Prisma introspect mapeia as tabelas de ambos.

## R7: Dashboard — Queries Live vs Materialized Views

**Decision**: Queries live no MVP. MVs na Fase 2 se necessario.

**Rationale**:
- 108K rows com indices corretos responde em <100ms
- Queries de contagem com GROUP BY em colunas indexadas sao rapidas
- MVs adicionam complexidade (refresh scheduling, stale data, UNIQUE INDEX gotchas)
- Se performance degradar com dados processados, adicionar MVs com `REFRESH CONCURRENTLY` via pg_cron

## R8: ETL — Estrategia de Ingestao

**Decision**: Script Python standalone com asyncpg, batch de 500, upsert por content_hash.

**Rationale**:
- Script one-shot (roda 1-3 vezes, nao e daemon)
- asyncpg para inserts em batch (500 por transacao)
- tqdm para barra de progresso no terminal
- content_hash (SHA-256 do conteudo) para dedup
- source_url formato `bradesco-help://<AREA>/<IID>`
- Encoding detection: tentar UTF-8, fallback latin-1, fallback cp1252

## Prior Knowledge from Cortex

- **Gotcha node:20-alpine**: NAO tem wget — se o healthcheck usar wget, adicionar `RUN apk add --no-cache wget` no Dockerfile (ou usar `node -e "..."`)
- **Gotcha PostgreSQL user**: O usuario correto e `postgres`, nao `votolimpo`
- **Pattern docker-swarm-deployment**: Dockerfile Alpine-based, Traefik labels, deploy via Portainer API
- **Decision processing-engine-standalone**: PE usa SKIP LOCKED, typing.Protocol — a plataforma apenas le resultados, nao interage com o worker
