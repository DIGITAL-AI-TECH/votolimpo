# Spec 006: PE Security & Quality Hardening

**Status:** Draft
**Priority:** MEDIUM
**Branch:** `feature/006-pe-hardening`

## Objetivo

Endereçar os 6 achados de tech debt e segurança dos gates QA e SENTINEL da spec 003.

## Acceptance Checklist

- A1. `safe_query()` helper centralizado substitui pattern manual de validate + f-string em todos os post-processors
- A2. Sink usa connection pool em vez de `asyncpg.connect()` por chamada
- A3. Nomes de tabelas `votolimpo.*` são configuráveis via YAML (não hardcoded)
- A4. Per-processor timeout implementado (default 30s, configurável)
- A5. Rate limit no `POST /v1/jobs` (default 100 req/min, configurável)
- A6. Max body size no `POST /v1/jobs` (default 10MB)
- A7. Testes cobrem todos os 6 itens

## IN-SCOPE

### 1. safe_query() Helper (A1)

**Problema:** 6 post-processors + sink usam pattern `validate_sql_identifier(table) → f"... {table} ..."`. Se alguém esquecer validate, abre SQL injection.

**Solução:** Criar `safe_query()` em `app/plugins/post_processors/__init__.py`:
```python
def safe_query(template: str, tables: dict[str, str], *params) -> tuple[str, list]:
    """Valida todos os identifiers e retorna query + params seguros.

    Usage:
        query, params = safe_query(
            "UPDATE {politician_table} SET score = $1 WHERE id = $2",
            {"politician_table": config["politician_table"]},
            score, politician_id
        )
        await conn.execute(query, *params)
    """
    validated = {}
    for key, value in tables.items():
        validate_sql_identifier(value)
        validated[key] = value
    return template.format(**validated), list(params)
```

Migrar todos os 6 post-processors + sink para usar `safe_query()`.

### 2. Connection Pool no Sink (A2)

**Problema:** `sinks/__init__.py` cria nova conexão via `asyncpg.connect()` a cada chamada de `persist()`. Ineficiente e não reutiliza connections.

**Solução:**
- Sink recebe `pool: asyncpg.Pool` como parâmetro (mesmo pattern dos post-processors)
- `persist()` faz `async with pool.acquire() as conn:` internamente
- Pool é criado uma vez no orchestrator startup e passado ao sink

### 3. Configurable Table Names (A3)

**Problema:** `article_matcher.py` e `cluster_updater.py` hardcodam `votolimpo.politicians`, `votolimpo.articles`, etc.

**Solução:** Todos os nomes de tabela vêm do `config` dict do YAML pipeline. Defaults sensatos no código:
```python
politician_table = config.get("politician_table", "votolimpo.politicians")
articles_table = config.get("articles_table", "votolimpo.articles")
```

### 4. Per-Processor Timeout (A4)

**Problema:** SENTINEL S-001 — se um post-processor travar, todo o pipeline trava.

**Solução:** Wrap cada `processor.process()` com `asyncio.wait_for()`:
```python
timeout = float(pp_config.get("timeout_seconds", 30))
result = await asyncio.wait_for(processor.process(output, metadata, pool, pp_config), timeout=timeout)
```

Timeout configurável por processor no YAML:
```yaml
post_processors:
  - id: entity_resolver
    timeout_seconds: 60
```

### 5. Rate Limit (A5)

**Problema:** SENTINEL S-002 — endpoint de submissão sem rate limit permite DoS.

**Solução:** Middleware simples com sliding window counter (in-memory dict):
```python
from fastapi import Request, HTTPException
import time

class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = {}

    async def __call__(self, request: Request):
        key = request.client.host
        now = time.monotonic()
        # ... sliding window logic
```

Adicionar como dependency no router de jobs.

### 6. Max Body Size (A6)

**Problema:** SENTINEL S-003 — sem limite de tamanho no body, um request enorme pode consumir toda a memória.

**Solução:** Middleware que rejeita requests com `Content-Length > 10MB`:
```python
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_body_size:
        return JSONResponse(status_code=413, content={"detail": "Request too large"})
    return await call_next(request)
```

Configurável via `PE_MAX_BODY_SIZE` (default `10485760` = 10MB).

## OUT-OF-SCOPE

- WAF ou rate limit distribuído (Redis-based)
- Connection pool tuning avançado
- Mudanças no schema do banco

## REMOVIDOS

- `asyncpg.connect()` direto no sink (substituído por pool)
- Pattern manual `validate_sql_identifier() + f-string` nos processors (substituído por `safe_query()`)

## Arquivos Afetados (Whitelist)

| Arquivo | Mudança |
|---------|---------|
| `processing-engine/app/plugins/post_processors/__init__.py` | safe_query() helper |
| `processing-engine/app/plugins/post_processors/entity_resolver.py` | Migrar para safe_query() |
| `processing-engine/app/plugins/post_processors/score_calculator.py` | Migrar para safe_query() |
| `processing-engine/app/plugins/post_processors/relationship_builder.py` | Migrar para safe_query() |
| `processing-engine/app/plugins/post_processors/milestone_detector.py` | Migrar para safe_query() |
| `processing-engine/app/plugins/post_processors/article_matcher.py` | Migrar para safe_query() + configurable tables |
| `processing-engine/app/plugins/post_processors/cluster_updater.py` | Migrar para safe_query() + configurable tables |
| `processing-engine/app/plugins/sinks/__init__.py` | Pool-based connection + safe_query() |
| `processing-engine/app/core/orchestrator.py` | Per-processor timeout + pool para sink |
| `processing-engine/app/api/routes/jobs.py` | Rate limit dependency |
| `processing-engine/app/api/middleware.py` | Max body size middleware (NOVO) |
| `processing-engine/app/config.py` | PE_MAX_BODY_SIZE, PE_RATE_LIMIT_* settings |
| `processing-engine/app/main.py` | Register middleware |
| `processing-engine/tests/test_safe_query.py` | Testes do helper |
| `processing-engine/tests/test_sink_pool.py` | Testes do pool no sink |
| `processing-engine/tests/test_rate_limit.py` | Testes do rate limit |
| `processing-engine/tests/test_body_size.py` | Testes do body size |
| `processing-engine/tests/test_processor_timeout.py` | Testes do timeout |
