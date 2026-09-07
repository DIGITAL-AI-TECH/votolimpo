from __future__ import annotations

from app.plugins.registry import register
from app.plugins.validators.composite import CompositeValidator
from app.plugins.validators.grounding import GroundingValidator
from app.plugins.validators.range_validator import RangeValidator
from app.plugins.validators.schema import SchemaValidator

register("validator", "schema", SchemaValidator)
register("validator", "grounding", GroundingValidator)
register("validator", "range", RangeValidator)
register("validator", "composite", CompositeValidator)

__all__ = ["SchemaValidator", "GroundingValidator", "RangeValidator", "CompositeValidator"]
