"""Database connection pool using asyncpg directly."""

import logging
import os

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

# Connection pool (initialized on startup)
_pool: asyncpg.Pool | None = None


def _get_dsn() -> str:
    """Convert SQLAlchemy-style URL to asyncpg DSN."""
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_get_dsn(),
            min_size=2,
            max_size=10,
        )
        logger.info("Database pool created")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def init_engine_schema(pool: asyncpg.Pool | None = None):
    """Ensure the processing_engine schema exists.

    Only creates the schema itself — tables are managed by Alembic migrations.
    If migrations haven't run yet, creates minimal tables as fallback.
    """
    if pool is None:
        pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS processing_engine")

        # Check if tables already exist (created by Alembic)
        row = await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'processing_engine' AND table_name = 'jobs'
        """)
        if row > 0:
            logger.info("Engine schema already initialized (tables exist)")
            return

        # Fallback: create tables if Alembic hasn't run
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS processing_engine.pipelines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0',
                config JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS processing_engine.jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pipeline_id UUID NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                priority TEXT NOT NULL DEFAULT 'normal',
                total_items INT NOT NULL DEFAULT 0,
                completed_items INT NOT NULL DEFAULT 0,
                failed_items INT NOT NULL DEFAULT 0,
                callback_url TEXT,
                idempotency_key TEXT,
                total_cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
                total_duration_ms INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_priority
                ON processing_engine.jobs (status, priority DESC, created_at ASC);

            CREATE TABLE IF NOT EXISTS processing_engine.job_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                job_id UUID NOT NULL REFERENCES processing_engine.jobs(id),
                content TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'text/plain',
                source_url TEXT,
                metadata JSONB NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                output JSONB,
                validation_errors JSONB NOT NULL DEFAULT '[]',
                dedup_result TEXT,
                usage JSONB,
                cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
                duration_ms INT NOT NULL DEFAULT 0,
                error TEXT,
                cached BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_job_items_job_id
                ON processing_engine.job_items (job_id);

            CREATE TABLE IF NOT EXISTS processing_engine.processing_logs (
                id BIGSERIAL PRIMARY KEY,
                job_id UUID NOT NULL,
                item_id UUID,
                step TEXT NOT NULL,
                status TEXT NOT NULL,
                model_used TEXT,
                prompt_tokens INT,
                completion_tokens INT,
                cost_usd NUMERIC(10,6),
                duration_ms INT NOT NULL DEFAULT 0,
                error_message TEXT,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS processing_engine.cache (
                content_hash TEXT PRIMARY KEY,
                pipeline_id UUID NOT NULL,
                output JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON processing_engine.cache (expires_at);
        """)
    logger.info("Engine schema initialized (fallback DDL)")


async def init_votolimpo_schema():
    """Ensure the votolimpo schema and all required tables exist.

    Uses VOTOLIMPO_DATABASE_URL (or PE_VOTOLIMPO_DATABASE_URL) to connect.
    Creates schema, ENUMs, tables, indexes — all idempotent (IF NOT EXISTS).
    """
    raw_url = os.environ.get("PE_VOTOLIMPO_DATABASE_URL") or os.environ.get(
        "VOTOLIMPO_DATABASE_URL", ""
    )
    if not raw_url:
        logger.info("No VOTOLIMPO_DATABASE_URL configured — skipping votolimpo init")
        return

    clean_url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(clean_url, timeout=10)
    except Exception:
        logger.exception("Failed to connect to votolimpo DB — skipping init")
        return

    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        await conn.execute("CREATE SCHEMA IF NOT EXISTS votolimpo;")

        # --- ENUMs (idempotent via DO block) ---
        for enum_name, enum_values in [
            ("severity_level", "'low','medium','high','critical'"),
            ("article_role", "'subject','mentioned','related'"),
            ("entity_type", "'company','organization','lobby','ngo'"),
            (
                "relationship_type",
                "'business','political','family','legal','financial'",
            ),
            (
                "milestone_type",
                "'inquiry','complaint','conviction','acquittal','arrest','impeachment','plea_deal','fine'",
            ),
            ("match_type", "'content','entity','temporal'"),
            ("processing_status", "'pending','processing','completed','failed'"),
        ]:
            await conn.execute(f"""
                DO $$ BEGIN
                    CREATE TYPE votolimpo.{enum_name} AS ENUM ({enum_values});
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)

        # --- Tables ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.parties (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                abbreviation VARCHAR(20) UNIQUE NOT NULL,
                logo_url TEXT,
                color VARCHAR(7),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.politicians (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                slug VARCHAR(200) UNIQUE NOT NULL,
                name TEXT NOT NULL,
                party VARCHAR(50),
                party_id UUID REFERENCES votolimpo.parties(id),
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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.sources (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                domain VARCHAR(255) UNIQUE NOT NULL,
                reputation NUMERIC(3,2),
                category VARCHAR(50),
                logo_url TEXT,
                article_count INT DEFAULT 0,
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.articles (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT,
                url TEXT,
                url_hash TEXT UNIQUE,
                summary TEXT,
                original_url TEXT,
                source_id UUID REFERENCES votolimpo.sources(id),
                source_domain TEXT,
                published_at TIMESTAMPTZ,
                collected_at TIMESTAMPTZ DEFAULT now(),
                veracity_score NUMERIC(5,4),
                severity votolimpo.severity_level,
                raw_content TEXT,
                ai_processed BOOLEAN DEFAULT false,
                source_reputation NUMERIC(5,4),
                multi_source_count INT,
                multi_source_score NUMERIC(5,4),
                narrative_consistency NUMERIC(5,4),
                documental_evidence NUMERIC(5,4),
                temporality_score NUMERIC(5,4),
                emotional_language NUMERIC(5,4),
                score_components JSONB,
                keywords TEXT[],
                is_political BOOLEAN,
                nc_article_id TEXT,
                source_url TEXT,
                raw_output JSONB,
                pe_item_id UUID,
                processing_status votolimpo.processing_status DEFAULT 'pending',
                processed_at TIMESTAMPTZ,
                sentiment TEXT,
                sentiment_score NUMERIC(5,4),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.politician_articles (
                politician_id UUID NOT NULL REFERENCES votolimpo.politicians(id),
                article_id UUID NOT NULL REFERENCES votolimpo.articles(id),
                role votolimpo.article_role DEFAULT 'mentioned',
                PRIMARY KEY (politician_id, article_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.entities (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                entity_type votolimpo.entity_type NOT NULL,
                description TEXT,
                score NUMERIC(5,2),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.relationships (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_type VARCHAR(20) NOT NULL,
                source_id UUID NOT NULL,
                target_type VARCHAR(20) NOT NULL,
                target_id UUID NOT NULL,
                relationship_type votolimpo.relationship_type NOT NULL,
                weight INT DEFAULT 1,
                description TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.relationship_evidence (
                relationship_id UUID NOT NULL REFERENCES votolimpo.relationships(id),
                article_id UUID NOT NULL REFERENCES votolimpo.articles(id),
                PRIMARY KEY (relationship_id, article_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.milestones (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                politician_id UUID NOT NULL REFERENCES votolimpo.politicians(id),
                title TEXT NOT NULL,
                description TEXT,
                milestone_type votolimpo.milestone_type NOT NULL,
                occurred_at DATE,
                source_url TEXT,
                article_id UUID REFERENCES votolimpo.articles(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.article_matches (
                article_a_id UUID NOT NULL REFERENCES votolimpo.articles(id),
                article_b_id UUID NOT NULL REFERENCES votolimpo.articles(id),
                similarity NUMERIC(5,4),
                entity_overlap NUMERIC(5,4),
                keyword_overlap NUMERIC(5,4),
                temporal_prox NUMERIC(5,4),
                match_type votolimpo.match_type,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (article_a_id, article_b_id),
                CHECK (article_a_id < article_b_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.score_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                politician_id UUID NOT NULL REFERENCES votolimpo.politicians(id),
                score NUMERIC(5,2) NOT NULL,
                score_components JSONB,
                article_count INT DEFAULT 0,
                calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        # --- Cluster tables (used by NC clusters router + PE cluster_updater) ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.news_clusters (
                id SERIAL PRIMARY KEY,
                title TEXT,
                summary TEXT,
                article_count INT DEFAULT 0,
                first_article TIMESTAMPTZ,
                last_article TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.cluster_articles (
                cluster_id INT NOT NULL REFERENCES votolimpo.news_clusters(id),
                article_id UUID NOT NULL REFERENCES votolimpo.articles(id),
                PRIMARY KEY (cluster_id, article_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.cluster_politicians (
                cluster_id INT NOT NULL REFERENCES votolimpo.news_clusters(id),
                politician_id UUID NOT NULL REFERENCES votolimpo.politicians(id),
                article_count INT DEFAULT 0,
                PRIMARY KEY (cluster_id, politician_id)
            );
        """)

        # --- Indexes ---
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_vl_politicians_score ON votolimpo.politicians (score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_vl_politicians_slug ON votolimpo.politicians (slug)",
            "CREATE INDEX IF NOT EXISTS idx_vl_articles_published ON votolimpo.articles (published_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_vl_articles_source ON votolimpo.articles (source_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_articles_url_hash ON votolimpo.articles (url_hash)",
            "CREATE INDEX IF NOT EXISTS idx_vl_milestones_politician ON votolimpo.milestones (politician_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_relationships_source ON votolimpo.relationships (source_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_relationships_target ON votolimpo.relationships (target_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_cluster_articles_cluster ON votolimpo.cluster_articles (cluster_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_cluster_articles_article ON votolimpo.cluster_articles (article_id)",
            "CREATE INDEX IF NOT EXISTS idx_vl_score_history_politician ON votolimpo.score_history (politician_id, calculated_at DESC)",
        ]:
            await conn.execute(idx_sql)

        # pg_trgm indexes (best-effort — extension may not be available)
        try:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vl_politicians_name_trgm
                ON votolimpo.politicians USING gin (name gin_trgm_ops)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vl_articles_title_trgm
                ON votolimpo.articles USING gin (title gin_trgm_ops)
            """)
        except Exception:
            logger.warning("pg_trgm indexes skipped (extension may not be available)")

        logger.info("Votolimpo schema initialized successfully")
    except Exception:
        logger.exception("Failed to initialize votolimpo schema")
    finally:
        await conn.close()
