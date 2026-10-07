from __future__ import annotations

import json
import logging

import jsonschema

from app.plugins.protocols import ValidationResult

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates pipeline output against a JSON Schema.

    Uses jsonschema.validate() for full JSON Schema Draft 7 validation.
    Returns ValidationResult(valid=True) on success or
    ValidationResult(valid=False, errors=[...]) with all validation errors.

    The ``schema`` argument is the validator's config dict (``ValidatorEntry.config``).
    The orchestrator injects ``output_schema`` from the pipeline config into this dict
    when the validator type is "schema", so the resolution order is:

    1. ``schema["output_schema"]`` — injected by orchestrator from pipeline.output_schema.
    2. The ``schema`` dict itself, if it looks like a JSON Schema (has "type" or "properties").
    3. Empty / missing — log a warning and skip (explicit pass-through, not silent NO-OP).

    An empty ``{}`` schema always passes jsonschema.validate() silently, which gives
    false confidence that validation is running. We make the no-schema case explicit.
    """

    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult:
        # Ensure schema is a dict (asyncpg returns JSONB as string)
        if isinstance(schema, str):
            schema = json.loads(schema)

        # Resolve the actual JSON Schema to validate against.
        # Priority 1: output_schema injected by orchestrator into config dict.
        resolved_schema = schema.get("output_schema") if isinstance(schema, dict) else None

        # Priority 2: the config dict itself looks like a JSON Schema.
        if not resolved_schema and isinstance(schema, dict):
            if schema.get("type") or schema.get("properties") or schema.get("$schema"):
                resolved_schema = schema

        # No usable schema — warn and skip (explicit, not silent).
        if not resolved_schema:
            logger.warning(
                "SchemaValidator: no output_schema configured for this pipeline — "
                "skipping schema validation (pass-through). "
                "Set output_schema in the pipeline YAML to enable."
            )
            return ValidationResult(valid=True)

        errors: list[str] = []

        try:
            validator = jsonschema.Draft7Validator(resolved_schema)
            for error in sorted(
                validator.iter_errors(output), key=lambda e: list(e.path)
            ):
                # Build a readable path like "field.subfield"
                path = ".".join(str(p) for p in error.path) if error.path else "<root>"
                errors.append(f"{path}: {error.message}")
        except Exception as exc:
            # Unexpected validation framework error
            errors.append(f"Schema validation error: {exc}")

        if errors:
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(valid=True)
