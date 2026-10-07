"""Add steps TEXT[] column to help_core.analysis_results

The steps field stores procedural checklist items extracted by the LLM
from each article. Essential for the copilot attendance interface
(weight 15pts in UI quality score).

Revision ID: 020
Revises: 019
Create Date: 2026-10-07
"""
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE help_core.analysis_results
        ADD COLUMN IF NOT EXISTS steps TEXT[]
        DEFAULT '{}'::TEXT[];
    """)

    op.execute("""
        COMMENT ON COLUMN help_core.analysis_results.steps IS
        'Passos do procedimento extraidos pelo LLM. Array vazio se artigo nao e procedimento.';
    """)


def downgrade():
    op.execute("""
        ALTER TABLE help_core.analysis_results
        DROP COLUMN IF EXISTS steps;
    """)
