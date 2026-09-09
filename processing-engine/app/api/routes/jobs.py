"""Job submission and status endpoints."""

import json
import uuid

from fastapi import APIRouter, HTTPException

from ...core.models import ProcessingJob, JobResult
from ...core.orchestrator import submit_job
from ...storage.database import get_pool

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """Processing engine statistics (authenticated — behind /v1 auth)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        jobs = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'processing') AS processing,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE status = 'partial') AS partial,
                COALESCE(SUM(total_cost_usd), 0) AS total_cost_usd,
                COUNT(*) AS total_jobs
            FROM processing_engine.jobs
        """)
        items = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                COUNT(*) FILTER (WHERE cached = true) AS cached,
                AVG(duration_ms) FILTER (WHERE status = 'completed') AS avg_duration_ms
            FROM processing_engine.job_items
        """)

    return {
        "jobs": dict(jobs) if jobs else {},
        "items": {
            "completed": items["completed"] if items else 0,
            "failed": items["failed"] if items else 0,
            "cached": items["cached"] if items else 0,
            "avg_duration_ms": round(items["avg_duration_ms"] or 0, 1) if items else 0,
        },
    }


@router.post("/jobs", status_code=202)
async def create_job(job: ProcessingJob):
    """Submit a new processing job."""
    job_id = str(uuid.uuid4())

    job_data = {
        "job_id": job_id,
        "pipeline_id": job.pipeline_id,
        "items": [
            {
                "item_id": str(uuid.uuid4()),
                "content": item.content,
                "content_type": item.content_type,
                "source_url": item.source_url,
                "metadata": item.metadata or {},
            }
            for item in job.items
        ],
        "priority": job.priority,
        "callback_url": job.callback_url,
        "idempotency_key": job.idempotency_key,
    }

    result_id = await submit_job(job_data)
    return {"job_id": result_id, "status": "pending", "total_items": len(job.items)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job status and summary."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM processing_engine.jobs WHERE id = $1", job_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": row["id"],
        "pipeline_id": row["pipeline_id"],
        "status": row["status"],
        "priority": row["priority"],
        "total_items": row["total_items"],
        "completed_items": row["completed_items"],
        "failed_items": row["failed_items"],
        "total_cost_usd": float(row["total_cost_usd"] or 0),
        "total_duration_ms": row["total_duration_ms"] or 0,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


@router.get("/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Get full job result with all item outputs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT * FROM processing_engine.jobs WHERE id = $1", job_id
        )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        items = await conn.fetch(
            "SELECT * FROM processing_engine.job_items WHERE job_id = $1 ORDER BY created_at",
            job_id,
        )

    return {
        "job_id": job["id"],
        "status": job["status"],
        "items": [
            {
                "item_id": item["id"],
                "status": item["status"],
                "output": json.loads(item["output"]) if item["output"] else None,
                "cached": item["cached"],
                "dedup_result": item["dedup_result"],
                "cost_usd": float(item["cost_usd"] or 0),
                "duration_ms": item["duration_ms"] or 0,
                "error": item["error"],
                "validation_errors": json.loads(item["validation_errors"]) if item["validation_errors"] else None,
            }
            for item in items
        ],
        "total_cost_usd": float(job["total_cost_usd"] or 0),
        "total_duration_ms": job["total_duration_ms"] or 0,
    }
