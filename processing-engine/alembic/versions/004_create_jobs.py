"""Create jobs table with idempotency unique index and SKIP LOCKED partial index

Revision ID: 004
Revises: 003
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.jobs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),
            pipeline_version INTEGER NOT NULL,
            idempotency_key TEXT,
            status          processing_engine.job_status NOT NULL DEFAULT 'queued',
            priority        INTEGER NOT NULL DEFAULT 0,

            -- Counters
            items_total     INTEGER NOT NULL DEFAULT 0,
            items_completed INTEGER NOT NULL DEFAULT 0,
            items_failed    INTEGER NOT NULL DEFAULT 0,

            -- Overrides
            override_model  TEXT,
            skip_dedup      BOOLEAN NOT NULL DEFAULT false,
            skip_cache      BOOLEAN NOT NULL DEFAULT false,
            dry_run         BOOLEAN NOT NULL DEFAULT false,

            -- Callback
            callback_url    TEXT,

            -- Metadata
            metadata        JSONB DEFAULT '{}',
            error_message   TEXT,
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_jobs_idempotency ON processing_engine.jobs (idempotency_key)
            WHERE idempotency_key IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_jobs_status_priority ON processing_engine.jobs (status, priority DESC, created_at)
            WHERE status = 'queued'
    """)

    op.execute("""
        CREATE INDEX idx_jobs_pipeline ON processing_engine.jobs (pipeline_id)
    """)

    op.execute("""
        CREATE INDEX idx_jobs_created ON processing_engine.jobs (created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.jobs CASCADE")
