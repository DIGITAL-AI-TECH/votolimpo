from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.pipeline import Pipeline, PipelineCreate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_VALID: dict = {
    "name": "test-pipeline",
    "system_prompt": "Extract data from text.",
    "output_schema": {
        "type": "object",
        "properties": {"title": {"type": "string"}},
    },
}


# ---------------------------------------------------------------------------
# PipelineCreate — campos obrigatórios
# ---------------------------------------------------------------------------


def test_pipeline_create_with_all_required_fields() -> None:
    """PipelineCreate aceita os três campos obrigatórios."""
    p = PipelineCreate(**MINIMAL_VALID)
    assert p.name == "test-pipeline"
    assert p.system_prompt == "Extract data from text."
    assert p.output_schema["type"] == "object"


def test_pipeline_create_missing_name_raises() -> None:
    """Ausência de 'name' deve lançar ValidationError."""
    data = {k: v for k, v in MINIMAL_VALID.items() if k != "name"}
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("name",) for e in errors)


def test_pipeline_create_missing_system_prompt_raises() -> None:
    """Ausência de 'system_prompt' deve lançar ValidationError."""
    data = {k: v for k, v in MINIMAL_VALID.items() if k != "system_prompt"}
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("system_prompt",) for e in errors)


def test_pipeline_create_missing_output_schema_raises() -> None:
    """Ausência de 'output_schema' deve lançar ValidationError."""
    data = {k: v for k, v in MINIMAL_VALID.items() if k != "output_schema"}
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**data)
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("output_schema",) for e in errors)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_pipeline_create_defaults_applied() -> None:
    """Valores padrão devem ser aplicados quando campos opcionais são omitidos."""
    p = PipelineCreate(**MINIMAL_VALID)

    assert p.ingestor_type == "auto"
    assert p.max_content_chars == 100_000
    assert p.dedup_strategy == "hash"
    assert p.dedup_threshold == pytest.approx(0.90)
    assert p.llm_provider == "openai"
    assert p.llm_model == "gpt-4.1-mini"
    assert p.llm_temperature == pytest.approx(0.0)
    assert p.llm_seed == 42
    assert p.llm_max_tokens == 16_384
    assert p.validators == ["schema"]
    assert p.sink_type == "postgresql"
    assert p.sink_config == {}
    assert p.max_concurrent == 5
    assert p.rate_limit_rpm == 60
    assert p.budget_limit_usd is None
    assert p.budget_period == "month"
    assert p.max_retries == 3
    assert p.cache_ttl_hours == 720


def test_pipeline_create_description_defaults_none() -> None:
    p = PipelineCreate(**MINIMAL_VALID)
    assert p.description is None


# ---------------------------------------------------------------------------
# Validadores de enum
# ---------------------------------------------------------------------------


def test_invalid_ingestor_type_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**{**MINIMAL_VALID, "ingestor_type": "xml"})
    assert any("ingestor_type" in str(e["loc"]) for e in exc_info.value.errors())


def test_invalid_dedup_strategy_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**{**MINIMAL_VALID, "dedup_strategy": "fuzzy"})
    assert any("dedup_strategy" in str(e["loc"]) for e in exc_info.value.errors())


def test_invalid_budget_period_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PipelineCreate(**{**MINIMAL_VALID, "budget_period": "year"})
    assert any("budget_period" in str(e["loc"]) for e in exc_info.value.errors())


def test_valid_ingestor_types_accepted() -> None:
    for t in ("html", "pdf", "text", "json", "auto"):
        p = PipelineCreate(**{**MINIMAL_VALID, "ingestor_type": t})
        assert p.ingestor_type == t


def test_valid_dedup_strategies_accepted() -> None:
    for s in ("hash", "semantic", "composite", "none"):
        p = PipelineCreate(**{**MINIMAL_VALID, "dedup_strategy": s})
        assert p.dedup_strategy == s


# ---------------------------------------------------------------------------
# Constraints numéricos
# ---------------------------------------------------------------------------


def test_llm_temperature_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineCreate(**{**MINIMAL_VALID, "llm_temperature": 3.0})


def test_max_concurrent_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineCreate(**{**MINIMAL_VALID, "max_concurrent": 51})


def test_max_retries_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        PipelineCreate(**{**MINIMAL_VALID, "max_retries": 11})


# ---------------------------------------------------------------------------
# Pipeline (response model)
# ---------------------------------------------------------------------------


def test_pipeline_response_model_includes_server_fields() -> None:
    """Pipeline (response) deve aceitar campos gerados pelo banco."""
    now = datetime.now(tz=timezone.utc)
    data = {
        **MINIMAL_VALID,
        "id": uuid.uuid4(),
        "version": 1,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    p = Pipeline.model_validate(data)
    assert isinstance(p.id, uuid.UUID)
    assert p.version == 1
    assert p.is_active is True
    assert p.created_at == now


def test_pipeline_response_model_version_increments() -> None:
    """Garante que version é um inteiro positivo e pode representar incremento."""
    now = datetime.now(tz=timezone.utc)
    data = {
        **MINIMAL_VALID,
        "id": uuid.uuid4(),
        "version": 5,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    p = Pipeline.model_validate(data)
    assert p.version == 5
