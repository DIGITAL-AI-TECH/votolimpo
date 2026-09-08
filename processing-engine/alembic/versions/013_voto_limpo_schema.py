"""Create voto_limpo schema with all tables, views and indexes

Schema for the Voto Limpo transparency platform — stores politicians,
articles, entities, relationships, milestones and match data extracted
by the Processing Engine's voto-limpo-news-analysis pipeline.

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
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # --- Schema ---
    op.execute("CREATE SCHEMA IF NOT EXISTS voto_limpo;")

    # --- ENUMs ---
    op.execute("""
        CREATE TYPE voto_limpo.severity_level AS ENUM ('low', 'medium', 'high', 'critical');
    """)
    op.execute("""
        CREATE TYPE voto_limpo.article_role AS ENUM ('subject', 'mentioned', 'related');
    """)
    op.execute("""
        CREATE TYPE voto_limpo.entity_type AS ENUM ('company', 'organization', 'lobby', 'ngo');
    """)
    op.execute("""
        CREATE TYPE voto_limpo.relationship_type AS ENUM ('business', 'political', 'family', 'legal', 'financial');
    """)
    op.execute("""
        CREATE TYPE voto_limpo.milestone_type AS ENUM (
            'inquiry', 'complaint', 'conviction', 'acquittal',
            'arrest', 'impeachment', 'plea_deal', 'fine'
        );
    """)
    op.execute("""
        CREATE TYPE voto_limpo.match_type AS ENUM ('content', 'entity', 'temporal');
    """)

    # --- Tables ---
    op.execute("""
        CREATE TABLE voto_limpo.parties (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            abbreviation VARCHAR(20) UNIQUE NOT NULL,
            logo_url TEXT,
            color VARCHAR(7),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.politicians (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug VARCHAR(200) UNIQUE NOT NULL,
            name TEXT NOT NULL,
            party_id UUID REFERENCES voto_limpo.parties(id),
            state VARCHAR(2),
            role TEXT,
            photo_url TEXT,
            score NUMERIC(5,2) DEFAULT 0,
            total_news INT DEFAULT 0,
            severity_max VARCHAR(10),
            first_news_at TIMESTAMPTZ,
            last_news_at TIMESTAMPTZ,
            bio TEXT,
            ai_summary TEXT,
            tse_id VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            domain VARCHAR(255) UNIQUE NOT NULL,
            reputation NUMERIC(3,2),
            category VARCHAR(50),
            logo_url TEXT,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.articles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title TEXT NOT NULL,
            summary TEXT,
            original_url TEXT,
            source_id UUID REFERENCES voto_limpo.sources(id),
            published_at TIMESTAMPTZ,
            collected_at TIMESTAMPTZ DEFAULT now(),
            veracity_score NUMERIC(3,2),
            severity voto_limpo.severity_level,
            raw_content TEXT,
            ai_processed BOOLEAN DEFAULT false,
            source_reputation NUMERIC(3,2),
            multi_source_count INT,
            narrative_consistency NUMERIC(3,2),
            documental_evidence NUMERIC(3,2),
            temporality_score NUMERIC(3,2),
            emotional_language NUMERIC(3,2),
            pe_item_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.politician_articles (
            politician_id UUID NOT NULL REFERENCES voto_limpo.politicians(id),
            article_id UUID NOT NULL REFERENCES voto_limpo.articles(id),
            role voto_limpo.article_role DEFAULT 'mentioned',
            PRIMARY KEY (politician_id, article_id)
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.entities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            entity_type voto_limpo.entity_type NOT NULL,
            description TEXT,
            score NUMERIC(5,2),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.relationships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_type VARCHAR(20) NOT NULL,
            source_id UUID NOT NULL,
            target_type VARCHAR(20) NOT NULL,
            target_id UUID NOT NULL,
            relationship_type voto_limpo.relationship_type NOT NULL,
            weight INT DEFAULT 1,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.relationship_evidence (
            relationship_id UUID NOT NULL REFERENCES voto_limpo.relationships(id),
            article_id UUID NOT NULL REFERENCES voto_limpo.articles(id),
            PRIMARY KEY (relationship_id, article_id)
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.milestones (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            politician_id UUID NOT NULL REFERENCES voto_limpo.politicians(id),
            title TEXT NOT NULL,
            description TEXT,
            milestone_type voto_limpo.milestone_type NOT NULL,
            occurred_at DATE,
            source_url TEXT,
            article_id UUID REFERENCES voto_limpo.articles(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE voto_limpo.article_matches (
            article_a_id UUID NOT NULL REFERENCES voto_limpo.articles(id),
            article_b_id UUID NOT NULL REFERENCES voto_limpo.articles(id),
            similarity NUMERIC(3,2),
            match_type voto_limpo.match_type,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (article_a_id, article_b_id),
            CHECK (article_a_id < article_b_id)
        );
    """)

    # --- Views ---
    op.execute("""
        CREATE OR REPLACE VIEW voto_limpo.v_politician_ranking AS
        SELECT
            p.*,
            pa.abbreviation AS party_name,
            pa.color AS party_color,
            RANK() OVER (ORDER BY p.score DESC) AS position
        FROM voto_limpo.politicians p
        LEFT JOIN voto_limpo.parties pa ON p.party_id = pa.id;
    """)

    op.execute("""
        CREATE OR REPLACE VIEW voto_limpo.v_politician_timeline AS
        SELECT
            politician_id,
            a.id AS event_id,
            'article' AS event_type,
            a.title,
            a.summary AS description,
            a.published_at AS event_date,
            a.severity::text AS severity,
            a.veracity_score
        FROM voto_limpo.politician_articles pa
        JOIN voto_limpo.articles a ON a.id = pa.article_id
        UNION ALL
        SELECT
            politician_id,
            m.id AS event_id,
            'milestone' AS event_type,
            m.title,
            m.description,
            m.occurred_at::timestamptz AS event_date,
            m.milestone_type::text AS severity,
            NULL AS veracity_score
        FROM voto_limpo.milestones m
        ORDER BY event_date DESC NULLS LAST;
    """)

    op.execute("""
        CREATE OR REPLACE VIEW voto_limpo.v_graph_nodes AS
        SELECT
            id, 'politician' AS node_type, name, slug,
            score, NULL::voto_limpo.entity_type AS entity_type
        FROM voto_limpo.politicians
        UNION ALL
        SELECT
            id, 'entity' AS node_type, name, NULL AS slug,
            score, entity_type
        FROM voto_limpo.entities;
    """)

    # --- Indexes ---
    op.execute("CREATE INDEX idx_vl_politicians_score ON voto_limpo.politicians (score DESC);")
    op.execute("CREATE INDEX idx_vl_politicians_slug ON voto_limpo.politicians (slug);")
    op.execute("CREATE INDEX idx_vl_articles_published ON voto_limpo.articles (published_at DESC);")
    op.execute("CREATE INDEX idx_vl_articles_source ON voto_limpo.articles (source_id);")
    op.execute("CREATE INDEX idx_vl_milestones_politician ON voto_limpo.milestones (politician_id);")
    op.execute("CREATE INDEX idx_vl_relationships_source ON voto_limpo.relationships (source_id);")
    op.execute("CREATE INDEX idx_vl_relationships_target ON voto_limpo.relationships (target_id);")

    # pg_trgm indexes for full-text search
    op.execute("""
        CREATE INDEX idx_vl_politicians_name_trgm
        ON voto_limpo.politicians USING gin (name gin_trgm_ops);
    """)
    op.execute("""
        CREATE INDEX idx_vl_articles_title_trgm
        ON voto_limpo.articles USING gin (title gin_trgm_ops);
    """)


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS voto_limpo CASCADE;")
