"""Create consolidated help_core schema: articles (master) + analysis_results (sink)

Consolidates inventory + quality_score + dedup_analysis into a single table
(analysis_results) fed by the unified helpcore-analysis pipeline (1 LLM call/article).
Adds articles as business-entity master table with per-pipeline status tracking.

Preserves existing tables (inventory, dedup_proposals, rewrites, quality_scores)
from migration 014 — they remain for legacy data and the separate rewrite pipeline.

Revision ID: 019
Revises: 018
Create Date: 2026-10-07
"""
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    # -------------------------------------------------------------------------
    # TABELA MASTER: articles
    # Representa o artigo como entidade de negocio.
    # source_url e a chave de negocio imutavel (bradesco-help://<AREA>/<IID>).
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS help_core.articles (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            -- Chave de negocio: imutavel, identifica o artigo na base Bradesco
            source_url              TEXT NOT NULL,

            -- Metadados do header do arquivo TXT (extraidos no script de ingestao)
            area                    TEXT,
            lista                   TEXT,
            title                   TEXT,
            subtitulo               TEXT,
            nivel3                  TEXT,
            iid                     TEXT,
            classificacao           TEXT,
            modified_at             TIMESTAMPTZ,
            source_filename         TEXT,
            links                   TEXT[],

            -- Status de processamento por pipeline
            -- Estados validos: pending | processing | processed | error | skipped
            inventory_status        TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (inventory_status IN ('pending','processing','processed','error','skipped')),
            dedup_status            TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (dedup_status IN ('pending','processing','processed','error','skipped')),
            quality_status          TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (quality_status IN ('pending','processing','processed','error','skipped')),
            rewrite_status          TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (rewrite_status IN ('pending','processing','processed','error','skipped')),
            analysis_status         TEXT NOT NULL DEFAULT 'pending'
                                    CHECK (analysis_status IN ('pending','processing','processed','error','skipped')),

            -- FKs para o ultimo pe_item_id processado por pipeline (nullable)
            inventory_pe_item_id    UUID,
            dedup_pe_item_id        UUID,
            quality_pe_item_id      UUID,
            rewrite_pe_item_id      UUID,
            analysis_pe_item_id     UUID,

            -- Versionamento de prompts por pipeline
            pipeline_versions       JSONB NOT NULL DEFAULT '{}',

            -- Controle de consumo acumulado (soma de todos os pipelines)
            total_prompt_tokens     INTEGER NOT NULL DEFAULT 0,
            total_completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost_usd          NUMERIC(10,6) NOT NULL DEFAULT 0,

            -- Contagem de falhas
            error_count             INTEGER NOT NULL DEFAULT 0,
            last_error              TEXT,

            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT articles_source_url_unique UNIQUE (source_url)
        );
    """)

    # Indexes para articles
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_articles_area ON help_core.articles (area);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_articles_analysis_status ON help_core.articles (analysis_status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_articles_rewrite_status ON help_core.articles (rewrite_status);")

    # -------------------------------------------------------------------------
    # TABELA: analysis_results
    # Destino do pipeline consolidado helpcore-analysis.
    # 1 chamada LLM = 1 row com inventory + quality + dedup_analysis.
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS help_core.analysis_results (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            -- Chave tecnica do PE (upsert target)
            pe_item_id                  UUID NOT NULL,

            -- FK para tabela master
            article_id                  UUID REFERENCES help_core.articles(id) ON DELETE SET NULL,

            -- source_url desnormalizada (evita JOIN para queries simples)
            source_url                  TEXT,

            -- === INVENTORY ===
            doc_type                    TEXT
                                        CHECK (doc_type IN ('procedimento','passo_a_passo','checklist',
                                                            'faq','referencia','politica','outro')),
            category                    TEXT,
            subcategory                 TEXT,
            target_audience             TEXT
                                        CHECK (target_audience IN ('operador','supervisor','tecnico',
                                                                   'cliente','multiplo')),
            inv_quality_score           NUMERIC(5,2) CHECK (inv_quality_score BETWEEN 0 AND 100),
            completeness_score          NUMERIC(5,2) CHECK (completeness_score BETWEEN 0 AND 100),
            key_topics                  TEXT[],
            summary                     TEXT,
            requires_update             BOOLEAN NOT NULL DEFAULT false,
            has_mandatory_fields        BOOLEAN,
            mandatory_fields_missing    TEXT[],
            estimated_word_count        INTEGER,
            language_issues             TEXT[],
            classification_confidence   NUMERIC(3,2) CHECK (classification_confidence BETWEEN 0 AND 1),

            -- === QUALITY ===
            clarity                     NUMERIC(5,2) CHECK (clarity BETWEEN 0 AND 100),
            structure                   NUMERIC(5,2) CHECK (structure BETWEEN 0 AND 100),
            quality_completeness        NUMERIC(5,2) CHECK (quality_completeness BETWEEN 0 AND 100),
            accuracy_signals            NUMERIC(5,2) CHECK (accuracy_signals BETWEEN 0 AND 100),
            readability                 NUMERIC(5,2) CHECK (readability BETWEEN 0 AND 100),
            overall_score               NUMERIC(5,2) CHECK (overall_score BETWEEN 0 AND 100),
            improvement_suggestions     TEXT[],
            priority_level              TEXT CHECK (priority_level IN ('critical','high','medium','low')),
            estimated_effort            TEXT CHECK (estimated_effort IN ('minor','moderate','major','rewrite')),
            actionable_items            JSONB,

            -- === DEDUP ANALYSIS (intra-artigo) ===
            has_internal_conflicts      BOOLEAN NOT NULL DEFAULT false,
            internal_conflict_details   TEXT,
            content_genericness         TEXT,

            -- === RASTREABILIDADE ===
            prompt_version              TEXT,
            prompt_tokens               INTEGER,
            completion_tokens           INTEGER,
            cost_usd                    NUMERIC(10,6),
            metadata                    JSONB NOT NULL DEFAULT '{}',

            processed_at                TIMESTAMPTZ,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT analysis_results_pe_item_id_unique UNIQUE (pe_item_id)
        );
    """)

    # Indexes para analysis_results
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_analysis_doc_type ON help_core.analysis_results (doc_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_analysis_category ON help_core.analysis_results (category);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_analysis_overall ON help_core.analysis_results (overall_score DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_analysis_priority ON help_core.analysis_results (priority_level);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hc_analysis_source_url ON help_core.analysis_results (source_url);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS help_core.analysis_results;")
    op.execute("DROP TABLE IF EXISTS help_core.articles;")
