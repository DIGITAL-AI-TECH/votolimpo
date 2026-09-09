"""Seed pipelines for Voto Limpo and HELP CORE

Inserts 5 preconfigured pipelines:
  1. voto-limpo-news-analysis — political news analysis
  2. helpcore-inventory — article classification
  3. helpcore-dedup — semantic deduplication
  4. helpcore-rewrite — assisted rewriting
  5. helpcore-quality-score — quality scoring

Revision ID: 015
Revises: 014
Create Date: 2026-09-08
"""

import json

from sqlalchemy import text

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

# --- System prompts ---

VOTO_LIMPO_SYSTEM_PROMPT = """Você é um analista político especializado em transparência pública brasileira.

Analise a notícia fornecida e extraia informações estruturadas sobre:
1. POLÍTICOS mencionados (nome completo, partido, UF, cargo, papel na notícia)
2. ENTIDADES relacionadas (empresas, organizações, lobbies, ONGs)
3. RELACIONAMENTOS entre políticos e entidades (tipo: business/political/family/legal/financial)
4. MARCOS JURÍDICOS (inquérito, denúncia, condenação, absolvição, prisão, impeachment, delação, multa)
5. RESUMO da notícia (2-3 frases, factual, sem opinião)
6. SEVERIDADE (low/medium/high/critical baseado no impacto institucional)
7. SCORE DE VERACIDADE com 6 sub-scores:
   - source_reputation (0-1): reputação da fonte
   - multi_source_count (int): quantas fontes independentes cobrem o mesmo fato
   - narrative_consistency (0-1): consistência da narrativa
   - documental_evidence (0-1): presença de documentos/provas citados
   - temporality_score (0-1): proximidade temporal dos fatos reportados
   - emotional_language (0-1): nível de linguagem emocional (1=factual, 0=sensacionalista)
8. PALAVRAS-CHAVE (tags relevantes para busca)
9. CATEGORIAS (corrupção, lavagem, nepotismo, desvio, fraude, improbidade, peculato, etc.)

Responda EXCLUSIVAMENTE em JSON válido seguindo o schema fornecido.
Mantenha nomes de políticos exatamente como aparecem na notícia.
Se um dado não estiver disponível, use null — NUNCA invente."""

VOTO_LIMPO_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "title",
        "summary",
        "severity",
        "veracity",
        "politicians",
        "keywords",
        "categories",
    ],
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "veracity": {
            "type": "object",
            "required": [
                "score",
                "source_reputation",
                "narrative_consistency",
                "documental_evidence",
                "temporality_score",
                "emotional_language",
            ],
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "source_reputation": {"type": "number", "minimum": 0, "maximum": 1},
                "multi_source_count": {"type": "integer", "minimum": 0},
                "narrative_consistency": {"type": "number", "minimum": 0, "maximum": 1},
                "documental_evidence": {"type": "number", "minimum": 0, "maximum": 1},
                "temporality_score": {"type": "number", "minimum": 0, "maximum": 1},
                "emotional_language": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "politicians": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "role_in_article"],
                "properties": {
                    "name": {"type": "string"},
                    "party": {"type": ["string", "null"]},
                    "state": {"type": ["string", "null"]},
                    "political_role": {"type": ["string", "null"]},
                    "role_in_article": {
                        "type": "string",
                        "enum": ["subject", "mentioned", "related"],
                    },
                },
            },
        },
        "entities": {"type": "array", "items": {"type": "object"}},
        "relationships": {"type": "array", "items": {"type": "object"}},
        "milestones": {"type": "array", "items": {"type": "object"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "categories": {"type": "array", "items": {"type": "string"}},
    },
}

HELPCORE_INVENTORY_PROMPT = """Você é um especialista em gestão de conhecimento corporativo.
Analise o artigo fornecido e classifique-o segundo: tipo (procedimento/passo-a-passo/checklist/FAQ/referência),
categoria temática, público-alvo (operador/cliente/técnico), qualidade textual (0-100),
completude (campos obrigatórios presentes), e metadados extraídos. Responda em JSON."""

HELPCORE_DEDUP_PROMPT = """Você é um analista de conteúdo. Dado um artigo e seus artigos similares detectados
pelo sistema, analise: (1) são duplicatas exatas? (2) são complementares? (3) há conflitos de informação?
Proponha ação: MERGE, KEEP_BOTH, ARCHIVE_ONE, FLAG_CONFLICT. Justifique e gere versão consolidada se MERGE.
Responda em JSON."""

HELPCORE_REWRITE_PROMPT = """Você é um redator técnico especializado em bases de conhecimento corporativo.
Reescreva o artigo fornecido seguindo estas regras: linguagem clara e direta, tom profissional sem jargão
desnecessário, formato de passo-a-passo quando aplicável, seções obrigatórias (Contexto, Procedimento,
Observações, Links Relacionados), título padronizado. Mantenha 100% do conteúdo — não resuma, não omita.
Retorne o artigo reescrito + diff de mudanças + score de aderência ao padrão. Responda em JSON."""

HELPCORE_QUALITY_PROMPT = """Você é um auditor de qualidade de base de conhecimento. Avalie o artigo nos
critérios: clareza (0-100), completude (0-100), consistência com padrão (0-100), recência (baseado em data
de revisão), acessibilidade (links válidos, imagens legíveis). Calcule score final ponderado. Gere alertas
para: conteúdo expirado, links quebrados, score abaixo de 60, informações potencialmente desatualizadas.
Responda em JSON."""

# --- INSERT SQL (SQLAlchemy text() with named params) ---
INSERT = text("""
INSERT INTO processing_engine.pipelines (
    name, description, ingestor_type, max_content_chars,
    dedup_strategy, dedup_threshold,
    llm_provider, llm_model, llm_temperature, llm_seed, llm_max_tokens,
    system_prompt, output_schema, validators, sink_type, sink_config,
    max_concurrent, rate_limit_rpm, budget_limit_usd, budget_period,
    max_retries, retry_backoff_base, cache_ttl_hours
) VALUES (
    :name, :description, :ingestor_type, :max_content_chars,
    :dedup_strategy, :dedup_threshold,
    :llm_provider, :llm_model, :llm_temperature, :llm_seed, :llm_max_tokens,
    :system_prompt, CAST(:output_schema AS jsonb), CAST(:validators AS text[]), :sink_type, CAST(:sink_config AS jsonb),
    :max_concurrent, :rate_limit_rpm, :budget_limit_usd, :budget_period,
    :max_retries, :retry_backoff_base, :cache_ttl_hours
)
""")


def upgrade():
    conn = op.get_bind()

    _KEYS = [
        "name",
        "description",
        "ingestor_type",
        "max_content_chars",
        "dedup_strategy",
        "dedup_threshold",
        "llm_provider",
        "llm_model",
        "llm_temperature",
        "llm_seed",
        "llm_max_tokens",
        "system_prompt",
        "output_schema",
        "validators",
        "sink_type",
        "sink_config",
        "max_concurrent",
        "rate_limit_rpm",
        "budget_limit_usd",
        "budget_period",
        "max_retries",
        "retry_backoff_base",
        "cache_ttl_hours",
    ]

    pipelines = [
        # 1. Voto Limpo — News Analysis
        (
            "voto-limpo-news-analysis",
            "Análise de notícias políticas brasileiras — extrai políticos, entidades, relações, veracidade e severidade",
            "auto",
            100000,
            "hash",
            0.85,
            "openai",
            "gpt-4.1-mini",
            0.0,
            42,
            16384,
            VOTO_LIMPO_SYSTEM_PROMPT,
            json.dumps(VOTO_LIMPO_OUTPUT_SCHEMA),
            ["schema"],
            "postgresql",
            json.dumps({"table": "voto_limpo.articles", "conflict_column": "pe_item_id"}),
            5,
            60,
            50.0,
            "monthly",
            3,
            2.0,
            720,
        ),
        # 2. HELP CORE — Inventory
        (
            "helpcore-inventory",
            "Classificação e inventário de artigos da base de conhecimento",
            "auto",
            100000,
            "composite",
            0.85,
            "openai",
            "gpt-4.1-mini",
            0.0,
            42,
            8192,
            HELPCORE_INVENTORY_PROMPT,
            json.dumps({}),
            ["schema"],
            "postgresql",
            json.dumps({"table": "help_core.inventory", "conflict_column": "pe_item_id"}),
            5,
            60,
            30.0,
            "monthly",
            3,
            2.0,
            720,
        ),
        # 3. HELP CORE — Dedup
        (
            "helpcore-dedup",
            "Deduplicação semântica de artigos da base de conhecimento",
            "auto",
            100000,
            "semantic",
            0.85,
            "openai",
            "gpt-4.1-mini",
            0.0,
            42,
            8192,
            HELPCORE_DEDUP_PROMPT,
            json.dumps({}),
            ["schema"],
            "postgresql",
            json.dumps({"table": "help_core.dedup_proposals", "conflict_column": "pe_item_id"}),
            3,
            30,
            20.0,
            "monthly",
            3,
            2.0,
            720,
        ),
        # 4. HELP CORE — Rewrite
        (
            "helpcore-rewrite",
            "Reescrita assistida de artigos para padrão corporativo",
            "auto",
            100000,
            "hash",
            0.85,
            "openai",
            "gpt-4.1-mini",
            0.0,
            42,
            16384,
            HELPCORE_REWRITE_PROMPT,
            json.dumps({}),
            ["schema"],
            "postgresql",
            json.dumps({"table": "help_core.rewrites", "conflict_column": "pe_item_id"}),
            3,
            30,
            30.0,
            "monthly",
            3,
            2.0,
            720,
        ),
        # 5. HELP CORE — Quality Score
        (
            "helpcore-quality-score",
            "Scoring de confiabilidade e qualidade de artigos",
            "auto",
            100000,
            "hash",
            0.85,
            "openai",
            "gpt-4.1-mini",
            0.0,
            42,
            8192,
            HELPCORE_QUALITY_PROMPT,
            json.dumps({}),
            ["schema"],
            "postgresql",
            json.dumps({"table": "help_core.quality_scores", "conflict_column": "pe_item_id"}),
            5,
            60,
            20.0,
            "monthly",
            3,
            2.0,
            720,
        ),
    ]

    for p in pipelines:
        conn.execute(INSERT, dict(zip(_KEYS, p, strict=False)))


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
        DELETE FROM processing_engine.pipelines
        WHERE name IN (
            'voto-limpo-news-analysis',
            'helpcore-inventory',
            'helpcore-dedup',
            'helpcore-rewrite',
            'helpcore-quality-score'
        )
    """)
    )
