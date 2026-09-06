"""Create llm_call_log table with budget partial index

Revision ID: 008
Revises: 007
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.llm_call_log (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            item_id         UUID REFERENCES processing_engine.items(id) ON DELETE SET NULL,
            job_id          UUID,
            pipeline_id     UUID NOT NULL,

            -- Call details
            provider        TEXT NOT NULL,
            model           TEXT NOT NULL,
            call_type       TEXT NOT NULL DEFAULT 'completion',
            prompt_tokens   INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens    INTEGER NOT NULL DEFAULT 0,

            -- Cost
            cost_usd        REAL NOT NULL DEFAULT 0.0,

            -- Performance
            latency_ms      INTEGER,
            status          processing_engine.call_status NOT NULL,
            error_message   TEXT,
            is_retry        BOOLEAN NOT NULL DEFAULT false,
            retry_number    INTEGER NOT NULL DEFAULT 0,

            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_pipeline ON processing_engine.llm_call_log (pipeline_id, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_job ON processing_engine.llm_call_log (job_id)
            WHERE job_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_item ON processing_engine.llm_call_log (item_id)
            WHERE item_id IS NOT NULL
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_model ON processing_engine.llm_call_log (model, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_created ON processing_engine.llm_call_log (created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_llm_call_budget ON processing_engine.llm_call_log (pipeline_id, cost_usd, created_at)
            WHERE status = 'success'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.llm_call_log CASCADE")
