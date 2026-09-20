"""Database connection pool using asyncpg directly."""

import asyncio
import logging
import os

import asyncpg

from ..config import settings

logger = logging.getLogger(__name__)

# Connection pool (initialized on startup)
_pool: asyncpg.Pool | None = None

# Retry settings for initial connection
_CONNECT_MAX_RETRIES = 10
_CONNECT_BASE_DELAY = 2  # seconds


def _get_dsn() -> str:
    """Convert SQLAlchemy-style URL to asyncpg DSN."""
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool with retry on transient failures."""
    global _pool
    if _pool is None:
        last_err: Exception | None = None
        for attempt in range(1, _CONNECT_MAX_RETRIES + 1):
            try:
                _pool = await asyncpg.create_pool(
                    dsn=_get_dsn(),
                    min_size=2,
                    max_size=10,
                )
                logger.info("Database pool created (attempt %d)", attempt)
                return _pool
            except (ConnectionRefusedError, OSError) as exc:
                last_err = exc
                delay = _CONNECT_BASE_DELAY * attempt
                logger.warning(
                    "DB connection attempt %d/%d failed: %s — retrying in %ds",
                    attempt,
                    _CONNECT_MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        raise last_err  # type: ignore[misc]
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


_SEED_SOURCES = [
    # BRASIL — Mainstream
    ("g1.globo.com", "g1.globo.com", 0.85, "mainstream"),
    ("folha.uol.com.br", "folha.uol.com.br", 0.85, "mainstream"),
    ("estadao.com.br", "estadao.com.br", 0.85, "mainstream"),
    ("oglobo.globo.com", "oglobo.globo.com", 0.85, "mainstream"),
    ("uol.com.br", "uol.com.br", 0.75, "mainstream"),
    ("terra.com.br", "terra.com.br", 0.70, "mainstream"),
    ("r7.com", "r7.com", 0.70, "mainstream"),
    ("band.uol.com.br", "band.uol.com.br", 0.75, "mainstream"),
    ("cnn.com.br", "cnn.com.br", 0.75, "mainstream"),
    ("bbc.com/portuguese", "bbc.com/portuguese", 0.90, "mainstream"),
    ("metropoles.com", "metropoles.com", 0.75, "mainstream"),
    ("poder360.com.br", "poder360.com.br", 0.80, "mainstream"),
    ("infomoney.com.br", "infomoney.com.br", 0.80, "mainstream"),
    ("valor.globo.com", "valor.globo.com", 0.85, "mainstream"),
    ("gazetadopovo.com.br", "gazetadopovo.com.br", 0.75, "mainstream"),
    ("cartacapital.com.br", "cartacapital.com.br", 0.70, "mainstream"),
    ("revistaforum.com.br", "revistaforum.com.br", 0.55, "mainstream"),
    ("crusoemagazine.com.br", "crusoemagazine.com.br", 0.65, "mainstream"),
    ("jornaldacidadeonline.com.br", "jornaldacidadeonline.com.br", 0.45, "portal"),
    ("diariodopoder.com.br", "diariodopoder.com.br", 0.65, "mainstream"),
    ("correiobraziliense.com.br", "correiobraziliense.com.br", 0.75, "mainstream"),
    ("istoe.com.br", "istoe.com.br", 0.70, "mainstream"),
    ("veja.abril.com.br", "veja.abril.com.br", 0.75, "mainstream"),
    ("exame.com", "exame.com", 0.75, "mainstream"),
    ("epocanegocios.globo.com", "epocanegocios.globo.com", 0.75, "mainstream"),
    # BRASIL — Regionais
    ("gazetaonline.com.br", "gazetaonline.com.br", 0.65, "regional"),
    ("diariodepernambuco.com.br", "diariodepernambuco.com.br", 0.65, "regional"),
    ("correio24horas.com.br", "correio24horas.com.br", 0.65, "regional"),
    ("nsctotal.com.br", "nsctotal.com.br", 0.65, "regional"),
    ("zerohora.com.br", "zerohora.com.br", 0.70, "regional"),
    ("jornaldocomercio.com", "jornaldocomercio.com", 0.65, "regional"),
    # BRASIL — Governo / Institucionais
    ("gov.br", "gov.br", 0.90, "govt"),
    ("agenciabrasil.ebc.com.br", "agenciabrasil.ebc.com.br", 0.85, "agency"),
    ("camara.leg.br", "camara.leg.br", 0.90, "govt"),
    ("senado.leg.br", "senado.leg.br", 0.90, "govt"),
    ("stf.jus.br", "stf.jus.br", 0.90, "govt"),
    ("tse.jus.br", "tse.jus.br", 0.90, "govt"),
    # INTERNACIONAL — Mainstream
    ("reuters.com", "reuters.com", 0.95, "international"),
    ("apnews.com", "apnews.com", 0.95, "international"),
    ("bbc.com", "bbc.com", 0.90, "international"),
    ("nytimes.com", "nytimes.com", 0.90, "international"),
    ("washingtonpost.com", "washingtonpost.com", 0.90, "international"),
    ("theguardian.com", "theguardian.com", 0.85, "international"),
    ("cnn.com", "cnn.com", 0.80, "international"),
    ("aljazeera.com", "aljazeera.com", 0.80, "international"),
    ("france24.com", "france24.com", 0.80, "international"),
    ("dw.com", "dw.com", 0.80, "international"),
    ("elpais.com", "elpais.com", 0.85, "international"),
    ("lemonde.fr", "lemonde.fr", 0.85, "international"),
    ("ft.com", "ft.com", 0.90, "international"),
    ("economist.com", "economist.com", 0.90, "international"),
    ("wsj.com", "wsj.com", 0.90, "international"),
    ("bloomberg.com", "bloomberg.com", 0.90, "international"),
    # AGÊNCIAS DE NOTÍCIA
    ("afp.com", "afp.com", 0.95, "agency"),
    ("efe.com", "efe.com", 0.90, "agency"),
    ("xinhua.net", "xinhua.net", 0.65, "agency"),
    ("tass.com", "tass.com", 0.55, "agency"),
    # PORTAIS / AGREGADORES
    ("msn.com", "msn.com", 0.55, "portal"),
    ("yahoo.com", "yahoo.com", 0.60, "portal"),
    ("ig.com.br", "ig.com.br", 0.55, "portal"),
    ("bol.uol.com.br", "bol.uol.com.br", 0.55, "portal"),
]


async def _seed_sources(conn: "asyncpg.Connection") -> None:
    """Insert baseline source reputation data (idempotent)."""
    for name, domain, score, category in _SEED_SOURCES:
        await conn.execute(
            """
            INSERT INTO votolimpo.sources (name, domain, reputation_score, category)
            VALUES ($1, $2, $3, $4::votolimpo.source_category)
            ON CONFLICT (name) DO UPDATE SET
                reputation_score = EXCLUDED.reputation_score,
                category = EXCLUDED.category,
                domain = EXCLUDED.domain,
                updated_at = NOW()
            """,
            name, domain, score, category,
        )
    logger.info("Seeded %d sources with reputation scores", len(_SEED_SOURCES))


async def init_votolimpo_schema():
    """Ensure the votolimpo schema and all required tables exist.

    Uses VOTOLIMPO_DATABASE_URL (or PE_VOTOLIMPO_DATABASE_URL) to connect.

    IMPORTANT: The votolimpo schema is OWNED by the News Collector (NC) migrations.
    NC uses SERIAL (INTEGER) PKs — this fallback DDL MUST match NC's schema exactly
    to avoid type mismatches when both services share the same database.

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

        # Detect legacy UUID-based schema and nuke it.
        # Old tables used UUID PKs + different column names (occurred_at, milestone_type).
        # Current DDL uses SERIAL INTEGER PKs + renamed columns (date, type).
        # CREATE TABLE IF NOT EXISTS won't fix the mismatch, so drop+recreate.
        legacy = await conn.fetchval("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'votolimpo' AND table_name = 'politicians'
              AND column_name = 'id'
        """)
        if legacy and legacy == 'uuid':
            logger.warning("Detected legacy UUID schema — dropping votolimpo for clean recreation")
            await conn.execute("DROP SCHEMA votolimpo CASCADE;")
            await conn.execute("CREATE SCHEMA votolimpo;")

        # --- ENUMs (must match NC 001_create_schema_enums.sql exactly) ---
        for enum_name, enum_values in [
            ("severity_level", "'low','medium','high','critical'"),
            (
                "article_role",
                "'protagonist','mentioned','investigated','witness','victim','other'",
            ),
            (
                "entity_type",
                "'person','organization','location','event','concept'",
            ),
            (
                "relationship_type",
                "'ally','opponent','party_member','family','business','legal','investigation'",
            ),
            (
                "milestone_type",
                "'inquiry','complaint','conviction','acquittal','arrest','impeachment','plea_deal','fine'",
            ),
            (
                "match_type",
                "'same_event','follow_up','related','contradiction'",
            ),
            (
                "processing_status",
                "'pending','processing','completed','failed','retry'",
            ),
            (
                "source_category",
                "'mainstream','regional','portal','blog','govt','agency','international'",
            ),
        ]:
            await conn.execute(f"""
                DO $$ BEGIN
                    CREATE TYPE votolimpo.{enum_name} AS ENUM ({enum_values});
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)

        # --- Tables (aligned with NC 002_create_tables.sql — SERIAL INTEGER PKs) ---

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.politicians (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                party TEXT,
                state TEXT,
                city TEXT,
                role TEXT,
                foto_url TEXT,
                bio TEXT,
                ai_summary TEXT,
                score DECIMAL(5,2) DEFAULT 0,
                score_components JSONB DEFAULT '{}',
                total_articles INTEGER DEFAULT 0,
                search_vector TSVECTOR,
                nc_entity_id TEXT,
                tse_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.parties (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                abbreviation TEXT NOT NULL UNIQUE,
                logo_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.politician_parties (
                id SERIAL PRIMARY KEY,
                politician_id INTEGER NOT NULL REFERENCES votolimpo.politicians(id),
                party_id INTEGER NOT NULL REFERENCES votolimpo.parties(id),
                start_date DATE,
                end_date DATE,
                is_current BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.sources (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                domain TEXT UNIQUE,
                reputation_score DECIMAL(3,2) DEFAULT 0.50,
                category votolimpo.source_category DEFAULT 'portal',
                article_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Seed sources with reputation scores (idempotent — ON CONFLICT updates).
        # This ensures production has baseline data even though migration 017
        # only runs in CI.
        await _seed_sources(conn)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.articles (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                url_hash TEXT NOT NULL UNIQUE,
                content_hash TEXT,
                source_id INTEGER REFERENCES votolimpo.sources(id),
                published_at TIMESTAMPTZ,
                collected_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                source_reputation DECIMAL(3,2),
                multi_source_score DECIMAL(3,2),
                narrative_consistency DECIMAL(3,2),
                documental_evidence DECIMAL(3,2),
                temporality_score DECIMAL(3,2),
                emotional_language DECIMAL(3,2),
                veracity_score DECIMAL(3,2),
                severity votolimpo.severity_level,
                summary TEXT,
                keywords TEXT[],
                processing_status votolimpo.processing_status DEFAULT 'pending',
                processing_errors JSONB DEFAULT '[]',
                nc_article_id TEXT,
                raw_extraction JSONB,
                score_components JSONB DEFAULT '{}',
                language VARCHAR(10) DEFAULT 'pt',
                is_political BOOLEAN DEFAULT true,
                source_url TEXT,
                raw_output JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.politician_articles (
                id SERIAL PRIMARY KEY,
                politician_id INTEGER NOT NULL REFERENCES votolimpo.politicians(id),
                article_id INTEGER NOT NULL REFERENCES votolimpo.articles(id),
                role votolimpo.article_role DEFAULT 'mentioned',
                relevance_score DECIMAL(3,2),
                UNIQUE(politician_id, article_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.article_matches (
                id SERIAL PRIMARY KEY,
                article_a_id INTEGER NOT NULL REFERENCES votolimpo.articles(id),
                article_b_id INTEGER NOT NULL REFERENCES votolimpo.articles(id),
                match_type votolimpo.match_type,
                similarity DECIMAL(3,2) NOT NULL,
                entity_overlap DECIMAL(3,2),
                keyword_overlap DECIMAL(3,2),
                temporal_prox DECIMAL(3,2),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                CHECK (article_a_id < article_b_id),
                UNIQUE(article_a_id, article_b_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.milestones (
                id SERIAL PRIMARY KEY,
                politician_id INTEGER NOT NULL REFERENCES votolimpo.politicians(id),
                article_id INTEGER REFERENCES votolimpo.articles(id),
                type votolimpo.milestone_type NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                date DATE NOT NULL,
                confidence DECIMAL(3,2) NOT NULL,
                source_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.entities (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                type votolimpo.entity_type NOT NULL,
                metadata JSONB DEFAULT '{}',
                first_seen_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                article_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.relationships (
                id SERIAL PRIMARY KEY,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                source_type TEXT NOT NULL CHECK (source_type IN ('politician', 'entity')),
                target_type TEXT NOT NULL CHECK (target_type IN ('politician', 'entity')),
                type votolimpo.relationship_type NOT NULL,
                weight INTEGER DEFAULT 1,
                first_seen_at TIMESTAMPTZ DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(source_id, target_id, source_type, target_type, type)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.relationship_evidence (
                id SERIAL PRIMARY KEY,
                relationship_id INTEGER NOT NULL REFERENCES votolimpo.relationships(id),
                article_id INTEGER NOT NULL REFERENCES votolimpo.articles(id),
                excerpt TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.news_clusters (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                article_count INTEGER DEFAULT 0,
                first_article TIMESTAMPTZ,
                last_article TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.cluster_articles (
                cluster_id INTEGER NOT NULL REFERENCES votolimpo.news_clusters(id),
                article_id INTEGER NOT NULL REFERENCES votolimpo.articles(id),
                PRIMARY KEY (cluster_id, article_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.cluster_politicians (
                cluster_id INTEGER NOT NULL REFERENCES votolimpo.news_clusters(id),
                politician_id INTEGER NOT NULL REFERENCES votolimpo.politicians(id),
                article_count INTEGER DEFAULT 0,
                PRIMARY KEY (cluster_id, politician_id)
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS votolimpo.score_history (
                id SERIAL PRIMARY KEY,
                politician_id INTEGER NOT NULL REFERENCES votolimpo.politicians(id),
                score DECIMAL(5,2) NOT NULL,
                components JSONB NOT NULL,
                calculated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # --- Indexes (aligned with NC 002_create_tables.sql) ---
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_politicians_slug ON votolimpo.politicians(slug)",
            "CREATE INDEX IF NOT EXISTS idx_politicians_score ON votolimpo.politicians(score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_politicians_state ON votolimpo.politicians(state)",
            "CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON votolimpo.articles(url_hash)",
            "CREATE INDEX IF NOT EXISTS idx_articles_published ON votolimpo.articles(published_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_articles_source ON votolimpo.articles(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_severity ON votolimpo.articles(severity)",
            "CREATE INDEX IF NOT EXISTS idx_articles_status ON votolimpo.articles(processing_status)",
            "CREATE INDEX IF NOT EXISTS idx_articles_keywords ON votolimpo.articles USING GIN(keywords)",
            "CREATE INDEX IF NOT EXISTS idx_pa_politician ON votolimpo.politician_articles(politician_id)",
            "CREATE INDEX IF NOT EXISTS idx_pa_article ON votolimpo.politician_articles(article_id)",
            "CREATE INDEX IF NOT EXISTS idx_am_articles ON votolimpo.article_matches(article_a_id, article_b_id)",
            "CREATE INDEX IF NOT EXISTS idx_milestones_politician ON votolimpo.milestones(politician_id, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_milestones_type ON votolimpo.milestones(type)",
            "CREATE INDEX IF NOT EXISTS idx_entities_normalized ON votolimpo.entities(normalized_name)",
            "CREATE INDEX IF NOT EXISTS idx_entities_type ON votolimpo.entities(type)",
            "CREATE INDEX IF NOT EXISTS idx_rel_source ON votolimpo.relationships(source_id, source_type)",
            "CREATE INDEX IF NOT EXISTS idx_rel_target ON votolimpo.relationships(target_id, target_type)",
            "CREATE INDEX IF NOT EXISTS idx_sh_politician ON votolimpo.score_history(politician_id, calculated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_pp_politician ON votolimpo.politician_parties(politician_id)",
        ]:
            await conn.execute(idx_sql)

        # pg_trgm indexes (best-effort — extension may not be available)
        try:
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_politicians_trgm
                ON votolimpo.politicians USING GIN(name gin_trgm_ops)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_trgm
                ON votolimpo.entities USING GIN(normalized_name gin_trgm_ops)
            """)
        except Exception:
            logger.warning("pg_trgm indexes skipped (extension may not be available)")

        logger.info("Votolimpo schema initialized successfully")
    except Exception:
        logger.exception("Failed to initialize votolimpo schema")
    finally:
        await conn.close()
