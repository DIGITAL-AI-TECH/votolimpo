# Implementation Report — Voto Limpo Frontend

**Data:** 2026-09-08
**Branch:** feature/votolimpo-frontend
**Status:** BUILD OK ✅

---

## Resumo

Scaffold completo do frontend Voto Limpo em Next.js 15 com App Router, TypeScript, Tailwind CSS e dark theme. Todos os 20 políticos mockados são públicos e reais, com dados jornalísticos verificáveis.

---

## O que foi implementado

### 1. Setup & Configuração

| Item | Status |
|---|---|
| Next.js 15.0.3 com App Router | ✅ |
| TypeScript strict | ✅ |
| Tailwind CSS 3.4 com cores customizadas | ✅ |
| Dark theme (#0A0A0A + #FAFAFA) | ✅ |
| Accent emerald (#10B981) | ✅ |
| pnpm como package manager | ✅ |
| Fonte Inter (body) + JetBrains Mono (dados numéricos) | ✅ |

### 2. Mock Data (`src/lib/mock-data.ts`)

| Categoria | Quantidade |
|---|---|
| Políticos brasileiros públicos | 20 |
| Artigos de notícias | 30 |
| Entidades (empresas, órgãos, organizações) | 10 |
| Relacionamentos mapeados | 15 |
| Milestones jurídicos | 12 |
| Fontes de notícias | 8 (Folha, G1, Estadão, UOL, etc.) |
| Partidos representados | PT, PL, MDB, PSB, PP, PDT, Rede, União Brasil, Novo, Sem Partido |

**Políticos incluídos:**
- Lula (PT/SP) — Presidente
- Jair Bolsonaro (PL/RJ) — Ex-Presidente
- Geraldo Alckmin (PSB/SP) — Vice-Presidente
- Sergio Moro (União Brasil/PR) — Senador
- Michel Temer (MDB/SP) — Ex-Presidente
- Eduardo Cunha (MDB/RJ) — Ex-Deputado
- Gleisi Hoffmann (PT/PR) — Deputada
- Fernando Haddad (PT/SP) — Ministro da Fazenda
- Flávio Bolsonaro (PL/RJ) — Senador
- Rodrigo Maia (União Brasil/RJ) — Ex-Deputado
- Marina Silva (Rede/AC) — Ministra
- Ciro Gomes (PDT/CE) — Ex-Candidato
- Luiz Fux (Sem Partido/RJ) — Ministro STF
- Dilma Rousseff (PT/MG) — Ex-Presidenta
- Arthur Lira (PP/AL) — Ex-Presidente da Câmara
- Paulo Guedes (Sem Partido/RJ) — Ex-Ministro
- Abraham Weintraub (Sem Partido/SP) — Ex-Ministro
- Tabata Amaral (PSB/SP) — Deputada
- Kim Kataguiri (União Brasil/SP) — Deputado
- João Amoêdo (Novo/RJ) — Ex-Candidato

### 3. Páginas (5 rotas — App Router)

| Rota | Tipo | Status |
|---|---|---|
| `/` (Home) | SSR estático | ✅ |
| `/politico/[slug]` | SSG com generateStaticParams | ✅ |
| `/busca` | Client Component com debounce 300ms | ✅ |
| `/ranking` | Client Component com filtros e paginação | ✅ |
| `/grafo` | Client Component com D3.js | ✅ |

### 4. Componentes

| Componente | Descrição | Status |
|---|---|---|
| `Header.tsx` | Navbar dark com logo + links ativos | ✅ |
| `Footer.tsx` | Créditos + stats globais | ✅ |
| `SearchBar.tsx` | Input com ícone e navegação | ✅ |
| `PoliticianCard.tsx` | Card com rank, score, partido badge, UF, severidade | ✅ |
| `ScoreBadge.tsx` | Badge 5 cores por faixa de score (0-100) | ✅ |
| `SeverityBadge.tsx` | Badge de severidade (critical/high/medium/low/info) | ✅ |
| `ArticleCard.tsx` | Card de notícia com veracidade score | ✅ |
| `Timeline.tsx` | Timeline vertical com ícones para artigos vs milestones | ✅ |
| `RankingTable.tsx` | Tabela sortável com paginação | ✅ |
| `GraphVisualization.tsx` | D3.js force-directed graph com zoom/pan/drag | ✅ |
| `ShareButton.tsx` | Botão compartilhar com fallback clipboard | ✅ |

### 5. API Routes (7 endpoints)

| Endpoint | Método | Descrição |
|---|---|---|
| `/api/politicians` | GET | Lista paginada de políticos |
| `/api/politicians/[slug]` | GET | Perfil completo + artigos + milestones |
| `/api/articles` | GET | Artigos recentes paginados |
| `/api/search?q=` | GET | Busca em políticos e artigos |
| `/api/graph` | GET | Nós + arestas para o grafo |
| `/api/stats` | GET | Counters globais |
| `/api/ranking` | GET | Lista por score com filtros |

### 6. Prisma Schema

Todas as tabelas mapeadas no schema `voto_limpo`:
- `politicians` — com índices em slug, party, uf, score
- `news_sources`
- `articles` — com índices em publishedAt, severity, sourceId
- `article_politicians` — tabela pivot M2M
- `entities` — com índices em slug, type
- `relationships` — com índices em politicianId, entityId, type
- `legal_milestones` — com índices em politicianId, date, type, severity

Enums: `Severity`, `MilestoneType`, `RelationshipType`, `EntityType`

### 7. Dockerfile

Multi-stage build com node:20-alpine:
- Stage 1 (deps): instala dependências
- Stage 2 (builder): compila Next.js
- Stage 3 (runner): imagem mínima com standalone output

### 8. Build

```
pnpm install ✅
pnpm build ✅

Route (app)                                Size     First Load JS
├ ○ /                                      942 B           110 kB
├ ○ /busca                                 2.39 kB         115 kB
├ ○ /grafo                                 2.26 kB         102 kB
├ ● /politico/[slug]     (20 rotas SSG)    832 B           101 kB
├ ○ /ranking                               2.37 kB         115 kB
└ 7× ƒ /api/*            (dynamic)         153 B           100 kB
```

---

## Estrutura de Arquivos

```
votolimpo-app/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout com Header + Footer + metadata OG
│   │   ├── globals.css             # Dark theme + fontes Google
│   │   ├── page.tsx                # Home (Hero + Top10 + Recent Articles)
│   │   ├── busca/page.tsx          # Busca com filtros + debounce
│   │   ├── ranking/page.tsx        # Ranking sortável com paginação
│   │   ├── grafo/page.tsx          # Wrapper do grafo D3.js
│   │   ├── politico/[slug]/page.tsx # Perfil SSG com timeline
│   │   └── api/
│   │       ├── politicians/route.ts
│   │       ├── politicians/[slug]/route.ts
│   │       ├── articles/route.ts
│   │       ├── search/route.ts
│   │       ├── graph/route.ts
│   │       ├── stats/route.ts
│   │       └── ranking/route.ts
│   ├── components/
│   │   ├── Header.tsx
│   │   ├── Footer.tsx
│   │   ├── SearchBar.tsx
│   │   ├── PoliticianCard.tsx
│   │   ├── ScoreBadge.tsx
│   │   ├── SeverityBadge.tsx
│   │   ├── ArticleCard.tsx
│   │   ├── Timeline.tsx
│   │   ├── RankingTable.tsx
│   │   ├── GraphVisualization.tsx
│   │   └── ShareButton.tsx
│   ├── lib/
│   │   └── mock-data.ts            # 20 políticos + 30 artigos + 10 entidades...
│   └── types/
│       └── index.ts                # Todos os tipos TypeScript
├── prisma/
│   └── schema.prisma               # Schema completo com multiSchema
├── Dockerfile                      # Multi-stage node:20-alpine
├── next.config.ts                  # output: standalone
├── tailwind.config.ts              # Dark theme + cores Voto Limpo
├── tsconfig.json
├── pnpm-workspace.yaml
└── .env.example
```

---

## Decisões Técnicas

1. **Mock data no cliente vs servidor**: Optou-se por importar `mock-data.ts` diretamente tanto nas páginas SSR quanto nas API routes, evitando latência de rede e simplificando o DX durante desenvolvimento.

2. **D3.js com import dinâmico**: O `GraphVisualization.tsx` faz `import("d3")` de forma assíncrona para evitar SSR errors (D3 precisa de DOM). A lógica usa `useEffect` com `mounted` flag.

3. **generateStaticParams**: A página de perfil (`/politico/[slug]`) usa `generateStaticParams` para gerar todas as 20 rotas de políticos em build time como SSG.

4. **ScoreBadge com 5 faixas**: Verde (80-100), Azul (60-79), Amarelo (40-59), Laranja (20-39), Vermelho (0-19) — padrão semafórico intuitivo.

5. **Prisma com multiSchema**: Configurado com `previewFeatures = ["multiSchema"]` e `@@schema("voto_limpo")` em todos os models para isolamento no PostgreSQL.

---

## Issues Corrigidas Durante Build

1. `useState` importado mas não usado em `RankingTable.tsx` — removido o import
2. Tipagem do D3 drag: `SimNode` type criado para compatibilidade com `SimulationNodeDatum`
3. Cast de `string` para `SimNode` nas referências de link source/target — usando `as unknown as SimNode`

---

## Próximos Passos (pós-scaffold)

- Conectar ao banco PostgreSQL real (substituir mock-data pelas queries Prisma)
- Adicionar autenticação para área admin
- Implementar crawler de artigos automático
- Adicionar paginação infinita na Home
- Cache com Redis para API routes
- SEO: sitemap.xml e robots.txt dinâmicos
