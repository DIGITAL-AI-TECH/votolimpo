<!--
  Sync Impact Report
  ==================
  Version change: N/A → 1.0.0 (initial ratification)
  Added principles:
    I.   Transparencia Radical
    II.  Anti-Reprocessamento
    III. Custo Controlado
    IV.  Dados > Opiniao
    V.   Idempotencia Total
    VI.  Schema First
    VII. Anti-Alucinacao
    VIII.Stack Minima
    IX.  Open Source & Eleicao 2026
    X.   Testabilidade
  Added sections:
    - Stack & Constraints
    - Pipeline Architecture
    - Governance
  Templates requiring updates:
    ✅ plan-template.md — compatible (Constitution Check section exists)
    ✅ spec-template.md — compatible (priority-based user stories)
    ✅ tasks-template.md — compatible (parallel tasks, story grouping)
  Follow-up TODOs: none
-->

# Voto Limpo Constitution

## Core Principles

### I. Transparencia Radical

Toda informacao exibida na plataforma DEVE ter fonte rastreavel.
Nenhum dado sem proveniencia entra no sistema.

- Cada artigo armazena `source_url`, `source_name`, `published_at` e
  `accessed_at` obrigatoriamente.
- Scores exibem tooltip com os sinais que os compuseram.
- Tela de perfil do politico lista todas as fontes que o mencionam.
- Se a fonte original ficar offline, `article_raw_content` preserva
  o texto integral para auditoria.

### II. Anti-Reprocessamento (NON-NEGOTIABLE)

Artigos ja coletados NUNCA sao reprocessados. O pipeline implementa
deduplicacao em 3 camadas:

1. **url_hash** (SHA-256 da URL canonica) — o Collector rejeita
   ANTES de fazer scrape se a URL ja existe na tabela `articles`.
2. **content_hash** (SHA-256 do corpo limpo) — o Processor rejeita
   ANTES de chamar a LLM se o hash ja existe (detecta mesmo conteudo
   em URLs diferentes).
3. **collection_runs** — cada execucao do coletor registra fonte,
   timestamp, contadores (coletados, duplicados, erros) para
   auditoria e idempotencia.

A violacao desta regra e bloqueante: nenhum PR que permita
reprocessamento passa pelo gate de review.

### III. Custo Controlado

GPT-4.1-mini e a LLM padrao. Nenhuma chamada desnecessaria a API.

- Meta de custo: < $10/mês para 10K artigos processados.
- Cache de respostas LLM: se content_hash ja processado, reutilizar
  o resultado anterior (zero custo).
- Batch processing: agrupar artigos por fonte para reduzir overhead.
- Monitorar custo real via `processing_logs` (tokens_input,
  tokens_output, cost_usd por artigo).
- Alertar se custo mensal ultrapassar $15 (150% do budget).

### IV. Dados > Opiniao

Scores e metricas sao calculados algoritmicamente, nunca
editorializados. A plataforma NAO emite opiniao — apresenta dados.

- Veracidade Score: 6 sinais ponderados objetivos (reputacao da
  fonte 30%, multi-fonte 25%, consistencia narrativa 15%, evidencia
  documental 10%, temporalidade 10%, linguagem emocional invertida 10%).
- Politician Score: severidade ponderada com normalizacao sigmoid (0-100).
- Nenhum campo de "comentario editorial" ou "opiniao da plataforma"
  existe no schema.
- Labels de severidade (`baixa`, `media`, `alta`, `gravissima`) sao
  definidos por regras explicitas, nao por julgamento humano.

### V. Idempotencia Total

Qualquer etapa do pipeline pode ser re-executada sem efeitos
colaterais. INSERT com ON CONFLICT, UPDATE com WHERE condicional.

- Collector: re-executar NAO cria artigos duplicados (url_hash UNIQUE).
- Processor: re-executar NAO duplica entidades/milestones (content_hash
  + dedup window ±7 dias para milestones).
- Score Calculator: re-executar recalcula scores e grava em
  `score_history` sem perder historico (append-only).
- Nenhuma etapa depende de estado em memoria — tudo persiste no banco.

### VI. Schema First

PostgreSQL 16 com tipos estritos. O schema e a fonte de verdade.

- ENUMs para todos os campos categoricos (severity_level, article_type,
  milestone_type, entity_type, relationship_type, processing_status,
  source_type).
- Constraints CHECK para validacao no banco (scores 0-100, datas
  validas, URLs nao-vazias).
- UNIQUE indexes para dedup (url_hash, content_hash, slug).
- Foreign keys com ON DELETE CASCADE/RESTRICT conforme semantica.
- Nenhum campo TEXT libre onde ENUM resolve. Novas categorias exigem
  migration explicita.

### VII. Anti-Alucinacao

11 checks de validacao automatica ANTES de persistir output da LLM.
Nenhum dado fabricado pela IA entra no banco sem validacao.

1. JSON schema validation (estrutura do output).
2. URL do artigo deve corresponder a URL de input.
3. published_at nao pode ser futura.
4. Entidades devem ter ao menos um match no texto original.
5. Severidade deve ser consistente com keywords detectadas.
6. Milestones devem referenciar entidades existentes no output.
7. Sentiment score dentro do range [-1.0, 1.0].
8. Categorias devem pertencer aos ENUMs definidos.
9. Resumo (summary) nao pode exceder 500 caracteres.
10. Titulo extraido deve ter overlap significativo com headline real.
11. Nenhum campo obrigatorio pode ser null ou vazio.

Artigo que falha em qualquer check vai para fila de reprocessamento
com `status = 'failed'` e `error_details` preenchido.

### VIII. Stack Minima

Complexidade minima necessaria. Sem over-engineering.

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| Frontend | Next.js 15 | SSR, React, ecosystem |
| Banco | PostgreSQL 16 (`pe-postgres` Docker, NAO Supabase) | ENUMs, pg_trgm, JSONB, views |
| Coleta | Firecrawl (self-hosted) | Crawl4Prospect da Digital AI |
| Processamento | GPT-4.1-mini | Custo/qualidade otimo |
| Deploy | Docker Swarm + Traefik | Infra existente Digital AI |
| Grafos | D3.js | Interatividade client-side |
| DNS/CDN | Cloudflare | Dominio votolimpo.com.br |

Adicionar tecnologia nova requer justificativa no PR e aprovacao.

### IX. Open Source & Eleicao 2026

Codigo publico em `DIGITAL-AI-TECH/votolimpo`. Dados de fontes
publicas apenas (portais de noticias, TSE, tribunais).

- Foco exclusivo: eleicao presidencial brasileira de 2026.
- Nenhum dado privado, pessoal (LGPD) ou de fontes pagas.
- Seed de politicos a partir de dados do TSE (candidatos registrados).
- Seed de fontes: 15 portais de noticias brasileiros com reputacao
  conhecida (definidos na processing-spec).

### X. Testabilidade

Todo componente e testavel de forma isolada.

- Collector: testavel com mock de Firecrawl (fixture HTML).
- Processor: testavel com artigo fixture → output JSON esperado.
- Score Calculator: testavel com dataset de artigos → scores esperados.
- Frontend: testavel com dados mockados (ja existentes no prototipo).
- Migrations: testavel com banco temporario em CI.

## Stack & Constraints

**Repositorios**:
- `github.com/DIGITAL-AI-TECH/votolimpo` (publico) — Processing Engine + Frontend Next.js
- `github.com/DIGITAL-AI-TECH/news-collector` — Collector (intake) + UI admin
**Branch model**: `main` (producao) ← `feature/*` | `fix/*`
**Dominio**: `votolimpo.com.br` (Cloudflare Pages + DNS)
**LLM**: OpenAI GPT-4.1-mini (structured JSON output)
**Coleta**: Firecrawl via Crawl4Prospect (`crawl4prospect.digital-ai.tech`)
**Deploy**: Docker Swarm (`digital-ai.tech` cluster) + Traefik

### Banco de Dados (NON-NEGOTIABLE)

**UNICO banco**: PostgreSQL 16 via container `pe-postgres:5432` (Docker Swarm overlay).
**NAO existe Supabase, banco externo ou banco AWS neste projeto.**

Dois databases na mesma instancia PostgreSQL, com schemas internos:

| Database | Schema | Proposito | Quem usa |
|----------|--------|-----------|----------|
| `processing_engine` | `public` | Job queue, pipelines, custos | PE (API + Worker) |
| `news_collector` | `news_collector` | Entities, articles, article_entities, schedules, sources (NC internal) | News Collector (FastAPI) |
| `news_collector` | `votolimpo` | Politicians, articles (sink output), milestones, scores, clusters | PE (sink writes via VOTOLIMPO_DATABASE_URL) + NC (cross-schema reads) + Frontend (via NC API) |

**NOTA**: O schema chama-se `votolimpo` (sem underscore). As tabelas do schema `votolimpo`
vivem DENTRO do database `news_collector` (mesmo database do NC). NC acessa ambos schemas.

**Connection strings** (env vars no Portainer stack 345):
- `DATABASE_URL` = `postgresql+asyncpg://postgres:<pwd>@pe-postgres:5432/processing_engine`
- `VOTOLIMPO_DATABASE_URL` = `postgresql://postgres:<pwd>@pe-postgres:5432/news_collector`
  (aponta pro database news_collector onde vive o schema votolimpo)

**NC** (Portainer stack 347) conecta no mesmo `pe-postgres`:
- `DATABASE_URL` = `postgresql+asyncpg://postgres:<pwd>@pe-postgres:5432/news_collector`

**Credenciais**: `/cortex/secrets/projects/votolimpo.env`

### Limites operacionais

- Budget LLM mensal: $10 (alerta em $15)
- Artigos/dia maximo: ~500 (rate limit Firecrawl + custo)
- Latencia frontend: < 2s para qualquer tela (SSR + cache)
- Uptime: best-effort (projeto open source, nao SLA comercial)

## Pipeline Architecture

```
Fontes (15 portais) → Firecrawl (coleta)
    ↓
  url_hash check (dedup camada 1)
    ↓
  raw_content → content_hash check (dedup camada 2)
    ↓
  GPT-4.1-mini (extracao estruturada)
    ↓
  11 validation checks (anti-alucinacao)
    ↓
  PostgreSQL (persist com ON CONFLICT)
    ↓
  Score Calculator (veracidade + politician score)
    ↓
  Frontend Next.js (5 telas: ranking, perfil, grafo, timeline, busca)
```

### Cron jobs

**NC crons** (APScheduler no News Collector):

| Job | Frequencia | Funcao |
|-----|-----------|--------|
| Collector | 4x/dia (6h, 12h, 18h, 0h) | Coletar artigos novos via Firecrawl |

**PE crons** (APScheduler em `app/cron/__init__.py` — globais, NAO configurados por pipeline YAML):

| Job | Frequencia | Funcao |
|-----|-----------|--------|
| cron_recalculate_scores | 1x/dia (3h) | Recalcular scores de politicos |
| cron_refresh_mvs | A cada 6h | Refresh materialized views (se existirem) |
| cron_regenerate_content | 1x/semana (dom 5h) | Gerar bios e AI summaries via LLM |
| cron_cleanup_logs | Mensal (dia 1, 2h) | Limpar logs >90 dias |
| cron_deactivate_stale_clusters | 1x/dia (4h) | Desativar clusters inativos |

## Governance

Esta constitution e o documento supremo do projeto Voto Limpo.
Todos os PRs, reviews e decisoes tecnicas DEVEM estar em
conformidade com os principios aqui definidos.

### Processo de emenda

1. Propor alteracao via PR com label `constitution`.
2. Descrever principio afetado, motivacao e impacto.
3. Aprovacao do owner do projeto (Matheus Terra).
4. Atualizar version (SemVer: MAJOR para remocao/redefinicao de
   principio, MINOR para adicao, PATCH para clarificacao).
5. Propagar alteracoes para templates dependentes.

### Compliance

- Todo PR DEVE verificar conformidade com os principios antes do merge.
- Anti-Reprocessamento (II) e Anti-Alucinacao (VII) sao NON-NEGOTIABLE
  — PRs que violem sao automaticamente rejeitados.
- O gate de review (engineering-quality-gate) verifica testes,
  seguranca e conformidade com esta constitution.

**Version**: 1.2.0 | **Ratified**: 2026-09-06 | **Last Amended**: 2026-09-19
