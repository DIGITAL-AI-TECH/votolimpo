"""Ensure votolimpo schema exists (tables created by News Collector migrations)

The votolimpo schema tables are created and owned by the News Collector
(NC) migrations (002_create_tables.sql + 009_articles_add_sink_columns.sql).
The PE only needs the schema and pg_trgm extension to exist.

This migration was originally a full CREATE TABLE set with an incompatible
schema (UUID PKs, different column names). It has been neutralized to avoid
conflicts with the NC-owned tables that are already in production.

Revision ID: 013
Revises: 012
Create Date: 2026-09-08
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure prerequisites exist (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE SCHEMA IF NOT EXISTS votolimpo;")

    # All votolimpo tables (politicians, articles, entities, relationships,
    # milestones, article_matches, score_history, news_clusters, etc.) are
    # created by the News Collector migrations. The PE writes to these tables
    # via post-processors and crons but does NOT own the DDL.
    #
    # See: news-collector/migrations/002_create_tables.sql (16 tables)
    #      news-collector/migrations/009_articles_add_sink_columns.sql (ALTERs)


def downgrade():
    # Do NOT drop the votolimpo schema — it is owned by News Collector.
    # Dropping it here would destroy production data.
    pass
