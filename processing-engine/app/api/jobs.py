from __future__ import annotations

import hashlib
import json
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_db, verify_api_key
from app.models.item import ItemResult, TokenUsage
from app.models.job import Job, JobCreate, JobListResponse
from app.models.log import ProcessingLog
from app.services.cost_tracker import CostTracker
from app.sql.items import (
    INSERT_ITEM,
    SELECT_ITEMS_BY_JOB,
    SELECT_LOGS_BY_JOB,
    SELECT_LOGS_BY_JOB_AND_STEP,
)
from app.sql.jobs import (
    CHECK_IDEMPOTENCY,
    COUNT_JOBS,
    INSERT_JOB,
    SELECT_JOB_BY_ID,
    SELECT_JOBS,
)
from app.sql.pipelines import SELECT_PIPELINE_BY_ID

router = APIRouter(tags=["Jobs"])


def _record_to_job(record: asyncpg.Record) -> Job:
    """Converte asyncpg.Record em modelo Job."""
    data = dict(record)
    if isinstance(data.get("metadata"), str):
        data["metadata"] = json.loads(data["metadata"])
    return Job.model_validate(data)


def _record_to_item_result(record: asyncpg.Record) -> ItemResult:
    """Converte asyncpg.Record em modelo ItemResult, construindo TokenUsage."""
    data = dict(record)
    if isinstance(data.get("output"), str):
        data["output"] = json.loads(data["output"])
    # Constrói sub-objeto usage a partir das colunas flat
    data["usage"] = TokenUsage(
        prompt_tokens=data.pop("prompt_tokens", 0) or 0,
        completion_tokens=data.pop("completion_tokens", 0) or 0,
        total_tokens=data.pop("total_tokens", 0) or 0,
        cost_usd=float(data.pop("cost_usd", 0) or 0),
    )
    return ItemResult.model_validate(data)


def _record_to_log(record: asyncpg.Record) -> ProcessingLog:
    """Converte asyncpg.Record em modelo ProcessingLog."""
    data = dict(record)
    if isinstance(data.get("metadata"), str):
        data["metadata"] = json.loads(data["metadata"])
    return ProcessingLog.model_validate(data)


def _compute_hash(value: str | None) -> str | None:
    """Computa SHA-256 hex do valor, ou None se ausente."""
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post(
    "/jobs",
    response_model=Job,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo job de processamento",
)
async def create_job(
    payload: JobCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> Job:
    # Verifica se o pipeline existe
    pipeline_record = await conn.fetchrow(SELECT_PIPELINE_BY_ID, payload.pipeline_id)
    if pipeline_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{payload.pipeline_id}' não encontrado.",
        )

    # Verifica budget do pipeline antes de criar o job
    cost_tracker = CostTracker()
    budget_status = await cost_tracker.check_budget(conn, payload.pipeline_id)
    if budget_status.get("is_exceeded"):
        raise HTTPException(
            status_code=429,
            detail=f"Budget limit reached for pipeline '{pipeline_record['name']}'. "
            f"Current: ${budget_status['current_cost']:.4f} / "
            f"Limit: ${budget_status['budget_limit']:.2f}",
        )

    # Verifica idempotência
    if payload.idempotency_key:
        existing_id = await conn.fetchval(CHECK_IDEMPOTENCY, payload.idempotency_key)
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job com idempotency_key '{payload.idempotency_key}' já existe. job_id={existing_id}",
            )

    # Insere o job
    job_record = await conn.fetchrow(
        INSERT_JOB,
        payload.pipeline_id,  # $1
        pipeline_record["version"],  # $2
        len(payload.items),  # $3
        payload.idempotency_key,  # $4
        payload.priority,  # $5
        json.dumps(payload.metadata) if payload.metadata else None,  # $6
        payload.override_model,  # $7
        payload.skip_dedup,  # $8
        payload.skip_cache,  # $9
        payload.dry_run,  # $10
        payload.callback_url,  # $11
    )

    job = _record_to_job(job_record)

    # Insere os itens do job
    for item in payload.items:
        await conn.execute(
            INSERT_ITEM,
            job.id,  # $1
            payload.pipeline_id,  # $2
            item.source_url,  # $3
            item.content,  # $4
            item.content_type,  # $5
            json.dumps(item.metadata) if item.metadata else None,  # $6
            _compute_hash(item.source_url),  # $7
            _compute_hash(item.content),  # $8
        )

    return job


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="Listar jobs com filtros opcionais",
)
async def list_jobs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    pipeline_id: Annotated[
        uuid.UUID | None, Query(description="Filtrar por pipeline")
    ] = None,
    status: Annotated[str | None, Query(description="Filtrar por status")] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Máximo de resultados")] = 20,
    offset: Annotated[int, Query(ge=0, description="Offset para paginação")] = 0,
) -> JobListResponse:
    records = await conn.fetch(SELECT_JOBS, pipeline_id, status, limit, offset)
    total: int = await conn.fetchval(COUNT_JOBS, pipeline_id, status)
    return JobListResponse(
        items=[_record_to_job(r) for r in records],
        total=total,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=Job,
    summary="Obter detalhes de um job",
)
async def get_job(
    job_id: uuid.UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> Job:
    record = await conn.fetchrow(SELECT_JOB_BY_ID, job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        )
    return _record_to_job(record)


@router.get(
    "/jobs/{job_id}/result",
    summary="Obter resultado de um job com todos os itens processados",
)
async def get_job_result(
    job_id: uuid.UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> dict:
    job_record = await conn.fetchrow(SELECT_JOB_BY_ID, job_id)
    if job_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        )

    item_records = await conn.fetch(SELECT_ITEMS_BY_JOB, job_id)
    items = [_record_to_item_result(r) for r in item_records]

    return {
        "job_id": str(job_id),
        "status": job_record["status"],
        "items": [i.model_dump() for i in items],
    }


@router.get(
    "/jobs/{job_id}/logs",
    response_model=list[ProcessingLog],
    summary="Obter logs de processamento de um job",
)
async def get_job_logs(
    job_id: uuid.UUID,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
    step: Annotated[
        str | None,
        Query(
            description="Filtrar por step (ingest, dedup, process, validate, persist)"
        ),
    ] = None,
) -> list[ProcessingLog]:
    job_record = await conn.fetchrow(SELECT_JOB_BY_ID, job_id)
    if job_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' não encontrado.",
        )

    if step is not None:
        records = await conn.fetch(SELECT_LOGS_BY_JOB_AND_STEP, job_id, step)
    else:
        records = await conn.fetch(SELECT_LOGS_BY_JOB, job_id)

    return [_record_to_log(r) for r in records]
