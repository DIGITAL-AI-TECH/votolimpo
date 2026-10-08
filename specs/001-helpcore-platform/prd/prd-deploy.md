# PRD: Help Core Platform — Deploy em Producao

**Fase**: 4 de 4 (executar apos quality gate APROVADO e merge autorizado)
**Complexidade**: S
**Dependencias**: PRD 1 (PR merged), PRD 2 (dados no banco), PRD 3 (gate aprovado)

---

## Objetivo

Fazer deploy do Help Core Platform em `helpcore.digital-ai.tech` via Docker Swarm,
usando a API do Portainer (NUNCA CLI), com HTTPS automatico via Traefik/Let's Encrypt.

## Problema

A plataforma esta implementada e validada, mas nao esta acessivel em producao.
O deploy e a ultima milha para que a equipe do Bradesco/Ello possa acessar e validar
o knowledge base do Help.

## Escopo

### IN-SCOPE
1. Build da imagem Docker (multi-stage, node:20-alpine)
2. Push para registry.digital-ai.tech
3. Configurar env vars no Portainer (DATABASE_URL, HELPCORE_AUTH_PASSWORD, HELPCORE_AUTH_SECRET)
4. Criar stack via Portainer API (endpoint 4, Digital AI Contabo)
5. Validar healthcheck (GET /api/health → 200)
6. Validar acesso HTTPS em helpcore.digital-ai.tech
7. Configurar notificacoes Discord via n8n (se CI/CD criado)

### OUT-OF-SCOPE
- CI/CD automatico (pode ser criado depois, nao bloqueia deploy manual)
- DNS (assumir que *.digital-ai.tech ja aponta para o cluster)
- Monitoramento avancado (Prometheus, Grafana)
- Backup do banco (ja coberto pelo pe-postgres existente)
- Prisma migrate em producao (schema ja existe via ETL)

## Pre-requisitos

- PR merged em `main` (PRD 1 + PRD 3)
- Dados ingeridos no banco (PRD 2)
- Schema `help_core.articles` populado com >= 100K registros
- Registry Docker acessivel: `registry.digital-ai.tech`
- Portainer API key: em `/cortex/secrets/org/portainer.env`
- Rede `traefik-public` existente no Swarm

## Artefatos de Deploy

| Artefato | Path | Status |
|----------|------|--------|
| Dockerfile | `helpcore-platform/Dockerfile` | Pronto (multi-stage, alpine, wget) |
| docker-stack.yml | `helpcore-platform/docker-stack.yml` | Pronto (Traefik labels, env vars) |
| Healthcheck | GET /api/health | Implementado no Next.js |

## Env Vars Necessarias

| Variavel | Valor | Fonte |
|----------|-------|-------|
| DATABASE_URL | `postgresql://postgres:<pwd>@pe-postgres:5432/processing_engine?schema=help_core` | Volume pe-postgres |
| HELPCORE_AUTH_PASSWORD | A definir (gerar com openssl rand) | Novo |
| HELPCORE_AUTH_SECRET | A definir (gerar com openssl rand -base64 32) | Novo |
| IMAGE_TAG | SHA do commit merged | CI ou manual |

## Procedimento de Deploy

```bash
# 1. Build e push (delegar ao DEVOPS)
cd helpcore-platform
docker build -t registry.digital-ai.tech/helpcore-platform:${SHA} .
docker push registry.digital-ai.tech/helpcore-platform:${SHA}

# 2. Criar stack via Portainer API (OBRIGATORIO — NUNCA CLI)
# POST /api/stacks/create/swarm/string?endpointId=4
# Body: docker-stack.yml com env vars preenchidas

# 3. Validar
curl -sf https://helpcore.digital-ai.tech/api/health
# Esperado: {"status":"healthy"} ou similar

# 4. Validar dados
curl -sf https://helpcore.digital-ai.tech/api/articles?page=1&pageSize=5
# Esperado: lista de artigos do Help Bradesco
```

## Criterios de Aceite

- A1. Imagem Docker buildada e pushada para registry.digital-ai.tech
- A2. Stack criada via Portainer API (endpoint 4), nao via CLI
- A3. Servico healthy (1/1 replicas, healthcheck passing)
- A4. HTTPS funcional: `curl -sf https://helpcore.digital-ai.tech/api/health` retorna 200
- A5. Certificado TLS valido (Let's Encrypt, sem erros de cert)
- A6. Pagina inicial carrega com dados reais (artigos do Help Bradesco visiveis)
- A7. Auth funcional: acesso sem credenciais retorna 401, com credenciais retorna 200
- A8. Notificacao Discord de deploy enviada (se pipeline CI/CD existir)

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|----------|
| Healthcheck falha (node:20-alpine sem wget) | Dockerfile ja inclui `apk add wget` (gotcha documentado) |
| Certificado TLS demora | Traefik + Let's Encrypt geralmente resolve em < 2 min |
| DATABASE_URL incorreta | Testar conexao antes do deploy (`psql` ou `asyncpg`) |
| Imagem grande | Multi-stage build + alpine + standalone output (~150MB estimado) |
| Stack aparece como "limited" no Portainer | Regra: SEMPRE via API, NUNCA via CLI |

## Rollback

Se o deploy falhar:
1. Via Portainer API: GET service → extrair PreviousSpec → POST update com PreviousSpec
2. Ou simplesmente deletar a stack (servico novo, sem versao anterior)
3. Dados no banco nao sao afetados pelo rollback do frontend
