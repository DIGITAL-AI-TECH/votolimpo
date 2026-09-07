from __future__ import annotations

from app.plugins.protocols import ValidationResult


class GroundingValidator:
    """Validates that key output values are grounded in the source text.

    For each string field (or only fields listed in schema['grounding_fields']),
    checks whether the value appears (case-insensitive) in source_text.
    Fields whose values are not found produce an error entry.
    """

    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult:
        errors: list[str] = []
        source_lower = source_text.lower()

        grounding_fields: list[str] | None = schema.get("grounding_fields")

        for field_name, value in output.items():
            if not isinstance(value, str):
                continue
            if grounding_fields is not None and field_name not in grounding_fields:
                continue
            if value.lower() not in source_lower:
                errors.append(f"{field_name}: value not grounded in source text")

        if errors:
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(valid=True)
