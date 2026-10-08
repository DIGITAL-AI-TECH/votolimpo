# Help Core Platform — PRDs de Entrega

**Projeto**: Help Core Platform (Knowledge Base Bradesco/Ello)
**Repo**: DIGITAL-AI-TECH/helpcore, subdiretorio `helpcore-platform/`
**Data**: 2026-10-08
**Status**: PRDs criados, aguardando execucao

---

## Ordem de Execucao (sequencial, com dependencias)

```
PRD 1: Branch + PR ─────────────────────────────────────────────┐
  (isolar codigo em branch propria, criar PR)                   │
                                                                 ▼
PRD 2: ETL Ingestao ────────────────────────────────────────────┐
  (popular banco com 108K artigos, zero custo IA)               │
                                                                 ▼
PRD 3: Quality Gate v3 ─────────────────────────────────────────┐
  (HOMELAND → QA + SENTINEL + DEVOPS → PM fecho)               │
  Se REPROVADO: corrigir e re-submeter (max 3 ciclos)           │
  Se APROVADO: pedir autorizacao de merge ao usuario            │
                                                                 ▼
PRD 4: Deploy em Producao ──────────────────────────────────────┘
  (build + push + Portainer API + validacao HTTPS)
  Delegar INTEGRALMENTE ao agente devops
```

## Mapa de PRDs

| # | PRD | Arquivo | Complexidade | Dependencia |
|---|-----|---------|-------------|-------------|
| 1 | Branch + PR | [prd-branch-pr.md](prd-branch-pr.md) | XS | Nenhuma |
| 2 | ETL Ingestao | [prd-etl-ingest.md](prd-etl-ingest.md) | S | PRD 1 (branch) + banco acessivel |
| 3 | Quality Gate | [prd-quality-gate.md](prd-quality-gate.md) | M | PRD 1 (PR criado) |
| 4 | Deploy | [prd-deploy.md](prd-deploy.md) | S | PRD 1 (merged) + PRD 2 (dados) + PRD 3 (gate) |

## Notas

- **PRD 2 e PRD 3 podem correr em paralelo** se o banco ja estiver acessivel.
  O gate nao depende dos dados ingeridos (revisa codigo, nao dados), mas ter os dados
  permite testes E2E mais completos.
- **PRD 4 so executa apos merge autorizado** pelo usuario (saida do PRD 3).
- **ETL e zero custo** — parser puro de .txt, sem chamadas LLM/IA.
- **Deploy e delegado ao devops** conforme deployment-governance.md.

## Artefatos Existentes (ja implementados)

| Artefato | Status | Validacao |
|----------|--------|-----------|
| Frontend Next.js 15 | Commitado (9796ff1) | tsc 0, vitest 44/44, next build OK |
| API Routes (13 endpoints) | Commitado | Tipagem completa, Prisma queries |
| Prisma Schema (help_core) | Commitado | 1 model (Article), 14 campos |
| ETL Script (ingest.py + parser.py) | Commitado | Testado com 100 artigos amostra |
| Dockerfile (multi-stage alpine) | Commitado | wget incluido para healthcheck |
| docker-stack.yml (Traefik) | Commitado | Labels corretas, env vars externalizadas |
| Spec + Plan + Tasks | Commitados | 12 fases, 57 tasks, 100% concluidas |
