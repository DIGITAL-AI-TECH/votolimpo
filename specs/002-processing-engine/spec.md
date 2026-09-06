# Feature Specification: Processing Engine

**Feature Branch**: `002-processing-engine`
**Created**: 2026-09-06
**Status**: Draft
**Input**: Mecanismo agnostico de processamento de dados com IA reutilizavel entre projetos (VotoLimpo + Help Core + futuros)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submeter Artigo para Processamento (Priority: P1)

Um operador de projeto (ex: scheduler do VotoLimpo) submete um artigo de noticia coletado da web para extracao estruturada. O engine ingere o conteudo, verifica se ja foi processado (dedup), envia para a LLM configurada, valida o resultado contra o schema esperado e persiste no banco de dados do projeto.

**Why this priority**: E o fluxo core do engine — sem ele, nenhum projeto funciona. Cobre o pipeline completo de ponta a ponta para o caso de uso mais comum (artigo unico).

**Independent Test**: Pode ser testado enviando um artigo via API e verificando que o resultado correto aparece no banco de destino.

**Acceptance Scenarios**:

1. **Given** um pipeline "votolimpo-article-extraction" registrado, **When** um job com 1 artigo HTML e submetido via POST /v1/jobs, **Then** o engine retorna job_id com status "queued" e, apos processamento, o resultado esta disponivel em GET /v1/jobs/{id}/result com status "completed".
2. **Given** um artigo que ja foi processado (mesmo url_hash), **When** o mesmo artigo e submetido novamente, **Then** o engine retorna dedup_result "duplicate" sem chamar a LLM e sem custo adicional.
3. **Given** um artigo valido, **When** processado pela LLM, **Then** o output passa em todas as validacoes (schema, grounding, range, date) e e persistido no sink configurado.
4. **Given** um artigo que gera output invalido da LLM, **When** a validacao falha, **Then** o engine tenta retry (conforme config max_retries) e, se falhar de novo, marca o item como "failed" com mensagem de erro detalhada.

---

### User Story 2 - Processar Batch de Documentos (Priority: P1)

Um operador de projeto (ex: batch runner do Help Core) submete um lote de dezenas ou centenas de documentos (PDFs, HTMLs, textos) para classificacao e normalizacao. O engine processa todos em paralelo (respeitando rate limits), faz dedup semantico entre documentos similares e persiste os resultados normalizados.

**Why this priority**: O Help Core precisa processar milhares de documentos legados. Sem batch, o projeto e inviavel. Tambem essencial para VotoLimpo processar backlog de artigos.

**Independent Test**: Pode ser testado submetendo 10 documentos via POST /v1/jobs e verificando que todos retornam resultado, com duplicatas detectadas e rate limits respeitados.

**Acceptance Scenarios**:

1. **Given** um pipeline configurado com max_concurrent=5, **When** um job com 20 itens e submetido, **Then** o engine processa no maximo 5 simultaneamente e completa todos os 20.
2. **Given** 2 documentos com conteudo 90%+ similar, **When** o dedup semantico esta configurado com threshold 0.90, **Then** o segundo documento e marcado como "similar" e nao e reprocessado.
3. **Given** um batch de 50 itens onde 3 falham, **When** o job finaliza, **Then** o status e "partial" com items_completed=47, items_failed=3, e cada falha tem error message.
4. **Given** um callback_url configurado no job, **When** o batch finaliza, **Then** o engine envia POST para o callback_url com o resultado completo.

---

### User Story 3 - Registrar Pipeline via Configuracao (Priority: P1)

Um administrador de projeto registra uma nova configuracao de pipeline (ingestor, dedup, LLM, validators, sink) via API ou arquivo YAML. Cada projeto define seu proprio pipeline sem escrever codigo, apenas configuracao.

**Why this priority**: A configurabilidade e o que torna o engine agnostico. Sem ela, cada projeto precisa de codigo customizado.

**Independent Test**: Pode ser testado registrando um pipeline via POST /v1/pipelines e verificando que jobs submetidos com aquele pipeline_id usam a configuracao correta.

**Acceptance Scenarios**:

1. **Given** uma configuracao YAML valida com ingestor=html, dedup=hash, llm=openai, sink=postgresql, **When** registrada via POST /v1/pipelines, **Then** o engine retorna pipeline_id e a config fica disponivel para jobs.
2. **Given** uma configuracao com campo obrigatorio ausente (ex: sem llm.model), **When** registrada, **Then** o engine rejeita com erro 422 indicando o campo faltante.
3. **Given** um pipeline ja registrado, **When** atualizado com nova versao, **Then** jobs futuros usam a nova config e jobs em andamento continuam com a config anterior.
4. **Given** um pipeline com system_prompt_file e output_schema_file, **When** registrado, **Then** o engine carrega os arquivos referenciados e os armazena junto a configuracao.

---

### User Story 4 - Consultar Status e Metricas (Priority: P2)

Um operador de projeto consulta o status de um job em andamento, os resultados processados e as metricas agregadas (custo total, volume processado, taxa de erro) para monitorar a saude do processamento.

**Why this priority**: Essencial para operacao e debug, mas nao bloqueia o processamento em si.

**Independent Test**: Pode ser testado submetendo jobs e consultando GET /v1/jobs/{id}, GET /v1/jobs/{id}/result e GET /v1/stats.

**Acceptance Scenarios**:

1. **Given** um job em processamento, **When** consultado via GET /v1/jobs/{id}, **Then** retorna status "running" com items_total, items_completed e items_failed atualizados em tempo real.
2. **Given** um job finalizado, **When** consultado via GET /v1/jobs/{id}/result, **Then** retorna lista completa de ProcessingResult com output, usage, cost_usd e duration_ms para cada item.
3. **Given** multiplos jobs processados ao longo do tempo, **When** consultado GET /v1/stats, **Then** retorna metricas agregadas: total de jobs, total de itens, custo total USD, taxa de sucesso, duracao media.

---

### User Story 5 - Cache de Resultados (Priority: P2)

Quando um conteudo identico (mesmo content_hash) e submetido novamente — por exemplo, um artigo republicado em outro dominio — o engine retorna o resultado cacheado sem chamar a LLM, economizando custo e tempo.

**Why this priority**: Otimizacao de custo significativa (~30% economia), mas o engine funciona sem cache.

**Independent Test**: Pode ser testado submetendo o mesmo conteudo com URLs diferentes e verificando que o segundo retorna cached=true sem custo LLM.

**Acceptance Scenarios**:

1. **Given** um artigo processado com content_hash X, **When** outro artigo com content_hash identico e submetido (URL diferente), **Then** o resultado e retornado do cache com cached=true e cost_usd=0.
2. **Given** um cache com TTL de 720 horas, **When** o item cacheado tem mais de 720 horas, **Then** o engine reprocessa normalmente e atualiza o cache.
3. **Given** um job com skip_cache=true, **When** submetido, **Then** o engine ignora o cache e reprocessa pela LLM, atualizando o cache com o novo resultado.

---

### User Story 6 - Logging e Auditoria Completa (Priority: P2)

Todo o processamento e registrado em logs detalhados: cada step do pipeline (ingest, dedup, process, validate, persist) gera um registro com tokens consumidos, custo, duracao e erros. Isso permite auditoria completa e debug de problemas.

**Why this priority**: Crucial para operacao em producao e controle de custo, mas o engine funciona sem logging detalhado.

**Independent Test**: Pode ser testado processando um artigo e consultando os logs gerados para cada step.

**Acceptance Scenarios**:

1. **Given** um artigo processado com sucesso, **When** os logs sao consultados, **Then** existe um registro para cada step (ingest, dedup, process, validate, persist) com status "success", duration_ms e metadata.
2. **Given** um item que falhou na validacao, **When** os logs sao consultados, **Then** o step "validate" mostra status "failed" com error_message detalhando quais validacoes falharam.
3. **Given** um job processado, **When** os logs sao consultados, **Then** o custo total (prompt_tokens, completion_tokens, cost_usd) esta registrado no step "process".

---

### Edge Cases

- O que acontece quando a LLM retorna JSON mal-formado? Retry ate max_retries, depois falha com erro claro.
- O que acontece quando o sink (banco de dados) esta indisponivel? O job fica com status "failed" no step "persist", mas o resultado processado fica salvo no log para reprocessamento manual.
- O que acontece quando um PDF esta corrompido ou vazio? O ingestor marca o item como "failed" no step "ingest" com erro descritivo, sem chamar a LLM.
- O que acontece com artigos em idiomas nao-portugueses? A LLM processa normalmente e preenche o campo language com o idioma detectado. O engine e agnostico a idioma.
- O que acontece quando rate limit da LLM e atingido? O engine aplica backoff exponencial (configuravel) e retenta automaticamente.
- O que acontece quando dois jobs identicos sao submetidos simultaneamente? O idempotency_key previne processamento duplo; se ausente, ambos sao processados e o dedup de sink resolve conflitos via upsert.
- O que acontece com conteudo maior que o context window da LLM? O ingestor trunca no max_content_chars configurado, preservando inicio e fim do documento.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema DEVE aceitar jobs com 1 ou mais itens de conteudo bruto (texto, HTML, PDF, JSON) via API.
- **FR-002**: Sistema DEVE processar cada item atraves de um pipeline configuravel de 5 etapas: Ingest → Dedup → Process (LLM) → Validate → Persist.
- **FR-003**: Sistema DEVE suportar multiplas estrategias de dedup intercambiaveis: hash (SHA-256 de URL e/ou conteudo), semantico (similaridade de embeddings acima de threshold configuravel) e composite (hash primeiro, semantico como fallback).
- **FR-004**: Sistema DEVE verificar dedup ANTES de chamar a LLM, garantindo zero chamadas desnecessarias (principio II da Constitution: Anti-Reprocessamento NON-NEGOTIABLE).
- **FR-005**: Sistema DEVE validar o output da LLM contra JSON Schema antes de persistir, rejeitando outputs invalidos.
- **FR-006**: Sistema DEVE suportar validacoes customizaveis alem do schema: grounding (verificar que entidades extraidas existem no texto original), range (scores entre 0.0 e 1.0), date (datas nao-futuras) e funcoes custom por projeto.
- **FR-007**: Sistema DEVE persistir resultados em sinks configuraveis por pipeline: banco de dados relacional, servicos de conteudo, armazenamento de objetos ou webhooks.
- **FR-008**: Sistema DEVE registrar um log de processamento para cada step de cada item, incluindo tokens consumidos, custo estimado, duracao e erros.
- **FR-009**: Sistema DEVE suportar processamento em batch com concorrencia configuravel e rate limiting para respeitar limites da LLM.
- **FR-010**: Sistema DEVE cachear resultados por content_hash com TTL configuravel, retornando cache hit sem custo LLM.
- **FR-011**: Sistema DEVE aceitar overrides por job (modelo LLM, skip_dedup, skip_cache, dry_run) sem alterar a configuracao do pipeline.
- **FR-012**: Sistema DEVE expor endpoints de health check e metricas agregadas (custo total, volume, taxa de sucesso).
- **FR-013**: Sistema DEVE suportar callback via webhook quando um job finaliza (sucesso, falha ou parcial).
- **FR-014**: Sistema DEVE ser agnostico ao provedor de LLM: a troca de provedor e uma mudanca de configuracao, nao de codigo.
- **FR-015**: Sistema DEVE suportar idempotency_key para prevenir reprocessamento acidental de jobs identicos.
- **FR-016**: Sistema DEVE suportar pipelines versionados, onde jobs em andamento usam a versao vigente no momento da submissao.
- **FR-017**: Sistema DEVE truncar conteudo que excede o limite configurado (max_content_chars), preservando inicio e fim do documento.
- **FR-018**: Sistema DEVE aplicar retry com backoff exponencial em falhas transientes (rate limit, timeout, erro de rede da LLM).

### Key Entities

- **Pipeline**: Configuracao reutilizavel que define como dados sao processados — ingestor, estrategia de dedup, provedor LLM + prompt + schema, validadores e sink de destino. Cada projeto registra 1+ pipelines.
- **Job**: Requisicao de processamento contendo 1 ou mais itens. Tem lifecycle (queued → running → completed/failed/partial), prioridade e callback opcional.
- **Item**: Unidade atomica de processamento dentro de um job. Contem conteudo bruto, tipo MIME, URL de origem e metadados livres do projeto.
- **Result**: Saida do processamento de um item: output estruturado da LLM, resultado da validacao, status de dedup, metricas de consumo (tokens, custo, duracao).
- **Processing Log**: Registro de auditoria para cada step do pipeline (ingest, dedup, process, validate, persist) com status, duracao, custo e erros.
- **Cache Entry**: Resultado processado indexado por content_hash, com TTL configuravel. Evita reprocessamento de conteudo identico.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um item individual e processado do inicio ao fim (ingest → persist) em menos de 30 segundos para conteudos de ate 5.000 palavras.
- **SC-002**: Batch de 100 itens e processado completamente em menos de 10 minutos com concorrencia padrao.
- **SC-003**: Itens duplicados (mesmo url_hash ou content_hash) sao rejeitados em menos de 100ms, sem nenhuma chamada a LLM.
- **SC-004**: Cache hit retorna resultado em menos de 200ms, com custo LLM zero.
- **SC-005**: 100% dos outputs persistidos passaram pela validacao de schema e todas as validacoes customizadas configuradas.
- **SC-006**: Custo total de processamento do VotoLimpo nao excede $10/mes para 10.000 artigos (conforme principio III da Constitution).
- **SC-007**: Taxa de sucesso de processamento e superior a 95% (itens completed / itens total) em operacao normal.
- **SC-008**: Trocar o provedor de LLM de um pipeline requer apenas alteracao de configuracao (0 linhas de codigo novo).
- **SC-009**: Registrar um novo pipeline para um projeto novo requer apenas 1 arquivo YAML e 0 linhas de codigo (para 80% dos casos de uso padrao).
- **SC-010**: Todo step de processamento gera log com tokens, custo e duracao — cobertura de logging de 100% dos steps executados.
- **SC-011**: Engine pode ser deployado como container unico com imagem menor que 200MB.

## Assumptions

- A infraestrutura de deploy (Docker Swarm + Traefik) ja existe e esta operacional na Digital AI.
- O banco PostgreSQL sera provisionado com extensao pgvector habilitada para dedup semantico.
- As API keys dos provedores de LLM (OpenAI, Anthropic) serao fornecidas como variaveis de ambiente.
- O volume inicial e de ~500 artigos/dia (VotoLimpo) + batches esporadicos de ~1.000 docs (Help Core).
- Pipelines customizados que requerem plugins Python (ex: SharePoint sink) serao adicionados como codigo no repositorio do engine, nao como upload dinamico.
- O acesso ao SharePoint do Help Core sera disponibilizado via credenciais OAuth2 (tenant_id, client_id, client_secret) quando o projeto avancar.
- Fila de jobs usa PostgreSQL FOR UPDATE SKIP LOCKED (sem Redis) — suficiente para o volume esperado.

## Scope

### IN SCOPE

- API REST com endpoints para jobs, pipelines, health e stats
- Orchestrator com pipeline de 5 etapas (ingest → dedup → process → validate → persist)
- Ingestors built-in: HTML, PDF, texto puro, JSON, auto-detect
- Dedup strategies built-in: hash, semantico (pgvector), composite
- LLM provider built-in: OpenAI (gpt-4.1-mini)
- Validators built-in: JSON Schema, grounding, range, date
- Sink built-in: PostgreSQL (upsert)
- Cache por content_hash com TTL configuravel
- Processing logs completos (tokens, custo, duracao, erros)
- Config de pipeline VotoLimpo pronta para uso
- Dockerfile + docker-compose para deploy

### OUT OF SCOPE (v1)

- Interface grafica (dashboard/admin UI) — operacao via API apenas
- Sink SharePoint (sera adicionado quando Help Core avancar)
- Sink S3/MinIO (sera adicionado sob demanda)
- Sink Webhook (sera adicionado sob demanda)
- LLM providers alem de OpenAI (Anthropic, Azure, Ollama serao adicionados como plugins)
- Dedup semantico cross-pipeline (dedup apenas dentro do mesmo pipeline)
- Reprocessamento automatico de itens falhados (reprocessamento e manual via skip_cache=true)
- Metricas Prometheus/Grafana (stats via API sao suficientes para v1)
- Autenticacao multi-tenant (API key unica por instancia na v1)

### REMOVIDOS (justificativa)

- Nenhum item removido (primeira versao da spec).

## Dependencies

- PostgreSQL 16 com extensao pgvector (para dedup semantico)
- OpenAI API (gpt-4.1-mini para processamento, text-embedding-3-small para embeddings)
- Docker Swarm com Traefik (infraestrutura de deploy existente)
- Firecrawl / Crawl4Prospect (coleta de dados upstream — externo ao engine)
