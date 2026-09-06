"""Create pipelines table with all columns and indexes

Revision ID: 003
Revises: 002
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.pipelines (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name            TEXT NOT NULL UNIQUE,
            version         INTEGER NOT NULL DEFAULT 1,
            description     TEXT,

            -- Ingestor config
            ingestor_type   TEXT NOT NULL DEFAULT 'auto',
            max_content_chars INTEGER DEFAULT 100000,

            -- Dedup config
            dedup_strategy  processing_engine.dedup_strategy NOT NULL DEFAULT 'hash',
            dedup_threshold REAL DEFAULT 0.90,

            -- LLM config
            llm_provider    TEXT NOT NULL DEFAULT 'openai',
            llm_model       TEXT NOT NULL DEFAULT 'gpt-4.1-mini',
            llm_temperature REAL NOT NULL DEFAULT 0.0,
            llm_seed        INTEGER DEFAULT 42,
            llm_max_tokens  INTEGER DEFAULT 16384,
            system_prompt   TEXT NOT NULL,
            output_schema   JSONB NOT NULL,

            -- Validators
            validators      TEXT[] NOT NULL DEFAULT '{"schema"}',

            -- Sink config
            sink_type       TEXT NOT NULL DEFAULT 'postgresql',
            sink_config     JSONB DEFAULT '{}',

            -- Rate limiting
            max_concurrent  INTEGER NOT NULL DEFAULT 5,
            rate_limit_rpm  INTEGER DEFAULT 60,

            -- Budget
            budget_limit_usd REAL,
            budget_period    TEXT DEFAULT 'month',

            -- Retry config
            max_retries     INTEGER NOT NULL DEFAULT 3,
            retry_backoff_base REAL NOT NULL DEFAULT 2.0,

            -- Cache
            cache_ttl_hours INTEGER NOT NULL DEFAULT 720,

            -- Metadata
            is_active       BOOLEAN NOT NULL DEFAULT true,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX idx_pipelines_name ON processing_engine.pipelines (name)
    """)

    op.execute("""
        CREATE INDEX idx_pipelines_active ON processing_engine.pipelines (is_active)
            WHERE is_active = true
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.pipelines CASCADE")
