# Spec 007: NC+PE Integrated CI/CD

**Status:** Draft
**Priority:** HIGH
**Branch:** `feature/007-nc-pe-cicd`

## Objetivo

Criar pipeline CI/CD para o Processing Engine e integrar com o pipeline existente do News Collector, garantindo deploy coordenado de ambos os serviços.

## Acceptance Checklist

- A1. GitHub Actions workflow para PE: test → build → push → deploy via Portainer API
- A2. Deploy do PE usa Portainer API (NUNCA `docker stack deploy` CLI)
- A3. Notificações Discord via n8n webhook em todas as etapas (padrão obrigatório)
- A4. Health check pós-deploy valida PE respondendo em `/health`
- A5. Workflow dispatch manual disponível para PE
- A6. `.env.example` do PE atualizado com todas as variáveis

## IN-SCOPE

### 1. PE CI/CD Workflow (A1, A2, A5)

**Arquivo:** `processing-engine/.github/workflows/deploy.yml`

```yaml
name: Deploy Processing Engine
on:
  push:
    branches: [master]
    paths: ['processing-engine/**']
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.12'}
      - run: pip install -e ".[dev]"
        working-directory: processing-engine
      - run: pytest tests/ -q --tb=short
        working-directory: processing-engine

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - Docker login to registry.digital-ai.tech
      - Build image: registry.digital-ai.tech/votolimpo/processing-engine:$SHA
      - Push image
      - Tag as latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - PUT /api/stacks/{stackId} via Portainer API (endpoint 4)
      - Use PORTAINER_ADMIN_API_KEY from GitHub Secrets
      - Update image tag in stack env

  health-check:
    needs: deploy
    runs-on: ubuntu-latest
    steps:
      - Wait 30s for service startup
      - curl pe.votolimpo.digital-ai.tech/health
      - Validate HTTP 200 response
```

### 2. Discord Notifications (A3)

Seguir padrão obrigatório de `knowledge/skills/github-actions-notifications/`:
- Secret `N8N_NOTIFY_URL` apontando para webhook n8n
- Matriz de notificações: pipeline iniciado, build sucesso/falha, deploy em andamento, deploy concluído/falhou
- Usar `curl -sf` (NUNCA Python urllib — Cloudflare bloqueia)

### 3. Health Check (A4)

```bash
for i in $(seq 1 10); do
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" https://pe.votolimpo.digital-ai.tech/health)
  if [ "$STATUS" = "200" ]; then echo "PE healthy"; exit 0; fi
  sleep 5
done
echo "PE health check failed" && exit 1
```

### 4. .env.example (A6)

Atualizar `processing-engine/.env.example` com todas as variáveis do `config.py` documentadas.

## OUT-OF-SCOPE

- Mudanças no CI/CD do News Collector (já funciona)
- Deploy coordenado NC+PE automático (cada um deploya independente)
- Staging environment

## REMOVIDOS

Nenhum.

## Arquivos Afetados (Whitelist)

| Arquivo | Mudança |
|---------|---------|
| `processing-engine/.github/workflows/deploy.yml` | NOVO — CI/CD completo |
| `processing-engine/.env.example` | Atualizar com todas as env vars |
