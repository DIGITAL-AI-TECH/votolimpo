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
        else:
            print("[ensure-schema] jobs table not found — alembic will create it")

        # --- 2. Ensure help_core schema ---
        await conn.execute("CREATE SCHEMA IF NOT EXISTS help_core")
        print("[ensure-schema] help_core schema: OK")

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

                    -- TRACEABILITY
                    prompt_version              TEXT,
                    prompt_tokens               INTEGER,
                    completion_tokens           INTEGER,
                    cost_usd                    DECIMAL,
                    metadata                    JSONB NOT NULL DEFAULT '{}',
                    processed_at                TIMESTAMPTZ,
                    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

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
            }
            missing = {k: v for k, v in needed_cols.items() if k not in cols}
            if missing:
                parts = [f"ADD COLUMN {col} {typedef}" for col, typedef in missing.items()]
                await conn.execute("ALTER TABLE help_core.analysis_results " + ", ".join(parts))
                print(f"[ensure-schema] analysis_results: added {list(missing.keys())}")
            else:
                print("[ensure-schema] analysis_results: all columns OK")

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

        print("[ensure-schema] Done — all critical tables/columns ensured.")

    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[ensure-schema] ERROR (non-fatal): {e}", file=sys.stderr)
