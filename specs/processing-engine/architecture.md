# Processing Engine Agnostico - Arquitetura

**Versao**: 1.0
**Data**: 2026-09-06
**Escopo**: Mecanismo reutilizavel de processamento de dados com IA

---

## 1. Visao Geral

Engine agnostico que recebe massa de dados brutos, aplica pipeline de processamento configuravel via LLM, faz dedup inteligente, valida output e persiste no destino configurado.

**Projetos-alvo iniciais:**
- **Voto Limpo**: artigos de noticias -> extracao estruturada -> PostgreSQL
- **Help Core (Bradesco/Ello)**: documentos SharePoint -> classificacao/normalizacao -> SharePoint Pages

---

## 2. Diagrama de Arquitetura

```
                         +---------------------------------------------------+
                         |              CLIENT PROJECTS                       |
                         |                                                    |
                         |  +--------------+      +--------------------+      |
                         |  |  VotoLimpo   |      |  Help Core         |      |
                         |  |  Scheduler   |      |  Batch Runner      |      |
                         |  |  (cron)      |      |  (on-demand)       |      |
                         |  +------+-------+      +--------+-----------+      |
                         +---------+---------------------------+---------------+
                                   |                           |
                         ==========+===========================+=============
                                   |  HTTP / SDK calls         |
                                   v                           v
+--------------------------------------------------------------------------+
|                     PROCESSING ENGINE (FastAPI)                            |
|                                                                           |
|  +--------------------------------------------------------------------+  |
|  |                        API LAYER                                    |  |
|  |  POST /v1/jobs              - Submeter job (single ou batch)        |  |
|  |  GET  /v1/jobs/{id}         - Status do job                         |  |
|  |  GET  /v1/jobs/{id}/result  - Resultado processado                  |  |
|  |  POST /v1/pipelines         - Registrar pipeline (CRUD)             |  |
|  |  GET  /v1/health            - Health check                          |  |
|  |  GET  /v1/stats             - Metricas agregadas                    |  |
|  +-------------------------------+------------------------------------+  |
|                                  |                                       |
|  +-------------------------------v------------------------------------+  |
|  |                     ORCHESTRATOR                                    |  |
|  |                                                                     |  |
|  |  1. Recebe ProcessingJob                                            |  |
|  |  2. Carrega PipelineConfig pelo pipeline_id                         |  |
|  |  3. Executa steps em sequencia:                                     |  |
|  |                                                                     |  |
|  |     +----------+   +----------+   +----------+   +----------+      |  |
|  |     | INGEST   |-->|  DEDUP   |-->| PROCESS  |-->| VALIDATE |      |  |
|  |     |          |   |          |   |  (LLM)   |   |          |      |  |
|  |     +----------+   +----------+   +----------+   +----------+      |  |
|  |           |                                             |           |  |
|  |           |         +----------+   +----------+         |           |  |
|  |           |         |  CACHE   |   |  PERSIST |<--------+           |  |
|  |           |         |  CHECK   |   |  (sink)  |                     |  |
|  |           |         +----------+   +----------+                     |  |
|  |           |                                                         |  |
|  |     +-----v---------------------------------------------------+    |  |
|  |     |                  PROCESSING LOG                          |    |  |
|  |     |  (cada step: tokens, custo, duracao, erros)              |    |  |
|  |     +---------------------------------------------------------+    |  |
|  +--------------------------------------------------------------------+  |
|                                                                           |
|  +--------------------------------------------------------------------+  |
|  |                     PLUGIN REGISTRY                                 |  |
|  |                                                                     |  |
|  |  LLM Providers:     |  Dedup Strategies:   |  Sinks:               |  |
|  |  +- OpenAI          |  +- HashDedup        |  +- PostgreSQL        |  |
|  |  +- Anthropic       |  +- SemanticDedup    |  +- SharePoint        |  |
|  |  +- Azure OpenAI    |  +- CompositeDedup   |  +- S3/MinIO          |  |
|  |  +- Ollama          |                      |  +- Webhook           |  |
|  |                     |  Ingestors:          |  +- FileSystem        |  |
|  |  Validators:        |  +- RawText          |                       |  |
|  |  +- JsonSchema      |  +- HTML             |                       |  |
|  |  +- GroundingCheck  |  +- PDF              |                       |  |
|  |  +- Custom          |  +- JSON             |                       |  |
|  +--------------------------------------------------------------------+  |
|                                                                           |
|  +--------------------------------------------------------------------+  |
|  |                     STORAGE (Engine DB)                             |  |
|  |  PostgreSQL schema: processing_engine                               |  |
|  |  - pipelines         (configuracoes registradas)                    |  |
|  |  - jobs              (fila + status)                                |  |
|  |  - job_items         (itens individuais dentro de um batch)         |  |
|  |  - processing_logs   (audit trail completo)                         |  |
|  |  - cache             (resultado cacheado por content_hash)          |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
```

---

## 3. Componentes

### 3.1 API Layer (FastAPI)

| Endpoint | Metodo | Funcao |
|----------|--------|--------|
| `/v1/jobs` | POST | Submeter job (single ou batch) |
| `/v1/jobs/{id}` | GET | Status do job |
| `/v1/jobs/{id}/result` | GET | Resultado processado |
| `/v1/jobs/batch` | POST | Batch com callback webhook |
| `/v1/pipelines` | POST | CRUD de pipelines |
| `/v1/pipelines/{id}` | GET | Configuracao do pipeline |
| `/v1/health` | GET | Health check |
| `/v1/stats` | GET | Metricas agregadas |

Auth: API key por projeto (header `X-Api-Key`).

### 3.2 Orchestrator

Coordena execucao step-by-step:
1. Recebe `ProcessingJob` da fila (PostgreSQL `SKIP LOCKED`)
2. Carrega `PipelineConfig` pelo `pipeline_id`
3. Para cada item: Ingest -> Cache Check -> Dedup -> Process (LLM) -> Validate -> Persist
4. Registra `processing_log` para cada step

### 3.3 Plugins

| Tipo | Plugins Built-in | Extensivel |
|------|-----------------|------------|
| **Ingestors** | RawText, HTML, PDF, JSON, Auto | Sim (Protocol) |
| **Dedup** | Hash, Semantic (pgvector), Composite | Sim |
| **LLM Providers** | OpenAI, Anthropic, Azure, Ollama | Sim |
| **Validators** | JsonSchema, Grounding, Range, Date, Custom | Sim |
| **Sinks** | PostgreSQL, SharePoint, S3, Webhook, File | Sim |

### 3.4 Processing Log

Cada step registra: `job_id`, `item_id`, `step`, `status`, `model_used`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `duration_ms`, `error_message`, `metadata` (JSONB).

---

## 4. ProcessingJob Schema (Pydantic)

```python
class ProcessingItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str                              # Conteudo bruto
    content_type: str = "text/plain"          # MIME type
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class ProcessingJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str                          # Ex: "votolimpo-article-extraction"
    items: list[ProcessingItem]
    priority: JobPriority = JobPriority.NORMAL
    callback_url: str | None = None
    idempotency_key: str | None = None
    llm_override: dict[str, Any] | None = None
    skip_dedup: bool = False
    skip_cache: bool = False
    dry_run: bool = False

class ProcessingResult(BaseModel):
    item_id: str
    status: JobStatus
    output: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    dedup_result: str | None = None           # "new" | "duplicate" | "similar"
    usage: dict[str, Any] | None = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    cached: bool = False
```

---

## 5. PipelineConfig (YAML)

Cada projeto registra configuracao via YAML — **sem codigo customizado para 80% dos casos**.

### 5.1 VotoLimpo

```yaml
pipeline:
  id: "votolimpo-article-extraction"
  name: "VotoLimpo - Extracao de Artigos Politicos"
  version: "1.0"

  ingestor:
    type: "html"
    config:
      max_content_chars: 15000
      strip_tags: true

  dedup:
    strategy: "composite"
    config:
      hash_fields: ["source_url", "content"]
      url_normalize: true
      semantic_enabled: false

  llm:
    provider: "openai"
    model: "gpt-4.1-mini"
    temperature: 0.1
    max_tokens: 4096
    max_retries: 1
    system_prompt_file: "./prompts/votolimpo-system.txt"
    output_schema_file: "./schemas/votolimpo-article-v1.json"

  validators:
    - type: "json_schema"
    - type: "grounding"
      config:
        check_fields:
          - path: "politicians[].name"
            strategy: "last_name_in_text"
          - path: "entities[].name"
            strategy: "any_word_in_text"
    - type: "range"
      config:
        fields: ["veracity_signals.*.score", "extraction_confidence.*"]
        min: 0.0
        max: 1.0
    - type: "date"
      config:
        fields: ["article.published_at"]
        no_future: true

  sink:
    type: "postgresql"
    config:
      connection_string: "${VOTOLIMPO_DATABASE_URL}"
      mappings:
        - source_path: "article"
          target_table: "articles"
          strategy: "upsert"
          key_column: "url_hash"
        - source_path: "politicians[]"
          target_table: "politicians"
          strategy: "resolve"
        - source_path: "milestones[]"
          target_table: "milestones"
          strategy: "dedup_insert"

  cache:
    enabled: true
    ttl_hours: 720
    key_strategy: "content_hash"
```

### 5.2 Help Core (Bradesco/Ello)

```yaml
pipeline:
  id: "helpcore-document-processing"
  name: "Help Core - Classificacao e Normalizacao"
  version: "1.0"

  ingestor:
    type: "auto"
    config:
      max_content_chars: 30000
      html_strip_sharepoint_chrome: true

  dedup:
    strategy: "semantic"
    config:
      embedding_model: "text-embedding-3-small"
      similarity_threshold: 0.90
      compare_scope: "same_library"

  llm:
    provider: "openai"
    model: "gpt-4.1-mini"
    temperature: 0.2
    max_tokens: 8192
    system_prompt_file: "./prompts/helpcore-system.txt"
    output_schema_file: "./schemas/helpcore-document-v1.json"

  validators:
    - type: "json_schema"
    - type: "custom"
      config:
        module: "helpcore.validators"
        function: "validate_html_structure"
    - type: "custom"
      config:
        module: "helpcore.validators"
        function: "check_content_preservation"

  sink:
    type: "sharepoint"
    config:
      tenant_id: "${SHAREPOINT_TENANT_ID}"
      site_url: "${SHAREPOINT_SITE_URL}"
      mappings:
        - output_field: "normalized_html"
          target: "page_content"
        - output_field: "classification"
          target: "page_metadata"

  cache:
    enabled: true
    ttl_hours: 2160
    key_strategy: "content_hash"
```

---

## 6. Decisoes Tecnicas

| Decisao | Escolha | Justificativa |
|---------|---------|---------------|
| Linguagem | Python (FastAPI) | Ecossistema IA maduro, PDF parsing, OpenAI SDK |
| Fila de jobs | PostgreSQL `SKIP LOCKED` | Sem dependencia extra (Redis); volume OK |
| Embeddings dedup | pgvector (PostgreSQL) | Evita servico separado; atende ate ~1M vetores |
| Arquitetura | Monolito modular + plugins | 2 projetos nao justificam microsservicos |
| Config vs Codigo | 80% config YAML / 20% plugins Python | Flexibilidade sem complexidade |

---

## 7. Estrutura de Diretorios

```
processing-engine/
  app/
    main.py                     # FastAPI app
    config.py                   # Settings (pydantic-settings)
    api/routes/                 # Endpoints
    core/
      orchestrator.py           # Pipeline coordinator
      models.py                 # Pydantic models
    plugins/
      ingestors/                # HTML, PDF, RawText, Auto
      dedup/                    # Hash, Semantic, Composite
      llm/                      # OpenAI, Anthropic, Azure, Ollama
      validators/               # JsonSchema, Grounding, Range, Date
      sinks/                    # PostgreSQL, SharePoint, S3, Webhook
    storage/
      database.py               # asyncpg
      models.py                 # ORM
      migrations/               # Alembic
  pipelines/                    # Configs YAML por projeto
  prompts/                      # System prompts por projeto
  schemas/                      # JSON Schemas de output
  tests/
  Dockerfile
  pyproject.toml
```

---

## 8. Otimizacoes de Custo

| Otimizacao | Impacto | Quando |
|-----------|---------|--------|
| Cache por content_hash | -30% custos | v1 |
| Truncamento inteligente | -20% tokens | v1 |
| Batch API OpenAI (async 24h) | -50% custo | v2 (Help Core) |
| Few-shot condicional | -$12/mes | v2 |
| Modelo menor para triagem | -40% (skip irrelevantes) | v2 |

---

## 9. Proximos Passos

1. Criar constitution + spec do Processing Engine
2. Definir schema do banco interno (pipelines, jobs, logs, cache)
3. Implementar core (orchestrator + 2 providers: OpenAI + hash dedup)
4. Implementar config VotoLimpo (prompt + schema + PostgreSQL sink)
5. Deploy no Docker Swarm
6. Implementar config Help Core quando acesso ao SharePoint estiver disponivel
