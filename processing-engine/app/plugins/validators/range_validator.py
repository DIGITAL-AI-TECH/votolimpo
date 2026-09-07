from __future__ import annotations

from app.plugins.protocols import ValidationResult


class RangeValidator:
    """Validates that numeric fields in the output are within expected ranges.

    The schema dict must contain a 'range_rules' key mapping field names to
    dicts with optional 'min' and/or 'max' keys.

    Example schema:
        {
            "range_rules": {
                "age":   {"min": 0, "max": 150},
                "score": {"min": 0, "max": 100},
            }
        }

    If 'range_rules' is absent from schema, validation passes (nothing to check).
    """

    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult:
        range_rules: dict[str, dict] | None = schema.get("range_rules")

        if not range_rules:
            return ValidationResult(valid=True)

        errors: list[str] = []

        for field_name, rule in range_rules.items():
            if field_name not in output:
                errors.append(f"{field_name}: field not found")
                continue

            value = output[field_name]
            min_val = rule.get("min")
            max_val = rule.get("max")

            out_of_range = (min_val is not None and value < min_val) or (
                max_val is not None and value > max_val
            )
            if out_of_range:
                errors.append(f"{field_name}: value {value} out of range [{min_val}, {max_val}]")

        if errors:
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(valid=True)
