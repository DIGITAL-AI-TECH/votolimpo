# PRD: Help Core Platform — Branch + Pull Request

**Fase**: 1 de 4 (executar PRIMEIRO)
**Complexidade**: XS
**Dependencias**: Nenhuma

---

## Objetivo

Isolar o trabalho do Help Core Platform em uma branch propria (`feature/helpcore-platform`)
e criar um Pull Request para `main`, separando-o da branch `fix/pe-sprint1-audit-fixes`
que nao tem relacao com este projeto.

## Problema

O codigo do Help Core Platform (71 arquivos, ~20k linhas, commit `9796ff1`) foi commitado
na branch `fix/pe-sprint1-audit-fixes`, que e uma branch de correcoes do Processing Engine.
Isso polui o historico de ambos os contextos e impede um PR limpo e focado.

## Escopo

### IN-SCOPE
1. Criar branch `feature/helpcore-platform` a partir de `main`
2. Cherry-pick dos commits relevantes do Help Core (3e17e14, 9796ff1)
3. Criar PR para `main` com titulo e descricao estruturados
4. Verificar que `tsc --noEmit`, `vitest` e `next build` passam na branch nova

### OUT-OF-SCOPE
- Qualquer alteracao de codigo
- Merge do PR (depende do quality gate, PRD 3)
- Alteracoes na branch `fix/pe-sprint1-audit-fixes`

## Criterios de Aceite

- A1. Branch `feature/helpcore-platform` existe e tem como base `main`
- A2. Commits do helpcore-platform estao presentes e corretos na branch
- A3. `tsc --noEmit` retorna 0 erros
- A4. `vitest run` retorna 0 falhas
- A5. `next build` completa com sucesso (output standalone)
- A6. PR criado no GitHub com titulo, resumo (## Summary) e test plan
- A7. PR aponta de `feature/helpcore-platform` para `main`

## Execucao

```bash
git checkout main && git pull
git checkout -b feature/helpcore-platform
git cherry-pick 3e17e14 9796ff1
cd helpcore-platform && npx tsc --noEmit && npx vitest run && npm run build
gh pr create --title "feat(helpcore): Help Core Platform — full implementation" \
  --body "..." --base main
```
