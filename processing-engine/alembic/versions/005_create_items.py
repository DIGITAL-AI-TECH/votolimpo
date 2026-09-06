"""Create items table with pgvector HNSW index and hash indexes

Revision ID: 005
Revises: 004
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id          UUID NOT NULL REFERENCES processing_engine.jobs(id) ON DELETE CASCADE,
            status          processing_engine.item_status NOT NULL DEFAULT 'pending',

            -- Input
            source_url      TEXT,
            url_hash        TEXT,
            content_type    TEXT NOT NULL DEFAULT 'text/plain',
            raw_content     TEXT,
            content_hash    TEXT,
            content_embedding VECTOR(1536),

            -- Output
            output          JSONB,
            dedup_result    TEXT,
            dedup_matched_item_id UUID,

            -- Metadata
            metadata        JSONB DEFAULT '{}',
            error_message   TEXT,
            retry_count     INTEGER NOT NULL DEFAULT 0,
            cached          BOOLEAN NOT NULL DEFAULT false,
            processing_started_at TIMESTAMPTZ,
            processing_completed_at TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_items_job ON processing_engine.items (job_id)
    """)

    op.execute("""
        CREATE INDEX idx_items_url_hash ON processing_engine.items (url_hash)
            WHERE url_hash IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_items_content_hash ON processing_engine.items (content_hash)
            WHERE content_hash IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_items_status ON processing_engine.items (job_id, status)
    """)

    op.execute("""
        CREATE INDEX idx_items_embedding ON processing_engine.items
            USING hnsw (content_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.items CASCADE")
