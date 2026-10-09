"""Pre-migration schema fix: ensures critical columns and tables exist.

Runs BEFORE alembic so the PE can start even if migrations fail.
Uses CREATE TABLE IF NOT EXISTS and ALTER TABLE ADD COLUMN IF NOT EXISTS (idempotent).

IMPORTANT: analysis_results uses SERIAL (Int) for id and Int for article_id
to match the existing articles table (created by ETL with Int IDs) and the
Prisma schema used by helpcore-platform.
"""
import asyncio
import os
import sys


async def main():
    import asyncpg

    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "")
    db_pe = os.environ.get("DB_NAME", "processing_engine")

    print(f"[ensure-schema] Connecting to {host}:{port}/{db_pe} as {user}...")

    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password,
            database=db_pe, timeout=15
        )
    except Exception as e:
        print(f"[ensure-schema] SKIP — cannot connect: {e}")
        return  # non-fatal

    try:
        # --- 1. processing_engine.jobs: ensure missing columns ---
        jobs_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='processing_engine' AND table_name='jobs')"
        )
        if jobs_exists:
            cols = {r["column_name"] for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='processing_engine' AND table_name='jobs'"
            )}

            # Column renames from migration 016
            renames = [
                ("items_total", "total_items"),
                ("items_completed", "completed_items"),
                ("items_failed", "failed_items"),
            ]
            for old_name, new_name in renames:
                if old_name in cols and new_name not in cols:
                    await conn.execute(
                        f"ALTER TABLE processing_engine.jobs "
                        f"RENAME COLUMN {old_name} TO {new_name}"
                    )
                    cols.discard(old_name)
                    cols.add(new_name)
                    print(f"[ensure-schema] jobs: renamed {old_name} -> {new_name}")

            # Priority type change (INTEGER -> TEXT)
            ptype = await conn.fetchval(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema='processing_engine' AND table_name='jobs' "
                "AND column_name='priority'"
            )
            if ptype and ptype == 'integer':
                await conn.execute(
                    "ALTER TABLE processing_engine.jobs "
                    "ALTER COLUMN priority TYPE TEXT USING CASE "
                    "WHEN priority=0 THEN 'normal' "
                    "WHEN priority=1 THEN 'high' "
                    "WHEN priority=2 THEN 'critical' "
                    "WHEN priority=-1 THEN 'low' "
                    "ELSE 'normal' END"
                )
                print("[ensure-schema] jobs: priority INTEGER -> TEXT")

            needed = {
                "skip_cache": "BOOLEAN NOT NULL DEFAULT false",
                "skip_dedup": "BOOLEAN NOT NULL DEFAULT false",
                "dry_run": "BOOLEAN NOT NULL DEFAULT false",
                "override_model": "TEXT",
                "total_cost_usd": "NUMERIC(10,6) NOT NULL DEFAULT 0",
                "total_duration_ms": "INTEGER NOT NULL DEFAULT 0",
                "total_items": "INTEGER NOT NULL DEFAULT 0",
                "completed_items": "INTEGER NOT NULL DEFAULT 0",
                "failed_items": "INTEGER NOT NULL DEFAULT 0",
            }
            missing = {k: v for k, v in needed.items() if k not in cols}
            if missing:
                parts = [f"ADD COLUMN {col} {typedef}" for col, typedef in missing.items()]
                await conn.execute("ALTER TABLE processing_engine.jobs " + ", ".join(parts))
                print(f"[ensure-schema] jobs: added {list(missing.keys())}")
            else:
                print("[ensure-schema] jobs: all columns OK")

            # --- 1b. Rename items -> job_items if needed ---
            items_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='processing_engine' AND table_name='items')"
            )
            job_items_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='processing_engine' AND table_name='job_items')"
            )
            if items_exists and not job_items_exists:
                await conn.execute(
                    "ALTER TABLE processing_engine.items "
                    "RENAME TO job_items"
                )
                print("[ensure-schema] renamed items -> job_items")
            elif not items_exists and not job_items_exists:
                print("[ensure-schema] WARNING: neither items nor job_items exists!")

            # --- 1b2. Ensure job_items has all needed columns ---
            ji_table = 'job_items' if (job_items_exists or (items_exists and not job_items_exists)) else None
            if ji_table:
                ji_actual = ji_table if await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='processing_engine' AND table_name='job_items')"
                ) else 'items'
                ji_cols = {r["column_name"] for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    f"WHERE table_schema='processing_engine' AND table_name='{ji_actual}'"
                )}
                ji_needed = {
                    "content": "TEXT",
                    "pipeline_id": "UUID",
                    "url_hash": "TEXT",
                    "content_hash": "TEXT",
                    "content_type": "TEXT NOT NULL DEFAULT 'text/plain'",
                    "source_url": "TEXT",
                    "raw_content": "TEXT",
                    "output": "JSONB",
                    "dedup_result": "TEXT",
                    "dedup_matched_item_id": "UUID",
                    "metadata": "JSONB DEFAULT '{}'",
                    "cached": "BOOLEAN NOT NULL DEFAULT false",
                    "retry_count": "INTEGER NOT NULL DEFAULT 0",
                    "prompt_tokens": "INTEGER NOT NULL DEFAULT 0",
                    "completion_tokens": "INTEGER NOT NULL DEFAULT 0",
                    "total_tokens": "INTEGER NOT NULL DEFAULT 0",
                    "cost_usd": "NUMERIC(12,6) NOT NULL DEFAULT 0",
                    "duration_ms": "INTEGER NOT NULL DEFAULT 0",
                    "error": "TEXT",
                    "updated_at": "TIMESTAMPTZ DEFAULT now()",
                    "validation_errors": "JSONB NOT NULL DEFAULT '[]'",
                    "usage": "JSONB",
                    "processing_started_at": "TIMESTAMPTZ",
                    "processing_completed_at": "TIMESTAMPTZ",
                }
                ji_missing = {k: v for k, v in ji_needed.items() if k not in ji_cols}
                if ji_missing:
                    parts = [f"ADD COLUMN IF NOT EXISTS {col} {typedef}" for col, typedef in ji_missing.items()]
                    await conn.execute(f"ALTER TABLE processing_engine.{ji_actual} " + ", ".join(parts))
                    print(f"[ensure-schema] {ji_actual}: added {list(ji_missing.keys())}")

                # Rename error_message -> error if needed
                if 'error_message' in ji_cols and 'error' not in ji_cols:
                    await conn.execute(
                        f"ALTER TABLE processing_engine.{ji_actual} "
                        "RENAME COLUMN error_message TO error"
                    )
                    print(f"[ensure-schema] {ji_actual}: renamed error_message -> error")

            # --- 1c. Rename cache_entries -> cache if needed ---
            ce_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='processing_engine' AND table_name='cache_entries')"
            )
            cache_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='processing_engine' AND table_name='cache')"
            )
            if ce_exists and not cache_exists:
                await conn.execute(
                    "ALTER TABLE processing_engine.cache_entries RENAME TO cache"
                )
                print("[ensure-schema] renamed cache_entries -> cache")

            # --- 1c2. Ensure cache composite UNIQUE index ---
            # Orchestrator uses ON CONFLICT (content_hash, pipeline_id) which requires
            # a UNIQUE constraint on that pair. The fallback DDL only has PK on content_hash.
            cache_tbl_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='processing_engine' AND table_name='cache')"
            )
            if cache_tbl_exists:
                idx_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                    "WHERE schemaname='processing_engine' AND tablename='cache' "
                    "AND indexname='idx_cache_hash_pipeline')"
                )
                if not idx_exists:
                    # Drop PK on content_hash alone if it exists (incompatible)
                    pk_name = await conn.fetchval(
                        "SELECT c.conname FROM pg_constraint c "
                        "JOIN pg_namespace n ON c.connamespace = n.oid "
                        "WHERE n.nspname='processing_engine' "
                        "AND c.conrelid = 'processing_engine.cache'::regclass "
                        "AND c.contype = 'p'"
                    )
                    if pk_name:
                        await conn.execute(
                            f"ALTER TABLE processing_engine.cache DROP CONSTRAINT {pk_name}"
                        )
                        print(f"[ensure-schema] cache: dropped old PK {pk_name}")
                    await conn.execute(
                        "CREATE UNIQUE INDEX idx_cache_hash_pipeline "
                        "ON processing_engine.cache (content_hash, pipeline_id)"
                    )
                    print("[ensure-schema] cache: created UNIQUE index (content_hash, pipeline_id)")
        else:
            print("[ensure-schema] jobs table not found — alembic will create it")

        # --- 1d. Ensure enum values exist ---
        # job_status needs 'pending' and 'processing'
        for val in ('pending', 'processing'):
            try:
                await conn.execute(
                    f"ALTER TYPE processing_engine.job_status ADD VALUE IF NOT EXISTS '{val}'"
                )
            except Exception:
                pass  # enum value already exists or type doesn't exist

        # --- 1e. Ensure dedup_strategy enum exists ---
        enum_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n "
            "ON t.typnamespace = n.oid WHERE n.nspname='processing_engine' "
            "AND t.typname='dedup_strategy')"
        )
        if not enum_exists:
            await conn.execute(
                "CREATE TYPE processing_engine.dedup_strategy AS ENUM "
                "('hash', 'semantic', 'composite', 'none')"
            )
            print("[ensure-schema] dedup_strategy enum: CREATED")
        else:
            print("[ensure-schema] dedup_strategy enum: OK")

        # --- 1e. Ensure pipelines table has all columns ---
        pip_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='processing_engine' AND table_name='pipelines')"
        )
        if pip_exists:
            pip_cols = {r["column_name"] for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='processing_engine' AND table_name='pipelines'"
            )}
            pip_needed = {
                "description": "TEXT",
                "ingestor_type": "TEXT NOT NULL DEFAULT 'auto'",
                "max_content_chars": "INTEGER DEFAULT 100000",
                "dedup_strategy": "TEXT DEFAULT 'hash'",
                "dedup_threshold": "REAL DEFAULT 0.90",
                "llm_provider": "TEXT NOT NULL DEFAULT 'openai'",
                "llm_model": "TEXT NOT NULL DEFAULT 'gpt-4.1-mini'",
                "llm_temperature": "REAL NOT NULL DEFAULT 0.0",
                "llm_seed": "INTEGER DEFAULT 42",
                "llm_max_tokens": "INTEGER DEFAULT 16384",
                "system_prompt": "TEXT NOT NULL DEFAULT ''",
                "output_schema": "JSONB NOT NULL DEFAULT '{}'",
                "validators": "TEXT[] NOT NULL DEFAULT '{\"schema\"}'",
                "sink_type": "TEXT NOT NULL DEFAULT 'postgresql'",
                "sink_config": "JSONB DEFAULT '{}'",
                "max_concurrent": "INTEGER NOT NULL DEFAULT 5",
                "rate_limit_rpm": "INTEGER DEFAULT 60",
                "budget_limit_usd": "REAL",
                "budget_period": "TEXT DEFAULT 'month'",
                "max_retries": "INTEGER NOT NULL DEFAULT 3",
                "retry_backoff_base": "REAL NOT NULL DEFAULT 2.0",
                "cache_ttl_hours": "INTEGER NOT NULL DEFAULT 720",
                "is_active": "BOOLEAN NOT NULL DEFAULT true",
                "version": "INTEGER NOT NULL DEFAULT 1",
            }
            pip_missing = {k: v for k, v in pip_needed.items() if k not in pip_cols}
            if pip_missing:
                parts = [f"ADD COLUMN IF NOT EXISTS {col} {typedef}" for col, typedef in pip_missing.items()]
                await conn.execute("ALTER TABLE processing_engine.pipelines " + ", ".join(parts))
                print(f"[ensure-schema] pipelines: added {list(pip_missing.keys())}")
            else:
                print("[ensure-schema] pipelines: all columns OK")

            # Drop NOT NULL on columns that the orchestrator doesn't populate
            for col in ['config']:
                has_col = col in pip_cols
                if has_col:
                    await conn.execute(
                        f"ALTER TABLE processing_engine.pipelines "
                        f"ALTER COLUMN {col} DROP NOT NULL"
                    )
                    print(f"[ensure-schema] pipelines: dropped NOT NULL on {col}")

            # Ensure UNIQUE constraint on name (needed for ON CONFLICT)
            has_unique = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint c "
                "JOIN pg_namespace n ON c.connamespace = n.oid "
                "WHERE n.nspname = 'processing_engine' "
                "AND c.conrelid = 'processing_engine.pipelines'::regclass "
                "AND c.contype = 'u' "
                "AND EXISTS (SELECT 1 FROM unnest(c.conkey) k "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k "
                "WHERE a.attname = 'name'))"
            )
            if not has_unique:
                await conn.execute(
                    "ALTER TABLE processing_engine.pipelines "
                    "ADD CONSTRAINT pipelines_name_key UNIQUE (name)"
                )
                print("[ensure-schema] pipelines: added UNIQUE constraint on name")

            # If dedup_strategy column uses the enum type, change to TEXT for flexibility
            ds_type = await conn.fetchval(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_schema='processing_engine' AND table_name='pipelines' "
                "AND column_name='dedup_strategy'"
            )
            if ds_type and ds_type == 'dedup_strategy':
                await conn.execute(
                    "ALTER TABLE processing_engine.pipelines "
                    "ALTER COLUMN dedup_strategy TYPE TEXT USING dedup_strategy::TEXT"
                )
                print("[ensure-schema] pipelines: dedup_strategy ENUM -> TEXT")
        else:
            # Create pipelines table from scratch
            print("[ensure-schema] Creating processing_engine.pipelines...")
            await conn.execute("""
                CREATE TABLE processing_engine.pipelines (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name            TEXT NOT NULL UNIQUE,
                    version         INTEGER NOT NULL DEFAULT 1,
                    description     TEXT,
                    ingestor_type   TEXT NOT NULL DEFAULT 'auto',
                    max_content_chars INTEGER DEFAULT 100000,
                    dedup_strategy  TEXT DEFAULT 'hash',
                    dedup_threshold REAL DEFAULT 0.90,
                    llm_provider    TEXT NOT NULL DEFAULT 'openai',
                    llm_model       TEXT NOT NULL DEFAULT 'gpt-4.1-mini',
                    llm_temperature REAL NOT NULL DEFAULT 0.0,
                    llm_seed        INTEGER DEFAULT 42,
                    llm_max_tokens  INTEGER DEFAULT 16384,
                    system_prompt   TEXT NOT NULL DEFAULT '',
                    output_schema   JSONB NOT NULL DEFAULT '{}',
                    validators      TEXT[] NOT NULL DEFAULT '{"schema"}',
                    sink_type       TEXT NOT NULL DEFAULT 'postgresql',
                    sink_config     JSONB DEFAULT '{}',
                    max_concurrent  INTEGER NOT NULL DEFAULT 5,
                    rate_limit_rpm  INTEGER DEFAULT 60,
                    budget_limit_usd REAL,
                    budget_period    TEXT DEFAULT 'month',
                    max_retries     INTEGER NOT NULL DEFAULT 3,
                    retry_backoff_base REAL NOT NULL DEFAULT 2.0,
                    cache_ttl_hours INTEGER NOT NULL DEFAULT 720,
                    is_active       BOOLEAN NOT NULL DEFAULT true,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pipelines_name "
                "ON processing_engine.pipelines (name)"
            )
            print("[ensure-schema] pipelines: CREATED")

        # --- 2. Ensure help_core schema in processing_engine db ---
        # ALL help_core tables live in schema help_core WITHIN the processing_engine
        # database. The helpcore-platform (Prisma) connects to processing_engine with
        # schemas=["help_core","processing_engine"]. The PE sink also writes here.
        # There is NO separate "help_core" database — everything is in processing_engine.
        await conn.execute("CREATE SCHEMA IF NOT EXISTS help_core")
        print("[ensure-schema] help_core schema in processing_engine db: OK")

        # --- 3. help_core.analysis_results (INT ids, matching Prisma) ---
        ar_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='help_core' AND table_name='analysis_results')"
        )
        if not ar_exists:
            print("[ensure-schema] Creating help_core.analysis_results...")
            await conn.execute("""
                CREATE TABLE help_core.analysis_results (
                    id                          SERIAL PRIMARY KEY,
                    pe_item_id                  UUID NOT NULL,
                    article_id                  INTEGER,
                    source_url                  TEXT,

                    -- INVENTORY
                    doc_type                    TEXT,
                    category                    TEXT,
                    subcategory                 TEXT,
                    target_audience             TEXT,
                    inv_quality_score           DECIMAL,
                    completeness_score          DECIMAL,
                    key_topics                  JSONB,
                    summary                     TEXT,
                    requires_update             BOOLEAN,
                    has_mandatory_fields         BOOLEAN,
                    missing_mandatory_fields     JSONB,
                    estimated_word_count        INTEGER,
                    language_issues             JSONB,
                    classification_confidence   DECIMAL,
                    steps                       JSONB,
                    area_operacional            TEXT,
                    complexity_level            TEXT,
                    mentions_systems            JSONB,
                    escalation_present          BOOLEAN,
                    confidence                  DECIMAL,

                    -- QUALITY
                    clarity                     DECIMAL,
                    structure                   DECIMAL,
                    readability                 DECIMAL,
                    completeness                DECIMAL,
                    accuracy_signals            DECIMAL,
                    overall_score               DECIMAL,
                    priority_level              TEXT,
                    estimated_effort            TEXT,
                    improvement_suggestions     JSONB,
                    actionable_items            JSONB,

                    -- DEDUP
                    has_internal_conflicts      BOOLEAN,
                    internal_conflict_details   TEXT,
                    content_genericness         TEXT,

                    -- CONTENT
                    markdown_content            TEXT,

                    -- CHANGE TRACKING
                    analyzed_content_hash   TEXT,
                    analysis_status         TEXT NOT NULL DEFAULT 'completed',

                    -- TRACEABILITY
                    prompt_version              TEXT,
                    prompt_tokens               INTEGER,
                    completion_tokens           INTEGER,
                    cost_usd                    DECIMAL,
                    metadata                    JSONB NOT NULL DEFAULT '{}',
                    processed_at                TIMESTAMPTZ,
                    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

                    -- COMPUTED FIELDS (calculated by helpcore_compute_fields.py)
                    char_count                  INTEGER,
                    word_count                  INTEGER,
                    sentence_count              INTEGER,
                    paragraph_count             INTEGER,
                    line_count                  INTEGER,
                    avg_sentence_length         DECIMAL,
                    reading_time_seconds        INTEGER,
                    has_numbered_steps          BOOLEAN,
                    has_bullet_points           BOOLEAN,
                    has_headers                 BOOLEAN,
                    has_tables                  BOOLEAN,
                    has_images                  BOOLEAN,
                    uppercase_ratio             DECIMAL,
                    content_hash                TEXT,
                    link_count                  INTEGER,
                    title_word_count            INTEGER,

                    CONSTRAINT analysis_results_pe_item_id_unique UNIQUE (pe_item_id)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hc_analysis_doc_type "
                "ON help_core.analysis_results (doc_type)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hc_analysis_overall "
                "ON help_core.analysis_results (overall_score DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hc_analysis_source_url "
                "ON help_core.analysis_results (source_url)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hc_analysis_category "
                "ON help_core.analysis_results (category)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hc_analysis_priority "
                "ON help_core.analysis_results (priority_level)"
            )
            print("[ensure-schema] help_core.analysis_results: CREATED (SERIAL ids)")
        else:
            # Table exists — ensure all columns are present
            cols = {r["column_name"] for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='help_core' AND table_name='analysis_results'"
            )}
            needed_cols = {
                "steps": "JSONB",
                "area_operacional": "TEXT",
                "complexity_level": "TEXT",
                "mentions_systems": "JSONB",
                "escalation_present": "BOOLEAN",
                "markdown_content": "TEXT",
                "confidence": "DECIMAL",
                "completeness": "DECIMAL",
                "missing_mandatory_fields": "JSONB",
                "content_genericness": "TEXT",
                # Computed fields (calculated by helpcore_compute_fields.py)
                "char_count": "INTEGER",
                "word_count": "INTEGER",
                "sentence_count": "INTEGER",
                "paragraph_count": "INTEGER",
                "line_count": "INTEGER",
                "avg_sentence_length": "DECIMAL",
                "reading_time_seconds": "INTEGER",
                "has_numbered_steps": "BOOLEAN",
                "has_bullet_points": "BOOLEAN",
                "has_headers": "BOOLEAN",
                "has_tables": "BOOLEAN",
                "has_images": "BOOLEAN",
                "uppercase_ratio": "DECIMAL",
                "content_hash": "TEXT",
                "link_count": "INTEGER",
                "title_word_count": "INTEGER",
                # Change tracking
                "analyzed_content_hash": "TEXT",
                "analysis_status": "TEXT NOT NULL DEFAULT 'completed'",
            }
            missing = {k: v for k, v in needed_cols.items() if k not in cols}
            if missing:
                parts = [f"ADD COLUMN {col} {typedef}" for col, typedef in missing.items()]
                await conn.execute("ALTER TABLE help_core.analysis_results " + ", ".join(parts))
                print(f"[ensure-schema] analysis_results: added {list(missing.keys())}")
            else:
                print("[ensure-schema] analysis_results: all columns OK")

            # Ensure UNIQUE constraint on pe_item_id (needed for ON CONFLICT)
            has_unique = await conn.fetchval("""
                SELECT EXISTS (SELECT 1 FROM pg_constraint c
                JOIN pg_namespace n ON c.connamespace = n.oid
                WHERE n.nspname = 'help_core'
                AND c.conrelid = 'help_core.analysis_results'::regclass
                AND c.contype = 'u'
                AND EXISTS (SELECT 1 FROM unnest(c.conkey) k
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k
                WHERE a.attname = 'pe_item_id'))
            """)
            if not has_unique:
                await conn.execute(
                    "ALTER TABLE help_core.analysis_results "
                    "ADD CONSTRAINT analysis_results_pe_item_id_unique UNIQUE (pe_item_id)"
                )
                print("[ensure-schema] analysis_results: added UNIQUE on pe_item_id")

        # --- 4. help_core.review_actions ---
        ra_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='help_core' AND table_name='review_actions')"
        )
        if not ra_exists:
            print("[ensure-schema] Creating help_core.review_actions...")
            await conn.execute("""
                CREATE TABLE help_core.review_actions (
                    id                 SERIAL PRIMARY KEY,
                    analysis_result_id INTEGER NOT NULL,
                    action             TEXT NOT NULL,
                    notes              TEXT,
                    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            print("[ensure-schema] help_core.review_actions: CREATED")
        else:
            print("[ensure-schema] review_actions: exists")

        # --- 5. help_core.article_relationships ---
        rel_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='help_core' AND table_name='article_relationships')"
        )
        if not rel_exists:
            print("[ensure-schema] Creating help_core.article_relationships...")
            await conn.execute("""
                CREATE TABLE help_core.article_relationships (
                    id                 SERIAL PRIMARY KEY,
                    source_article_id  INTEGER NOT NULL,
                    target_article_id  INTEGER NOT NULL,
                    relationship_type  TEXT NOT NULL,
                    similarity_score   DECIMAL,
                    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            print("[ensure-schema] help_core.article_relationships: CREATED")
        else:
            print("[ensure-schema] article_relationships: exists")

        # --- 6. help_core.article_changes ---
        ac_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='help_core' AND table_name='article_changes')"
        )
        if not ac_exists:
            print("[ensure-schema] Creating help_core.article_changes...")
            await conn.execute("""
                CREATE TABLE help_core.article_changes (
                    id                      SERIAL PRIMARY KEY,
                    article_id              INTEGER NOT NULL,
                    detected_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
                    previous_hash           TEXT NOT NULL,
                    new_hash                TEXT NOT NULL,
                    change_type             TEXT NOT NULL DEFAULT 'content_modified',
                    fields_changed          TEXT[],
                    triggered_reprocessing  BOOLEAN NOT NULL DEFAULT true,
                    CONSTRAINT fk_article_changes_article
                        FOREIGN KEY (article_id) REFERENCES help_core.articles(id)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_article_changes_article_id "
                "ON help_core.article_changes (article_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_article_changes_detected_at "
                "ON help_core.article_changes (detected_at)"
            )
            print("[ensure-schema] help_core.article_changes: CREATED")
        else:
            print("[ensure-schema] article_changes: OK")

        print("[ensure-schema] Done — all critical tables/columns ensured.")

    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[ensure-schema] ERROR (non-fatal): {e}", file=sys.stderr)
