"""Create cache_entries table with unique hash+pipeline index

Revision ID: 007
Revises: 006
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.cache_entries (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content_hash    TEXT NOT NULL,
            pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),
            output          JSONB NOT NULL,

            -- Usage tracking
            prompt_tokens   INTEGER,
            completion_tokens INTEGER,
            cost_usd        REAL,
            llm_model       TEXT,

            hit_count       INTEGER NOT NULL DEFAULT 0,
            expires_at      TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_cache_hash_pipeline ON processing_engine.cache_entries (content_hash, pipeline_id)
    """)

    op.execute("""
        CREATE INDEX idx_cache_expires ON processing_engine.cache_entries (expires_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.cache_entries CASCADE")
