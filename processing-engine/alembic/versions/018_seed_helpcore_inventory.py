"""Seed helpcore-inventory pipeline (was missing from production DB)

Migration 015 ran before helpcore pipelines were added to the code.
This migration ensures the helpcore-inventory pipeline exists in the DB.

Revision ID: 018
Revises: 017
Create Date: 2026-10-04
"""

import json

from sqlalchemy import text

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

SYSTEM_PROMPT = """Voce e um especialista em gestao de conhecimento corporativo do setor bancario brasileiro.
Analise o artigo da base de conhecimento do Bradesco e extraia informacoes estruturadas.

Classifique o artigo segundo:
- doc_type: tipo do documento (procedimento, passo_a_passo, checklist, faq, referencia, politica, outro)
- category: categoria tematica (ex: cancelamento, bloqueio, credito, fraude, cadastro, contestacao, cartao, pix, transferencia, emprestimo, investimento, seguro, conta, atendimento, outro)
- target_audience: publico-alvo principal (operador, supervisor, tecnico, cliente, multiplo)
- quality_score: qualidade textual de 0-100 (clareza, organizacao, linguagem profissional)
- completeness_score: completude de 0-100 (passos claros, informacoes completas, sem lacunas)
- key_topics: lista de 3-8 topicos principais do artigo
- summary: resumo factual de 1-2 frases do procedimento/conteudo
- requires_update: true se houver indicios de conteudo desatualizado (datas antigas, sistemas obsoletos, referencias quebradas)

REGRAS:
- Se o artigo for apenas um link sem conteudo textual, retorne doc_type="referencia", quality_score=10, completeness_score=5
- Se o artigo for muito curto (menos de 50 palavras), ajuste quality_score proporcionalmente
- Responda EXCLUSIVAMENTE com JSON valido no formato do schema"""

OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "doc_type", "category", "target_audience", "quality_score",
        "completeness_score", "key_topics", "summary", "requires_update",
    ],
    "additionalProperties": False,
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": ["procedimento", "passo_a_passo", "checklist", "faq", "referencia", "politica", "outro"],
        },
        "category": {"type": "string"},
        "target_audience": {
            "type": "string",
            "enum": ["operador", "supervisor", "tecnico", "cliente", "multiplo"],
        },
        "quality_score": {"type": "number", "minimum": 0, "maximum": 100},
        "completeness_score": {"type": "number", "minimum": 0, "maximum": 100},
        "key_topics": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "requires_update": {"type": "boolean"},
    },
}

SINK_CONFIG = {
    "database_url_env": "VOTOLIMPO_DATABASE_URL",
    "table": "help_core.inventory",
    "conflict_column": "pe_item_id",
    "column_mapping": {
        "doc_type": "doc_type",
        "category": "category",
        "target_audience": "target_audience",
        "quality_score": "quality_score",
        "completeness_score": "completeness_score",
    },
    "item_field_mapping": {
        "source_url": "source_url",
        "title": "title",
    },
    "jsonb_fallback": "metadata",
}


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
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
            :system_prompt, CAST(:output_schema AS jsonb), CAST(:validators AS text[]),
            :sink_type, CAST(:sink_config AS jsonb),
            :max_concurrent, :rate_limit_rpm, :budget_limit_usd, :budget_period,
            :max_retries, :retry_backoff_base, :cache_ttl_hours
        )
        ON CONFLICT (name) DO NOTHING
        """),
        {
            "name": "helpcore-inventory",
            "description": "Classificacao e inventario de artigos da base de conhecimento Help Bradesco",
            "ingestor_type": "auto",
            "max_content_chars": 100000,
            "dedup_strategy": "hash",
            "dedup_threshold": 0.85,
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
            "llm_temperature": 0.0,
            "llm_seed": 42,
            "llm_max_tokens": 8192,
            "system_prompt": SYSTEM_PROMPT,
            "output_schema": json.dumps(OUTPUT_SCHEMA),
            "validators": ["schema"],
            "sink_type": "postgresql",
            "sink_config": json.dumps(SINK_CONFIG),
            "max_concurrent": 5,
            "rate_limit_rpm": 60,
            "budget_limit_usd": 100.0,
            "budget_period": "month",
            "max_retries": 2,
            "retry_backoff_base": 2.0,
            "cache_ttl_hours": 720,
        },
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM processing_engine.pipelines WHERE name = 'helpcore-inventory'")
    )
