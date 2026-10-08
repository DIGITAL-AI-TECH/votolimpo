# PRD: Help Core Platform — Engineering Quality Gate v3

**Fase**: 3 de 4 (executar apos ETL validado)
**Complexidade**: M
**Dependencias**: PRD 1 (PR criado), PRD 2 (dados no banco para testes E2E opcionais)

---

## Objetivo

Submeter a implementacao completa do Help Core Platform (71 arquivos, ~20k linhas)
ao pipeline obrigatorio do Engineering Quality Gate v3, garantindo que o codigo esta
pronto para merge e deploy em producao.

## Problema

O codigo foi implementado em 12 fases (57 tasks) mas ainda nao passou pelo gate formal.
Sem a validacao de HOMELAND, QA, SENTINEL, DEVOPS e PM, o merge nao pode acontecer
conforme o protocolo do Cortex.

## Escopo

### IN-SCOPE
1. Anti-regressao: validar que nenhum simbolo foi removido sem justificativa
2. HOMELAND review: arquitetura, logica vs spec, edge cases, SOLID, error handling
3. QA (code-reviewer): seguranca basica, logica de negocio, padroes, cobertura de testes
4. SENTINEL: OWASP Top 10, secrets no codigo, input validation, authn/authz
5. DEVOPS: CI readiness, Dockerfile, docker-stack.yml, env vars, healthcheck
6. PM fecho de aceite: validar A1..An da spec original vs entregue

### OUT-OF-SCOPE
- Correcoes de codigo (saem como tasks do gate, se necessario)
- Implementacao de novas features
- Deploy (PRD 4)
- Testes E2E contra banco de producao (opcional se dados ja ingeridos)

## Artefatos de Entrada

- **Spec**: `/workspace/helpcore/specs/001-helpcore-platform/spec.md`
- **Plan**: `/workspace/helpcore/specs/001-helpcore-platform/plan.md`
- **Tasks**: `/workspace/helpcore/specs/001-helpcore-platform/tasks.md`
- **Diff**: `git diff main...feature/helpcore-platform` (71 arquivos)
- **Branch**: `feature/helpcore-platform`
- **PR**: criado no PRD 1

## Pipeline de Gates

```
4a. Anti-Regressao
    git diff --name-status main...HEAD
    Verificar: nenhum arquivo do repo principal foi removido/alterado indevidamente

4b. HOMELAND (bloqueante, PRIMEIRO)
    Delegar ao agente homeland
    Input: diff completo + spec + plan
    Output: APROVADO | REPROVADO + achados
    REPROVADO → corrigir → re-submeter (max 3 ciclos)

4c. QA (code-reviewer) — apos HOMELAND aprovar
    Delegar ao agente code-reviewer
    Foco: seguranca, testes, padroes, diff coverage
    Output: APROVADO | REPROVADO + CRITICOS/ALERTAS/SUGESTOES

4d. SENTINEL — paralelo com QA
    Delegar ao agente sentinel
    Foco: OWASP, secrets, input validation, auth
    Output: APROVADO (score >= 85/100) | REPROVADO
    CRITICAL/HIGH bloqueiam

4e. DEVOPS — paralelo com QA
    Delegar ao agente devops
    Foco: Dockerfile, docker-stack.yml, CI, env vars, healthcheck
    Output: APROVADO | REPROVADO + diagnostico

4f. PM — Fecho de Aceite (apos todos os anteriores)
    Reler pedido original + Acceptance Checklist da spec
    Mapear cada item → artefato → evidencia
    Output: FECHO APROVADO | BLOQUEADO + lista do que falta
```

## Criterios de Aceite

- A1. Anti-regressao APROVADO (zero remocoes nao justificadas)
- A2. HOMELAND APROVADO (zero CRITICAL, zero HIGH nao resolvidos)
- A3. QA APROVADO (testes existem para modulos tocados, diff coverage adequado)
- A4. SENTINEL APROVADO (score >= 85/100, zero CRITICAL/HIGH)
- A5. DEVOPS APROVADO (Dockerfile valido, stack config correta, env vars documentadas)
- A6. PM fecho de aceite APROVADO (todos os itens da spec DONE ou DEFERIDO-acordado)
- A7. DoD completo com evidencias (comandos + saida, SHAs, URLs)
- A8. Pergunta de merge feita ao usuario ("Gate completo. Posso mergear?")

## Evidencias Requeridas no DoD

```
Pedido original: Help Core Platform — plataforma de gestao de knowledge base
Branch/PR: feature/helpcore-platform → PR #N
Spec: specs/001-helpcore-platform/spec.md
Testes: tsc 0 erros | vitest N/N | next build OK
HOMELAND: APROVADO (achados: ...)
QA: APROVADO (CRITICOS: 0, ALERTAS: N, SUGESTOES: N)
SENTINEL: APROVADO (score: N/100)
DEVOPS: APROVADO (Dockerfile OK, stack OK, env vars OK)
PM: FECHO APROVADO (A1..An: DONE)
```

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|----------|
| HOMELAND reprova por auth fraca | Auth basica (password) e declarada na spec como MVP, nao e surpresa |
| SENTINEL encontra secret hardcoded | Env vars ja externalizadas no docker-stack.yml |
| Ciclo de correcoes excede 3 iteracoes | Escalar ao usuario com lista do que falta |
| Diff grande (71 arquivos) sobrecarrega revisores | Focar em files criticos: auth, API routes, Prisma schema |
