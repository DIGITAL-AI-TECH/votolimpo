"""Tests for validator plugins."""

import pytest

from app.plugins.validators import (
    get_validator,
    JsonSchemaValidator,
    GroundingValidator,
    RangeValidator,
    DateValidator,
    _extract_path,
)


class TestJsonSchemaValidator:
    def test_valid_dict(self):
        v = JsonSchemaValidator()
        assert v.validate({"key": "value"}, "", {}) == []

    def test_invalid_non_dict(self):
        v = JsonSchemaValidator()
        errors = v.validate("not a dict", "", {})
        assert len(errors) == 1
        assert "not a dict" in errors[0]


class TestGroundingValidator:
    def test_last_name_found(self):
        v = GroundingValidator()
        output = {"politicians": [{"name": "Jair Bolsonaro"}]}
        config = {"check_fields": [{"path": "politicians[].name", "strategy": "last_name_in_text"}]}
        errors = v.validate(output, "O presidente Bolsonaro viajou.", config)
        assert len(errors) == 0

    def test_last_name_not_found(self):
        v = GroundingValidator()
        output = {"politicians": [{"name": "Fernando Collor"}]}
        config = {"check_fields": [{"path": "politicians[].name", "strategy": "last_name_in_text"}]}
        errors = v.validate(output, "O presidente Bolsonaro viajou.", config)
        assert len(errors) == 1
        assert "Collor" in errors[0]

    def test_any_word_found(self):
        v = GroundingValidator()
        output = {"entities": [{"name": "Supremo Tribunal Federal"}]}
        config = {"check_fields": [{"path": "entities[].name", "strategy": "any_word_in_text"}]}
        errors = v.validate(output, "O Supremo decidiu nesta terça.", config)
        assert len(errors) == 0

    def test_any_word_not_found(self):
        v = GroundingValidator()
        output = {"entities": [{"name": "TSE"}]}
        config = {"check_fields": [{"path": "entities[].name", "strategy": "any_word_in_text"}]}
        errors = v.validate(output, "O Supremo decidiu nesta terça.", config)
        assert len(errors) == 1

    def test_skips_none_values(self):
        v = GroundingValidator()
        output = {"politicians": [{"name": None}]}
        config = {"check_fields": [{"path": "politicians[].name", "strategy": "last_name_in_text"}]}
        errors = v.validate(output, "Qualquer texto.", config)
        assert len(errors) == 0


class TestRangeValidator:
    def test_in_range(self):
        v = RangeValidator()
        output = {"score": 0.5}
        config = {"fields": ["score"], "min": 0.0, "max": 1.0}
        assert v.validate(output, "", config) == []

    def test_out_of_range(self):
        v = RangeValidator()
        output = {"score": 1.5}
        config = {"fields": ["score"], "min": 0.0, "max": 1.0}
        errors = v.validate(output, "", config)
        assert len(errors) == 1

    def test_nested_field(self):
        v = RangeValidator()
        output = {"veracity_signals": {"source_reputation": 0.8}}
        config = {"fields": ["veracity_signals.source_reputation"], "min": 0.0, "max": 1.0}
        assert v.validate(output, "", config) == []


class TestDateValidator:
    def test_valid_date(self):
        v = DateValidator()
        output = {"published_date": "2025-01-15"}
        config = {"fields": ["published_date"], "no_future": True}
        assert v.validate(output, "", config) == []

    def test_future_date(self):
        v = DateValidator()
        output = {"published_date": "2099-01-01"}
        config = {"fields": ["published_date"], "no_future": True}
        errors = v.validate(output, "", config)
        assert len(errors) == 1
        assert "future" in errors[0]

    def test_invalid_date(self):
        v = DateValidator()
        output = {"published_date": "not-a-date"}
        config = {"fields": ["published_date"]}
        errors = v.validate(output, "", config)
        assert len(errors) == 1
        assert "parseable" in errors[0]

    def test_skips_null(self):
        v = DateValidator()
        output = {"published_date": None}
        config = {"fields": ["published_date"]}
        assert v.validate(output, "", config) == []


class TestExtractPath:
    def test_simple_field(self):
        assert _extract_path({"a": 1}, "a") == [1]

    def test_nested_field(self):
        assert _extract_path({"a": {"b": 2}}, "a.b") == [2]

    def test_array_wildcard(self):
        data = {"items": [{"name": "A"}, {"name": "B"}]}
        assert _extract_path(data, "items[].name") == ["A", "B"]

    def test_star_wildcard(self):
        data = {"items": [{"name": "A"}, {"name": "B"}]}
        assert _extract_path(data, "items.*.name") == ["A", "B"]

    def test_empty_path(self):
        data = {"a": 1}
        assert _extract_path(data, "") == [data]

    def test_missing_field(self):
        assert _extract_path({"a": 1}, "b") == []


class TestGetValidator:
    def test_known_types(self):
        for vtype in ["json_schema", "grounding", "range", "date"]:
            v = get_validator(vtype)
            assert hasattr(v, "validate")

    def test_unknown_falls_back_to_json_schema(self):
        v = get_validator("unknown")
        assert isinstance(v, JsonSchemaValidator)
