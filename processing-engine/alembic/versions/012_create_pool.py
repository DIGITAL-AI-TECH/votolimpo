"""Create pool table for decoupled ingestion with indexes

Pool is the ingestion buffer — N collectors deposit raw data via REST API,
the Auto-Batcher consumes pending items and creates jobs automatically.

Revision ID: 012
Revises: 011
Create Date: 2026-09-07
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.pool (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id     UUID NOT NULL REFERENCES processing_engine.pipelines(id),

            -- Raw content (at least content OR source_url required, validated at API level)
            source_url      TEXT,
            content         TEXT,
            content_type    TEXT NOT NULL DEFAULT 'text/plain',
            metadata        JSONB DEFAULT '{}',

            -- Hashes for fast dedup
            url_hash        TEXT,
            content_hash    TEXT,

            -- State control
            status          TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'claimed', 'duplicate_rejected', 'error')),
            priority        INTEGER NOT NULL DEFAULT 0,

            -- Collector traceability
            source_id       TEXT,
            batch_ref       TEXT,

            -- Job reference (filled by Auto-Batcher)
            job_id          UUID REFERENCES processing_engine.jobs(id),

            -- Timestamps
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            claimed_at      TIMESTAMPTZ
        )
    """)

    # Auto-Batcher: fetch pending items per pipeline (SKIP LOCKED)
    op.execute("""
        CREATE INDEX idx_pool_pending
            ON processing_engine.pool (pipeline_id, priority DESC, created_at ASC)
            WHERE status = 'pending'
    """)

    # Fast URL dedup at ingestion
    op.execute("""
        CREATE INDEX idx_pool_url_hash
            ON processing_engine.pool (url_hash, pipeline_id)
            WHERE url_hash IS NOT NULL AND status != 'duplicate_rejected'
    """)

    # Content hash dedup (complementary)
    op.execute("""
        CREATE INDEX idx_pool_content_hash
            ON processing_engine.pool (content_hash, pipeline_id)
            WHERE content_hash IS NOT NULL AND status != 'duplicate_rejected'
    """)

    # Tracing by collector
    op.execute("""
        CREATE INDEX idx_pool_source
            ON processing_engine.pool (source_id, created_at DESC)
            WHERE source_id IS NOT NULL
    """)

    # Lookup by job_id (join with jobs table)
    op.execute("""
        CREATE INDEX idx_pool_job_id
            ON processing_engine.pool (job_id)
            WHERE job_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.pool CASCADE")
