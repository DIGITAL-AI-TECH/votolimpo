from __future__ import annotations

from app.plugins.protocols import ValidationResult


class CompositeValidator:
    """Chains multiple validators and collects all their errors.

    Each validator must implement validate(output, source_text, schema) ->
    ValidationResult. The composite passes only when every validator passes.
    """

    def __init__(self, validators: list) -> None:
        self.validators = validators

    def validate(
        self,
        output: dict,
        source_text: str,
        schema: dict,
    ) -> ValidationResult:
        all_errors: list[str] = []

        for validator in self.validators:
            result = validator.validate(output, source_text, schema)
            if not result.valid:
                all_errors.extend(result.errors)

        if all_errors:
            return ValidationResult(valid=False, errors=all_errors)
        return ValidationResult(valid=True)
