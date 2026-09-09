"""Validator plugins — validate LLM output before persisting."""

import logging
from datetime import datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class Validator(Protocol):
    """Protocol for validator plugins."""

    def validate(self, output: dict, original_content: str, config: dict) -> list[str]:
        """Validate output. Returns list of error strings (empty = valid)."""
        ...


class JsonSchemaValidator:
    """Validate output matches expected structure (basic type checks)."""

    def validate(self, output: dict, original_content: str, config: dict) -> list[str]:
        errors = []
        if not isinstance(output, dict):
            errors.append("Output is not a dict")
        return errors


class GroundingValidator:
    """Validate that extracted entities actually appear in source text."""

    def validate(self, output: dict, original_content: str, config: dict) -> list[str]:
        errors = []
        content_lower = original_content.lower()
        check_fields = config.get("check_fields", [])

        for field_check in check_fields:
            path = field_check.get("path", "")
            strategy = field_check.get("strategy", "any_word_in_text")
            values = _extract_path(output, path)

            for val in values:
                if not val or not isinstance(val, str):
                    continue

                if strategy == "last_name_in_text":
                    # Check if last name appears in text
                    parts = val.strip().split()
                    if parts:
                        last_name = parts[-1].lower()
                        if last_name not in content_lower:
                            errors.append(f"Grounding: '{val}' last name not in text")
                elif strategy == "any_word_in_text":
                    # Check if any word (3+ chars) appears in text
                    words = [w.lower() for w in val.split() if len(w) >= 3]
                    if words and not any(w in content_lower for w in words):
                        errors.append(f"Grounding: '{val}' not grounded in text")

        return errors


class RangeValidator:
    """Validate numeric fields are within expected range."""

    def validate(self, output: dict, original_content: str, config: dict) -> list[str]:
        errors = []
        fields = config.get("fields", [])
        min_val = config.get("min", 0.0)
        max_val = config.get("max", 1.0)

        for field_path in fields:
            values = _extract_path(output, field_path)
            for val in values:
                if isinstance(val, (int, float)) and not (min_val <= val <= max_val):
                    errors.append(f"Range: {field_path} value {val} not in [{min_val}, {max_val}]")

        return errors


class DateValidator:
    """Validate date fields are parseable and not in the future."""

    def validate(self, output: dict, original_content: str, config: dict) -> list[str]:
        errors = []
        fields = config.get("fields", [])
        no_future = config.get("no_future", True)

        for field_path in fields:
            values = _extract_path(output, field_path)
            for val in values:
                if not val or not isinstance(val, str):
                    continue
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    if no_future and dt.date() > datetime.now().date():
                        errors.append(f"Date: {field_path} is in the future: {val}")
                except (ValueError, TypeError):
                    errors.append(f"Date: {field_path} not parseable: {val}")

        return errors


def _extract_path(data: dict, path: str) -> list[Any]:
    """Extract values from a nested dict using dot/bracket path notation.

    Supports: "field", "field.sub", "field[].sub", "field.*.sub"
    """
    if not path:
        return [data]

    parts = path.replace("[]", ".*").split(".")
    current = [data]

    for part in parts:
        next_vals = []
        for item in current:
            if part == "*":
                if isinstance(item, dict):
                    next_vals.extend(item.values())
                elif isinstance(item, list):
                    next_vals.extend(item)
            elif isinstance(item, dict) and part in item:
                next_vals.append(item[part])
        current = next_vals

    return current


# Registry
VALIDATORS: dict[str, type] = {
    "json_schema": JsonSchemaValidator,
    "grounding": GroundingValidator,
    "range": RangeValidator,
    "date": DateValidator,
}


def get_validator(validator_type: str) -> Validator:
    """Get a validator by type name."""
    cls = VALIDATORS.get(validator_type, JsonSchemaValidator)
    return cls()
