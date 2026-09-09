"""Create processing_engine schema and pgvector extension

Revision ID: 001
Revises: None
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS processing_engine")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS processing_engine CASCADE")
