# PRD: Help Core Platform — ETL de Ingestao dos 108K Artigos

**Fase**: 2 de 4 (executar apos branch/PR estar pronto)
**Complexidade**: S
**Dependencias**: PRD 1 (branch criada), banco pe-postgres:5432 acessivel

---

## Objetivo

Executar o script `etl/ingest.py` contra o banco de producao para popular a tabela
`help_core.articles` com os ~108K artigos do Help Bradesco. Parser puro, zero custo de IA.

## Problema

O Help Core Platform esta implementado (frontend + API + schema Prisma), mas a tabela
`help_core.articles` esta vazia em producao. Sem dados, a plataforma nao tem utilidade.
Os artigos fonte estao em ~108K arquivos `.txt` no formato proprietario Help Bradesco.

## Escopo

### IN-SCOPE
1. Configurar DATABASE_URL para pe-postgres:5432/processing_engine (schema help_core)
2. Executar `etl/ingest.py` com o diretorio dos 108K arquivos .txt
3. Validar contagem pos-ingestao (SELECT COUNT)
4. Validar integridade dos dados (campos nao-nulos, content_hash unico)
5. Registrar metricas: inseridos, duplicatas, erros, tempo total

### OUT-OF-SCOPE
- Processamento com LLM/IA (nao existe nesta fase)
- Modificacoes no schema do banco
- Alteracoes no script ETL (ja validado com amostra de 100)
- Deploy da aplicacao (PRD 4)

## Pre-requisitos

- Acesso de rede ao pe-postgres:5432 (Docker Swarm interno)
- Credenciais: user `postgres`, password do volume (`LzsV8TScgtl9AVol80HZcO-m7_5WIVNv`)
- Schema `help_core` com tabela `articles` ja criada (via Prisma migrate ou DDL)
- Python 3.12 com `asyncpg` e `tqdm` instalados
- Diretorio com os ~108K arquivos .txt acessivel

## Criterios de Aceite

- A1. Script executado sem erros fatais (exit code 0)
- A2. COUNT(*) em help_core.articles >= 100.000 (margem para dedup)
- A3. Zero registros com `title IS NULL` ou `content IS NULL`
- A4. Zero registros com `content_hash` duplicado (dedup por source_url funciona)
- A5. Metricas de execucao registradas: total de arquivos, inseridos, duplicatas, erros, duracao
- A6. Pelo menos 3 artigos amostrados manualmente com conteudo correto vs .txt original

## Execucao

```bash
# 1. Instalar deps
cd helpcore-platform/etl && pip install asyncpg tqdm

# 2. Configurar acesso (via Docker exec ou tunnel)
export DATABASE_URL="postgresql://postgres:LzsV8TScgtl9AVol80HZcO-m7_5WIVNv@pe-postgres:5432/processing_engine"

# 3. Garantir schema existe
# Se Prisma: cd .. && npx prisma migrate deploy
# Se DDL manual: verificar que help_core.articles existe

# 4. Executar ingestao
python ingest.py --source /path/to/help-bradesco/ --database-url "$DATABASE_URL"

# 5. Validar
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM help_core.articles;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM help_core.articles WHERE title IS NULL OR content IS NULL;"
psql "$DATABASE_URL" -c "SELECT title, LENGTH(content) FROM help_core.articles ORDER BY RANDOM() LIMIT 5;"
```

## Estimativas

- **Tempo**: ~15-30 min para 108K arquivos (BATCH_SIZE=500, asyncpg)
- **Custo**: $0 (parser puro, sem chamadas LLM)
- **Disco**: ~500MB-1GB em PostgreSQL (estimado ~5-10KB por artigo medio)

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|----------|
| Sem acesso de rede ao banco | Usar Docker exec no container PE ou SSH tunnel |
| Schema help_core nao existe | Rodar Prisma migrate deploy antes |
| Arquivos corrompidos | Script ja tem try/except por arquivo, registra erros |
| Timeout de conexao | asyncpg connection pool com timeout configuravel |
