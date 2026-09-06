"""Create calculate_call_cost() and check_budget() PostgreSQL functions

Revision ID: 010
Revises: 009
Create Date: 2026-09-06
"""
from alembic import op

# revision identifiers, used by Alembic
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION processing_engine.calculate_call_cost(
            p_provider TEXT,
            p_model TEXT,
            p_prompt_tokens INTEGER,
            p_completion_tokens INTEGER
        ) RETURNS REAL AS $$
        DECLARE
            v_input_price REAL;
            v_output_price REAL;
        BEGIN
            SELECT input_price_per_million_tokens, output_price_per_million_tokens
            INTO v_input_price, v_output_price
            FROM processing_engine.model_pricing
            WHERE provider = p_provider AND model = p_model AND is_active = true
            LIMIT 1;

            IF v_input_price IS NULL THEN
                RAISE WARNING 'No pricing found for %/%, using 0', p_provider, p_model;
                RETURN 0.0;
            END IF;

            RETURN (p_prompt_tokens * v_input_price / 1000000.0)
                 + (p_completion_tokens * v_output_price / 1000000.0);
        END;
        $$ LANGUAGE plpgsql STABLE
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION processing_engine.check_budget(
            p_pipeline_id UUID
        ) RETURNS TABLE(current_cost REAL, budget_limit REAL, pct_used REAL, is_exceeded BOOLEAN) AS $$
        DECLARE
            v_budget REAL;
            v_period TEXT;
            v_start TIMESTAMPTZ;
            v_cost REAL;
        BEGIN
            SELECT p.budget_limit_usd, p.budget_period
            INTO v_budget, v_period
            FROM processing_engine.pipelines p
            WHERE p.id = p_pipeline_id;

            IF v_budget IS NULL THEN
                RETURN QUERY SELECT 0.0::REAL, NULL::REAL, 0.0::REAL, false;
                RETURN;
            END IF;

            v_start := CASE v_period
                WHEN 'day' THEN date_trunc('day', now())
                WHEN 'week' THEN date_trunc('week', now())
                WHEN 'month' THEN date_trunc('month', now())
                ELSE date_trunc('month', now())
            END;

            SELECT COALESCE(SUM(l.cost_usd), 0.0)
            INTO v_cost
            FROM processing_engine.llm_call_log l
            WHERE l.pipeline_id = p_pipeline_id
              AND l.created_at >= v_start
              AND l.status = 'success';

            RETURN QUERY SELECT v_cost, v_budget, (v_cost / v_budget * 100.0), (v_cost >= v_budget);
        END;
        $$ LANGUAGE plpgsql STABLE
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS processing_engine.check_budget(UUID)")
    op.execute("""
        DROP FUNCTION IF EXISTS processing_engine.calculate_call_cost(TEXT, TEXT, INTEGER, INTEGER)
    """)
