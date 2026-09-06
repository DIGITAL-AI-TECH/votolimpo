"""Create model_pricing table and insert OpenAI seed data

Revision ID: 009
Revises: 008
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE processing_engine.model_pricing (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider        TEXT NOT NULL,
            model           TEXT NOT NULL,
            input_price_per_million_tokens  REAL NOT NULL,
            output_price_per_million_tokens REAL NOT NULL DEFAULT 0.0,
            is_active       BOOLEAN NOT NULL DEFAULT true,
            effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_model_pricing_unique ON processing_engine.model_pricing (provider, model)
            WHERE is_active = true
    """)

    # Seed with current OpenAI pricing (2026-09)
    op.execute("""
        INSERT INTO processing_engine.model_pricing
            (provider, model, input_price_per_million_tokens, output_price_per_million_tokens)
        VALUES
            ('openai', 'gpt-4.1-mini', 0.40, 1.60),
            ('openai', 'gpt-4.1', 2.00, 8.00),
            ('openai', 'gpt-4o', 2.50, 10.00),
            ('openai', 'gpt-4o-mini', 0.15, 0.60),
            ('openai', 'text-embedding-3-small', 0.02, 0.00)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS processing_engine.model_pricing CASCADE")
