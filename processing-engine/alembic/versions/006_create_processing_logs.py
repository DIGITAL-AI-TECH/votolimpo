"""Create processing_logs table with indexes

Revision ID: 006
Revises: 005
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.processing_logs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id         UUID NOT NULL REFERENCES processing_engine.items(id) ON DELETE CASCADE,
            job_id          UUID NOT NULL,
            pipeline_id     UUID NOT NULL,

            step            processing_engine.log_step NOT NULL,
            status          TEXT NOT NULL,
            duration_ms     INTEGER,
            error_message   TEXT,
            metadata        JSONB DEFAULT '{}',

            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_processing_logs_item ON processing_engine.processing_logs (item_id)
    """)

    op.execute("""
        CREATE INDEX idx_processing_logs_job ON processing_engine.processing_logs (job_id)
    """)

    op.execute("""
        CREATE INDEX idx_processing_logs_step ON processing_engine.processing_logs (step, status)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.processing_logs CASCADE")
