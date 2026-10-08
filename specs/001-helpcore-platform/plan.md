# Implementation Plan: Help Core Platform

**Branch**: `001-helpcore-platform` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-helpcore-platform/spec.md`

## Summary

Plataforma web monolitica (Next.js 15) para o time Ello/Bradesco visualizar, navegar e validar o processamento de 108K artigos da base de conhecimento Help Bradesco. Inclui ETL Python standalone para ingestao, dashboard de progresso em tempo real, navegacao por area operacional, visualizacao de resultados LLM com diff visual, e autenticacao basica via middleware.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js), Python 3.12 (ETL)
**Primary Dependencies**: Next.js 15, Tailwind CSS, shadcn/ui, Prisma, Recharts, react-diff-viewer-continued
**Storage**: PostgreSQL 16 (existente, pe-postgres:5432, schemas help_core + processing_engine)
**Testing**: Vitest + React Testing Library (frontend), pytest (ETL)
**Target Platform**: Linux server (Docker Swarm), browsers modernos
**Project Type**: Web application (monolito Next.js + ETL Python)
**Performance Goals**: Dashboard <2s load, busca <2s, paginacao <500ms, 108K artigos sem timeout
**Constraints**: Cookie auth httpOnly/Secure/SameSite, queries live (sem MVs no MVP), Docker <100MB image
**Scale/Scope**: 108K artigos, ~10 usuarios simultaneos, 26 areas operacionais, 33 campos LLM por artigo

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Status | Notas |
|-----------|--------|-------|
| I. Monorepo Multi-Service | PASS | helpcore-platform e subpasta do monorepo votolimpo com Dockerfile e deploy independente |
| II. Spec-Driven Development | PASS | Seguindo ciclo Speckit completo |
| III. Quality Gate Mandatorio | PASS | HOMELAND + QA + SENTINEL antes do merge |
| IV. Testes Obrigatorios | PASS | Vitest para frontend, pytest para ETL, diff coverage 100% |
| V. Deploy via DevOps | PASS | Docker Swarm + Traefik via Portainer API |

## Project Structure

### Documentation (this feature)

```text
specs/001-helpcore-platform/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-routes.md    # Next.js API routes spec
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### Source Code (repository root)

```text
helpcore-platform/
├── src/
│   ├── app/
│   │   ├── layout.tsx                    # Layout global com sidebar + auth check
│   │   ├── page.tsx                      # Redirect para /dashboard
│   │   ├── login/page.tsx                # Tela de login (senha fixa)
│   │   ├── dashboard/page.tsx            # Dashboard de progresso + analytics
│   │   ├── browse/
│   │   │   ├── page.tsx                  # Lista de areas operacionais
│   │   │   └── [area]/page.tsx           # Artigos de uma area (paginado)
│   │   ├── articles/
│   │   │   ├── page.tsx                  # Busca + filtros
│   │   │   └── [id]/
│   │   │       ├── page.tsx              # Detalhe (original + resultados LLM)
│   │   │       └── diff/page.tsx         # Diff visual
│   │   ├── review/page.tsx               # Fila de revisao
│   │   └── api/
│   │       ├── auth/login/route.ts       # POST login
│   │       ├── auth/logout/route.ts      # POST logout
│   │       ├── dashboard/progress/route.ts  # GET metricas
│   │       ├── articles/route.ts         # GET lista + busca + filtros
│   │       ├── articles/[id]/route.ts    # GET detalhe
│   │       ├── articles/[id]/review/route.ts  # POST aprovar/rejeitar
│   │       └── areas/route.ts            # GET areas com contagem
│   ├── components/
│   │   ├── ui/                           # shadcn/ui components
│   │   ├── Sidebar.tsx                   # Navegacao por area
│   │   ├── ProgressBar.tsx               # Barra de progresso
│   │   ├── QualityRadar.tsx              # Radar chart 5 scores
│   │   ├── DiffViewer.tsx                # Wrapper react-diff-viewer
│   │   ├── ArticleCard.tsx               # Card de artigo na lista
│   │   ├── StepsChecklist.tsx            # Passos extraidos
│   │   └── ScoreBadge.tsx                # Badge priority_level
│   ├── lib/
│   │   ├── db.ts                         # Prisma client singleton
│   │   ├── auth.ts                       # Helpers de auth (cookie, validate)
│   │   └── constants.ts                  # Areas operacionais, enums
│   └── middleware.ts                     # Auth middleware (cookie check)
├── prisma/
│   └── schema.prisma                     # Prisma schema (introspection help_core + processing_engine)
├── etl/
│   ├── ingest.py                         # Script ETL principal
│   ├── parser.py                         # Parser de .txt (header + conteudo)
│   ├── requirements.txt                  # asyncpg, tqdm, hashlib
│   └── tests/
│       └── test_parser.py                # Testes do parser
├── Dockerfile                            # Multi-stage (node:20-alpine)
├── docker-stack.yml                      # Swarm deploy com Traefik
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.ts
└── vitest.config.ts
```

**Structure Decision**: Next.js 15 App Router monolito com API routes internas. O ETL e um script Python standalone em `etl/` — roda uma vez (ou sob demanda), nao faz parte do runtime Next.js. Prisma conecta ao PostgreSQL existente via introspection do schema `help_core`.

## Complexity Tracking

Nenhuma violacao de constitution. Estrutura minima para o escopo.
