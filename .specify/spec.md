# VotoLimpo HOMELAND Audit Fixes — P0 + P1

## Objetivo

Corrigir os 6 bugs identificados na auditoria HOMELAND (score 52/100) para
elevar a qualidade do projeto VotoLimpo. Os bugs abrangem backend (Python),
frontend (React/TypeScript) e pipeline de resubmit.

## IN-SCOPE

### P0 — Críticos

**P0-1: Mapeamento sentiment_score←veracity_score incorreto**
- Arquivo: `news-collector/src/app/routers/webhooks.py:148`
- Bug: `sentiment_score=output.get("veracity_score")` — o PE não emite
  `sentiment_score`, apenas `sentiment` (label) e `veracity_score` (score de
  veracidade). São dimensões diferentes: sentimento vs veracidade.
- Fix: Mapear `sentiment_score=None` (PE não fornece esse campo)

**P0-2: Wildcards não-escapados no ILIKE**
- Arquivo: `news-collector/src/app/routers/articles.py:98-101`
- Bug: Embora use parâmetros nomeados (`:q`) via SQLAlchemy `text()` (não é SQL
  injection), o escape de wildcards ILIKE (`%`, `_`) é feito manualmente com
  `str.replace()`. Melhorar para usar abordagem mais robusta.
- Fix: Manter escape existente (já funcional) mas adicionar `ESCAPE '\'` na
  cláusula ILIKE para tornar explícito.

**P0-3: Race condition TOCTOU no resubmit**
- Arquivo: `news-collector/src/app/services/pe_resilience.py:625-664`
- Bug: SELECT e UPDATE usam sessões DB separadas. Entre fechar a sessão de
  leitura e abrir a de escrita, outro ciclo de resubmit pode ler os mesmos
  artigos `raw`, causando resubmit duplicado.
- Fix: Unificar em sessão única com `SELECT ... FOR UPDATE SKIP LOCKED` para
  lock atômico.

### P1 — Importantes

**P1-5: Status 'completed' ausente no filtro frontend**
- Arquivo: `news-collector/ui/src/pages/Articles.tsx:9`
- Bug: `STATUSES` array não inclui `'completed'` que existe no type
  `Article.status`
- Fix: Adicionar `'completed'` ao array

**P1-6: source_name não exibido**
- Arquivo: `news-collector/ui/src/pages/Articles.tsx:277`
- Bug: Exibe apenas `source_domain`, mas `source_name` é o campo mais
  descritivo
- Fix: Exibir `source_name` com fallback para `source_domain`

**P1-7: Clientes HTTP duplicados**
- Arquivo: `news-collector/ui/src/api/client.ts:46-64`
- Bug: `ncApi` e `peApi` duplicam a mesma estrutura de métodos
- Fix: Extrair factory function `createApiClient(fetchFn)`

## OUT-OF-SCOPE

- P1-4 (`|| true` em CI/CD): Não confirmado — line 31 do deploy.yml já está
  limpa. Os `|| true` existentes são em curl de notificação (correto).
- P2 items (rate limiting, JSONB index, PE coverage indicator)
- Diagnóstico da cobertura PE (0.17%) — frente separada

## REMOVIDOS

Nenhum código/funcionalidade será removido.

## Aceite

- A1. `sentiment_score` não recebe mais `veracity_score` no webhook callback
- A2. Query ILIKE usa `ESCAPE '\'` explícito
- A3. Resubmit usa sessão única com lock atômico (sem TOCTOU window)
- A4. Filtro de status no frontend inclui 'completed'
- A5. Coluna source exibe `source_name ?? source_domain ?? '—'`
- A6. Cliente HTTP usa factory sem duplicação
- A7. Testes existentes continuam passando
