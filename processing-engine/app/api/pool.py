from __future__ import annotations

import hashlib
import json
import uuid
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_db, verify_api_key
from app.models.pool import (
    PoolIngestItem,
    PoolIngestRequest,
    PoolIngestResponse,
    PoolPipelineStatus,
    PoolRejection,
    PoolSingleIngestRequest,
    PoolSingleIngestResponse,
    PoolStatusResponse,
)
from app.sql.pipelines import SELECT_PIPELINE_BY_ID
from app.sql.pool import (
    CHECK_URL_HASH_EXISTS,
    COUNT_PENDING_TOTAL,
    GET_POOL_STATUS,
    INSERT_POOL_ITEM,
)

router = APIRouter(tags=["Pool"])


def _compute_hash(value: str | None) -> str | None:
    """Compute SHA-256 hash of a string, or None if input is None."""
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _ingest_items(
    conn: asyncpg.Connection,
    pipeline_id: uuid.UUID,
    items: list[PoolIngestItem],
    source_id: str | None,
    batch_ref: str | None,
    priority: int,
) -> PoolIngestResponse:
    """Core ingestion logic shared by batch and single endpoints."""
    # Validate pipeline exists
    pipeline = await conn.fetchrow(SELECT_PIPELINE_BY_ID, pipeline_id)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' not found.",
        )

    accepted_ids: list[uuid.UUID] = []
    rejections: list[PoolRejection] = []

    async with conn.transaction():
        for idx, item in enumerate(items):
            url_hash = _compute_hash(item.source_url)
            content_hash = _compute_hash(item.content)

            # Check URL dedup
            if url_hash is not None:
                existing_id = await conn.fetchval(CHECK_URL_HASH_EXISTS, url_hash, pipeline_id)
                if existing_id is not None:
                    rejections.append(
                        PoolRejection(
                            index=idx,
                            reason="duplicate_url",
                            existing_pool_id=existing_id,
                        )
                    )
                    continue

            # Insert accepted item
            pool_id = await conn.fetchval(
                INSERT_POOL_ITEM,
                pipeline_id,  # $1
                item.source_url,  # $2
                item.content,  # $3
                item.content_type,  # $4
                json.dumps(item.metadata) if item.metadata else "{}",  # $5
                url_hash,  # $6
                content_hash,  # $7
                "pending",  # $8
                priority,  # $9
                source_id,  # $10
                batch_ref,  # $11
            )
            accepted_ids.append(pool_id)

    return PoolIngestResponse(
        accepted=len(accepted_ids),
        rejected=len(rejections),
        pool_ids=accepted_ids,
        rejections=rejections,
    )


@router.post(
    "/pool/ingest",
    response_model=PoolIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deposit items into pool for processing",
)
async def pool_ingest(
    payload: PoolIngestRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> PoolIngestResponse:
    return await _ingest_items(
        conn=conn,
        pipeline_id=payload.pipeline_id,
        items=payload.items,
        source_id=payload.source_id,
        batch_ref=payload.batch_ref,
        priority=payload.priority,
    )


@router.post(
    "/pool/ingest/single",
    response_model=PoolSingleIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Deposit single item into pool",
)
async def pool_ingest_single(
    payload: PoolSingleIngestRequest,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> PoolSingleIngestResponse:
    item = PoolIngestItem(
        source_url=payload.source_url,
        content=payload.content,
        content_type=payload.content_type,
        metadata=payload.metadata,
    )

    result = await _ingest_items(
        conn=conn,
        pipeline_id=payload.pipeline_id,
        items=[item],
        source_id=payload.source_id,
        batch_ref=None,
        priority=0,
    )

    if result.rejected > 0:
        rejection = result.rejections[0]
        return PoolSingleIngestResponse(
            pool_id=None,
            status="duplicate",
            existing_pool_id=rejection.existing_pool_id,
        )

    return PoolSingleIngestResponse(
        pool_id=result.pool_ids[0],
        status="accepted",
    )


@router.get(
    "/pool/status",
    response_model=PoolStatusResponse,
    summary="Pool ingestion status",
)
async def pool_status(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    _key: Annotated[str, Depends(verify_api_key)],
) -> PoolStatusResponse:
    pending_total: int = await conn.fetchval(COUNT_PENDING_TOTAL) or 0

    records = await conn.fetch(GET_POOL_STATUS)
    by_pipeline = [
        PoolPipelineStatus(
            pipeline_id=r["pipeline_id"],
            pipeline_name=r["pipeline_name"],
            pending=r["pending"],
            oldest_pending=r["oldest_pending"],
        )
        for r in records
    ]

    return PoolStatusResponse(
        pending_total=pending_total,
        by_pipeline=by_pipeline,
    )
