"""Create help_core schema for knowledge base treatment pipelines

Schema for HELP CORE (Bradesco/Ello) — stores inventory, dedup proposals,
rewrites and quality scores produced by the Processing Engine's
helpcore-* pipelines.

Revision ID: 014
Revises: 013
Create Date: 2026-09-08
"""
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS help_core;")

    op.execute("""
        CREATE TABLE help_core.inventory (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_url TEXT,
            title TEXT,
            content TEXT,
            content_type VARCHAR(50),
            doc_type VARCHAR(50),
            category TEXT,
            target_audience VARCHAR(50),
            quality_score NUMERIC(5,2),
            completeness_score NUMERIC(5,2),
            metadata JSONB,
            pe_item_id UUID,
            processed_at TIMESTAMPTZ DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE help_core.dedup_proposals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            article_a_id UUID,
            article_b_id UUID,
            similarity NUMERIC(3,2),
            action VARCHAR(20),
            justification TEXT,
            consolidated_version TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            pe_item_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE help_core.rewrites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            original_id UUID,
            original_content TEXT,
            rewritten_content TEXT,
            diff_summary TEXT,
            adherence_score NUMERIC(5,2),
            template_used VARCHAR(50),
            status VARCHAR(20) DEFAULT 'draft',
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            pe_item_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE help_core.quality_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            article_id UUID,
            clarity_score NUMERIC(5,2),
            completeness_score NUMERIC(5,2),
            consistency_score NUMERIC(5,2),
            recency_score NUMERIC(5,2),
            accessibility_score NUMERIC(5,2),
            overall_score NUMERIC(5,2),
            alerts JSONB,
            pe_item_id UUID,
            scored_at TIMESTAMPTZ DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Indexes
    op.execute("CREATE INDEX idx_hc_inventory_doc_type ON help_core.inventory (doc_type);")
    op.execute("CREATE INDEX idx_hc_inventory_category ON help_core.inventory (category);")
    op.execute("CREATE INDEX idx_hc_dedup_status ON help_core.dedup_proposals (status);")
    op.execute("CREATE INDEX idx_hc_rewrites_status ON help_core.rewrites (status);")
    op.execute("CREATE INDEX idx_hc_quality_overall ON help_core.quality_scores (overall_score DESC);")


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS help_core CASCADE;")
