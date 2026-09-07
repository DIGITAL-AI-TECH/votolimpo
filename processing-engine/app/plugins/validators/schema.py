from __future__ import annotations

import jsonschema

from app.plugins.protocols import ValidationResult


class SchemaValidator:
    """Validates pipeline output against a JSON Schema.

    Uses jsonschema.validate() for full JSON Schema Draft 7 validation.
    Returns ValidationResult(valid=True) on success or
    ValidationResult(valid=False, errors=[...]) with all validation errors.
    """

    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult:
        errors: list[str] = []

        try:
            validator = jsonschema.Draft7Validator(schema)
            for error in sorted(validator.iter_errors(output), key=lambda e: list(e.path)):
                # Build a readable path like "field.subfield"
                path = ".".join(str(p) for p in error.path) if error.path else "<root>"
                errors.append(f"{path}: {error.message}")
        except Exception as exc:
            # Unexpected validation framework error
            errors.append(f"Schema validation error: {exc}")

        if errors:
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(valid=True)
