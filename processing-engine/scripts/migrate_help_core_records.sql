-- Migrate records from separate help_core DB to processing_engine.help_core schema
-- This script runs inside the processing_engine database
-- Context: The PE sink was incorrectly writing to a separate help_core DB.
-- Now both HELPCORE_DATABASE_URL and VOTOLIMPO_DATABASE_URL point to processing_engine.
-- This migrates any records that ended up in the wrong place.
--
-- USAGE (run inside hc-postgres container):
--   psql -U postgres -d processing_engine -f /tmp/migrate_help_core_records.sql
--
-- IDEMPOTENT: Uses INSERT ... ON CONFLICT DO NOTHING

-- Step 1: Ensure help_core schema exists in processing_engine
CREATE SCHEMA IF NOT EXISTS help_core;

-- Step 2: Check if we can access the help_core database via dblink
-- If the help_core database doesn't exist, this is a no-op
DO $$
DECLARE
    hc_db_exists BOOLEAN;
    record_count INTEGER;
BEGIN
    -- Check if help_core database exists
    SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = 'help_core') INTO hc_db_exists;

    IF NOT hc_db_exists THEN
        RAISE NOTICE 'Database help_core does not exist — nothing to migrate';
        RETURN;
    END IF;

    -- Install dblink if not present
    CREATE EXTENSION IF NOT EXISTS dblink;

    -- Count records in source
    SELECT count(*) INTO record_count
    FROM dblink(
        'dbname=help_core',
        'SELECT id FROM help_core.articles'
    ) AS t(id INTEGER);

    RAISE NOTICE 'Found % records in help_core.help_core.articles', record_count;

    IF record_count = 0 THEN
        RAISE NOTICE 'No records to migrate';
        RETURN;
    END IF;

    -- Migrate articles
    INSERT INTO help_core.articles (
        id, source_url, title, subtitle, area, lista, content, html_content,
        content_hash, created_at, updated_at
    )
    SELECT *
    FROM dblink(
        'dbname=help_core',
        'SELECT id, source_url, title, subtitle, area, lista, content, html_content,
                content_hash, created_at, updated_at
         FROM help_core.articles'
    ) AS t(
        id INTEGER, source_url TEXT, title TEXT, subtitle TEXT, area TEXT, lista TEXT,
        content TEXT, html_content TEXT, content_hash TEXT,
        created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
    )
    ON CONFLICT (source_url) DO NOTHING;

    GET DIAGNOSTICS record_count = ROW_COUNT;
    RAISE NOTICE 'Migrated % articles', record_count;

    -- Migrate analysis_results
    INSERT INTO help_core.analysis_results (
        article_id, clarity_score, structure_score, completeness_score,
        accuracy_signals_score, readability_score, overall_score,
        priority_level, main_topic, content_type, target_audience,
        key_findings, improvement_suggestions, missing_information,
        quality_issues, created_at
    )
    SELECT *
    FROM dblink(
        'dbname=help_core',
        'SELECT article_id, clarity_score, structure_score, completeness_score,
                accuracy_signals_score, readability_score, overall_score,
                priority_level, main_topic, content_type, target_audience,
                key_findings, improvement_suggestions, missing_information,
                quality_issues, created_at
         FROM help_core.analysis_results'
    ) AS t(
        article_id INTEGER, clarity_score NUMERIC, structure_score NUMERIC,
        completeness_score NUMERIC, accuracy_signals_score NUMERIC,
        readability_score NUMERIC, overall_score NUMERIC,
        priority_level TEXT, main_topic TEXT, content_type TEXT,
        target_audience TEXT, key_findings TEXT, improvement_suggestions TEXT,
        missing_information TEXT, quality_issues TEXT, created_at TIMESTAMPTZ
    )
    ON CONFLICT DO NOTHING;

    GET DIAGNOSTICS record_count = ROW_COUNT;
    RAISE NOTICE 'Migrated % analysis_results', record_count;

END $$;
