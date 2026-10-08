# API Routes Contract: Help Core Platform

## Auth

### POST /api/auth/login
**Request**: `{ password: string }`
**Response 200**: `{ ok: true }` + Set-Cookie `hc_session` (httpOnly, Secure, SameSite=Strict, maxAge=7d)
**Response 401**: `{ error: "Senha incorreta" }`

### POST /api/auth/logout
**Response 200**: `{ ok: true }` + Clear-Cookie `hc_session`

## Dashboard

### GET /api/dashboard/progress
**Response 200**:
```json
{
  "total_articles": 108062,
  "by_status": {
    "not_processed": 54000,
    "processed": 54000,
    "error": 62
  },
  "by_area": [
    { "area": "Alto Valor", "total": 5230, "processed": 2100 }
  ],
  "cost_usd": 45.23,
  "avg_duration_ms": 3200,
  "estimated_remaining_hours": 12.5,
  "last_updated": "2026-10-08T14:30:00Z"
}
```

## Articles

### GET /api/articles?area=&search=&priority=&score_min=&score_max=&doc_type=&page=&per_page=
**Query params**:
- `area`: filtro por area operacional (exact match)
- `search`: busca full-text (ts_vector)
- `priority`: filtro por priority_level (critical|high|medium|low)
- `score_min`, `score_max`: faixa de overall_score (0-100)
- `doc_type`: filtro por doc_type
- `page`: pagina (default 1)
- `per_page`: itens por pagina (default 50, max 100)

**Response 200**:
```json
{
  "articles": [
    {
      "id": 1,
      "title": "Abertura de Atendimento",
      "area": "Alto Valor",
      "lista": "Data de Associacao",
      "classification": "TEXTUAL",
      "modified_date": "2025-08-14T09:42:00Z",
      "is_processed": true,
      "overall_score": 73.5,
      "priority_level": "low",
      "highlight": "...procedimento de <mark>cartao</mark>..."
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 5230,
    "total_pages": 105
  }
}
```

### GET /api/articles/[id]
**Response 200**:
```json
{
  "article": {
    "id": 1,
    "title": "Abertura de Atendimento",
    "subtitle": null,
    "area": "Alto Valor",
    "lista": "Data de Associacao",
    "content": "1. Abertura de Atendimento...",
    "classification": "TEXTUAL",
    "modified_date": "2025-08-14T09:42:00Z",
    "links": ["..."],
    "source_url": "bradesco-help://Alto Valor/93"
  },
  "analysis": {
    "doc_type": "procedimento",
    "category": "atendimento",
    "subcategory": "abertura",
    "target_audience": "operador",
    "key_topics": ["cartao", "pid", "autenticacao"],
    "overall_score": 73.5,
    "priority_level": "low",
    "clarity": 70,
    "structure": 75,
    "completeness": 70,
    "accuracy_signals": 80,
    "readability": 75,
    "steps": [
      { "order": 1, "action": "Confirmar dados PID/MD", "detail": "..." }
    ],
    "improvement_suggestions": ["Adicionar exemplos praticos"],
    "markdown_content": "# Abertura de Atendimento\n\n1. ...",
    "processed_at": "2026-10-08T10:00:00Z"
  },
  "review_status": "pending",
  "last_review": null
}
```
**Response 404**: `{ error: "Artigo nao encontrado" }`

### POST /api/articles/[id]/review
**Request**: `{ action: "approved" | "rejected" | "revision_requested", notes?: string }`
**Validation**: `notes` obrigatorio quando action != "approved"
**Response 200**: `{ ok: true, review_id: 42 }`
**Response 400**: `{ error: "Notas obrigatorias para rejeicao" }`

## Areas

### GET /api/areas
**Response 200**:
```json
{
  "areas": [
    { "area": "Alto Valor", "count": 5230, "processed": 2100 },
    { "area": "SAC Cartoes", "count": 8100, "processed": 4050 }
  ]
}
```

## Analytics

### GET /api/analytics/distribution
**Response 200**:
```json
{
  "by_category": [{ "category": "atendimento", "count": 30000 }],
  "by_doc_type": [{ "doc_type": "procedimento", "count": 45000 }],
  "by_priority": [{ "priority": "low", "count": 60000 }],
  "score_histogram": [{ "range": "0-10", "count": 500 }],
  "areas_ranked": [{ "area": "Alto Valor", "avg_score": 72.3, "count": 5230 }]
}
```
