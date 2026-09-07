"""Unit tests for validator plugins."""
from __future__ import annotations

import pytest

from app.plugins.protocols import ValidationResult
from app.plugins.validators.schema import SchemaValidator


# ---------------------------------------------------------------------------
# SchemaValidator
# ---------------------------------------------------------------------------

class TestSchemaValidator:
    validator = SchemaValidator()

    # Reusable schema for most tests
    SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "score": {"type": "number"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["name", "score"],
        "additionalProperties": False,
    }

    def test_valid_output_passes(self):
        output = {"name": "Alice", "score": 0.95}
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert not result.errors

    def test_valid_output_with_optional_field_passes(self):
        output = {"name": "Bob", "score": 0.5, "tags": ["foo", "bar"]}
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is True

    def test_missing_required_field_fails(self):
        output = {"name": "Carol"}  # missing "score"
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is False
        assert result.errors
        assert any("score" in e for e in result.errors)

    def test_wrong_type_fails(self):
        output = {"name": 123, "score": 0.9}  # name should be string
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is False
        assert result.errors
        assert any("name" in e for e in result.errors)

    def test_additional_property_fails(self):
        output = {"name": "Dave", "score": 1.0, "extra": "not allowed"}
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is False
        assert result.errors

    def test_empty_output_fails_with_required_fields(self):
        output: dict = {}
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is False
        assert len(result.errors) >= 2  # both "name" and "score" are required

    def test_wrong_array_item_type_fails(self):
        output = {"name": "Eve", "score": 0.8, "tags": [1, 2, 3]}  # should be strings
        result = self.validator.validate(output, "source text", self.SCHEMA)
        assert result.valid is False
        assert result.errors

    def test_empty_schema_accepts_everything(self):
        result = self.validator.validate({"anything": True}, "source", {})
        assert result.valid is True

    def test_source_text_not_used_in_schema_validation(self):
        """SchemaValidator does not use source_text — any value is fine."""
        output = {"name": "Frank", "score": 0.7}
        result = self.validator.validate(output, "", self.SCHEMA)
        assert result.valid is True

    def test_multiple_errors_reported(self):
        output = {"name": 99, "extra_field": "oops"}  # wrong type + missing required + extra
        result = self.validator.validate(output, "source", self.SCHEMA)
        assert result.valid is False
        assert len(result.errors) >= 2

    def test_nested_schema_validation(self):
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                    },
                    "required": ["city"],
                }
            },
            "required": ["address"],
        }
        # Missing nested required field
        output = {"address": {"country": "BR"}}
        result = self.validator.validate(output, "src", schema)
        assert result.valid is False
        assert any("city" in e for e in result.errors)

    def test_returns_validation_result_instance(self):
        result = self.validator.validate({}, "src", {"type": "object"})
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestValidatorRegistryIntegration:
    def test_schema_validator_registered(self):
        import app.plugins.validators  # noqa: F401 — triggers registration
        from app.plugins.registry import list_available

        assert "schema" in list_available("validator")
