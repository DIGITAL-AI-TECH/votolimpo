from __future__ import annotations

import json
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_db, verify_api_key
from app.models.pipeline import Pipeline, PipelineCreate
from app.sql.pipelines import (
    CHECK_NAME_UNIQUE,
    INSERT_PIPELINE,
    SELECT_ALL_PIPELINES,
    SELECT_PIPELINE_BY_ID,
    UPDATE_PIPELINE,
)

router = APIRouter(tags=["Pipelines"])

# Sentinel UUID usado na checagem de unicidade ao criar (nenhum registro terá esse id)
_ZERO_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _record_to_pipeline(record: asyncpg.Record) -> Pipeline:
    """Converte asyncpg.Record em modelo Pipeline."""
    data = dict(record)
    # output_schema e sink_config chegam como str JSON do JSONB do asyncpg
    for field in ("output_schema", "sink_config"):
        if isinstance(data.get(field), str):
            data[field] = json.loads(data[field])
    return Pipeline.model_validate(data)


def _pipeline_args(p: PipelineCreate) -> tuple:
    """Retorna a tupla de argumentos posicionais para INSERT/UPDATE."""
    return (
        p.name,
        p.description,
        p.ingestor_type,
        p.max_content_chars,
        p.dedup_strategy,
        p.dedup_threshold,
        p.llm_provider,
        p.llm_model,
        p.llm_temperature,
        p.llm_seed,
        p.llm_max_tokens,
        p.system_prompt,
        json.dumps(p.output_schema),
        p.validators,
        p.sink_type,
        json.dumps(p.sink_config),
        p.max_concurrent,
        p.rate_limit_rpm,
        p.budget_limit_usd,
        p.budget_period,
        p.max_retries,
        p.retry_backoff_base,
        p.cache_ttl_hours,
    )


@router.post(
    "/pipelines",
    response_model=Pipeline,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo pipeline",
)
async def create_pipeline(
    payload: PipelineCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> Pipeline:
    # Verifica unicidade do nome (exclui o próprio registro — usa UUID zero pois ainda não existe)
    name_taken: bool = await conn.fetchval(CHECK_NAME_UNIQUE, payload.name, _ZERO_UUID)
    if name_taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um pipeline com o nome '{payload.name}'.",
        )

    record = await conn.fetchrow(INSERT_PIPELINE, *_pipeline_args(payload))
    return _record_to_pipeline(record)


@router.get(
    "/pipelines",
    response_model=list[Pipeline],
    summary="Listar pipelines registrados",
)
async def list_pipelines(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    active_only: Annotated[
        bool | None, Query(description="Filtrar apenas pipelines ativos")
    ] = True,
) -> list[Pipeline]:
    records = await conn.fetch(SELECT_ALL_PIPELINES, active_only)
    return [_record_to_pipeline(r) for r in records]


@router.get(
    "/pipelines/{pipeline_id}",
    response_model=Pipeline,
    summary="Obter detalhes de um pipeline",
)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> Pipeline:
    record = await conn.fetchrow(SELECT_PIPELINE_BY_ID, pipeline_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' não encontrado.",
        )
    return _record_to_pipeline(record)


@router.put(
    "/pipelines/{pipeline_id}",
    response_model=Pipeline,
    summary="Atualizar pipeline (nova versão)",
)
async def update_pipeline(
    pipeline_id: uuid.UUID,
    payload: PipelineCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> Pipeline:
    # Verifica se pipeline existe
    existing = await conn.fetchrow(SELECT_PIPELINE_BY_ID, pipeline_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' não encontrado.",
        )

    # Verifica unicidade do novo nome (exclui o próprio registro)
    name_taken: bool = await conn.fetchval(CHECK_NAME_UNIQUE, payload.name, pipeline_id)
    if name_taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe outro pipeline com o nome '{payload.name}'.",
        )

    record = await conn.fetchrow(
        UPDATE_PIPELINE,
        pipeline_id,  # $1
        *_pipeline_args(payload),  # $2 … $24
    )
    return _record_to_pipeline(record)
