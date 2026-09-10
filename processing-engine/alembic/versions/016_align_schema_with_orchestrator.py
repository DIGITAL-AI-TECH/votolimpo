"""Align DB schema with orchestrator code expectations

Renames columns and table to match what app/core/orchestrator.py and
app/api/routes/jobs.py expect. Adds missing columns and enum values.

This migration is IDEMPOTENT — safe to run on a DB that already had some
of these changes applied manually.

Revision ID: 016
Revises: 015
Create Date: 2026-09-10
"""

from alembic import op

# revision identifiers, used by Alembic
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Rename table: items → job_items ───────────────────────
    # The orchestrator and routes reference "job_items" everywhere.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'processing_engine' AND table_name = 'items'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'processing_engine' AND table_name = 'job_items'
            ) THEN
                ALTER TABLE processing_engine.items RENAME TO job_items;
            END IF;
        END $$
    """)

    # ── 2. Rename columns in jobs table ──────────────────────────
    # items_total → total_items, items_completed → completed_items,
    # items_failed → failed_items
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'jobs'
                  AND column_name = 'items_total'
            ) THEN
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN items_total TO total_items;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'jobs'
                  AND column_name = 'items_completed'
            ) THEN
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN items_completed TO completed_items;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'jobs'
                  AND column_name = 'items_failed'
            ) THEN
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN items_failed TO failed_items;
            END IF;
        END $$
    """)

    # ── 3. Add missing columns to jobs ───────────────────────────
    op.execute("""
        ALTER TABLE processing_engine.jobs
            ADD COLUMN IF NOT EXISTS total_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS total_duration_ms INTEGER NOT NULL DEFAULT 0
    """)

    # pipeline_version: add default so orchestrator INSERT works without it
    op.execute("""
        ALTER TABLE processing_engine.jobs
            ALTER COLUMN pipeline_version SET DEFAULT 1
    """)

    # ── 4. Rename error_message → error in job_items ─────────────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'job_items'
                  AND column_name = 'error_message'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'job_items'
                  AND column_name = 'error'
            ) THEN
                ALTER TABLE processing_engine.job_items
                    RENAME COLUMN error_message TO error;
            END IF;
        END $$
    """)

    # ── 5. Add missing columns to job_items ──────────────────────
    op.execute("""
        ALTER TABLE processing_engine.job_items
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now(),
            ADD COLUMN IF NOT EXISTS validation_errors JSONB NOT NULL DEFAULT '[]',
            ADD COLUMN IF NOT EXISTS usage JSONB
    """)

    # ── 6. Processing logs: nullable FKs + missing columns ───────
    op.execute("""
        ALTER TABLE processing_engine.processing_logs
            ALTER COLUMN item_id DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE processing_engine.processing_logs
            ALTER COLUMN pipeline_id DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE processing_engine.processing_logs
            ADD COLUMN IF NOT EXISTS model_used TEXT,
            ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER,
            ADD COLUMN IF NOT EXISTS completion_tokens INTEGER,
            ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6)
    """)

    # ── 7. Add missing enum values ───────────────────────────────
    # job_status
    op.execute(
        "ALTER TYPE processing_engine.job_status ADD VALUE IF NOT EXISTS 'pending'"
    )
    op.execute(
        "ALTER TYPE processing_engine.job_status ADD VALUE IF NOT EXISTS 'processing'"
    )

    # log_step — orchestrator uses these step names
    op.execute("ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'llm'")
    op.execute(
        "ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'cache_hit'"
    )
    op.execute("ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'error'")
    op.execute(
        "ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'post_process'"
    )
    op.execute(
        "ALTER TYPE processing_engine.log_step ADD VALUE IF NOT EXISTS 'validation'"
    )

    # ── 8. Ensure priority column is TEXT (was INTEGER) ──────────
    op.execute("""
        DO $$
        BEGIN
            IF (
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'jobs'
                  AND column_name = 'priority'
            ) = 'integer' THEN
                ALTER TABLE processing_engine.jobs
                    ALTER COLUMN priority SET DEFAULT 'normal',
                    ALTER COLUMN priority TYPE TEXT USING
                        CASE priority
                            WHEN 0 THEN 'normal'
                            WHEN 1 THEN 'high'
                            WHEN 2 THEN 'critical'
                            WHEN -1 THEN 'low'
                            ELSE 'normal'
                        END;
            END IF;
        END $$
    """)

    # ── 9. Rename table: cache_entries → cache ─────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'processing_engine' AND table_name = 'cache_entries'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'processing_engine' AND table_name = 'cache'
            ) THEN
                ALTER TABLE processing_engine.cache_entries RENAME TO cache;
            END IF;
        END $$
    """)


def downgrade() -> None:
    # Reverse renames
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'processing_engine' AND table_name = 'job_items'
            ) THEN
                ALTER TABLE processing_engine.job_items RENAME TO items;
            END IF;
        END $$
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'processing_engine'
                  AND table_name = 'items'
                  AND column_name = 'total_items'
            ) THEN
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN total_items TO items_total;
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN completed_items TO items_completed;
                ALTER TABLE processing_engine.jobs
                    RENAME COLUMN failed_items TO items_failed;
            END IF;
        END $$
    """)
