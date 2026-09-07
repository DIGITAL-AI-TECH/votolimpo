# Quickstart: Pool de Ingestão

Guia prático para coletores que querem enviar dados ao Processing Engine via Pool.

## Conceito

A Pool é o ponto de entrada para **qualquer coletor** depositar dados brutos. Você informa o `pipeline_id` e o conteúdo — o engine cuida do resto (batching, dedup, processamento, validação, persistência).

```
Seu Coletor ──POST /v1/pool/ingest──> Pool ──Auto-Batcher──> Engine ──> Sink
```

## Pré-requisitos

1. Processing Engine rodando (local ou produção)
2. Um pipeline registrado (via POST /v1/pipelines ou YAML)
3. API key configurada

## Enviar múltiplos itens

```bash
curl -X POST http://localhost:8000/v1/pool/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua-api-key" \
  -d '{
    "pipeline_id": "uuid-do-pipeline",
    "source_id": "meu-scraper",
    "batch_ref": "coleta-2026-09-07",
    "items": [
      {
        "source_url": "https://example.com/page1",
        "content": "<html><body>Conteúdo da página...</body></html>",
        "content_type": "text/html",
        "metadata": {"portal": "Example News"}
      },
      {
        "source_url": "https://example.com/page2",
        "content": "Texto extraído do PDF...",
        "content_type": "text/plain"
      }
    ]
  }'
```

**Resposta (201)**:
```json
{
  "accepted": 2,
  "rejected": 0,
  "pool_ids": ["uuid-1", "uuid-2"],
  "rejections": []
}
```

## Enviar item único (webhook)

```bash
curl -X POST http://localhost:8000/v1/pool/ingest/single \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sua-api-key" \
  -d '{
    "pipeline_id": "uuid-do-pipeline",
    "source_id": "n8n-webhook",
    "source_url": "https://example.com/article",
    "content": "Conteúdo do artigo...",
    "content_type": "text/plain"
  }'
```

## Consultar status da pool

```bash
curl http://localhost:8000/v1/pool/status \
  -H "X-API-Key: sua-api-key"
```

**Resposta**:
```json
{
  "pending_total": 47,
  "by_pipeline": [
    {
      "pipeline_id": "uuid-votolimpo",
      "pipeline_name": "VotoLimpo Analyzer",
      "pending": 35,
      "oldest_pending": "2026-09-07T13:45:00Z"
    }
  ]
}
```

## Campos do item

| Campo | Obrigatório | Tipo | Descrição |
|-------|-------------|------|-----------|
| `source_url` | * | string | URL de origem |
| `content` | * | string | Conteúdo bruto |
| `content_type` | Não | string | MIME type (default: "text/plain") |
| `metadata` | Não | object | Metadados livres |

\* Pelo menos `content` **ou** `source_url` é obrigatório.

## Campos do request

| Campo | Obrigatório | Tipo | Descrição |
|-------|-------------|------|-----------|
| `pipeline_id` | Sim | UUID | Pipeline que processará os itens |
| `source_id` | Não | string | Identificador do coletor |
| `batch_ref` | Não | string | Referência do batch |
| `priority` | Não | int | Prioridade (default: 0, maior = primeiro) |
| `items` | Sim | array | 1 a 500 itens |

## Duplicatas

A pool rejeita automaticamente itens com `source_url` já existente para o mesmo pipeline. Você receberá:

```json
{
  "accepted": 3,
  "rejected": 2,
  "pool_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "rejections": [
    {"index": 1, "reason": "duplicate_url", "existing_pool_id": "uuid-existente"},
    {"index": 4, "reason": "duplicate_url", "existing_pool_id": "uuid-existente-2"}
  ]
}
```

Isso é comportamento normal — significa que o coletor pode reenviar sem medo de duplicação.

## Exemplos por tipo de coletor

### Scraper (Firecrawl, Crawl4Prospect)

```python
import httpx

items = []
for page in scraped_pages:
    items.append({
        "source_url": page["url"],
        "content": page["html"],
        "content_type": "text/html",
        "metadata": {"scraped_at": page["timestamp"]}
    })

resp = httpx.post("http://engine:8000/v1/pool/ingest", json={
    "pipeline_id": "votolimpo-analyzer-uuid",
    "source_id": "votolimpo-scraper",
    "batch_ref": f"crawl-{datetime.now().isoformat()}",
    "items": items
}, headers={"X-API-Key": API_KEY})
```

### File Importer (upload de PDFs)

```python
import httpx
import fitz  # PyMuPDF

items = []
for pdf_path in pdf_files:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    items.append({
        "content": text,
        "content_type": "text/plain",
        "metadata": {"filename": pdf_path.name, "pages": len(doc)}
    })

resp = httpx.post("http://engine:8000/v1/pool/ingest", json={
    "pipeline_id": "helpcore-processor-uuid",
    "source_id": "helpcore-importer",
    "items": items
}, headers={"X-API-Key": API_KEY})
```

### Webhook n8n

Configure um HTTP Request node no n8n apontando para `POST /v1/pool/ingest/single` com o payload do item.
