from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.deps import get_db, verify_api_key
from app.models.cost import ModelPricing, ModelPricingCreate
from app.sql.costs import SELECT_ALL_PRICING, UPSERT_PRICING

router = APIRouter(tags=["Pricing"])


def _record_to_pricing(record: asyncpg.Record) -> ModelPricing:
    return ModelPricing.model_validate(dict(record))


@router.get("/pricing", response_model=list[ModelPricing], summary="Listar preços de modelos LLM")
async def list_pricing(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    active_only: Annotated[bool | None, Query(description="Filtrar apenas ativos")] = True,
) -> list[ModelPricing]:
    records = await conn.fetch(SELECT_ALL_PRICING, active_only)
    return [_record_to_pricing(r) for r in records]


@router.post("/pricing", response_model=ModelPricing, summary="Criar/atualizar preço de modelo")
async def upsert_pricing(
    payload: ModelPricingCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> ModelPricing:
    record = await conn.fetchrow(
        UPSERT_PRICING,
        payload.provider,
        payload.model,
        payload.input_price_per_million_tokens,
        payload.output_price_per_million_tokens,
        payload.is_active,
        payload.effective_from,
    )
    return _record_to_pricing(record)
