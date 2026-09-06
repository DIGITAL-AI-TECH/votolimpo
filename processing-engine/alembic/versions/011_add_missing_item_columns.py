"""Add missing columns to items table and cache to log_step enum

Items table was missing: pipeline_id, content (aliased from raw_content),
prompt_tokens, completion_tokens, total_tokens, cost_usd, duration_ms.
Also adds 'cache' value to log_step enum for cache hit/miss logging.

Revision ID: 011
Revises: 010
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to items table
    op.execute("""
        ALTER TABLE processing_engine.items
            ADD COLUMN IF NOT EXISTS pipeline_id UUID REFERENCES processing_engine.pipelines(id),
            ADD COLUMN IF NOT EXISTS content TEXT,
            ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS completion_tokens INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_tokens INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS duration_ms INTEGER NOT NULL DEFAULT 0
    """)

    # Backfill pipeline_id from jobs table
    op.execute("""
        UPDATE processing_engine.items i
        SET pipeline_id = j.pipeline_id
        FROM processing_engine.jobs j
        WHERE i.job_id = j.id AND i.pipeline_id IS NULL
    """)

    # Backfill content from raw_content
    op.execute("""
        UPDATE processing_engine.items
        SET content = raw_content
        WHERE content IS NULL AND raw_content IS NOT NULL
    """)

    # Index for pipeline_id lookups (dedup, stats)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_items_pipeline
        ON processing_engine.items (pipeline_id)
        WHERE pipeline_id IS NOT NULL
    """)

    # Add 'cache' to log_step enum
    op.execute("""
        ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'cache'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE processing_engine.items
            DROP COLUMN IF EXISTS pipeline_id,
            DROP COLUMN IF EXISTS content,
            DROP COLUMN IF EXISTS prompt_tokens,
            DROP COLUMN IF EXISTS completion_tokens,
            DROP COLUMN IF EXISTS total_tokens,
            DROP COLUMN IF EXISTS cost_usd,
            DROP COLUMN IF EXISTS duration_ms
    """)
    # Cannot remove enum values in PostgreSQL without recreating the type
