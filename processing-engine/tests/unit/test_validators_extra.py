"""Unit tests for GroundingValidator, RangeValidator and CompositeValidator."""
from __future__ import annotations

from app.plugins.protocols import ValidationResult
from app.plugins.validators.composite import CompositeValidator
from app.plugins.validators.grounding import GroundingValidator
from app.plugins.validators.range_validator import RangeValidator

# ---------------------------------------------------------------------------
# GroundingValidator
# ---------------------------------------------------------------------------

class TestGroundingValidator:
    validator = GroundingValidator()

    def test_grounding_valid(self):
        """Todos os valores string presentes no source_text retornam valid=True."""
        output = {"name": "Alice", "city": "São Paulo"}
        source = "Alice mora em São Paulo e trabalha como engenheira."
        result = self.validator.validate(output, source, {})
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert not result.errors

    def test_grounding_missing_value(self):
        """Valor ausente no source_text deve gerar erro e valid=False."""
        output = {"name": "Bob", "city": "Recife"}
        source = "Bob mora em São Paulo."
        result = self.validator.validate(output, source, {})
        assert result.valid is False
        assert any("city" in e for e in result.errors)
        assert any("not grounded" in e for e in result.errors)

    def test_grounding_case_insensitive(self):
        """A comparacao deve ser case-insensitive."""
        output = {"name": "ALICE"}
        source = "alice trabalha aqui."
        result = self.validator.validate(output, source, {})
        assert result.valid is True

    def test_grounding_specific_fields(self):
        """Com grounding_fields definido, apenas esses campos sao verificados."""
        output = {"name": "Carol", "city": "Marte"}  # city nao existe no source
        source = "Carol e uma pessoa incrivel."
        schema = {"grounding_fields": ["name"]}  # so verifica "name"
        result = self.validator.validate(output, source, schema)
        assert result.valid is True
        assert not result.errors

    def test_grounding_specific_fields_failure(self):
        """Campo listado em grounding_fields e ausente no source gera erro."""
        output = {"name": "Diana", "city": "Rio de Janeiro"}
        source = "A cidade e bonita."
        schema = {"grounding_fields": ["name"]}
        result = self.validator.validate(output, source, schema)
        assert result.valid is False
        assert any("name" in e for e in result.errors)

    def test_grounding_non_string_fields_ignored(self):
        """Campos nao-string (int, float, list, etc.) sao ignorados."""
        output = {"score": 99, "active": True, "tags": ["a", "b"], "label": "ok"}
        source = "ok"
        result = self.validator.validate(output, source, {})
        assert result.valid is True

    def test_grounding_empty_output(self):
        """Output vazio sempre retorna valid=True (nada a verificar)."""
        result = self.validator.validate({}, "qualquer texto", {})
        assert result.valid is True


# ---------------------------------------------------------------------------
# RangeValidator
# ---------------------------------------------------------------------------

class TestRangeValidator:
    validator = RangeValidator()

    def test_range_valid(self):
        """Todos os numeros dentro do range retornam valid=True."""
        output = {"age": 30, "score": 85}
        schema = {"range_rules": {"age": {"min": 0, "max": 150}, "score": {"min": 0, "max": 100}}}
        result = self.validator.validate(output, "", schema)
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert not result.errors

    def test_range_below_min(self):
        """Valor abaixo do min gera erro."""
        output = {"age": -1}
        schema = {"range_rules": {"age": {"min": 0, "max": 150}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is False
        assert any("age" in e for e in result.errors)
        assert any("out of range" in e for e in result.errors)

    def test_range_above_max(self):
        """Valor acima do max gera erro."""
        output = {"score": 101}
        schema = {"range_rules": {"score": {"min": 0, "max": 100}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is False
        assert any("score" in e for e in result.errors)
        assert any("out of range" in e for e in result.errors)

    def test_range_missing_field(self):
        """Campo listado em range_rules mas ausente no output gera erro."""
        output = {}
        schema = {"range_rules": {"age": {"min": 0, "max": 150}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is False
        assert any("age" in e for e in result.errors)
        assert any("field not found" in e for e in result.errors)

    def test_range_no_rules(self):
        """Schema sem range_rules retorna valid=True (nada a verificar)."""
        output = {"age": 9999}
        result = self.validator.validate(output, "", {})
        assert result.valid is True

    def test_range_only_min(self):
        """Regra apenas com min: valores no limite ou acima sao validos."""
        output = {"count": 0}
        schema = {"range_rules": {"count": {"min": 0}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is True

    def test_range_only_max(self):
        """Regra apenas com max: valores no limite ou abaixo sao validos."""
        output = {"ratio": 1.0}
        schema = {"range_rules": {"ratio": {"max": 1.0}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is True

    def test_range_boundary_values_inclusive(self):
        """Valores exatamente no min ou max sao validos (limites inclusivos)."""
        output = {"age": 0, "score": 100}
        schema = {"range_rules": {"age": {"min": 0, "max": 150}, "score": {"min": 0, "max": 100}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is True

    def test_range_multiple_errors(self):
        """Multiplos campos fora do range retornam todos os erros."""
        output = {"age": -5, "score": 200}
        schema = {"range_rules": {"age": {"min": 0, "max": 150}, "score": {"min": 0, "max": 100}}}
        result = self.validator.validate(output, "", schema)
        assert result.valid is False
        assert len(result.errors) == 2


# ---------------------------------------------------------------------------
# CompositeValidator
# ---------------------------------------------------------------------------

class TestCompositeValidator:
    def test_composite_all_pass(self):
        """Todos os validators passam -> valid=True sem erros."""
        v1 = GroundingValidator()
        v2 = RangeValidator()
        composite = CompositeValidator(validators=[v1, v2])

        output = {"name": "Eve", "score": 50}
        source = "Eve obteve score 50 no teste."
        schema = {
            "range_rules": {"score": {"min": 0, "max": 100}},
        }
        result = composite.validate(output, source, schema)
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert not result.errors

    def test_composite_one_fails(self):
        """Um validator reprovando torna o resultado invalido com os erros dele."""
        v1 = GroundingValidator()
        v2 = RangeValidator()
        composite = CompositeValidator(validators=[v1, v2])

        # score nao esta no source_text -> GroundingValidator vai reclamar de "city"
        output = {"city": "Narnia", "score": 50}
        source = "A cidade e longe."  # "Narnia" nao esta aqui
        schema = {"range_rules": {"score": {"min": 0, "max": 100}}}

        result = composite.validate(output, source, schema)
        assert result.valid is False
        assert result.errors
        assert any("city" in e for e in result.errors)

    def test_composite_both_fail(self):
        """Quando ambos reprovam, todos os erros sao acumulados."""
        v1 = GroundingValidator()
        v2 = RangeValidator()
        composite = CompositeValidator(validators=[v1, v2])

        output = {"city": "Narnia", "score": 200}
        source = "Texto sem correspondencia."
        schema = {"range_rules": {"score": {"min": 0, "max": 100}}}

        result = composite.validate(output, source, schema)
        assert result.valid is False
        assert any("city" in e for e in result.errors)
        assert any("score" in e for e in result.errors)

    def test_composite_empty_validators(self):
        """Lista vazia de validators retorna valid=True."""
        composite = CompositeValidator(validators=[])
        result = composite.validate({"x": 1}, "src", {})
        assert result.valid is True

    def test_composite_returns_validation_result_instance(self):
        """O retorno deve ser sempre uma instancia de ValidationResult."""
        composite = CompositeValidator(validators=[GroundingValidator()])
        result = composite.validate({}, "", {})
        assert isinstance(result, ValidationResult)


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestNewValidatorsRegistryIntegration:
    def test_all_new_validators_registered(self):
        import app.plugins.validators  # noqa: F401 — dispara o registro
        from app.plugins.registry import list_available

        available = list_available("validator")
        assert "grounding" in available
        assert "range" in available
        assert "composite" in available
