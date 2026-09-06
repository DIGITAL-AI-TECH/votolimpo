# Feature Specification: Core Engine

**Feature Branch**: `001-core-engine`
**Created**: 2026-09-06
**Status**: Draft
**Input**: Processing Engine standalone — serviço agnóstico de processamento de dados com IA, reutilizável entre projetos

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submeter Item para Processamento (Priority: P1)

Um sistema cliente (ex: scheduler, crawler, API interna) submete um item de conteúdo bruto para processamento. O engine ingere o conteúdo, verifica se já foi processado (dedup), envia para a LLM configurada, valida o resultado contra o schema esperado e persiste no sink configurado.

**Why this priority**: É o fluxo core do engine — sem ele, nenhum projeto funciona. Cobre o pipeline completo de ponta a ponta para o caso de uso mais comum (item único).

**Independent Test**: Pode ser testado enviando um item via API e verificando que o resultado correto aparece no sink de destino.

**Acceptance Scenarios**:

1. **Given** um pipeline registrado, **When** um job com 1 item é submetido via POST /v1/jobs, **Then** o engine retorna job_id com status "queued" e, após processamento, o resultado está disponível em GET /v1/jobs/{id}/result com status "completed".
2. **Given** um item que já foi processado (mesmo url_hash), **When** o mesmo item é submetido novamente, **Then** o engine retorna dedup_result "duplicate" sem chamar a LLM e sem custo adicional.
3. **Given** um item válido, **When** processado pela LLM, **Then** o output passa em todas as validações (schema, grounding, range, date) e é persistido no sink configurado.
4. **Given** um item que gera output inválido da LLM, **When** a validação falha, **Then** o engine tenta retry (conforme config max_retries) e, se falhar de novo, marca o item como "failed" com mensagem de erro detalhada.

---

### User Story 2 - Processar Batch de Documentos (Priority: P1)

Um sistema cliente submete um lote de dezenas ou centenas de documentos (PDFs, HTMLs, textos) para processamento em paralelo. O engine processa todos respeitando rate limits, faz dedup entre documentos similares e persiste os resultados normalizados.

**Why this priority**: Processamento em batch é essencial para qualquer projeto que tenha backlog. Sem batch, o serviço é inviável para volumes reais.

**Independent Test**: Pode ser testado submetendo 10 documentos via POST /v1/jobs e verificando que todos retornam resultado, com duplicatas detectadas e rate limits respeitados.

**Acceptance Scenarios**:

1. **Given** um pipeline configurado com max_concurrent=5, **When** um job com 20 itens é submetido, **Then** o engine processa no máximo 5 simultaneamente e completa todos os 20.
2. **Given** 2 documentos com conteúdo 90%+ similar, **When** o dedup semântico está configurado com threshold 0.90, **Then** o segundo documento é marcado como "similar" e não é reprocessado.
3. **Given** um batch de 50 itens onde 3 falham, **When** o job finaliza, **Then** o status é "partial" com items_completed=47, items_failed=3, e cada falha tem error message.
4. **Given** um callback_url configurado no job, **When** o batch finaliza, **Then** o engine envia POST para o callback_url com o resultado completo.

---

### User Story 3 - Registrar Pipeline via Configuração (Priority: P1)

Um administrador registra uma nova configuração de pipeline (ingestor, dedup, LLM, validators, sink) via API ou arquivo YAML. Cada projeto define seu próprio pipeline sem escrever código, apenas configuração.

**Why this priority**: A configurabilidade é o que torna o engine agnóstico. Sem ela, cada projeto precisa de código customizado.

**Independent Test**: Pode ser testado registrando um pipeline via POST /v1/pipelines e verificando que jobs submetidos com aquele pipeline_id usam a configuração correta.

**Acceptance Scenarios**:

1. **Given** uma configuração YAML válida com ingestor=html, dedup=hash, llm=openai, sink=postgresql, **When** registrada via POST /v1/pipelines, **Then** o engine retorna pipeline_id e a config fica disponível para jobs.
2. **Given** uma configuração com campo obrigatório ausente (ex: sem llm.model), **When** registrada, **Then** o engine rejeita com erro 422 indicando o campo faltante.
3. **Given** um pipeline já registrado, **When** atualizado com nova versão, **Then** jobs futuros usam a nova config e jobs em andamento continuam com a config anterior.
4. **Given** um pipeline com system_prompt_file e output_schema_file, **When** registrado, **Then** o engine carrega os arquivos referenciados e os armazena junto à configuração.

---

### User Story 4 - Consultar Status e Métricas (Priority: P2)

Um operador consulta o status de um job em andamento, os resultados processados e as métricas agregadas (custo total, volume processado, taxa de erro) para monitorar a saúde do processamento.

**Why this priority**: Essencial para operação e debug, mas não bloqueia o processamento em si.

**Independent Test**: Pode ser testado submetendo jobs e consultando GET /v1/jobs/{id}, GET /v1/jobs/{id}/result e GET /v1/stats.

**Acceptance Scenarios**:

1. **Given** um job em processamento, **When** consultado via GET /v1/jobs/{id}, **Then** retorna status "running" com items_total, items_completed e items_failed atualizados em tempo real.
2. **Given** um job finalizado, **When** consultado via GET /v1/jobs/{id}/result, **Then** retorna lista completa de resultados com output, usage, cost_usd e duration_ms para cada item.
3. **Given** múltiplos jobs processados, **When** consultado GET /v1/stats, **Then** retorna métricas agregadas: total de jobs, total de itens, custo total USD, taxa de sucesso, duração média.

---

### User Story 5 - Cache de Resultados (Priority: P2)

Quando um conteúdo idêntico (mesmo content_hash) é submetido novamente — por exemplo, conteúdo republicado em outro domínio — o engine retorna o resultado cacheado sem chamar a LLM, economizando custo e tempo.

**Why this priority**: Otimização de custo significativa (~30% economia), mas o engine funciona sem cache.

**Independent Test**: Pode ser testado submetendo o mesmo conteúdo com URLs diferentes e verificando que o segundo retorna cached=true sem custo LLM.

**Acceptance Scenarios**:

1. **Given** um item processado com content_hash X, **When** outro item com content_hash idêntico é submetido (URL diferente), **Then** o resultado é retornado do cache com cached=true e cost_usd=0.
2. **Given** um cache com TTL de 720 horas, **When** o item cacheado tem mais de 720 horas, **Then** o engine reprocessa normalmente e atualiza o cache.
3. **Given** um job com skip_cache=true, **When** submetido, **Then** o engine ignora o cache e reprocessa pela LLM, atualizando o cache com o novo resultado.

---

### User Story 6 - Logging e Auditoria Completa (Priority: P2)

Todo o processamento é registrado em logs detalhados: cada step do pipeline (ingest, dedup, process, validate, persist) gera um registro com tokens consumidos, custo, duração e erros. Isso permite auditoria completa e debug de problemas.

**Why this priority**: Crucial para operação em produção e controle de custo, mas o engine funciona sem logging detalhado.

**Independent Test**: Pode ser testado processando um item e consultando os logs gerados para cada step.

**Acceptance Scenarios**:

1. **Given** um item processado com sucesso, **When** os logs são consultados, **Then** existe um registro para cada step (ingest, dedup, process, validate, persist) com status "success", duration_ms e metadata.
2. **Given** um item que falhou na validação, **When** os logs são consultados, **Then** o step "validate" mostra status "failed" com error_message detalhando quais validações falharam.
3. **Given** um job processado, **When** os logs são consultados, **Then** o custo total (prompt_tokens, completion_tokens, cost_usd) está registrado no step "process".

---

### User Story 7 - Metrificação de Custos por Execução, Chamada e Projeto (Priority: P1)

Um operador precisa saber exatamente quanto cada execução, cada chamada de API e cada projeto estão custando. O engine armazena logs granulares de todas as chamadas LLM (modelo, tokens in/out, custo unitário) e expõe endpoints de consulta com agregações por job, por pipeline e por período — permitindo controle financeiro preciso e alertas de budget.

**Why this priority**: Sem metrificação de custo, o engine funciona mas é impossível saber se está dentro do orçamento. Para um serviço multi-projeto, controle de custo é P1 — cada projeto paga pelo que consome.

**Independent Test**: Pode ser testado processando itens em 2 pipelines diferentes e verificando que GET /v1/costs retorna breakdown correto por pipeline, por job e por período.

**Acceptance Scenarios**:

1. **Given** uma chamada LLM processada, **When** o log de custo é consultado, **Then** existe registro com: model, provider, prompt_tokens, completion_tokens, total_tokens, cost_usd (calculado a partir da tabela de preços do modelo), latency_ms, timestamp, job_id, item_id, pipeline_id.
2. **Given** 3 jobs processados no pipeline "votolimpo", **When** GET /v1/costs?pipeline_id=votolimpo é consultado, **Then** retorna total_cost_usd, total_tokens, total_calls, avg_cost_per_item e breakdown por job.
3. **Given** jobs processados em múltiplos pipelines durante o mês, **When** GET /v1/costs?group_by=pipeline&period=month é consultado, **Then** retorna ranking de pipelines por custo, com totais e médias.
4. **Given** um pipeline com budget_limit_usd configurado, **When** o custo acumulado no período atinge 80% do limite, **Then** o engine emite warning no log; ao atingir 100%, rejeita novos jobs com erro 429 e mensagem "Budget limit reached".
5. **Given** múltiplas chamadas LLM (incluindo retries), **When** o custo do item é calculado, **Then** TODAS as chamadas (inclusive retries falhados) são contabilizadas no custo total do item.

---

### Edge Cases

- O que acontece quando a LLM retorna JSON mal-formado? Retry até max_retries, depois falha com erro claro.
- O que acontece quando o sink (banco de dados) está indisponível? O job fica com status "failed" no step "persist", mas o resultado processado fica salvo no log para reprocessamento manual.
- O que acontece quando um PDF está corrompido ou vazio? O ingestor marca o item como "failed" no step "ingest" com erro descritivo, sem chamar a LLM.
- O que acontece quando rate limit da LLM é atingido? O engine aplica backoff exponencial (configurável) e retenta automaticamente.
- O que acontece quando dois jobs idênticos são submetidos simultaneamente? O idempotency_key previne processamento duplo; se ausente, ambos são processados e o dedup de sink resolve conflitos via upsert.
- O que acontece com conteúdo maior que o context window da LLM? O ingestor trunca no max_content_chars configurado, preservando início e fim do documento.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema DEVE aceitar jobs com 1 ou mais itens de conteúdo bruto (texto, HTML, PDF, JSON) via API REST.
- **FR-002**: Sistema DEVE processar cada item através de um pipeline configurável de 5 etapas: Ingest → Dedup → Process (LLM) → Validate → Persist.
- **FR-003**: Sistema DEVE suportar múltiplas estratégias de dedup intercambiáveis: hash (SHA-256 de URL e/ou conteúdo), semântico (similaridade de embeddings acima de threshold configurável) e composite (hash primeiro, semântico como fallback).
- **FR-004**: Sistema DEVE verificar dedup ANTES de chamar a LLM, garantindo zero chamadas desnecessárias (princípio II da Constitution: Anti-Reprocessamento NON-NEGOTIABLE).
- **FR-005**: Sistema DEVE validar o output da LLM contra JSON Schema antes de persistir, rejeitando outputs inválidos.
- **FR-006**: Sistema DEVE suportar validações customizáveis além do schema: grounding (verificar que entidades extraídas existem no texto original), range (scores entre 0.0 e 1.0), date (datas não-futuras) e funções custom por projeto.
- **FR-007**: Sistema DEVE persistir resultados em sinks configuráveis por pipeline: banco de dados relacional, serviços de conteúdo, armazenamento de objetos ou webhooks.
- **FR-008**: Sistema DEVE registrar um log de processamento para cada step de cada item, incluindo tokens consumidos, custo estimado, duração e erros.
- **FR-009**: Sistema DEVE suportar processamento em batch com concorrência configurável e rate limiting para respeitar limites da LLM.
- **FR-010**: Sistema DEVE cachear resultados por content_hash com TTL configurável, retornando cache hit sem custo LLM.
- **FR-011**: Sistema DEVE aceitar overrides por job (modelo LLM, skip_dedup, skip_cache, dry_run) sem alterar a configuração do pipeline.
- **FR-012**: Sistema DEVE expor endpoints de health check e métricas agregadas (custo total, volume, taxa de sucesso).
- **FR-013**: Sistema DEVE suportar callback via webhook quando um job finaliza (sucesso, falha ou parcial).
- **FR-014**: Sistema DEVE ser agnóstico ao provedor de LLM: a troca de provedor é uma mudança de configuração, não de código.
- **FR-015**: Sistema DEVE suportar idempotency_key para prevenir reprocessamento acidental de jobs idênticos.
- **FR-016**: Sistema DEVE suportar pipelines versionados, onde jobs em andamento usam a versão vigente no momento da submissão.
- **FR-017**: Sistema DEVE truncar conteúdo que excede o limite configurado (max_content_chars), preservando início e fim do documento.
- **FR-018**: Sistema DEVE aplicar retry com backoff exponencial em falhas transientes (rate limit, timeout, erro de rede da LLM).
- **FR-019**: Sistema DEVE registrar cada chamada LLM individual em tabela `llm_call_log` com: model, provider, prompt_tokens, completion_tokens, total_tokens, cost_usd (calculado via tabela de preços interna), latency_ms, status (success/error), error_message, job_id, item_id, pipeline_id, created_at. Retries geram registros separados.
- **FR-020**: Sistema DEVE manter tabela `model_pricing` com custo por token (input e output) por modelo/provider, usada para calcular cost_usd automaticamente. Preços atualizáveis via API ou config.
- **FR-021**: Sistema DEVE expor endpoint GET /v1/costs com filtros: pipeline_id, job_id, period (day/week/month/custom), group_by (pipeline/job/model/day). Retorna total_cost_usd, total_tokens, total_calls, avg_cost_per_item, breakdown por grupo.
- **FR-022**: Sistema DEVE suportar budget_limit_usd por pipeline (configurável no YAML). Ao atingir 80% emite warning; ao atingir 100% rejeita novos jobs com HTTP 429.
- **FR-023**: Sistema DEVE contabilizar custo de TODAS as chamadas LLM, incluindo retries falhados e chamadas de embedding para dedup semântico.

### Key Entities

- **Pipeline**: Configuração reutilizável que define como dados são processados — ingestor, estratégia de dedup, provedor LLM + prompt + schema, validadores e sink de destino. Cada projeto registra 1+ pipelines.
- **Job**: Requisição de processamento contendo 1 ou mais itens. Tem lifecycle (queued → running → completed/failed/partial), prioridade e callback opcional.
- **Item**: Unidade atômica de processamento dentro de um job. Contém conteúdo bruto, tipo MIME, URL de origem e metadados livres do projeto.
- **Result**: Saída do processamento de um item: output estruturado da LLM, resultado da validação, status de dedup, métricas de consumo (tokens, custo, duração).
- **Processing Log**: Registro de auditoria para cada step do pipeline (ingest, dedup, process, validate, persist) com status, duração, custo e erros.
- **Cache Entry**: Resultado processado indexado por content_hash, com TTL configurável. Evita reprocessamento de conteúdo idêntico.
- **LLM Call Log**: Registro individual de cada chamada a um provedor de LLM — modelo, tokens consumidos (prompt + completion), custo calculado em USD, latência, status e referências ao job/item/pipeline. Inclui retries e chamadas de embedding.
- **Model Pricing**: Tabela de preços por modelo/provider (custo por token de input e output). Usada para calcular cost_usd automaticamente em cada chamada. Atualizável sem deploy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um item individual é processado do início ao fim (ingest → persist) em menos de 30 segundos para conteúdos de até 5.000 palavras.
- **SC-002**: Batch de 100 itens é processado completamente em menos de 10 minutos com concorrência padrão.
- **SC-003**: Itens duplicados (mesmo url_hash ou content_hash) são rejeitados em menos de 100ms, sem nenhuma chamada à LLM.
- **SC-004**: Cache hit retorna resultado em menos de 200ms, com custo LLM zero.
- **SC-005**: 100% dos outputs persistidos passaram pela validação de schema e todas as validações customizadas configuradas.
- **SC-006**: Custo total de processamento para 10.000 itens/mês não excede $10 com gpt-4.1-mini (conforme princípio III da Constitution).
- **SC-007**: Taxa de sucesso de processamento é superior a 95% (itens completed / itens total) em operação normal.
- **SC-008**: Trocar o provedor de LLM de um pipeline requer apenas alteração de configuração (0 linhas de código novo).
- **SC-009**: Registrar um novo pipeline para um projeto novo requer apenas 1 arquivo YAML e 0 linhas de código (para 80% dos casos de uso padrão).
- **SC-010**: Todo step de processamento gera log com tokens, custo e duração — cobertura de logging de 100% dos steps executados.
- **SC-011**: Engine pode ser deployado como container único com imagem menor que 200MB.
- **SC-012**: 100% das chamadas LLM (incluindo retries e embeddings) são registradas em `llm_call_log` com custo calculado — zero chamadas não-contabilizadas.
- **SC-013**: Endpoint GET /v1/costs retorna breakdown de custo por pipeline com latência < 500ms para até 100K registros de chamadas.
- **SC-014**: Alerta de budget (80%) e bloqueio (100%) funcionam corretamente por pipeline, prevenindo gastos não-autorizados.

## Assumptions

- A infraestrutura de deploy (Docker Swarm + Traefik) já existe e está operacional.
- O banco PostgreSQL será provisionado com extensão pgvector habilitada para dedup semântico.
- As API keys dos provedores de LLM (OpenAI, Anthropic) serão fornecidas como variáveis de ambiente.
- O volume inicial é de ~500-1000 itens/dia por projeto cliente.
- Plugins customizados que requerem código Python (ex: sink para SharePoint) serão adicionados como código no repositório do engine, não como upload dinâmico.
- Fila de jobs usa PostgreSQL FOR UPDATE SKIP LOCKED (sem Redis) — suficiente para o volume esperado.

## Scope

### IN SCOPE

- API REST com endpoints para jobs, pipelines, health e stats
- Orchestrator com pipeline de 5 etapas (ingest → dedup → process → validate → persist)
- Ingestors built-in: HTML, PDF, texto puro, JSON, auto-detect
- Dedup strategies built-in: hash, semântico (pgvector), composite
- LLM provider built-in: OpenAI (gpt-4.1-mini)
- Validators built-in: JSON Schema, grounding, range, date
- Sink built-in: PostgreSQL (upsert)
- Cache por content_hash com TTL configurável
- Processing logs completos (tokens, custo, duração, erros)
- Dockerfile + docker-compose para deploy
- CLI para registrar pipelines via YAML

### OUT OF SCOPE (v1)

- Interface gráfica (dashboard/admin UI) — operação via API apenas
- Sink SharePoint (será adicionado como plugin)
- Sink S3/MinIO (será adicionado como plugin)
- Sink Webhook (será adicionado como plugin)
- LLM providers além de OpenAI (Anthropic, Azure, Ollama serão adicionados como plugins)
- Dedup semântico cross-pipeline (dedup apenas dentro do mesmo pipeline)
- Reprocessamento automático de itens falhados (reprocessamento é manual via skip_cache=true)
- Métricas Prometheus/Grafana (stats via API são suficientes para v1)
- Autenticação multi-tenant (API key única por instância na v1)

### REMOVIDOS (justificativa)

- Nenhum item removido (primeira versão da spec).

## Dependencies

- PostgreSQL 16 com extensão pgvector (para dedup semântico)
- OpenAI API (gpt-4.1-mini para processamento, text-embedding-3-small para embeddings)
- Docker + Docker Compose (desenvolvimento local)
- Docker Swarm + Traefik (deploy produção — opcional, via Digital AI infra)
