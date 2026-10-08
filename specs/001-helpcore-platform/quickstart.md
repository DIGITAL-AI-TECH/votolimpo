# Quickstart: Help Core Platform

## Pre-requisitos

- Node.js 20+
- Python 3.12+
- PostgreSQL 16 (acesso ao `pe-postgres:5432` com schemas `help_core` + `processing_engine`)
- Docker (para build e deploy)

## Setup Local

### 1. Instalar dependencias Next.js

```bash
cd helpcore-platform
npm install
```

### 2. Configurar variaveis de ambiente

```bash
cp .env.example .env.local
```

Editar `.env.local`:
```env
DATABASE_URL="postgresql://postgres:<senha>@pe-postgres:5432/processing_engine?schema=help_core"
HELPCORE_AUTH_PASSWORD="<senha-de-acesso>"
HELPCORE_AUTH_SECRET="<secret-hmac-para-cookie>"
```

### 3. Gerar Prisma Client

```bash
npx prisma generate
```

### 4. Rodar em desenvolvimento

```bash
npm run dev
```

Acesse `http://localhost:3000` — sera redirecionado para `/login`.

## ETL: Ingestao de Artigos

### 1. Instalar dependencias Python

```bash
cd helpcore-platform/etl
pip install -r requirements.txt
```

### 2. Rodar ingestao

```bash
python ingest.py --source /path/to/help-bradesco/conteudos --database-url "postgresql://postgres:<senha>@pe-postgres:5432/processing_engine"
```

O script insere os artigos .txt na tabela `help_core.articles` com dedup por `content_hash`.

## Build & Deploy

### Build Docker

```bash
docker build -t helpcore-platform .
```

### Deploy via Portainer API

O deploy e feito via `docker-stack.yml` usando a API do Portainer (nunca via CLI).
Hostname: `helpcore.digital-ai.tech`

## Testes

```bash
# Frontend (Vitest)
npm run test

# ETL (pytest)
cd etl && pytest
```
