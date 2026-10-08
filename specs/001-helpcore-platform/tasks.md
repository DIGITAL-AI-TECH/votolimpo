# Tasks: Help Core Platform

**Input**: Design documents from `/specs/001-helpcore-platform/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-routes.md

**Tests**: Incluidos conforme constitution (diff coverage 100%). Vitest para frontend, pytest para ETL.

**Organization**: Tasks agrupadas por user story. 9 stories (4×P1, 3×P2, 2×P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependencias)
- **[Story]**: US1-US9 conforme spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicializacao do projeto Next.js + ETL Python

- [x] T001 Create helpcore-platform/ directory with package.json, tsconfig.json, next.config.ts, tailwind.config.ts, postcss.config.js per plan.md structure
- [x] T002 Install dependencies: next@15 react react-dom tailwindcss @tailwindcss/typography prisma @prisma/client recharts react-diff-viewer-continued in helpcore-platform/package.json
- [x] T003 [P] Configure vitest.config.ts with React Testing Library + jsdom in helpcore-platform/vitest.config.ts
- [x] T004 [P] Create ETL directory structure: helpcore-platform/etl/ with requirements.txt (asyncpg, tqdm, pytest) and __init__.py
- [x] T005 [P] Create .env.example with DATABASE_URL, HELPCORE_AUTH_PASSWORD, HELPCORE_AUTH_SECRET in helpcore-platform/.env.example
- [x] T006 [P] Create Dockerfile (multi-stage node:20-alpine, RUN apk add --no-cache wget for healthcheck) in helpcore-platform/Dockerfile
- [x] T007 [P] Create docker-stack.yml with Traefik labels for helpcore.digital-ai.tech in helpcore-platform/docker-stack.yml

**Checkpoint**: Projeto inicializado, `npm install` e `npm run dev` funcionam.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database schema, auth middleware e layout — DEVEM estar prontos antes de qualquer user story

**⚠️ CRITICAL**: Nenhuma user story pode comecar sem esta fase completa

- [x] T008 Create Prisma schema with multiSchema preview feature, models Article + AnalysisResult + ReviewAction + ArticleRelationship mapping help_core schema in helpcore-platform/prisma/schema.prisma
- [x] T009 Generate Prisma client and validate connection to pe-postgres:5432 processing_engine database
- [x] T010 [P] Create auth helpers: generateToken (HMAC), validateToken, setSessionCookie, clearSessionCookie in helpcore-platform/src/lib/auth.ts
- [x] T011 [P] Create Prisma client singleton with global caching in helpcore-platform/src/lib/db.ts
- [x] T012 [P] Create constants: AREAS list, priority levels, score ranges, pagination defaults in helpcore-platform/src/lib/constants.ts
- [x] T013 Create Next.js middleware for cookie auth check, redirect to /login on all routes except /login and /api/auth/* in helpcore-platform/src/middleware.ts
- [x] T014 [P] Create root layout with sidebar navigation (areas list, links to /dashboard, /browse, /articles, /review) in helpcore-platform/src/app/layout.tsx
- [x] T015 [P] Create shadcn/ui base components: Button, Card, Input, Badge, Skeleton, Table in helpcore-platform/src/components/ui/
- [x] T016 Create root page.tsx that redirects to /dashboard in helpcore-platform/src/app/page.tsx

**Checkpoint**: Foundation pronta — auth funciona, layout renderiza, Prisma conecta ao banco.

---

## Phase 3: User Story 1 — ETL de Ingestao de Artigos (Priority: P1) 🎯 MVP

**Goal**: Script Python que le .txt do Help Bradesco e insere na tabela help_core.articles com dedup por content_hash.

**Independent Test**: Executar o script contra 100 .txt de amostra e verificar insercoes no banco.

### Tests for User Story 1

- [x] T017 [P] [US1] Create parser unit tests: header extraction, content extraction, encoding fallbacks, malformed files in helpcore-platform/etl/tests/test_parser.py
- [x] T018 [P] [US1] Create ingest integration tests: batch insert, dedup by content_hash, error handling in helpcore-platform/etl/tests/test_ingest.py

### Implementation for User Story 1

- [x] T019 [P] [US1] Create parser.py: parse_file() extracts 11 header fields (HELP, AREA, LISTA, TITULO, SUBTITULO, NIVEL3, GROUPSTRING, LIST_URL, IID, MODIFIED, CLASSIFICACAO) + LINKS section + CONTEUDO section, with UTF-8/latin-1/cp1252 fallback in helpcore-platform/etl/parser.py
- [x] T020 [US1] Create ingest.py: main script with asyncpg, batch of 500, content_hash SHA-256 dedup, source_url format bradesco-help://<AREA>/<IID>, tqdm progress bar, final report (inserted/duped/errors) in helpcore-platform/etl/ingest.py
- [x] T021 [US1] Run pytest and validate parser against sample .txt files from /workspace/help-bradesco/

**Checkpoint**: ETL funcional — roda contra amostra, insere corretamente, dedup funciona.

---

## Phase 4: User Story 4 — Autenticacao Basica (Priority: P1)

**Goal**: Login com senha fixa, cookie httpOnly 7d, middleware redirect.

**Independent Test**: Acessar rota protegida sem login → redirect /login. Fazer login → acesso liberado.

### Tests for User Story 4

- [x] T022 [P] [US4] Create auth API route tests: login success/failure, logout, cookie validation in helpcore-platform/src/app/api/auth/__tests__/auth.test.ts

### Implementation for User Story 4

- [x] T023 [P] [US4] Create login page with password field and error state in helpcore-platform/src/app/login/page.tsx
- [x] T024 [P] [US4] Create POST /api/auth/login route: validate password against HELPCORE_AUTH_PASSWORD env, set hc_session cookie (httpOnly, Secure, SameSite=Strict, maxAge=7d) in helpcore-platform/src/app/api/auth/login/route.ts
- [x] T025 [P] [US4] Create POST /api/auth/logout route: clear hc_session cookie in helpcore-platform/src/app/api/auth/logout/route.ts

**Checkpoint**: Auth completa — login/logout funciona, rotas protegidas redirecionam.

---

## Phase 5: User Story 2 — Dashboard de Progresso (Priority: P1)

**Goal**: Painel com progresso geral, por area, custo, tempo restante estimado, auto-refresh 30s.

**Independent Test**: Acessar /dashboard e verificar metricas contra queries SQL diretas.

### Tests for User Story 2

- [x] T026 [P] [US2] Create dashboard API route tests: progress endpoint returns correct counts, costs, areas in helpcore-platform/src/app/api/dashboard/__tests__/progress.test.ts

### Implementation for User Story 2

- [x] T027 [US2] Create GET /api/dashboard/progress route: query articles count by status (LEFT JOIN analysis_results), cost from PE stats, avg_duration, estimated_remaining in helpcore-platform/src/app/api/dashboard/progress/route.ts
- [x] T028 [P] [US2] Create ProgressBar component: total/processed percentage bar with labels in helpcore-platform/src/components/ProgressBar.tsx
- [x] T029 [P] [US2] Create ScoreBadge component: colored badge for priority_level (critical=red, high=orange, medium=yellow, low=green) in helpcore-platform/src/components/ScoreBadge.tsx
- [x] T030 [US2] Create dashboard page: progress bar, area breakdown chart (Recharts BarChart stacked), cost display, estimated time, auto-refresh with setInterval 30s in helpcore-platform/src/app/dashboard/page.tsx

**Checkpoint**: Dashboard funcional — metricas corretas, auto-refresh, graficos renderizam.

---

## Phase 6: User Story 3 — Help Browser (Priority: P1)

**Goal**: Navegar artigos por area operacional com sidebar, lista paginada e detalhe.

**Independent Test**: Acessar /browse, clicar numa area, ver lista de artigos, abrir detalhe.

### Tests for User Story 3

- [x] T031 [P] [US3] Create areas API route tests: returns areas with counts in helpcore-platform/src/app/api/areas/__tests__/areas.test.ts
- [x] T032 [P] [US3] Create articles API route tests: pagination, area filter in helpcore-platform/src/app/api/articles/__tests__/articles.test.ts

### Implementation for User Story 3

- [x] T033 [US3] Create GET /api/areas route: SELECT area, COUNT(*) grouped by area with processed count (LEFT JOIN analysis_results) in helpcore-platform/src/app/api/areas/route.ts
- [x] T034 [US3] Create GET /api/articles route: query with area filter, pagination (page, per_page default 50, max 100), return articles with basic fields in helpcore-platform/src/app/api/articles/route.ts
- [x] T035 [US3] Create GET /api/articles/[id] route: return article with all fields + joined analysis_result if exists + latest review_action in helpcore-platform/src/app/api/articles/[id]/route.ts
- [x] T036 [P] [US3] Create Sidebar component: list of areas with counts, active state highlight, link to /browse/[area] in helpcore-platform/src/components/Sidebar.tsx
- [x] T037 [P] [US3] Create ArticleCard component: title, area, lista, modified_date, classification badge, processed indicator in helpcore-platform/src/components/ArticleCard.tsx
- [x] T038 [US3] Create browse page: Sidebar + main area with area selection in helpcore-platform/src/app/browse/page.tsx
- [x] T039 [US3] Create browse/[area] page: ArticleCard list with server-side pagination in helpcore-platform/src/app/browse/[area]/page.tsx
- [x] T040 [US3] Create article detail page: content display, metadata, classification, links list; if processed show indicator in helpcore-platform/src/app/articles/[id]/page.tsx

**Checkpoint**: Help Browser completo — navegar por area, ver lista, ler artigo.

---

## Phase 7: User Story 5 — Visualizador de Resultados Processados (Priority: P2)

**Goal**: Exibir 33 campos LLM para artigos processados com radar chart de qualidade.

**Independent Test**: Acessar detalhe de artigo processado e verificar campos LLM visíveis.

### Implementation for User Story 5

- [x] T041 [P] [US5] Create QualityRadar component: Recharts RadarChart with 5 axes (clarity, structure, completeness, accuracy_signals, readability) + overall_score number in helpcore-platform/src/components/QualityRadar.tsx
- [x] T042 [P] [US5] Create StepsChecklist component: ordered list of steps with action + detail in helpcore-platform/src/components/StepsChecklist.tsx
- [x] T043 [US5] Extend article detail page /articles/[id]/page.tsx: add sections Inventario (doc_type, category, subcategory, target_audience, key_topics), Qualidade (QualityRadar + ScoreBadge), Passos (StepsChecklist), Sugestoes (improvement_suggestions list)

**Checkpoint**: Visualizador funcional — artigos processados mostram todos os campos LLM.

---

## Phase 8: User Story 6 — Diff Visual (Priority: P2)

**Goal**: Side-by-side e inline diff entre conteudo original e markdown processado.

**Independent Test**: Acessar /articles/[id]/diff e verificar diferencas destacadas.

### Implementation for User Story 6

- [x] T044 [P] [US6] Create DiffViewer wrapper component: react-diff-viewer-continued with splitView toggle (side-by-side / inline), word-level highlighting in helpcore-platform/src/components/DiffViewer.tsx
- [x] T045 [US6] Create diff page: load article content + analysis markdown_content, word count comparison, DiffViewer component in helpcore-platform/src/app/articles/[id]/diff/page.tsx

**Checkpoint**: Diff funcional — side-by-side e inline, word-level highlighting.

---

## Phase 9: User Story 7 — Busca Full-Text e Filtros (Priority: P2)

**Goal**: Busca ts_vector com highlight + filtros combinados (area, priority, score, doc_type).

**Independent Test**: Buscar "cartao credito" e verificar resultados com highlight.

### Implementation for User Story 7

- [x] T046 [US7] Extend GET /api/articles route: add search param (ts_query with plainto_tsquery('portuguese', ...)), priority filter, score_min/score_max, doc_type filter, ts_headline for highlight in helpcore-platform/src/app/api/articles/route.ts
- [x] T047 [US7] Create articles search page: search input, filter panel (area dropdown, priority checkboxes, score slider, doc_type dropdown), results list with ArticleCard + highlight in helpcore-platform/src/app/articles/page.tsx

**Checkpoint**: Busca funcional — resultados relevantes, filtros combinam, highlight nos trechos.

---

## Phase 10: User Story 8 — Fila de Revisao (Priority: P3)

**Goal**: Aprovar/rejeitar/pedir revisao de artigos processados com notas obrigatorias em rejeicao.

**Independent Test**: Acessar /review, ver fila de pendentes, aprovar e rejeitar uma reescrita.

### Implementation for User Story 8

- [x] T048 [US8] Create POST /api/articles/[id]/review route: validate action (approved/rejected/revision_requested), require notes for non-approved, insert ReviewAction in helpcore-platform/src/app/api/articles/[id]/review/route.ts
- [x] T049 [US8] Create review queue page: list articles with pending review sorted by priority_level, approve/reject buttons, notes textarea (required for reject), status update in helpcore-platform/src/app/review/page.tsx

**Checkpoint**: Fila de revisao funcional — aprovar/rejeitar com notas, status atualiza.

---

## Phase 11: User Story 9 — Analytics de Distribuicao (Priority: P3)

**Goal**: Graficos de distribuicao por categoria, doc_type, area, histograma de overall_score.

**Independent Test**: Acessar /dashboard e verificar graficos de distribuicao renderizando.

### Implementation for User Story 9

- [x] T050 [US9] Create GET /api/analytics/distribution route: queries for by_category, by_doc_type, by_priority, score_histogram (10 buckets), areas_ranked in helpcore-platform/src/app/api/analytics/distribution/route.ts
- [x] T051 [US9] Add analytics section to dashboard page: donut chart (PieChart) for category/doc_type distribution, bar chart histogram for overall_score, sortable table of areas ranked by avg_score in helpcore-platform/src/app/dashboard/page.tsx

**Checkpoint**: Analytics funcional — donuts, histograma, tabela de areas renderizam.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Qualidade, performance, deploy readiness

- [x] T052 [P] Create error page (database unavailable, generic error) in helpcore-platform/src/app/error.tsx and helpcore-platform/src/app/not-found.tsx
- [x] T053 [P] Create loading skeletons for dashboard, browse, articles pages in helpcore-platform/src/app/dashboard/loading.tsx, browse/loading.tsx, articles/loading.tsx
- [x] T054 Run tsc --noEmit to verify zero TypeScript errors
- [x] T055 Run vitest to verify all tests pass
- [x] T056 Run next build to verify production build succeeds
- [x] T057 Validate all API routes against contracts/api-routes.md (response shapes, status codes)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependencias — comeca imediatamente
- **Foundational (Phase 2)**: Depende de Setup — BLOQUEIA todas as user stories
- **US1 ETL (Phase 3)**: Depende de Phase 2 (Prisma schema precisa existir para as tabelas) — BLOQUEIA US2/US3/US5/US6/US7 (sem artigos no banco, nada funciona)
- **US4 Auth (Phase 4)**: Depende de Phase 2 — INDEPENDENTE de US1 (pode rodar em paralelo)
- **US2 Dashboard (Phase 5)**: Depende de Phase 2 + US1 (precisa de artigos no banco)
- **US3 Help Browser (Phase 6)**: Depende de Phase 2 + US1 (precisa de artigos no banco)
- **US5 Visualizador (Phase 7)**: Depende de Phase 6 (estende a pagina de detalhe)
- **US6 Diff (Phase 8)**: Depende de Phase 6 (estende a pagina de detalhe)
- **US7 Busca (Phase 9)**: Depende de Phase 6 (reutiliza ArticleCard e API articles)
- **US8 Revisao (Phase 10)**: Depende de Phase 6 (precisa do detalhe de artigo)
- **US9 Analytics (Phase 11)**: Depende de Phase 5 (estende o dashboard)
- **Polish (Phase 12)**: Depende de todas as stories desejadas

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundation)
                       │
                       ├── Phase 3 (US1 ETL) ─────┬── Phase 5 (US2 Dashboard) → Phase 11 (US9 Analytics)
                       │                          │
                       │                          └── Phase 6 (US3 Browser) ─┬── Phase 7 (US5 Visualizador)
                       │                                                     ├── Phase 8 (US6 Diff)
                       │                                                     ├── Phase 9 (US7 Busca)
                       │                                                     └── Phase 10 (US8 Revisao)
                       │
                       └── Phase 4 (US4 Auth) ─── (paralelo com US1)
```

### Parallel Opportunities

- **Phase 1**: T003, T004, T005, T006, T007 em paralelo
- **Phase 2**: T010, T011, T012, T014, T015 em paralelo (apos T008/T009)
- **Phase 3 + Phase 4**: US1 (ETL) e US4 (Auth) podem rodar em paralelo
- **Phase 5 + Phase 6**: US2 (Dashboard) e US3 (Browser) podem rodar em paralelo apos US1
- **Phase 7 + Phase 8 + Phase 9 + Phase 10**: US5, US6, US7, US8 podem rodar em paralelo apos US3

---

## Parallel Example: Phase 2 Foundation

```bash
# Apos T008 (Prisma schema) e T009 (generate), em paralelo:
Task: "Create auth helpers in src/lib/auth.ts"           # T010
Task: "Create Prisma client singleton in src/lib/db.ts"  # T011
Task: "Create constants in src/lib/constants.ts"         # T012
Task: "Create root layout in src/app/layout.tsx"         # T014
Task: "Create shadcn/ui components in src/components/ui/"# T015
```

## Parallel Example: Phase 3 + Phase 4

```bash
# Em paralelo apos Foundation:
Task: "ETL parser.py + ingest.py"     # US1 (T019, T020)
Task: "Login page + auth routes"      # US4 (T023, T024, T025)
```

---

## Implementation Strategy

### MVP First (US1 + US4 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — bloqueia tudo)
3. Complete Phase 3: US1 ETL (popular banco) + Phase 4: US4 Auth (em paralelo)
4. Complete Phase 5: US2 Dashboard + Phase 6: US3 Browser (em paralelo)
5. **STOP and VALIDATE**: ETL rodou, dashboard mostra metricas, browser navega, auth protege
6. Deploy MVP em helpcore.digital-ai.tech

### Incremental Delivery (Sprint 2)

7. Add US5 Visualizador (33 campos LLM) → Test → Deploy
8. Add US6 Diff Visual → Test → Deploy
9. Add US7 Busca + Filtros → Test → Deploy

### Sprint 3 (Nice-to-Have)

10. Add US8 Fila de Revisao → Test → Deploy
11. Add US9 Analytics de Distribuicao → Test → Deploy
12. Polish → Gate → Merge

---

## Notes

- [P] tasks = arquivos diferentes, sem dependencias mutuas
- [USn] = referencia a User Story n do spec.md
- Cada story e testavel independentemente apos conclusao
- Commit apos cada task ou grupo logico
- ETL (US1) e o alicerce: sem artigos no banco, nada funciona
- Auth (US4) e independente e pode ser paralelizada com ETL
- Gotcha: node:20-alpine NAO tem wget — Dockerfile DEVE incluir `RUN apk add --no-cache wget`
- Gotcha: usuario PostgreSQL e `postgres`, nao `votolimpo`
