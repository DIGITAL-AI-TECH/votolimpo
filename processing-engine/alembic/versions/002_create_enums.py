"""Create all ENUMs in processing_engine schema

Revision ID: 002
Revises: 001
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE processing_engine.job_status AS ENUM (
            'queued', 'running', 'completed', 'failed', 'partial', 'cancelled'
        )
    """)

    op.execute("""
        CREATE TYPE processing_engine.item_status AS ENUM (
            'pending', 'ingesting', 'deduplicating', 'processing', 'validating',
            'persisting', 'completed', 'failed', 'duplicate', 'similar'
        )
    """)

    op.execute("""
        CREATE TYPE processing_engine.log_step AS ENUM (
            'ingest', 'dedup', 'process', 'validate', 'persist'
        )
    """)

    op.execute("""
        CREATE TYPE processing_engine.dedup_strategy AS ENUM (
            'hash', 'semantic', 'composite', 'none'
        )
    """)

    op.execute("""
        CREATE TYPE processing_engine.call_status AS ENUM (
            'success', 'error'
        )
    """)


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS processing_engine.call_status")
    op.execute("DROP TYPE IF EXISTS processing_engine.dedup_strategy")
    op.execute("DROP TYPE IF EXISTS processing_engine.log_step")
    op.execute("DROP TYPE IF EXISTS processing_engine.item_status")
    op.execute("DROP TYPE IF EXISTS processing_engine.job_status")
